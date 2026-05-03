from collections.abc import Callable
from typing import TypedDict, Literal, Any

from alpha93.fastapi._internal._compat.v2 import ModelField
from fastapi.dependencies.models import Dependant


class DependantParams(TypedDict, total=False):
    path_params: list[ModelField]
    query_params: list[ModelField]
    header_params: list[ModelField]
    cookie_params: list[ModelField]
    body_params: list[ModelField]
    dependencies: list[Dependant]
    name: str
    call: Callable[..., Any]
    request_param_name: str
    websocket_param_name: str
    http_connection_param_name: str
    response_param_name: str
    background_tasks_param_name: str
    security_scopes_param_name: str
    own_oauth_scopes: list[str]
    parent_oauth_scopes: list[str]
    use_cache: bool
    path: str
    scope: Literal["function", "request"]
