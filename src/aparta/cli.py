"""aparta CLI: no args opens the wizard or menu; subcommands do the rest."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .apply import apply_profile
from .doctor import check_profile
from .fsutil import SafeWriter
from .i18n import _
from .profiles import load_profiles, profiles_path

app = typer.Typer(
    name="aparta",
    help=_(
        "Isolates development accounts (git, gh, gcloud) per project folder "
        "and injects environment variables into terminal AI agents."
    ),
)
console = Console()


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
    if ctx.invoked_subcommand is None:
        if default_action() == "wizard":
            _run_wizard(dry_run, verbose)
        else:
            _run_menu(dry_run, verbose)


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
            name = questionary.select(_("Which profile?"), choices=list(profiles)).ask()
            if name:
                apply_profile(profiles[name], SafeWriter(dry_run=dry_run, verbose=verbose))
        elif choice == "doctor":
            for p in load_profiles().values():
                check_profile(p)
        elif choice == "list":
            _print_profiles()


@app.command()
def init(ctx: typer.Context) -> None:
    """Interactive wizard: pick agents, configure profiles and apply."""
    _run_wizard(ctx.obj["dry_run"], ctx.obj["verbose"])


@app.command()
def apply(
    ctx: typer.Context,
    profile_name: str = typer.Argument(..., help=_("Name of the profile to apply.")),
) -> None:
    """Apply a profile: gitconfigs, gh config dir, gcloud config and repo env."""
    profiles = load_profiles()
    profile = profiles.get(profile_name)
    if not profile:
        console.print(_("[red]Profile '{name}' not found.[/red] Run `aparta init`.", name=profile_name))
        raise typer.Exit(1)
    apply_profile(profile, SafeWriter(dry_run=ctx.obj["dry_run"], verbose=ctx.obj["verbose"]))


@app.command()
def doctor(
    profile_name: str = typer.Argument(
        None, help=_("Profile to check (empty = all).")
    ),
) -> None:
    """Check the real state: git user.email per repo, gh auth status, gcloud config."""
    profiles = load_profiles()
    if not profiles:
        console.print(_("[yellow]No profile configured. Run `aparta init`.[/yellow]"))
        raise typer.Exit(1)
    if profile_name and profile_name not in profiles:
        console.print(_("[red]Profile '{name}' not found.[/red]", name=profile_name))
        raise typer.Exit(1)
    selected = [profiles[profile_name]] if profile_name else list(profiles.values())

    # list comprehension on purpose: all() must not short-circuit, every
    # profile's table should render even after a failure
    ok = all([check_profile(p) for p in selected])
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


@app.command("list")
def list_profiles() -> None:
    """List configured profiles."""
    _print_profiles()


@app.command()
def scan(
    paths: list[str] = typer.Argument(
        None, help=_("Folders to scan (empty = your whole home).")
    ),
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


@app.command()
def remove(
    ctx: typer.Context,
    profile_name: str = typer.Argument(..., help=_("Name of the profile to remove.")),
    yes: bool = typer.Option(False, "--yes", "-y", help=_("Do not ask for confirmation.")),
) -> None:
    """Remove a profile and undo the configuration it applied."""
    from .profiles import save_profiles
    from .remove import remove_profile

    profiles = load_profiles()
    profile = profiles.get(profile_name)
    if not profile:
        console.print(_("[red]Profile '{name}' not found.[/red]", name=profile_name))
        raise typer.Exit(1)
    if not yes:
        import questionary

        confirmed = questionary.confirm(
            _("Remove '{name}' and undo its gitconfig, gh, gcloud and agent env?", name=profile_name),
            default=False,
        ).ask()
        if not confirmed:
            console.print(_("[yellow]Cancelled.[/yellow]"))
            raise typer.Exit(0)
    writer = SafeWriter(dry_run=ctx.obj["dry_run"], verbose=ctx.obj["verbose"])
    remove_profile(profile, writer)
    if not ctx.obj["dry_run"]:
        del profiles[profile_name]
        save_profiles(profiles, writer)


@app.command("help")
def show_help() -> None:
    """Show every command and what it does."""
    console.print(_("[bold]aparta[/bold]: the right account in every folder.") + "\n")
    table = Table(show_header=True)
    table.add_column(_("Command"), style="bold", no_wrap=True)
    table.add_column(_("What it does"), overflow="fold")
    table.add_row("aparta", _("First run opens the setup wizard; afterwards, an interactive menu."))
    table.add_row("aparta init", _("Guided wizard: pick agents, detect or create profiles, apply."))
    table.add_row("aparta scan \\[folders]", _("Read-only: find git repos and suggest profile groups (default: your home)."))
    table.add_row("aparta apply <profile>", _("Re-apply a profile: gitconfigs, gh, gcloud and agent env in the repos."))
    table.add_row("aparta remove <profile>", _("Remove a profile and undo what it applied (backups kept)."))
    table.add_row("aparta doctor \\[profile]", _("Check the real state: e-mail per repo, gh auth, gcloud config, agent env."))
    table.add_row("aparta list", _("List configured profiles."))
    table.add_row("aparta help", _("This screen."))
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
