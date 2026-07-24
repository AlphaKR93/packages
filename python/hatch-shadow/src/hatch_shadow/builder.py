import tempfile
from typing import override, Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

from .managers import PackageManager


class ShadowBuildHook(BuildHookInterface):
    PLUGIN_NAME = "shadow"

    __vendor: str

    @override
    def initialize(self, version: str, build_data: dict[str, Any]):
        self.app.display_waiting("[shadow] Resolving dependencies...")
        pm = PackageManager.get_package_manager(self.build_config.root)

        self.__vendor = tempfile.mkdtemp()
        self.app.display_info(f"[shadow] Downloading dependencies to: {self.__vendor}")

        pm.install_packages(self.__vendor)
        build_data["force_include"][self.__vendor] = ""
        self.app.display_success("[shadow] Resolved runtime dependencies")

    @override
    def clean(self, versions: list[str]):
        import shutil

        shutil.rmtree(self.__vendor)
