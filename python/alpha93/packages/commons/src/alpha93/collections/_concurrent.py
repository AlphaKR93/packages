import threading

if __debug__ and __import__("typing").TYPE_CHECKING:
    from typing import Final


class GuardedValue[T]:
    __slots__ = "__lock", "__value"

    def __init__(self, value: T, lock: type[threading.Lock] = threading.Lock, /):
        self.__value: Final[T] = value
        self.__lock = lock()

    def __enter__(self, /) -> T:
        self.__lock.acquire()
        return self.__value

    def __exit__(self, /, *_):
        self.__lock.release()
