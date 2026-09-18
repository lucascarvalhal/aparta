"""gitconfig merging: includeIf added only when absent, the rest preserved."""

import os
import subprocess
from pathlib import Path

from aparta.backends.git import (
    apply_git,
    has_includeif,
    merge_includeif,
    reconcile_workspace_git,
    render_context_gitconfig,
)
from aparta.fsutil import SafeWriter
from aparta.profiles import Profile
from aparta.workspaces import Workspace


def make_profile(**kw) -> Profile:
    base = dict(
        name="pessoal",
        root="~/pessoal",
        git_email="eu@example.com",
        ssh_key="~/.ssh/id_ed25519_pessoal",
        ssh_alias="github-pessoal",
    )
    base.update(kw)
    return Profile(**base)


def test_merge_adds_block_when_absent():
    existing = "[user]\n\temail = global@example.com\n"
    merged = merge_includeif(existing, "~/pessoal/", "~/.gitconfig-pessoal")
    assert existing.rstrip("\n") in merged
    assert '[includeIf "gitdir:~/pessoal/"]' in merged
    assert "path = ~/.gitconfig-pessoal" in merged


def test_merge_is_idempotent():
    merged = merge_includeif("", "~/pessoal/", "~/.gitconfig-pessoal")
    again = merge_includeif(merged, "~/pessoal/", "~/.gitconfig-pessoal")
    assert again == merged
    assert has_includeif(merged, "~/pessoal/")


def test_merge_preserves_other_includeifs():
    existing = '[includeIf "gitdir:~/trabalho/"]\n\tpath = ~/.gitconfig-trabalho\n'
    merged = merge_includeif(existing, "~/pessoal/", "~/.gitconfig-pessoal")
    assert "gitconfig-trabalho" in merged
    assert "gitconfig-pessoal" in merged


def test_render_context_gitconfig_contents():
    text = render_context_gitconfig(make_profile(git_name="Ana"))
    assert "email = eu@example.com" in text
    assert "name = Ana" in text
    assert "sshCommand = ssh -i ~/.ssh/id_ed25519_pessoal -o IdentitiesOnly=yes" in text
    assert '[url "git@github-pessoal:"]' in text
    assert "insteadOf = https://github.com/" in text


def test_apply_git_backs_up_existing_gitconfig(tmp_path: Path):
    home = tmp_path
    gitconfig = home / ".gitconfig"
    gitconfig.write_text("[user]\n\temail = global@example.com\n")

    profile = make_profile(root=str(tmp_path / "pessoal"))
    writer = SafeWriter(dry_run=False)
    apply_git(profile, writer, home=home)

    assert (home / ".gitconfig-pessoal").exists()
    assert "includeIf" in gitconfig.read_text()
    assert "global@example.com" in gitconfig.read_text()
    backups = list(home.glob(".gitconfig.bak-aparta-*"))
    assert len(backups) == 1
    assert backups[0].read_text() == "[user]\n\temail = global@example.com\n"


def test_render_gitconfig_uses_profile_git_host():
    from aparta.backends.git import render_context_gitconfig
    from aparta.profiles import Profile

    p = Profile(
        name="x",
        root="~/x",
        git_email="a@b.c",
        ssh_alias="gitlab.com-work",
        git_host="gitlab.com",
    )
    text = render_context_gitconfig(p)
    assert "insteadOf = https://gitlab.com/" in text
    assert "insteadOf = git@gitlab.com:" in text
    assert "github.com" not in text


def test_tilde_does_not_match_sibling_prefix(tmp_path, monkeypatch):
    from pathlib import Path

    from aparta.fsutil import tilde

    home = tmp_path / "luca"
    sibling = tmp_path / "lucax" / "repo"
    home.mkdir()
    sibling.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    assert tilde(sibling) == str(sibling)
    assert tilde(home / "repo") == "~/repo"


def test_linked_worktrees_resolve_distinct_git_and_ssh_profiles(tmp_path, monkeypatch):
    """A linked worktree's gitdir lives under the main checkout, not its path."""
    config_dir = tmp_path / "aparta-config"
    monkeypatch.setenv("APARTA_CONFIG_DIR", str(config_dir))
    home = tmp_path / "home"
    home.mkdir()
    (home / ".gitconfig").write_text(
        "[alias]\n\tco = checkout\n"
        "[user]\n\temail = global@example.com\n"
        '[url "git@github-personal:"]\n'
        "\tinsteadOf = https://github.com/\n"
    )

    main = tmp_path / "initech" / "trade"
    linked = tmp_path / "acme" / "trade-pr"
    main.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(main)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(main),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "--allow-empty",
            "-m",
            "base",
            "-q",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(main), "worktree", "add", "-q", "-b", "acme-pr", str(linked)],
        check=True,
    )

    initech = Profile(
        "initech",
        str(main.parent),
        "dev@initech.com",
        ssh_key="/keys/initech",
        ssh_alias="github-initech",
    )
    acme = Profile(
        "acme",
        str(linked.parent),
        "dev@acme.com",
        ssh_key="/keys/acme",
        ssh_alias="github-acme",
    )
    workspaces = {
        "initech-trade": Workspace(
            "initech-trade", str(main), initech.name, ["git", "ssh"]
        ),
        "acme-trade": Workspace(
            "acme-trade", str(linked), acme.name, ["git", "ssh"]
        ),
    }

    reconcile_workspace_git(
        {initech.name: initech, acme.name: acme},
        workspaces,
        SafeWriter(),
        home=home,
    )
    reconciled_once = (home / ".gitconfig").read_text()
    reconcile_workspace_git(
        {initech.name: initech, acme.name: acme},
        workspaces,
        SafeWriter(),
        home=home,
    )
    assert (home / ".gitconfig").read_text() == reconciled_once

    query_env = {**os.environ, "GIT_CONFIG_GLOBAL": str(home / ".gitconfig")}
    assert subprocess.run(
        ["git", "-C", str(main), "config", "user.email"],
        env=query_env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip() == "dev@initech.com"
    assert subprocess.run(
        ["git", "-C", str(linked), "config", "user.email"],
        env=query_env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip() == "dev@acme.com"
    assert "/keys/initech" in subprocess.run(
        ["git", "-C", str(main), "config", "core.sshCommand"],
        env=query_env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "/keys/acme" in subprocess.run(
        ["git", "-C", str(linked), "config", "core.sshCommand"],
        env=query_env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "github-initech" in subprocess.run(
        ["git", "-C", str(main), "ls-remote", "--get-url", "https://github.com/org/repo"],
        env=query_env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "github-acme" in subprocess.run(
        ["git", "-C", str(linked), "ls-remote", "--get-url", "https://github.com/org/repo"],
        env=query_env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "co = checkout" in (home / ".gitconfig").read_text()
