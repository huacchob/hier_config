from __future__ import annotations

from abc import ABC, abstractmethod
from itertools import chain
from logging import getLogger
from typing import TYPE_CHECKING

from .exceptions import DuplicateChildError

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from .child import HConfigChild
    from .model import MatchRule, SetLikeOfStr
    from .platforms.driver_base import HConfigDriverBase
    from .root import HConfig

logger = getLogger(__name__)


class HConfigBase(ABC):  # noqa: PLR0904
    __slots__ = ("children", "children_dict")

    def __init__(self) -> None:
        self.children: list[HConfigChild] = []
        self.children_dict: dict[str, HConfigChild] = {}

    def __len__(self) -> int:
        return len(tuple(self.all_children()))

    def __bool__(self) -> bool:
        return True

    def __contains__(self, item: str) -> bool:
        return item in self.children_dict

    @abstractmethod
    def __hash__(self) -> int:
        pass

    def __iter__(self) -> Iterator[HConfigChild]:
        return iter(self.children)

    @abstractmethod
    def _duplicate_child_allowed_check(self) -> bool:
        pass

    @property
    @abstractmethod
    def root(self) -> HConfig:
        pass

    @abstractmethod
    def lineage(self) -> Iterator[HConfigChild]:
        pass

    @abstractmethod
    def depth(self) -> int:
        pass

    @property
    @abstractmethod
    def _child_class(self) -> type[HConfigChild]:
        pass

    def add_children(self, lines: Iterable[str]) -> None:
        """Add child instances of HConfigChild."""
        for line in lines:
            self.add_child(line)

    def add_child(
        self,
        text: str,
        *,
        raise_on_duplicate: bool = False,
        force_duplicate: bool = False,
    ) -> HConfigChild:
        """Add a child instance of HConfigChild."""
        if not text:
            message = "text was empty"
            raise ValueError(message)

        # if child does not exist
        if text not in self:
            new_item = self._child_class(self, text)  # type: ignore[arg-type]
            self.children.append(new_item)
            self.children_dict[text] = new_item
            return new_item
        # if child does exist and is allowed to be installed as a duplicate
        if self._duplicate_child_allowed_check() or force_duplicate:
            new_item = self._child_class(self, text)  # type: ignore[arg-type]
            self.children.append(new_item)
            return new_item

        # If the child is already present and the parent does not allow for it
        if raise_on_duplicate:
            message = f"Found a duplicate section: {(*self.path(), text)}"
            raise DuplicateChildError(message)
        return self.children_dict[text]

    def path(self) -> Iterator[str]:  # noqa: PLR6301
        yield from ()

    def add_deep_copy_of(
        self,
        child_to_add: HConfigChild,
        *,
        merged: bool = False,
    ) -> HConfigChild:
        """Add a nested copy of a child to self."""
        new_child = self.add_shallow_copy_of(child_to_add, merged=merged)
        for child in child_to_add.children:
            new_child.add_deep_copy_of(child, merged=merged)

        return new_child

    def delete_child_by_text(self, text: str) -> None:
        """Delete all children with the provided text."""
        if text in self.children_dict:
            self.children[:] = [c for c in self.children if c.text != text]
            self.rebuild_children_dict()

    def delete_child(self, child: HConfigChild) -> None:
        """Delete a child from self.children and self.children_dict."""
        old_len = len(self.children)
        self.children = [c for c in self.children if c is not child]
        if old_len != len(self.children):
            self.rebuild_children_dict()

    def all_children_sorted(self) -> Iterator[HConfigChild]:
        """Recursively find and yield all children sorted at each hierarchy."""
        for child in sorted(self.children):
            yield child
            yield from child.all_children_sorted()

    def all_children(self) -> Iterator[HConfigChild]:
        """Recursively find and yield all children at each hierarchy."""
        for child in self.children:
            yield child
            yield from child.all_children()

    def get_child_deep(self, match_rules: tuple[MatchRule, ...]) -> HConfigChild | None:
        """Find the first child recursively given a tuple of MatchRules."""
        return next(self.get_children_deep(match_rules), None)

    def get_children_deep(
        self,
        match_rules: tuple[MatchRule, ...],
    ) -> Iterator[HConfigChild]:
        """Find children recursively given a tuple of MatchRules."""
        rule = match_rules[0]
        remaining_rules = match_rules[1:]
        for child in self.get_children(
            equals=rule.equals,
            startswith=rule.startswith,
            endswith=rule.endswith,
            contains=rule.contains,
            re_search=rule.re_search,
        ):
            if remaining_rules:
                yield from child.get_children_deep(remaining_rules)
            else:
                yield child

    def get_child(
        self,
        *,
        equals: str | SetLikeOfStr | None = None,
        startswith: str | tuple[str, ...] | None = None,
        endswith: str | tuple[str, ...] | None = None,
        contains: str | tuple[str, ...] | None = None,
        re_search: str | None = None,
    ) -> HConfigChild | None:
        """Find a child by text_match rule. If it is not found, return None."""
        return next(
            self.get_children(
                equals=equals,
                startswith=startswith,
                endswith=endswith,
                contains=contains,
                re_search=re_search,
            ),
            None,
        )

    def get_children(
        self,
        *,
        equals: str | SetLikeOfStr | None = None,
        startswith: str | tuple[str, ...] | None = None,
        endswith: str | tuple[str, ...] | None = None,
        contains: str | tuple[str, ...] | None = None,
        re_search: str | None = None,
    ) -> Iterator[HConfigChild]:
        """Find all children matching a text_match rule and return them."""
        # For isinstance(equals, str) only matches, find the first child using children_dict
        children_slice = slice(None, None)
        if (
            isinstance(equals, str)
            and startswith is endswith is contains is re_search is None
        ):
            if child := self.children_dict.get(equals):
                yield child
                children_slice = slice(self.children.index(child) + 1, None)
            else:
                return

        elif (
            isinstance(startswith, str | tuple)
            and equals is endswith is contains is re_search is None
        ):
            duplicates_allowed = None
            for child_text, child in self.children_dict.items():
                if child_text.startswith(startswith):
                    yield child
                    if duplicates_allowed is None:
                        duplicates_allowed = self._duplicate_child_allowed_check()
                    if duplicates_allowed:
                        children_slice = slice(self.children.index(child) + 1, None)
                        break
            else:
                return

        for child in self.children[children_slice]:
            if child.matches(
                equals=equals,
                startswith=startswith,
                endswith=endswith,
                contains=contains,
                re_search=re_search,
            ):
                yield child

    def add_shallow_copy_of(
        self,
        child_to_add: HConfigChild,
        *,
        merged: bool = False,
    ) -> HConfigChild:
        """Add a nested copy of a child_to_add to self.children."""
        new_child = self.add_child(child_to_add.text)

        if merged:
            new_child.instances.append(child_to_add.instance)
        new_child.comments.update(child_to_add.comments)
        new_child.order_weight = child_to_add.order_weight
        if child_to_add.is_leaf:
            new_child.tags_add(child_to_add.tags)

        return new_child

    def rebuild_children_dict(self) -> None:
        """Rebuild self.children_dict."""
        self.children_dict = {}
        for child in self.children:
            self.children_dict.setdefault(child.text, child)

    def delete_all_children(self) -> None:
        """Delete all children."""
        self.children.clear()
        self.rebuild_children_dict()

    def unified_diff(self, target: HConfig | HConfigChild) -> Iterator[str]:
        """In its current state, this algorithm does not consider duplicate child differences.
        e.g. two instances `endif` in an IOS-XR route-policy. It also does not respect the
        order of commands where it may count, such as in ACLs. In the case of ACLs, they
        should contain sequence numbers if order is important.

        provides a similar output to difflib.unified_diff()
        """
        # if a self child is missing from the target "- self_child.text"
        for self_child in self.children:
            self_iter = iter((f"{self_child.indentation}{self_child.text}",))
            if target_child := target.children_dict.get(self_child.text, None):
                found = self_child.unified_diff(target_child)
                if peek := next(found, None):
                    yield from chain(self_iter, (peek,), found)
            else:
                yield f"{self_child.indentation}- {self_child.text}"
                yield from (
                    f"{c.indentation}- {c.text}"
                    for c in self_child.all_children_sorted()
                )
        # if a target child is missing from self "+ target_child.text"
        for target_child in target.children:
            if target_child.text not in self.children_dict:
                yield f"{target_child.indentation}+ {target_child.text}"
                yield from (
                    f"{c.indentation}+ {c.text}"
                    for c in target_child.all_children_sorted()
                )

    def _future_pre(self, config: HConfig | HConfigChild) -> tuple[set[str], set[str]]:
        negated_or_recursed = set()
        config_children_ignore = set()
        for self_child in self.children:
            # Is the command effectively negating a command in self.children?
            if (
                negation_text := self.root.driver.negation_negate_with_check(self_child)
            ) and (config_child := config.get_child(equals=negation_text)):
                negated_or_recursed.add(self_child.text)
                config_children_ignore.add(config_child.text)
        return negated_or_recursed, config_children_ignore

    def _future(  # noqa: C901
        self,
        config: HConfig | HConfigChild,
        future_config: HConfig | HConfigChild,
    ) -> None:
        """The below cases still need to be accounted for:
        - negate a numbered ACL when removing an item
        - idempotent command avoid list
        - idempotent_acl_check
        - and likely others.
        """
        negated_or_recursed, config_children_ignore = self._future_pre(config)

        for config_child in config.children:
            if config_child.text in config_children_ignore:
                continue
            # sectional_overwrite
            # sectional_overwrite_no_negate
            if (
                config_child.sectional_overwrite_check()
                or config_child.sectional_overwrite_no_negate_check()
            ):
                future_config.add_deep_copy_of(config_child)
            # Idempotent commands
            elif self_child := self.root.driver.idempotent_for(
                config_child,
                self.children,
            ):
                future_config.add_deep_copy_of(config_child)
                negated_or_recursed.add(self_child.text)
            # config_child is already in self
            elif self_child := self.get_child(equals=config_child.text):
                future_child = future_config.add_shallow_copy_of(self_child)
                self_child._future(config_child, future_child)  # noqa: SLF001
                negated_or_recursed.add(config_child.text)
            # config_child is being negated
            elif config_child.text.startswith(self.driver.negation_prefix):
                unnegated_command = config_child.text_without_negation
                if self.get_child(equals=unnegated_command):
                    negated_or_recursed.add(unnegated_command)
                # Account for "no ..." commands in the running config
                else:
                    future_config.add_shallow_copy_of(config_child)
            # The negated form of config_child is in self.children
            elif self_child := self.get_child(
                equals=f"{self.driver.negation_prefix}{config_child.text}",
            ):
                negated_or_recursed.add(self_child.text)
            # config_child is not in self and doesn't match a special case
            else:
                future_config.add_deep_copy_of(config_child)

        for self_child in self.children:
            # self_child matched an above special case and should be ignored
            if self_child.text in negated_or_recursed:
                continue
            # self_child was not modified above and should be present in the future config
            future_config.add_deep_copy_of(self_child)

    @property
    @abstractmethod
    def driver(self) -> HConfigDriverBase:
        pass

    def _with_tags(
        self,
        tags: frozenset[str],
        new_instance: HConfig | HConfigChild,
    ) -> HConfig | HConfigChild:
        """Adds children recursively that have a subset of tags."""
        for child in self.children:
            if tags.issubset(child.tags):
                new_child = new_instance.add_shallow_copy_of(child)
                child._with_tags(tags, new_instance=new_child)  # noqa: SLF001

        return new_instance

    def _config_to_get_to(
        self,
        target: HConfig | HConfigChild,
        delta: HConfig | HConfigChild,
    ) -> HConfig | HConfigChild:
        """Figures out what commands need to be executed to transition from self to target.
        self is the source data structure(i.e. the running_config),
        target is the destination(i.e. generated_config).

        """
        self._config_to_get_to_left(target, delta)
        self._config_to_get_to_right(target, delta)

        return delta

    @staticmethod
    def _strip_acl_sequence_number(hier_child: HConfigChild) -> str:
        words = hier_child.text.split()
        if words[0].isdecimal():
            words.pop(0)
        return " ".join(words)

    def _difference(
        self,
        target: HConfig | HConfigChild,
        delta: HConfig | HConfigChild,
        target_acl_children: dict[str, HConfigChild] | None = None,
        *,
        in_acl: bool = False,
    ) -> HConfig | HConfigChild:
        acl_sw_matches = tuple(f"ip{x} access-list " for x in ("", "v4", "v6"))

        for self_child in self.children:
            # Not dealing with negations and defaults for now
            if self_child.text.startswith((self.driver.negation_prefix, "default ")):
                continue

            if in_acl:
                # Ignore ACL sequence numbers
                if target_acl_children is None:
                    message = "target_acl_children cannot be None"
                    raise TypeError(message)
                target_child = target_acl_children.get(
                    self._strip_acl_sequence_number(self_child),
                )
            else:
                target_child = target.get_child(equals=self_child.text)

            if target_child is None:
                delta.add_deep_copy_of(self_child)
            else:
                delta_child = delta.add_child(self_child.text)
                if self_child.text.startswith(acl_sw_matches):
                    self_child._difference(  # noqa: SLF001
                        target_child,
                        delta_child,
                        target_acl_children={
                            self._strip_acl_sequence_number(c): c
                            for c in target_child.children
                        },
                        in_acl=True,
                    )
                else:
                    self_child._difference(target_child, delta_child)  # noqa: SLF001
                if not delta_child.children:
                    delta_child.delete()

        return delta

    def _config_to_get_to_left(
        self,
        target: HConfig | HConfigChild,
        delta: HConfig | HConfigChild,
    ) -> None:
        # find self.children that are not in target.children
        # i.e. what needs to be negated or defaulted
        # Also, find out if another command in self.children will overwrite
        # i.e. be idempotent
        for self_child in self.children:
            if self_child.text in target:
                continue
            if self_child.is_idempotent_command(target.children):
                continue

            # in other but not self
            # add this node but not any children
            deleted = delta.add_child(self_child.text)
            deleted.negate()
            if self_child.children:
                deleted.comments.add(f"removes {len(self_child.children) + 1} lines")

    def _config_to_get_to_right(
        self,
        target: HConfig | HConfigChild,
        delta: HConfig | HConfigChild,
    ) -> None:
        # find what would need to be added to source_config to get to self
        for target_child in target.children:
            # if the child exist, recurse into its children
            if self_child := self.get_child(equals=target_child.text):
                # This creates a new HConfigChild object just in case there are some delta children
                # Not very efficient, think of a way to not do this
                subtree = delta.add_child(target_child.text)
                self_child._config_to_get_to(target_child, subtree)  # noqa: SLF001
                if not subtree.children:
                    subtree.delete()
                # Do we need to rewrite the child and its children as well?
                elif self_child.sectional_overwrite_check():
                    target_child.overwrite_with(self_child, delta)
                elif self_child.sectional_overwrite_no_negate_check():
                    target_child.overwrite_with(self_child, delta, negate=False)
            # the child is absent, add it
            else:
                new_item = delta.add_deep_copy_of(target_child)
                # mark the new item and all of its children as new_in_config
                new_item.new_in_config = True
                for child in new_item.all_children():
                    child.new_in_config = True
                if new_item.children:
                    new_item.comments.add("new section")
