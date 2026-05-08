if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Callable

constant = lambda _: _()

def catch[T : BaseException = BaseException](*exc_types: type[T]):
    def func[R](block: Callable[[], R], /) -> tuple[R, None] | tuple[None, T]:
        try: return block(), None
        except exc_types as e: return None, e
    return func
