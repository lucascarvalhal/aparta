"""gcloud backend, with two isolation levels.

Light mode selects a named configuration through CLOUDSDK_ACTIVE_CONFIG_NAME:
cheap, but credentials and the application default credentials stay global, so
SDKs and Terraform ignore the profile.

Isolated mode gives the profile its own config directory through
CLOUDSDK_CONFIG, the same shape the gh backend uses. Credentials, named
configurations and the ADC file live inside it, so everything that reads
gcloud state honors the profile. The directory is seeded from the global one
so it starts already authenticated, copying only the credential and
configuration files (never the logs and cache, which dominate the size).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from ..fsutil import SafeWriter
from ..i18n import _
from ..profiles import Profile
from . import Note

# The minimum that makes an isolated dir start authenticated. access_tokens.db
# is a cache gcloud re-mints, and logs/, virtenv/ and cache/ are the bulk of
# the global dir (over 200MB on a working machine), so none of them are copied.
SEED_FILES = (
    "credentials.db",
    "active_config",
    "application_default_credentials.json",
)
SEED_DIRS = ("configurations",)


def gcloud_home(config_root: Path | None = None) -> Path:
    """The global gcloud config dir, honoring CLOUDSDK_CONFIG."""
    if config_root is not None:
        return config_root
    override = os.environ.get("CLOUDSDK_CONFIG")
    if override:
        return Path(override).expanduser()
    from ..profiles import config_home

    return config_home() / "gcloud"


def _run(
    args: list[str],
    config_name: str | None = None,
    config_dir: Path | None = None,
) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if config_dir is not None:
        env["CLOUDSDK_CONFIG"] = str(config_dir)
        env.pop("CLOUDSDK_ACTIVE_CONFIG_NAME", None)
    elif config_name:
        env["CLOUDSDK_ACTIVE_CONFIG_NAME"] = config_name
    return subprocess.run(args, env=env, capture_output=True, text=True, timeout=30)


def configuration_exists(name: str, config_dir: Path | None = None) -> bool:
    """Whether the named gcloud configuration already exists (locale-safe)."""
    r = _run(["gcloud", "config", "configurations", "describe", name], config_dir=config_dir)
    return r.returncode == 0


def prune_credentials(db_path: Path, keep_account: str) -> bool:
    """Drop every other account from a copied credentials.db.

    Without this the copy carries every refresh token the machine has, which
    would make the isolation a convenience, not a boundary. Any failure leaves
    the database untouched: the profile still works, just less isolated.
    """
    if not keep_account or not db_path.exists():
        return False
    try:
        import sqlite3

        with sqlite3.connect(db_path) as db:
            db.execute("DELETE FROM credentials WHERE account_id != ?", (keep_account,))
        return True
    except Exception:
        return False


def seed_isolated_dir(
    target: Path, source: Path | None = None, keep_account: str = ""
) -> bool:
    """Copy credentials and configurations into a fresh isolated dir.

    Returns True when something was copied. Existing directories are left
    alone so a profile never loses credentials it already has.
    """
    if target.exists():
        return False
    source = source or gcloud_home()
    target.mkdir(parents=True, mode=0o700, exist_ok=True)
    copied = False
    if source.exists():
        for name in SEED_FILES:
            origin = source / name
            if origin.exists():
                destination = target / name
                shutil.copy2(origin, destination)
                if destination.suffix in (".db", ".json"):
                    destination.chmod(0o600)
                copied = True
        for name in SEED_DIRS:
            origin = source / name
            if origin.is_dir():
                shutil.copytree(origin, target / name, dirs_exist_ok=True)
                copied = True
    prune_credentials(target / "credentials.db", keep_account)
    return copied


def apply_gcloud(profile: Profile, writer: SafeWriter) -> list[Note]:
    notes: list[Note] = []
    if not (profile.gcloud_account or profile.gcloud_project):
        return notes

    return (
        _apply_isolated(profile, writer, notes)
        if profile.gcloud_isolated
        else _apply_named(profile, writer, notes)
    )


def _apply_named(profile: Profile, writer: SafeWriter, notes: list[Note]) -> list[Note]:
    name = profile.name
    cmds: list[tuple[list[str], str | None]] = [
        (["gcloud", "config", "configurations", "create", name, "--no-activate"], None)
    ]
    if profile.gcloud_account:
        cmds.append((["gcloud", "config", "set", "account", profile.gcloud_account], name))
    if profile.gcloud_project:
        cmds.append((["gcloud", "config", "set", "project", profile.gcloud_project], name))

    if writer.dry_run:
        for args, cfg in cmds:
            prefix = f"CLOUDSDK_ACTIVE_CONFIG_NAME={cfg} " if cfg else ""
            notes.append(Note("info", f"[yellow]--dry-run[/yellow] {prefix}{' '.join(args)}"))
        return notes

    if not configuration_exists(name):
        create = _run(*cmds[0])
        if create.returncode != 0:
            notes.append(Note("error", _("[red]gcloud configurations create failed:[/red] {error}", error=create.stderr.strip())))
            return notes
    for args, cfg in cmds[1:]:
        r = _run(args, cfg)
        if r.returncode != 0:
            notes.append(Note("error", _("[red]{cmd} failed:[/red] {error}", cmd=" ".join(args), error=r.stderr.strip())))
    notes.append(Note("info", _("[green]gcloud:[/green] configuration '{name}' ready", name=name)))
    return notes


def _apply_isolated(profile: Profile, writer: SafeWriter, notes: list[Note]) -> list[Note]:
    target = profile.gcloud_config_dir
    cmds = []
    if profile.gcloud_account:
        cmds.append(["gcloud", "config", "set", "account", profile.gcloud_account])
    if profile.gcloud_project:
        cmds.append(["gcloud", "config", "set", "project", profile.gcloud_project])

    if writer.dry_run:
        if not target.exists():
            notes.append(Note("info", _("[yellow]--dry-run[/yellow] would seed {dst} from {src}", dst=target, src=gcloud_home())))
        for args in cmds:
            notes.append(Note("info", f"[yellow]--dry-run[/yellow] CLOUDSDK_CONFIG={target} {' '.join(args)}"))
        return notes

    if seed_isolated_dir(target, keep_account=profile.gcloud_account):
        notes.append(Note("info", _("[green]created:[/green] {dst}", dst=target)))
    for args in cmds:
        r = _run(args, config_dir=target)
        if r.returncode != 0:
            notes.append(Note("error", _("[red]{cmd} failed:[/red] {error}", cmd=" ".join(args), error=r.stderr.strip())))
    notes.append(Note("info", _("[green]gcloud:[/green] isolated config dir ready for '{name}'", name=profile.name)))
    return notes
