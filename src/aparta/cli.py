"""aparta CLI: no args opens the wizard or menu; subcommands do the rest."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .apply import apply_profile
from .doctor import check_profile
from .fsutil import SafeWriter
from .profiles import load_profiles, profiles_path

app = typer.Typer(
    name="aparta",
    help="Isola contas de desenvolvimento (git, gh, gcloud) por pasta de projeto "
    "e injeta variáveis de ambiente nos agentes de IA de terminal.",
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
        False, "--dry-run", help="Mostra o diff do que seria alterado, sem aplicar nada."
    ),
    version: bool = typer.Option(False, "--version", help="Mostra a versão e sai."),
) -> None:
    if version:
        console.print(f"aparta {__version__}")
        raise typer.Exit()
    ctx.obj = {"dry_run": dry_run}
    if ctx.invoked_subcommand is None:
        if default_action() == "wizard":
            _run_wizard(dry_run)
        else:
            _run_menu(dry_run)


def _run_wizard(dry_run: bool) -> None:
    from .wizard import run_wizard

    try:
        run_wizard(dry_run=dry_run)
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelado.[/yellow]")
        raise typer.Exit(1)


def _run_menu(dry_run: bool) -> None:
    import questionary

    while True:
        choice = questionary.select(
            "aparta — o que você quer fazer?",
            choices=[
                questionary.Choice("Novo perfil (wizard)", value="init"),
                questionary.Choice("Aplicar um perfil (apply)", value="apply"),
                questionary.Choice("Validar tudo (doctor)", value="doctor"),
                questionary.Choice("Listar perfis (list)", value="list"),
                questionary.Choice("Sair", value="quit"),
            ],
        ).ask()
        if choice in (None, "quit"):
            return
        if choice == "init":
            _run_wizard(dry_run)
        elif choice == "apply":
            profiles = load_profiles()
            if not profiles:
                console.print("[yellow]Nenhum perfil configurado ainda.[/yellow]")
                continue
            name = questionary.select("Qual perfil?", choices=list(profiles)).ask()
            if name:
                apply_profile(profiles[name], SafeWriter(dry_run=dry_run))
        elif choice == "doctor":
            for p in load_profiles().values():
                check_profile(p)
        elif choice == "list":
            _print_profiles()


@app.command()
def init(ctx: typer.Context) -> None:
    """Wizard interativo: escolhe agentes, configura contextos e aplica."""
    _run_wizard(ctx.obj["dry_run"])


@app.command()
def apply(
    ctx: typer.Context,
    profile_name: str = typer.Argument(..., help="Nome do perfil a aplicar."),
) -> None:
    """Aplica um perfil: gitconfigs, gh config dir, gcloud config e env nos repos."""
    profiles = load_profiles()
    profile = profiles.get(profile_name)
    if not profile:
        console.print(f"[red]Perfil '{profile_name}' não encontrado.[/red] Rode `aparta init`.")
        raise typer.Exit(1)
    apply_profile(profile, SafeWriter(dry_run=ctx.obj["dry_run"]))


@app.command()
def doctor(
    profile_name: str = typer.Argument(
        None, help="Perfil a validar (vazio = todos)."
    ),
) -> None:
    """Valida o estado real: git user.email por repo, gh auth status, gcloud config."""
    profiles = load_profiles()
    if not profiles:
        console.print("[yellow]Nenhum perfil configurado. Rode `aparta init`.[/yellow]")
        raise typer.Exit(1)
    if profile_name and profile_name not in profiles:
        console.print(f"[red]Perfil '{profile_name}' não encontrado.[/red]")
        raise typer.Exit(1)
    selected = [profiles[profile_name]] if profile_name else list(profiles.values())

    # list comprehension on purpose: all() must not short-circuit, every
    # profile's table should render even after a failure
    ok = all([check_profile(p) for p in selected])
    raise typer.Exit(0 if ok else 1)


def _print_profiles() -> None:
    profiles = load_profiles()
    if not profiles:
        console.print("[yellow]Nenhum perfil configurado. Rode `aparta init`.[/yellow]")
        return
    table = Table(title=f"Perfis ({profiles_path()})")
    table.add_column("Nome", style="bold")
    table.add_column("Raiz")
    table.add_column("Git e-mail")
    table.add_column("gh")
    table.add_column("gcloud")
    table.add_column("Agentes")
    for p in profiles.values():
        gcloud = p.gcloud_account + (f" / {p.gcloud_project}" if p.gcloud_project else "")
        table.add_row(p.name, p.root, p.git_email, p.gh_user or "—", gcloud or "—", ", ".join(p.agents) or "—")
    console.print(table)


@app.command("list")
def list_profiles() -> None:
    """Lista os perfis configurados."""
    _print_profiles()


@app.command()
def scan(
    paths: list[str] = typer.Argument(
        None, help="Pastas a varrer (vazio = sua home inteira)."
    ),
) -> None:
    """Varre o disco e sugere grupos de projetos (somente leitura, nada é alterado)."""
    from .discovery import discover

    where = ", ".join(paths) if paths else "sua home"
    console.print(f"[dim]Varrendo {where} e ~/.gitconfig (somente leitura)...[/dim]")
    suggestions = discover(scan_roots=paths or None)
    if not suggestions:
        console.print("[yellow]Nenhum repositório git encontrado.[/yellow]")
        return
    table = Table(title="Grupos de projetos detectados")
    table.add_column("Nome sugerido", style="bold")
    table.add_column("Pasta")
    table.add_column("Repos", justify="right")
    table.add_column("Git e-mail")
    table.add_column("gh / gcloud")
    table.add_column("Origem")
    for s in suggestions:
        accounts = " / ".join(x for x in (s.gh_config, s.gcloud_config) if x) or "—"
        source = "~/.gitconfig" if s.source == "gitconfig" else "varredura"
        table.add_row(s.name, s.root, str(s.repo_count), s.git_email or "—", accounts, source)
    console.print(table)
    console.print("Use [bold]aparta init[/bold] para transformá-los em perfis.")


if __name__ == "__main__":
    app()
