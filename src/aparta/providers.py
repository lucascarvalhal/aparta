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
    "gcloud",
    "adc",
    "aws",
}


PROVIDER_LABELS = {"gcloud": "gcloud", "adc": "ADC", "github": "gh", "aws": "aws"}


def provider_label(provider: str) -> str:
    """How a provider is written in messages and tables."""
    return PROVIDER_LABELS.get(provider, provider)


class ProviderError(ValueError):
    """An unknown or unsafe provider selection."""


def canonical_provider(value: str) -> str:
    provider = value.strip().lower()
    provider = PROVIDER_ALIASES.get(provider, provider)
    if provider not in KNOWN_PROVIDERS:
        choices = ", ".join(sorted(KNOWN_PROVIDERS))
        raise ProviderError(f"unknown provider '{value}'; choose one of: {choices}")
    return provider


_MISSING = {
    "ssh": "has no SSH identity configured",
    "github": "has no GitHub account configured",
    "gcloud": "has no gcloud account configured",
    "adc": "has no gcloud account configured",
    "aws": "has no AWS profile configured",
}


def validate_provider(profile: Profile, provider: str) -> None:
    """Reject a provider the profile cannot isolate."""
    provider = canonical_provider(provider)
    configured = profile.provider_env()
    if provider in {"gcloud", "adc"} and "gcloud" in configured and not profile.gcloud_isolated:
        raise ProviderError(f"profile '{profile.name}' must use isolated gcloud mode before enabling {provider}")
    if provider not in configured:
        raise ProviderError(f"profile '{profile.name}' {_MISSING.get(provider, 'cannot enable ' + provider)}")


def canonical_providers(values: list[str]) -> list[str]:
    return list(dict.fromkeys(canonical_provider(value) for value in values))


def workspace_env(workspace: Workspace, profile: Profile) -> dict[str, str]:
    """Only the variables of the providers enabled for this exact workspace."""
    selected = set(canonical_providers(workspace.providers))
    configured = profile.provider_env()
    env: dict[str, str] = {}
    if selected.intersection({"git", "ssh"}):
        env.update(
            {
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "include.path",
                "GIT_CONFIG_VALUE_0": str(workspace.gitconfig_path),
            }
        )
    for provider in ("ssh", "github", "gcloud", "adc", "aws"):
        if provider in selected:
            env.update(configured.get(provider, {}))
    return env
