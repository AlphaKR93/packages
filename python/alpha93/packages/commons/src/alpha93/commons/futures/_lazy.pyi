import sys
from types import ModuleType

if sys.version_info >= (3, 15):
    from builtins import __lazy_import__
else:
    def __lazy_import__(name: str) -> ModuleType:
        """
        Lazily imports a module.

        Returns either the module to be imported or a imp.lazy_module object which
        indicates the module to be lazily imported.
        """
