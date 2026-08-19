"""Profile model and persistence (~/.config/aparta/profiles.toml)."""

from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import tomli_w

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

from .fsutil import SafeWriter


def config_dir() -> Path:
    """Config directory; APARTA_CONFIG_DIR overrides it (used by tests)."""
    override = os.environ.get("APARTA_CONFIG_DIR")
    if override:
        return Path(override)
    return Path.home() / ".config" / "aparta"


def profiles_path() -> Path:
    return config_dir() / "profiles.toml"


@dataclass
class Profile:
    name: str
    root: str  # projects root folder (e.g. ~/personal)
    git_email: str
    git_name: str = ""
    ssh_key: str = ""  # dedicated SSH key path
    ssh_alias: str = ""  # SSH host alias for url insteadOf remote rewriting
    gh_user: str = ""  # GitHub CLI account
    gcloud_account: str = ""
    gcloud_project: str = ""
    agents: list[str] = field(default_factory=lambda: ["claude-code"])
    # repos outside root owned by this profile; identity is applied via a
    # local include in each .git/config, without moving the folder
    adopted_repos: list[str] = field(default_factory=list)

    @property
    def root_path(self) -> Path:
        return Path(self.root).expanduser()

    @property
    def gh_config_dir(self) -> Path:
        return Path.home() / ".config" / f"gh-{self.name}"

    def env(self) -> dict[str, str]:
        """Environment variables this profile injects into agents."""
        env: dict[str, str] = {}
        if self.gh_user:
            env["GH_CONFIG_DIR"] = str(self.gh_config_dir)
        if self.gcloud_account or self.gcloud_project:
            env["CLOUDSDK_ACTIVE_CONFIG_NAME"] = self.name
        return env


def load_profiles(path: Path | None = None) -> dict[str, Profile]:
    path = path or profiles_path()
    if not path.exists():
        return {}
    data = tomllib.loads(path.read_text())
    result: dict[str, Profile] = {}
    for name, raw in data.get("profiles", {}).items():
        fields = {k: v for k, v in raw.items() if k in Profile.__dataclass_fields__}
        result[name] = Profile(name=name, **{k: v for k, v in fields.items() if k != "name"})
    return result


def save_profiles(
    profiles: dict[str, Profile],
    writer: SafeWriter,
    path: Path | None = None,
) -> None:
    path = path or profiles_path()
    doc = {
        "profiles": {
            name: {k: v for k, v in asdict(p).items() if k != "name" and v not in ("", [])}
            for name, p in profiles.items()
        }
    }
    writer.write_text(path, tomli_w.dumps(doc), label=str(path))
