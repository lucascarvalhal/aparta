"""Credential probes: four honest states, silent refresh and caching."""

from __future__ import annotations

import subprocess

import pytest

from aparta import auth
from aparta.profiles import Profile

PROFILE = Profile(
    name="acme",
    root="~/acme",
    git_email="a@b.c",
    gh_user="ana-acme",
    gcloud_account="ana@acme.com",
)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("APARTA_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.delenv("APARTA_AUTH_CHECK", raising=False)


def _result(code: int, stdout: str = "", stderr: str = ""):
    def run(args, **kwargs):
        return subprocess.CompletedProcess(args, code, stdout=stdout, stderr=stderr)

    return run


def test_valid_credential_is_ok(monkeypatch):
    monkeypatch.setattr(auth.subprocess, "run", _result(0, stdout="ya29.token"))
    assert auth.check_gcloud(PROFILE).state == auth.OK


def test_probe_disables_prompts_so_it_never_hangs(monkeypatch):
    seen = {}

    def run(args, env=None, **kwargs):
        seen["prompts"] = (env or {}).get("CLOUDSDK_CORE_DISABLE_PROMPTS")
        seen["stdin"] = kwargs.get("stdin")
        return subprocess.CompletedProcess(args, 0, stdout="token", stderr="")

    monkeypatch.setattr(auth.subprocess, "run", run)
    auth.check_gcloud(PROFILE)
    assert seen["prompts"] == "1"
    assert seen["stdin"] == subprocess.DEVNULL


def test_expired_session_asks_for_a_human(monkeypatch):
    monkeypatch.setattr(
        auth.subprocess,
        "run",
        _result(1, stderr="Reauthentication failed. cannot prompt during non-interactive execution"),
    )
    status = auth.check_gcloud(PROFILE)
    assert status.state == auth.REAUTH
    assert status.needs_human is True


def test_revoked_credential_asks_for_a_human(monkeypatch):
    monkeypatch.setattr(
        auth.subprocess,
        "run",
        _result(1, stderr="invalid_grant: Token has been expired or revoked."),
    )
    assert auth.check_gcloud(PROFILE).state == auth.REAUTH


def test_missing_credential_is_its_own_state(monkeypatch):
    monkeypatch.setattr(
        auth.subprocess, "run", _result(1, stderr="You do not currently have an active account selected")
    )
    assert auth.check_gcloud(PROFILE).state == auth.MISSING


def test_network_failure_never_cries_wolf(monkeypatch):
    """A flaky connection must not be reported as an expired credential."""

    def timeout(args, **kwargs):
        raise subprocess.TimeoutExpired(args, 20)

    monkeypatch.setattr(auth.subprocess, "run", timeout)
    status = auth.check_gcloud(PROFILE)
    assert status.state == auth.UNKNOWN
    assert status.needs_human is False


def test_missing_binary_is_unknown_too(monkeypatch):
    def missing(args, **kwargs):
        raise FileNotFoundError(args[0])

    monkeypatch.setattr(auth.subprocess, "run", missing)
    assert auth.check_gcloud(PROFILE).state == auth.UNKNOWN


def test_github_sso_is_recognized(monkeypatch):
    monkeypatch.setattr(
        auth.subprocess,
        "run",
        _result(1, stderr="HTTP 403: Resource protected by organization SAML enforcement"),
    )
    status = auth.check_gh(PROFILE)
    assert status.state == auth.REAUTH
    assert "SSO" in status.detail or "sso" in status.detail.lower()


def test_providers_the_profile_does_not_use_are_skipped():
    bare = Profile(name="x", root="~/x", git_email="a@b.c")
    assert auth.check_gcloud(bare) is None
    assert auth.check_gh(bare) is None
    assert auth.check_profile(bare) == []


def test_check_is_cached(monkeypatch):
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="token", stderr="")

    monkeypatch.setattr(auth.subprocess, "run", run)
    auth.cached_check(PROFILE)
    first = len(calls)
    auth.cached_check(PROFILE)
    assert len(calls) == first  # second call served from cache
    auth.cached_check(PROFILE, force=True)
    assert len(calls) > first


def test_checks_can_be_turned_off(monkeypatch):
    monkeypatch.setenv("APARTA_AUTH_CHECK", "off")

    def explode(*a, **kw):  # pragma: no cover - must not be called
        raise AssertionError("no probe when checks are off")

    monkeypatch.setattr(auth.subprocess, "run", explode)
    assert auth.problems([PROFILE]) == []


def test_problems_lists_only_what_needs_a_human(monkeypatch):
    monkeypatch.setattr(auth, "check_profile", lambda p: [
        auth.AuthStatus("gcloud", auth.REAUTH, "session expired"),
        auth.AuthStatus("gh", auth.OK),
    ])
    found = auth.problems([PROFILE])
    assert [(name, s.provider) for name, s in found] == [("acme", "gcloud")]


def test_account_without_credentials_is_missing(monkeypatch):
    """The wording gcloud actually uses when the account has no credential."""
    monkeypatch.setattr(
        auth.subprocess,
        "run",
        _result(1, stderr="ERROR: Your current active account [x@y.com] does not have any valid credentials"),
    )
    assert auth.check_gcloud(PROFILE).state == auth.MISSING
