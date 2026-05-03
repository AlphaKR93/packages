from abc import ABC, abstractmethod
from enum import Enum

from fastapi.datastructures import Default
from fastapi.utils import generate_unique_id as _default_generate_unique_id
from starlette.responses import JSONResponse


if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any


class Methods(Enum):
    get = "GET"
    put = "PUT"
    post = "POST"
    delete = "DELETE"
    options = "OPTIONS"
    head = "HEAD"
    patch = "PATCH"
    trace = "TRACE"

class Routable(ABC):
    @abstractmethod
    def add_api_route(self, path, endpoint, /, **kwargs): ...

    @abstractmethod
    def include_router(self, router, /, **kwargs): ...

    def api_route(
        self,
        path,
        /,
        response_model = Default(None),
        response_model_by_alias = True,
        response_model_exclude_unset = False,
        response_model_exclude_defaults = False,
        response_model_exclude_none = False,
        response_class = Default(JSONResponse),
        generate_unique_id = Default(_default_generate_unique_id),
        strict_content_type = Default(True),
        **kwargs
    ):
        kwargs.update({
            "response_model": response_model,
            "response_model_by_alias": response_model_by_alias,
            "response_model_exclude_unset": response_model_exclude_unset,
            "response_model_exclude_defaults": response_model_exclude_defaults,
            "response_model_exclude_none": response_model_exclude_none,
            "response_class": response_class,
            "generate_unique_id": generate_unique_id,
            "strict_content_type": strict_content_type,
        })
        def wrapper(func: Callable[..., Any], /):
            self.add_api_route(path, func, **kwargs)
            return func
        return wrapper

@lambda _: _()
def __decorators():
    def decorator(http_method: str, /):
        def route(self: Routable, path: str, /, **kwargs):
            return self.api_route(path, methods={http_method}, **kwargs)
        return route

    for method in Methods:
        setattr(Routable, method.name, decorator(method.value))
