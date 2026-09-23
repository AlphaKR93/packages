from collections.abc import Awaitable, Sequence, Callable
from typing import Any, Protocol, TypeIs, Concatenate


__all__ = (
    "AwaitableOr",
    "SequenceOr",
    "any_object",
    "typed",
)

Unset: Any
typed: __TypedAccessor
type_is: __TypeIsAccessor
constructor: __ConstructorAccessor

type SequenceOr[T] = T | Sequence[T]
type AwaitableOr[T] = T | Awaitable[T]

type Optional[T] = T
"""Helper type for Pydantic. Use with default or default_factory in `Annotated[Field()]`."""

def any_object(obj: Any | None = None, /) -> Any:
    """
    Returns ``obj`` or a new `object()` with ``Any`` type.

    :param obj: The value to cast to ``Any``. Returns a new ``object()`` if ``None``.
    """

class __TypedAccessor(Protocol):
    def __getitem__[T](self, typ: type[T]) -> __Typed[T]: ...
    class __Typed[T](Protocol):
        def getattr[U](self, obj, name: str, default: U = ...) -> T: ...

class __TypeIsAccessor(Protocol):
    def __getitem__[T](self, typ: type[T]) -> __TypeIs[T]: ...
    class __TypeIs[T](Protocol):
        def hasattr(self, obj, attr: str, /) -> TypeIs[T]: ...

class __ConstructorAccessor(Protocol):
    def __getitem__[T](self, typ: type[T]) -> __Constructor[T]: ...
    class __Constructor[T](Protocol):
        def i[**P](self, init: Callable[Concatenate[T, P], None], /) -> Callable[P, T]: ...
        def __call__[**P](self, init: Callable[Concatenate[T, P], None], /) -> Callable[P, T]: ...
