"""aparta doctor: valida git, gh, gcloud e agentes por perfil, em tabela rich."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .agents import get_adapters
from .discovery import find_repos  # noqa: F401 — reexportado (cli importa daqui)
from .profiles import Profile

console = Console()


def _run(args: list[str], extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(extra_env or {})
    try:
        return subprocess.run(args, env=env, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        return subprocess.CompletedProcess(args, 127, "", f"{args[0]} não encontrado")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 1, "", "timeout")


def _row(table: Table, area: str, item: str, ok: bool | None, detail: str) -> bool:
    icon = {True: "[green]✔[/green]", False: "[red]✘[/red]", None: "[yellow]—[/yellow]"}[ok]
    table.add_row(area, item, icon, detail)
    return bool(ok)


def check_profile(profile: Profile) -> bool:
    table = Table(title=f"doctor — perfil '{profile.name}'", show_lines=False)
    table.add_column("Área", style="bold")
    table.add_column("Item")
    table.add_column("OK", justify="center")
    table.add_column("Detalhe", overflow="fold")

    all_ok = True
    repos = find_repos(profile.root_path)

    # git: e-mail resolvido em cada repo
    if not repos:
        all_ok &= _row(table, "git", str(profile.root_path), None, "nenhum repositório encontrado")
    for repo in repos:
        r = _run(["git", "-C", str(repo), "config", "user.email"])
        email = r.stdout.strip()
        ok = email == profile.git_email
        all_ok &= _row(table, "git", repo.name, ok, email or "user.email não resolvido")

    # gh: auth status com o GH_CONFIG_DIR do perfil
    if profile.gh_user:
        gh_dir = profile.gh_config_dir
        if not gh_dir.exists():
            all_ok &= _row(table, "gh", str(gh_dir), False, "config dir ausente — rode `aparta apply`")
        else:
            r = _run(["gh", "auth", "status"], {"GH_CONFIG_DIR": str(gh_dir)})
            output = r.stdout + r.stderr
            ok = r.returncode == 0 and profile.gh_user in output
            detail = f"logado como {profile.gh_user}" if ok else (output.strip().splitlines() or ["falhou"])[-1]
            all_ok &= _row(table, "gh", gh_dir.name, ok, detail)

    # gcloud: conta/projeto da configuração do perfil
    if profile.gcloud_account or profile.gcloud_project:
        env = {"CLOUDSDK_ACTIVE_CONFIG_NAME": profile.name}
        if profile.gcloud_account:
            r = _run(["gcloud", "config", "get", "account"], env)
            account = r.stdout.strip()
            ok = account == profile.gcloud_account
            all_ok &= _row(table, "gcloud", "account", ok, account or r.stderr.strip())
        if profile.gcloud_project:
            r = _run(["gcloud", "config", "get", "project"], env)
            project = r.stdout.strip()
            ok = project == profile.gcloud_project
            all_ok &= _row(table, "gcloud", "project", ok, project or r.stderr.strip())

    # agentes: env injetado em cada repo
    expected_env = profile.env()
    if expected_env:
        for adapter in get_adapters(profile.agents):
            for repo in repos:
                if not adapter.detect(repo):
                    continue
                ok, msg = adapter.validate(repo, expected_env)
                all_ok &= _row(table, adapter.name, repo.name, ok, msg)

    console.print(table)
    return bool(all_ok)
