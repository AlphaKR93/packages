from terser_hints import constant

from fastapi.dependencies.models import Dependant
from fastapi.exceptions import DependencyScopeError
from fastapi.utils import get_path_param_names
from ...._internal import params
from ..._compat.shared import lenient_issubclass
from ._param import analyze_param
from ._signature import get_typed_signature


if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any, Final, Literal

get_validation_alias = lambda field: field.validation_alias or field.alias

@constant
def add_non_field_param_to_dependency():
    from starlette.background import BackgroundTasks
    from starlette.requests import Request, HTTPConnection
    from starlette.responses import Response

    attr_map = {
        Request: "request",
        HTTPConnection: "http_connection",
        Response: "response",
        BackgroundTasks: "background_tasks",
    }

    def func(dependant: Dependant, annotation, name: str, /):
        for type_, attr_ in attr_map.items():
            if lenient_issubclass(annotation, type_):
                setattr(dependant, f"{attr_}_param_name", name)
                return True
        return None
    return func

@constant
def add_param_to_fields():
    from ...params._params import ParamTypes

    attr_map = {
        ParamTypes.path: "path_params",
        ParamTypes.query: "query_params",
        ParamTypes.header: "header_params",
        ParamTypes.cookie: "cookie_params"
    }
    return lambda dependant, field: getattr(dependant, attr_map[getattr(field.field_info, "in_")]).append(field)

def get_dependant(
    *,
    path: str,
    call: Callable[..., Any],
    name: str | None = None,
    own_oauth_scopes: list[str] | None = None,
    parent_oauth_scopes: list[str] | None = None,
    use_cache: bool = True,
    scope: Literal["function", "request"] | None = None,
) -> Dependant:
    dependant = Dependant(
        path=path,
        call=call,
        name=name,
        own_oauth_scopes=own_oauth_scopes,
        parent_oauth_scopes=parent_oauth_scopes,
        use_cache=use_cache,
        scope=scope,
    )
    current_scopes: Final = (parent_oauth_scopes or []) + (own_oauth_scopes or [])
    path_param_names: Final = get_path_param_names(path)
    for param_name, param in get_typed_signature(call).parameters.items():
        param_details = analyze_param(param, param_name, param_name in path_param_names)
        if param_details.depends is not None:
            assert param_details.depends.dependency
            if (
                (dependant.is_gen_callable or dependant.is_async_gen_callable)
                and dependant.computed_scope == "request"
                and param_details.depends.scope == "function"
            ):
                assert dependant.call
                call_name = getattr(dependant.call, "__name__", "<unnamed_callable>")
                raise DependencyScopeError(
                    f'The dependency "{call_name}" has a scope of '
                    '"request", it cannot depend on dependencies with scope "function".'
                )
            sub_own_oauth_scopes: list[str] = []
            if isinstance(param_details.depends, params.Security):
                if param_details.depends.scopes:
                    sub_own_oauth_scopes = list(param_details.depends.scopes)
            dependant.dependencies.append(get_dependant(
                path=path,
                call=param_details.depends.dependency,
                name=param_name,
                own_oauth_scopes=sub_own_oauth_scopes,
                parent_oauth_scopes=current_scopes,
                use_cache=param_details.depends.use_cache,
                scope=param_details.depends.scope,
            ))
            continue
        if add_non_field_param_to_dependency(dependant, param_details.type_annotation, param_name):
            assert param_details.field is None, f"Cannot specify multiple FastAPI annotations for {param_name!r}"
            continue
        assert param_details.field is not None
        if isinstance(param_details.field.field_info, params.Body):
            dependant.body_params.append(param_details.field)
        else:
            add_param_to_fields(dependant, param_details.field)
    return dependant

def get_parameterless_sub_dependant(depends: params.Depends, /, **kwargs):
    assert callable(depends.dependency), "A parameter-less dependency must have a callable dependency"
    if isinstance(depends, params.Security) and depends.scopes:
        kwargs["own_oauth_scopes"] = list(depends.scopes)
    return get_dependant(call=depends.dependency, scope=depends.scope, **kwargs)
