from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from .managers import PackageManager, PackageManagerError

if TYPE_CHECKING:
    from hatchling.bridge.app import Application

VENDOR_DIRNAME = ".shadow-vendor"


class VendorResolutionError(Exception):
    """Raised when dependencies cannot be resolved/vendored from the current build context."""


def vendor_dir(root: str) -> Path:
    return Path(root) / VENDOR_DIRNAME


def is_vendored(root: str) -> bool:
    vendor = vendor_dir(root)
    return vendor.exists() and any(vendor.iterdir())


def vendor(root: str, app: Application) -> Path:
    """Resolve and vendor every runtime dependency of `root` into `.shadow-vendor`.

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
            f"workspace first, so its `.shadow-vendor` directory can be reused by the `wheel` target.\n{e}"
        )
        raise VendorResolutionError(msg) from e

    app.display_success("[shadow] Resolved runtime dependencies")
    return target
