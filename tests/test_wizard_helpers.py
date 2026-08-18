"""Helpers de descoberta do wizard: chaves SSH e parsing de contas gh."""

from pathlib import Path

from aparta.wizard import list_ssh_keys, parse_gh_accounts


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
