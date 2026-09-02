"""Workspace provider canonicalization and environment selection."""

from aparta.profiles import Profile
from aparta.providers import canonical_provider, workspace_env
from aparta.workspaces import Workspace


def test_provider_aliases_are_canonical():
    """Persisting aliases would make provider filtering depend on CLI spelling."""
    assert canonical_provider("gh") == "github"
    assert canonical_provider("google") == "gcloud"
    assert canonical_provider("BitBucket") == "bitbucket"


def test_workspace_env_excludes_unselected_profile_providers(tmp_path, monkeypatch):
    """Sharing a profile must not enable every provider in every worktree."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    profile = Profile(
        name="client",
        root="/client",
        git_email="dev@client.com",
        gh_user="dev-client",
        gcloud_account="dev@client.com",
        gcloud_isolated=True,
        aws_profile="client",
    )
    workspace = Workspace("cloud-only", "/client/cloud", profile.name, ["gcloud"])

    env = workspace_env(workspace, profile)

    assert env["CLOUDSDK_CONFIG"].endswith("gcloud-client")
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in env
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
