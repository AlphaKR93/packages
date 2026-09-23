from collections.abc import Awaitable, Sequence

if __debug__ and __import__("typing").TYPE_CHECKING:
    from typing import Any, TypeIs

type AwaitableOr[T] = T | Awaitable[T]
type SequenceOr[T] = T | Sequence[T]
type Optional[T] = T | None
Unset = ...

def any_object(obj: object | None = None, /) -> Any:
    return obj or object()


class typed[T]:
    @staticmethod
    def getattr(self, name: str, default = ..., /) -> T:  # noqa: PLW0211
        return getattr(self, name) if default is ... else getattr(self, name, default)

class type_is[T]:
    @staticmethod
    def hasattr(self, attr: str, /) -> TypeIs[T]:
        return hasattr(self, attr)

class __ConstructorObject:
    __slots__ = ()
    def __getitem__(self, typ, /):
        call = lambda _: typ
        setattr(call, "i", call)
        return call
constructor = any_object(__ConstructorObject())
