"""Helpers de descoberta do wizard: chaves SSH e parsing de contas gh."""

from pathlib import Path

from aparta.wizard import list_ssh_host_aliases, list_ssh_keys, parse_gh_accounts

SSH_CONFIG = """\
Host *
    AddKeysToAgent yes

Host github.com-pessoal
    HostName github.com
    IdentityFile ~/.ssh/github_pessoal

Host github.com-eneva
    HostName github.com
    IdentityFile ~/.ssh/id_ed25519_eneva

Host meu-servidor
    HostName 10.0.0.5
    User root

# alias == hostname não é apelido
Host github.com
    IdentityFile ~/.ssh/id_ed25519
"""


def test_list_ssh_host_aliases(tmp_path: Path):
    config = tmp_path / "config"
    config.write_text(SSH_CONFIG)
    aliases = list_ssh_host_aliases(config)
    assert [a["alias"] for a in aliases] == [
        "github.com-pessoal",
        "github.com-eneva",
        "meu-servidor",
    ]
    assert aliases[0]["hostname"] == "github.com"
    assert aliases[0]["identity"] == "~/.ssh/github_pessoal"
    assert aliases[2]["identity"] == ""  # sem IdentityFile


def test_list_ssh_host_aliases_sem_config(tmp_path: Path):
    assert list_ssh_host_aliases(tmp_path / "nao-existe") == []


def test_list_ssh_keys_pairs_only(tmp_path: Path):
    (tmp_path / "id_ed25519_pessoal").write_text("PRIVATE")
    (tmp_path / "id_ed25519_pessoal.pub").write_text("PUB")
    (tmp_path / "id_rsa_trabalho").write_text("PRIVATE")
    (tmp_path / "id_rsa_trabalho.pub").write_text("PUB")
    (tmp_path / "known_hosts").write_text("...")
    (tmp_path / "orfao.pub").write_text("PUB sem chave privada")

    keys = list_ssh_keys(tmp_path)
    assert keys == [
        str(tmp_path / "id_ed25519_pessoal"),
        str(tmp_path / "id_rsa_trabalho"),
    ]


def test_list_ssh_keys_missing_dir(tmp_path: Path):
    assert list_ssh_keys(tmp_path / "nao-existe") == []


def test_parse_gh_accounts_multiple():
    output = """
github.com
  ✓ Logged in to github.com account lucas-pessoal (keyring)
  - Active account: true
  ✓ Logged in to github.com account lucas-trabalho (keyring)
  - Active account: false
"""
    assert parse_gh_accounts(output) == ["lucas-pessoal", "lucas-trabalho"]


def test_parse_gh_accounts_empty():
    assert parse_gh_accounts("You are not logged into any GitHub hosts.") == []
