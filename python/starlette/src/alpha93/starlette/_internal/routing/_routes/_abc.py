import re
from abc import ABC, abstractmethod

from starlette.convertors import CONVERTOR_TYPES

from .._match import Match

if __debug__ and __import__("typing").TYPE_CHECKING:
    from typing import Any

    from starlette.convertors import Convertor
    from starlette.datastructures import URLPath
    from starlette.types import Receive, Scope, Send

# Match parameters in URL paths, eg. '{param}', and '{param:int}'
PARAM_REGEX = re.compile("{([a-zA-Z_][a-zA-Z0-9_]*)(:[a-zA-Z_][a-zA-Z0-9_]*)?}")

class BaseRoute(ABC):
    @abstractmethod
    def matches(self, scope: Scope, /) -> tuple[Match, Scope]: ...

    @abstractmethod
    def url_path_for(self, name: str, /, **path_params: Any) -> URLPath: ...

    @abstractmethod
    async def handle(self, scope: Scope, receive: Receive, send: Send, /) -> None: ...

    async def __call__(self, scope: Scope, receive: Receive, send: Send, /) -> None:
        """
        A route may be used in isolation as a stand-alone ASGI app.
        This is a somewhat contrived case, as they'll almost always be used
        within a Router, but could be useful for some tooling and minimal apps.
        """
        match, child_scope = self.matches(scope)
        if match == Match.NONE:
            from starlette.responses import PlainTextResponse

            response = PlainTextResponse("Not Found", status_code=404)
            await response(scope, receive, send)
            return

        scope.update(child_scope)
        await self.handle(scope, receive, send)

    @staticmethod
    def replace_params(path: str, param_convertors: dict[str, Convertor[Any]], path_params: dict[str, str], /):
        for key, value in list(path_params.items()):
            if "{" + key + "}" in path:
                convertor = param_convertors[key]
                value = convertor.to_string(value)
                path = path.replace("{" + key + "}", value)
                path_params.pop(key)
        return path, path_params

    @staticmethod
    def compile_path(path: str, /):
        """
        Given a path string, like: "/{username:str}",
        or a host string, like: "{subdomain}.mydomain.org", return a three-tuple
        of (regex, format, {param_name:convertor}).

        regex:      "/(?P<username>[^/]+)"
        format:     "/{username}"
        convertors: {"username": StringConvertor()}
        """
        is_host = not path.startswith("/")

        path_regex = "^"
        path_format = ""
        duplicated_params: set[str] = set()

        idx = 0
        param_convertors = {}
        for match in PARAM_REGEX.finditer(path):
            param_name, convertor_type = match.groups("str")
            convertor_type = convertor_type.lstrip(":")
            assert convertor_type in CONVERTOR_TYPES, f"Unknown path convertor '{convertor_type}'"
            convertor = CONVERTOR_TYPES[convertor_type]

            path_regex += re.escape(path[idx : match.start()])
            path_regex += f"(?P<{param_name}>{convertor.regex})"

            path_format += path[idx : match.start()]
            path_format += f"{{{param_name}}}"

            if param_name in param_convertors:
                duplicated_params.add(param_name)

            param_convertors[param_name] = convertor

            idx = match.end()

        if duplicated_params:
            names = ", ".join(sorted(duplicated_params))
            ending = "s" if len(duplicated_params) > 1 else ""
            raise ValueError(f"Duplicated param name{ending} {names} at path {path}")

        if is_host:
            # Align with `Host.matches()` behavior, which ignores port.
            hostname = path[idx:].split(":")[0]
            path_regex += re.escape(hostname) + "$"
        else:
            path_regex += re.escape(path[idx:]) + "$"

        path_format += path[idx:]

        return re.compile(path_regex), path_format, param_convertors
