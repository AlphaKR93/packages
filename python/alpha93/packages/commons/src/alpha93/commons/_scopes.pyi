import builtins
from collections.abc import AsyncIterable, Callable, Iterable
from typing import Any, Literal, Protocol, overload

from .types import Coroutine

def throw[T: BaseException](cls: type[T], /, *args, caused_by: BaseException | None = None, **kwargs) -> T: ...

@overload
def enumerate[T](
    iterable: Iterable[T], /, start: int = 0
) -> builtins.enumerate[T]: ...
@overload
def enumerate[T](
    iterable: AsyncIterable[T], /, start: int = 0
) -> AsyncIterable[tuple[int, T]]: ...

@overload
def catch[T: BaseException](
    *exc_types: type[T],
    coro: Literal[False],
) -> __Catch[T]: ...
@overload
def catch[T: BaseException](
    *exc_types: type[T],
    coro: Literal[True],
) -> __AsyncCatch[T]: ...
@overload
def catch[T: BaseException](
    *exc_types: type[T],
    coro: None = None,
) -> __AmbiguousCatch[T]: ...


class __Catch[E: BaseException](Protocol):
    def __call__[**P, T](self, fn: Callable[P, T], /) -> Callable[P, tuple[T, E]]: ...


class __AsyncCatch[E: BaseException](Protocol):
    def __call__[**P, T](self, fn: Coroutine[P, T], /) -> Coroutine[P, tuple[T, E]]: ...


class __AmbiguousCatch[E: BaseException](Protocol):
    def __call__(self, fn: Callable[..., Any], /) -> Callable[..., Any]: ...
