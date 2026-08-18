"""Adapter Codex: seção [env] em .codex/config.toml do repositório (merge)."""

from __future__ import annotations

import sys
from pathlib import Path

import tomli_w

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

from ..fsutil import SafeWriter
from .base import AgentAdapter


def merge_codex_env(existing_text: str, env: dict[str, str]) -> str:
    data = tomllib.loads(existing_text) if existing_text.strip() else {}
    current = data.get("env", {})
    if not isinstance(current, dict):
        current = {}
    data["env"] = {**current, **env}
    return tomli_w.dumps(data)


class CodexAdapter(AgentAdapter):
    name = "codex"

    def config_path(self, repo: Path) -> Path:
        return repo / ".codex" / "config.toml"

    def detect(self, repo: Path) -> bool:
        return (repo / ".codex").exists()

    def inject(self, repo: Path, env: dict[str, str], writer: SafeWriter) -> bool:
        path = self.config_path(repo)
        existing = path.read_text() if path.exists() else ""
        return writer.write_text(path, merge_codex_env(existing, env))

    def validate(self, repo: Path, env: dict[str, str]) -> tuple[bool, str]:
        path = self.config_path(repo)
        if not path.exists():
            return False, "config.toml ausente"
        data = tomllib.loads(path.read_text())
        current = data.get("env", {})
        missing = [k for k, v in env.items() if current.get(k) != v]
        return (not missing, "env ok" if not missing else f"env divergente: {', '.join(missing)}")
