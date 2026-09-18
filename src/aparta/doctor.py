"""aparta doctor: validate git, gh, gcloud, aws, credentials and agents per profile."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import NamedTuple

from rich.console import Console
from rich.table import Table

from .agents import get_adapters
from . import auth
from .backends.aws import aws_profile_exists
from .backends.gcloud import apply_gcloud, has_adc
from .backends.gh import apply_gh
from .backends.git import reconcile_workspace_git
from .fsutil import SafeWriter
from .i18n import _
from .profiles import MANAGED_ENV_KEYS, Profile, clean_environment, load_profiles
from .providers import workspace_env
from .workspaces import implicit_workspace, load_workspaces, profile_repos, workspace_for_path

console = Console()


class IssueKind(str, Enum):
    GIT = "git"
    GH_DIR = "gh_dir"
    GCLOUD_DIR = "gcloud_dir"
    GCLOUD_ACCOUNT = "gcloud_account"
    GCLOUD_PROJECT = "gcloud_project"
    ENV = "env"
    HUMAN = "human"
    AWS = "aws"

    @property
    def manual(self) -> bool:
        """Whether only the user can resolve it."""
        return self in (IssueKind.HUMAN, IssueKind.AWS)


@dataclass
class Issue:
    kind: IssueKind
    detail: str = ""
    repo: Path | None = None


class Row(NamedTuple):
    area: str
    item: str
    ok: bool | None
    detail: str


Findings = tuple[list[Row], list[Issue]]


def _run(args: list[str], extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = clean_environment(os.environ, extra_env or {})
    try:
        return subprocess.run(args, env=env, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        return subprocess.CompletedProcess(args, 127, "", _("{cmd} not found", cmd=args[0]))
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 1, "", "timeout")


def _check_git(profile: Profile, repos: list[Path]) -> Findings:
    rows: list[Row] = []
    issues: list[Issue] = []
    if not repos:
        rows.append(Row("git", str(profile.root_path), False, _("no repository found")))
    for repo in repos:
        email = _run(["git", "-C", str(repo), "config", "user.email"]).stdout.strip()
        ok = email == profile.git_email
        rows.append(Row("git", repo.name, ok, email or _("user.email not resolved")))
        if not ok:
            issues.append(Issue(IssueKind.GIT, repo.name, repo))
    return rows, issues


def _check_gh(profile: Profile) -> Findings:
    if not profile.gh_user:
        return [], []
    gh_dir = profile.gh_config_dir
    if not gh_dir.exists():
        row = Row("gh", str(gh_dir), False, _("config dir missing, run `aparta apply`"))
        return [row], [Issue(IssueKind.GH_DIR, str(gh_dir))]
    r = _run(["gh", "auth", "status"], {"GH_CONFIG_DIR": str(gh_dir)})
    output = r.stdout + r.stderr
    ok = r.returncode == 0 and profile.gh_user in output
    detail = _("logged in as {user}", user=profile.gh_user) if ok else (output.strip().splitlines() or [_("failed")])[-1]
    return [Row("gh", gh_dir.name, ok, detail)], []


def _check_gcloud(profile: Profile) -> Findings:
    rows: list[Row] = []
    issues: list[Issue] = []
    if not (profile.gcloud_account or profile.gcloud_project):
        return rows, issues
    env = profile.gcloud_env()
    if profile.gcloud_isolated and not profile.gcloud_config_dir.exists():
        rows.append(Row("gcloud", str(profile.gcloud_config_dir), False, _("config dir missing, run `aparta apply`")))
        issues.append(Issue(IssueKind.GCLOUD_DIR, str(profile.gcloud_config_dir)))
    for key, expected, kind in (
        ("account", profile.gcloud_account, IssueKind.GCLOUD_ACCOUNT),
        ("project", profile.gcloud_project, IssueKind.GCLOUD_PROJECT),
    ):
        if not expected:
            continue
        r = _run(["gcloud", "config", "get", key], env)
        value = r.stdout.strip()
        ok = value == expected
        rows.append(Row("gcloud", key, ok, value or r.stderr.strip()))
        if not ok:
            issues.append(Issue(kind, value))
    if profile.gcloud_isolated and profile.gcloud_config_dir.exists() and not has_adc(profile.gcloud_config_dir):
        rows.append(
            Row("gcloud", "ADC", None, _("none yet; `aparta login {name}` offers to create them", name=profile.name))
        )
    return rows, issues


def _check_aws(profile: Profile) -> Findings:
    if not profile.aws_profile:
        return [], []
    ok = aws_profile_exists(profile.aws_profile)
    detail = (
        _("profile found in ~/.aws")
        if ok
        else _("profile missing, run `aws configure --profile {name}`", name=profile.aws_profile)
    )
    issues = [] if ok else [Issue(IssueKind.AWS, profile.aws_profile)]
    return [Row("aws", profile.aws_profile, ok, detail)], issues


def _check_credentials(profile: Profile) -> Findings:
    rows: list[Row] = []
    issues: list[Issue] = []
    if not auth.checks_enabled():
        return rows, issues
    for status in auth.cached_check(profile):
        if status.state == auth.OK:
            rows.append(Row(status.label, _("credential"), True, _("valid")))
        elif status.state == auth.UNKNOWN:
            rows.append(Row(status.label, _("credential"), None, status.detail))
        else:
            detail = _("{detail}, run `aparta login {name}`", detail=status.detail, name=profile.name)
            rows.append(Row(status.label, _("credential"), False, detail))
            issues.append(Issue(IssueKind.HUMAN, status.label))
    return rows, issues


def _check_agents(profile: Profile, repos: list[Path], profiles: dict[str, Profile]) -> Findings:
    rows: list[Row] = []
    issues: list[Issue] = []
    saved_workspaces = load_workspaces()
    for adapter in get_adapters(profile.agents):
        for repo in repos:
            workspace = workspace_for_path(repo, profiles, saved_workspaces) or implicit_workspace(repo.resolve(), profile)
            expected_env = workspace_env(workspace, profile) if workspace.profile == profile.name else profile.env()
            current = adapter.read_env(repo)
            unexpected = [key for key in MANAGED_ENV_KEYS if key not in expected_env and key in current]
            if not expected_env and not unexpected:
                continue
            if unexpected:
                ok, msg = False, _("env mismatch: {keys}", keys=", ".join(unexpected))
            else:
                ok, msg = adapter.validate(repo, expected_env)
            rows.append(Row(adapter.name, repo.name, ok, msg))
            if not ok:
                issues.append(Issue(IssueKind.ENV, f"{adapter.name}: {repo.name}", repo))
    return rows, issues


def _diagnose(profile: Profile) -> tuple[list[Row], bool, list[Issue]]:
    """Read-only inspection: (table rows, everything ok, issues found)."""
    profiles = load_profiles()
    profiles.setdefault(profile.name, profile)
    repos = profile_repos(profile, profiles)
    rows: list[Row] = []
    issues: list[Issue] = []
    for found_rows, found_issues in (
        _check_git(profile, repos),
        _check_gh(profile),
        _check_gcloud(profile),
        _check_aws(profile),
        _check_credentials(profile),
        _check_agents(profile, repos, profiles),
    ):
        rows += found_rows
        issues += found_issues
    return rows, all(row.ok is not False for row in rows), issues


def _render(profile: Profile, rows: list[Row]) -> None:
    table = Table(title=_("doctor: profile '{name}'", name=profile.name), show_lines=False)
    table.add_column(_("Area"), style="bold")
    table.add_column(_("Item"))
    table.add_column("OK", justify="center")
    table.add_column(_("Detail"), overflow="fold")
    icons = {True: "[green]✔[/green]", False: "[red]✘[/red]", None: "[yellow]—[/yellow]"}
    for row in rows:
        table.add_row(row.area, row.item, icons[row.ok], row.detail)
    console.print(table)


def check_profile(profile: Profile, fix: bool = False, dry_run: bool = False, verbose: bool = False) -> bool:
    """Print the diagnosis table; with `fix`, repair what is safe to repair."""
    rows, all_ok, issues = _diagnose(profile)
    _render(profile, rows)
    if not fix:
        return all_ok
    fixed = fix_profile(profile, issues, SafeWriter(dry_run=dry_run, verbose=verbose))
    return all_ok if fixed is None else fixed


def fix_profile(profile: Profile, issues: list[Issue], writer: SafeWriter) -> bool | None:
    """Repair the deterministic issues; None when nothing was attempted, else whether it ends healthy."""
    kinds = {issue.kind for issue in issues}
    manual = [issue for issue in issues if issue.kind.manual]
    fixable = {kind for kind in kinds if not kind.manual}
    if not fixable:
        if manual:
            _report_manual(profile, manual)
        else:
            console.print(_("[green]doctor --fix: nothing to repair.[/green]"))
        return None

    console.print(_("[bold]doctor --fix: repairing profile '{name}'[/bold]", name=profile.name))
    done: list[str] = []
    if IssueKind.GIT in kinds:
        profiles = load_profiles()
        profiles.setdefault(profile.name, profile)
        reconcile_workspace_git(profiles, load_workspaces(), writer)
        done.append(_("git: workspace identities reapplied"))
    if IssueKind.GH_DIR in kinds:
        _print_notes(apply_gh(profile, writer), writer.verbose)
        done.append(_("gh: config dir reapplied"))
    if kinds & {IssueKind.GCLOUD_DIR, IssueKind.GCLOUD_ACCOUNT, IssueKind.GCLOUD_PROJECT}:
        _print_notes(apply_gcloud(profile, writer), writer.verbose)
        done.append(_("gcloud: account and project reasserted"))
    env_repos = sorted({issue.repo for issue in issues if issue.kind == IssueKind.ENV and issue.repo})
    if env_repos:
        touched = _reinject_env(profile, env_repos, writer)
        done.append(_("agents: env reinjected into {n} config file(s)", n=touched))
    for line in done:
        console.print(f"  [green]OK[/green] {line}")
    if writer.dry_run:
        console.print(_("[yellow]--dry-run: nothing was changed; run without --dry-run to repair.[/yellow]"))
        return None

    _rows, all_ok, remaining = _diagnose(profile)
    manual = [issue for issue in remaining if issue.kind.manual]
    still_broken = sorted({issue.kind.value for issue in remaining if not issue.kind.manual})
    if manual:
        _report_manual(profile, manual)
    if still_broken:
        console.print(
            _(
                "[yellow]Still failing after the fix: {items}. Run `aparta doctor {name}` for the detail.[/yellow]",
                items=", ".join(still_broken),
                name=profile.name,
            )
        )
    if all_ok:
        console.print(_("[green]doctor --fix: profile '{name}' is healthy now.[/green]", name=profile.name))
    return all_ok


def _print_notes(notes, verbose: bool) -> None:
    for note in notes:
        if note.level != "info" or verbose:
            console.print(note.text)


def _reinject_env(profile: Profile, repos: list[Path], writer: SafeWriter) -> int:
    """Re-inject each exact workspace env into the given repos, as apply does."""
    from .apply import apply_workspace_agents

    saved_workspaces = load_workspaces()
    profiles = load_profiles()
    profiles.setdefault(profile.name, profile)
    before = len(writer.changes)
    for repo in repos:
        workspace = workspace_for_path(repo, profiles, saved_workspaces) or implicit_workspace(repo.resolve(), profile)
        if workspace.profile == profile.name:
            apply_workspace_agents(profile, workspace, writer)
    return len(set(writer.changes[before:]))


def _report_manual(profile: Profile, manual: list[Issue]) -> None:
    """Print what aparta will not do on the user's behalf."""
    console.print(_("[bold]Still needs you:[/bold]"))
    for issue in manual:
        if issue.kind == IssueKind.HUMAN:
            console.print(
                _(
                    "  [yellow]{provider}[/yellow] credential: run `aparta login {name}` (aparta never reauthenticates for you)",
                    provider=issue.detail,
                    name=profile.name,
                )
            )
        else:
            console.print(_("  [yellow]aws[/yellow]: run `aws configure --profile {name}`", name=issue.detail))
