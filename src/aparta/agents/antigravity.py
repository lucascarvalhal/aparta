"""Antigravity adapter: terminal env in .vscode/settings.json, the check as a folderOpen task."""

from __future__ import annotations

from pathlib import Path

from .base import AgentAdapter, JsonFormat

_PLATFORM_KEYS = (
    "terminal.integrated.env.windows",
    "terminal.integrated.env.linux",
    "terminal.integrated.env.osx",
)


class AntigravityAdapter(AgentAdapter):
    name = "antigravity"
    display_name = "Antigravity"
    format = JsonFormat()
    hook_key = ("tasks",)
    hook_defaults = {"version": "2.0.0"}

    def env_path(self, repo: Path) -> Path:
        return repo / ".vscode" / "settings.json"

    def env_of(self, doc: dict) -> dict[str, str]:
        env: dict[str, str] = {}
        for key in _PLATFORM_KEYS:
            current = doc.get(key)
            if isinstance(current, dict):
                env.update(current)
        return env

    def set_env(self, doc: dict, env: dict[str, str]) -> None:
        removed = set(self.env_of(doc)) - set(env)
        for key in _PLATFORM_KEYS:
            current = doc.get(key)
            merged = {k: v for k, v in current.items() if k not in removed} if isinstance(current, dict) else {}
            merged.update(env)
            if merged:
                doc[key] = merged
            else:
                doc.pop(key, None)

    def hook_path(self, repo: Path) -> Path:
        return repo / ".vscode" / "tasks.json"

    def hook_entry(self) -> dict:
        return {
            "label": "aparta check",
            "type": "shell",
            "command": self.hook_command,
            "presentation": {"reveal": "silent", "panel": "shared"},
            "runOptions": {"runOn": "folderOpen"},
        }

    def hook_is_empty(self, doc: dict) -> bool:
        return set(doc) <= set(self.hook_defaults)
