from typing import Protocol, Any

from hatchling.bridge.app import Application
from hatchling.metadata.core import ProjectMetadata


class HatchHookInterface(Protocol):
    @property
    def app(self, /) -> Application:
        """
        An instance of [Application](../utilities.md#hatchling.bridge.app.Application).
        """

    @property
    def root(self, /) -> str:
        """
        The root of the project tree.
        """

    @property
    def config(self, /) -> dict[str, Any]:
        """
        The cumulative hook configuration.

        ```toml config-example
        [tool.hatch.build.hooks.<PLUGIN_NAME>]
        [tool.hatch.build.targets.<TARGET_NAME>.hooks.<PLUGIN_NAME>]
        ```
        """

    @property
    def metadata(self, /) -> ProjectMetadata:
        ...

    @property
    def directory(self, /) -> str:
        """
        The build directory.
        """

    @property
    def target_name(self, /) -> str:
        """
        The plugin name of the build target.
        """

    def dependencies(self, /) -> list[str]:  # noqa: PLR6301
        """
        A list of extra [dependencies](../../config/dependency.md) that must be installed
        prior to builds.

        !!! warning
            - For this to have any effect the hook dependency itself cannot be dynamic and
                must always be defined in `build-system.requires`.
            - As the hook must be imported to call this method, imports that require these
                dependencies must be evaluated lazily.
        """
