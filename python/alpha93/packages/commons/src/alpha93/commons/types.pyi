from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Concatenate, TypeGuard, overload

__all__ = (
    "AwaitableOr",
    "SequenceOr",
    "any_object",
    "typed",
)

Unset: Any

type SequenceOr[T] = T | Sequence[T]
type AwaitableOr[T] = T | Awaitable[T]

type Optional[T] = T
Optional.__doc__ = "Helper type for Pydantic. Use with default or default_factory in `Annotated[Field()]`." # noqa: PYI017

def any_object(obj: Any | None = None, /) -> Any:
    """
    Returns ``obj`` or a new `object()` with ``Any`` type.

    :param obj: The value to cast to ``Any``. Returns a new ``object()`` if ``None``.
    """

class typed[T]:
    __slots__ = ()

    def __new__[**P](cls, init: Callable[Concatenate[T, P], None], /) -> Callable[P, T]: ...

    @overload
    @classmethod
    def getattr(cls, obj: object, name: str, /) -> T: ...

    @overload
    @classmethod
    def getattr[U = None](cls, obj: object, name: str, default: U = ..., /) -> T | U: ...

class type_is[T]:
    __slots__ = ()

    def __new__(cls, obj: object, /) -> TypeGuard[T]: ...

    @classmethod
    def hasattr(cls, obj: object, attr: str, /) -> TypeGuard[T]: ...

from warnings import deprecated

@deprecated("Use typed instead.")
class constructor[T]:
    @deprecated("Use typed instead.")
    def __new__[P](cls, init: Callable[Concatenate[T, P], None], /) -> Callable[P, T]: ...
