from __future__ import annotations

from packages.web_search_runtime.contracts import WebSearchClient
from packages.web_search_runtime.factory import create_web_search_client
from packages.web_search_runtime.models import MediaWikiSiteConfig, WebSearchProfile, WebSearchRuntimeConfig
from saga.storage.persistence import SagaRelationalStore


WEB_SEARCH_PROVIDER = "web_search"
MODE_DUCKDUCKGO = "duckduckgo"

DEFAULT_MEDIAWIKI_SITES = {
    "acotar": MediaWikiSiteConfig(
        site_id="acotar",
        base_url="https://acourtofthornsandroses.fandom.com",
    ),
    "harry-potter": MediaWikiSiteConfig(
        site_id="harry-potter",
        base_url="https://harrypotter.fandom.com",
    ),
    "hp": MediaWikiSiteConfig(
        site_id="hp",
        base_url="https://harrypotter.fandom.com",
    ),
}


def build_web_search_runtime_config(*, store: SagaRelationalStore | None = None) -> WebSearchRuntimeConfig:
    relational_store = store or SagaRelationalStore()
    payload = relational_store.get_provider_config(WEB_SEARCH_PROVIDER) or {}
    profile = WebSearchProfile(
        name="runtime_web_search",
        mode=str(payload.get("mode") or MODE_DUCKDUCKGO).strip().lower() or MODE_DUCKDUCKGO,
        timeout_seconds=max(5, int(payload.get("timeout_seconds") or 20)),
        max_results=max(1, int(payload.get("max_results") or 8)),
        user_agent=str(payload.get("user_agent") or WebSearchProfile(name="default").user_agent).strip(),
    )
    return WebSearchRuntimeConfig(
        profiles={profile.name: profile},
        mediawiki_sites=dict(DEFAULT_MEDIAWIKI_SITES),
    )


def create_runtime_web_search_client(
    *,
    mode: str = MODE_DUCKDUCKGO,
    store: SagaRelationalStore | None = None,
    timeout: int = 20,
    max_results: int = 8,
    user_agent: str = "",
) -> WebSearchClient:
    config = build_web_search_runtime_config(store=store)
    profile = WebSearchProfile(
        name=f"runtime_{mode}",
        mode=str(mode or MODE_DUCKDUCKGO).strip().lower() or MODE_DUCKDUCKGO,
        timeout_seconds=max(5, int(timeout)),
        max_results=max(1, int(max_results)),
        user_agent=str(user_agent or (config.profiles["runtime_web_search"].user_agent if config.profiles else "")).strip()
        or WebSearchProfile(name="default").user_agent,
    )
    config.profiles[profile.name] = profile
    return create_web_search_client(profile_name=profile.name, config=config, profile=profile)


def resolve_mediawiki_base_url(series_id: str, *, store: SagaRelationalStore | None = None, fallback: str = "") -> str:
    normalized = str(series_id or "").strip().lower()
    config = build_web_search_runtime_config(store=store)
    site = config.mediawiki_sites.get(normalized)
    if site:
        return site.base_url.rstrip("/")
    return str(fallback or "").rstrip("/")
