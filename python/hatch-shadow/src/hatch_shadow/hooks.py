from hatchling.plugin import hookimpl

from .builder import ShadowBuildHook


@hookimpl
def hatch_register_build_hook():
    return ShadowBuildHook
