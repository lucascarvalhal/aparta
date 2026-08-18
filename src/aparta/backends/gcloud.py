"""Backend gcloud: configurations nomeadas selecionadas por CLOUDSDK_ACTIVE_CONFIG_NAME."""

from __future__ import annotations

import os
import subprocess

from rich.console import Console

from ..fsutil import SafeWriter
from ..profiles import Profile

console = Console()


def _run(args: list[str], config_name: str | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if config_name:
        env["CLOUDSDK_ACTIVE_CONFIG_NAME"] = config_name
    return subprocess.run(args, env=env, capture_output=True, text=True)


def apply_gcloud(profile: Profile, writer: SafeWriter) -> None:
    if not (profile.gcloud_account or profile.gcloud_project):
        return
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
            console.print(f"[yellow]--dry-run[/yellow] {prefix}{' '.join(args)}")
        return

    create = _run(*cmds[0])
    if create.returncode != 0 and "already exists" not in create.stderr:
        console.print(f"[red]gcloud configurations create falhou:[/red] {create.stderr.strip()}")
        return
    for args, cfg in cmds[1:]:
        r = _run(args, cfg)
        if r.returncode != 0:
            console.print(f"[red]{' '.join(args)} falhou:[/red] {r.stderr.strip()}")
    console.print(f"[green]gcloud:[/green] configuração '{name}' pronta")
