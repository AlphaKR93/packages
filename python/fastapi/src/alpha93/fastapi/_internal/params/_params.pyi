from abc import ABC
from collections.abc import Callable
from enum import Enum
from typing import Final, Unpack, Literal

from fastapi.datastructures import _Unset
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from ._types import PydanticFieldInfoParameters as PydanticFieldInfoParameters


class ParamTypes(Enum):
    query = "query"
    header = "header"
    path = "path"
    cookie = "cookie"

class Param[T](FieldInfo, ABC): # type: ignore[misc]
    in_: Final[ParamTypes]  # type: ignore[misc]

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
        annotation: type[T] | None = None,
        examples: list[T] | None = None,
        **kwargs: Unpack[PydanticFieldInfoParameters],
    ): ...

class Path[T](Param[T]):
    """
    Declare a path parameter for a *path operation*.

    Read more about it in the
    [FastAPI docs for Path Parameters and Numeric Validations](https://fastapi.tiangolo.com/tutorial/path-params-numeric-validations/).

    ```python
    from typing import Annotated

    from fastapi import FastAPI, Path

    app = FastAPI()


    @app.get("/items/{item_id}")
    async def read_items(
        item_id: Annotated[int, Path(title="The ID of the item to get")],
    ):
        return {"item_id": item_id}
    ```
    """

    in_: Final[Literal[ParamTypes.path]]    # type: ignore[misc]

    def __init__(
        self,
        default: T = ...,
        *,
        default_factory: Callable[[], T] | None = _Unset,
        alias_priority: int | None = _Unset,
        strict: bool | None = _Unset,
        multiple_of: float | None = _Unset,
        allow_inf_nan: bool | None = _Unset,
        max_digits: int | None = _Unset,
        decimal_places: int | None = _Unset,
        annotation: type[T] | None = None,
        examples: list[T] | None = None,
        **kwargs: Unpack[PydanticFieldInfoParameters],
    ): ...

class Query[T](Param[T]):
    in_: Final[Literal[ParamTypes.query]]   # type: ignore[misc]

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
        annotation: type[T] | None = None,
        examples: list[T] | None = None,
        **kwargs: Unpack[PydanticFieldInfoParameters],
    ): ...

class Header[T](Param[T]):
    in_: Final[Literal[ParamTypes.header]]  # type: ignore[misc]

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
        annotation: type[T] | None = None,
        examples: list[T] | None = None,
        **kwargs: Unpack[PydanticFieldInfoParameters],
    ): ...

class Cookie[T](Param[T]):
    in_: Final[Literal[ParamTypes.cookie]]  # type: ignore[misc]

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
        annotation: type[T] | None = None,
        examples: list[T] | None = None,
        **kwargs: Unpack[PydanticFieldInfoParameters],
    ): ...
