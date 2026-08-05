from collections.abc import Awaitable, Callable, Coroutine
from types import CoroutineType
from typing import Any

from ._callable import Function, Method

__all__ = (
    "Callable",
    "Decorator",
    "Function",
    "Method",
    "ReturnsCoroutine",
    "Transformer",
    "Wrapper",
)

type Decorator[F, V] = Callable[[F], V]
type Wrapper[T] = Decorator[T, T]
type Transformer[**P, T, U] = Decorator[Callable[P, T], Callable[P, U]]

type ReturnsCoroutine[**P, T] = Callable[P, Awaitable[T] | Coroutine[Any, Any, T] | CoroutineType[Any, Any, T]]
