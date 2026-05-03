from collections.abc import Callable
from typing import Unpack, Any

from alpha93.fastapi._internal._compat.v2 import ModelField
from fastapi.dependencies.models import Dependant
from ..models import DependantParams
from ...params import Depends


def get_validation_alias(field: ModelField, /) -> str: ...

def get_dependant(
    *,
    path: str,
    call: Callable[..., Any],
    **kwargs: Unpack[DependantParams]
) -> Dependant: ...

def get_parameterless_sub_dependant(
    depends: Depends,
    /,
    **kwargs: Unpack[DependantParams]
) -> Dependant: ...
