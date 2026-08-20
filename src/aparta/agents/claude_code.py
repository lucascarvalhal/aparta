"""Claude Code adapter: "env" field in .claude/settings.local.json (merged)."""

from __future__ import annotations

import json
from pathlib import Path

from ..i18n import _
from ..fsutil import SafeWriter
from .base import CHECK_COMMAND, AgentAdapter, missing_keys


def merge_settings_env(existing_text: str, env: dict[str, str]) -> str:
    """Merge the env object, preserving everything else in the JSON."""
    try:
        data = json.loads(existing_text) if existing_text.strip() else {}
    except json.JSONDecodeError as exc:
        raise ValueError(_("settings.local.json is invalid")) from exc
    if not isinstance(data, dict):
        raise ValueError(_("settings.local.json is not a JSON object"))
    current_env = data.get("env", {})
    if not isinstance(current_env, dict):
        current_env = {}
    data["env"] = {**current_env, **env}
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


class ClaudeCodeAdapter(AgentAdapter):
    name = "claude-code"
    display_name = "Claude Code"

    def settings_path(self, repo: Path) -> Path:
        return repo / ".claude" / "settings.local.json"

    def detect(self, repo: Path) -> bool:
        return True  # applies to any repo

    def inject(self, repo: Path, env: dict[str, str], writer: SafeWriter) -> bool:
        path = self.settings_path(repo)
        existing = path.read_text() if path.exists() else ""
        merged = merge_settings_env(existing, env)
        return writer.write_text(path, merged)

    def validate(self, repo: Path, env: dict[str, str]) -> tuple[bool, str]:
        path = self.settings_path(repo)
        if not path.exists():
            return False, _("settings.local.json missing")
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            return False, _("settings.local.json is invalid")
        current = data.get("env", {})
        missing = missing_keys(current if isinstance(current, dict) else {}, env)
        if missing:
            return False, _("env mismatch: {keys}", keys=", ".join(missing))
        return True, _("env ok")

    def remove_env(self, repo: Path, keys: list[str], writer: SafeWriter) -> bool:
        path = self.settings_path(repo)
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            return False
        env = data.get("env", {})
        if not isinstance(env, dict) or not any(k in env for k in keys):
            return False
        for k in keys:
            env.pop(k, None)
        data["env"] = env
        return writer.write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    def install_check(self, repo: Path, writer: SafeWriter) -> bool:
        """Add a SessionStart hook that runs the credential check."""
        path = self.settings_path(repo)
        try:
            data = json.loads(path.read_text()) if path.exists() else {}
        except json.JSONDecodeError:
            return False
        if not isinstance(data, dict):
            return False
        hooks = data.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            return False
        entries = hooks.setdefault("SessionStart", [])
        if not isinstance(entries, list):
            return False
        if any(CHECK_COMMAND in json.dumps(entry) for entry in entries):
            return False
        entries.append({"hooks": [{"type": "command", "command": CHECK_COMMAND}]})
        return writer.write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    def uninstall_check(self, repo: Path, writer: SafeWriter) -> bool:
        path = self.settings_path(repo)
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            return False
        hooks = data.get("hooks", {})
        entries = hooks.get("SessionStart", []) if isinstance(hooks, dict) else []
        remaining = [e for e in entries if CHECK_COMMAND not in json.dumps(e)]
        if len(remaining) == len(entries):
            return False
        if remaining:
            hooks["SessionStart"] = remaining
        else:
            hooks.pop("SessionStart", None)
            if not hooks:
                data.pop("hooks", None)
        return writer.write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    def read_env(self, repo: Path) -> dict[str, str]:
        path = self.settings_path(repo)
        if not path.exists():
            return {}
        try:
            env = json.loads(path.read_text()).get("env", {})
        except (json.JSONDecodeError, AttributeError):
            return {}
        return env if isinstance(env, dict) else {}
