from collections.abc import Awaitable, Sequence

type AwaitableOr[T] = T | Awaitable[T]
type SequenceOr[T] = T | Sequence[T]
type Optional[T] = T | None
Unset = ...

def any_object(obj: object | None = None, /):
    return obj or object()


class typed[T]:
    @staticmethod
    def getattr(self, name: str, default = ...) -> T:  # ruff: ignore[bad-staticmethod-argument]
        return getattr(self, name) if default is ... else getattr(self, name, default)
