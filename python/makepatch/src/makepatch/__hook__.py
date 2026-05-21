from hatchling.plugin import hookimpl
from makepatch.hooks import PatcherBuildHook


@hookimpl
def hatch_register_build_hook():
    return PatcherBuildHook
