"""Gemini CLI adapter: variables in <repo>/.gemini/.env (native mechanism).

Gemini CLI loads .env files automatically, checking .gemini/.env before the
project's own .env, so this location never clashes with application config.
"""

from __future__ import annotations

from pathlib import Path

from ..i18n import _
from ..fsutil import SafeWriter
from .base import CHECK_JSON_COMMAND, AgentAdapter, merge_env_lines, missing_keys, parse_env_lines, remove_env_lines


def merge_dotenv(existing_text: str, env: dict[str, str]) -> str:
    return merge_env_lines(existing_text, env, '{k}="{v}"')


class GeminiAdapter(AgentAdapter):
    name = "gemini"
    display_name = "Gemini CLI"

    def env_path(self, repo: Path) -> Path:
        return repo / ".gemini" / ".env"

    def detect(self, repo: Path) -> bool:
        return True  # .gemini/ is created on demand; always applicable

    def inject(self, repo: Path, env: dict[str, str], writer: SafeWriter) -> bool:
        path = self.env_path(repo)
        existing = path.read_text() if path.exists() else ""
        return writer.write_text(path, merge_dotenv(existing, env))

    def validate(self, repo: Path, env: dict[str, str]) -> tuple[bool, str]:
        path = self.env_path(repo)
        if not path.exists():
            return False, _(".gemini/.env missing")
        missing = missing_keys(parse_env_lines(path.read_text()), env)
        return (not missing, _("env ok") if not missing else _("missing: {keys}", keys=", ".join(missing)))

    def remove_env(self, repo: Path, keys: list[str], writer: SafeWriter) -> bool:
        path = self.env_path(repo)
        if not path.exists():
            return False
        return writer.write_text(path, remove_env_lines(path.read_text(), keys))

    def settings_path(self, repo: Path) -> Path:
        return repo / ".gemini" / "settings.json"

    def install_check(self, repo: Path, writer: SafeWriter) -> bool:
        """Add a SessionStart hook. Gemini requires JSON-only output."""
        import json

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
        if any(CHECK_JSON_COMMAND in json.dumps(entry) for entry in entries):
            return False
        entries.append(
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": CHECK_JSON_COMMAND,
                        "name": "aparta credential check",
                        "timeout": 5000,
                    }
                ]
            }
        )
        return writer.write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    def uninstall_check(self, repo: Path, writer: SafeWriter) -> bool:
        import json

        path = self.settings_path(repo)
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            return False
        hooks = data.get("hooks", {})
        entries = hooks.get("SessionStart", []) if isinstance(hooks, dict) else []
        remaining = [e for e in entries if CHECK_JSON_COMMAND not in json.dumps(e)]
        if len(remaining) == len(entries):
            return False
        if remaining:
            hooks["SessionStart"] = remaining
        else:
            hooks.pop("SessionStart", None)
            if not hooks:
                data.pop("hooks", None)
        if data:
            return writer.write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        return writer.remove_file(path)

    def read_env(self, repo: Path) -> dict[str, str]:
        path = self.env_path(repo)
        return parse_env_lines(path.read_text()) if path.exists() else {}
