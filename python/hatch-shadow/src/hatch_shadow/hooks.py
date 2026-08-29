from hatchling.plugin import hookimpl

from .builder import ShadowBuildHook
from .target import ShadowVendorBuilder


@hookimpl
def hatch_register_build_hook():
    return ShadowBuildHook


@hookimpl
def hatch_register_builder():
    return ShadowVendorBuilder
