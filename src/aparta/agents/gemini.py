"""Gemini CLI adapter: variables in <repo>/.gemini/.env (native mechanism).

Gemini CLI loads .env files automatically, checking .gemini/.env before the
project's own .env, so this location never clashes with application config.
"""

from __future__ import annotations

from pathlib import Path

from ..i18n import _
from ..fsutil import SafeWriter
from .base import AgentAdapter, merge_env_lines, missing_keys, parse_env_lines, remove_env_lines


def merge_dotenv(existing_text: str, env: dict[str, str]) -> str:
    return merge_env_lines(existing_text, env, '{k}="{v}"')


class GeminiAdapter(AgentAdapter):
    name = "gemini"
    display_name = "Gemini CLI"

    def env_path(self, repo: Path) -> Path:
        return repo / ".gemini" / ".env"

    def detect(self, repo: Path) -> bool:
        return True  # .gemini/ is created on demand; always applicable

    def inject(self, repo: Path, env: dict[str, str], writer: SafeWriter) -> bool:
        path = self.env_path(repo)
        existing = path.read_text() if path.exists() else ""
        return writer.write_text(path, merge_dotenv(existing, env))

    def validate(self, repo: Path, env: dict[str, str]) -> tuple[bool, str]:
        path = self.env_path(repo)
        if not path.exists():
            return False, _(".gemini/.env missing")
        missing = missing_keys(parse_env_lines(path.read_text()), env)
        return (not missing, _("env ok") if not missing else _("missing: {keys}", keys=", ".join(missing)))

    def remove_env(self, repo: Path, keys: list[str], writer: SafeWriter) -> bool:
        path = self.env_path(repo)
        if not path.exists():
            return False
        return writer.write_text(path, remove_env_lines(path.read_text(), keys))

    def read_env(self, repo: Path) -> dict[str, str]:
        path = self.env_path(repo)
        return parse_env_lines(path.read_text()) if path.exists() else {}
