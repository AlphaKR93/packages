from functools import lru_cache
from types import UnionType
from typing import TYPE_CHECKING, Union, get_args, get_origin

from terser_hints import constant

from alpha93.fastapi._internal._compat.shared import lenient_issubclass
from alpha93.fastapi._internal._compat.v2 import ModelField
from pydantic import ValidationError, BaseModel


if __debug__ and TYPE_CHECKING:
    from typing import Any


@constant
def _is_mappable():
    from collections.abc import Mapping
    from dataclasses import is_dataclass

    return lambda annotation: lenient_issubclass(annotation, (BaseModel, Mapping)) or is_dataclass(annotation)

def get_missing_field_error(loc: tuple[int | str, ...]) -> dict[str, Any]:
    error = ValidationError.from_exception_data(
        "Field required", [{"type": "missing", "loc": loc, "input": {}}]
    ).errors(include_url=False)[0]
    error["input"] = None
    return error  # type: ignore[return-value]

@lru_cache
def get_cached_model_fields(model: type[BaseModel], /) -> list[ModelField]:
    model_fields: list[ModelField] = []
    for name, field_info in model.model_fields.items():
        config = None if _is_mappable(field_info.annotation) else model.model_config

        model_fields.append(ModelField(field_info=field_info, name=name, config=config))
    return model_fields

@constant
def _annotation_is_sequence():
    from collections import deque
    from collections.abc import Iterator, Sequence

    sequence_types = (Iterator, Sequence, list, tuple, set, frozenset, deque,)

    def func(annotation, /) -> bool:
        if lenient_issubclass(annotation, (str, bytes)):
            return False
        return lenient_issubclass(annotation, sequence_types)
    return func

def field_annotation_is_sequence(annotation: type[Any] | None) -> bool:
    origin = get_origin(annotation)
    if origin is Union or origin is UnionType:
        for arg in get_args(annotation):
            if field_annotation_is_sequence(arg):
                return True
        return False
    return _annotation_is_sequence(annotation) or _annotation_is_sequence(get_origin(annotation))

@constant
def field_annotation_is_scalar():
    from typing import Annotated

    _cmplx = lambda annotation: _is_mappable(annotation) or _annotation_is_sequence(annotation)
    def is_complex_field(annotation, /) -> bool:
        origin = get_origin(annotation)
        if origin is Union or origin is UnionType:
            return any(is_complex_field(arg) for arg in get_args(annotation))

        if origin is Annotated:
            return is_complex_field(get_args(annotation)[0])

        return (
            _cmplx(annotation)
            or _cmplx(origin)
            or hasattr(origin, "__pydantic_core_schema__")
            or hasattr(origin, "__get_pydantic_core_schema__")
        )

    return lambda annotation: annotation is Ellipsis or not is_complex_field(annotation)

def field_annotation_is_scalar_sequence(annotation: type[Any] | None) -> bool:
    origin = get_origin(annotation)
    if origin is Union or origin is UnionType:
        at_least_one_scalar_sequence = False
        for arg in get_args(annotation):
            if field_annotation_is_scalar_sequence(arg):
                at_least_one_scalar_sequence = True
                continue
            elif not field_annotation_is_scalar(arg):
                return False
        return at_least_one_scalar_sequence
    return field_annotation_is_sequence(annotation) \
        and all(field_annotation_is_scalar(sub_annotation) for sub_annotation in get_args(annotation))
