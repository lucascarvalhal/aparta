"""Antigravity adapter (Google's agent-first IDE, a VS Code fork).

Injects into "terminal.integrated.env.{osx,linux}" in .vscode/settings.json,
which the integrated terminal (and agent-run commands) honors. If agent
commands do not inherit these variables in your build, combine with the
`direnv` adapter as a fallback.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..i18n import _
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
        raise ValueError(_(".vscode/settings.json is invalid")) from exc
    if not isinstance(data, dict):
        raise ValueError(_(".vscode/settings.json is not a JSON object"))
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

    def remove_env(self, repo: Path, keys: list[str], writer: SafeWriter) -> bool:
        path = self.settings_path(repo)
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            return False
        changed = False
        for platform_key in _PLATFORM_KEYS:
            env = data.get(platform_key)
            if isinstance(env, dict):
                for k in keys:
                    changed |= env.pop(k, None) is not None
        if not changed:
            return False
        return writer.write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    def validate(self, repo: Path, env: dict[str, str]) -> tuple[bool, str]:
        path = self.settings_path(repo)
        if not path.exists():
            return False, _(".vscode/settings.json missing")
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            return False, _(".vscode/settings.json is invalid")
        for key in _PLATFORM_KEYS:
            current = data.get(key, {})
            missing = [k for k, v in env.items() if current.get(k) != v]
            if missing:
                return False, _("{key} mismatch: {keys}", key=key, keys=", ".join(missing))
        return True, _("env ok")
