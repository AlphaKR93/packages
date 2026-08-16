import weakref

if __debug__ and __import__("typing").TYPE_CHECKING:
    from collections.abc import Callable

class Reference[T]:
    """Lazy-initialized weakref wrapper"""

    __slots__ = "__getter", "__ref"

    __ref: weakref.ReferenceType[T]
    __getter: Callable[[], T]

    def __init__(self, getter: Callable[[], T], /) -> None:
        self.__getter = getter

    def __call__(self, /) -> T:
        not_initialized: bool
        try:
            if (ref := self.__ref) and (obj := ref()):
                return obj
            not_initialized = False
        except AttributeError:
            not_initialized = True

        obj = self.__getter()
        if not_initialized:
            del self.__ref
        self.__ref = weakref.ref(obj)
        return obj
