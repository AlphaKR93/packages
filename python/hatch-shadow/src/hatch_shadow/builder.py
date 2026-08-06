import shutil
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

from ._compat import override
from .vendor import is_vendored, vendor, vendor_dir


class ShadowBuildHook(BuildHookInterface):
    PLUGIN_NAME = "shadow"

    @override
    def initialize(self, version: str, build_data: dict[str, Any]):
        # Only the standard (non-editable) wheel actually needs vendored
        # dependencies:
        # - the sdist stays a plain source distribution. Bundling deps into
        #   it makes this package's own file listing double as a copy of
        #   its (possibly workspace-local) dependencies, which nests/
        #   duplicates whatever a workspace-aware installer like uv also
        #   installs for those same packages independently.
        # - an editable wheel (`uv sync`, `pip install -e`) runs straight
        #   from source. Vendored files force-included here would collide
        #   in a shared virtualenv with the real, independently-installed
        #   copies of those same packages.
        if self.target_name != "wheel" or version != "standard":
            return

        vendor_path = vendor_dir(self.root)
        if is_vendored(self.root):
            self.app.display_info("[shadow] Reusing dependencies vendored by the `shadow-vendor` target")
        else:
            vendor_path = vendor(self.root, self.app)

        # a site-packages layout requires the vendored packages at the
        # archive root, so flatten them there.
        build_data["force_include"][str(vendor_path)] = ""

    @override
    def clean(self, versions: list[str]):
        shutil.rmtree(vendor_dir(self.root), ignore_errors=True)
