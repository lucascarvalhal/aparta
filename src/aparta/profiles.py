"""Modelo e persistência dos perfis em ~/.config/aparta/profiles.toml."""

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
    """Diretório de configuração do aparta (override via APARTA_CONFIG_DIR p/ testes)."""
    override = os.environ.get("APARTA_CONFIG_DIR")
    if override:
        return Path(override)
    return Path.home() / ".config" / "aparta"


def profiles_path() -> Path:
    return config_dir() / "profiles.toml"


@dataclass
class Profile:
    name: str
    root: str  # pasta raiz dos projetos (ex.: ~/pessoal)
    git_email: str
    git_name: str = ""
    ssh_key: str = ""  # caminho da chave SSH específica
    ssh_alias: str = ""  # alias de host p/ reescrever remotes https (url insteadOf)
    gh_user: str = ""  # conta do GitHub CLI
    gcloud_account: str = ""
    gcloud_project: str = ""
    agents: list[str] = field(default_factory=lambda: ["claude-code"])

    @property
    def root_path(self) -> Path:
        return Path(self.root).expanduser()

    @property
    def gh_config_dir(self) -> Path:
        return Path.home() / ".config" / f"gh-{self.name}"

    def env(self) -> dict[str, str]:
        """Variáveis de ambiente que este perfil injeta nos agentes."""
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
