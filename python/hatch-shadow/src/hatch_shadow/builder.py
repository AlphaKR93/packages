import shutil
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

from ._compat import override
from .vendor import EMBEDDED_VENDOR_DIRNAME, embedded_vendor_dir, is_embedded_vendored, is_vendored, vendor, vendor_dir


class ShadowBuildHook(BuildHookInterface):
    PLUGIN_NAME = "shadow"

    @override
    def initialize(self, version: str, build_data: dict[str, Any]):
        # An editable wheel (`uv sync`, `pip install -e`) runs straight from
        # source. Vendored files force-included here would collide in a
        # shared virtualenv with the real, independently-installed copies of
        # those same packages, so editable builds get none at all.
        if version != "standard":
            return

        if self.target_name == "wheel" and is_embedded_vendored(self.root):
            # This wheel is being built from an extracted sdist that already
            # carries a vendored payload (see the `sdist` branch below), so
            # reuse it without needing workspace access ourselves.
            self.app.display_info("[shadow] Reusing dependencies bundled with the sdist")
            build_data["force_include"][str(embedded_vendor_dir(self.root))] = ""
            return

        vendor_path = vendor_dir(self.root)
        if is_vendored(self.root):
            self.app.display_info("[shadow] Reusing dependencies vendored by the `shadow-vendor` target")
        else:
            vendor_path = vendor(self.root, self.app)

        if self.target_name == "wheel":
            # a site-packages layout requires the vendored packages at the
            # archive root, so flatten them there.
            build_data["force_include"][str(vendor_path)] = ""
        else:
            # `uv build` builds the wheel from a freshly extracted copy of
            # the sdist in an isolated cache directory, cut off from the
            # workspace this hook needs to resolve dependencies. Bundling
            # the vendored files inside the sdist under a fixed, reserved
            # name lets that later wheel-from-sdist build reuse them
            # without needing workspace access itself (see above).
            build_data["force_include"][str(vendor_path)] = EMBEDDED_VENDOR_DIRNAME

    @override
    def clean(self, versions: list[str]):
        shutil.rmtree(vendor_dir(self.root), ignore_errors=True)
