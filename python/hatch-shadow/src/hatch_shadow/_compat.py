import sys

if sys.version_info >= (3, 12):
    from typing import override
else:
    def override(func):
        return func

__all__ = ("override",)
