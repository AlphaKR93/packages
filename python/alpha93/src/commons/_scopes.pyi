from collections.abc import Callable
from typing import Literal, overload

from commons.types import Coroutine, Decorator, Transformer


def constant[T](func: Callable[[], T]) -> T: ...

type SuccessResult[R, T: BaseException = BaseException] = tuple[R, None]
type ErrorResult[R, T: BaseException = BaseException] = tuple[None, T]
type Result[R, T: BaseException = BaseException] = tuple[R | None, None | T] | SuccessResult[R, T] | ErrorResult[R, T]

@overload
def catch[R, **P, T: BaseException = BaseException](
    *exc_types: type[T],
    coro: Literal[False] = False,
) -> Transformer[P, R, SuccessResult[R, T]]: ...
@overload
def catch[R, **P, T: BaseException = BaseException](
    *exc_types: type[T],
    coro: Literal[False] = False,
) -> Transformer[P, R, ErrorResult[R, T]]: ...
@overload
def catch[R, **P, T: BaseException = BaseException](
    *exc_types: type[T],
    coro: Literal[False] = False,
) -> Transformer[P, R, Result[R, T]]: ...
@overload
def catch[R, **P, T: BaseException = BaseException](
    *exc_types: type[T],
    coro: Literal[True],
) -> Decorator[Coroutine[P, T], Coroutine[P, SuccessResult[R, T]]]: ...
@overload
def catch[R, **P, T: BaseException = BaseException](
    *exc_types: type[T],
    coro: Literal[True],
) -> Decorator[Coroutine[P, T], Coroutine[P, ErrorResult[R, T]]]: ...
@overload
def catch[R, **P, T: BaseException = BaseException](
    *exc_types: type[T],
    coro: Literal[True],
) -> Decorator[Coroutine[P, T], Coroutine[P, Result[R, T]]]: ...
@overload   # FIXME: Remove
def catch[R, **P, T: BaseException = BaseException](
    *exc_types: type[T],
    coro: bool = False,
) -> Transformer[P, R, Result[R, T]] | Decorator[Coroutine[P, T], Coroutine[P, Result[R, T]]]: ...
