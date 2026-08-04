from collections.abc import Awaitable, Callable, Sequence
from types import CoroutineType
from typing import Any, Protocol

__all__ = (
    "AwaitableOr",
    "Coroutine",
    "Decorator",
    "SequenceOr",
    "Transformer",
    "Wrapper",
    "typed",
)

typed: __TypedGetter

type SequenceOr[T] = T | Sequence[T]

type Decorator[F, V] = Callable[[F], V]
type Wrapper[T] = Decorator[T, T]
type Transformer[**P, T, U] = Decorator[Callable[P, T], Callable[P, U]]

type AwaitableOr[T] = T | Awaitable[T]
type Coroutine[**P, T] = Callable[P, Awaitable[T] | CoroutineType[Any, Any, T]]

class __TypedGetter(Protocol):
    def __getitem__[T](self, item: type[T]) -> __Typed[T]: ...
    class __Typed[T](Protocol):
        def getattr[U](self, obj, name: str, default: U = ...) -> T: ...
