"""gcloud backend: named configuration creation and dry-run."""

from __future__ import annotations

import subprocess

from aparta.backends import gcloud
from aparta.fsutil import SafeWriter
from aparta.profiles import Profile

PROFILE = Profile(
    name="acme",
    root="~/acme",
    git_email="a@b.c",
    gcloud_account="a@b.c",
    gcloud_project="acme-prod",
)


def _recorder(calls, describe_rc=1, create_rc=0):
    def run(args, env=None, capture_output=True, text=True, timeout=None):
        calls.append((args, (env or {}).get("CLOUDSDK_ACTIVE_CONFIG_NAME", "")))
        if "describe" in args:
            return subprocess.CompletedProcess(args, describe_rc, stdout="", stderr="")
        if "create" in args:
            return subprocess.CompletedProcess(args, create_rc, stdout="", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    return run


def test_apply_gcloud_creates_missing_configuration(monkeypatch):
    calls = []
    monkeypatch.setattr(gcloud.subprocess, "run", _recorder(calls, describe_rc=1))
    gcloud.apply_gcloud(PROFILE, SafeWriter())
    commands = [" ".join(a) for a, _ in calls]
    assert any("configurations describe acme" in c for c in commands)
    assert any("configurations create acme --no-activate" in c for c in commands)
    # account and project set inside the named configuration
    set_calls = [(a, cfg) for a, cfg in calls if "set" in a]
    assert all(cfg == "acme" for _, cfg in set_calls)
    assert len(set_calls) == 2


def test_apply_gcloud_skips_create_when_configuration_exists(monkeypatch):
    calls = []
    monkeypatch.setattr(gcloud.subprocess, "run", _recorder(calls, describe_rc=0))
    gcloud.apply_gcloud(PROFILE, SafeWriter())
    commands = [" ".join(a) for a, _ in calls]
    assert not any("configurations create" in c for c in commands)


def test_apply_gcloud_dry_run_runs_nothing_but_describe(monkeypatch):
    calls = []
    monkeypatch.setattr(gcloud.subprocess, "run", _recorder(calls))
    gcloud.apply_gcloud(PROFILE, SafeWriter(dry_run=True))
    assert calls == []


def test_apply_gcloud_without_account_is_noop(monkeypatch):
    def explode(*a, **kw):  # pragma: no cover - must not be called
        raise AssertionError("no subprocess expected")

    monkeypatch.setattr(gcloud.subprocess, "run", explode)
    gcloud.apply_gcloud(Profile(name="x", root="~/x", git_email="a@b.c"), SafeWriter())
