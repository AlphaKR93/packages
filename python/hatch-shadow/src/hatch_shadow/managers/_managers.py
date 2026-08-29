from __future__ import annotations

from abc import ABC, abstractmethod


class PackageManagerError(Exception):
    """Raised when a package manager fails to resolve/install dependencies."""


class PackageManager(ABC):
    def __init__(self, root: str):
        self.root = root

    @staticmethod
    def get_package_manager(root: str) -> PackageManager:
        from ._uv import UvPackageManager
        from ._pip import PipPackageManager

        for pm in [
            UvPackageManager,
            PipPackageManager,
        ]:
            if pm.is_supported(root):
                return pm(root)
        raise ValueError("No supported package manager found")

    @classmethod
    @abstractmethod
    def is_supported(cls, root: str) -> bool:
        ...

    @abstractmethod
    def install_packages(self, target: str):
        ...
