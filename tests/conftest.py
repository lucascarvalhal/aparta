"""Deterministic test environment: canonical English, no update checks, and
none of the variables the aparta shell hook exports into a developer's
terminal (a GIT_CONFIG_* include from the real workspace would override every
temporary gitconfig the tests build)."""

import os

import pytest


@pytest.fixture(autouse=True)
def english_ui(monkeypatch):
    monkeypatch.setenv("APARTA_LANG", "en")
    monkeypatch.setenv("APARTA_UPDATES", "off")
    for key in list(os.environ):
        if key.startswith(("GIT_CONFIG_", "APARTA_WORKSPACE", "APARTA_PROFILE", "APARTA_PROVIDERS")):
            monkeypatch.delenv(key, raising=False)
