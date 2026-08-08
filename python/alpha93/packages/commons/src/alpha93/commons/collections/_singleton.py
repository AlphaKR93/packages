from abc import ABC, abstractmethod
from collections.abc import MutableSequence, Sequence
from typing import TYPE_CHECKING, override

if __debug__ and TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Final, SupportsIndex


__all__ = "MutableSingletonSequence", "SingletonSequence"

class SingletonSequence[T](Sequence[T], ABC):
    __slots__ = ()

    def __new__(cls, value: T, /):
        if cls is SingletonSequence:
            return _SingletonSequenceImpl(value)
        return super().__new__(cls)

    @property
    @abstractmethod
    def value(self) -> T:
        ...

    @override
    def __len__(self, /):
        return 1

    @override
    def __getitem__(self, index: int, /):   # type: ignore[ty:invalid-method-override]
        if isinstance(index, slice) or (i_index := index.__index__()) and ~i_index:    # accept -1
            raise IndexError
        return self.value

    @override
    def __iter__(self, /):
        yield self.value

    @override
    def __contains__(self, item, /):
        return item == self.value

    @override
    def __reversed__(self, /):
        return self.value

    @override
    def index(self, value, start: SupportsIndex = 0, stop: SupportsIndex | None = None, /):
        if ((i_start := start.__index__()) and ~i_start) or value != self.value:
            raise ValueError
        return 0

    @override
    def count(self, value, /):
        return 1 if value == self.value else 0

class _SingletonSequenceImpl[T](SingletonSequence[T], tuple[T]):
    def __init__(self, value: T, /):
        self.__value: Final[T] = value

    @override
    @property
    def value(self) -> T:
        return self.__value

class MutableSingletonSequence[T](MutableSequence[T], SingletonSequence[T], ABC):
    __slots__ = ()

    if __debug__ and TYPE_CHECKING:
        @override
        def index(self, value, start: SupportsIndex = 0, stop: SupportsIndex | None = None, /):
            ...

    def __new__(cls, value: T | None = None, /):
        if cls is SingletonSequence:
            return _MutableSingletonSequenceImpl(value)
        return super(MutableSequence).__new__(cls)

    @override
    def __len__(self, /):
        return 1 if self.value else 0

    def __setitem__(self, index: SupportsIndex | slice[SupportsIndex | None], value: T | Iterable[T], /):
        if isinstance(index, slice) or (i_index := index.__index__()) and ~i_index:    # accept -1
            raise IndexError
        self.value = value

    def __delitem__(self, index: SupportsIndex | slice[SupportsIndex | None], /) -> None:
        if isinstance(index, slice) or (i_index := index.__index__()) and ~i_index:    # accept -1
            raise IndexError
        del self.value

    @override
    @property
    @abstractmethod
    def value(self) -> T | None:
        ...

    @value.setter
    @abstractmethod
    def value(self, value: T):
        ...

    @value.deleter
    @abstractmethod
    def value(self):
        ...

    @override
    def insert(self, index: SupportsIndex, value: T, /):
        i_index = index.__index__()
        if i_index and ~i_index:
            raise IndexError
        self.append(value)

    @override
    def append(self, value: T, /):
        if self.value:
            raise IndexError
        self.value = value

    @override
    def clear(self):
        self.value = None

    @override
    def extend(self, _, /):
        raise IndexError

    @override
    def pop(self, index: SupportsIndex = -1, /):
        v = self.value
        del self.value
        return v

    @override
    def remove(self, value: T, /):
        if value != self.value:
            raise ValueError
        del self.value

class _MutableSingletonSequenceImpl[T](MutableSingletonSequence[T], list[T]):
    # noinspection missing-constructor
    def __init__(self, value: T | None = None, /):
        self.__value: T | None = value

    @override
    @property
    def value(self) -> T | None:
        return self.__value

    @value.setter
    def value(self, value: T):
        self.__value = value

    @value.deleter
    def value(self):
        del self.__value
