from abc import ABC, abstractmethod
from enum import Enum

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

    def api_route(self, path, /, **kwargs):
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
