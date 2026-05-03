from collections.abc import Callable
from typing import Any

from commons.types import Decorator


def constant[T](func: Callable[[], T]) -> T: ...

def catch(*exc_types: type[BaseException]) -> Decorator[Callable[[], Any], BaseException | None]: ...
