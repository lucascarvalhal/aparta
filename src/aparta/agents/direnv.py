"""Generic direnv adapter: `export VAR=...` lines in .envrc (merged)."""

from __future__ import annotations

from pathlib import Path

from ..i18n import _
from ..fsutil import SafeWriter
from .base import AgentAdapter, merge_env_lines, missing_keys, parse_env_lines


def merge_envrc(existing_text: str, env: dict[str, str]) -> str:
    return merge_env_lines(existing_text, env, 'export {k}="{v}"')


class DirenvAdapter(AgentAdapter):
    name = "direnv"
    display_name = "direnv (generic)"

    def envrc_path(self, repo: Path) -> Path:
        return repo / ".envrc"

    def detect(self, repo: Path) -> bool:
        return True

    def inject(self, repo: Path, env: dict[str, str], writer: SafeWriter) -> bool:
        path = self.envrc_path(repo)
        existing = path.read_text() if path.exists() else ""
        return writer.write_text(path, merge_envrc(existing, env))

    def validate(self, repo: Path, env: dict[str, str]) -> tuple[bool, str]:
        path = self.envrc_path(repo)
        if not path.exists():
            return False, _(".envrc missing")
        missing = missing_keys(parse_env_lines(path.read_text()), env)
        return (not missing, _("env ok") if not missing else _("missing: {keys}", keys=", ".join(missing)))

    def read_env(self, repo: Path) -> dict[str, str]:
        path = self.envrc_path(repo)
        return parse_env_lines(path.read_text()) if path.exists() else {}
