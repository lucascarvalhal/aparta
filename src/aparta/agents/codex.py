"""Codex CLI adapter: [env] section in the repo's .codex/config.toml (merged)."""

from __future__ import annotations

import sys
from pathlib import Path

import tomli_w

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

from ..i18n import _
from ..fsutil import SafeWriter
from .base import CHECK_COMMAND, AgentAdapter, missing_keys


def merge_codex_env(existing_text: str, env: dict[str, str]) -> str:
    try:
        data = tomllib.loads(existing_text) if existing_text.strip() else {}
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(_("config.toml is invalid")) from exc
    current = data.get("env", {})
    if not isinstance(current, dict):
        current = {}
    data["env"] = {**current, **env}
    return tomli_w.dumps(data)


class CodexAdapter(AgentAdapter):
    name = "codex"
    display_name = "Codex CLI"

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
            return False, _("config.toml missing")
        try:
            data = tomllib.loads(path.read_text())
        except tomllib.TOMLDecodeError:
            return False, _("config.toml is invalid")
        current = data.get("env", {})
        missing = missing_keys(current if isinstance(current, dict) else {}, env)
        return (not missing, _("env ok") if not missing else _("env mismatch: {keys}", keys=", ".join(missing)))

    def remove_env(self, repo: Path, keys: list[str], writer: SafeWriter) -> bool:
        path = self.config_path(repo)
        if not path.exists():
            return False
        try:
            data = tomllib.loads(path.read_text())
        except tomllib.TOMLDecodeError:
            return False
        env = data.get("env", {})
        if not isinstance(env, dict) or not any(k in env for k in keys):
            return False
        for k in keys:
            env.pop(k, None)
        data["env"] = env
        return writer.write_text(path, tomli_w.dumps(data))

    def install_check(self, repo: Path, writer: SafeWriter) -> bool:
        """Add a SessionStart hook. Codex asks the user to trust it once."""
        path = self.config_path(repo)
        try:
            data = tomllib.loads(path.read_text()) if path.exists() else {}
        except tomllib.TOMLDecodeError:
            return False
        hooks = data.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            return False
        entries = hooks.setdefault("SessionStart", [])
        if not isinstance(entries, list):
            return False
        if any(CHECK_COMMAND in str(entry) for entry in entries):
            return False
        entries.append(
            {
                "matcher": "startup|resume",
                "hooks": [{"type": "command", "command": CHECK_COMMAND}],
            }
        )
        return writer.write_text(path, tomli_w.dumps(data))

    def uninstall_check(self, repo: Path, writer: SafeWriter) -> bool:
        path = self.config_path(repo)
        if not path.exists():
            return False
        try:
            data = tomllib.loads(path.read_text())
        except tomllib.TOMLDecodeError:
            return False
        hooks = data.get("hooks", {})
        entries = hooks.get("SessionStart", []) if isinstance(hooks, dict) else []
        remaining = [e for e in entries if CHECK_COMMAND not in str(e)]
        if len(remaining) == len(entries):
            return False
        if remaining:
            hooks["SessionStart"] = remaining
        else:
            hooks.pop("SessionStart", None)
            if not hooks:
                data.pop("hooks", None)
        return writer.write_text(path, tomli_w.dumps(data))

    def read_env(self, repo: Path) -> dict[str, str]:
        path = self.config_path(repo)
        if not path.exists():
            return {}
        try:
            env = tomllib.loads(path.read_text()).get("env", {})
        except tomllib.TOMLDecodeError:
            return {}
        return env if isinstance(env, dict) else {}
