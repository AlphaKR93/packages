from __future__ import annotations

import hashlib
import os
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from .managers import PackageManager, PackageManagerError

if TYPE_CHECKING:
    from hatchling.bridge.app import Application

VENDOR_DIRNAME = "shadow-vendor"

# The name vendored files are embedded under, relative to the project root,
# when they're bundled inside an sdist. `uv build` builds the wheel from a
# freshly extracted copy of that sdist in an isolated cache directory with
# no workspace access, so this lets that later wheel-from-sdist build find
# the payload with nothing more than a lookup relative to its own root.
EMBEDDED_VENDOR_DIRNAME = ".shadow-vendor"


class VendorResolutionError(Exception):
    """Raised when dependencies cannot be resolved/vendored from the current build context."""


def _cache_root() -> Path:
    if cache_home := os.environ.get("XDG_CACHE_HOME"):
        return Path(cache_home) / "hatch"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "hatch"
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(local_app_data) / "hatch" / "Cache"
    return Path.home() / ".cache" / "hatch"


def vendor_dir(root: str) -> Path:
    # Vendoring outside the project tree (rather than e.g. a `.shadow-vendor`
    # directory at the project root) sidesteps VCS-based file selection
    # entirely: a project-root directory must be un-ignored for the sdist to
    # carry it, which defeats the purpose of `.gitignore`-ing build output.
    resolved = Path(root).resolve()
    key = hashlib.sha256(str(resolved).encode()).hexdigest()[:16]
    return _cache_root() / VENDOR_DIRNAME / f"{resolved.name}-{key}"


def is_vendored(root: str) -> bool:
    vendor = vendor_dir(root)
    return vendor.exists() and any(vendor.iterdir())


def embedded_vendor_dir(root: str) -> Path:
    return Path(root) / EMBEDDED_VENDOR_DIRNAME


def is_embedded_vendored(root: str) -> bool:
    vendor = embedded_vendor_dir(root)
    return vendor.exists() and any(vendor.iterdir())


def vendor(root: str, app: Application) -> Path:
    """Resolve and vendor every runtime dependency of `root` into a cache directory.

    Requires real filesystem access to the project's package manager context
    (e.g. a reachable `uv.lock`/workspace for uv-managed projects), so this
    only succeeds when run against a live checkout, not an isolated,
    extracted-from-sdist build directory.
    """
    target = vendor_dir(root)

    app.display_waiting("[shadow] Resolving dependencies...")
    pm = PackageManager.get_package_manager(root)

    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)
    try:
        pm.install_packages(str(target))
    except PackageManagerError as e:
        shutil.rmtree(target, ignore_errors=True)
        msg = (
            "[shadow] Failed to resolve dependencies for vendoring. This usually means the build has "
            "no access to the package manager's workspace context (e.g. a wheel built from an "
            "isolated, extracted sdist). Run `hatch build -t shadow-vendor` from within the project's "
            f"workspace first, so its cached vendor directory can be reused by the `wheel` target.\n{e}"
        )
        raise VendorResolutionError(msg) from e

    app.display_success("[shadow] Resolved runtime dependencies")
    return target
