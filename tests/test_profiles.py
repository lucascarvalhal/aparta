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
