from fastapi.datastructures import _Unset
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined


class Body(FieldInfo):  # type: ignore[misc]
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
        media_type = "application/json",
        embed = None,
        **params
    ):
        self.media_type = media_type
        self.embed = embed
        kwargs = dict(
            default=default,
            default_factory=default_factory,
            alias_priority=alias_priority,
            strict=strict,
            multiple_of=multiple_of,
            allow_inf_nan=allow_inf_nan,
            max_digits=max_digits,
            decimal_places=decimal_places,
            **params,
        )

        if (not kwargs["validation_alias"] or kwargs["validation_alias"] is _Unset):
            kwargs["validation_alias"] = kwargs["alias"]
        if (not kwargs["serialization_alias"] or kwargs["serialization_alias"] is _Unset) \
            and isinstance(kwargs["alias"], str):
            kwargs["serialization_alias"] = kwargs["alias"]

        super().__init__(**{k: v for k, v in kwargs.items() if v is not _Unset})

    def __repr__(self, /):
        return f"{self.__class__.__name__}({self.default})"
