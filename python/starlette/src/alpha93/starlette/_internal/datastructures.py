if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Mapping, Iterable, Iterator, KeysView, ValuesView, ItemsView
    from typing import Any


class ImmutableMultiDict[K, V](Mapping[K, V]):
    _dict: dict[K, V]

    def __init__(
        self,
        *args: ImmutableMultiDict[K, V] | Mapping[K, V] | Iterable[tuple[K, V]],
        **kwargs: Any,
    ) -> None:
        assert len(args) < 2, "Too many arguments."

        value: Any = args[0] if args else []
        if kwargs:
            value = ImmutableMultiDict(value).multi_items() + ImmutableMultiDict(kwargs).multi_items()

        if not value:
            _items: list[tuple[Any, Any]] = []
        elif hasattr(value, "multi_items"):
            _items = list(value.multi_items())
        elif hasattr(value, "items"):
            _items = list(value.items())
        else:
            _items = list(value)

        self._dict = {k: v for k, v in _items}
        self._list = _items

    def getlist(self, key: Any) -> list[V]:
        return [item_value for item_key, item_value in self._list if item_key == key]

    def keys(self) -> KeysView[K]:
        return self._dict.keys()

    def values(self) -> ValuesView[V]:
        return self._dict.values()

    def items(self) -> ItemsView[K, V]:
        return self._dict.items()

    def multi_items(self) -> list[tuple[K, V]]:
        return list(self._list)

    def __getitem__(self, key: K) -> V:
        return self._dict[key]

    def __contains__(self, key: Any) -> bool:
        return key in self._dict

    def __iter__(self) -> Iterator[K]:
        return iter(self.keys())

    def __len__(self) -> int:
        return len(self._dict)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return sorted(self._list) == sorted(other._list)

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        items = self.multi_items()
        return f"{class_name}({items!r})"


class MultiDict(ImmutableMultiDict[Any, Any]):
    def __setitem__(self, key: Any, value: Any) -> None:
        self.setlist(key, [value])

    def __delitem__(self, key: Any) -> None:
        self._list = [(k, v) for k, v in self._list if k != key]
        del self._dict[key]

    def pop(self, key: Any, default: Any = None) -> Any:
        self._list = [(k, v) for k, v in self._list if k != key]
        return self._dict.pop(key, default)

    def popitem(self) -> tuple[Any, Any]:
        key, value = self._dict.popitem()
        self._list = [(k, v) for k, v in self._list if k != key]
        return key, value

    def poplist(self, key: Any) -> list[Any]:
        values = [v for k, v in self._list if k == key]
        self.pop(key)
        return values

    def clear(self) -> None:
        self._dict.clear()
        self._list.clear()

    def setdefault(self, key: Any, default: Any = None) -> Any:
        if key not in self:
            self._dict[key] = default
            self._list.append((key, default))

        return self[key]

    def setlist(self, key: Any, values: list[Any]) -> None:
        if not values:
            self.pop(key, None)
        else:
            existing_items = [(k, v) for (k, v) in self._list if k != key]
            self._list = existing_items + [(key, value) for value in values]
            self._dict[key] = values[-1]

    def append(self, key: Any, value: Any) -> None:
        self._list.append((key, value))
        self._dict[key] = value

    def update(
        self,
        *args: MultiDict | Mapping[Any, Any] | list[tuple[Any, Any]],
        **kwargs: Any,
    ) -> None:
        value = MultiDict(*args, **kwargs)
        existing_items = [(k, v) for (k, v) in self._list if k not in value.keys()]
        self._list = existing_items + value.multi_items()
        self._dict.update(value)
