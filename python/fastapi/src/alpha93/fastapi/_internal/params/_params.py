from abc import ABC
from enum import Enum

from fastapi.datastructures import _Unset
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined


if __debug__ and __import__("typing").TYPE_CHECKING:
    from typing import Any, Final, ClassVar


class ParamTypes(Enum):
    query = "query"
    header = "header"
    path = "path"
    cookie = "cookie"

class Param(FieldInfo, ABC):    # type: ignore[misc]
    in_: ClassVar[Final[ParamTypes]]    # type: ignore[misc]

    def __init__(
        self,
        default = PydanticUndefined,
        *,
        alias = None,
        default_factory = _Unset,
        alias_priority = _Unset,
        strict = _Unset,
        multiple_of = _Unset,
        allow_inf_nan = _Unset,
        max_digits = _Unset,
        decimal_places = _Unset,
        validation_alias = None,
        serialization_alias = None,
        **params
    ):
        if alias:
            if not validation_alias or validation_alias is _Unset:
                validation_alias = alias
            if (not serialization_alias or serialization_alias is _Unset) and isinstance(alias, str):
                serialization_alias = alias

        kwargs = {
            "alias": alias,
            "default": default,
            "default_factory": default_factory,
            "alias_priority": alias_priority,
            "strict": strict,
            "multiple_of": multiple_of,
            "allow_inf_nan": allow_inf_nan,
            "max_digits": max_digits,
            "decimal_places": decimal_places,
            "validation_alias": validation_alias,
            "serialization_alias": serialization_alias,
            **params,
        }
        super().__init__(**{k: v for k, v in kwargs.items() if v is not _Unset})

class Path(Param):
    in_ = ParamTypes.path

    def __init__(
        self,
        default: Any = ...,
        *,
        default_factory = _Unset,
        alias_priority = _Unset,
        strict = _Unset,
        multiple_of = _Unset,
        allow_inf_nan = _Unset,
        max_digits = _Unset,
        decimal_places = _Unset,
        **kwargs
    ):
        assert default is ..., "Path parameters cannot have a default value"
        super().__init__(
            default=default,
            default_factory=default_factory,
            alias_priority=alias_priority,
            strict=strict,
            multiple_of=multiple_of,
            allow_inf_nan=allow_inf_nan,
            max_digits=max_digits,
            decimal_places=decimal_places,
            **kwargs
        )

class Query(Param):
    in_ = ParamTypes.query

    def __init__(
        self,
        default = PydanticUndefined,
        *,
        default_factory = _Unset,
        alias_priority = _Unset,
        strict = _Unset,
        multiple_of = _Unset,
        allow_inf_nan = _Unset,
        max_digits = _Unset,
        decimal_places = _Unset,
        **kwargs
    ):
        super().__init__(
            default=default,
            default_factory=default_factory,
            alias_priority=alias_priority,
            strict=strict,
            multiple_of=multiple_of,
            allow_inf_nan=allow_inf_nan,
            max_digits=max_digits,
            decimal_places=decimal_places,
            **kwargs
        )

class Header(Param):
    in_ = ParamTypes.header

    def __init__(
        self,
        default = PydanticUndefined,
        *,
        default_factory = _Unset,
        alias_priority = _Unset,
        strict = _Unset,
        multiple_of = _Unset,
        allow_inf_nan = _Unset,
        max_digits = _Unset,
        decimal_places = _Unset,
        convert_underscores: bool = True,
        **kwargs
    ):
        self.convert_underscores = convert_underscores
        super().__init__(
            default=default,
            default_factory=default_factory,
            alias_priority=alias_priority,
            strict=strict,
            multiple_of=multiple_of,
            allow_inf_nan=allow_inf_nan,
            max_digits=max_digits,
            decimal_places=decimal_places,
            **kwargs
        )

class Cookie(Param):
    in_ = ParamTypes.cookie

    def __init__(
        self,
        default = PydanticUndefined,
        *,
        default_factory = _Unset,
        alias_priority = _Unset,
        strict = _Unset,
        multiple_of = _Unset,
        allow_inf_nan = _Unset,
        max_digits = _Unset,
        decimal_places = _Unset,
        **kwargs
    ):
        super().__init__(
            default=default,
            default_factory=default_factory,
            alias_priority=alias_priority,
            strict=strict,
            multiple_of=multiple_of,
            allow_inf_nan=allow_inf_nan,
            max_digits=max_digits,
            decimal_places=decimal_places,
            **kwargs
        )
