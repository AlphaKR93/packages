import shutil
from pathlib import Path
from typing import override, Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

from .managers import PackageManager


class ShadowBuildHook(BuildHookInterface):
    PLUGIN_NAME = "shadow"

    __vendor: Path

    @override
    def initialize(self, version: str, build_data: dict[str, Any]):
        self.__vendor = Path(self.build_config.root) / ".shadow-vendor"

        if not self.__vendor.exists() or not any(self.__vendor.iterdir()):
            # A wheel built from an already-vendored sdist (e.g. when this
            # package is resolved as a local/workspace dependency of another
            # project) has no uv.lock/workspace context to resolve against.
            # Vendoring already happened once while building the sdist, and
            # those files travel inside the sdist itself, so skip re-running it.
            self.app.display_waiting("[shadow] Resolving dependencies...")
            pm = PackageManager.get_package_manager(self.build_config.root)

            shutil.rmtree(self.__vendor, ignore_errors=True)
            self.__vendor.mkdir(parents=True)
            pm.install_packages(str(self.__vendor))
            self.app.display_success("[shadow] Resolved runtime dependencies")
        else:
            self.app.display_info("[shadow] Reusing dependencies vendored during sdist build")

        if self.target_name == "wheel":
            # a site-packages layout requires the vendored packages at the
            # archive root, so flatten them there.
            build_data["force_include"][str(self.__vendor)] = ""
        else:
            # keep the vendored files nested under a fixed name so they
            # survive an sdist round-trip (e.g. this package built as a
            # local/workspace dependency of another project), where the
            # resulting wheel-from-sdist build has no uv.lock/workspace
            # context to resolve dependencies against.
            build_data["force_include"][str(self.__vendor)] = ".shadow-vendor"

    @override
    def clean(self, versions: list[str]):
        shutil.rmtree(self.__vendor, ignore_errors=True)
