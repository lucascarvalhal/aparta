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


@dataclass
class Profile:
    name: str
    root: str  # projects root folder (e.g. ~/personal)
    git_email: str
    git_name: str = ""
    ssh_key: str = ""  # dedicated SSH key path
    ssh_alias: str = ""  # SSH host alias for url insteadOf remote rewriting
    git_host: str = "github.com"  # host whose remote URLs the alias rewrites
    gh_user: str = ""  # GitHub CLI account
    gcloud_account: str = ""
    gcloud_project: str = ""
    # isolated mode gives the profile its own gcloud config dir, which also
    # isolates credentials and the application default credentials the SDKs use
    gcloud_isolated: bool = False
    aws_profile: str = ""  # named profile in ~/.aws/config, selected via AWS_PROFILE
    agents: list[str] = field(default_factory=lambda: ["claude-code"])
    # repos outside root owned by this profile; identity is applied via a
    # local include in each .git/config, without moving the folder
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
            if self.gcloud_isolated:
                # the whole gcloud config dir is the profile's, so credentials
                # and ADC are isolated too, not just the active configuration
                env["CLOUDSDK_CONFIG"] = str(self.gcloud_config_dir)
                # gcloud, Python and Java honor CLOUDSDK_CONFIG, but the Node
                # and Go libraries (so Terraform too) hardcode the global ADC
                # path; pointing at the file directly is honored by all of them
                adc = self.gcloud_config_dir / "application_default_credentials.json"
                if adc.exists():
                    env["GOOGLE_APPLICATION_CREDENTIALS"] = str(adc)
                # each isolated dir would otherwise grow its own log tree
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
    # Omit only empty strings: an explicitly empty list (e.g. agents=[])
    # must survive the round-trip instead of falling back to the default.
    doc = {
        "profiles": {
            name: {k: v for k, v in asdict(p).items() if k != "name" and v != ""}
            for name, p in profiles.items()
        }
    }
    writer.write_text(path, tomli_w.dumps(doc), label=str(path))
