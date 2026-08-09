"""Portable configuration models for the web-search runtime."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MediaWikiSiteConfig:
    site_id: str
    base_url: str

    def __post_init__(self) -> None:
        if not str(self.site_id or "").strip():
            raise ValueError("MediaWikiSiteConfig.site_id is required.")
        if not str(self.base_url or "").strip().startswith(("http://", "https://")):
            raise ValueError("MediaWikiSiteConfig.base_url must be an HTTP(S) URL.")


@dataclass(frozen=True)
class WebSearchProfile:
    name: str
    mode: str = "duckduckgo"
    timeout_seconds: int = 20
    max_results: int = 8
    user_agent: str = "Mozilla/5.0 (compatible; SagaWebSearchRuntime/1.0; +https://example.invalid)"

    def __post_init__(self) -> None:
        if not str(self.name or "").strip():
            raise ValueError("WebSearchProfile.name is required.")
        if not str(self.mode or "").strip():
            raise ValueError("WebSearchProfile.mode is required.")
        if int(self.timeout_seconds) <= 0:
            raise ValueError("WebSearchProfile.timeout_seconds must be positive.")
        if int(self.max_results) < 1:
            raise ValueError("WebSearchProfile.max_results must be at least 1.")
        if not str(self.user_agent or "").strip():
            raise ValueError("WebSearchProfile.user_agent is required.")


@dataclass
class WebSearchRuntimeConfig:
    profiles: dict[str, WebSearchProfile] = field(default_factory=dict)
    mediawiki_sites: dict[str, MediaWikiSiteConfig] = field(default_factory=dict)
