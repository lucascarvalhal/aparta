"""gcloud backend, with two isolation levels."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from ..fsutil import SafeWriter
from ..i18n import _
from ..profiles import Profile, clean_environment
from . import Note

SEED_FILES = ("credentials.db",)


def gcloud_home() -> Path:
    """The global gcloud config dir, honoring CLOUDSDK_CONFIG."""
    override = os.environ.get("CLOUDSDK_CONFIG")
    if override:
        return Path(override).expanduser()
    from ..config import config_home

    return config_home() / "gcloud"


def _run(
    args: list[str],
    config_name: str | None = None,
    config_dir: Path | None = None,
) -> subprocess.CompletedProcess:
    overlay: dict[str, str] = {}
    if config_dir is not None:
        overlay["CLOUDSDK_CONFIG"] = str(config_dir)
    if config_name:
        overlay["CLOUDSDK_ACTIVE_CONFIG_NAME"] = config_name
    env = clean_environment(os.environ, overlay)
    return subprocess.run(args, env=env, capture_output=True, text=True, timeout=30)


def configuration_exists(name: str) -> bool:
    """Whether the named gcloud configuration already exists (locale-safe)."""
    r = _run(["gcloud", "config", "configurations", "describe", name])
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


def prune_configurations(target: Path, keep: str, writer: SafeWriter) -> list[str]:
    """Drop named configurations that do not belong to this profile."""
    folder = target / "configurations"
    if not folder.is_dir():
        return []
    removed = []
    for item in sorted(folder.glob("config_*")):
        if item.name != f"config_{keep}" and writer.remove_file(item):
            removed.append(item.name[len("config_"):])
    return removed


def activate_configuration(target: Path, name: str, writer: SafeWriter) -> None:
    """Point the isolated dir at its own configuration, creating it if needed."""
    config_file = target / "configurations" / f"config_{name}"
    if not config_file.exists():
        writer.write_text(config_file, "[core]\n")
    writer.write_text(target / "active_config", name)


def seed_isolated_dir(
    target: Path, writer: SafeWriter, source: Path | None = None, keep_account: str = ""
) -> bool:
    """Create the isolated dir, seeded from the global credentials; True when created (or would be)."""
    if target.exists():
        return False
    source = source or gcloud_home()
    if writer.dry_run:
        writer.changes.append(f"[dry-run] seed {target} from {source}")
        return True
    target.mkdir(parents=True, mode=0o700, exist_ok=True)
    for name in SEED_FILES:
        origin = source / name
        if origin.exists():
            destination = target / name
            shutil.copy2(origin, destination)
            destination.chmod(0o600)
            writer.changes.append(str(destination))
    prune_credentials(target / "credentials.db", keep_account)
    return True


def apply_gcloud(profile: Profile, writer: SafeWriter) -> list[Note]:
    if not (profile.gcloud_account or profile.gcloud_project):
        return []
    return _apply_isolated(profile, writer) if profile.gcloud_isolated else _apply_named(profile, writer)


def _apply_named(profile: Profile, writer: SafeWriter) -> list[Note]:
    notes: list[Note] = []
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
        create = _run(cmds[0][0])
        if create.returncode != 0:
            notes.append(Note("error", _("[red]gcloud configurations create failed:[/red] {error}", error=create.stderr.strip())))
            return notes
    for args, cfg in cmds[1:]:
        r = _run(args, cfg)
        if r.returncode != 0:
            notes.append(Note("error", _("[red]{cmd} failed:[/red] {error}", cmd=" ".join(args), error=r.stderr.strip())))
    notes.append(Note("info", _("[green]gcloud:[/green] configuration '{name}' ready", name=name)))
    return notes


def _apply_isolated(profile: Profile, writer: SafeWriter) -> list[Note]:
    notes: list[Note] = []
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

    if seed_isolated_dir(target, writer, keep_account=profile.gcloud_account):
        notes.append(Note("info", _("[green]created:[/green] {dst}", dst=target)))
    dropped = prune_configurations(target, profile.name, writer)
    if dropped:
        notes.append(Note("info", _("[green]gcloud:[/green] dropped foreign configurations: {names}", names=", ".join(dropped))))
    activate_configuration(target, profile.name, writer)
    for args in cmds:
        r = _run(args, config_name=profile.name, config_dir=target)
        if r.returncode != 0:
            notes.append(Note("error", _("[red]{cmd} failed:[/red] {error}", cmd=" ".join(args), error=r.stderr.strip())))
    notes.append(Note("info", _("[green]gcloud:[/green] isolated config dir ready for '{name}'", name=profile.name)))
    return notes


def list_gcloud_accounts() -> list[str]:
    try:
        r = _run(["gcloud", "auth", "list", "--format=value(account)"])
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if r.returncode != 0:
        return []
    return [line.strip() for line in r.stdout.splitlines() if line.strip()]


def login_gcloud(name: str) -> tuple[str, str]:
    """Interactive `gcloud auth login` inside the named configuration: (account, error)."""
    try:
        if not configuration_exists(name):
            create = _run(["gcloud", "config", "configurations", "create", name, "--no-activate"])
            if create.returncode != 0:
                return "", _("[red]gcloud configurations create failed:[/red] {error}", error=create.stderr.strip())
        env = clean_environment(os.environ, {"CLOUDSDK_ACTIVE_CONFIG_NAME": name})
        if subprocess.run(["gcloud", "auth", "login"], env=env).returncode != 0:
            return "", _("[yellow]Login cancelled or failed; skipping gcloud.[/yellow]")
        active = _run(["gcloud", "config", "get", "account"], config_name=name)
    except FileNotFoundError:
        return "", _("[red]gcloud not found in PATH.[/red]")
    return active.stdout.strip(), ""
