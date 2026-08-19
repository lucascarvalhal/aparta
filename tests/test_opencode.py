"""opencode adapter: shell.env plugin generation, merge and validation."""

from __future__ import annotations

from pathlib import Path

from aparta.agents.opencode import OpencodeAdapter, parse_plugin_env, render_plugin
from aparta.fsutil import SafeWriter

ENV = {"GH_CONFIG_DIR": "/home/ana/.config/gh-acme", "CLOUDSDK_ACTIVE_CONFIG_NAME": "acme"}


def test_render_and_parse_roundtrip():
    text = render_plugin(ENV)
    assert '"shell.env"' in text
    assert parse_plugin_env(text) == ENV


def test_inject_creates_plugin_and_validates(tmp_path: Path):
    adapter = OpencodeAdapter()
    assert adapter.inject(tmp_path, ENV, SafeWriter()) is True
    assert adapter.validate(tmp_path, ENV) == (True, "env ok")
    assert adapter.read_env(tmp_path) == ENV


def test_inject_merges_with_existing_vars(tmp_path: Path):
    adapter = OpencodeAdapter()
    adapter.inject(tmp_path, {"KEEP_ME": "yes"}, SafeWriter())
    adapter.inject(tmp_path, ENV, SafeWriter())
    merged = adapter.read_env(tmp_path)
    assert merged["KEEP_ME"] == "yes"
    assert merged["GH_CONFIG_DIR"] == ENV["GH_CONFIG_DIR"]


def test_validate_reports_missing(tmp_path: Path):
    adapter = OpencodeAdapter()
    adapter.inject(tmp_path, {"OTHER": "x"}, SafeWriter())
    ok, msg = adapter.validate(tmp_path, ENV)
    assert ok is False and "GH_CONFIG_DIR" in msg


def test_value_quotes_are_escaped():
    text = render_plugin({"K": 'a"b'})
    assert 'output.env["K"] = "a\\"b";' in text


def test_registered_in_registry():
    from aparta.agents import ADAPTERS

    assert "opencode" in ADAPTERS
