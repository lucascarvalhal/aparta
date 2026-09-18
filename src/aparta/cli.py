"""aparta CLI: no args opens the wizard or menu; subcommands do the rest."""

from __future__ import annotations

import inspect
import json
import math
import os
import re
import subprocess
import time
from pathlib import Path
from typing import NoReturn

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table
from typer.models import ArgumentInfo

from . import __version__
from .apply import apply_profile
from .doctor import check_profile
from .fsutil import SafeWriter
from .i18n import _
from .profiles import load_profiles, profiles_path
from .providers import ProviderError, canonical_provider, canonical_providers, validate_provider, workspace_env
from .workspaces import (
    WorkspaceResolutionError,
    enable_provider,
    load_workspaces,
    profile_for_path,
    resolve_target,
    save_workspaces,
    workspace_for_path,
)

QUIET_COMMANDS = frozenset({"update", "login", "check", "run", "env", "status", "hook"})

app = typer.Typer(
    name="aparta",
    help=_(
        "Isolates development accounts (git, gh, gcloud) per project folder "
        "and injects environment variables into terminal AI agents."
    ),
)
console = Console()


err = Console(stderr=True)


def _fail(message: str, code: int = 1) -> NoReturn:
    """Print an already formatted error to stderr and exit."""
    err.print(message)
    raise typer.Exit(code)


def _writer(ctx: typer.Context) -> SafeWriter:
    options = ctx.obj or {}
    return SafeWriter(dry_run=options.get("dry_run", False), verbose=options.get("verbose", False))


def _profile_or_fail(profiles: dict, name: str):
    profile = profiles.get(name)
    if profile is None:
        _fail(_("[red]Profile '{name}' not found.[/red]", name=name))
    return profile


def default_action(profiles_file: Path | None = None) -> str:
    """No-args routing: 'wizard' on first run, 'menu' afterwards."""
    profiles_file = profiles_file or profiles_path()
    return "menu" if profiles_file.exists() else "wizard"


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    dry_run: bool = typer.Option(
        False, "--dry-run", help=_("Show the diff of what would change, without applying anything.")
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help=_("Show every file, backup and diff instead of the compact summary.")
    ),
    version: bool = typer.Option(False, "--version", help=_("Show the version and exit.")),
) -> None:
    if version:
        console.print(f"aparta {__version__}")
        raise typer.Exit()
    ctx.obj = {"dry_run": dry_run, "verbose": verbose}
    if ctx.invoked_subcommand not in QUIET_COMMANDS:
        from .updates import notify_or_autoupdate

        notify_or_autoupdate()
        _warn_about_credentials()
        _warn_about_stale_profiles()
    if ctx.invoked_subcommand is None:
        if default_action() == "wizard":
            _run_wizard(dry_run, verbose)
        else:
            _run_menu(dry_run, verbose)


def _warn_about_stale_profiles() -> None:
    """A new release can bring behaviour that only lands on the next apply."""
    from .apply import stale_profiles

    try:
        names = stale_profiles()
        if names:
            console.print(
                _(
                    "[yellow]These profiles were set up by an older aparta and may miss new behaviour: {names}. Run [bold]aparta apply <profile>[/bold] to bring them up to date.[/yellow]",
                    names=", ".join(names),
                )
            )
    except (OSError, ValueError):
        pass


def _warn_about_credentials() -> None:
    """Expired credentials of the profile owning this folder, or of every profile outside one."""
    from .auth import problems

    try:
        profiles = load_profiles()
        current = profile_for_path(Path.cwd(), profiles)
        scope = [current] if current is not None else list(profiles.values())
        for name, status in problems(scope):
            console.print(
                _(
                    "[yellow]{provider} of profile '{name}': {detail}. Run [bold]aparta login {name}[/bold].[/yellow]",
                    provider=status.label,
                    name=name,
                    detail=status.detail,
                )
            )
    except (OSError, ValueError, subprocess.SubprocessError):
        pass


def _run_wizard(dry_run: bool, verbose: bool = False) -> None:
    from .wizard import run_wizard

    try:
        run_wizard(dry_run=dry_run, verbose=verbose)
    except KeyboardInterrupt:
        console.print("\n" + _("[yellow]Cancelled.[/yellow]"))
        raise typer.Exit(1)


def _run_menu(dry_run: bool, verbose: bool = False) -> None:
    import questionary

    while True:
        choice = questionary.select(
            _("aparta: what do you want to do?"),
            choices=[
                questionary.Choice(_("New profile (wizard)"), value="init"),
                questionary.Choice(_("Apply a profile (apply)"), value="apply"),
                questionary.Choice(_("Check everything (doctor)"), value="doctor"),
                questionary.Choice(_("List profiles (list)"), value="list"),
                questionary.Choice(_("Quit"), value="quit"),
            ],
            qmark="",
        ).ask()
        if choice in (None, "quit"):
            return
        if choice == "init":
            _run_wizard(dry_run, verbose)
        elif choice == "apply":
            profiles = load_profiles()
            if not profiles:
                console.print(_("[yellow]No profile configured yet.[/yellow]"))
                continue
            name = questionary.select(_("Which profile?"), choices=list(profiles), qmark="").ask()
            if name:
                apply_profile(profiles[name], SafeWriter(dry_run=dry_run, verbose=verbose))
        elif choice == "doctor":
            for p in load_profiles().values():
                check_profile(p, verbose=verbose)
        elif choice == "list":
            _print_profiles()


@app.command(help=_("Guided wizard: pick agents, detect or create profiles, apply."))
def init(ctx: typer.Context) -> None:
    _run_wizard(ctx.obj["dry_run"], ctx.obj["verbose"])


@app.command(help=_("Re-apply a profile: gitconfigs, gh, gcloud and agent env in the repos."))
def apply(
    ctx: typer.Context,
    profile_name: str = typer.Argument(..., metavar="profile", help=_("Name of the profile to apply.")),
) -> None:
    """Apply a profile: gitconfigs, gh config dir, gcloud config and repo env."""
    profile = _profile_or_fail(load_profiles(), profile_name)
    apply_profile(profile, _writer(ctx))


@app.command(help=_("Check the real state: e-mail per repo, gh auth, gcloud config, agent env."))
def doctor(
    ctx: typer.Context,
    profile_name: str = typer.Argument(None, metavar="profile", help=_("Profile to check (empty = all).")),
    fix: bool = typer.Option(
        False,
        "--fix",
        "-f",
        help=_("Repair what is deterministic and safe; credentials still need `aparta login`."),
    ),
) -> None:
    """Check the real state: git user.email per repo, gh auth status, gcloud config."""
    profiles = load_profiles()
    if not profiles:
        console.print(_("[yellow]No profile configured. Run `aparta init`.[/yellow]"))
        raise typer.Exit(1)
    selected = [_profile_or_fail(profiles, profile_name)] if profile_name else list(profiles.values())
    options = ctx.obj or {}
    ok = all(
        [
            check_profile(p, fix=fix, dry_run=options.get("dry_run", False), verbose=options.get("verbose", False))
            for p in selected
        ]
    )
    raise typer.Exit(0 if ok else 1)


def _print_profiles() -> None:
    profiles = load_profiles()
    if not profiles:
        console.print(_("[yellow]No profile configured. Run `aparta init`.[/yellow]"))
        return
    table = Table(title=_("Profiles ({path})", path=profiles_path()))
    table.add_column(_("Name"), style="bold")
    table.add_column(_("Root"))
    table.add_column(_("Git e-mail"))
    table.add_column("gh")
    table.add_column("gcloud")
    table.add_column(_("Agents"))
    for p in profiles.values():
        gcloud = p.gcloud_account + (f" / {p.gcloud_project}" if p.gcloud_project else "")
        table.add_row(p.name, p.root, p.git_email, p.gh_user or "—", gcloud or "—", ", ".join(p.agents) or "—")
    console.print(table)


@app.command("list", help=_("List configured profiles."))
def list_profiles() -> None:
    _print_profiles()


@app.command(help=_("Read-only: find git repos and suggest profile groups (default: your home)."))
def scan(
    paths: list[str] = typer.Argument(None, metavar="folders", help=_("Folders to scan (empty = your whole home).")),
) -> None:
    """Scan the disk and suggest project groups (read-only, nothing changes)."""
    from .discovery import discover

    where = ", ".join(paths) if paths else _("your home")
    console.print(_("[dim]Scanning {where} and ~/.gitconfig (read-only)...[/dim]", where=where))
    suggestions = discover(scan_roots=paths or None)
    if not suggestions:
        console.print(_("[yellow]No git repository found.[/yellow]"))
        return
    table = Table(title=_("Detected project groups"))
    table.add_column(_("Suggested name"), style="bold")
    table.add_column(_("Folder"))
    table.add_column(_("Repos"), justify="right")
    table.add_column(_("Git e-mail"))
    table.add_column("gh / gcloud")
    table.add_column(_("Source"))
    for s in suggestions:
        accounts = " / ".join(x for x in (s.gh_config, s.gcloud_config) if x) or "—"
        source = "~/.gitconfig" if s.source == "gitconfig" else _("scan")
        table.add_row(s.name, s.root, str(s.repo_count), s.git_email or "—", accounts, source)
    console.print(table)
    console.print(_("Use [bold]aparta init[/bold] to turn them into profiles."))


@app.command(help=_("Remove a profile and undo what it applied (backups kept)."))
def remove(
    ctx: typer.Context,
    profile_name: str = typer.Argument(..., metavar="profile", help=_("Name of the profile to remove.")),
    yes: bool = typer.Option(False, "--yes", "-y", help=_("Do not ask for confirmation.")),
) -> None:
    """Remove a profile and undo the configuration it applied."""
    from .profiles import save_profiles
    from .remove import remove_profile

    profiles = load_profiles()
    profile = _profile_or_fail(profiles, profile_name)
    if not yes:
        from . import prompts

        confirmed = prompts.confirm(
            _("Remove '{name}' and undo its gitconfig, gh, gcloud and agent env?", name=profile_name)
        )
        if not confirmed:
            console.print(_("[yellow]Cancelled.[/yellow]"))
            raise typer.Exit(0)
    writer = _writer(ctx)
    remove_profile(profile, writer)
    if not writer.dry_run:
        del profiles[profile_name]
        save_profiles(profiles, writer)


@app.command(help=_("Show what runs outside any profile; --secure makes it neutral, --restore undoes it."))
def fallback(
    ctx: typer.Context,
    secure: bool = typer.Option(
        False, "--secure", help=_("Make the global default neutral, so commands outside a profile fail instead of using someone's account.")
    ),
    restore: bool = typer.Option(
        False, "--restore", help=_("Put the configuration that was global before --secure back.")
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help=_("Do not ask for confirmation.")),
) -> None:
    """Show, neutralize or restore what runs outside any profile."""
    from . import fallback as fallback_mod

    if secure and restore:
        _fail(_("[red]Use --secure or --restore, not both.[/red]"))
    writer = _writer(ctx)
    if secure:
        if not fallback_mod.make_secure(writer, assume_yes=yes):
            raise typer.Exit(1)
    elif restore:
        if not fallback_mod.restore(writer):
            raise typer.Exit(1)
    else:
        fallback_mod.show_state()


@app.command(help=_("Update aparta to the latest release."))
def update() -> None:
    from .updates import check_for_update, run_update

    latest = check_for_update(force=True)
    if not latest:
        console.print(_("[green]You are already on the latest version ({current}).[/green]", current=__version__))
        return
    console.print(_("Updating {current} -> {latest}...", current=__version__, latest=latest))
    if not run_update(latest):
        raise typer.Exit(1)


@app.command(help=_("Enable a provider in the current or named workspace."))
def add(
    ctx: typer.Context,
    values: list[str] = typer.Argument(..., metavar="[workspace] <provider>", help=_("[workspace] provider to enable.")),
) -> None:
    """Enable a provider in the current or explicitly named workspace."""
    if len(values) == 1:
        selector, raw_provider = "", values[0]
    elif len(values) == 2:
        selector, raw_provider = values
    else:
        _fail(_("[red]Usage: aparta add [workspace] <provider>[/red]"), code=2)

    profiles = load_profiles()
    workspaces = load_workspaces()
    try:
        profile, workspace = resolve_target(selector, Path.cwd(), profiles, workspaces)
        if workspace is None:
            raise WorkspaceResolutionError(f"'{selector}' is a profile; name a workspace or run inside one")
        provider = canonical_provider(raw_provider)
        validate_provider(profile, provider)
    except (WorkspaceResolutionError, ProviderError) as exc:
        _fail(f"[red]{escape(str(exc))}[/red]")

    record, already = enable_provider(workspaces, workspace, provider)
    if already:
        console.print(
            _("[green]{provider}[/green] is already enabled in workspace '{workspace}'.", provider=provider, workspace=record.name)
        )
        return
    writer = _writer(ctx)
    save_workspaces(workspaces, writer)
    from .apply import apply_workspace_agents
    from .backends.git import reconcile_workspace_git
    from .shell import install_for_current_shell

    reconcile_workspace_git(profiles, workspaces, writer)
    apply_workspace_agents(profile, record, writer)
    install_for_current_shell(writer)
    console.print(_("[green]{provider}[/green] enabled in workspace '{workspace}'.", provider=provider, workspace=record.name))


@app.command(help=_("Reauthenticate the current workspace or an explicit target."))
def login(
    profile_name: str = typer.Argument("", metavar="workspace|profile", help=_("Workspace or profile to reauthenticate (default: current workspace).")),
    provider: str = typer.Option("", "--provider", help=_("Only this provider (gcloud, gh, adc or aws).")),
) -> None:
    """Reauthenticate the current workspace or an explicit target."""
    from .auth import login_profile

    try:
        profile, workspace = resolve_target(profile_name, Path.cwd(), load_profiles(), load_workspaces())
        selected_provider = canonical_provider(provider) if provider else ""
    except (WorkspaceResolutionError, ProviderError) as exc:
        _fail(f"[red]{escape(str(exc))}[/red]")
    enabled = workspace.providers if workspace is not None else None
    if not login_profile(profile, selected_provider, enabled_providers=enabled):
        raise typer.Exit(1)


def _expiry_warning_minutes() -> int:
    try:
        return max(0, int(os.environ.get("APARTA_EXPIRY_WARNING_MINUTES", "30")))
    except ValueError:
        return 30


@app.command(help=_("Show workspace identity, providers and credential expiry."))
def status(
    selector: str = typer.Argument("", metavar="workspace|profile", help=_("Workspace or profile to inspect (default: current workspace).")),
    shell: bool = typer.Option(False, "--shell", help=_("Print a compact prompt status.")),
) -> None:
    """Show the current workspace, provider health, and known expiry warning."""
    from .auth import OK, cached_check, read_cached_status, workspace_statuses

    try:
        profile, workspace = resolve_target(selector, Path.cwd(), load_profiles(), load_workspaces())
    except WorkspaceResolutionError as exc:
        _fail(f"[red]{escape(str(exc))}[/red]")
    providers = (
        canonical_providers(workspace.providers) if workspace is not None else profile.providers
    )
    source = read_cached_status(profile) if shell else cached_check(profile)
    statuses = workspace_statuses(profile, set(providers), source)
    known = {item.provider for item in statuses}
    expected_auth = set(providers).intersection({"gcloud", "adc", "github", "aws"})
    blocked = any(item.needs_human for item in statuses)
    unknown = bool(expected_auth - known) or any(
        item.state != OK and not item.needs_human for item in statuses
    )
    state = _("reauth needed") if blocked else _("unknown") if unknown else "ok"

    now = time.time()
    warning_seconds = _expiry_warning_minutes() * 60
    imminent = [
        item
        for item in statuses
        if item.expires_at is not None
        and not item.renewable
        and item.expires_at - now <= warning_seconds
    ]
    remaining = None
    if imminent:
        remaining = min(item.expires_at for item in imminent if item.expires_at is not None) - now
    countdown = f"{max(0, math.ceil(remaining / 60))}m" if remaining is not None else ""
    renewable = any(item.renewable for item in statuses)
    workspace_name = workspace.name if workspace is not None else profile.name

    if shell:
        prompt_name = re.sub(r"[^A-Za-z0-9._/-]", "?", workspace_name)
        extras = f" {countdown}" if countdown else ""
        print(f"[aparta:{prompt_name} {state}{extras}]")
        return

    console.print(_("Workspace: [bold]{name}[/bold]", name=workspace_name))
    console.print(_("Profile: [bold]{name}[/bold]", name=profile.name))
    console.print(_("Providers: {providers}", providers=", ".join(providers)))
    if countdown:
        console.print(_("Credential expires in [yellow]{remaining}[/yellow].", remaining=countdown))
    elif renewable:
        console.print(_("Credential is renewable automatically."))
    for item in statuses:
        detail = f": {item.detail}" if item.detail else ""
        console.print(f"{item.label}: {item.state.value}{detail}")


def _resolve_profile(profile_name: str):
    """The named profile, or the one owning the current folder."""
    profiles = load_profiles()
    if profile_name:
        return _profile_or_fail(profiles, profile_name)
    profile = profile_for_path(Path.cwd(), profiles)
    if profile is None:
        _fail(_("[red]This folder belongs to no profile.[/red] Use --profile <name> or run from a configured folder."))
    return profile


def _current_workspace():
    """The exact workspace of the current folder and its profile."""
    try:
        profile, workspace = resolve_target("", Path.cwd(), load_profiles(), load_workspaces())
    except WorkspaceResolutionError as exc:
        _fail(f"[red]{escape(str(exc))}[/red]")
    return workspace, profile


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True}, help=_("Run a command with the folder's profile environment."))
def run(
    ctx: typer.Context,
    profile_name: str = typer.Option(
        "", "--profile", "-p", help=_("Profile to use (default: the one owning the current folder).")
    ),
    with_gh_token: bool = typer.Option(
        False,
        "--with-gh-token",
        help=_("Also export GITHUB_TOKEN from the profile's gh (opt-in: it exposes the token to child processes)."),
    ),
) -> None:
    """Run a command with the profile's environment, exactly as the agents get it."""
    from .runner import run_in_profile, run_in_workspace

    command = list(ctx.args)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        _fail(_("[red]Nothing to run.[/red] Usage: aparta run -- <command> [args...]"), code=2)
    if profile_name:
        code = run_in_profile(_resolve_profile(profile_name), command, with_gh_token)
    else:
        workspace, profile = _current_workspace()
        code = run_in_workspace(profile, workspace, command, with_gh_token)
    raise typer.Exit(code)


@app.command(help=_("Print the profile's exports for scripts: eval \"$(aparta env)\"."))
def env(
    profile_name: str = typer.Argument("", metavar="profile", help=_("Profile to print (default: the one owning the current folder).")),
    with_gh_token: bool = typer.Option(
        False,
        "--with-gh-token",
        help=_("Also export GITHUB_TOKEN from the profile's gh (opt-in: it exposes the token to child processes)."),
    ),
    activate: bool = typer.Option(
        False,
        "--activate",
        help=_("Emit a complete shell transition, including stale-variable cleanup."),
    ),
) -> None:
    """Print export lines for scripts: eval "$(aparta env)"."""

    from .runner import export_lines, profile_env, with_github_token

    if activate:
        from .shell import activation_lines

        profiles = load_profiles()
        workspace = workspace_for_path(Path.cwd(), profiles, load_workspaces())
        profile = profiles.get(workspace.profile) if workspace is not None else None
        print(activation_lines(workspace, profile))
        return

    if profile_name:
        selected = profile_env(_resolve_profile(profile_name), with_gh_token)
    else:
        workspace, profile = _current_workspace()
        selected = workspace_env(workspace, profile)
        if with_gh_token and "github" in workspace.providers:
            with_github_token(selected, profile)
    lines = export_lines(selected)
    if lines:
        print(lines)


@app.command(hidden=True)
def hook(shell: str = typer.Argument("zsh")) -> None:
    """Print the integration code evaluated by a supported shell."""
    if shell != "zsh":
        _fail(_("[red]Unsupported shell: {shell}[/red]", shell=shell))
    from .shell import render_zsh_hook

    print(render_zsh_hook(), end="")


@app.command("shell-install", help=_("Install automatic zsh activation when directories change."))
def shell_install(ctx: typer.Context) -> None:
    from .shell import install_zsh_hook

    changed = install_zsh_hook(_writer(ctx))
    if changed:
        console.print(_("[green]Automatic zsh workspace activation installed.[/green]"))
    else:
        console.print(_("[green]Automatic zsh workspace activation is already installed.[/green]"))


@app.command(help=_("Check every credential, quiet when all is well."))
def check(
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help=_("Print nothing when every credential is valid (for startup hooks).")
    ),
    as_json: bool = typer.Option(
        False, "--json", help=_("Emit a JSON hook payload instead of text (for Gemini CLI).")
    ),
) -> None:
    """Check the credentials of every profile, quiet when all is well."""
    from .auth import OK, cached_check

    profiles = load_profiles()
    if not profiles:
        if quiet or as_json:
            if as_json:
                print("{}")
            return
        console.print(_("[yellow]No profile configured. Run `aparta init`.[/yellow]"))
        raise typer.Exit(1)

    lines: list[str] = []
    for profile in profiles.values():
        for status in cached_check(profile, force=not (quiet or as_json)):
            if status.state == OK:
                continue
            lines.append(
                _("{provider} in '{name}': {detail}", provider=status.label, name=profile.name, detail=status.detail)
            )
            if status.needs_human:
                lines.append(_("  run `aparta login {name}`", name=profile.name))

    if as_json:
        print(json.dumps({"systemMessage": "\n".join(lines)} if lines else {}))
        return
    for line in lines:
        console.print(f"[yellow]{line}[/yellow]" if not line.startswith("  ") else line)
    if not lines and not quiet:
        console.print(_("[green]Every credential is valid.[/green]"))


def _usage(command) -> str:
    """`name <required> [optional]` from the command's declared arguments."""
    name = command.name or command.callback.__name__.replace("_", "-")
    parts = [name]
    for param in inspect.signature(command.callback).parameters.values():
        info = param.default
        if not isinstance(info, ArgumentInfo):
            continue
        label = info.metavar or param.name.replace("_", "-")
        if "[" in label or "<" in label:
            parts.append(label)
        else:
            parts.append(f"<{label}>" if info.default is ... else f"[{label}]")
    if (command.context_settings or {}).get("allow_extra_args"):
        parts.append("-- <cmd>")
    return escape(" ".join(parts))


@app.command("help", help=_("This screen."))
def show_help() -> None:
    console.print(_("[bold]aparta[/bold]: the right account in every folder.") + "\n")
    table = Table(show_header=True)
    table.add_column(_("Command"), style="bold", no_wrap=True)
    table.add_column(_("What it does"), overflow="fold")
    table.add_row("aparta", _("First run opens the setup wizard; afterwards, an interactive menu."))
    for command in app.registered_commands:
        if not command.hidden:
            table.add_row(f"aparta {_usage(command)}", command.help or "")
    console.print(table)
    console.print(
        "\n"
        + _(
            "Global flags: [bold]--dry-run[/bold] previews every change as a diff, "
            "[bold]--version[/bold] prints the version. Language: [bold]APARTA_LANG=en|pt[/bold]."
        )
    )
    console.print(_("More detail per command: [bold]aparta <command> --help[/bold]."))
    console.print(_("Shell autocompletion: [bold]aparta --install-completion[/bold]."))


if __name__ == "__main__":
    app()
