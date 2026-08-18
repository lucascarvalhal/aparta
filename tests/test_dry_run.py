"""Dry-run: nada é escrito, nenhum backup criado, mudanças apenas reportadas."""

import json
from pathlib import Path

from aparta.agents.claude_code import ClaudeCodeAdapter
from aparta.backends.git import apply_git
from aparta.fsutil import SafeWriter
from aparta.profiles import Profile


def snapshot(root: Path) -> dict[str, str]:
    return {str(p): p.read_text() for p in root.rglob("*") if p.is_file()}


def test_dry_run_apply_git_touches_nothing(tmp_path: Path):
    home = tmp_path
    (home / ".gitconfig").write_text("[user]\n\temail = global@example.com\n")
    before = snapshot(home)

    profile = Profile(name="pessoal", root=str(tmp_path / "pessoal"), git_email="eu@x.com")
    writer = SafeWriter(dry_run=True)
    apply_git(profile, writer, home=home)

    assert snapshot(home) == before  # nada mudou, nenhum .bak
    assert writer.changes  # mas mudanças foram detectadas e reportadas
    assert all(c.startswith("[dry-run]") for c in writer.changes)


def test_dry_run_inject_touches_nothing(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    settings = repo / ".claude" / "settings.local.json"
    settings.write_text(json.dumps({"env": {"FOO": "bar"}}))
    before = snapshot(tmp_path)

    writer = SafeWriter(dry_run=True)
    changed = ClaudeCodeAdapter().inject(repo, {"GH_CONFIG_DIR": "/x"}, writer)

    assert changed is True
    assert snapshot(tmp_path) == before


def test_writer_skips_identical_content(tmp_path: Path):
    f = tmp_path / "a.txt"
    f.write_text("mesmo\n")
    writer = SafeWriter(dry_run=False)
    assert writer.write_text(f, "mesmo\n") is False
    assert not list(tmp_path.glob("*.bak-aparta-*"))
