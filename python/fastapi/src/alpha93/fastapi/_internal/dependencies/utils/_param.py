import dataclasses
import inspect
from copy import copy
from dataclasses import dataclass
from typing import Annotated, get_args, get_origin

from alpha93.fastapi._internal._compat.shared import lenient_issubclass
from alpha93.fastapi._internal._compat.v2 import ModelField
from alpha93.fastapi._internal.params._params import Param
from alpha93.fastapi._internal import params
from fastapi.utils import create_model_field
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined
from starlette.background import BackgroundTasks
from starlette.requests import Request, HTTPConnection
from starlette.responses import Response
from typing_inspection.typing_objects import is_typealiastype

from ._pydantic_utils import field_annotation_is_scalar, field_annotation_is_scalar_sequence


if __debug__ and __import__("typing").TYPE_CHECKING:
    from typing import Any


@dataclass(frozen=True)
class ParamDetails:
    type_annotation: Any
    depends: params.Depends | None
    field: ModelField | None

def _copy_field_info(self: FieldInfo, annotation, /) -> FieldInfo:
    merged = type(self).from_annotation(annotation)
    copied = copy(self)
    copied.metadata = merged.metadata
    copied.annotation = merged.annotation
    return copied

def _is_scalar_field(field: ModelField, /):
    return field_annotation_is_scalar(field.field_info.annotation) and not isinstance(field.field_info, params.Body)

def analyze_param(
    param: inspect.Parameter,
    param_name: str,
    is_path_param: bool,
    /,
) -> ParamDetails:
    value = param.default
    annotation = param.annotation
    # Unpack in case PEP 695 type syntax is used
    if is_typealiastype(annotation): annotation = annotation.__value__

    field_info = None
    depends = None
    use_annotation: Any = Any
    type_annotation: Any = Any
    if annotation is not inspect.Signature.empty:
        use_annotation = annotation
        type_annotation = annotation

    # Extract Annotated info
    if get_origin(use_annotation) is Annotated:
        annotated_args = get_args(annotation)
        type_annotation = annotated_args[0]
        fastapi_annotation: FieldInfo | params.Depends | None = next(
            (arg for arg in reversed(annotated_args[1:]) if isinstance(arg, (Param, params.Body, params.Depends))),
            None
        )

        if isinstance(fastapi_annotation, params.Depends):
            depends = fastapi_annotation
        elif isinstance(fastapi_annotation, FieldInfo):
            # Copy `field_info` because we mutate `field_info.default` below.
            field_info = _copy_field_info(fastapi_annotation, type_annotation)
            assert field_info.default == PydanticUndefined, \
                f"`{field_info.__class__.__name__}` default value cannot be set in `Annotated`"

            if value is not inspect.Signature.empty:
                assert not is_path_param, "Path parameters cannot have default values"
                field_info.default = value
            else:
                field_info.default = PydanticUndefined

    # Get from default value
    if isinstance(value, params.Depends):
        assert not depends, "Cannot specify `Depends` in `Annotated` and default value together"
        assert not field_info, "Cannot specify FastAPI annotation in `Annotated` and default value together"
        depends = value
    elif isinstance(value, FieldInfo):
        assert not field_info, "Cannot specify FastAPI annotation in `Annotated` and default value together"
        field_info = value
        if isinstance(field_info, FieldInfo):
            field_info.annotation = type_annotation

    if depends:
        if not depends.dependency:
            # Copy `depends` before mutating it
            depends = copy(depends)
            depends = dataclasses.replace(depends, dependency=type_annotation)
    else:
        if lenient_issubclass(type_annotation, (Request, HTTPConnection, Response, BackgroundTasks)):
            # Handle non-param type annotations like Request
            # Only apply special handling when there's no explicit Depends - if there's a Depends,
            # the dependency will be called and its return value used instead of the special injection
            assert field_info is None, f"Cannot specify FastAPI annotation for type {type_annotation!r}"
        elif field_info is None:
            if is_path_param:
                # We might check here that `default_value is RequiredParam`, but the fact is that the same
                # parameter might sometimes be a path parameter and sometimes not. See
                # `tests/test_infer_param_optionality.py` for an example.
                field_info = params.Path(annotation=use_annotation)
            else:
                # Handle default assignations, neither field_info nor depends was not found in Annotated nor default value
                default_value = PydanticUndefined if value is inspect.Signature.empty else value
                if field_annotation_is_scalar(annotation=type_annotation):
                    field_info = params.Query(annotation=use_annotation, default=default_value)
                else:
                    field_info = params.Body(annotation=use_annotation, default=default_value)

    field = None
    # It's a field_info, not a dependency
    if field_info is not None:
        # Handle field_info.in_
        if is_path_param:
            assert isinstance(field_info, params.Path), f"Cannot use `{field_info.__class__.__name__}` for path param"
        elif isinstance(field_info, Param) and not getattr(field_info, "in_", None):
            # noinspection PyFinal
            field_info.in_ = params.Query.in_

        if not field_info.alias and getattr(field_info, "convert_underscores", None):
            alias = param_name.replace("_", "-")
        else:
            alias = field_info.alias or param_name
        field_info.alias = alias
        field = create_model_field(
            name=param_name,
            type_=use_annotation,
            default=field_info.default,
            alias=alias,
            field_info=field_info,
        )

        if is_path_param:
            assert _is_scalar_field(field), "Path params must be of one of the supported types"
        elif isinstance(field_info, params.Query):
            assert (
                _is_scalar_field(field)
                or field_annotation_is_scalar_sequence(field.field_info.annotation)
                or lenient_issubclass(field.field_info.annotation, BaseModel)
            ), f"Query parameter {param_name!r} must be one of the supported types"

    return ParamDetails(type_annotation=type_annotation, depends=depends, field=field)
