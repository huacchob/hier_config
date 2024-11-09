from __future__ import annotations

from collections.abc import Iterable, Iterator
from itertools import chain
from logging import getLogger
from re import search
from typing import TYPE_CHECKING

from .base import HConfigBase
from .model import Instance, MatchRule, SetLikeOfStr

if TYPE_CHECKING:
    from hier_config.platforms.driver_base import HConfigDriverBase

    from .root import HConfig


logger = getLogger(__name__)


class HConfigChild(  # noqa: PLR0904  pylint: disable=too-many-instance-attributes
    HConfigBase
):
    __slots__ = (
        "_tags",
        "_text",
        "comments",
        "facts",
        "instances",
        "new_in_config",
        "order_weight",
        "parent",
        "real_indent_level",
    )

    def __init__(self, parent: HConfig | HConfigChild, text: str) -> None:
        super().__init__()
        self.parent = parent
        self._text: str = text.strip()
        self.real_indent_level: int
        # 0 is the default. Positive weights sink while negative weights rise.
        self.order_weight: int = 0
        self._tags: set[str] = set()
        self.comments: set[str] = set()
        self.new_in_config: bool = False
        self.instances: list[Instance] = []
        # To store externally inserted facts
        self.facts: dict = {}  # type: ignore[type-arg]

    def __str__(self) -> str:
        return "\n".join(self.lines(sectional_exiting=True))

    def __repr__(self) -> str:
        return f"HConfigChild(HConfig{'' if self.parent is self.root else 'Child'}, {self.text})"

    def __lt__(self, other: HConfigChild) -> bool:
        return self.order_weight < other.order_weight

    def __hash__(self) -> int:
        return hash(
            (
                self.text,
                # self.tags,
                # self.comments,
                self.new_in_config,
                self.order_weight,
                *self.children,
            )
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HConfigChild):
            return NotImplemented

        if (
            self.text != other.text
            or self.tags != other.tags
            or self.comments != other.comments
            or self.new_in_config != other.new_in_config
        ):
            return False

        if len(self.children) != len(other.children):
            return False

        return all(
            self_child == other_child
            for self_child, other_child in zip(
                sorted(self.children), sorted(other.children), strict=False
            )
        )

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    @property
    def driver(self) -> HConfigDriverBase:
        return self.root.driver

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        """
        Used for when self.text is changed after the object
        is instantiated to rebuild the children dictionary.
        """
        self._text = value.strip()
        self.parent.rebuild_children_dict()

    @property
    def text_without_negation(self) -> str:
        return self.text.removeprefix(self._negation_prefix)

    @property
    def root(self) -> HConfig:
        """Returns the HConfig object at the base of the tree."""
        return self.parent.root

    def lines(self, *, sectional_exiting: bool = False) -> Iterable[str]:
        yield self.cisco_style_text()
        for child in sorted(self.children):
            yield from child.lines(sectional_exiting=sectional_exiting)

        if sectional_exiting and (exit_text := self.sectional_exit):
            yield " " * self.driver.indentation * self.depth() + exit_text

    @property
    def sectional_exit(self) -> str | None:
        for rule in self.driver.sectional_exiting_rules:
            if self.lineage_test(rule.lineage):
                if exit_text := rule.exit_text:
                    return exit_text
                return None

        if not self.children:
            return None

        return "exit"

    def delete_sectional_exit(self) -> None:
        try:
            potential_exit = self.children[-1]
        except IndexError:
            return

        if (exit_text := self.sectional_exit) and exit_text == potential_exit.text:
            potential_exit.delete()

    def depth(self) -> int:
        """Returns the distance to the root HConfig object i.e. indent level."""
        return self.parent.depth() + 1

    def move(self, new_parent: HConfig | HConfigChild) -> None:
        """
        move one HConfigChild object to different HConfig parent object.

        .. code:: python

            hier1 = config_for_platform(host.platform)
            interface1 = hier1.add_child('interface Vlan2')
            interface1.add_child('ip address 10.0.0.1 255.255.255.252')

            hier2 = Hconfig(host)

            interface1.move(hier2)

        :param new_parent: HConfigChild object -> type list
        """
        new_parent.children.append(self)
        new_parent.rebuild_children_dict()
        self.delete()

    def lineage(self) -> Iterator[HConfigChild]:
        """Yields the lineage of parent objects up to, but excluding, the root."""
        yield from self.parent.lineage()
        yield self

    def path(self) -> Iterator[str]:
        """Yields the text attribute of child objects up to, but excluding, the root."""
        for child in self.lineage():
            yield child.text

    def cisco_style_text(
        self, style: str = "without_comments", tag: str | None = None
    ) -> str:
        """Return a Cisco style formated line i.e. indentation_level + text ! comments."""
        comments = []
        if style == "without_comments":
            pass
        elif style == "merged":
            # count the number of instances that have the tag
            instance_count = 0
            instance_comments: set[str] = set()
            for instance in self.instances:
                if tag is None or tag in instance.tags:
                    instance_count += 1
                    instance_comments.update(instance.comments)

            # should the word 'instance' be plural?
            word = "instance" if instance_count == 1 else "instances"

            comments.append(f"{instance_count} {word}")
            comments.extend(instance_comments)
        elif style == "with_comments":
            comments.extend(self.comments)

        comments_str = f" !{', '.join(sorted(comments))}" if comments else ""
        return f"{self.indentation}{self.text}{comments_str}"

    @property
    def indentation(self) -> str:
        return " " * self.driver.indentation * (self.depth() - 1)

    def delete(self) -> None:
        """Delete the current object from its parent."""
        self.parent.delete_child(self)

    def tags_add(self, tag: str | Iterable[str]) -> None:
        """
        Add a tag to self._tags on all leaf nodes.
        """
        if self.is_branch:
            for child in self.children:
                child.tags_add(tag)
        elif isinstance(tag, str):
            self._tags.add(tag)
        else:
            self._tags.update(tag)

    def tags_remove(self, tag: str | Iterable[str]) -> None:
        """
        Remove a tag from self._tags on all leaf nodes.
        """
        if self.is_branch:
            for child in self.children:
                child.tags_remove(tag)
        elif isinstance(tag, str):
            self._tags.remove(tag)
        else:
            self._tags.difference_update(tag)

    def negate(self) -> HConfigChild:
        """Negate self.text."""
        if negate_with := self.driver.negation_negate_with_check(self):
            self.text = negate_with
            return self

        if self.negation_default_when_check(self):
            return self._default()

        return self._swap_negation()

    def negation_default_when_check(self, config: HConfigChild) -> bool:
        return any(
            config.lineage_test(rule.lineage)
            for rule in self.driver.negation_default_when_rules
        )

    @property
    def is_leaf(self) -> bool:
        """Returns True if there are no children and is not an instance of HConfig."""
        return not self.is_branch

    @property
    def is_branch(self) -> bool:
        """Returns True if there are children or is an instance of HConfig."""
        return bool(self.children)

    @property
    def tags(self) -> frozenset[str]:
        """Recursive access to tags on all leaf nodes."""
        if self.is_branch:
            found_tags: set[str] = set()
            for child in self.children:
                found_tags.update(child.tags)
            return frozenset(found_tags)

        return frozenset(self._tags)

    @tags.setter
    def tags(self, value: Iterable[str]) -> None:
        """Recursive access to tags on all leaf nodes."""
        if self.is_branch:
            for child in self.children:
                child.tags = value
        else:
            self._tags = set(value)

    def is_idempotent_command(self, other_children: Iterable[HConfigChild]) -> bool:
        """Determine if self.text is an idempotent change."""
        # Avoid list commands from matching as idempotent
        for rule in self.driver.idempotent_commands_avoid_rules:
            if self.lineage_test(rule.lineage):
                return False

        # Handles idempotent acl entry identification
        if self.driver.idempotent_acl_check(self, other_children):
            return True

        # Idempotent command identification
        return bool(self.driver.idempotent_for(self, other_children))

    def sectional_overwrite_no_negate_check(self) -> bool:
        """
        Check self's text to see if negation should be handled by
        overwriting the section without first negating it.
        """
        return any(
            self.lineage_test(rule.lineage)
            for rule in self.driver.sectional_overwrite_no_negate_rules
        )

    def sectional_overwrite_check(self) -> bool:
        """Determines if self.text matches a sectional overwrite rule."""
        return any(
            self.lineage_test(rule.lineage)
            for rule in self.driver.sectional_overwrite_rules
        )

    def overwrite_with(
        self,
        other: HConfigChild,
        delta: HConfig | HConfigChild,
        *,
        negate: bool = True,
    ) -> None:
        """Deletes delta.child[self.text], adds a deep copy of self to delta."""
        if other.children != self.children:
            if negate:
                delta.delete_child_by_text(self.text)
                deleted = delta.add_child(self.text).negate()
                deleted.comments.add("dropping section")
            if self.children:
                delta.delete_child_by_text(self.text)
                new_item = delta.add_deep_copy_of(self)
                new_item.comments.add("re-create section")

    def line_inclusion_test(
        self, include_tags: Iterable[str], exclude_tags: Iterable[str]
    ) -> bool:
        """
        Given the line_tags, include_tags, and exclude_tags,
        determine if the line should be included.
        """
        include_line = False

        if include_tags:
            include_line = bool(self.tags.intersection(include_tags))
        if exclude_tags and (include_line or not include_tags):
            return not bool(self.tags.intersection(exclude_tags))

        return include_line

    @property
    def instance(self) -> Instance:
        return Instance(
            id=id(self),
            comments=frozenset(self.comments),
            tags=frozenset(self.tags),
        )

    def all_children_sorted_by_tags(
        self, include_tags: Iterable[str], exclude_tags: Iterable[str]
    ) -> Iterator[HConfigChild]:
        """Yield all children recursively that match include/exclude tags."""
        if self.is_leaf:
            if self.line_inclusion_test(include_tags, exclude_tags):
                yield self
        else:
            self_iter = iter((self,))
            for child in sorted(self.children):
                included_children = child.all_children_sorted_by_tags(
                    include_tags, exclude_tags
                )
                if peek := next(included_children, None):
                    yield from chain(self_iter, (peek,), included_children)

    def lineage_test(self, rules: tuple[MatchRule, ...]) -> bool:
        """A generic test against a lineage of HConfigChild objects."""
        lineage = tuple(self.lineage())

        return len(rules) == len(lineage) and all(
            child.matches(
                equals=rule.equals,
                startswith=rule.startswith,
                endswith=rule.endswith,
                contains=rule.contains,
                re_search=rule.re_search,
            )
            for (child, rule) in zip(reversed(lineage), reversed(rules), strict=True)
        )

    def matches(  # noqa: PLR0911
        self,
        *,
        equals: str | SetLikeOfStr | None = None,
        startswith: str | tuple[str, ...] | None = None,
        endswith: str | tuple[str, ...] | None = None,
        contains: str | tuple[str, ...] | None = None,
        re_search: str | None = None,
    ) -> bool:
        """
        True if `self.text` matches all the criteria.

        If all args are None, the function will return True.
        If multiple args are provided, then all will need to match in order to return True.
        """
        # Equals filter
        if isinstance(equals, str):
            if self.text != equals:
                return False
        elif (  # pylint: disable=confusing-consecutive-elif
            isinstance(equals, frozenset) and self.text not in equals
        ):
            return False

        # Startswith filter
        if isinstance(startswith, str | tuple) and not self.text.startswith(startswith):
            return False

        # Regex filter
        if isinstance(re_search, str) and not search(re_search, self.text):
            return False

        # The below filters are less commonly used
        # Endswith filter
        if isinstance(endswith, str | tuple) and not self.text.endswith(endswith):
            return False

        # Contains filter
        if isinstance(contains, str):
            if contains not in self.text:
                return False
        elif isinstance(  # pylint: disable=confusing-consecutive-elif
            contains, tuple
        ) and not any(c in self.text for c in contains):
            return False

        return True

    def add_children_deep(self, lines: Iterable[str]) -> HConfigChild:
        """Add child instances of HConfigChild deeply."""
        base = self
        for line in lines:
            base = base.add_child(line)
        return base

    def _swap_negation(self) -> HConfigChild:
        """Swap negation of a `self.text`."""
        if self.text.startswith(self._negation_prefix):
            self.text = self.text_without_negation
        else:
            self.text = f"{self._negation_prefix}{self.text}"

        return self

    def _default(self) -> HConfigChild:
        """Default self.text."""
        self.text = f"default {self.text_without_negation}"
        return self

    @property
    def _child_class(self) -> type[HConfigChild]:
        return HConfigChild

    def _duplicate_child_allowed_check(self) -> bool:
        """Determine if duplicate(identical text) children are allowed under the parent."""
        return any(
            self.lineage_test(rule.lineage)
            for rule in self.driver.parent_allows_duplicate_child_rules
        )
