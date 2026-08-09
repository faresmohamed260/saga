from packages.web_search_runtime.client import WebSearchRuntimeClient
from packages.web_search_runtime.contracts import SearchResult, WebDocument, WebDocumentMetadata, WebSearchRequestMetadata
from packages.web_search_runtime.models import MediaWikiSiteConfig, WebSearchProfile, WebSearchRuntimeConfig


def test_mediawiki_api_url_uses_w_path_for_wikipedia_root():
    assert WebSearchRuntimeClient._mediawiki_api_url("https://en.wikipedia.org") == "https://en.wikipedia.org/w/api.php"


def test_mediawiki_api_url_rewrites_wiki_path_to_w_api():
    assert WebSearchRuntimeClient._mediawiki_api_url("https://example.fandom.com/wiki") == "https://example.fandom.com/w/api.php"


def test_mediawiki_api_url_rewrites_page_url_to_w_api():
    assert WebSearchRuntimeClient._mediawiki_api_url("https://en.wikipedia.org/wiki/Main_Page") == "https://en.wikipedia.org/w/api.php"


def test_mediawiki_api_url_preserves_explicit_w_path():
    assert WebSearchRuntimeClient._mediawiki_api_url("https://example.fandom.com/w") == "https://example.fandom.com/w/api.php"


def test_web_search_request_metadata_is_typed():
    metadata = WebSearchRequestMetadata(
        trace_id="trace-1",
        run_id="run-1",
        component="web_search_runtime",
        operation="search",
        provider="duckduckgo",
        query="frankenstein",
        site="wikipedia.org",
        status_code=200,
        result_count=3,
    )

    payload = metadata.model_dump()

    assert payload["operation"] == "search"
    assert payload["provider"] == "duckduckgo"
    assert payload["trace_id"] == "trace-1"
    assert payload["component"] == "web_search_runtime"
    assert payload["result_count"] == 3


def test_web_search_profiles_reject_invalid_values():
    try:
        WebSearchProfile(name="", mode="duckduckgo")
    except ValueError as exc:
        assert "name is required" in str(exc)
    else:
        raise AssertionError("Expected invalid web-search profile to be rejected.")

    try:
        MediaWikiSiteConfig(site_id="wiki", base_url="example.com/wiki")
    except ValueError as exc:
        assert "base_url" in str(exc)
    else:
        raise AssertionError("Expected invalid MediaWiki site config to be rejected.")


def test_web_document_extraction_produces_clean_summary_and_excerpt():
    client = WebSearchRuntimeClient(
        profile=WebSearchProfile(name="test-web-search", mode="duckduckgo"),
        config=WebSearchRuntimeConfig(),
    )
    html = """
    <html>
      <head><title>Frankenstein's monster</title></head>
      <body>
        <p>| Frankenstein character | Created by | Mary Shelley |</p>
        <p>Frankenstein's monster is a fictional character in Mary Shelley's 1818 novel Frankenstein.</p>
        <p>He was created by Victor Frankenstein from assembled body parts and brought to life through an unnatural process.</p>
        <p>References</p>
      </body>
    </html>
    """

    title, text, summary, excerpt, focus_text, evidence_sentences = client._extract_document_fields(
        html,
        url="https://example.com/frankenstein",
        query="who created frankenstein's monster",
    )

    assert title == "Frankenstein's monster"
    assert "Victor Frankenstein" in text
    assert summary.startswith("He was created by Victor Frankenstein")
    assert "Created by | Mary Shelley" not in summary
    assert "Victor Frankenstein" in excerpt
    assert focus_text == "He was created by Victor Frankenstein from assembled body parts and brought to life through an unnatural process."
    assert evidence_sentences[0].score >= evidence_sentences[-1].score


def test_fetch_document_uses_structured_mediawiki_intro_for_wiki_urls():
    client = WebSearchRuntimeClient(
        profile=WebSearchProfile(name="test-web-search", mode="duckduckgo"),
        config=WebSearchRuntimeConfig(),
    )

    def _mediawiki_get(base_url: str, params: dict[str, object]) -> dict[str, object]:
        assert base_url == "https://en.wikipedia.org"
        assert params["titles"] == "Frankenstein's monster"
        return {
            "query": {
                "pages": {
                    "123": {
                        "pageid": 123,
                        "title": "Frankenstein's monster",
                        "extract": (
                            "Frankenstein's monster is a fictional character in Mary Shelley's 1818 novel Frankenstein. "
                            "Victor Frankenstein creates the creature from assembled body parts."
                        ),
                        "categories": [{"title": "Category:Fictional monsters"}],
                    }
                }
            }
        }

    client.mediawiki_get = _mediawiki_get  # type: ignore[method-assign]
    document = client.fetch_document("https://en.wikipedia.org/wiki/Frankenstein%27s_monster", query="who created frankenstein's monster")

    assert document.title == "Frankenstein's monster"
    assert isinstance(document.metadata, WebDocumentMetadata)
    assert document.metadata.source_type == "mediawiki"
    assert document.metadata.page_title == "Frankenstein's_monster"
    assert document.query == "who created frankenstein's monster"
    assert document.focus_text == "Victor Frankenstein creates the creature from assembled body parts."
    assert document.summary.startswith("Victor Frankenstein creates the creature")
    assert "Victor Frankenstein creates the creature" in document.excerpt
    assert document.evidence_sentences[0].text == "Victor Frankenstein creates the creature from assembled body parts."
    assert document.html == ""


def test_web_search_tool_payload_uses_request_metadata():
    client = WebSearchRuntimeClient(
        profile=WebSearchProfile(name="test-web-search", mode="duckduckgo"),
        config=WebSearchRuntimeConfig(),
    )

    client.search = lambda query, max_results=8, site="": [  # type: ignore[method-assign]
        SearchResult(title="Victor Frankenstein", url="https://example.com/victor", snippet="Creates the creature.", source="stub", rank=1)
    ]
    client.last_request_metadata = lambda: {"operation": "search", "provider": "duckduckgo"}  # type: ignore[method-assign]

    tools = {tool.name: tool for tool in client.as_langgraph_tools()}
    result = tools["web_search_search"].invoke({"query": "who creates Frankenstein's monster"})

    assert result["ok"] is True
    assert result["data"]["result_count"] == 1
    assert "request_metadata" in result["data"]
    assert result["data"]["request_metadata"]["operation"] == "search"


def test_web_fetch_document_tool_payload_uses_typed_document_metadata():
    client = WebSearchRuntimeClient(
        profile=WebSearchProfile(name="test-web-search", mode="duckduckgo"),
        config=WebSearchRuntimeConfig(),
    )

    client.fetch_document = lambda url, query="": WebDocument(  # type: ignore[method-assign]
        url=url,
        title="Frankenstein's monster",
        summary="Victor Frankenstein creates the creature.",
        excerpt="Victor Frankenstein creates the creature.",
        focus_text="Victor Frankenstein creates the creature.",
        query=query,
        evidence_sentences=[],
        text="Victor Frankenstein creates the creature.",
        html="",
        metadata=WebDocumentMetadata(status_code=200, source_type="mediawiki", page_title="Frankenstein's_monster"),
    )
    client.last_request_metadata = lambda: {"operation": "fetch_document", "provider": "duckduckgo"}  # type: ignore[method-assign]

    tools = {tool.name: tool for tool in client.as_langgraph_tools()}
    result = tools["web_search_fetch_document"].invoke({"url": "https://example.com/frankenstein", "query": "creator"})

    assert result["ok"] is True
    assert result["data"]["metadata"]["source_type"] == "mediawiki"
    assert result["data"]["metadata"]["page_title"] == "Frankenstein's_monster"
    assert result["data"]["metadata"]["status_code"] == 200
