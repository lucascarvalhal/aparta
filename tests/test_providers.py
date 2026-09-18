"""Workspace provider canonicalization and environment selection."""

import subprocess

from aparta.profiles import Profile
from aparta.providers import canonical_provider, workspace_env
from aparta.workspaces import Workspace


def test_provider_aliases_are_canonical():
    """Persisting aliases would make provider filtering depend on CLI spelling."""
    assert canonical_provider("gh") == "github"
    assert canonical_provider("google") == "gcloud"
    assert canonical_provider("Google-Cloud") == "gcloud"


def test_workspace_env_excludes_unselected_profile_providers(tmp_path, monkeypatch):
    """Sharing a profile must not enable every provider in every worktree."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    profile = Profile(
        name="client",
        root="/client",
        git_email="dev@client.com",
        gh_user="dev-client",
        gcloud_account="dev@client.com",
        gcloud_project="client-prod",
        gcloud_isolated=True,
        aws_profile="client",
    )
    workspace = Workspace("cloud-only", "/client/cloud", profile.name, ["gcloud"])

    env = workspace_env(workspace, profile)

    assert env["CLOUDSDK_CONFIG"].endswith("gcloud-client")
    assert env["CLOUDSDK_CORE_ACCOUNT"] == "dev@client.com"
    assert env["CLOUDSDK_CORE_PROJECT"] == "client-prod"
    assert env["GOOGLE_CLOUD_PROJECT"] == "client-prod"
    assert env["GCLOUD_PROJECT"] == "client-prod"
    assert env["GOOGLE_APPLICATION_CREDENTIALS"].endswith(
        "gcloud-client/application_default_credentials.json"
    )
    assert "GH_CONFIG_DIR" not in env
    assert "AWS_PROFILE" not in env


def test_adc_provider_selects_the_isolated_adc_and_gcloud_directory(tmp_path, monkeypatch):
    """An ADC without its matching gcloud directory would not be profile scoped."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    profile = Profile(
        name="client",
        root="/client",
        git_email="dev@client.com",
        gcloud_account="dev@client.com",
        gcloud_isolated=True,
    )
    workspace = Workspace("terraform", "/client/tf", profile.name, ["adc"])

    env = workspace_env(workspace, profile)

    assert env["CLOUDSDK_CONFIG"].endswith("gcloud-client")
    assert env["GOOGLE_APPLICATION_CREDENTIALS"].endswith(
        "gcloud-client/application_default_credentials.json"
    )


def test_git_and_ssh_select_the_exact_workspace_config(tmp_path, monkeypatch):
    monkeypatch.setenv("APARTA_CONFIG_DIR", str(tmp_path / "aparta"))
    profile = Profile(
        name="client",
        root="/client",
        git_email="dev@client.com",
        ssh_key="/keys/client",
    )
    repo = tmp_path / "api"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    workspace = Workspace("api", str(repo), profile.name, ["git", "ssh"])

    env = workspace_env(workspace, profile)

    assert env["GIT_CONFIG_COUNT"] == "1"
    assert env["GIT_CONFIG_KEY_0"] == f"includeIf.gitdir:{repo.resolve() / '.git'}.path"
    assert env["GIT_CONFIG_VALUE_0"].startswith(str(tmp_path / "aparta"))
    assert env["GIT_SSH_COMMAND"] == "ssh -i /keys/client -o IdentitiesOnly=yes"


def test_injected_git_identity_does_not_follow_a_cd_into_another_repo(tmp_path, monkeypatch):
    """An agent launched in one repo that runs git elsewhere must not carry the first identity along."""
    import os

    monkeypatch.setenv("APARTA_CONFIG_DIR", str(tmp_path / "aparta"))
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in ("a", "b"):
        subprocess.run(["git", "init", "-q", str(tmp_path / name)], check=True)
    profile = Profile(name="client", root=str(tmp_path / "a"), git_email="a@client.com")
    workspace = Workspace("a", str(tmp_path / "a"), profile.name, ["git"])
    from pathlib import Path

    Path(workspace.gitconfig_path).parent.mkdir(parents=True, exist_ok=True)
    Path(workspace.gitconfig_path).write_text("[user]\n\temail = a@client.com\n")

    env = {**os.environ, **workspace_env(workspace, profile)}
    in_a = subprocess.run(["git", "-C", str(tmp_path / "a"), "config", "user.email"], env=env, capture_output=True, text=True).stdout.strip()
    in_b = subprocess.run(["git", "-C", str(tmp_path / "b"), "config", "user.email"], env=env, capture_output=True, text=True).stdout.strip()
    assert in_a == "a@client.com"
    assert in_b != "a@client.com"
