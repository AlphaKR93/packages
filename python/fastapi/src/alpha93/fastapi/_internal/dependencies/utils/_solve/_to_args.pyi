from collections.abc import Mapping, Sequence
from typing import Any

from alpha93.fastapi._internal._compat.v2 import ModelField
from starlette.datastructures import QueryParams, Headers


def extract_from_params(
    fields: Sequence[ModelField],
    params: QueryParams | Headers | Mapping[str, Any],
    /,
) -> tuple[Mapping[str, Any], Sequence[Any]]: ...

def extract_from_body(
    body: Mapping[str, Any] | bytes | None,
    fields: Sequence[ModelField],
    embed_body_fields: bool,
    /
) -> tuple[Mapping[str, Any], Sequence[Mapping[str, Any]]]: ...
