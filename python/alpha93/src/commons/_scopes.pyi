from collections.abc import Callable
from typing import Literal, overload, Protocol

from commons.types import Coroutine, Decorator, Transformer


def constant[T](func: Callable[[], T]) -> T: ...

class Catcher[E: BaseException](Protocol):
    @overload
    def __call__[**P, T](self, fn: Callable[P, T], /) -> Callable[P, tuple[T, None]]: ...
    @overload
    def __call__[**P, T](self, fn: Callable[P, T], /) -> Callable[P, tuple[None, E]]: ...
    def __call__[**P, T](self, fn: Callable[P, T], /) -> Callable[P, tuple[T | None, None | E]]: ...

class AsyncCatcher[E: BaseException](Protocol):
    @overload
    def __call__[**P, T](self, fn: Coroutine[P, T], /) -> Coroutine[P, tuple[T, None]]: ...
    @overload
    def __call__[**P, T](self, fn: Coroutine[P, T], /) -> Coroutine[P, tuple[None, E]]: ...
    def __call__[**P, T](self, fn: Coroutine[P, T], /) -> Coroutine[P, tuple[T | None, None | E]]: ...

@overload
def catch[T: BaseException = BaseException](
    *exc_types: type[T],
    coro: Literal[False] = False,
) -> Catcher[T]: ...
@overload
def catch[T: BaseException = BaseException](
    *exc_types: type[T],
    coro: Literal[True],
) -> AsyncCatcher[T]: ...
def catch[T: BaseException = BaseException](
    *exc_types: type[T],
    coro: bool = False,
) -> Catcher[T] | AsyncCatcher[T]: ...
