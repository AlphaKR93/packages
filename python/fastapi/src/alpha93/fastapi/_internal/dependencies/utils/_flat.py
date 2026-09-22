from fastapi.dependencies.models import Dependant, _get_cache_key, _get_oauth_scopes

if __debug__ and __import__("typing").TYPE_CHECKING:
    from fastapi.dependencies.models import _UsesScopesCache
    from fastapi.types import DependencyCacheKey


def get_flat_dependant(
    dependant: Dependant,
    /,
    *,
    skip_repeats: bool = False,
    visited: list[DependencyCacheKey] | None = None,
    parent_oauth_scopes: list[str] | None = None,
    uses_scopes_cache: "_UsesScopesCache | None" = None,
) -> Dependant:
    if visited is None:
        visited: list[DependencyCacheKey] = []
    if uses_scopes_cache is None:
        uses_scopes_cache = {}

    visited.append(_get_cache_key(dependant=dependant, uses_scopes_cache=uses_scopes_cache))
    use_parent_oauth_scopes = (parent_oauth_scopes or []) + _get_oauth_scopes(dependant=dependant)

    flat_dependant = Dependant(
        path_params=dependant.path_params.copy(),
        query_params=dependant.query_params.copy(),
        header_params=dependant.header_params.copy(),
        cookie_params=dependant.cookie_params.copy(),
        body_params=dependant.body_params.copy(),
        name=dependant.name,
        call=dependant.call,
        request_param_name=dependant.request_param_name,
        websocket_param_name=dependant.websocket_param_name,
        http_connection_param_name=dependant.http_connection_param_name,
        response_param_name=dependant.response_param_name,
        background_tasks_param_name=dependant.background_tasks_param_name,
        security_scopes_param_name=dependant.security_scopes_param_name,
        own_oauth_scopes=dependant.own_oauth_scopes,
        parent_oauth_scopes=use_parent_oauth_scopes,
        use_cache=dependant.use_cache,
        path=dependant.path,
        scope=dependant.scope,
    )

    for sub_dependant in dependant.dependencies:
        if skip_repeats and _get_cache_key(dependant=sub_dependant, uses_scopes_cache=uses_scopes_cache) in visited:
            continue

        flat_sub = get_flat_dependant(
            sub_dependant,
            skip_repeats=skip_repeats,
            visited=visited,
            parent_oauth_scopes=_get_oauth_scopes(dependant=flat_dependant),
            uses_scopes_cache=uses_scopes_cache,
        )
        flat_dependant.dependencies.append(flat_sub)
        flat_dependant.path_params.extend(flat_sub.path_params)
        flat_dependant.query_params.extend(flat_sub.query_params)
        flat_dependant.header_params.extend(flat_sub.header_params)
        flat_dependant.cookie_params.extend(flat_sub.cookie_params)
        flat_dependant.body_params.extend(flat_sub.body_params)
        flat_dependant.dependencies.extend(flat_sub.dependencies)

    return flat_dependant
