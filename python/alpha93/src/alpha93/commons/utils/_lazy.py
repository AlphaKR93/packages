import sys
import importlib.util as importlib


def lazy(name: str, /):
    try:
        return sys.modules[name]
    except KeyError:
        spec = importlib.find_spec(name)
        module = importlib.module_from_spec(spec)
        loader = importlib.LazyLoader(spec.loader)
        loader.exec_module(module)
        return module
