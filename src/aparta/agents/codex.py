"""Codex CLI adapter using project shell_environment_policy.set."""

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
from ..profiles import MANAGED_ENV_KEYS
from .base import CHECK_COMMAND, AgentAdapter, missing_keys


def merge_codex_env(existing_text: str, env: dict[str, str]) -> str:
    try:
        data = tomllib.loads(existing_text) if existing_text.strip() else {}
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(_("config.toml is invalid")) from exc
    policy = data.get("shell_environment_policy", {})
    if not isinstance(policy, dict):
        policy = {}
    current = policy.get("set", {})
    if not isinstance(current, dict):
        current = {}
    policy["set"] = {**current, **env}
    data["shell_environment_policy"] = policy

    old_env = data.get("env")
    if isinstance(old_env, dict):
        for key in MANAGED_ENV_KEYS:
            old_env.pop(key, None)
        if old_env:
            data["env"] = old_env
        else:
            data.pop("env", None)
    return tomli_w.dumps(data)


class CodexAdapter(AgentAdapter):
    name = "codex"
    display_name = "Codex CLI"

    def config_path(self, repo: Path) -> Path:
        return repo / ".codex" / "config.toml"

    def detect(self, repo: Path) -> bool:
        return True

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
        policy = data.get("shell_environment_policy", {})
        current = policy.get("set", {}) if isinstance(policy, dict) else {}
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
        changed = False
        policy = data.get("shell_environment_policy", {})
        env = policy.get("set", {}) if isinstance(policy, dict) else {}
        if isinstance(env, dict):
            for key in keys:
                if key in env:
                    env.pop(key)
                    changed = True
            if isinstance(policy, dict):
                if env:
                    policy["set"] = env
                else:
                    policy.pop("set", None)
                if policy:
                    data["shell_environment_policy"] = policy
                else:
                    data.pop("shell_environment_policy", None)
        old_env = data.get("env", {})
        if isinstance(old_env, dict):
            for key in keys:
                if key in old_env:
                    old_env.pop(key)
                    changed = True
            if old_env:
                data["env"] = old_env
            else:
                data.pop("env", None)
        return writer.write_text(path, tomli_w.dumps(data)) if changed else False

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
            data = tomllib.loads(path.read_text())
        except tomllib.TOMLDecodeError:
            return {}
        old_env = data.get("env", {})
        policy = data.get("shell_environment_policy", {})
        current = policy.get("set", {}) if isinstance(policy, dict) else {}
        result = old_env if isinstance(old_env, dict) else {}
        if isinstance(current, dict):
            result = {**result, **current}
        return result
