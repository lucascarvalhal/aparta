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
    i18n._saved_cache = None  # force a re-read from disk
    assert i18n.saved_language() == "pt"
    assert i18n.resolve_lang() == "pt"


def test_garbage_in_language_file_is_ignored(tmp_path, monkeypatch):
    from aparta.profiles import config_dir

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
    # would raise if it tried to prompt: no questionary patched
    assert wizard._ask_language() is True
