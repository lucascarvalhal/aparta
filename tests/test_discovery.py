"""Testes da descoberta automática de contextos (discovery.py)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from aparta.discovery import (
    ContextSuggestion,
    discover,
    find_repos,
    parse_includeifs,
    read_agent_env,
    suggestions_from_gitconfig,
)

GITCONFIG = """\
[user]
    email = default@example.com
[includeIf "gitdir:~/pessoal/"]
    path = ~/.gitconfig-pessoal
[includeIf "gitdir:~/projects/effektra/"]
    path = .gitconfig-effektra
[core]
    editor = vim
"""


def _make_repo(path: Path, email: str = "") -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    if email:
        subprocess.run(
            ["git", "-C", str(path), "config", "user.email", email], check=True
        )
    return path


def test_parse_includeifs():
    pairs = parse_includeifs(GITCONFIG)
    assert pairs == [
        ("~/pessoal/", "~/.gitconfig-pessoal"),
        ("~/projects/effektra/", ".gitconfig-effektra"),
    ]


def test_parse_includeifs_ignora_sem_path():
    text = '[includeIf "gitdir:~/x/"]\n[user]\n    email = a@b.c\n'
    assert parse_includeifs(text) == []


def test_suggestions_from_gitconfig(tmp_path: Path):
    gitconfig = tmp_path / ".gitconfig"
    gitconfig.write_text(
        '[includeIf "gitdir:~/pessoal/"]\n    path = .gitconfig-pessoal\n'
    )
    (tmp_path / ".gitconfig-pessoal").write_text(
        "[user]\n    email = eu@gmail.com\n"
    )
    suggestions = suggestions_from_gitconfig(gitconfig)
    assert len(suggestions) == 1
    s = suggestions[0]
    assert s.name == "pessoal"
    assert s.git_email == "eu@gmail.com"
    assert s.source == "gitconfig"


def test_suggestions_from_gitconfig_inexistente(tmp_path: Path):
    assert suggestions_from_gitconfig(tmp_path / "nao-existe") == []


def test_find_repos_pula_pastas_pesadas(tmp_path: Path):
    _make_repo(tmp_path / "app")
    escondido = tmp_path / "node_modules" / "dep"
    escondido.mkdir(parents=True)
    (escondido / ".git").mkdir()
    repos = find_repos(tmp_path)
    assert [r.name for r in repos] == ["app"]


def test_read_agent_env(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "settings.local.json").write_text(
        '{"env": {"GH_CONFIG_DIR": "/home/x/.config/gh-pessoal"}}'
    )
    (repo / ".envrc").write_text('export CLOUDSDK_ACTIVE_CONFIG_NAME="pessoal"\n')
    env = read_agent_env(repo)
    assert env["GH_CONFIG_DIR"].endswith("gh-pessoal")
    assert env["CLOUDSDK_ACTIVE_CONFIG_NAME"] == "pessoal"


def test_read_agent_env_json_invalido(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "settings.local.json").write_text("{quebrado")
    assert read_agent_env(repo) == {}


def test_discover_agrupa_por_pasta_mae(tmp_path: Path):
    pessoal = tmp_path / "pessoal"
    _make_repo(pessoal / "blog", "eu@gmail.com")
    _make_repo(pessoal / "cli", "eu@gmail.com")
    _make_repo(tmp_path / "projects" / "acme" / "api", "eu@acme.com")

    suggestions = discover(
        scan_roots=[str(pessoal), str(tmp_path / "projects")],
        gitconfig=tmp_path / "sem-gitconfig",
        config_root=tmp_path / "config-vazio",
    )
    by_name = {s.name: s for s in suggestions}
    assert by_name["pessoal"].repo_count == 2
    assert by_name["pessoal"].git_email == "eu@gmail.com"
    assert by_name["acme"].repo_count == 1
    assert by_name["acme"].git_email == "eu@acme.com"
    # mais repos primeiro
    assert suggestions[0].name == "pessoal"


def test_discover_mescla_gitconfig_com_varredura(tmp_path: Path):
    pessoal = tmp_path / "pessoal"
    _make_repo(pessoal / "blog", "eu@gmail.com")
    gitconfig = tmp_path / ".gitconfig"
    gitconfig.write_text(
        f'[includeIf "gitdir:{pessoal}/"]\n    path = .gitconfig-pessoal\n'
    )
    (tmp_path / ".gitconfig-pessoal").write_text("[user]\n    email = fixo@gmail.com\n")

    suggestions = discover(
        scan_roots=[str(pessoal)], gitconfig=gitconfig, config_root=tmp_path / "config-vazio"
    )
    assert len(suggestions) == 1
    s = suggestions[0]
    assert s.source == "gitconfig"  # sinal mais forte prevalece
    assert s.git_email == "fixo@gmail.com"
    assert s.repo_count == 1  # enriquecido pela varredura


def test_suggestion_dataclass_defaults():
    s = ContextSuggestion(name="x", root="~/x")
    assert s.repo_count == 0 and s.source == "repos"


def test_suggestions_from_gitconfig_extrai_ssh_key(tmp_path: Path):
    gitconfig = tmp_path / ".gitconfig"
    gitconfig.write_text('[includeIf "gitdir:~/eneva/"]\n    path = .gitconfig-eneva\n')
    (tmp_path / ".gitconfig-eneva").write_text(
        "[user]\n    email = a@eneva.com\n"
        "[core]\n    sshCommand = ssh -i ~/.ssh/id_ed25519_eneva -o IdentitiesOnly=yes\n"
    )
    s = suggestions_from_gitconfig(gitconfig)[0]
    assert s.ssh_key == "~/.ssh/id_ed25519_eneva"


def test_suggestions_from_gitconfig_extrai_ssh_alias(tmp_path: Path):
    gitconfig = tmp_path / ".gitconfig"
    gitconfig.write_text('[includeIf "gitdir:~/pessoal/"]\n    path = .gitconfig-pessoal\n')
    (tmp_path / ".gitconfig-pessoal").write_text(
        "[user]\n    email = eu@gmail.com\n"
        '[url "git@github.com-pessoal:"]\n'
        "    insteadOf = https://github.com/\n"
    )
    s = suggestions_from_gitconfig(gitconfig)[0]
    assert s.ssh_alias == "github.com-pessoal"


def test_gh_user_from_config_dir(tmp_path: Path):
    from aparta.discovery import gh_user_from_config_dir

    gh_dir = tmp_path / "gh-pessoal"
    gh_dir.mkdir()
    (gh_dir / "hosts.yml").write_text(
        "github.com:\n    users:\n        fulano:\n    user: fulano\n"
    )
    assert gh_user_from_config_dir("gh-pessoal", tmp_path) == "fulano"
    assert gh_user_from_config_dir("gh-inexistente", tmp_path) == ""


def test_gcloud_account_from_config(tmp_path: Path):
    from aparta.discovery import gcloud_account_from_config

    (tmp_path / "configurations").mkdir(parents=True)
    (tmp_path / "configurations" / "config_eneva").write_text(
        "[core]\naccount = lucas@sysmanager.com.br\nproject = data-lake\n"
    )
    assert gcloud_account_from_config("eneva", tmp_path) == "lucas@sysmanager.com.br"
    assert gcloud_account_from_config("nada", tmp_path) == ""


def test_discover_enriquece_contas_por_convencao(tmp_path: Path):
    """Sugestão 'pessoal' acha gh-pessoal e config_pessoal pela convenção de nomes."""
    pessoal = tmp_path / "pessoal"
    _make_repo(pessoal / "blog", "eu@gmail.com")
    config_root = tmp_path / ".config"
    gh_dir = config_root / "gh-pessoal"
    gh_dir.mkdir(parents=True)
    (gh_dir / "hosts.yml").write_text("github.com:\n    user: lucascarvalhal\n")
    (config_root / "gcloud" / "configurations").mkdir(parents=True)
    (config_root / "gcloud" / "configurations" / "config_pessoal").write_text(
        "[core]\naccount = eu@gmail.com\n"
    )

    s = discover(
        scan_roots=[str(pessoal)],
        gitconfig=tmp_path / "sem-gitconfig",
        config_root=config_root,
    )[0]
    assert s.gh_user == "lucascarvalhal"
    assert s.gcloud_account == "eu@gmail.com"
