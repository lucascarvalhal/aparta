"""Language resolution: env override, saved choice, locale fallback."""

from __future__ import annotations

import pytest

from aparta import i18n


@pytest.fixture(autouse=True)
def clean_lang_env(tmp_path, monkeypatch):
    for var in ("APARTA_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("APARTA_CONFIG_DIR", str(tmp_path / "cfg"))
    i18n._saved_cache = None
    yield
    i18n._saved_cache = None


def test_defaults_to_english():
    assert i18n.resolve_lang() == "en"


def test_locale_selects_portuguese(monkeypatch):
    monkeypatch.setenv("LANG", "pt_BR.UTF-8")
    assert i18n.resolve_lang() == "pt"


def test_saved_choice_beats_locale(monkeypatch):
    monkeypatch.setenv("LANG", "pt_BR.UTF-8")
    i18n.set_language("en")
    assert i18n.resolve_lang() == "en"


def test_env_beats_saved_choice(monkeypatch):
    i18n.set_language("pt")
    monkeypatch.setenv("APARTA_LANG", "en")
    assert i18n.resolve_lang() == "en"


def test_set_language_persists(tmp_path, monkeypatch):
    i18n.set_language("pt")
    i18n._saved_cache = None
    assert i18n.saved_language() == "pt"
    assert i18n.resolve_lang() == "pt"


def test_garbage_in_language_file_is_ignored(tmp_path, monkeypatch):
    from aparta.config import config_dir

    config_dir().mkdir(parents=True, exist_ok=True)
    (config_dir() / "language").write_text("klingon\n")
    assert i18n.saved_language() == ""
    assert i18n.resolve_lang() == "en"


def test_translation_lookup(monkeypatch):
    monkeypatch.setenv("APARTA_LANG", "pt")
    assert i18n._("Cancel") == "Cancelar"
    monkeypatch.setenv("APARTA_LANG", "en")
    assert i18n._("Cancel") == "Cancel"


def test_wizard_language_question_skipped_when_saved(monkeypatch):
    from aparta import wizard

    i18n.set_language("en")
    assert wizard._ask_language() is True


def test_every_catalog_entry_keeps_its_placeholders():
    import re

    for key, value in i18n.catalog("pt").items():
        assert set(re.findall(r"{(\w+)}", key)) == set(re.findall(r"{(\w+)}", value)), key


def test_unknown_language_has_an_empty_catalog():
    assert i18n.catalog("klingon") == {}


def test_every_source_string_has_a_translation():
    import ast
    from pathlib import Path

    missing = set()
    for path in Path("src/aparta").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            is_call = isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_"
            if is_call and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                if node.args[0].value not in i18n.catalog("pt"):
                    missing.add(node.args[0].value)
    assert not missing, sorted(missing)
