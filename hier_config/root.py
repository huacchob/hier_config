from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

from .base import HConfigBase
from .child import HConfigChild
from .model import Dump, DumpLine

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from hier_config.platforms.driver_base import HConfigDriverBase

logger = getLogger(__name__)

# Refactoring ideas:
# - What if children were moved into its own class? e.g. child.children.add()
# - Cases of children.index() could be replaced with an identity based version.


class HConfig(HConfigBase):  # noqa: PLR0904
    """A class for representing and comparing Cisco like configurations in a
    hierarchical tree data structure.
    """

    __slots__ = ("_driver",)

    def __init__(self, driver: HConfigDriverBase) -> None:
        super().__init__()
        self._driver = driver

    @property
    def driver(self) -> HConfigDriverBase:
        return self._driver

    def __str__(self) -> str:
        return "\n".join(str(c) for c in sorted(self.children))

    def __repr__(self) -> str:
        return f"HConfig(driver={self.driver.platform}, lines={self.dump_simple()})"

    def __hash__(self) -> int:
        return hash(*self.children)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HConfig):
            return NotImplemented

        if len(self.children) != len(other.children):
            return False

        return all(
            self_child == other_child
            for self_child, other_child in zip(
                sorted(self.children),
                sorted(other.children),
                strict=False,
            )
        )

    @property
    def real_indent_level(self) -> int:
        return -1

    @property
    def parent(self) -> HConfig:
        return self

    @property
    def root(self) -> HConfig:
        """Returns the HConfig object at the base of the tree."""
        return self

    @property
    def is_leaf(self) -> bool:
        """Returns True if there are no children and is not an instance of HConfig."""
        return False

    @property
    def is_branch(self) -> bool:
        """Returns True if there are children or is an instance of HConfig."""
        return True

    @property
    def _child_class(self) -> type[HConfigChild]:
        return HConfigChild

    @property
    def tags(self) -> frozenset[str]:
        """Recursive access to tags on all leaf nodes."""
        found_tags: set[str] = set()
        for child in self.children:
            found_tags.update(child.tags)
        return frozenset(found_tags)

    @tags.setter
    def tags(self, value: frozenset[str]) -> None:
        """Recursive access to tags on all leaf nodes."""
        for child in self.children:
            child.tags = value

    def merge(self, other: HConfig | Iterable[HConfig]) -> HConfig:
        """Merges other HConfig objects into this one."""
        other_configs = (other,) if isinstance(other, HConfig) else other

        for other_config in other_configs:
            for child in other_config.children:
                self.add_deep_copy_of(child, merged=True)

        return self

    def add_children_deep(self, lines: Iterable[str]) -> HConfigChild:
        """Add child instances of HConfigChild deeply."""
        base: HConfig | HConfigChild = self
        for line in lines:
            base = base.add_child(line)
        if isinstance(base, HConfig):
            message = "base was an HConfig object for some reason."
            raise TypeError(message)
        return base

    def lineage(self) -> Iterator[HConfigChild]:  # noqa: PLR6301
        """Yields the lineage of parent objects, up to but excluding the root."""
        yield from ()

    def lines(self, *, sectional_exiting: bool = False) -> Iterable[str]:
        for child in sorted(self.children):
            yield from child.lines(sectional_exiting=sectional_exiting)

    def dump_simple(self, *, sectional_exiting: bool = False) -> tuple[str, ...]:
        return tuple(self.lines(sectional_exiting=sectional_exiting))

    def dump(self) -> Dump:
        """Dump loaded HConfig data."""
        return Dump(
            driver_platform=self.driver.platform,
            lines=tuple(
                DumpLine(
                    depth=c.depth(),
                    text=c.text,
                    tags=frozenset(c.tags),
                    comments=frozenset(c.comments),
                    new_in_config=c.new_in_config,
                )
                for c in self.all_children_sorted()
            ),
        )

    def depth(self) -> int:  # noqa: PLR6301
        """Returns the distance to the root HConfig object i.e. indent level."""
        return 0

    def difference(self, target: HConfig) -> HConfig:
        """Creates a new HConfig object with the config from self that is not in target."""
        delta = HConfig(self.driver)
        difference = self._difference(target, delta)
        # Makes mypy happy
        if not isinstance(difference, HConfig):
            raise TypeError
        return difference

    def config_to_get_to(
        self,
        target: HConfig,
        delta: HConfig | None = None,
    ) -> HConfig:
        """Figures out what commands need to be executed to transition from self to target.
        self is the source data structure(i.e. the running_config),
        target is the destination(i.e. generated_config).

        """
        if delta is None:
            delta = HConfig(self.driver)

        root_config = self._config_to_get_to(target, delta)
        if not isinstance(root_config, HConfig):
            raise TypeError

        return root_config

    def add_ancestor_copy_of(
        self,
        parent_to_add: HConfigChild,
    ) -> HConfig | HConfigChild:
        """Add a copy of the ancestry of parent_to_add to self
        and return the deepest child which is equivalent to parent_to_add.
        """
        base: HConfig | HConfigChild = self
        for parent in parent_to_add.lineage():
            base = base.add_shallow_copy_of(parent)

        return base

    def set_order_weight(self) -> HConfig:
        """Sets self.order integer on all children."""
        for child in self.all_children():
            for rule in self.driver.ordering_rules:
                if child.lineage_test(rule.lineage):
                    child.order_weight = rule.weight
        return self

    def future(self, config: HConfig) -> HConfig:
        """EXPERIMENTAL - predict the future config after config is applied to self.

        The quality of this method's output will in part depend on how well
        the OS options are tuned. Ensuring that idempotency rules are accurate is
        especially important.
        """
        future_config = HConfig(self.driver)
        self._future(config, future_config)
        return future_config

    def with_tags(self, tags: Iterable[str]) -> HConfig:
        """Returns a new instance recursively containing children that only have a subset of tags."""
        new_instance = HConfig(self.driver)
        result = self._with_tags(frozenset(tags), new_instance)
        # Makes mypy happy
        if not isinstance(result, HConfig):
            raise TypeError
        return new_instance

    def all_children_sorted_by_tags(
        self,
        include_tags: Iterable[str],
        exclude_tags: Iterable[str],
    ) -> Iterator[HConfigChild]:
        """Yield all children recursively that match include/exclude tags."""
        for child in sorted(self.children):
            yield from child.all_children_sorted_by_tags(include_tags, exclude_tags)

    def deep_copy(self) -> HConfig:
        """Return a copy of this object."""
        new_instance = HConfig(self.driver)
        for child in self.children:
            new_instance.add_deep_copy_of(child)
        return new_instance

    def _duplicate_child_allowed_check(self) -> bool:  # noqa: PLR6301
        """Determine if duplicate(identical text) children are allowed under the parent."""
        return False
