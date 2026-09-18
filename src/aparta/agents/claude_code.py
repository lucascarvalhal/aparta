"""Claude Code adapter: the env object in .claude/settings.local.json."""

from __future__ import annotations

from pathlib import Path

from .base import AgentAdapter, JsonFormat


class ClaudeCodeAdapter(AgentAdapter):
    name = "claude-code"
    display_name = "Claude Code"
    format = JsonFormat()
    hook_key = ("hooks", "SessionStart")

    def env_path(self, repo: Path) -> Path:
        return repo / ".claude" / "settings.local.json"

    def env_of(self, doc: dict) -> dict[str, str]:
        env = doc.get("env")
        return env if isinstance(env, dict) else {}

    def set_env(self, doc: dict, env: dict[str, str]) -> None:
        if env:
            doc["env"] = env
        else:
            doc.pop("env", None)

    def hook_entry(self) -> dict:
        return {"hooks": [{"type": "command", "command": self.hook_command}]}
