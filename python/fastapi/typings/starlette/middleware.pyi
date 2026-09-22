from collections.abc import Iterator
from typing import Any, Protocol

from .types import ASGIApp

class _MiddlewareFactory[**P](Protocol):
    def __call__(
        self, app: ASGIApp, /, *args: P.args, **kwargs: P.kwargs
    ) -> ASGIApp: ...

class Middleware:
    def __init__[**P](
        self, cls: _MiddlewareFactory[P], *args: P.args, **kwargs: P.kwargs
    ) -> None: ...
    def __iter__(self) -> Iterator[Any]: ...
