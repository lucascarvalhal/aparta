"""Apply reconciles the agent env, it does not only add to it."""


def test_apply_clears_variables_the_profile_no_longer_sets(tmp_path, monkeypatch):
    """An ADC that vanished must not stay in the agent config pointing nowhere."""
    import json

    from aparta.apply import apply_profile
    from aparta.fsutil import SafeWriter
    from aparta.profiles import Profile

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("APARTA_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setattr("pathlib.Path.home", lambda: home)

    repo = tmp_path / "root" / "app"
    (repo / ".git").mkdir(parents=True)
    settings = repo / ".claude" / "settings.local.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"env": {
        "GH_CONFIG_DIR": "/old/gh",
        "GOOGLE_APPLICATION_CREDENTIALS": "/gone/adc.json",
    }}))

    profile = Profile(
        name="p",
        root=str(tmp_path / "root"),
        git_email="a@b.c",
        gh_user="someone",
        agents=["claude-code"],
    )
    apply_profile(profile, SafeWriter())

    env = json.loads(settings.read_text())["env"]
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in env
    assert env["GH_CONFIG_DIR"].endswith("gh-p")


def test_apply_filters_agent_env_for_each_exact_workspace(tmp_path, monkeypatch):
    """Two worktrees sharing a profile must not receive each other's providers."""
    import json
    import subprocess

    from aparta.apply import apply_profile
    from aparta.fsutil import SafeWriter
    from aparta.profiles import Profile
    from aparta.workspaces import Workspace, save_workspaces

    monkeypatch.setenv("APARTA_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: home)
    root = tmp_path / "client"
    github_repo = root / "github-app"
    cloud_repo = root / "cloud-app"
    for repo in (github_repo, cloud_repo):
        repo.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
    profile = Profile(
        name="client",
        root=str(root),
        git_email="dev@client.com",
        gh_user="client-gh",
        gcloud_account="dev@client.com",
        gcloud_isolated=True,
        agents=["claude-code"],
    )
    save_workspaces(
        {
            "github-app": Workspace("github-app", str(github_repo), profile.name, ["github"]),
            "cloud-app": Workspace("cloud-app", str(cloud_repo), profile.name, ["gcloud"]),
        },
        SafeWriter(),
    )
    monkeypatch.setattr("aparta.apply.BACKENDS", [])

    apply_profile(profile, SafeWriter(), siblings={profile.name: profile})

    github_env = json.loads(
        (github_repo / ".claude" / "settings.local.json").read_text()
    )["env"]
    cloud_env = json.loads(
        (cloud_repo / ".claude" / "settings.local.json").read_text()
    )["env"]
    assert set(github_env) == {"GH_CONFIG_DIR"}
    assert set(cloud_env) == {
        "CLOUDSDK_CONFIG",
        "CLOUDSDK_ACTIVE_CONFIG_NAME",
        "CLOUDSDK_CORE_ACCOUNT",
        "CLOUDSDK_CORE_DISABLE_FILE_LOGGING",
        "GOOGLE_APPLICATION_CREDENTIALS",
    }
