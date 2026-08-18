"""Fluxo `aparta` sem argumentos: wizard na primeira execução, menu depois."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from aparta import cli
from aparta.cli import app, default_action

runner = CliRunner()


def test_default_action_without_profiles(tmp_path: Path):
    assert default_action(tmp_path / "profiles.toml") == "wizard"


def test_default_action_with_profiles(tmp_path: Path):
    f = tmp_path / "profiles.toml"
    f.write_text("[profiles.pessoal]\nroot = '~/p'\ngit_email = 'a@b.c'\n")
    assert default_action(f) == "menu"


@pytest.fixture()
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("APARTA_CONFIG_DIR", str(tmp_path / "cfg"))
    return tmp_path / "cfg"


def test_no_args_first_run_routes_to_wizard(isolated_config, monkeypatch):
    called = {}
    monkeypatch.setattr(cli, "_run_wizard", lambda: called.setdefault("wizard", True))
    monkeypatch.setattr(cli, "_run_menu", lambda: called.setdefault("menu", True))
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert called == {"wizard": True}


def test_no_args_with_profiles_routes_to_menu(isolated_config, monkeypatch):
    isolated_config.mkdir(parents=True)
    (isolated_config / "profiles.toml").write_text(
        "[profiles.pessoal]\nroot = '~/p'\ngit_email = 'a@b.c'\n"
    )
    called = {}
    monkeypatch.setattr(cli, "_run_wizard", lambda: called.setdefault("wizard", True))
    monkeypatch.setattr(cli, "_run_menu", lambda: called.setdefault("menu", True))
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert called == {"menu": True}


def test_subcommand_does_not_trigger_wizard(isolated_config, monkeypatch):
    monkeypatch.setattr(cli, "_run_wizard", lambda: pytest.fail("wizard não deveria rodar"))
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "Nenhum perfil" in result.output


def test_version_flag(isolated_config):
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "aparta" in result.output
