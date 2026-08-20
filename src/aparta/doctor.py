"""aparta doctor: validate git, gh, gcloud and agents per profile.

Diagnosis and repair are separate on purpose: `_diagnose` only reads and
returns the rows to render plus the issues it found, and `--fix` feeds those
issues back into the very same backends `aparta apply` uses. Anything that
needs a human at a browser (an expired or revoked credential) is never
touched, only reported with the command that solves it.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .agents import get_adapters
from .i18n import _
from .discovery import find_repos
from .profiles import Profile

console = Console()

# Issue kinds the fixer knows how to act on
GIT = "git"
GH_DIR = "gh_dir"
GCLOUD_DIR = "gcloud_dir"
GCLOUD_ACCOUNT = "gcloud_account"
GCLOUD_PROJECT = "gcloud_project"
ENV = "env"
HUMAN = "human"  # credential: only a human can fix it
AWS = "aws"  # named profile missing in ~/.aws


@dataclass
class Issue:
    kind: str
    detail: str = ""
    repo: Path | None = None


def _run(args: list[str], extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(extra_env or {})
    try:
        return subprocess.run(args, env=env, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        return subprocess.CompletedProcess(args, 127, "", _("{cmd} not found", cmd=args[0]))
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 1, "", "timeout")


def _row(rows: list[tuple[str, str, bool | None, str]], area: str, item: str, ok: bool | None, detail: str) -> bool:
    rows.append((area, item, ok, detail))
    return bool(ok)


def _diagnose(profile: Profile) -> tuple[list[tuple[str, str, bool | None, str]], bool, list[Issue]]:
    """Read-only inspection: (table rows, everything ok, issues found)."""
    rows: list[tuple[str, str, bool | None, str]] = []
    issues: list[Issue] = []
    all_ok = True
    repos = find_repos(profile.root_path) + [
        p for p in (Path(r).expanduser() for r in profile.adopted_repos) if p.exists()
    ]

    # git: e-mail resolved in each repo
    if not repos:
        all_ok &= _row(rows, "git", str(profile.root_path), None, _("no repository found"))
    for repo in repos:
        r = _run(["git", "-C", str(repo), "config", "user.email"])
        email = r.stdout.strip()
        ok = email == profile.git_email
        all_ok &= _row(rows, "git", repo.name, ok, email or _("user.email not resolved"))
        if not ok:
            issues.append(Issue(GIT, repo.name, repo))

    # gh: auth status under the profile's GH_CONFIG_DIR
    if profile.gh_user:
        gh_dir = profile.gh_config_dir
        if not gh_dir.exists():
            all_ok &= _row(rows, "gh", str(gh_dir), False, _("config dir missing, run `aparta apply`"))
            issues.append(Issue(GH_DIR, str(gh_dir)))
        else:
            r = _run(["gh", "auth", "status"], {"GH_CONFIG_DIR": str(gh_dir)})
            output = r.stdout + r.stderr
            ok = r.returncode == 0 and profile.gh_user in output
            detail = _("logged in as {user}", user=profile.gh_user) if ok else (output.strip().splitlines() or [_("failed")])[-1]
            all_ok &= _row(rows, "gh", gh_dir.name, ok, detail)

    # gcloud: account/project of the profile's configuration
    if profile.gcloud_account or profile.gcloud_project:
        # probe with exactly what the agents get, so doctor cannot pass while
        # a stray variable in this shell makes the real thing pick another one
        env = {k: v for k, v in profile.env().items() if k.startswith(("CLOUDSDK_", "GOOGLE_"))}
        if profile.gcloud_isolated:
            if not profile.gcloud_config_dir.exists():
                all_ok &= _row(
                    rows,
                    "gcloud",
                    str(profile.gcloud_config_dir),
                    False,
                    _("config dir missing, run `aparta apply`"),
                )
                issues.append(Issue(GCLOUD_DIR, str(profile.gcloud_config_dir)))
        if profile.gcloud_account:
            r = _run(["gcloud", "config", "get", "account"], env)
            account = r.stdout.strip()
            ok = account == profile.gcloud_account
            all_ok &= _row(rows, "gcloud", "account", ok, account or r.stderr.strip())
            if not ok:
                issues.append(Issue(GCLOUD_ACCOUNT, account))
        if profile.gcloud_project:
            r = _run(["gcloud", "config", "get", "project"], env)
            project = r.stdout.strip()
            ok = project == profile.gcloud_project
            all_ok &= _row(rows, "gcloud", "project", ok, project or r.stderr.strip())
            if not ok:
                issues.append(Issue(GCLOUD_PROJECT, project))

    if profile.gcloud_isolated and profile.gcloud_config_dir.exists():
        from .backends.gcloud import has_adc

        # not an error: no ADC is safer than the wrong ADC
        if not has_adc(profile.gcloud_config_dir):
            _row(
                rows,
                "gcloud",
                "ADC",
                None,
                _("none yet; SDKs need `gcloud auth application-default login`"),
            )

    # aws: the named profile must exist in ~/.aws
    if profile.aws_profile:
        from .backends.aws import aws_profile_exists

        ok = aws_profile_exists(profile.aws_profile)
        detail = _("profile found in ~/.aws") if ok else _("profile missing, run `aws configure --profile {name}`", name=profile.aws_profile)
        all_ok &= _row(rows, "aws", profile.aws_profile, ok, detail)
        if not ok:
            issues.append(Issue(AWS, profile.aws_profile))

    # credentials: valid, needing a human, or simply unknown
    from .auth import OK as AUTH_OK, UNKNOWN as AUTH_UNKNOWN, checks_enabled, cached_check

    if checks_enabled():
        for status in cached_check(profile):
            if status.state == AUTH_OK:
                all_ok &= _row(rows, status.provider, _("credential"), True, _("valid"))
            elif status.state == AUTH_UNKNOWN:
                # a network hiccup is not a broken credential
                _row(rows, status.provider, _("credential"), None, status.detail)
            else:
                all_ok &= _row(
                    rows,
                    status.provider,
                    _("credential"),
                    False,
                    _("{detail}, run `aparta login {name}`", detail=status.detail, name=profile.name),
                )
                issues.append(Issue(HUMAN, status.provider))

    # agents: env injected in each repo
    expected_env = profile.env()
    if expected_env:
        for adapter in get_adapters(profile.agents):
            for repo in repos:
                if not adapter.detect(repo):
                    continue
                ok, msg = adapter.validate(repo, expected_env)
                all_ok &= _row(rows, adapter.name, repo.name, ok, msg)
                if not ok:
                    issues.append(Issue(ENV, f"{adapter.name}: {repo.name}", repo))

    return rows, bool(all_ok), issues


def _render(profile: Profile, rows: list[tuple[str, str, bool | None, str]]) -> None:
    table = Table(title=_("doctor: profile '{name}'", name=profile.name), show_lines=False)
    table.add_column(_("Area"), style="bold")
    table.add_column(_("Item"))
    table.add_column("OK", justify="center")
    table.add_column(_("Detail"), overflow="fold")
    for area, item, ok, detail in rows:
        icon = {True: "[green]✔[/green]", False: "[red]✘[/red]", None: "[yellow]—[/yellow]"}[ok]
        table.add_row(area, item, icon, detail)
    console.print(table)


def check_profile(profile: Profile, fix: bool = False, dry_run: bool = False, verbose: bool = False) -> bool:
    """Print the diagnosis table; with `fix`, repair what is safe to repair."""
    rows, all_ok, issues = _diagnose(profile)
    _render(profile, rows)
    if not fix:
        return all_ok
    return fix_profile(profile, issues, dry_run=dry_run, verbose=verbose, was_ok=all_ok)


def fix_profile(
    profile: Profile,
    issues: list[Issue],
    dry_run: bool = False,
    verbose: bool = False,
    was_ok: bool = False,
) -> bool:
    """Repair the deterministic issues; return whether the profile ends healthy.

    Credentials are deliberately out of scope: reauthentication needs a human,
    so those issues are only reported with the command that solves them.
    """
    from .fsutil import SafeWriter

    kinds = {issue.kind for issue in issues}
    fixable = kinds - {HUMAN, AWS}
    manual = [issue for issue in issues if issue.kind in (HUMAN, AWS)]

    if not fixable:
        if not manual:
            console.print(_("[green]doctor --fix: nothing to repair.[/green]"))
            return was_ok
        _report_manual(profile, manual)
        return was_ok

    writer = SafeWriter(dry_run=dry_run, verbose=verbose)
    console.print(_("[bold]doctor --fix: repairing profile '{name}'[/bold]", name=profile.name))
    done: list[str] = []

    if GIT in kinds:
        from .backends.git import apply_git

        _print_notes(apply_git(profile, writer), verbose)
        done.append(_("git: includeIf and ~/.gitconfig-{name} reapplied", name=profile.name))

    if GH_DIR in kinds:
        from .backends.gh import apply_gh

        _print_notes(apply_gh(profile, writer), verbose)
        done.append(_("gh: config dir reapplied"))

    if kinds & {GCLOUD_DIR, GCLOUD_ACCOUNT, GCLOUD_PROJECT}:
        from .backends.gcloud import apply_gcloud

        _print_notes(apply_gcloud(profile, writer), verbose)
        done.append(_("gcloud: account and project reasserted"))

    env_repos = sorted({issue.repo for issue in issues if issue.kind == ENV and issue.repo})
    if env_repos:
        touched = _reinject_env(profile, env_repos, writer)
        done.append(_("agents: env reinjected into {n} config file(s)", n=touched))

    for line in done:
        console.print(_("  [green]fixed[/green] {what}", what=line))

    if dry_run:
        console.print(_("[yellow]--dry-run: nothing was changed; run without --dry-run to repair.[/yellow]"))
        if manual:
            _report_manual(profile, manual)
        return was_ok

    # the verdict has to come from the real state, not from what we intended
    _rows, all_ok, remaining = _diagnose(profile)
    manual = [issue for issue in remaining if issue.kind in (HUMAN, AWS)]
    still_broken = [issue for issue in remaining if issue.kind not in (HUMAN, AWS)]
    if manual:
        _report_manual(profile, manual)
    if still_broken:
        console.print(
            _(
                "[yellow]Still failing after the fix: {items}. Run `aparta doctor {name}` for the detail.[/yellow]",
                items=", ".join(sorted({i.kind for i in still_broken})),
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


def _reinject_env(profile: Profile, repos: list[Path], writer) -> int:
    """Re-inject the profile env into the given repos, as `apply` does."""
    env = profile.env()
    before = len(writer.changes)
    for repo in repos:
        for adapter in get_adapters(profile.agents):
            if not adapter.detect(repo):
                continue
            try:
                adapter.inject(repo, env, writer)
                adapter.install_check(repo, writer)
            except ValueError as exc:
                # one broken config file must not stop the repair
                console.print(
                    _("[yellow]warning:[/yellow] {adapter} in {repo}: {error}; skipping.", adapter=adapter.name, repo=repo.name, error=exc)
                )
    # env and the startup hook usually share a file: count files, not writes
    return len(set(writer.changes[before:]))


def _report_manual(profile: Profile, manual: list[Issue]) -> None:
    """Print what aparta will not do on the user's behalf."""
    console.print(_("[bold]Still needs you:[/bold]"))
    for issue in manual:
        if issue.kind == HUMAN:
            console.print(
                _(
                    "  [yellow]{provider}[/yellow] credential: run `aparta login {name}` (aparta never reauthenticates for you)",
                    provider=issue.detail,
                    name=profile.name,
                )
            )
        else:
            console.print(
                _("  [yellow]aws[/yellow]: run `aws configure --profile {name}`", name=issue.detail)
            )
