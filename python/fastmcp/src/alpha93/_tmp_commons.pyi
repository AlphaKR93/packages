from collections.abc import Callable, Awaitable
from typing import overload, Any
from types import CoroutineType

from commons.types import Decorator


type Coroutine[**P, T] = Callable[P, Awaitable[T] | CoroutineType[Any, Any, T]]

@overload
def catch[R, T: BaseException = BaseException](*exc_types: type[T]) -> Decorator[Coroutine[[], R], Awaitable[tuple[R, None]]]: ...
@overload
def catch[R, T: BaseException = BaseException](*exc_types: type[T]) -> Decorator[Coroutine[[], R], Awaitable[tuple[None, T]]]: ...
@overload   # TODO: Remove
def catch[R, T: BaseException = BaseException](*exc_types: type[T]) -> Decorator[Coroutine[[], R], Awaitable[tuple[R | None, None | T]]]: ...
