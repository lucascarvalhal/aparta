"""Generic direnv adapter: export lines in .envrc, the check as a trailing line."""

from __future__ import annotations

from pathlib import Path

from ..fsutil import SafeWriter
from .base import DotenvAdapter, DotenvFormat


class DirenvAdapter(DotenvAdapter):
    name = "direnv"
    display_name = "direnv (generic)"
    format = DotenvFormat('export {k}="{v}"')

    def env_path(self, repo: Path) -> Path:
        return repo / ".envrc"

    def install_check(self, repo: Path, writer: SafeWriter) -> bool:
        path = self.env_path(repo)
        existing = path.read_text() if path.exists() else ""
        if self.hook_command in existing:
            return False
        body = existing.rstrip("\n") + ("\n" if existing.strip() else "")
        return writer.write_text(path, f"{body}{self.hook_command} || true\n")

    def uninstall_check(self, repo: Path, writer: SafeWriter) -> bool:
        path = self.env_path(repo)
        if not path.exists():
            return False
        lines = path.read_text().splitlines()
        kept = [line for line in lines if self.hook_command not in line]
        if len(kept) == len(lines):
            return False
        return writer.write_text(path, "\n".join(kept) + ("\n" if kept else ""))
