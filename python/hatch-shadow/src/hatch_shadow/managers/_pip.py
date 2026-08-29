import sys
from pathlib import Path
from subprocess import CalledProcessError, run

from hatch_shadow.managers import PackageManager, PackageManagerError


class PipPackageManager(PackageManager):
    @classmethod
    def is_supported(cls, root: str) -> bool:
        return (Path(root) / "requirements.txt").exists()

    def install_packages(self, target: str):
        args = [
            sys.executable,
            "-m", "pip",
            "install",
            "--upgrade",
            "--disable-pip-version-check",
            "--no-python-version-warning",
            "-r",
            str(Path(self.root) / "requirements.txt"),
            "-t",
            target,
        ]
        try:
            run(args, capture_output=True, text=True, check=True)
        except CalledProcessError as e:
            msg = f"Command `{' '.join(args)}` failed:\n{e.stderr}"
            raise PackageManagerError(msg) from e
