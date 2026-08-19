"""gcloud backend: named configurations selected via CLOUDSDK_ACTIVE_CONFIG_NAME."""

from __future__ import annotations

import os
import subprocess

from ..i18n import _
from . import Note

from ..fsutil import SafeWriter
from ..profiles import Profile


def _run(args: list[str], config_name: str | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if config_name:
        env["CLOUDSDK_ACTIVE_CONFIG_NAME"] = config_name
    return subprocess.run(args, env=env, capture_output=True, text=True, timeout=30)


def configuration_exists(name: str) -> bool:
    """Whether the named gcloud configuration already exists (locale-safe)."""
    r = _run(["gcloud", "config", "configurations", "describe", name])
    return r.returncode == 0


def apply_gcloud(profile: Profile, writer: SafeWriter) -> list[Note]:
    notes: list[Note] = []
    if not (profile.gcloud_account or profile.gcloud_project):
        return notes
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
