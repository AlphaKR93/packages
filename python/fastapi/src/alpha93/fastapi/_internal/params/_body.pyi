from fastapi.datastructures import _Unset
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined


if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Unpack

    from ._types import PydanticFieldInfoParameters


class Body[T](FieldInfo):  # type: ignore[misc]
    def __init__(
        self,
        default: T = PydanticUndefined,
        *,
        default_factory: Callable[[], T] | None = _Unset,
        alias_priority: int | None = _Unset,
        strict: bool | None = _Unset,
        multiple_of: float | None = _Unset,
        allow_inf_nan: bool | None = _Unset,
        max_digits: int | None = _Unset,
        decimal_places: int | None = _Unset,
        media_type: str = "application/json",
        embed: bool | None = None,
        **params: Unpack[PydanticFieldInfoParameters[T]],
    ): ...

    def __repr__(self) -> str: ...
