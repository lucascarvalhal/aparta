"""Profile model and persistence (~/.config/aparta/profiles.toml)."""

from __future__ import annotations

from collections.abc import Mapping

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


def config_home() -> Path:
    """Base user config directory, honoring XDG_CONFIG_HOME."""
    return Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()


def config_dir() -> Path:
    """Config directory; APARTA_CONFIG_DIR overrides it (used by tests)."""
    override = os.environ.get("APARTA_CONFIG_DIR")
    if override:
        return Path(override)
    return config_home() / "aparta"


def gh_config_dir(profile_name: str, config_root: Path | None = None) -> Path:
    """Single source of truth for the gh-<profile> config dir convention."""
    return (config_root or config_home()) / f"gh-{profile_name}"


def gcloud_config_dir(profile_name: str, config_root: Path | None = None) -> Path:
    """Isolated gcloud config dir for a profile (CLOUDSDK_CONFIG)."""
    return (config_root or config_home()) / f"gcloud-{profile_name}"


def profiles_path() -> Path:
    return config_dir() / "profiles.toml"


MANAGED_ENV_KEYS = (
    "GH_CONFIG_DIR",
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "GH_ENTERPRISE_TOKEN",
    "GITHUB_ENTERPRISE_TOKEN",
    "GH_HOST",
    "GLAB_CONFIG_DIR",
    "GLAB_TOKEN",
    "GITLAB_TOKEN",
    "BITBUCKET_TOKEN",
    "CLOUDSDK_CONFIG",
    "CLOUDSDK_ACTIVE_CONFIG_NAME",
    "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE",
    "CLOUDSDK_AUTH_ACCESS_TOKEN",
    "CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT",
    "CLOUDSDK_CORE_ACCOUNT",
    "CLOUDSDK_CORE_PROJECT",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "GOOGLE_CLOUD_PROJECT",
    "GCLOUD_PROJECT",
    "CLOUDSDK_CORE_DISABLE_FILE_LOGGING",
    "AWS_PROFILE",
    "AWS_DEFAULT_PROFILE",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_SECURITY_TOKEN",
    "AWS_SHARED_CREDENTIALS_FILE",
    "AWS_CONFIG_FILE",
    "AWS_WEB_IDENTITY_TOKEN_FILE",
    "AWS_ROLE_ARN",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_KEY_0",
    "GIT_CONFIG_VALUE_0",
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_COMMON_DIR",
    "GIT_SSH_COMMAND",
    "GIT_AUTHOR_NAME",
    "GIT_AUTHOR_EMAIL",
    "GIT_COMMITTER_NAME",
    "GIT_COMMITTER_EMAIL",
)

MANAGED_ENV_PREFIXES = ("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")


def is_managed_env_key(key: str) -> bool:
    return key in MANAGED_ENV_KEYS or key.startswith(MANAGED_ENV_PREFIXES)


def clean_environment(base: Mapping[str, str], overlay: Mapping[str, str]) -> dict[str, str]:
    """Replace every aparta-owned selector instead of layering across clients."""
    clean = {key: value for key, value in base.items() if not is_managed_env_key(key)}
    clean.update(overlay)
    return clean


@dataclass
class Profile:
    name: str
    root: str
    git_email: str
    git_name: str = ""
    ssh_key: str = ""
    ssh_alias: str = ""
    git_host: str = "github.com"
    gh_user: str = ""
    gcloud_account: str = ""
    gcloud_project: str = ""
    gcloud_isolated: bool = False
    aws_profile: str = ""
    agents: list[str] = field(default_factory=lambda: ["claude-code"])
    applied_with: str = ""
    adopted_repos: list[str] = field(default_factory=list)

    @property
    def root_path(self) -> Path:
        return Path(self.root).expanduser()

    @property
    def gh_config_dir(self) -> Path:
        return gh_config_dir(self.name)

    @property
    def gcloud_config_dir(self) -> Path:
        return gcloud_config_dir(self.name)

    def env(self) -> dict[str, str]:
        """Environment variables this profile injects into agents."""
        env: dict[str, str] = {}
        if self.gh_user:
            env["GH_CONFIG_DIR"] = str(self.gh_config_dir)
        if self.gcloud_account or self.gcloud_project:
            if self.gcloud_account:
                env["CLOUDSDK_CORE_ACCOUNT"] = self.gcloud_account
            if self.gcloud_project:
                env["CLOUDSDK_CORE_PROJECT"] = self.gcloud_project
                env["GOOGLE_CLOUD_PROJECT"] = self.gcloud_project
                env["GCLOUD_PROJECT"] = self.gcloud_project
            if self.gcloud_isolated:
                env["CLOUDSDK_CONFIG"] = str(self.gcloud_config_dir)
                env["CLOUDSDK_ACTIVE_CONFIG_NAME"] = self.name
                adc = self.gcloud_config_dir / "application_default_credentials.json"
                env["GOOGLE_APPLICATION_CREDENTIALS"] = str(adc)
                env["CLOUDSDK_CORE_DISABLE_FILE_LOGGING"] = "1"
            else:
                env["CLOUDSDK_ACTIVE_CONFIG_NAME"] = self.name
        if self.aws_profile:
            env["AWS_PROFILE"] = self.aws_profile
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
            name: {k: v for k, v in asdict(p).items() if k != "name" and v != ""}
            for name, p in profiles.items()
        }
    }
    writer.write_text(path, tomli_w.dumps(doc), label=str(path))
