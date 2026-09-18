"""Codex CLI adapter: shell_environment_policy.set in .codex/config.toml."""

from __future__ import annotations

from pathlib import Path

from ..profiles import is_managed_env_key
from .base import AgentAdapter, TomlFormat


class CodexAdapter(AgentAdapter):
    name = "codex"
    display_name = "Codex CLI"
    format = TomlFormat()
    hook_key = ("hooks", "SessionStart")

    def env_path(self, repo: Path) -> Path:
        return repo / ".codex" / "config.toml"

    def env_of(self, doc: dict) -> dict[str, str]:
        legacy = doc.get("env")
        policy = doc.get("shell_environment_policy")
        current = policy.get("set") if isinstance(policy, dict) else None
        migrated = {k: v for k, v in legacy.items() if is_managed_env_key(k)} if isinstance(legacy, dict) else {}
        return {**migrated, **(current if isinstance(current, dict) else {})}

    def set_env(self, doc: dict, env: dict[str, str]) -> None:
        legacy = doc.get("env")
        if isinstance(legacy, dict):
            for key in [k for k in legacy if is_managed_env_key(k)]:
                legacy.pop(key)
            if not legacy:
                doc.pop("env")
        policy = doc.get("shell_environment_policy")
        if not isinstance(policy, dict):
            policy = {}
        if env:
            policy["set"] = env
        else:
            policy.pop("set", None)
        if policy:
            doc["shell_environment_policy"] = policy
        else:
            doc.pop("shell_environment_policy", None)

    def hook_entry(self) -> dict:
        return {
            "matcher": "startup|resume",
            "hooks": [{"type": "command", "command": self.hook_command}],
        }
