from enum import Enum

if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any


class Match(Enum):
    NONE = 0
    PARTIAL = 1
    FULL = 2


class NoMatchFound(Exception):
    """
    Raised by `.url_for(name, **path_params)` and `.url_path_for(name, **path_params)`
    if no matching route exists.
    """

    def __init__(self, name: str, path_params: Mapping[str, Any], /) -> None:
        params = ", ".join(list(path_params.keys()))
        super().__init__(f'No route exists for name "{name}" and params "{params}".')
