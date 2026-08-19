"""Deterministic test language: canonical English regardless of the host locale."""

import pytest


@pytest.fixture(autouse=True)
def english_ui(monkeypatch):
    monkeypatch.setenv("APARTA_LANG", "en")
    monkeypatch.setenv("APARTA_UPDATES", "off")
