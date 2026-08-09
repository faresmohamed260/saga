"""Factory helpers for portable web-search clients."""

from __future__ import annotations

from packages.web_search_runtime.client import WebSearchRuntimeClient
from packages.web_search_runtime.models import WebSearchProfile, WebSearchRuntimeConfig


def create_web_search_client(
    *,
    profile_name: str,
    config: WebSearchRuntimeConfig,
    profile: WebSearchProfile | None = None,
) -> WebSearchRuntimeClient:
    resolved_profile = profile or config.profiles.get(profile_name)
    if resolved_profile is None:
        raise KeyError(f"Unknown web-search profile '{profile_name}'.")
    return WebSearchRuntimeClient(profile=resolved_profile, config=config)
