"""Profile removal: undoing gitconfig, includeIf, gh dir and agent env."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from aparta.agents.claude_code import ClaudeCodeAdapter
from aparta.agents.direnv import DirenvAdapter
from aparta.backends.git import remove_includeif
from aparta.fsutil import SafeWriter
from aparta.profiles import Profile
from aparta.remove import remove_profile

GITCONFIG = (
    "[user]\n\temail = base@x.com\n"
    '[includeIf "gitdir:~/work/"]\n\tpath = ~/.gitconfig-work\n'
    '[includeIf "gitdir:~/other/"]\n\tpath = ~/.gitconfig-other\n'
)


def test_remove_includeif_drops_only_the_target_block():
    out = remove_includeif(GITCONFIG, "~/work/")
    assert "gitdir:~/work/" not in out
    assert "gitdir:~/other/" in out
    assert "email = base@x.com" in out


def test_safewriter_remove_file_keeps_backup(tmp_path: Path):
    f = tmp_path / "config"
    f.write_text("data")
    assert SafeWriter().remove_file(f) is True
    assert not f.exists()
    backups = list(tmp_path.glob("config.bak-aparta-*"))
    assert len(backups) == 1 and backups[0].read_text() == "data"


def test_safewriter_remove_dir_renames_to_backup(tmp_path: Path):
    d = tmp_path / "gh-x"
    d.mkdir()
    (d / "hosts.yml").write_text("x")
    assert SafeWriter().remove_dir(d) is True
    assert not d.exists()
    assert list(tmp_path.glob("gh-x.bak-aparta-*"))


def test_safewriter_remove_dry_run_touches_nothing(tmp_path: Path):
    f = tmp_path / "config"
    f.write_text("data")
    w = SafeWriter(dry_run=True)
    assert w.remove_file(f) is True
    assert f.exists() and not list(tmp_path.glob("*.bak-aparta-*"))


def test_adapters_remove_env(tmp_path: Path):
    claude = ClaudeCodeAdapter()
    claude.inject(tmp_path, {"GH_CONFIG_DIR": "/x", "OTHER": "keep"}, SafeWriter())
    assert claude.remove_env(tmp_path, ["GH_CONFIG_DIR"], SafeWriter()) is True
    env = json.loads((tmp_path / ".claude" / "settings.local.json").read_text())["env"]
    assert env == {"OTHER": "keep"}

    direnv = DirenvAdapter()
    direnv.inject(tmp_path, {"GH_CONFIG_DIR": "/x", "OTHER": "keep"}, SafeWriter())
    assert direnv.remove_env(tmp_path, ["GH_CONFIG_DIR"], SafeWriter()) is True
    text = (tmp_path / ".envrc").read_text()
    assert "GH_CONFIG_DIR" not in text and "OTHER" in text


def test_remove_profile_end_to_end(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    repo = tmp_path / "work" / "app"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)

    profile = Profile(
        name="acme",
        root=str(tmp_path / "work"),
        git_email="a@b.c",
        gh_user="someone",
        agents=["claude-code"],
    )

    from aparta.apply import apply_profile

    monkeypatch.setattr("aparta.apply.BACKENDS", [])
    apply_profile(profile, SafeWriter())
    (tmp_path / ".gitconfig").write_text(
        '[includeIf "gitdir:~/work/"]\n\tpath = ~/.gitconfig-acme\n'
    )
    (tmp_path / ".gitconfig-acme").write_text("[user]\n\temail = a@b.c\n")
    gh_dir = tmp_path / ".config" / "gh-acme"
    gh_dir.mkdir(parents=True)

    remove_profile(profile, SafeWriter(), home=tmp_path)

    assert "includeIf" not in (tmp_path / ".gitconfig").read_text()
    assert not (tmp_path / ".gitconfig-acme").exists()
    assert not gh_dir.exists()
    env = json.loads((repo / ".claude" / "settings.local.json").read_text())["env"]
    assert "GH_CONFIG_DIR" not in env
