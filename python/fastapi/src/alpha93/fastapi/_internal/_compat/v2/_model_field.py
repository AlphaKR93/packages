import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Any, Annotated

from pydantic import ConfigDict, TypeAdapter, ValidationError
from pydantic.fields import FieldInfo, Field
from pydantic.main import IncEx
from pydantic.warnings import UnsupportedFieldAttributeWarning
from pydantic_core import PydanticUndefined as Undefined


@dataclass
class ModelField:
    field_info: FieldInfo | None
    name: str
    mode: Literal["validation", "serialization"] = "validation"
    config: ConfigDict | None = None

    @property
    def alias(self) -> str:
        a = self.field_info.alias
        return a if a is not None else self.name

    @property
    def validation_alias(self) -> str | None:
        va = self.field_info.validation_alias
        if isinstance(va, str) and va:
            return va
        return None

    @property
    def serialization_alias(self) -> str | None:
        sa = self.field_info.serialization_alias
        return sa or None

    @property
    def default(self) -> Any:
        return self.get_default()

    def __post_init__(self) -> None:
        # noinspection PyTypeChecker
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=UnsupportedFieldAttributeWarning)
            field_dict = self.field_info.asdict()
            annotated_args = (
                field_dict["annotation"],
                *field_dict["metadata"],
                # this FieldInfo needs to be created again so that it doesn't include
                # the old field info metadata and only the rest of the attributes
                Field(**field_dict["attributes"]),
            )
            # noinspection PyTypeHints
            self._type_adapter: TypeAdapter[Any] = TypeAdapter(
                Annotated[annotated_args],  # ty: ignore[invalid-type-form]
                config=self.config,
            )

    def get_default(self) -> Any:
        if self.field_info.is_required():
            return Undefined
        return self.field_info.get_default(call_default_factory=True)

    def validate(
        self,
        value: Any,
        values: dict[str, Any] = {},  # noqa: B006
        *,
        loc: tuple[int | str, ...] = (),
    ) -> tuple[Any, list[dict[str, Any]]]:
        try:
            return (
                self._type_adapter.validate_python(value, from_attributes=True),
                [],
            )
        except ValidationError as exc:
            return None, _regenerate_error_with_loc(
                errors=exc.errors(include_url=False), loc_prefix=loc
            )

    def serialize(
        self,
        value: Any,
        *,
        mode: Literal["json", "python"] = "json",
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        by_alias: bool = True,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> Any:
        # What calls this code passes a value that already called
        # self._type_adapter.validate_python(value)
        return self._type_adapter.dump_python(
            value,
            mode=mode,
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )

    def serialize_json(
        self,
        value: Any,
        *,
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        by_alias: bool = True,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> bytes:
        # What calls this code passes a value that already called
        # self._type_adapter.validate_python(value)
        # This uses Pydantic's dump_json() which serializes directly to JSON
        # bytes in one pass (via Rust), avoiding the intermediate Python dict
        # step of dump_python(mode="json") + json.dumps().
        return self._type_adapter.dump_json(
            value,
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )

    def __hash__(self) -> int:
        # Each ModelField is unique for our purposes, to allow making a dict from
        # ModelField to its JSON Schema.
        return id(self)

def _regenerate_error_with_loc(*, errors: Sequence[Any], loc_prefix: tuple[str | int, ...]) -> list[dict[str, Any]]:
    return [{**err, "loc": loc_prefix + err.get("loc", ())} for err in errors]
