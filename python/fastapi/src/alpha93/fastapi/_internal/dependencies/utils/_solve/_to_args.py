from copy import deepcopy

from alpha93.fastapi._internal._compat.shared import lenient_issubclass
from commons import constant
from pydantic import BaseModel
from starlette.datastructures import ImmutableMultiDict, Headers

from .._base import get_validation_alias
from .._pydantic_utils import get_missing_field_error, get_cached_model_fields, field_annotation_is_sequence


if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from typing import Any

    from alpha93.fastapi._internal._compat.v2 import ModelField


def _validate_value_with_model_field(field: ModelField, value, /, *args, **kwargs):
    if value:
        return field.validate(value, *args, **kwargs)

    return (None, [get_missing_field_error(**kwargs)]) if field.field_info.is_required() \
        else (deepcopy(field.default), [])

@constant
def _get_multidict_value():
    from pydantic import Json

    _not_json = lambda field: not any(type(item) is Json for item in field.field_info.metadata)

    def _multidict_get(field: ModelField, values: Mapping[str, Any], alias: str | None = None, /):
        is_iterable: bool = field_annotation_is_sequence(field.field_info.annotation)
        alias = alias or get_validation_alias(field)
        value = values.getlist(alias) \
            if (_not_json(field) and is_iterable and isinstance(values, (ImmutableMultiDict, Headers))) \
            else values.get(alias, None)

        if not value or (is_iterable and not len(value)):
            return None if field.field_info.is_required() else deepcopy(field.default)
        return value
    return _multidict_get

def extract_from_body(
    body_to_process: dict[str, Any] | bytes | None,
    body_fields: list[ModelField],
    embed_body_fields: bool,
    /,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if len(body_fields) == 1 and not embed_body_fields:
        first_field = body_fields[0]
        v_, errors_ = _validate_value_with_model_field(first_field, body_to_process, {}, loc=("body",))
        return {first_field.name: v_}, errors_

    values: dict[str, Any] = {}
    errors: list[dict[str, Any]] = []
    for field in body_fields:
        loc = ("body", get_validation_alias(field))
        value: Any | None = None
        if body_to_process and not isinstance(body_to_process, bytes):
            try:
                value = body_to_process.get(get_validation_alias(field))
            # If the received body is a list, not a dict
            except AttributeError:
                errors.append(get_missing_field_error(loc))
                continue
        v_, errors_ = _validate_value_with_model_field(field, value, values, loc=loc)
        if errors_:
            errors.extend(errors_)
        else:
            values[field.name] = v_
    return values, errors

def extract_from_params(fields: Sequence[ModelField], params: Mapping[str, Any], /) -> tuple[dict[str, Any], list[Any]]:
    values: dict[str, Any] = {}
    errors: list[dict[str, Any]] = []

    if not fields:
        return values, errors

    first_field = fields[0]
    fields_to_extract = fields
    single_not_embedded_field = False
    convert_underscores = True
    if len(fields) == 1 and lenient_issubclass(first_field.field_info.annotation, BaseModel):
        fields_to_extract = get_cached_model_fields(first_field.field_info.annotation)
        single_not_embedded_field = True
        # If headers are in a Pydantic model, the way to disable convert_underscores
        # would be with Header(convert_underscores=False) at the Pydantic model level
        convert_underscores = getattr(first_field.field_info, "convert_underscores", True)

    params_to_process: dict[str, Any] = {}

    processed_keys = set()

    is_headers = isinstance(params, Headers)
    for field in fields_to_extract:
        alias = None
        # Handle fields extracted from a Pydantic Model for a header, each field
        # doesn't have a FieldInfo of type Header with the default convert_underscores=True
        if is_headers and getattr(field.field_info, "convert_underscores", convert_underscores):
            alias = get_validation_alias(field)
            if alias == field.name:
                alias = alias.replace("_", "-")

        value = _get_multidict_value(field, params, alias)
        if value is not None:
            params_to_process[get_validation_alias(field)] = value

        processed_keys.add(alias or get_validation_alias(field))

    has_getlist = is_headers or isinstance(params, ImmutableMultiDict)
    for key in params.keys():
        if key in processed_keys:
            continue

        if has_getlist:
            value = params.getlist(key)
            params_to_process[key] = value[0] if isinstance(value, list) and len(value) == 1 else value
        else:
            params_to_process[key] = params.get(key)

    if single_not_embedded_field:
        field_info = first_field.field_info
        assert isinstance(field_info, params.Param), "Params must be subclasses of Param"
        loc: tuple[str, ...] = (field_info.in_.value,)
        v_, errors_ = _validate_value_with_model_field(first_field, params_to_process, values, loc=loc)
        return {first_field.name: v_}, errors_

    for field in fields:
        value = _get_multidict_value(field, params)
        field_info = field.field_info
        assert isinstance(field_info, params.Param), "Params must be subclasses of Param"
        loc = (field_info.in_.value, get_validation_alias(field))
        v_, errors_ = _validate_value_with_model_field(field, value, values, loc=loc)
        if errors_:
            errors.extend(errors_)
        else:
            values[field.name] = v_
    return values, errors
