from typing import TYPE_CHECKING, get_args, get_origin

from pydantic import create_model
from terser_hints import constant

from alpha93.fastapi._internal.params import Body
from fastapi.utils import create_model_field

if __debug__ and TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any

    from alpha93.fastapi._internal._compat.v2 import ModelField
    from fastapi.dependencies.models import Dependant
    from pydantic import BaseModel


def should_embed_body_fields(fields: list[ModelField], /) -> bool:
    if not fields:
        return False

    # More than one dependency could have the same field, it would show up as multiple
    # fields but it's the same one, so count them by name
    # A top level field has to be a single field, not multiple
    if len({field.name for field in fields}) > 1:
        return True

    # If it explicitly specifies it is embedded, it has to be embedded
    if getattr(fields[0].field_info, "embed", None):
        return True

    return False

@constant
def get_body_field():
    def create_body_model(name: str, fields: Sequence[ModelField], /) -> type[BaseModel]:
        field_params = {f.name: (f.field_info.annotation, f.field_info) for f in fields}
        return create_model(name, **field_params)

    def func(flat_dependant: Dependant, name: str, embed_body_fields: bool, /) -> ModelField | None:
        """
        Get a ModelField representing the request body for a path operation, combining
        all body parameters into a single field if necessary.

        Used to check if it's form data (with `isinstance(body_field, params.Form)`)
        or JSON and to generate the JSON Schema for a request body.

        This is **not** used to validate/parse the request body, that's done with each
        individual body parameter.
        """
        if not flat_dependant.body_params:
            return None

        first_param = flat_dependant.body_params[0]
        if not embed_body_fields:
            return first_param

        model = create_body_model(f"Body_{name}", flat_dependant.body_params)
        kwargs: dict[str, Any] = {
            "annotation": model,
            "alias": "body",
        }

        for f in flat_dependant.body_params:
            if f.field_info.is_required():
                kwargs["default"] = None
                break

        meda_types = [f.field_info.media_type for f in flat_dependant.body_params if isinstance(f.field_info, Body)]
        if len(set(meda_types)) == 1:
            kwargs["media_type"] = meda_types[0]

        return create_model_field(name="body", type_=model, alias="body", field_info=Body(**kwargs))
    return func

@constant
def get_stream_item_type():
    from collections.abc import AsyncIterable, AsyncIterator, AsyncGenerator, Iterable, Iterator, Generator
    from typing import Any

    origins = { AsyncIterable, AsyncIterator, AsyncGenerator, Iterable, Iterator, Generator }

    def func(annotation, /) -> Any | None:
        origin = get_origin(annotation)
        if not origin or origin not in origins:
            return None

        return type_args[0] if (type_args := get_args(annotation)) else Any
    return func
