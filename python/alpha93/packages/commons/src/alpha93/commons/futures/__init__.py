if __debug__ and __import__("typing").TYPE_CHECKING:
    from ._lazy import __lazy_import__

__all__ = (
    "__lazy_import__",
)

def __getattr__(name: str, /):
    match name:
        case "__lazy_import__":
            from ._lazy import __lazy_import__

            return __lazy_import__
        case _:
            raise ImportError(name)
