"""Deterministic test environment: English, no update checks, no shell-hook variables."""

import os

import pytest


@pytest.fixture(autouse=True)
def english_ui(monkeypatch):
    monkeypatch.setenv("APARTA_LANG", "en")
    monkeypatch.setenv("APARTA_UPDATES", "off")
    for key in list(os.environ):
        if key.startswith(("GIT_CONFIG_", "APARTA_WORKSPACE", "APARTA_PROFILE", "APARTA_PROVIDERS")):
            monkeypatch.delenv(key, raising=False)
