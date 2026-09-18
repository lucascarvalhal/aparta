"""gcloud backend, with two isolation levels."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from ..fsutil import SafeWriter
from ..i18n import _
from ..profiles import Profile
from . import Note

SEED_FILES = ("credentials.db",)


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
    if config_name:
        env["CLOUDSDK_ACTIVE_CONFIG_NAME"] = config_name
    return subprocess.run(args, env=env, capture_output=True, text=True, timeout=30)


def configuration_exists(name: str, config_dir: Path | None = None) -> bool:
    """Whether the named gcloud configuration already exists (locale-safe)."""
    r = _run(["gcloud", "config", "configurations", "describe", name], config_dir=config_dir)
    return r.returncode == 0


def prune_credentials(db_path: Path, keep_account: str) -> bool:
    """Drop every other account from a copied credentials.db."""
    if not keep_account or not db_path.exists():
        return False
    try:
        import sqlite3

        with sqlite3.connect(db_path) as db:
            db.execute("DELETE FROM credentials WHERE account_id != ?", (keep_account,))
        return True
    except Exception:
        return False


def has_adc(profile_dir: Path) -> bool:
    """Whether the isolated dir already has its own application credentials."""
    return (profile_dir / "application_default_credentials.json").exists()


def prune_configurations(target: Path, keep: str) -> list[str]:
    """Drop named configurations that do not belong to this profile."""
    folder = target / "configurations"
    if not folder.is_dir():
        return []
    removed = []
    for item in sorted(folder.glob("config_*")):
        if item.name == f"config_{keep}":
            continue
        try:
            item.unlink()
        except OSError:
            continue
        removed.append(item.name[len("config_"):])
    return removed


def activate_configuration(target: Path, name: str) -> None:
    """Point the isolated dir at its own configuration, creating it if needed."""
    config_file = target / "configurations" / f"config_{name}"
    if not config_file.exists():
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text("[core]\n")
    (target / "active_config").write_text(name)


def seed_isolated_dir(
    target: Path, source: Path | None = None, keep_account: str = ""
) -> bool:
    """Copy credentials and configurations into a fresh isolated dir."""
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
    dropped = prune_configurations(target, profile.name)
    if dropped:
        notes.append(Note("info", _("[green]gcloud:[/green] dropped foreign configurations: {names}", names=", ".join(dropped))))
    activate_configuration(target, profile.name)
    for args in cmds:
        r = _run(args, config_name=profile.name, config_dir=target)
        if r.returncode != 0:
            notes.append(Note("error", _("[red]{cmd} failed:[/red] {error}", cmd=" ".join(args), error=r.stderr.strip())))
    notes.append(Note("info", _("[green]gcloud:[/green] isolated config dir ready for '{name}'", name=profile.name)))
    return notes
