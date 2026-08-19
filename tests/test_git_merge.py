"""gitconfig merging: includeIf added only when absent, the rest preserved."""

from pathlib import Path

from aparta.backends.git import (
    apply_git,
    has_includeif,
    merge_includeif,
    render_context_gitconfig,
)
from aparta.fsutil import SafeWriter
from aparta.profiles import Profile


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
    text = render_context_gitconfig(make_profile(git_name="Lucas"))
    assert "email = eu@example.com" in text
    assert "name = Lucas" in text
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
