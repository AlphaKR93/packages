import importlib.util as importlib
import sys

from terser_hints import not_none

if sys.version_info >= (3, 15):
    lazy = __lazy_import__  # ruff: ignore[undefined-name]
else:
    def lazy(name: str, /):
        try:
            return sys.modules[name]
        except KeyError:
            spec = not_none(importlib.find_spec(name))
            module = importlib.module_from_spec(spec)
            loader = importlib.LazyLoader(not_none(spec.loader))
            loader.exec_module(module)
            return module
