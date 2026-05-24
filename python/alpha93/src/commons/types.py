from collections.abc import Awaitable, Callable, Sequence
from typing import Any
from types import CoroutineType


type AwaitableOr[T] = T | Awaitable[T]
type SequenceOr[T] = T | Sequence[T]

type Coroutine[**P, T] = Callable[P, Awaitable[T] | CoroutineType[Any, Any, T]]
type Decorator[F, V] = Callable[[F], V]
type Wrapper[T] = Decorator[T, T]
type Transformer[**P, T, U] = Decorator[Callable[P, T], Callable[P, U]]
