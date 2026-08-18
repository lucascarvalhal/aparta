"""Wizard interativo do aparta: agentes primeiro, depois contextos guiados.

Fluxo:
1. Escolha dos agentes de IA (checkbox multi-seleção, vindos do registry).
2. Descoberta: varredura do disco (discovery.discover) sugere grupos de
   projetos já em uso, com nome/pasta/e-mail pré-preenchidos.
3. Por grupo: nome → pasta raiz → e-mail git → chave SSH (lista ~/.ssh)
   → conta gh (lista `gh auth status` + opção de logar conta nova no config
   dir do perfil) → conta gcloud (idem, na configuração nomeada do perfil).
4. Repos soltos (fora das raízes) podem ser adotados por um perfil:
   include.path local no .git/config, sem mover a pasta.
5. Resumo rico de tudo que será feito + confirmação única + apply automático
   (ou só salvar sem aplicar).
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .agents import ADAPTERS
from .discovery import ContextSuggestion, discover
from .fsutil import SafeWriter
from .profiles import Profile, load_profiles, profiles_path, save_profiles

console = Console()

SKIP = "(pular)"
NEW_LOGIN = "(logar nova conta agora...)"


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


# -------------------------------------------------------------- login novo

def login_new_gh_account(profile_name: str, dry_run: bool = False) -> str:
    """`gh auth login` interativo já dentro de ~/.config/gh-<perfil>.

    A conta nova nasce isolada no config dir do perfil — a config global do gh
    não é tocada. Retorna o usuário logado ('' se falhou/cancelou/dry-run).
    """
    dst = Path.home() / ".config" / f"gh-{profile_name}"
    if dry_run:
        console.print(f"[yellow]--dry-run[/yellow] GH_CONFIG_DIR={dst} gh auth login")
        return ""
    dst.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, GH_CONFIG_DIR=str(dst))
    try:
        r = subprocess.run(["gh", "auth", "login"], env=env)  # interativo, herda o TTY
    except FileNotFoundError:
        console.print("[red]gh não encontrado no PATH.[/red]")
        return ""
    if r.returncode != 0:
        console.print("[yellow]Login cancelado ou falhou; pulando gh.[/yellow]")
        return ""
    status = subprocess.run(
        ["gh", "auth", "status"], env=env, capture_output=True, text=True, timeout=30
    )
    accounts = parse_gh_accounts(status.stdout + status.stderr)
    if accounts:
        console.print(f"[green]gh:[/green] '{accounts[0]}' logado em {dst}")
        return accounts[0]
    return ""


def login_new_gcloud_account(profile_name: str, dry_run: bool = False) -> str:
    """`gcloud auth login` interativo dentro da configuração nomeada do perfil.

    A configuração é criada com --no-activate antes, e o login roda com
    CLOUDSDK_ACTIVE_CONFIG_NAME apontando para ela — a conta ativa da sua
    configuração global não muda. Retorna a conta logada ('' se falhou).
    """
    if dry_run:
        console.print(
            f"[yellow]--dry-run[/yellow] CLOUDSDK_ACTIVE_CONFIG_NAME={profile_name} gcloud auth login"
        )
        return ""
    try:
        subprocess.run(
            ["gcloud", "config", "configurations", "create", profile_name, "--no-activate"],
            capture_output=True,
            text=True,
        )  # "already exists" é ok — o login abaixo só usa a config
        env = dict(os.environ, CLOUDSDK_ACTIVE_CONFIG_NAME=profile_name)
        r = subprocess.run(["gcloud", "auth", "login"], env=env)  # interativo
        if r.returncode != 0:
            console.print("[yellow]Login cancelado ou falhou; pulando gcloud.[/yellow]")
            return ""
        active = subprocess.run(
            ["gcloud", "config", "get", "account"],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        console.print("[red]gcloud não encontrado no PATH.[/red]")
        return ""
    account = active.stdout.strip()
    if account:
        console.print(f"[green]gcloud:[/green] '{account}' na configuração '{profile_name}'")
    return account


# ------------------------------------------------------------------- wizard

def _choose_from(
    question: str,
    options: list[str],
    allow_manual: bool = True,
    default: str = "",
) -> str:
    """Select com opção de pular; retorna '' quando pulado. `default` (se
    estiver entre as opções) começa selecionado — Enter direto confirma."""
    import questionary

    choices = options + ([SKIP] if SKIP not in options else [])
    answer = questionary.select(
        question, choices=choices, default=default if default in choices else None
    ).ask()
    if answer is None:
        raise KeyboardInterrupt
    return "" if answer == SKIP else answer


def _ask_context(
    agents: list[str],
    existing_names: list[str],
    suggestion: ContextSuggestion | None = None,
    dry_run: bool = False,
) -> Profile | None:
    import questionary

    name = questionary.text(
        f"Nome do perfil para {suggestion.root}:"
        if suggestion
        else "Nome do novo perfil (ex.: pessoal, trabalho, cliente-x):",
        default=suggestion.name if suggestion else "",
        validate=lambda v: bool(v.strip()) or "obrigatório",
    ).ask()
    if name is None:
        return None
    name = name.strip()
    if name in existing_names:
        if not questionary.confirm(f"'{name}' já existe. Sobrescrever?", default=False).ask():
            return None

    root = questionary.path(
        "Pasta raiz dos projetos deste grupo:",
        default=suggestion.root if suggestion else f"~/{name}",
    ).ask()
    if root is None:
        return None

    git_email = questionary.text(
        "E-mail do git para esses repositórios:",
        default=suggestion.git_email if suggestion else "",
        validate=lambda v: "@" in v or "informe um e-mail válido",
    ).ask()
    if git_email is None:
        return None

    ssh_keys = list_ssh_keys()
    ssh_key = ""
    ssh_alias = ""
    suggested_key = str(Path(suggestion.ssh_key).expanduser()) if suggestion and suggestion.ssh_key else ""
    if ssh_keys:
        ssh_key = _choose_from(
            "Chave SSH específica deste perfil:", ssh_keys, default=suggested_key
        )
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
    if not gh_accounts:
        console.print("[dim]Nenhuma conta gh logada ainda (gh auth status).[/dim]")
    gh_user = _choose_from(
        "Conta do GitHub CLI para este perfil:",
        gh_accounts + [NEW_LOGIN],
        default=suggestion.gh_user if suggestion else "",
    )
    if gh_user == NEW_LOGIN:
        gh_user = login_new_gh_account(name, dry_run=dry_run)

    gcloud_accounts = list_gcloud_accounts()
    if not gcloud_accounts:
        console.print("[dim]Nenhuma conta gcloud logada ainda (gcloud auth list).[/dim]")
    gcloud_account = _choose_from(
        "Conta gcloud para este perfil:",
        gcloud_accounts + [NEW_LOGIN],
        default=suggestion.gcloud_account if suggestion else "",
    )
    if gcloud_account == NEW_LOGIN:
        gcloud_account = login_new_gcloud_account(name, dry_run=dry_run)
    gcloud_project = ""
    if gcloud_account:
        gcloud_project = (
            questionary.text("Projeto gcloud padrão (opcional):", default="").ask() or ""
        ).strip()

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


def _suggestion_label(s: ContextSuggestion) -> str:
    parts = [f"{s.root} ({s.repo_count} repo{'s' if s.repo_count != 1 else ''}"]
    if s.git_email:
        parts.append(f", {s.git_email}")
    if s.gh_user or s.gh_config:
        parts.append(f", gh:{s.gh_user or s.gh_config}")
    if s.gcloud_account or s.gcloud_config:
        parts.append(f", gcloud:{s.gcloud_account or s.gcloud_config}")
    if s.source == "gitconfig":
        parts.append(", já no ~/.gitconfig")
    return "".join(parts) + ")"


def _adopt_loose_repos(all_profiles: list[Profile]) -> None:
    """Oferece repos fora das raízes dos perfis para adoção (identidade local,
    sem mover pastas). Altera all_profiles in-place via adopted_repos."""
    import questionary

    from .discovery import loose_repos

    already = {r for p in all_profiles for r in p.adopted_repos}
    loose = [r for r in loose_repos([p.root for p in all_profiles]) if str(r) not in already]
    if not loose:
        return
    console.print(
        f"\nEncontrei [bold]{len(loose)}[/bold] repositório(s) fora das pastas dos "
        "perfis. Você pode adotá-los: eles ficam onde estão e recebem a identidade "
        "do perfil só no próprio repo."
    )
    remaining = [str(r) for r in loose]
    for p in all_profiles:
        if not remaining:
            break
        chosen = questionary.checkbox(
            f"Quais destes pertencem a '{p.name}'? (Enter = nenhum)",
            choices=remaining,
        ).ask()
        if chosen is None:
            return
        p.adopted_repos.extend(chosen)
        remaining = [r for r in remaining if r not in chosen]


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
        if p.adopted_repos:
            actions.append(
                f"git: adotar {len(p.adopted_repos)} repo(s) fora da raiz "
                "(include.path local, sem mover): "
                + ", ".join(Path(r).name for r in p.adopted_repos)
            )
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

    # Passo 2: descoberta — varre o disco e sugere grupos prontos
    profiles = load_profiles()
    new_profiles: list[Profile] = []

    console.print("[dim]Procurando projetos existentes no disco...[/dim]")
    suggestions = [s for s in discover() if s.name not in profiles]
    if suggestions:
        console.print(
            f"Encontrei [bold]{len(suggestions)}[/bold] grupo(s) de projetos já em uso:"
        )
        chosen = questionary.checkbox(
            "Quais devem virar perfis? (as respostas vêm pré-preenchidas)",
            choices=[
                questionary.Choice(_suggestion_label(s), value=s, checked=True)
                for s in suggestions
            ],
        ).ask()
        for i, s in enumerate(chosen or [], start=1):
            console.print(
                Panel(
                    _suggestion_label(s)
                    + "\n[dim]Enter aceita os valores sugeridos; edite o que quiser.[/dim]",
                    title=f"Grupo {i}/{len(chosen)} — {s.root}",
                    border_style="cyan",
                )
            )
            profile = _ask_context(
                agents,
                list(profiles) + [p.name for p in new_profiles],
                suggestion=s,
                dry_run=dry_run,
            )
            if profile is not None:
                new_profiles.append(profile)

    # Passo 3: grupos manuais (primeiro obrigatório se nada foi descoberto)
    while True:
        if new_profiles and not questionary.confirm(
            "Configurar outro grupo de projetos?", default=False
        ).ask():
            break
        profile = _ask_context(
            agents, list(profiles) + [p.name for p in new_profiles], dry_run=dry_run
        )
        if profile is not None:
            new_profiles.append(profile)
        elif new_profiles:
            break
        elif not questionary.confirm("Tentar novamente?", default=True).ask():
            break

    if not new_profiles:
        console.print("[yellow]Nenhum contexto configurado.[/yellow]")
        return

    # Passo 4: repos soltos — fora das raízes dos perfis — podem ser adotados
    _adopt_loose_repos(list(profiles.values()) + new_profiles)

    # Passo 5: resumo + confirmação única
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
