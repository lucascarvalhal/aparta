"""Adapter genérico direnv: linhas `export VAR=...` no .envrc (adiciona só se ausentes)."""

from __future__ import annotations

import re
from pathlib import Path

from ..fsutil import SafeWriter
from .base import AgentAdapter


def merge_envrc(existing_text: str, env: dict[str, str]) -> str:
    lines = existing_text.splitlines()
    out = list(lines)
    for key, value in env.items():
        pattern = re.compile(rf"^\s*export\s+{re.escape(key)}=")
        replaced = False
        for i, line in enumerate(out):
            if pattern.match(line):
                out[i] = f'export {key}="{value}"'
                replaced = True
                break
        if not replaced:
            out.append(f'export {key}="{value}"')
    return "\n".join(out) + "\n"


class DirenvAdapter(AgentAdapter):
    name = "direnv"

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
            return False, ".envrc ausente"
        text = path.read_text()
        missing = [k for k, v in env.items() if f'export {k}="{v}"' not in text]
        return (not missing, "env ok" if not missing else f"faltando: {', '.join(missing)}")
