if __debug__ and __import__("typing").TYPE_CHECKING:
    from starlette.types import Scope


def get_route_path(scope: Scope, /) -> str:
    path: str = scope["path"]
    root_path = scope.get("root_path", "")
    if not root_path or not path.startswith(root_path):
        return path

    if path == root_path:
        return ""

    if path[len(root_path)] == "/":
        return path[len(root_path):]

    return path
