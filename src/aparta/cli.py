"""CLI do aparta: init, apply, doctor, list — com --dry-run global."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .agents import ADAPTERS, get_adapters
from .backends.gcloud import apply_gcloud
from .backends.gh import apply_gh
from .backends.git import apply_git
from .doctor import check_profile, find_repos
from .fsutil import SafeWriter
from .profiles import Profile, load_profiles, profiles_path, save_profiles

app = typer.Typer(
    name="aparta",
    help="Isola contas de desenvolvimento (git, gh, gcloud) por pasta de projeto "
    "e injeta variáveis de ambiente nos agentes de IA de terminal.",
    no_args_is_help=True,
)
console = Console()

_state = {"dry_run": False}


@app.callback(invoke_without_command=True)
def main(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Mostra o diff do que seria alterado, sem aplicar nada."
    ),
    version: bool = typer.Option(False, "--version", help="Mostra a versão e sai."),
) -> None:
    if version:
        console.print(f"aparta {__version__}")
        raise typer.Exit()
    _state["dry_run"] = dry_run


def _writer() -> SafeWriter:
    return SafeWriter(dry_run=_state["dry_run"])


@app.command()
def init() -> None:
    """Wizard interativo: cria ou edita um perfil/contexto."""
    import questionary

    profiles = load_profiles()
    console.print("[bold]aparta init[/bold] — vamos configurar um perfil.\n")

    name = questionary.text("Nome do perfil (ex.: pessoal, trabalho):").ask()
    if not name:
        raise typer.Exit(1)
    name = name.strip()
    if name in profiles and not questionary.confirm(
        f"Perfil '{name}' já existe. Sobrescrever?", default=False
    ).ask():
        raise typer.Exit(1)

    root = questionary.path(
        "Pasta raiz dos projetos deste perfil:", default=f"~/{name}"
    ).ask()
    git_email = questionary.text("E-mail do git para esses repositórios:").ask()
    git_name = questionary.text("Nome do git (vazio = manter o global):", default="").ask()
    ssh_key = questionary.path(
        "Chave SSH específica (vazio = nenhuma):", default=""
    ).ask()
    ssh_alias = ""
    if ssh_key:
        ssh_alias = questionary.text(
            "Alias de host SSH para reescrever remotes https (vazio = não reescrever):",
            default="",
        ).ask()
    gh_user = questionary.text("Usuário do GitHub CLI (vazio = não isolar gh):", default="").ask()
    gcloud_account = questionary.text(
        "Conta gcloud (vazio = não isolar gcloud):", default=""
    ).ask()
    gcloud_project = ""
    if gcloud_account:
        gcloud_project = questionary.text("Projeto gcloud padrão (opcional):", default="").ask()
    agents = questionary.checkbox(
        "Agentes que devem receber as variáveis de ambiente:",
        choices=[
            questionary.Choice(n, checked=(n == "claude-code")) for n in ADAPTERS
        ],
    ).ask()

    if None in (root, git_email):
        raise typer.Exit(1)

    profile = Profile(
        name=name,
        root=root.strip(),
        git_email=git_email.strip(),
        git_name=(git_name or "").strip(),
        ssh_key=(ssh_key or "").strip(),
        ssh_alias=(ssh_alias or "").strip(),
        gh_user=(gh_user or "").strip(),
        gcloud_account=(gcloud_account or "").strip(),
        gcloud_project=(gcloud_project or "").strip(),
        agents=agents or [],
    )
    profiles[name] = profile
    save_profiles(profiles, _writer())
    if not _state["dry_run"]:
        console.print(
            f"\n[green]Perfil '{name}' salvo em {profiles_path()}.[/green] "
            f"Rode [bold]aparta apply {name}[/bold] para aplicar."
        )


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

    writer = _writer()
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
    selected = [profiles[profile_name]] if profile_name else list(profiles.values())
    if profile_name and profile_name not in profiles:
        console.print(f"[red]Perfil '{profile_name}' não encontrado.[/red]")
        raise typer.Exit(1)

    ok = all([check_profile(p) for p in selected])
    raise typer.Exit(0 if ok else 1)


@app.command("list")
def list_profiles() -> None:
    """Lista os perfis configurados."""
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


if __name__ == "__main__":
    app()
