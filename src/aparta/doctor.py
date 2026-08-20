"""aparta doctor: validate git, gh, gcloud and agents per profile."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .agents import get_adapters
from .i18n import _
from .discovery import find_repos
from .profiles import Profile

console = Console()


def _run(args: list[str], extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(extra_env or {})
    try:
        return subprocess.run(args, env=env, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        return subprocess.CompletedProcess(args, 127, "", _("{cmd} not found", cmd=args[0]))
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 1, "", "timeout")


def _row(table: Table, area: str, item: str, ok: bool | None, detail: str) -> bool:
    icon = {True: "[green]✔[/green]", False: "[red]✘[/red]", None: "[yellow]—[/yellow]"}[ok]
    table.add_row(area, item, icon, detail)
    return bool(ok)


def check_profile(profile: Profile) -> bool:
    table = Table(title=_("doctor: profile '{name}'", name=profile.name), show_lines=False)
    table.add_column(_("Area"), style="bold")
    table.add_column(_("Item"))
    table.add_column("OK", justify="center")
    table.add_column(_("Detail"), overflow="fold")

    all_ok = True
    repos = find_repos(profile.root_path) + [
        p for p in (Path(r).expanduser() for r in profile.adopted_repos) if p.exists()
    ]

    # git: e-mail resolved in each repo
    if not repos:
        all_ok &= _row(table, "git", str(profile.root_path), None, _("no repository found"))
    for repo in repos:
        r = _run(["git", "-C", str(repo), "config", "user.email"])
        email = r.stdout.strip()
        ok = email == profile.git_email
        all_ok &= _row(table, "git", repo.name, ok, email or _("user.email not resolved"))

    # gh: auth status under the profile's GH_CONFIG_DIR
    if profile.gh_user:
        gh_dir = profile.gh_config_dir
        if not gh_dir.exists():
            all_ok &= _row(table, "gh", str(gh_dir), False, _("config dir missing, run `aparta apply`"))
        else:
            r = _run(["gh", "auth", "status"], {"GH_CONFIG_DIR": str(gh_dir)})
            output = r.stdout + r.stderr
            ok = r.returncode == 0 and profile.gh_user in output
            detail = _("logged in as {user}", user=profile.gh_user) if ok else (output.strip().splitlines() or [_("failed")])[-1]
            all_ok &= _row(table, "gh", gh_dir.name, ok, detail)

    # gcloud: account/project of the profile's configuration
    if profile.gcloud_account or profile.gcloud_project:
        if profile.gcloud_isolated:
            env = {"CLOUDSDK_CONFIG": str(profile.gcloud_config_dir)}
            if not profile.gcloud_config_dir.exists():
                all_ok &= _row(
                    table,
                    "gcloud",
                    str(profile.gcloud_config_dir),
                    False,
                    _("config dir missing, run `aparta apply`"),
                )
        else:
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

    # aws: the named profile must exist in ~/.aws
    if profile.aws_profile:
        from .backends.aws import aws_profile_exists

        ok = aws_profile_exists(profile.aws_profile)
        detail = _("profile found in ~/.aws") if ok else _("profile missing, run `aws configure --profile {name}`", name=profile.aws_profile)
        all_ok &= _row(table, "aws", profile.aws_profile, ok, detail)

    # credentials: valid, needing a human, or simply unknown
    from .auth import OK as AUTH_OK, UNKNOWN as AUTH_UNKNOWN, checks_enabled, cached_check

    if checks_enabled():
        for status in cached_check(profile):
            if status.state == AUTH_OK:
                all_ok &= _row(table, status.provider, _("credential"), True, _("valid"))
            elif status.state == AUTH_UNKNOWN:
                # a network hiccup is not a broken credential
                _row(table, status.provider, _("credential"), None, status.detail)
            else:
                all_ok &= _row(
                    table,
                    status.provider,
                    _("credential"),
                    False,
                    _("{detail}, run `aparta login {name}`", detail=status.detail, name=profile.name),
                )

    # agents: env injected in each repo
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
