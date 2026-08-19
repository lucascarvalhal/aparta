"""Gemini CLI adapter: variables in <repo>/.gemini/.env (native mechanism).

Gemini CLI loads .env files automatically, checking .gemini/.env before the
project's own .env, so this location never clashes with application config.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..fsutil import SafeWriter
from .base import AgentAdapter


def merge_dotenv(existing_text: str, env: dict[str, str]) -> str:
    """Update or append KEY="value" lines, preserving the rest of the file."""
    lines = existing_text.splitlines()
    out = list(lines)
    for key, value in env.items():
        pattern = re.compile(rf"^\s*(export\s+)?{re.escape(key)}=")
        replaced = False
        for i, line in enumerate(out):
            if pattern.match(line):
                out[i] = f'{key}="{value}"'
                replaced = True
                break
        if not replaced:
            out.append(f'{key}="{value}"')
    return "\n".join(out) + "\n"


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
            return False, ".gemini/.env ausente"
        text = path.read_text()
        missing = [k for k, v in env.items() if f'{k}="{v}"' not in text]
        return (not missing, "env ok" if not missing else f"faltando: {', '.join(missing)}")
