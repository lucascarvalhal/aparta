"""Extracted wizard steps, tested with the interactive helpers stubbed."""

from __future__ import annotations

from aparta import wizard
from aparta.backends import Note
from aparta.discovery import ContextSuggestion


def test_ask_ssh_uses_suggested_key(monkeypatch):
    captured = {}

    def fake_choose(question, options, sentinels=(), default=""):
        captured["default"] = default
        return default

    monkeypatch.setattr(wizard, "_choose_from", fake_choose)
    monkeypatch.setattr(wizard, "list_ssh_keys", lambda: ["/k/a", "/k/b"])
    monkeypatch.setattr(wizard, "_ask_ssh_alias", lambda key, suggested: "github.com-acme")

    s = ContextSuggestion(name="acme", root="~/acme", ssh_key="/k/b")
    key, alias, generated = wizard._ask_ssh("acme", s, dry_run=False)
    assert captured["default"] == "/k/b"
    assert (key, alias, generated) == ("/k/b", "github.com-acme", False)


def test_ask_ssh_generates_new_key(monkeypatch):
    monkeypatch.setattr(wizard, "_choose_from", lambda *a, **kw: wizard.NEW_SSH_KEY)
    monkeypatch.setattr(wizard, "list_ssh_keys", lambda: [])
    monkeypatch.setattr(wizard, "generate_ssh_key", lambda name, dry_run: "/new/key")
    monkeypatch.setattr(wizard, "_ask_ssh_alias", lambda key, suggested: "")

    key, alias, generated = wizard._ask_ssh("acme", None, dry_run=False)
    assert (key, generated) == ("/new/key", True)


def test_ask_gh_triggers_login_on_sentinel(monkeypatch):
    monkeypatch.setattr(wizard, "list_gh_accounts", lambda: [])
    monkeypatch.setattr(wizard, "_choose_from", lambda *a, **kw: wizard.NEW_GH_LOGIN)
    monkeypatch.setattr(wizard, "login_new_gh_account", lambda name, dry_run: "new-user")
    assert wizard._ask_gh("acme", None, dry_run=False) == "new-user"


def test_ask_gcloud_skip_means_no_project_prompt(monkeypatch):
    monkeypatch.setattr(wizard, "list_gcloud_accounts", lambda: ["a@b.c"])
    monkeypatch.setattr(wizard, "_choose_from", lambda *a, **kw: "")
    account, project, isolated = wizard._ask_gcloud("acme", None, dry_run=False)
    assert (account, project, isolated) == ("", "", False)


def test_ask_gcloud_offers_isolation_when_an_account_is_chosen(monkeypatch):
    monkeypatch.setattr(wizard, "list_gcloud_accounts", lambda: ["a@b.c"])
    monkeypatch.setattr(wizard, "_choose_from", lambda *a, **kw: "a@b.c")
    monkeypatch.setattr(wizard, "_confirm", lambda question, default=False: True)

    class FakeText:
        def __init__(self, *a, **kw):
            pass

        def ask(self):
            return "acme-prod"

    import questionary as q

    monkeypatch.setattr(q, "text", FakeText)
    account, project, isolated = wizard._ask_gcloud("acme", None, dry_run=False)
    assert (account, project, isolated) == ("a@b.c", "acme-prod", True)


def test_backends_return_notes_instead_of_printing(tmp_path, monkeypatch):
    from aparta.backends.gh import apply_gh
    from aparta.fsutil import SafeWriter
    from aparta.profiles import Profile

    profile = Profile(name="x", root="~/x", git_email="a@b.c", gh_user="u")
    notes = apply_gh(profile, SafeWriter(), home=tmp_path)
    assert len(notes) == 1
    assert isinstance(notes[0], Note)
    assert notes[0].level == "warn"
