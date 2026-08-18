"""Backend git: gitconfig por contexto + includeIf no ~/.gitconfig (merge, nunca substitui)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from rich.console import Console

from ..fsutil import SafeWriter
from ..profiles import Profile

console = Console()


def context_gitconfig_path(profile: Profile, home: Path) -> Path:
    return home / f".gitconfig-{profile.name}"


def render_context_gitconfig(profile: Profile) -> str:
    """Gera o conteúdo de ~/.gitconfig-<contexto>."""
    lines = ["# Gerado pelo aparta — perfil: " + profile.name, "[user]"]
    if profile.git_name:
        lines.append(f"\tname = {profile.git_name}")
    lines.append(f"\temail = {profile.git_email}")
    if profile.ssh_key:
        key = profile.ssh_key
        lines += [
            "[core]",
            f'\tsshCommand = ssh -i {key} -o IdentitiesOnly=yes',
        ]
    if profile.ssh_alias:
        lines += [
            f'[url "git@{profile.ssh_alias}:"]',
            "\tinsteadOf = https://github.com/",
            "\tinsteadOf = git@github.com:",
        ]
    return "\n".join(lines) + "\n"


def gitdir_pattern(profile: Profile) -> str:
    """Padrão gitdir com ~ preservado quando a raiz está sob a home."""
    root = str(profile.root_path)
    home = str(Path.home())
    if root.startswith(home):
        root = "~" + root[len(home):]
    if not root.endswith("/"):
        root += "/"
    return root


def render_includeif_block(gitdir: str, include_path: str) -> str:
    return f'[includeIf "gitdir:{gitdir}"]\n\tpath = {include_path}\n'


def has_includeif(gitconfig_text: str, gitdir: str) -> bool:
    """True se já existe um bloco includeIf para este gitdir."""
    pattern = re.compile(
        r'\[includeIf\s+"gitdir:' + re.escape(gitdir) + r'"\]', re.IGNORECASE
    )
    return bool(pattern.search(gitconfig_text))


def merge_includeif(gitconfig_text: str, gitdir: str, include_path: str) -> str:
    """Adiciona o bloco includeIf apenas se ausente; preserva todo o resto."""
    if has_includeif(gitconfig_text, gitdir):
        return gitconfig_text
    block = render_includeif_block(gitdir, include_path)
    if gitconfig_text and not gitconfig_text.endswith("\n"):
        gitconfig_text += "\n"
    sep = "\n" if gitconfig_text else ""
    return gitconfig_text + sep + block


def apply_git(profile: Profile, writer: SafeWriter, home: Path | None = None) -> None:
    """Escreve ~/.gitconfig-<contexto> e faz merge do includeIf no ~/.gitconfig."""
    home = home or Path.home()
    ctx_path = context_gitconfig_path(profile, home)
    writer.write_text(ctx_path, render_context_gitconfig(profile))

    gitconfig = home / ".gitconfig"
    existing = gitconfig.read_text() if gitconfig.exists() else ""
    include_path = str(ctx_path)
    if include_path.startswith(str(home)):
        include_path = "~" + include_path[len(str(home)):]
    merged = merge_includeif(existing, gitdir_pattern(profile), include_path)
    if merged != existing:
        writer.write_text(gitconfig, merged)

    apply_adopted_git(profile, writer, home)


def apply_adopted_git(profile: Profile, writer: SafeWriter, home: Path | None = None) -> None:
    """Repos adotados (fora da raiz): o .git/config local passa a incluir o
    ~/.gitconfig-<perfil>, herdando e-mail/chave/insteadOf sem mover a pasta."""
    if not profile.adopted_repos:
        return
    home = home or Path.home()
    include = str(context_gitconfig_path(profile, home))
    for raw in profile.adopted_repos:
        repo = Path(raw).expanduser()
        if not (repo / ".git").exists():
            console.print(f"[yellow]aviso:[/yellow] {repo} não é um repositório git; pulando.")
            continue
        current = subprocess.run(
            ["git", "-C", str(repo), "config", "--local", "--get-all", "include.path"],
            capture_output=True,
            text=True,
        )
        if include in current.stdout.splitlines():
            continue  # já adotado
        if writer.dry_run:
            console.print(
                f"[yellow]--dry-run[/yellow] git -C {repo} config --local --add include.path {include}"
            )
            continue
        r = subprocess.run(
            ["git", "-C", str(repo), "config", "--local", "--add", "include.path", include],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            console.print(f"[red]adoção de {repo} falhou:[/red] {r.stderr.strip()}")
        else:
            console.print(f"[green]git:[/green] {repo.name} adotado pelo perfil '{profile.name}'")
