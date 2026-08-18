"""Wizard interativo do aparta: agentes primeiro, depois contextos guiados.

Fluxo:
1. Escolha dos agentes de IA (checkbox multi-seleção, vindos do registry).
2. Por contexto: nome → pasta raiz → e-mail git → chave SSH (lista ~/.ssh)
   → conta gh (lista `gh auth status`) → conta gcloud (lista `gcloud auth list`).
3. Resumo rico de tudo que será feito + confirmação única + apply automático
   (ou só salvar sem aplicar).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .agents import ADAPTERS
from .fsutil import SafeWriter
from .profiles import Profile, load_profiles, profiles_path, save_profiles

console = Console()

SKIP = "(pular)"


# ---------------------------------------------------------------- descoberta

def list_ssh_keys(ssh_dir: Path | None = None) -> list[str]:
    """Chaves privadas em ~/.ssh (arquivos com par .pub correspondente)."""
    ssh_dir = ssh_dir or Path.home() / ".ssh"
    if not ssh_dir.exists():
        return []
    keys = []
    for pub in sorted(ssh_dir.glob("*.pub")):
        private = pub.with_suffix("")
        if private.exists():
            keys.append(str(private))
    return keys


def parse_gh_accounts(status_output: str) -> list[str]:
    """Extrai usuários logados da saída de `gh auth status` (todas as contas)."""
    return list(dict.fromkeys(re.findall(r"Logged in to \S+ account (\S+)", status_output)))


def list_gh_accounts() -> list[str]:
    try:
        r = subprocess.run(
            ["gh", "auth", "status"], capture_output=True, text=True, timeout=30
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    return parse_gh_accounts(r.stdout + r.stderr)


def list_gcloud_accounts() -> list[str]:
    try:
        r = subprocess.run(
            ["gcloud", "auth", "list", "--format=value(account)"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if r.returncode != 0:
        return []
    return [line.strip() for line in r.stdout.splitlines() if line.strip()]


# ------------------------------------------------------------------- wizard

def _choose_from(question: str, options: list[str], allow_manual: bool = True) -> str:
    """Select com opção de pular; retorna '' quando pulado."""
    import questionary

    choices = options + ([SKIP] if SKIP not in options else [])
    answer = questionary.select(question, choices=choices).ask()
    if answer is None:
        raise KeyboardInterrupt
    return "" if answer == SKIP else answer


def _ask_context(agents: list[str], existing_names: list[str]) -> Profile | None:
    import questionary

    name = questionary.text(
        "Nome do contexto (ex.: pessoal, trabalho):",
        validate=lambda v: bool(v.strip()) or "obrigatório",
    ).ask()
    if name is None:
        return None
    name = name.strip()
    if name in existing_names:
        if not questionary.confirm(f"'{name}' já existe. Sobrescrever?", default=False).ask():
            return None

    root = questionary.path("Pasta raiz dos projetos deste contexto:", default=f"~/{name}").ask()
    if root is None:
        return None

    git_email = questionary.text(
        "E-mail do git para esses repositórios:",
        validate=lambda v: "@" in v or "informe um e-mail válido",
    ).ask()
    if git_email is None:
        return None

    ssh_keys = list_ssh_keys()
    ssh_key = ""
    ssh_alias = ""
    if ssh_keys:
        ssh_key = _choose_from("Chave SSH específica deste contexto:", ssh_keys)
    else:
        ssh_key = (questionary.path("Chave SSH (vazio = pular):", default="").ask() or "").strip()
    if ssh_key:
        ssh_alias = (
            questionary.text(
                "Alias de host SSH p/ reescrever remotes https (vazio = não reescrever):",
                default="",
            ).ask()
            or ""
        ).strip()

    gh_accounts = list_gh_accounts()
    if gh_accounts:
        gh_user = _choose_from("Conta do GitHub CLI para este contexto:", gh_accounts)
    else:
        console.print("[dim]Nenhuma conta gh detectada (gh auth status). Pulando gh.[/dim]")
        gh_user = ""

    gcloud_accounts = list_gcloud_accounts()
    gcloud_account = ""
    gcloud_project = ""
    if gcloud_accounts:
        gcloud_account = _choose_from("Conta gcloud para este contexto:", gcloud_accounts)
        if gcloud_account:
            gcloud_project = (
                questionary.text("Projeto gcloud padrão (opcional):", default="").ask() or ""
            ).strip()
    else:
        console.print("[dim]Nenhuma conta gcloud detectada (gcloud auth list). Pulando gcloud.[/dim]")

    return Profile(
        name=name,
        root=root.strip(),
        git_email=git_email.strip(),
        ssh_key=ssh_key,
        ssh_alias=ssh_alias,
        gh_user=gh_user,
        gcloud_account=gcloud_account,
        gcloud_project=gcloud_project,
        agents=agents,
    )


def _summary(new_profiles: list[Profile]) -> None:
    table = Table(title="Resumo — o que o aparta vai fazer", show_lines=True)
    table.add_column("Contexto", style="bold")
    table.add_column("Ações", overflow="fold")
    for p in new_profiles:
        actions = [
            f"git: criar ~/.gitconfig-{p.name} (email {p.git_email}"
            + (f", chave {p.ssh_key}" if p.ssh_key else "")
            + ") e adicionar includeIf p/ "
            + p.root,
        ]
        if p.ssh_alias:
            actions.append(f"git: reescrever remotes https via alias git@{p.ssh_alias}:")
        if p.gh_user:
            actions.append(
                f"gh: copiar ~/.config/gh → ~/.config/gh-{p.name} e ativar '{p.gh_user}'"
            )
        if p.gcloud_account:
            proj = f" (projeto {p.gcloud_project})" if p.gcloud_project else ""
            actions.append(f"gcloud: configuração '{p.name}' com {p.gcloud_account}{proj}")
        env = p.env()
        if env and p.agents:
            names = ", ".join(ADAPTERS[a].display_name for a in p.agents if a in ADAPTERS)
            actions.append(f"agentes ({names}): injetar {', '.join(env)} nos repos de {p.root}")
        table.add_row(p.name, "\n".join(actions))
    console.print(table)
    console.print(
        Panel(
            "Toda escrita em arquivo existente cria backup (.bak-aparta-<timestamp>) "
            "e faz merge — nada é substituído. Use --dry-run para só ver o diff.",
            title="Segurança",
            border_style="dim",
        )
    )


def run_wizard(dry_run: bool = False) -> None:
    """Wizard completo. Levanta KeyboardInterrupt/retorna cedo se cancelado."""
    import questionary

    console.print(
        Panel(
            "Bem-vindo ao [bold]aparta[/bold]! Vamos isolar suas contas de "
            "desenvolvimento por pasta de projeto.",
            border_style="cyan",
        )
    )

    # Passo 1: agentes de IA (do registry — novos adapters aparecem sozinhos)
    agents = questionary.checkbox(
        "Quais agentes de IA devem receber as variáveis de ambiente?",
        choices=[
            questionary.Choice(cls.display_name, value=name, checked=(name == "claude-code"))
            for name, cls in sorted(ADAPTERS.items())
        ],
    ).ask()
    if agents is None:
        return

    # Passo 2: contextos
    profiles = load_profiles()
    new_profiles: list[Profile] = []
    while True:
        profile = _ask_context(agents, list(profiles) + [p.name for p in new_profiles])
        if profile is not None:
            new_profiles.append(profile)
        if not questionary.confirm("Configurar outro contexto?", default=False).ask():
            break

    if not new_profiles:
        console.print("[yellow]Nenhum contexto configurado.[/yellow]")
        return

    # Passo 3: resumo + confirmação única
    _summary(new_profiles)
    action = questionary.select(
        "Como prosseguir?",
        choices=[
            questionary.Choice("Salvar e aplicar agora", value="apply"),
            questionary.Choice("Só salvar os perfis (aplicar depois com `aparta apply`)", value="save"),
            questionary.Choice("Cancelar", value="cancel"),
        ],
    ).ask()
    if action in (None, "cancel"):
        console.print("[yellow]Cancelado; nada foi salvo.[/yellow]")
        return

    writer = SafeWriter(dry_run=dry_run)
    for p in new_profiles:
        profiles[p.name] = p
    save_profiles(profiles, writer)
    if not dry_run:
        console.print(f"[green]Perfis salvos em {profiles_path()}.[/green]")

    if action == "apply":
        from .cli import _apply_profile

        for p in new_profiles:
            _apply_profile(p, writer)
    else:
        names = ", ".join(p.name for p in new_profiles)
        console.print(f"Quando quiser aplicar: [bold]aparta apply {names.split(', ')[0]}[/bold]")
