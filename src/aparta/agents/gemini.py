"""Gemini CLI adapter: variables in .gemini/.env, the hook in .gemini/settings.json."""

from __future__ import annotations

from pathlib import Path

from .base import CHECK_JSON_COMMAND, DotenvAdapter, DotenvFormat, FileFormat, JsonFormat


class GeminiAdapter(DotenvAdapter):
    name = "gemini"
    display_name = "Gemini CLI"
    format = DotenvFormat('{k}="{v}"')
    hook_key = ("hooks", "SessionStart")
    hook_command = CHECK_JSON_COMMAND

    def env_path(self, repo: Path) -> Path:
        return repo / ".gemini" / ".env"

    def hook_path(self, repo: Path) -> Path:
        return repo / ".gemini" / "settings.json"

    def hook_format(self) -> FileFormat:
        return JsonFormat()

    def hook_entry(self) -> dict:
        return {
            "hooks": [
                {
                    "type": "command",
                    "command": self.hook_command,
                    "name": "aparta credential check",
                    "timeout": 5000,
                }
            ]
        }
