from abc import ABC, abstractmethod
from re import Pattern
from typing import Any, final

from starlette.convertors import Convertor
from starlette.datastructures import URLPath
from starlette.types import Receive, Scope, Send

from .._match import Match

class BaseRoute(ABC):
    @abstractmethod
    def matches(self, scope: Scope, /) -> tuple[Match, Scope]: ...

    @abstractmethod
    def url_path_for(self, name: str, /, **path_params: Any) -> URLPath: ...

    @abstractmethod
    async def handle(self, scope: Scope, receive: Receive, send: Send, /) -> None: ...

    @final
    @staticmethod
    def replace_params(
        path: str, param_convertors: dict[str, Convertor[Any]], path_params: dict[str, str], /
    ) -> tuple[str, dict[str, str]]:
        ...

    @final
    @staticmethod
    def compile_path(path: str, /) -> tuple[Pattern[str], str, dict[str, Convertor[Any]]]:
        """
        Given a path string, like: "/{username:str}",
        or a host string, like: "{subdomain}.mydomain.org", return a three-tuple
        of (regex, format, {param_name:convertor}).

        regex:      "/(?P<username>[^/]+)"
        format:     "/{username}"
        convertors: {"username": StringConvertor()}
        """
