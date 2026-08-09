import requests

from packages.web_search_runtime.client import WebSearchRuntimeClient
from packages.web_search_runtime.factory import create_web_search_client
from packages.web_search_runtime.models import WebSearchProfile, WebSearchRuntimeConfig
from saga.services.web_search_service import WebSearchService


class _DummyResponse:
    def __init__(self, *, text: str = "", json_payload=None, status_code: int = 200):
        self.text = text
        self._json_payload = json_payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self._json_payload


def test_duckduckgo_search_parses_html_results(monkeypatch):
    html = """
    <div class="result">
      <div class="result__title"><a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpage">Example Title</a></div>
      <a class="result__snippet">Example snippet.</a>
    </div>
    """
    config = WebSearchRuntimeConfig(profiles={"default": WebSearchProfile(name="default")})
    client = create_web_search_client(profile_name="default", config=config)
    monkeypatch.setattr(client.session, "get", lambda *args, **kwargs: _DummyResponse(text=html))

    results = client.search("example")

    assert len(results) == 1
    assert results[0].title == "Example Title"
    assert results[0].url == "https://example.com/page"
    assert results[0].snippet == "Example snippet."


def test_mediawiki_search_normalizes_result_rows(monkeypatch):
    config = WebSearchRuntimeConfig(profiles={"default": WebSearchProfile(name="default")})
    client = create_web_search_client(profile_name="default", config=config)
    monkeypatch.setattr(
        client,
        "mediawiki_get",
        lambda base_url, params: {
            "query": {
                "search": [
                    {"title": "Feyre Archeron", "snippet": "<span>High Fae huntress</span>", "pageid": 42},
                ]
            }
        },
    )

    results = client.mediawiki_search("https://acourtofthornsandroses.fandom.com", "Feyre")

    assert len(results) == 1
    assert results[0].metadata["page_title"] == "Feyre_Archeron"
    assert results[0].snippet == "High Fae huntress"


def test_fetch_document_uses_text_extractor(monkeypatch):
    html = "<html><head><title>Demo</title></head><body><article><p>Hello world.</p></article></body></html>"
    config = WebSearchRuntimeConfig(profiles={"default": WebSearchProfile(name="default")})
    client = create_web_search_client(profile_name="default", config=config)
    monkeypatch.setattr(client.session, "get", lambda *args, **kwargs: _DummyResponse(text=html))
    monkeypatch.setattr("packages.web_search_runtime.client.trafilatura.extract", lambda *args, **kwargs: "Hello world.")

    document = client.fetch_document("https://example.com/page")

    assert document.title == "Demo"
    assert document.text == "Hello world."


def test_web_search_service_returns_serializable_shape():
    class _StubClient:
        mode = "duckduckgo"

        def search(self, query, *, max_results=8, site=""):
            from packages.web_search_runtime.contracts import SearchResult

            return [SearchResult(title="Result", url="https://example.com", snippet="Snippet", source="duckduckgo", rank=1)]

        def fetch_document(self, url):
            from packages.web_search_runtime.contracts import WebDocument

            return WebDocument(url=url, title="Title", text="Body", html="<html></html>", metadata={"ok": True})

        def mediawiki_search(self, base_url, query, *, max_results=5):
            return []

        def mediawiki_get(self, base_url, params):
            return {}

        def mediawiki_page_categories(self, base_url, page_title):
            return []

        def mediawiki_parse_html(self, base_url, page_title):
            return ""

        def provider_name(self):
            return "duckduckgo"

        def last_request_metadata(self):
            return {"query": "demo"}

    service = WebSearchService(web_client=_StubClient())
    payload = service.search("demo")

    assert payload["provider"] == "duckduckgo"
    assert payload["results"][0]["title"] == "Result"
    assert payload["metadata"] == {"query": "demo"}
