from collections.abc import Awaitable, Sequence
from typing import Any, Protocol

__all__ = (
    "AwaitableOr",
    "SequenceOr",
    "any_object",
    "typed",
)

Unset: Any
typed: __TypedGetter

type SequenceOr[T] = T | Sequence[T]
type AwaitableOr[T] = T | Awaitable[T]

type Optional[T] = T
"""Helper type for Pydantic. Use with default or default_factory in `Annotated[Field()]`."""

def any_object(obj: Any | None = None, /) -> Any:
    """
    Returns ``obj`` or a new `object()` with ``Any`` type.

    :param obj: The value to cast to ``Any``. Returns a new ``object()`` if ``None``.
    """

class __TypedGetter(Protocol):
    def __getitem__[T](self, item: type[T]) -> __Typed[T]: ...
    class __Typed[T](Protocol):
        def getattr[U](self, obj, name: str, default: U = ...) -> T: ...
