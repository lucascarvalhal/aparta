"""Antigravity adapter (Google's agent-first IDE, a VS Code fork).

Injects into "terminal.integrated.env.{osx,linux}" in .vscode/settings.json,
which the integrated terminal (and agent-run commands) honors. If agent
commands do not inherit these variables in your build, combine with the
`direnv` adapter as a fallback.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..fsutil import SafeWriter
from .base import AgentAdapter

_PLATFORM_KEYS = (
    "terminal.integrated.env.osx",
    "terminal.integrated.env.linux",
    "terminal.integrated.env.windows",
)


def merge_vscode_settings(existing_text: str, env: dict[str, str]) -> str:
    """Merge env into terminal.integrated.env.{osx,linux}, preserving the rest."""
    try:
        data = json.loads(existing_text) if existing_text.strip() else {}
    except json.JSONDecodeError as exc:
        raise ValueError(".vscode/settings.json inválido") from exc
    if not isinstance(data, dict):
        raise ValueError(".vscode/settings.json não contém um objeto JSON")
    for key in _PLATFORM_KEYS:
        current = data.get(key, {})
        if not isinstance(current, dict):
            current = {}
        data[key] = {**current, **env}
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


class AntigravityAdapter(AgentAdapter):
    name = "antigravity"
    display_name = "Antigravity"

    def settings_path(self, repo: Path) -> Path:
        return repo / ".vscode" / "settings.json"

    def detect(self, repo: Path) -> bool:
        return True  # workspace settings apply to any repo

    def inject(self, repo: Path, env: dict[str, str], writer: SafeWriter) -> bool:
        path = self.settings_path(repo)
        existing = path.read_text() if path.exists() else ""
        return writer.write_text(path, merge_vscode_settings(existing, env))

    def validate(self, repo: Path, env: dict[str, str]) -> tuple[bool, str]:
        path = self.settings_path(repo)
        if not path.exists():
            return False, ".vscode/settings.json ausente"
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            return False, ".vscode/settings.json inválido"
        for key in _PLATFORM_KEYS:
            current = data.get(key, {})
            missing = [k for k, v in env.items() if current.get(k) != v]
            if missing:
                return False, f"{key} divergente: {', '.join(missing)}"
        return True, "env ok"
