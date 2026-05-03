if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

constant = lambda _: _()

def catch(*exc_types: type[BaseException]):
    def wrapper(func: Callable[[], Any]) -> BaseException | None:
        try: func()
        except exc_types as e: return e
    return wrapper
