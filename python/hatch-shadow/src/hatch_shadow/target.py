from typing import Any

from hatchling.builders.plugin.interface import BuilderInterface

from ._compat import override
from .vendor import vendor


class ShadowVendorBuilder(BuilderInterface):
    """Resolves and vendors runtime dependencies into `.shadow-vendor`.

    Runs against the live project tree, so it must be invoked from a context
    with real access to the package manager's workspace (e.g. `hatch build -t
    shadow-vendor` from within a uv workspace checkout), unlike the `wheel`
    target, which may run against an isolated, extracted-from-sdist copy of
    the project with no such access.
    """

    PLUGIN_NAME = "shadow-vendor"

    @override
    def get_version_api(self) -> dict[str, Any]:
        return {"standard": self.build_standard}

    def build_standard(self, directory: str, **build_data: Any) -> str:
        target = vendor(self.root, self.app)
        return str(target)
