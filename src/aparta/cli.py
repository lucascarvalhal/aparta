"""CLI do aparta: sem argumentos cai no wizard/menu; comandos init, apply, doctor, list."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .agents import get_adapters
from .backends.gcloud import apply_gcloud
from .backends.gh import apply_gh
from .backends.git import apply_git
from .doctor import check_profile, find_repos
from .fsutil import SafeWriter
from .profiles import Profile, load_profiles, profiles_path

app = typer.Typer(
    name="aparta",
    help="Isola contas de desenvolvimento (git, gh, gcloud) por pasta de projeto "
    "e injeta variáveis de ambiente nos agentes de IA de terminal.",
)
console = Console()

_state = {"dry_run": False}


def default_action(profiles_file: Path | None = None) -> str:
    """Roteamento do `aparta` sem argumentos: 'wizard' na primeira execução, senão 'menu'."""
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
    _state["dry_run"] = dry_run
    if ctx.invoked_subcommand is None:
        if default_action() == "wizard":
            _run_wizard()
        else:
            _run_menu()


def _writer() -> SafeWriter:
    return SafeWriter(dry_run=_state["dry_run"])


def _run_wizard() -> None:
    from .wizard import run_wizard

    try:
        run_wizard(dry_run=_state["dry_run"])
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelado.[/yellow]")
        raise typer.Exit(1)


def _run_menu() -> None:
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
            _run_wizard()
        elif choice == "apply":
            profiles = load_profiles()
            name = questionary.select("Qual perfil?", choices=list(profiles)).ask()
            if name:
                _apply_profile(profiles[name], _writer())
        elif choice == "doctor":
            for p in load_profiles().values():
                check_profile(p)
        elif choice == "list":
            _print_profiles()


@app.command()
def init() -> None:
    """Wizard interativo: escolhe agentes, configura contextos e aplica."""
    _run_wizard()


def _apply_profile(profile: Profile, writer: SafeWriter) -> None:
    console.print(f"[bold]Aplicando perfil '{profile.name}'[/bold] (raiz: {profile.root_path})\n")

    apply_git(profile, writer)
    apply_gh(profile, writer)
    apply_gcloud(profile, writer)

    env = profile.env()
    if env:
        repos = find_repos(profile.root_path)
        if not repos:
            console.print(f"[yellow]Nenhum repositório git encontrado em {profile.root_path}.[/yellow]")
        adapters = get_adapters(profile.agents)
        for repo in repos:
            for adapter in adapters:
                if adapter.detect(repo):
                    adapter.inject(repo, env, writer)
    else:
        console.print("[dim]Perfil sem gh/gcloud: nada de env para injetar nos agentes.[/dim]")

    if writer.dry_run:
        console.print(f"\n[yellow]--dry-run: {len(writer.changes)} mudança(s) prevista(s); nada foi alterado.[/yellow]")
    elif not writer.changes:
        console.print("\n[green]Tudo já estava aplicado; nada a mudar.[/green]")
    else:
        console.print(f"\n[green]Pronto: {len(writer.changes)} arquivo(s) atualizado(s).[/green]")


@app.command()
def apply(
    profile_name: str = typer.Argument(..., help="Nome do perfil a aplicar."),
) -> None:
    """Aplica um perfil: gitconfigs, gh config dir, gcloud config e env nos repos."""
    profiles = load_profiles()
    profile = profiles.get(profile_name)
    if not profile:
        console.print(f"[red]Perfil '{profile_name}' não encontrado.[/red] Rode `aparta init`.")
        raise typer.Exit(1)
    _apply_profile(profile, _writer())


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


if __name__ == "__main__":
    app()
