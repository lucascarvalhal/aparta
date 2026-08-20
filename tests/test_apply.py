"""Apply reconciles the agent env, it does not only add to it."""


def test_apply_clears_variables_the_profile_no_longer_sets(tmp_path):
    """An ADC that vanished must not stay in the agent config pointing nowhere."""
    import json

    from aparta.apply import apply_profile
    from aparta.fsutil import SafeWriter
    from aparta.profiles import Profile

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
