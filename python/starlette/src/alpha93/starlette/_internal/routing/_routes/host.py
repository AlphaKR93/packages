from starlette.datastructures import Headers, URLPath

from .._match import Match, NoMatchFound
from ._abc import BaseRoute

if __debug__ and __import__("typing").TYPE_CHECKING:
    from typing import Any

    from starlette.types import ASGIApp, Receive, Scope, Send


class Host(BaseRoute):
    def __init__(self, host: str, /, app: ASGIApp, name: str | None = None) -> None:
        assert not host.startswith("/"), "Host must not start with '/'"
        self.host = host
        self.app = app
        self.name = name
        self.host_regex, self.host_format, self.param_convertors = self.compile_path(host)

    @property
    def routes(self) -> list[BaseRoute]:
        return getattr(self.app, "routes", [])

    def matches(self, scope: Scope, /) -> tuple[Match, Scope]:
        if scope["type"] == "http":  # pragma:no branch
            headers = Headers(scope=scope)
            host = headers.get("host", "").split(":")[0]
            match = self.host_regex.match(host)
            if match:
                matched_params = match.groupdict()
                for key, value in matched_params.items():
                    matched_params[key] = self.param_convertors[key].convert(value)
                path_params = dict(scope.get("path_params", {}))
                path_params.update(matched_params)
                child_scope = {"path_params": path_params, "endpoint": self.app}
                return Match.FULL, child_scope
        return Match.NONE, {}

    def url_path_for(self, name: str, /, **path_params: Any) -> URLPath:
        if self.name is not None and name == self.name and "path" in path_params:
            # 'name' matches "<mount_name>".
            path = path_params.pop("path")
            host, remaining_params = self.replace_params(self.host_format, self.param_convertors, path_params)
            if not remaining_params:
                return URLPath(path=path, host=host)
        elif self.name is None or name.startswith(self.name + ":"):
            if self.name is None:
                # No mount name.
                remaining_name = name
            else:
                # 'name' matches "<mount_name>:<child_name>".
                remaining_name = name[len(self.name) + 1 :]
            host, remaining_params = self.replace_params(self.host_format, self.param_convertors, path_params)
            for route in self.routes or []:
                try:
                    url = route.url_path_for(remaining_name, **remaining_params)
                    return URLPath(path=str(url), protocol=url.protocol, host=host)
                except NoMatchFound:
                    pass
        raise NoMatchFound(name, path_params)

    async def handle(self, scope: Scope, receive: Receive, send: Send, /) -> None:
        await self.app(scope, receive, send)

    def __eq__(self, other: Any, /) -> bool:
        return isinstance(other, Host) and self.host == other.host and self.app == other.app

    def __repr__(self, /) -> str:
        class_name = self.__class__.__name__
        name = self.name or ""
        return f"{class_name}(host={self.host!r}, name={name!r}, app={self.app!r})"
