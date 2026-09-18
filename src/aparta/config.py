"""Where aparta keeps its own state, and the few ways it reads and writes it."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

from . import _toml

if TYPE_CHECKING:
    from .fsutil import SafeWriter


def config_home() -> Path:
    """Base user config directory, honoring XDG_CONFIG_HOME."""
    return Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()


def config_dir() -> Path:
    """aparta's own directory; APARTA_CONFIG_DIR overrides it, which the tests rely on."""
    override = os.environ.get("APARTA_CONFIG_DIR")
    return Path(override) if override else config_home() / "aparta"


def gh_config_dir(profile_name: str, config_root: Path | None = None) -> Path:
    return (config_root or config_home()) / f"gh-{profile_name}"


def gcloud_config_dir(profile_name: str, config_root: Path | None = None) -> Path:
    return (config_root or config_home()) / f"gcloud-{profile_name}"


def setting_path(name: str) -> Path:
    return config_dir() / name


def read_setting(name: str, allowed: tuple[str, ...] = (), default: str = "") -> str:
    """One-line preference file; anything unreadable or unexpected yields the default."""
    try:
        value = setting_path(name).read_text().strip()
    except OSError:
        return default
    if allowed and value not in allowed:
        return default
    return value or default


def write_setting(name: str, value: str) -> None:
    path = setting_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value + "\n")


def read_json(name: str) -> dict:
    """A JSON cache file; missing or corrupt means empty."""
    try:
        data = json.loads(setting_path(name).read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json(name: str, data: dict) -> None:
    """Best-effort cache write; a read-only config dir must not break a command."""
    try:
        path = setting_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
    except OSError:
        pass


def load_table(path: Path, section: str) -> dict[str, dict]:
    """Rows of a TOML file shaped {section: {name: {...}}}; missing file means no rows."""
    if not path.exists():
        return {}
    rows = _toml.loads(path.read_text()).get(section, {})
    return {name: dict(raw) for name, raw in rows.items() if isinstance(raw, dict)}


def save_table(path: Path, section: str, rows: dict[str, dict], writer: SafeWriter) -> None:
    writer.write_text(path, _toml.dumps({section: rows}), label=str(path))
