import os
import tempfile
from pathlib import Path
from subprocess import PIPE, check_call, check_output

from hatch_shadow.managers import PackageManager


class UvPackageManager(PackageManager):
    @classmethod
    def is_supported(cls, root: str) -> bool:
        return (Path(root) / "pyproject.toml").exists()

    def install_packages(self, target: str):
        # uv resolves relative paths of workspace members / local path
        # dependencies against the workspace root (where uv.lock lives),
        # not against `self.root` or the process cwd.
        workspace_root = self.__find_workspace_root()

        remote_requirements = self.__export(no_local=True)
        full_requirements = self.__export(no_local=False)
        local_specs = self.__local_specs(full_requirements, remote_requirements)

        self.__install_remote(remote_requirements, target, workspace_root)
        self.__install_local(local_specs, target, workspace_root)

    def __find_workspace_root(self) -> Path:
        root = Path(self.root).resolve()
        for candidate in (root, *root.parents):
            if (candidate / "uv.lock").exists():
                return candidate
        return root

    def __export(self, *, no_local: bool) -> str:
        args = [
            "uv", "export",
            "--project", str(self.root),
            "--no-dev",
            "--no-header",
            "--no-emit-project",
        ]
        if no_local:
            # workspace members and local path dependencies have no prebuilt
            # wheel, so they are excluded here and installed separately.
            args += ["--no-emit-workspace", "--no-emit-local"]
        return check_output(args, stderr=PIPE, text=True)

    @staticmethod
    def __local_specs(full: str, remote: str) -> list[str]:
        def top_level_lines(text: str) -> list[str]:
            return [
                line.rstrip(" \\")
                for line in text.splitlines()
                if line and not line[0].isspace() and not line.startswith("#")
            ]

        remote_lines = set(top_level_lines(remote))
        return [
            line.removeprefix("-e ").strip()
            for line in top_level_lines(full)
            if line not in remote_lines
        ]

    @staticmethod
    def __install_remote(requirements: str, target: str, cwd: Path):
        fd, requirements_file = tempfile.mkstemp()
        os.close(fd)
        try:
            Path(requirements_file).write_text(requirements)
            check_call([
                "uv", "pip", "install",
                "--no-build",
                "--requirements", requirements_file,
                "--target", target,
            ], stdout=PIPE, stderr=PIPE, cwd=cwd)
        finally:
            Path(requirements_file).unlink()

    @staticmethod
    def __install_local(specs: list[str], target: str, cwd: Path):
        if not specs:
            return

        check_call([
            "uv", "pip", "install",
            "--no-deps",
            "--target", target,
            *specs,
        ], stdout=PIPE, stderr=PIPE, cwd=cwd)
