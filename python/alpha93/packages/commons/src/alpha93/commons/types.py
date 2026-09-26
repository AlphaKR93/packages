from collections.abc import Awaitable, Sequence

if __debug__ and __import__("typing").TYPE_CHECKING:
    from typing import Any, TypeGuard


type AwaitableOr[T] = T | Awaitable[T]
type SequenceOr[T] = T | Sequence[T]
type Optional[T] = T | None
Unset = ...

def any_object(obj: object | None = None, /) -> Any:
    return obj or object()


class typed:
    __slots__ = ()

    def __getitem__(self, typ, /):
        return self.__Typed(typ)

    class __Typed:
        __slots__ = ("__type",)

        def __init__(self, typ, /):
            self.__type = typ

        def __call__(self, init, /):
            return self.__type

        @staticmethod
        def getattr(obj, name: str, default = ..., /):
            return getattr(obj, name) if default is ... else getattr(obj, name, default)
typed = typed() # type: ignore[ty:invalid-assignment]
constructor = any_object(typed)


class type_is[T]:
    __slots__ = ()

    def __new__(cls, obj, /):
        return True

    @staticmethod
    def hasattr(obj, attr: str, /) -> TypeGuard[T]:
        return hasattr(obj, attr)
