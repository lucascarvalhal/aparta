"""Profile generation and round-trip through profiles.toml."""

from pathlib import Path

from aparta.fsutil import SafeWriter
from aparta.profiles import Profile, load_profiles, save_profiles


def test_profiles_roundtrip(tmp_path: Path):
    path = tmp_path / "profiles.toml"
    profiles = {
        "pessoal": Profile(
            name="pessoal",
            root="~/pessoal",
            git_email="eu@example.com",
            ssh_key="~/.ssh/id_ed25519_pessoal",
            gh_user="lucas-pessoal",
            gcloud_account="eu@gmail.com",
            gcloud_project="meu-projeto",
            agents=["claude-code", "direnv"],
        ),
        "trabalho": Profile(name="trabalho", root="~/trabalho", git_email="eu@empresa.com"),
    }
    save_profiles(profiles, SafeWriter(), path=path)
    loaded = load_profiles(path)

    assert set(loaded) == {"pessoal", "trabalho"}
    p = loaded["pessoal"]
    assert p.git_email == "eu@example.com"
    assert p.agents == ["claude-code", "direnv"]
    assert loaded["trabalho"].agents == ["claude-code"]  # default


def test_profile_env():
    p = Profile(name="pessoal", root="~/p", git_email="e@x.com", gh_user="u", gcloud_account="a")
    env = p.env()
    assert env["CLOUDSDK_ACTIVE_CONFIG_NAME"] == "pessoal"
    assert env["GH_CONFIG_DIR"].endswith("gh-pessoal")

    sem_nada = Profile(name="x", root="~/x", git_email="e@x.com")
    assert sem_nada.env() == {}


def test_load_missing_file_returns_empty(tmp_path: Path):
    assert load_profiles(tmp_path / "nope.toml") == {}


def test_config_dir_env_override(tmp_path: Path, monkeypatch):
    from aparta.profiles import config_dir, profiles_path

    monkeypatch.setenv("APARTA_CONFIG_DIR", str(tmp_path))
    assert config_dir() == tmp_path
    assert profiles_path() == tmp_path / "profiles.toml"


def test_empty_agents_list_survives_roundtrip(tmp_path):
    from aparta.fsutil import SafeWriter
    from aparta.profiles import Profile, load_profiles, save_profiles

    path = tmp_path / "profiles.toml"
    p = Profile(name="x", root="~/x", git_email="a@b.c", agents=[])
    save_profiles({"x": p}, SafeWriter(), path)
    assert load_profiles(path)["x"].agents == []


def test_gh_config_dir_honors_xdg(tmp_path, monkeypatch):
    from aparta.profiles import gh_config_dir

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert gh_config_dir("acme") == tmp_path / "xdg" / "gh-acme"


def test_isolated_gcloud_uses_its_own_config_dir(monkeypatch, tmp_path):
    from aparta.profiles import Profile

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    light = Profile(name="acme", root="~/a", git_email="a@b.c", gcloud_account="a@b.c")
    assert light.env()["CLOUDSDK_ACTIVE_CONFIG_NAME"] == "acme"
    assert "CLOUDSDK_CONFIG" not in light.env()

    isolated = Profile(
        name="acme", root="~/a", git_email="a@b.c", gcloud_account="a@b.c", gcloud_isolated=True
    )
    env = isolated.env()
    assert env["CLOUDSDK_CONFIG"] == str(tmp_path / "gcloud-acme")
    # the isolated dir replaces the named-configuration selector
    # pinned by name so a stray value in the shell cannot pick another one
    assert env["CLOUDSDK_ACTIVE_CONFIG_NAME"] == "acme"
