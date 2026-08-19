"""AWS backend: profile listing, env injection and doctor detail."""

from __future__ import annotations

from pathlib import Path

from aparta.backends.aws import apply_aws, aws_profile_exists, list_aws_profiles
from aparta.fsutil import SafeWriter
from aparta.profiles import Profile, load_profiles, save_profiles

AWS_CONFIG = """\
[default]
region = us-east-1

[profile acme]
region = us-east-1
output = json

[profile personal]
region = sa-east-1
"""


def test_list_aws_profiles_from_config_and_credentials(tmp_path: Path):
    (tmp_path / "config").write_text(AWS_CONFIG)
    (tmp_path / "credentials").write_text("[legacy]\naws_access_key_id = X\n")
    assert list_aws_profiles(tmp_path) == ["default", "acme", "personal", "legacy"]


def test_list_aws_profiles_missing_dir(tmp_path: Path):
    assert list_aws_profiles(tmp_path / "nope") == []


def test_env_includes_aws_profile():
    p = Profile(name="x", root="~/x", git_email="a@b.c", aws_profile="acme")
    assert p.env()["AWS_PROFILE"] == "acme"


def test_aws_profile_roundtrip_in_toml(tmp_path: Path):
    path = tmp_path / "profiles.toml"
    p = Profile(name="x", root="~/x", git_email="a@b.c", aws_profile="acme")
    save_profiles({"x": p}, SafeWriter(), path)
    assert load_profiles(path)["x"].aws_profile == "acme"


def test_apply_aws_notes(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / ".aws").mkdir()
    (tmp_path / ".aws" / "config").write_text("[profile acme]\nregion = us-east-1\n")

    found = apply_aws(Profile(name="x", root="~/x", git_email="a@b.c", aws_profile="acme"), SafeWriter())
    assert found[0].level == "info"

    missing = apply_aws(Profile(name="x", root="~/x", git_email="a@b.c", aws_profile="ghost"), SafeWriter())
    assert missing[0].level == "warn"

    none = apply_aws(Profile(name="x", root="~/x", git_email="a@b.c"), SafeWriter())
    assert none == []


def test_aws_profile_exists(tmp_path: Path):
    (tmp_path / "config").write_text("[profile acme]\n")
    assert aws_profile_exists("acme", tmp_path) is True
    assert aws_profile_exists("ghost", tmp_path) is False
