"""Provider names, workspace validation, and environment selection."""

from __future__ import annotations

from .profiles import Profile
from .workspaces import Workspace


PROVIDER_ALIASES = {
    "gh": "github",
    "google": "gcloud",
    "google-cloud": "gcloud",
}
KNOWN_PROVIDERS = {
    "git",
    "ssh",
    "github",
    "gitlab",
    "bitbucket",
    "gcloud",
    "adc",
    "aws",
}


class ProviderError(ValueError):
    """An unknown or unsafe provider selection."""


def canonical_provider(value: str) -> str:
    provider = value.strip().lower()
    provider = PROVIDER_ALIASES.get(provider, provider)
    if provider not in KNOWN_PROVIDERS:
        choices = ", ".join(sorted(KNOWN_PROVIDERS))
        raise ProviderError(f"unknown provider '{value}'; choose one of: {choices}")
    return provider


def validate_provider(profile: Profile, provider: str) -> None:
    """Reject a provider that cannot be isolated by the selected profile."""
    provider = canonical_provider(provider)
    if provider == "ssh" and not (profile.ssh_key or profile.ssh_alias):
        raise ProviderError(f"profile '{profile.name}' has no SSH identity configured")
    if provider == "github" and not profile.gh_user:
        raise ProviderError(f"profile '{profile.name}' has no GitHub account configured")
    if provider in {"gcloud", "adc"}:
        if not (profile.gcloud_account or profile.gcloud_project):
            raise ProviderError(f"profile '{profile.name}' has no gcloud account configured")
        if not profile.gcloud_isolated:
            raise ProviderError(
                f"profile '{profile.name}' must use isolated gcloud mode before enabling {provider}"
            )
    if provider == "aws" and not profile.aws_profile:
        raise ProviderError(f"profile '{profile.name}' has no AWS profile configured")


def canonical_providers(values: list[str]) -> list[str]:
    return list(dict.fromkeys(canonical_provider(value) for value in values))


def workspace_env(workspace: Workspace, profile: Profile) -> dict[str, str]:
    """Return only the profile selectors enabled for this exact workspace."""
    selected = set(canonical_providers(workspace.providers))
    available = profile.env()
    env: dict[str, str] = {}

    if selected.intersection({"git", "ssh"}):
        from .backends.git import workspace_gitconfig_path

        env.update(
            {
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "include.path",
                "GIT_CONFIG_VALUE_0": str(workspace_gitconfig_path(workspace)),
            }
        )
    if "ssh" in selected and profile.ssh_key:
        env["GIT_SSH_COMMAND"] = (
            f"ssh -i {profile.ssh_key} -o IdentitiesOnly=yes"
        )

    if "github" in selected and "GH_CONFIG_DIR" in available:
        env["GH_CONFIG_DIR"] = available["GH_CONFIG_DIR"]

    if selected.intersection({"gcloud", "adc"}):
        for key in (
            "CLOUDSDK_CONFIG",
            "CLOUDSDK_ACTIVE_CONFIG_NAME",
            "CLOUDSDK_CORE_ACCOUNT",
            "CLOUDSDK_CORE_PROJECT",
            "CLOUDSDK_CORE_DISABLE_FILE_LOGGING",
            "GOOGLE_CLOUD_PROJECT",
            "GCLOUD_PROJECT",
            "GOOGLE_APPLICATION_CREDENTIALS",
        ):
            if key in available:
                env[key] = available[key]

    if "aws" in selected and "AWS_PROFILE" in available:
        env["AWS_PROFILE"] = available["AWS_PROFILE"]

    return env


def auth_provider_name(provider: str) -> str:
    provider = canonical_provider(provider)
    return "gh" if provider == "github" else provider


def status_provider_name(provider: str) -> str:
    lowered = provider.lower()
    return "github" if lowered == "gh" else lowered
