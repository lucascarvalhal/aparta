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


# ---- isolated mode ----

ISOLATED = Profile(
    name="acme",
    root="~/acme",
    git_email="a@b.c",
    gcloud_account="a@b.c",
    gcloud_project="acme-prod",
    gcloud_isolated=True,
)


def _fake_global_gcloud(tmp_path):
    """A global config dir with credentials, configurations, logs and cache."""
    source = tmp_path / "gcloud"
    (source / "configurations").mkdir(parents=True)
    (source / "logs" / "2026").mkdir(parents=True)
    (source / "cache").mkdir()
    (source / "credentials.db").write_text("creds")
    (source / "access_tokens.db").write_text("tokens")
    (source / "application_default_credentials.json").write_text('{"type": "authorized_user"}')
    (source / "configurations" / "config_default").write_text("[core]\naccount = a@b.c\n")
    (source / "logs" / "2026" / "run.log").write_text("x" * 1000)
    (source / "cache" / "blob").write_text("y" * 1000)
    return source


def test_seed_copies_credentials_but_never_the_shared_adc(tmp_path):
    from aparta.backends.gcloud import seed_isolated_dir

    source = _fake_global_gcloud(tmp_path)
    target = tmp_path / "gcloud-acme"
    assert seed_isolated_dir(target, source) is True

    assert (target / "credentials.db").read_text() == "creds"
    assert not (target / "access_tokens.db").exists()  # cache, gcloud re-mints it
    # the global ADC belongs to whoever logged in last, so it must not be
    # handed to a profile: no credentials beats the wrong credentials
    assert not (target / "application_default_credentials.json").exists()
    assert (target / "configurations" / "config_default").exists()
    # the heavy, disposable parts stay behind
    assert not (target / "logs").exists()
    assert not (target / "cache").exists()


def test_seed_never_touches_an_existing_dir(tmp_path):
    from aparta.backends.gcloud import seed_isolated_dir

    source = _fake_global_gcloud(tmp_path)
    target = tmp_path / "gcloud-acme"
    target.mkdir()
    (target / "credentials.db").write_text("mine")
    assert seed_isolated_dir(target, source) is False
    assert (target / "credentials.db").read_text() == "mine"


def test_isolated_apply_runs_inside_the_profile_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(gcloud, "gcloud_home", lambda config_root=None: _fake_global_gcloud(tmp_path))
    calls = []

    def fake_run(args, env=None, capture_output=True, text=True, timeout=None):
        calls.append((args, (env or {}).get("CLOUDSDK_CONFIG", "")))
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(gcloud.subprocess, "run", fake_run)
    notes = gcloud.apply_gcloud(ISOLATED, SafeWriter())

    target = str(tmp_path / "gcloud-acme")
    assert (tmp_path / "gcloud-acme" / "credentials.db").exists()
    # every command ran against the profile's own dir, never the global one
    assert calls and all(cfg == target for _args, cfg in calls)
    assert any("set" in a and "account" in a for a, _ in calls)
    assert notes[-1].level == "info"


def test_isolated_dry_run_creates_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    def explode(*a, **kw):  # pragma: no cover - must not be called
        raise AssertionError("no subprocess in dry-run")

    monkeypatch.setattr(gcloud.subprocess, "run", explode)
    notes = gcloud.apply_gcloud(ISOLATED, SafeWriter(dry_run=True))
    assert not (tmp_path / "gcloud-acme").exists()
    assert any("--dry-run" in n.text for n in notes)


def test_seed_prunes_other_accounts_from_the_credential_store(tmp_path):
    import sqlite3

    from aparta.backends.gcloud import seed_isolated_dir

    source = _fake_global_gcloud(tmp_path)
    db = source / "credentials.db"
    db.unlink()
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE credentials (account_id TEXT PRIMARY KEY, value BLOB)")
        conn.executemany(
            "INSERT INTO credentials VALUES (?, ?)",
            [("a@b.c", b"mine"), ("other@client.com", b"theirs")],
        )

    target = tmp_path / "gcloud-acme"
    seed_isolated_dir(target, source, keep_account="a@b.c")

    with sqlite3.connect(target / "credentials.db") as conn:
        accounts = [row[0] for row in conn.execute("SELECT account_id FROM credentials")]
    assert accounts == ["a@b.c"]
    # the global store is never touched
    with sqlite3.connect(db) as conn:
        assert len(list(conn.execute("SELECT account_id FROM credentials"))) == 2


def test_isolated_env_points_sdks_at_the_profile_adc(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    profile = Profile(
        name="acme", root="~/a", git_email="a@b.c", gcloud_account="a@b.c", gcloud_isolated=True
    )
    # no ADC file yet: nothing to point at, so the variable stays out
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in profile.env()

    adc = tmp_path / "gcloud-acme" / "application_default_credentials.json"
    adc.parent.mkdir(parents=True)
    adc.write_text("{}")
    env = profile.env()
    assert env["GOOGLE_APPLICATION_CREDENTIALS"] == str(adc)
    assert env["CLOUDSDK_CORE_DISABLE_FILE_LOGGING"] == "1"


def test_has_adc_reports_the_profile_own_credentials(tmp_path):
    from aparta.backends.gcloud import has_adc

    assert has_adc(tmp_path) is False
    (tmp_path / "application_default_credentials.json").write_text("{}")
    assert has_adc(tmp_path) is True
