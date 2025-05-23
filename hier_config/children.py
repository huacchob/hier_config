from __future__ import annotations

from typing import TYPE_CHECKING, Optional, TypeVar, Union, overload

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from hier_config import HConfigChild

_D = TypeVar("_D")


class HConfigChildren:
    def __init__(self) -> None:
        """Initialize the HConfigChildren class."""
        self._data: list[HConfigChild] = []
        self._mapping: dict[str, HConfigChild] = {}

    @overload
    def __getitem__(self, subscript: Union[int, str]) -> HConfigChild: ...

    @overload
    def __getitem__(self, subscript: slice) -> list[HConfigChild]: ...

    def __getitem__(
        self, subscript: Union[slice, int, str]
    ) -> Union[HConfigChild, list[HConfigChild]]:
        if isinstance(subscript, slice):
            return self._data[subscript]
        if isinstance(subscript, int):
            return self._data[subscript]
        return self._mapping[subscript]

    def __setitem__(self, index: int, child: HConfigChild) -> None:
        self._data[index] = child
        self.rebuild_mapping()

    def __contains__(self, item: str) -> bool:
        return item in self._mapping

    def __iter__(self) -> Iterator[HConfigChild]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HConfigChildren):
            return NotImplemented

        self_len = len(self._data)
        other_len = len(other._data)
        # Superfast succeed method for no children
        if self_len == other_len == 0:
            return True

        # Superfast fail method
        if self_len != other_len:
            return False

        # Fast fail method
        if self._mapping.keys() != other._mapping.keys():
            return False

        # Slower full comparison
        return all(
            self_child == other_child
            for self_child, other_child in zip(
                sorted(self._data),
                sorted(other._data),
            )
        )

    def __hash__(self) -> int:
        return hash(
            (*self._data,),
        )

    def append(
        self,
        child: HConfigChild,
        *,
        update_mapping: bool = True,
    ) -> HConfigChild:
        """Add a child instance of HConfigChild.

        Args:
            child (HConfigChild): The child to add.
            update_mapping (bool, optional): Whether to update the text to child mapping.
                Defaults to True.

        Returns:
            HConfigChild: The child that was added.

        """
        self._data.append(child)
        if update_mapping:
            self._mapping.setdefault(child.text, child)

        return child

    def clear(self) -> None:
        """Delete all children."""
        self._data.clear()
        self._mapping.clear()

    def delete(self, child_or_text: Union[HConfigChild, str]) -> None:
        """Delete a child from self._data and self._mapping.

        Args:
            child_or_text (Union[HConfigChild, str]): The child or text to delete.

        """
        if isinstance(child_or_text, str):
            if child_or_text in self._mapping:
                self._data[:] = [c for c in self._data if c.text != child_or_text]
                self.rebuild_mapping()
        else:
            old_len: int = len(self._data)
            self._data = [c for c in self._data if c is not child_or_text]
            if old_len != len(self._data):
                self.rebuild_mapping()

    def extend(self, children: Iterable[HConfigChild]) -> None:
        """Add child instances of HConfigChild and update _mapping.

        Args:
            children (Iterable[HConfigChild]): The children to add.

        """
        self._data.extend(children)
        for child in children:
            self._mapping.setdefault(child.text, child)

    def get(
        self, key: str, default: Optional[_D] = None
    ) -> Union[HConfigChild, _D, None]:
        """Get a child from self._mapping.

        Args:
            key (str): The config text to get.
            default (Optional[_D], optional): Object to return if the key doesn't exist.
                Defaults to None.

        Returns:
            Union[HConfigChild, _D, None]: HConfigChild if found, default otherwise.

        """
        return self._mapping.get(key, default)

    def index(self, child: HConfigChild) -> int:
        """Get the index of a child in self._data.

        Args:
            child (HConfigChild): The child to get the index of.

        Returns:
            int: The index of the child.

        """
        return self._data.index(child)

    def rebuild_mapping(self) -> None:
        """Rebuild self._mapping from self._data."""
        self._mapping.clear()
        for child in self._data:
            self._mapping.setdefault(child.text, child)
