from __future__ import annotations

from pathlib import Path

from packages.agent_runtime.graph import AgentGraphRuntime
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.retrieval_runtime.client import RetrievalRuntimeClient
from packages.retrieval_runtime.models import RetrievalProfile, RetrievalRuntimeConfig
from packages.reasoning_runtime.client import ReasoningRuntimeClient
from packages.reasoning_runtime.contracts import ReasoningClient
from packages.reasoning_runtime.models import ReasoningProfile, ReasoningRuntimeConfig
from packages.web_search_runtime.client import WebSearchRuntimeClient
from packages.web_search_runtime.contracts import SearchResult, WebDocument
from packages.web_search_runtime.models import WebSearchProfile, WebSearchRuntimeConfig


def _runtime(*, reasoning_client, tools, system_prompt: str, checkpoint_engine=None, allow_in_memory_checkpointer: bool = False):
    return AgentGraphRuntime(
        reasoning_client=reasoning_client,
        tools=tools,
        system_prompt=system_prompt,
        checkpoint_engine=checkpoint_engine,
        allow_in_memory_checkpointer=allow_in_memory_checkpointer,
    )


class StubReasoningClient(ReasoningClient):
    mode = "stub"

    def __init__(self) -> None:
        self.calls = 0

    def generate_json(
        self,
        prompt: str,
        strict: bool = False,
        validator=None,
        max_tokens: int = 4096,
        response_format=None,
        tools=None,
        tool_choice=None,
    ) -> dict:
        self.calls += 1
        if self.calls == 1:
            return {
                "action": "tool",
                "rationale": "Ensure the storage bucket exists first.",
                "response": "",
                "tool_name": "persistence_ensure_bucket",
                "tool_input": {
                    "bucket_name": "agent-outputs",
                    "public": False,
                },
            }
        if self.calls == 2:
            return {
                "action": "tool",
                "rationale": "Persist the requested note before responding.",
                "response": "",
                "tool_name": "persistence_upload_text_object",
                "tool_input": {
                    "bucket_name": "agent-outputs",
                    "object_path": "agent_outputs/note.txt",
                    "text": "hello from langgraph",
                },
            }
        if self.calls == 3:
            return {
                "action": "tool",
                "rationale": "Read back the stored note before responding.",
                "response": "",
                "tool_name": "persistence_download_text_object",
                "tool_input": {
                    "bucket_name": "agent-outputs",
                    "object_path": "agent_outputs/note.txt",
                },
            }
        return {
            "action": "respond",
            "rationale": "The note has been stored successfully.",
            "response": "Stored the note successfully.",
            "tool_name": "",
            "tool_input": {},
        }

    def generate_text(self, prompt: str, *, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 4096) -> str:
        return "unused"

    def provider_name(self) -> str:
        return "stub"

    def resolved_model_name(self) -> str:
        return "stub-model"

    def last_request_metadata(self) -> dict:
        return {}


class StubMalformedPlanner(ReasoningClient):
    mode = "stub_malformed"

    def __init__(self) -> None:
        self.calls = 0

    def generate_json(
        self,
        prompt: str,
        strict: bool = False,
        validator=None,
        max_tokens: int = 4096,
        response_format=None,
        tools=None,
        tool_choice=None,
    ) -> dict:
        self.calls += 1
        if self.calls == 1:
            return {
                "error": "validation_failed",
                "raw_output": {
                    "action": "run",
                    "rationale": "Query the retrieval tool first.",
                    "response": "<html><body>ignore this</body></html>",
                    "tool_name": "Elasticsearch Query",
                    "tool_input": "{\"top_k\": 1}",
                },
            }
        return {
            "action": "respond",
            "rationale": "The retrieval tool already returned the evidence.",
            "response": "Retrieved the indexed document successfully.",
            "tool_name": "",
            "tool_input": {},
        }

    def generate_text(self, prompt: str, *, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 4096) -> str:
        return "unused"

    def provider_name(self) -> str:
        return "stub-malformed"

    def resolved_model_name(self) -> str:
        return "stub-malformed-model"

    def last_request_metadata(self) -> dict:
        return {}


class StubFallbackAfterToolPlanner(ReasoningClient):
    mode = "stub_fallback_after_tool"

    def __init__(self) -> None:
        self.calls = 0

    def generate_json(
        self,
        prompt: str,
        strict: bool = False,
        validator=None,
        max_tokens: int = 4096,
        response_format=None,
        tools=None,
        tool_choice=None,
    ) -> dict:
        self.calls += 1
        if self.calls == 1:
            return {
                "error": "validation_failed",
                "raw_output": {
                    "action": "run",
                    "rationale": "Query retrieval first.",
                    "response": "",
                    "tool_name": "Elasticsearch Query",
                    "tool_input": "{}",
                },
            }
        return {"error": "parse_failed", "raw_output": "<html>bad output</html>"}

    def generate_text(self, prompt: str, *, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 4096) -> str:
        return "unused"

    def provider_name(self) -> str:
        return "stub-fallback-after-tool"

    def resolved_model_name(self) -> str:
        return "stub-fallback-after-tool-model"

    def last_request_metadata(self) -> dict:
        return {}


class StubRepeatingToolPlanner(ReasoningClient):
    mode = "stub_repeating_tool"

    def __init__(self, index_ref: dict[str, object]) -> None:
        self.calls = 0
        self.index_ref = dict(index_ref)

    def generate_json(
        self,
        prompt: str,
        strict: bool = False,
        validator=None,
        max_tokens: int = 4096,
        response_format=None,
        tools=None,
        tool_choice=None,
    ) -> dict:
        self.calls += 1
        return {
            "action": "tool",
            "rationale": "Run the retrieval query.",
            "response": "",
            "tool_name": "retrieval_query_documents",
            "tool_input": {
                "index_ref": dict(self.index_ref),
                "query_text": "Who is the creature created by Victor Frankenstein?",
                "top_k": 1,
                "allowed_types": [],
                "character_bias": [],
                "metadata_filters": {},
            },
        }

    def generate_text(self, prompt: str, *, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 4096) -> str:
        return "unused"

    def provider_name(self) -> str:
        return "stub-repeating-tool"

    def resolved_model_name(self) -> str:
        return "stub-repeating-tool-model"

    def last_request_metadata(self) -> dict:
        return {}


class StubValidPlannerWithNullOptionals(ReasoningClient):
    mode = "stub_valid_null_optionals"

    def __init__(self, index_ref: dict[str, object]) -> None:
        self.calls = 0
        self.index_ref = dict(index_ref)

    def generate_json(
        self,
        prompt: str,
        strict: bool = False,
        validator=None,
        max_tokens: int = 4096,
        response_format=None,
        tools=None,
        tool_choice=None,
    ) -> dict:
        self.calls += 1
        if self.calls == 1:
            return {
                "action": "tool",
                "rationale": "Run retrieval.",
                "response": "",
                "tool_name": "retrieval_query_documents",
                "tool_input": {
                    "index_ref": dict(self.index_ref),
                    "query_text": "Who is the creature created by Victor Frankenstein?",
                    "top_k": 1,
                    "allowed_types": None,
                    "character_bias": None,
                    "metadata_filters": None,
                },
            }
        return {
            "action": "respond",
            "rationale": "The retrieval output is enough.",
            "response": "Completed.",
            "tool_name": "",
            "tool_input": {},
        }

    def generate_text(self, prompt: str, *, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 4096) -> str:
        return "unused"

    def provider_name(self) -> str:
        return "stub-valid-null-optionals"

    def resolved_model_name(self) -> str:
        return "stub-valid-null-optionals-model"

    def last_request_metadata(self) -> dict:
        return {}


class StubMixedRuntimePlanner(ReasoningClient):
    mode = "stub_mixed_runtime"

    def __init__(self) -> None:
        self.calls = 0

    def generate_json(
        self,
        prompt: str,
        strict: bool = False,
        validator=None,
        max_tokens: int = 4096,
        response_format=None,
        tools=None,
        tool_choice=None,
    ) -> dict:
        self.calls += 1
        if self.calls == 1:
            return {
                "action": "tool",
                "rationale": "Search the wiki first.",
                "response": "",
                "tool_name": "web_search_mediawiki_search",
                "tool_input": {
                    "base_url": "https://en.wikipedia.org",
                    "query": "Frankenstein novel creature creator",
                    "max_results": 1,
                },
            }
        if self.calls == 2:
            return {
                "action": "tool",
                "rationale": "Fetch the top wiki page.",
                "response": "",
                "tool_name": "web_search_fetch_document",
                "tool_input": {
                    "url": "https://en.wikipedia.org/wiki/Frankenstein",
                },
            }
        if self.calls == 3:
            return {
                "action": "tool",
                "rationale": "Persist the extracted note for reuse.",
                "response": "",
                "tool_name": "persistence_upsert_provider_config",
                "tool_input": {
                    "provider_name": "mixed-runtime-test",
                    "payload": {
                        "summary": "Victor Frankenstein creates the creature in Mary Shelley's Frankenstein."
                    },
                },
            }
        if self.calls == 4:
            return {
                "action": "tool",
                "rationale": "Read the persisted note back through the runtime.",
                "response": "",
                "tool_name": "persistence_get_provider_config",
                "tool_input": {
                    "provider_name": "mixed-runtime-test",
                },
            }
        return {
            "action": "respond",
            "rationale": "The mixed-runtime flow completed successfully.",
            "response": "Victor Frankenstein creates the creature in Mary Shelley's Frankenstein.",
            "tool_name": "",
            "tool_input": {},
        }

    def generate_text(self, prompt: str, *, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 4096) -> str:
        return "unused"

    def provider_name(self) -> str:
        return "stub-mixed-runtime"

    def resolved_model_name(self) -> str:
        return "stub-mixed-runtime-model"

    def last_request_metadata(self) -> dict:
        return {}


class StubWrongRetrievalResponder(ReasoningClient):
    mode = "stub_wrong_retrieval_responder"

    def __init__(self, index_ref: dict[str, object]) -> None:
        self.calls = 0
        self.index_ref = dict(index_ref)

    def generate_json(
        self,
        prompt: str,
        strict: bool = False,
        validator=None,
        max_tokens: int = 4096,
        response_format=None,
        tools=None,
        tool_choice=None,
    ) -> dict:
        self.calls += 1
        if self.calls == 1:
            return {
                "action": "tool",
                "rationale": "Run retrieval first.",
                "response": "",
                "tool_name": "retrieval_query_documents",
                "tool_input": {
                    "index_ref": dict(self.index_ref),
                    "query_text": "What happens right after Victor Frankenstein creates the creature?",
                    "top_k": 2,
                    "allowed_types": [],
                    "character_bias": [],
                    "metadata_filters": {},
                },
            }
        return {
            "action": "respond",
            "rationale": "Use the retrieval result.",
            "response": "The creature confronts Victor.",
            "tool_name": "",
            "tool_input": {},
        }

    def generate_text(self, prompt: str, *, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 4096) -> str:
        return "unused"

    def provider_name(self) -> str:
        return "stub-wrong-retrieval-responder"

    def resolved_model_name(self) -> str:
        return "stub-wrong-retrieval-responder-model"

    def last_request_metadata(self) -> dict:
        return {}


class StubPrematureMixedRuntimeResponder(ReasoningClient):
    mode = "stub_premature_mixed_runtime"

    def __init__(self) -> None:
        self.calls = 0

    def generate_json(
        self,
        prompt: str,
        strict: bool = False,
        validator=None,
        max_tokens: int = 4096,
        response_format=None,
        tools=None,
        tool_choice=None,
    ) -> dict:
        self.calls += 1
        if self.calls == 1:
            return {
                "action": "tool",
                "rationale": "Search the wiki first.",
                "response": "",
                "tool_name": "web_search_mediawiki_search",
                "tool_input": {
                    "base_url": "https://en.wikipedia.org",
                    "query": "who creates Frankenstein's monster",
                    "max_results": 1,
                },
            }
        return {
            "action": "respond",
            "rationale": "Answer from the wiki page.",
            "response": "Mary Shelley created Frankenstein's monster.",
            "tool_name": "",
            "tool_input": {},
        }

    def generate_text(self, prompt: str, *, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 4096) -> str:
        return "unused"

    def provider_name(self) -> str:
        return "stub-premature-mixed-runtime"

    def resolved_model_name(self) -> str:
        return "stub-premature-mixed-runtime-model"

    def last_request_metadata(self) -> dict:
        return {}


class StubPrematureRetrievalProviderResponder(ReasoningClient):
    mode = "stub_premature_retrieval_provider"

    def __init__(self, index_ref: dict[str, object]) -> None:
        self.calls = 0
        self.index_ref = dict(index_ref)

    def generate_json(
        self,
        prompt: str,
        strict: bool = False,
        validator=None,
        max_tokens: int = 4096,
        response_format=None,
        tools=None,
        tool_choice=None,
    ) -> dict:
        self.calls += 1
        if self.calls == 1:
            return {
                "action": "tool",
                "rationale": "Query retrieval first.",
                "response": "",
                "tool_name": "retrieval_query_documents",
                "tool_input": {
                    "index_ref": dict(self.index_ref),
                    "query_text": "Who creates Frankenstein's monster?",
                    "top_k": 1,
                    "allowed_types": [],
                    "character_bias": [],
                    "metadata_filters": {},
                },
            }
        return {
            "action": "respond",
            "rationale": "The provider state should already be enough.",
            "response": "Victor Frankenstein creates Frankenstein's monster.",
            "tool_name": "",
            "tool_input": {},
        }

    def generate_text(self, prompt: str, *, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 4096) -> str:
        return "unused"

    def provider_name(self) -> str:
        return "stub-premature-retrieval-provider"

    def resolved_model_name(self) -> str:
        return "stub-premature-retrieval-provider-model"

    def last_request_metadata(self) -> dict:
        return {}


class StubPostSequenceLoopPlanner(ReasoningClient):
    mode = "stub_post_sequence_loop"

    def __init__(self) -> None:
        self.calls = 0

    def generate_json(
        self,
        prompt: str,
        strict: bool = False,
        validator=None,
        max_tokens: int = 4096,
        response_format=None,
        tools=None,
        tool_choice=None,
    ) -> dict:
        self.calls += 1
        if self.calls == 1:
            return {
                "action": "tool",
                "rationale": "Search the wiki first.",
                "response": "",
                "tool_name": "web_search_mediawiki_search",
                "tool_input": {"base_url": "https://en.wikipedia.org", "query": "who creates Frankenstein's monster", "max_results": 5},
            }
        if self.calls == 2:
            return {
                "action": "tool",
                "rationale": "Fetch the page.",
                "response": "",
                "tool_name": "web_search_fetch_document",
                "tool_input": {"url": "https://en.wikipedia.org/wiki/Frankenstein%27s_monster"},
            }
        if self.calls == 3:
            return {
                "action": "tool",
                "rationale": "Persist the summary.",
                "response": "",
                "tool_name": "persistence_upsert_provider_config",
                "tool_input": {"provider_name": "loop-test", "payload": {"summary": "Victor Frankenstein creates Frankenstein's monster."}},
            }
        if self.calls == 4:
            return {
                "action": "tool",
                "rationale": "Read the summary back.",
                "response": "",
                "tool_name": "persistence_get_provider_config",
                "tool_input": {"provider_name": "loop-test"},
            }
        return {
            "action": "tool",
            "rationale": "Search again unnecessarily.",
            "response": "",
            "tool_name": "web_search_mediawiki_search",
            "tool_input": {"base_url": "https://en.wikipedia.org", "query": "who creates Frankenstein's monster", "max_results": 5},
        }

    def generate_text(self, prompt: str, *, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 4096) -> str:
        return "unused"

    def provider_name(self) -> str:
        return "stub-post-sequence-loop"

    def resolved_model_name(self) -> str:
        return "stub-post-sequence-loop-model"

    def last_request_metadata(self) -> dict:
        return {}


class StubPlannerWithReasoningTool(ReasoningClient):
    mode = "stub_planner"

    def __init__(self) -> None:
        self.calls = 0

    def generate_json(
        self,
        prompt: str,
        strict: bool = False,
        validator=None,
        max_tokens: int = 4096,
        response_format=None,
        tools=None,
        tool_choice=None,
    ) -> dict:
        self.calls += 1
        if self.calls == 1:
            return {
                "action": "tool",
                "rationale": "Use the reasoning tool to draft the answer.",
                "response": "",
                "tool_name": "reasoning_generate_text",
                "tool_input": {
                    "prompt": "Summarize why LangGraph is useful for stateful orchestration in one sentence.",
                    "system_prompt": "Be concise and direct.",
                    "temperature": 0.0,
                    "max_tokens": 120,
                },
            }
        return {
            "action": "respond",
            "rationale": "The reasoning tool already produced the requested draft.",
            "response": "LangGraph is useful because it gives explicit stateful orchestration for tool-using agents.",
            "tool_name": "",
            "tool_input": {},
        }

    def generate_text(self, prompt: str, *, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 4096) -> str:
        return "unused"

    def provider_name(self) -> str:
        return "stub-planner"

    def resolved_model_name(self) -> str:
        return "stub-planner-model"

    def last_request_metadata(self) -> dict:
        return {}


class StubResumableReasoningClient(ReasoningClient):
    mode = "stub_resumable"

    def __init__(self) -> None:
        self.calls = 0

    def generate_json(
        self,
        prompt: str,
        strict: bool = False,
        validator=None,
        max_tokens: int = 4096,
        response_format=None,
        tools=None,
        tool_choice=None,
    ) -> dict:
        self.calls += 1
        if self.calls == 1:
            return {
                "action": "tool",
                "rationale": "Ensure the resumable bucket exists.",
                "response": "",
                "tool_name": "persistence_ensure_bucket",
                "tool_input": {
                    "bucket_name": "resume-outputs",
                    "public": False,
                },
            }
        if self.calls == 2:
            return {
                "action": "tool",
                "rationale": "Store progress before responding.",
                "response": "",
                "tool_name": "persistence_upload_text_object",
                "tool_input": {
                    "bucket_name": "resume-outputs",
                    "object_path": "agent_outputs/resume.txt",
                    "text": "checkpointed",
                },
            }
        return {
            "action": "respond",
            "rationale": "Resume from the stored checkpoint.",
            "response": "Resumed successfully.",
            "tool_name": "",
            "tool_input": {},
        }

    def generate_text(self, prompt: str, *, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 4096) -> str:
        return "unused"

    def provider_name(self) -> str:
        return "stub-resumable"

    def resolved_model_name(self) -> str:
        return "stub-resumable-model"

    def last_request_metadata(self) -> dict:
        return {}


class StubPersistencePlanner(ReasoningClient):
    mode = "stub_persistence"

    def __init__(self) -> None:
        self.calls = 0

    def generate_json(
        self,
        prompt: str,
        strict: bool = False,
        validator=None,
        max_tokens: int = 4096,
        response_format=None,
        tools=None,
        tool_choice=None,
    ) -> dict:
        self.calls += 1
        if self.calls == 1:
            return {
                "action": "tool",
                "rationale": "Create the series first.",
                "response": "",
                "tool_name": "persistence_upsert_series",
                "tool_input": {
                    "series_id": "series-graph",
                    "title": "Graph Series",
                    "metadata": {"scope": "test"},
                },
            }
        if self.calls == 2:
            return {
                "action": "tool",
                "rationale": "Store vector documents next.",
                "response": "",
                "tool_name": "persistence_upsert_vector_documents",
                "tool_input": {
                    "namespace": "graph-runtime",
                    "documents": [
                        {
                            "document_id": "doc-1",
                            "content": "Nesta trains in the library.",
                            "summary": "Training scene",
                            "metadata": {"scope": "test"},
                            "embedding": [0.9, 0.1, 0.2, 0.3],
                        }
                    ],
                },
            }
        if self.calls == 3:
            return {
                "action": "tool",
                "rationale": "Create a storage bucket before writing an object.",
                "response": "",
                "tool_name": "persistence_ensure_bucket",
                "tool_input": {
                    "bucket_name": "graph-bucket",
                    "public": False,
                },
            }
        if self.calls == 4:
            return {
                "action": "tool",
                "rationale": "Write a text object through the same runtime.",
                "response": "",
                "tool_name": "persistence_upload_text_object",
                "tool_input": {
                    "bucket_name": "graph-bucket",
                    "object_path": "notes/runtime.txt",
                    "text": "unified storage works",
                },
            }
        if self.calls == 5:
            return {
                "action": "tool",
                "rationale": "Query the vector namespace to confirm retrieval.",
                "response": "",
                "tool_name": "persistence_query_vector_documents",
                "tool_input": {
                    "namespace": "graph-runtime",
                    "query_vector": [0.91, 0.1, 0.18, 0.31],
                    "top_k": 1,
                    "metadata_filters": {"scope": "test"},
                },
            }
        return {
            "action": "respond",
            "rationale": "The persistence runtime completed both structured and vector operations.",
            "response": "Persistence runtime completed successfully.",
            "tool_name": "",
            "tool_input": {},
        }

    def generate_text(self, prompt: str, *, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 4096) -> str:
        return "unused"

    def provider_name(self) -> str:
        return "stub-persistence"

    def resolved_model_name(self) -> str:
        return "stub-persistence-model"

    def last_request_metadata(self) -> dict:
        return {}


class StubResponseFormatCapturingPlanner(ReasoningClient):
    mode = "stub_response_format_capture"

    def __init__(self) -> None:
        self.calls = 0
        self.last_response_format = None

    def generate_json(
        self,
        prompt: str,
        strict: bool = False,
        validator=None,
        max_tokens: int = 4096,
        response_format=None,
        tools=None,
        tool_choice=None,
    ) -> dict:
        self.calls += 1
        self.last_response_format = response_format
        return {
            "action": "respond",
            "rationale": "Schema capture complete.",
            "response": "Completed.",
            "tool_name": "",
            "tool_input": {},
        }

    def generate_text(self, prompt: str, *, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 4096) -> str:
        return "unused"

    def provider_name(self) -> str:
        return "stub-response-format-capture"

    def resolved_model_name(self) -> str:
        return "stub-response-format-capture-model"

    def last_request_metadata(self) -> dict:
        return {}


def test_persistence_runtime_exposes_object_storage_tools(tmp_path: Path) -> None:
    profile = PersistenceProfile(
        name="test-storage-tools",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'storage-tools.sqlite3'}",
        local_storage_root_dir=str(tmp_path / "unified_storage"),
    )
    client = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=profile),
        profile=profile,
    )
    client.initialize()
    tools = {tool.name: tool for tool in client.as_langgraph_tools()}
    tools["persistence_ensure_bucket"].invoke({"bucket_name": "notes-bucket", "public": False})
    result = tools["persistence_upload_text_object"].invoke(
        {
            "bucket_name": "notes-bucket",
            "object_path": "notes/hello.txt",
            "text": "native tool integration",
        }
    )
    download = tools["persistence_download_text_object"].invoke(
        {
            "bucket_name": "notes-bucket",
            "object_path": "notes/hello.txt",
        }
    )
    assert result["ok"] is True
    assert result["data"]["bytes_written"] > 0
    assert result["trace"]["component"] == "persistence_runtime"
    assert download["data"]["text"] == "native tool integration"


def test_retrieval_runtime_exposes_langgraph_tools(tmp_path: Path) -> None:
    persistence_profile = PersistenceProfile(
        name="test-retrieval-persistence",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'retrieval-runtime.sqlite3'}",
    )
    persistence_client = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=persistence_profile),
        profile=persistence_profile,
    )
    persistence_client.initialize()
    client = RetrievalRuntimeClient(
        profile=RetrievalProfile(
            name="test_retrieval",
            mode="document_index",
            embedding_model="stub-model",
            ollama_embed_url="http://localhost:11434/api/embed",
            batch_size=8,
        ),
        config=RetrievalRuntimeConfig(
            profile=RetrievalProfile(
                name="test_retrieval",
                mode="document_index",
                embedding_model="stub-model",
                ollama_embed_url="http://localhost:11434/api/embed",
                batch_size=8,
            )
        ),
        embedder=lambda texts: [[float(index + 1)] * 4 for index, _ in enumerate(texts)],
        persistence_client=persistence_client,
    )
    tools = {tool.name: tool for tool in client.as_langgraph_tools()}
    index_result = tools["retrieval_ensure_document_index"].invoke(
        {
            "series_id": "series-1",
            "scope_key": "scope-1",
            "documents": [
                {"document_id": "doc-1", "text": "Nesta trains in the library.", "summary": "Training scene", "source_type": "scene", "metadata": {"characters": ["Nesta"]}},
                {"document_id": "doc-2", "text": "Cassian argues in the war room.", "summary": "Argument scene", "source_type": "scene", "metadata": {"characters": ["Cassian"]}},
            ],
        }
    )
    query_result = tools["retrieval_query_documents"].invoke(
        {
            "index_ref": index_result["data"]["index_ref"],
            "query_text": "Who is training?",
            "top_k": 1,
        }
    )
    assert index_result["ok"] is True
    assert query_result["ok"] is True
    assert query_result["data"]["result_count"] == 1
    assert query_result["data"]["results"][0]["document_id"] in {"doc-1", "doc-2"}
    assert "excerpt" in query_result["data"]["results"][0]
    assert not (tmp_path / "indices" / "series-1" / "scope-1" / "index.json").exists()
    rows = persistence_client.vectors.list_documents("retrieval.series-1.scope-1")
    assert len(rows) == 2


def test_langgraph_runtime_can_use_persistence_runtime_tools(tmp_path: Path) -> None:
    profile = PersistenceProfile(
        name="test-persistence",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'langgraph-persistence.sqlite3'}",
        local_storage_root_dir=str(tmp_path / "langgraph-unified-storage"),
    )
    persistence_runtime = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=profile),
        profile=profile,
    )
    persistence_runtime.initialize()

    runtime = _runtime(
        reasoning_client=StubPersistencePlanner(),
        tools=persistence_runtime.as_langgraph_tools(),
        system_prompt="You are a test persistence orchestration agent.",
        checkpoint_engine=persistence_runtime.engine,
    )
    result = runtime.invoke(user_input="Store structured and vector data.", max_steps=6)

    assert result.final_output == "Persistence runtime completed successfully."
    assert len(result.tool_history) == 5
    assert result.tool_history[0].tool_name == "persistence_upsert_series"
    assert result.tool_history[1].tool_name == "persistence_upsert_vector_documents"
    assert result.tool_history[2].tool_name == "persistence_ensure_bucket"
    assert result.tool_history[3].tool_name == "persistence_upload_text_object"
    assert result.tool_history[4].tool_name == "persistence_query_vector_documents"
    assert result.tool_history[4].tool_output.ok is True
    assert result.tool_history[4].tool_output.data["results"][0]["document_id"] == "doc-1"
    assert result.tool_history[0].trace.run_id
    assert result.tool_history[0].trace.run_id == result.tool_history[4].trace.run_id
    assert len(result.planner_history) == 6
    assert result.planner_history[0].decision is not None
    assert result.planner_history[0].raw_payload["action"] == "tool"


def test_persistence_runtime_rejects_object_path_escape(tmp_path: Path) -> None:
    profile = PersistenceProfile(
        name="test-storage-escape",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'storage-escape.sqlite3'}",
        local_storage_root_dir=str(tmp_path / "unified_storage"),
    )
    client = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=profile),
        profile=profile,
    )
    client.initialize()
    client.objects.ensure_bucket("escape-bucket")
    try:
        client.objects.upload_text("escape-bucket", "../escape.txt", "nope")
    except ValueError as exc:
        assert "Parent traversal is not allowed" in str(exc)
    else:
        raise AssertionError("Expected path escape to be rejected.")


def test_langgraph_runtime_executes_native_runtime_tools(tmp_path: Path) -> None:
    profile = PersistenceProfile(
        name="test_storage",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'native-runtime.sqlite3'}",
        local_storage_root_dir=str(tmp_path / "native_storage"),
    )
    storage_client = create_persistence_client(
        profile=profile,
        config=PersistenceRuntimeConfig(profile=profile),
    )
    storage_client.initialize()
    runtime = _runtime(
        reasoning_client=StubReasoningClient(),
        tools=storage_client.as_langgraph_tools(),
        system_prompt="You are the SAGA orchestration agent.",
        checkpoint_engine=storage_client.engine,
    )
    result = runtime.invoke(user_input="Save a note for later.")
    assert result.final_output == "Stored the note successfully."
    assert result.steps == 4
    assert len(result.tool_history) == 3
    assert result.tool_history[0].tool_name == "persistence_ensure_bucket"
    assert result.tool_history[1].tool_name == "persistence_upload_text_object"
    assert result.tool_history[2].tool_name == "persistence_download_text_object"
    assert result.tool_history[0].trace.run_id == result.tool_history[2].trace.run_id
    assert len(result.planner_history) == 4
    assert result.summary.status == "ok"
    assert result.summary.thread_id
    assert result.summary.run_id == result.tool_history[0].trace.run_id
    assert result.summary.planner_steps == 4
    assert result.summary.tool_steps == 3
    assert result.summary.successful_tool_steps == 3
    assert result.summary.failed_tool_steps == 0
    assert result.summary.latest_tool_name == "persistence_download_text_object"
    assert result.summary.latest_trace_id == result.tool_history[2].trace.trace_id
    assert result.tool_history[0].trace.events[0].event_type == "runtime_tool.started"
    assert result.tool_history[0].trace.events[-1].event_type == "runtime_tool.succeeded"
    assert result.tool_history[2].trace.events[-1].details["tool_name"] == "persistence_download_text_object"
    report = result.to_report_payload()
    assert report["report_type"] == "agent_execution_report"
    assert report["summary"]["status"] == "ok"
    assert report["tool_history"][2]["tool_name"] == "persistence_download_text_object"
    assert report["tool_history"][0]["trace"]["events"][0]["event_type"] == "runtime_tool.started"
    assert storage_client.objects.download_text("agent-outputs", "agent_outputs/note.txt") == "hello from langgraph"


def test_langgraph_runtime_resumes_existing_thread_state(tmp_path: Path) -> None:
    profile = PersistenceProfile(
        name="test_storage",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'resume-runtime.sqlite3'}",
        local_storage_root_dir=str(tmp_path / "resume_storage"),
    )
    storage_client = create_persistence_client(
        profile=profile,
        config=PersistenceRuntimeConfig(profile=profile),
    )
    storage_client.initialize()
    runtime = _runtime(
        reasoning_client=StubResumableReasoningClient(),
        tools=storage_client.as_langgraph_tools(),
        system_prompt="You are a resumable orchestration agent.",
        checkpoint_engine=storage_client.engine,
    )
    first = runtime.invoke(user_input="Start resumable run.", max_steps=1, thread_id="resume-thread")
    second = runtime.invoke(user_input="Continue resumable run.", max_steps=2, thread_id="resume-thread")

    assert "exceeded the configured step limit" in first.final_output
    assert len(first.tool_history) == 1
    assert first.summary.status == "max_steps_exceeded"
    assert first.summary.remaining_required_tools == []
    assert second.final_output == "Resumed successfully."
    assert len(second.tool_history) == 2
    assert second.tool_history[0].tool_name == "persistence_ensure_bucket"
    assert second.tool_history[1].tool_name == "persistence_upload_text_object"
    assert second.tool_history[0].trace.run_id == "resume-thread"
    assert second.summary.status == "ok"
    assert second.summary.thread_id == "resume-thread"
    assert second.summary.run_id == "resume-thread"
    assert second.summary.tool_steps == 2
    assert storage_client.objects.download_text("resume-outputs", "agent_outputs/resume.txt") == "checkpointed"


def test_reasoning_runtime_exposes_langgraph_tools() -> None:
    profile = ReasoningProfile(name="test_reasoning", mode=ReasoningRuntimeClient.MODE_GPT_OSS)
    client = ReasoningRuntimeClient(
        profile=profile,
        config=ReasoningRuntimeConfig(profiles={profile.name: profile}),
    )

    def fake_generate_text(prompt: str, *, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 4096) -> str:
        return "LangGraph provides explicit state transitions for agents."

    def fake_last_request_metadata() -> dict:
        return {"provider": "stubbed"}

    client.generate_text = fake_generate_text  # type: ignore[method-assign]
    client.last_request_metadata = fake_last_request_metadata  # type: ignore[method-assign]

    tools = {tool.name: tool for tool in client.as_langgraph_tools()}
    result = tools["reasoning_generate_text"].invoke(
        {
            "prompt": "Why is LangGraph useful?",
            "system_prompt": "Be concise.",
            "temperature": 0.0,
            "max_tokens": 80,
        }
    )
    assert result["ok"] is True
    assert "LangGraph provides explicit state transitions" in result["data"]["text"]
    assert result["data"]["provider"] == "ollama"
    assert result["trace"]["component"] == "reasoning_runtime"


def test_langgraph_runtime_can_use_reasoning_tool() -> None:
    profile = ReasoningProfile(name="test_reasoning", mode=ReasoningRuntimeClient.MODE_GPT_OSS)
    reasoning_runtime = ReasoningRuntimeClient(
        profile=profile,
        config=ReasoningRuntimeConfig(profiles={profile.name: profile}),
    )

    def fake_generate_text(prompt: str, *, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 4096) -> str:
        return "LangGraph is useful because it gives explicit stateful orchestration for tool-using agents."

    def fake_last_request_metadata() -> dict:
        return {"provider": "stubbed"}

    reasoning_runtime.generate_text = fake_generate_text  # type: ignore[method-assign]
    reasoning_runtime.last_request_metadata = fake_last_request_metadata  # type: ignore[method-assign]

    runtime = _runtime(
        reasoning_client=StubPlannerWithReasoningTool(),
        tools=reasoning_runtime.as_langgraph_tools(),
        system_prompt="You are a test orchestration agent.",
        allow_in_memory_checkpointer=True,
    )
    result = runtime.invoke(user_input="Explain why LangGraph is useful.", max_steps=4)
    assert "LangGraph is useful" in result.final_output
    assert len(result.tool_history) == 1
    assert result.tool_history[0].tool_name == "reasoning_generate_text"
    assert result.tool_history[0].tool_output.ok is True
    assert "stateful orchestration" in result.tool_history[0].tool_output.data["text"]
    assert len(result.planner_history) == 2


def test_langgraph_runtime_coerces_near_valid_planner_tool_payload(tmp_path: Path) -> None:
    persistence_profile = PersistenceProfile(
        name="test-retrieval-coercion",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'retrieval-coercion.sqlite3'}",
    )
    persistence_client = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=persistence_profile),
        profile=persistence_profile,
    )
    persistence_client.initialize()
    retrieval_client = RetrievalRuntimeClient(
        profile=RetrievalProfile(
            name="test_retrieval_coercion",
            mode="document_index",
            embedding_model="stub-model",
            ollama_embed_url="http://localhost:11434/api/embed",
            batch_size=8,
        ),
        config=RetrievalRuntimeConfig(
            profile=RetrievalProfile(
                name="test_retrieval_coercion",
                mode="document_index",
                embedding_model="stub-model",
                ollama_embed_url="http://localhost:11434/api/embed",
                batch_size=8,
            )
        ),
        embedder=lambda texts: [[float(index + 1)] * 4 for index, _ in enumerate(texts)],
        persistence_client=persistence_client,
    )
    index_payload = retrieval_client.ensure_document_index(
        series_id="series-coercion",
        scope_key="scope-coercion",
        documents=[
            {
                "document_id": "doc-1",
                "text": "Victor Frankenstein creates a creature.",
                "summary": "Creation scene",
                "source_type": "scene",
                "metadata": {"characters": ["Victor Frankenstein", "Creature"]},
            }
        ],
    )

    runtime = _runtime(
        reasoning_client=StubMalformedPlanner(),
        tools=retrieval_client.as_langgraph_tools(),
        system_prompt="You are a resilient orchestration agent.",
        checkpoint_engine=persistence_client.engine,
    )
    result = runtime.invoke(
        user_input="Who is the creature created by Victor Frankenstein?",
        context={
            "index_ref": {
                "index_id": index_payload.get("index_id"),
                "series_id": index_payload.get("series_id"),
                "scope_key": index_payload.get("scope_key"),
                "fingerprint": index_payload.get("fingerprint"),
            }
        },
        max_steps=4,
    )

    assert result.final_output == "Retrieved the indexed document successfully."
    assert len(result.tool_history) == 1
    assert result.tool_history[0].tool_name == "retrieval_query_documents"
    assert result.tool_history[0].tool_input["query_text"] == "Who is the creature created by Victor Frankenstein?"
    assert result.tool_history[0].tool_input["index_ref"]["series_id"] == "series-coercion"
    assert result.tool_history[0].tool_output.ok is True


def test_langgraph_runtime_falls_back_to_retrieval_excerpt_when_planner_breaks_after_tool(tmp_path: Path) -> None:
    persistence_profile = PersistenceProfile(
        name="test-retrieval-fallback",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'retrieval-fallback.sqlite3'}",
    )
    persistence_client = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=persistence_profile),
        profile=persistence_profile,
    )
    persistence_client.initialize()
    retrieval_client = RetrievalRuntimeClient(
        profile=RetrievalProfile(
            name="test_retrieval_fallback",
            mode="document_index",
            embedding_model="stub-model",
            ollama_embed_url="http://localhost:11434/api/embed",
            batch_size=8,
        ),
        config=RetrievalRuntimeConfig(
            profile=RetrievalProfile(
                name="test_retrieval_fallback",
                mode="document_index",
                embedding_model="stub-model",
                ollama_embed_url="http://localhost:11434/api/embed",
                batch_size=8,
            )
        ),
        embedder=lambda texts: [[float(index + 1)] * 4 for index, _ in enumerate(texts)],
        persistence_client=persistence_client,
    )
    index_payload = retrieval_client.ensure_document_index(
        series_id="series-fallback",
        scope_key="scope-fallback",
        documents=[
            {
                "document_id": "doc-1",
                "text": "Victor Frankenstein creates a living creature from assembled body parts and abandons it immediately.",
                "summary": "Creation and abandonment scene",
                "source_type": "scene",
                "metadata": {"characters": ["Victor Frankenstein", "Creature"]},
            }
        ],
    )
    runtime = _runtime(
        reasoning_client=StubFallbackAfterToolPlanner(),
        tools=retrieval_client.as_langgraph_tools(),
        system_prompt="You are a resilient orchestration agent.",
        checkpoint_engine=persistence_client.engine,
    )
    result = runtime.invoke(
        user_input="Who is the creature created by Victor Frankenstein?",
        context={
            "index_ref": {
                "index_id": index_payload.get("index_id"),
                "series_id": index_payload.get("series_id"),
                "scope_key": index_payload.get("scope_key"),
                "fingerprint": index_payload.get("fingerprint"),
            }
        },
        max_steps=4,
    )

    assert "abandons it immediately" in result.final_output
    assert len(result.tool_history) == 1


def test_langgraph_runtime_stops_repeating_identical_successful_tool_calls(tmp_path: Path) -> None:
    persistence_profile = PersistenceProfile(
        name="test-retrieval-repeat",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'retrieval-repeat.sqlite3'}",
    )
    persistence_client = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=persistence_profile),
        profile=persistence_profile,
    )
    persistence_client.initialize()
    retrieval_client = RetrievalRuntimeClient(
        profile=RetrievalProfile(
            name="test_retrieval_repeat",
            mode="document_index",
            embedding_model="stub-model",
            ollama_embed_url="http://localhost:11434/api/embed",
            batch_size=8,
        ),
        config=RetrievalRuntimeConfig(
            profile=RetrievalProfile(
                name="test_retrieval_repeat",
                mode="document_index",
                embedding_model="stub-model",
                ollama_embed_url="http://localhost:11434/api/embed",
                batch_size=8,
            )
        ),
        embedder=lambda texts: [[float(index + 1)] * 4 for index, _ in enumerate(texts)],
        persistence_client=persistence_client,
    )
    index_payload = retrieval_client.ensure_document_index(
        series_id="series-repeat",
        scope_key="scope-repeat",
        documents=[
            {
                "document_id": "doc-1",
                "text": "Victor Frankenstein creates a living creature from assembled body parts and abandons it immediately.",
                "summary": "Creation and abandonment scene",
                "source_type": "scene",
                "metadata": {"characters": ["Victor Frankenstein", "Creature"]},
            }
        ],
    )
    index_ref = {
        "index_id": index_payload.get("index_id"),
        "series_id": index_payload.get("series_id"),
        "scope_key": index_payload.get("scope_key"),
        "fingerprint": index_payload.get("fingerprint"),
    }
    runtime = _runtime(
        reasoning_client=StubRepeatingToolPlanner(index_ref),
        tools=retrieval_client.as_langgraph_tools(),
        system_prompt="You are a resilient orchestration agent.",
        checkpoint_engine=persistence_client.engine,
    )
    result = runtime.invoke(
        user_input="Who is the creature created by Victor Frankenstein?",
        context={"index_ref": index_ref},
        max_steps=4,
    )

    assert "abandons it immediately" in result.final_output
    assert len(result.tool_history) == 1


def test_langgraph_runtime_normalizes_null_optional_tool_fields(tmp_path: Path) -> None:
    persistence_profile = PersistenceProfile(
        name="test-retrieval-null-optionals",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'retrieval-null-optionals.sqlite3'}",
    )
    persistence_client = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=persistence_profile),
        profile=persistence_profile,
    )
    persistence_client.initialize()
    retrieval_client = RetrievalRuntimeClient(
        profile=RetrievalProfile(
            name="test_retrieval_null_optionals",
            mode="document_index",
            embedding_model="stub-model",
            ollama_embed_url="http://localhost:11434/api/embed",
            batch_size=8,
        ),
        config=RetrievalRuntimeConfig(
            profile=RetrievalProfile(
                name="test_retrieval_null_optionals",
                mode="document_index",
                embedding_model="stub-model",
                ollama_embed_url="http://localhost:11434/api/embed",
                batch_size=8,
            )
        ),
        embedder=lambda texts: [[float(index + 1)] * 4 for index, _ in enumerate(texts)],
        persistence_client=persistence_client,
    )
    index_payload = retrieval_client.ensure_document_index(
        series_id="series-null-optionals",
        scope_key="scope-null-optionals",
        documents=[
            {
                "document_id": "doc-1",
                "text": "Victor Frankenstein creates a living creature from assembled body parts and abandons it immediately.",
                "summary": "Creation and abandonment scene",
                "source_type": "scene",
                "metadata": {"characters": ["Victor Frankenstein", "Creature"]},
            }
        ],
    )
    index_ref = {
        "index_id": index_payload.get("index_id"),
        "series_id": index_payload.get("series_id"),
        "scope_key": index_payload.get("scope_key"),
        "fingerprint": index_payload.get("fingerprint"),
    }
    runtime = _runtime(
        reasoning_client=StubValidPlannerWithNullOptionals(index_ref),
        tools=retrieval_client.as_langgraph_tools(),
        system_prompt="You are a resilient orchestration agent.",
        checkpoint_engine=persistence_client.engine,
    )
    result = runtime.invoke(
        user_input="Who is the creature created by Victor Frankenstein?",
        context={"index_ref": index_ref},
        max_steps=4,
    )

    assert result.final_output == "Completed."
    assert len(result.tool_history) == 1
    assert result.tool_history[0].tool_input["allowed_types"] == []
    assert result.tool_history[0].tool_input["character_bias"] == []
    assert result.tool_history[0].tool_input["metadata_filters"] == {}


def test_langgraph_runtime_regrounds_wrong_planner_response_to_top_retrieval_result(tmp_path: Path) -> None:
    persistence_profile = PersistenceProfile(
        name="test-retrieval-regrounding",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'retrieval-regrounding.sqlite3'}",
    )
    persistence_client = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=persistence_profile),
        profile=persistence_profile,
    )
    persistence_client.initialize()
    retrieval_client = RetrievalRuntimeClient(
        profile=RetrievalProfile(
            name="test_retrieval_regrounding",
            mode="document_index",
            embedding_model="stub-model",
            ollama_embed_url="http://localhost:11434/api/embed",
            batch_size=8,
        ),
        config=RetrievalRuntimeConfig(
            profile=RetrievalProfile(
                name="test_retrieval_regrounding",
                mode="document_index",
                embedding_model="stub-model",
                ollama_embed_url="http://localhost:11434/api/embed",
                batch_size=8,
            )
        ),
        embedder=lambda texts: [[float(index + 1)] * 4 for index, _ in enumerate(texts)],
        persistence_client=persistence_client,
    )
    index_payload = retrieval_client.ensure_document_index(
        series_id="series-regrounding",
        scope_key="scope-regrounding",
        documents=[
            {
                "document_id": "doc-1",
                "text": "Victor Frankenstein creates a living creature from assembled body parts and abandons it immediately out of horror.",
                "summary": "Victor creates and abandons the creature.",
                "source_type": "scene",
                "metadata": {"characters": ["Victor Frankenstein", "Creature"]},
            },
            {
                "document_id": "doc-2",
                "text": "The creature later seeks companionship and confronts Victor about his suffering and isolation.",
                "summary": "The creature confronts Victor.",
                "source_type": "scene",
                "metadata": {"characters": ["Victor Frankenstein", "Creature"]},
            },
        ],
    )
    index_ref = {
        "index_id": index_payload.get("index_id"),
        "series_id": index_payload.get("series_id"),
        "scope_key": index_payload.get("scope_key"),
        "fingerprint": index_payload.get("fingerprint"),
    }
    runtime = _runtime(
        reasoning_client=StubWrongRetrievalResponder(index_ref),
        tools=retrieval_client.as_langgraph_tools(),
        system_prompt="You are a resilient orchestration agent.",
        checkpoint_engine=persistence_client.engine,
    )
    result = runtime.invoke(
        user_input="What happens right after Victor Frankenstein creates the creature?",
        context={"index_ref": index_ref},
        max_steps=4,
    )

    assert "abandons it immediately out of horror" in result.final_output
    assert len(result.tool_history) == 1


def test_langgraph_runtime_passes_explicit_planner_response_schema() -> None:
    planner = StubResponseFormatCapturingPlanner()
    runtime = _runtime(
        reasoning_client=planner,
        tools=[],
        system_prompt="You are a resilient orchestration agent.",
        allow_in_memory_checkpointer=True,
    )

    result = runtime.invoke(user_input="Say hello.", max_steps=2)

    assert result.final_output == "Completed."
    assert len(result.planner_history) == 1
    assert result.planner_history[0].decision is not None
    assert planner.last_response_format is not None
    assert planner.last_response_format["type"] == "json_schema"
    assert planner.last_response_format["json_schema"]["name"] == "agent_planner_decision"
    assert "properties" in planner.last_response_format["json_schema"]["schema"]


def test_langgraph_runtime_composes_web_search_and_persistence_tools(tmp_path: Path) -> None:
    persistence_profile = PersistenceProfile(
        name="test-mixed-runtime",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'mixed-runtime.sqlite3'}",
    )
    persistence_client = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=persistence_profile),
        profile=persistence_profile,
    )
    persistence_client.initialize()

    web_client = WebSearchRuntimeClient(
        profile=WebSearchProfile(name="test-web-search", mode="duckduckgo"),
        config=WebSearchRuntimeConfig(),
    )
    web_client.mediawiki_search = lambda base_url, query, max_results=5: [  # type: ignore[method-assign]
        SearchResult(
            title="Frankenstein",
            url="https://en.wikipedia.org/wiki/Frankenstein",
            snippet="Frankenstein is an 1818 novel by Mary Shelley.",
            source="wikipedia",
            rank=1,
        )
    ]
    web_client.fetch_document = lambda url, query="": WebDocument(  # type: ignore[method-assign]
        url=url,
        title="Frankenstein",
        summary="Victor Frankenstein creates the creature in Mary Shelley's novel Frankenstein.",
        excerpt="Victor Frankenstein creates the creature.",
        focus_text="Victor Frankenstein creates the creature.",
        query=query,
        evidence_sentences=[],
        text="Victor Frankenstein is the scientist who creates the creature in Mary Shelley's novel Frankenstein.",
        html="<html><body><p>Victor Frankenstein creates the creature.</p></body></html>",
        metadata={"status_code": 200},
    )

    runtime = _runtime(
        reasoning_client=StubMixedRuntimePlanner(),
        tools=[*web_client.as_langgraph_tools(), *persistence_client.as_langgraph_tools()],
        system_prompt="You are a resilient orchestration agent.",
        checkpoint_engine=persistence_client.engine,
    )
    result = runtime.invoke(
        user_input="Find who creates the creature in Frankenstein, persist the note, then answer.",
        max_steps=6,
    )

    assert result.error == ""
    assert "Victor Frankenstein creates the creature" in result.final_output
    assert [record.tool_name for record in result.tool_history] == [
        "web_search_mediawiki_search",
        "web_search_fetch_document",
        "persistence_upsert_provider_config",
        "persistence_get_provider_config",
    ]
    persisted = persistence_client.provider_configs.get_provider_config("mixed-runtime-test")
    assert persisted is not None
    assert persisted["payload"]["summary"] == "Victor Frankenstein creates the creature in Mary Shelley's Frankenstein."


def test_langgraph_runtime_required_tool_sequence_grounds_web_summary_into_persistence(tmp_path: Path) -> None:
    persistence_profile = PersistenceProfile(
        name="test-mixed-runtime-grounding",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'mixed-runtime-grounding.sqlite3'}",
    )
    persistence_client = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=persistence_profile),
        profile=persistence_profile,
    )
    persistence_client.initialize()

    web_client = WebSearchRuntimeClient(
        profile=WebSearchProfile(name="test-web-search", mode="duckduckgo"),
        config=WebSearchRuntimeConfig(),
    )
    web_client.mediawiki_search = lambda base_url, query, max_results=5: [  # type: ignore[method-assign]
        SearchResult(
            title="Victor Frankenstein",
            url="https://en.wikipedia.org/wiki/Victor_Frankenstein",
            snippet="Victor later regrets meddling with his own creature.",
            source="wikipedia",
            rank=1,
        ),
        SearchResult(
            title="Frankenstein's monster",
            url="https://en.wikipedia.org/wiki/Frankenstein%27s_monster",
            snippet="Frankenstein's monster is a fictional character.",
            source="wikipedia",
            rank=2,
        ),
    ]
    web_client.fetch_document = lambda url, query="": WebDocument(  # type: ignore[method-assign]
        url=url,
        title="Frankenstein's monster" if "monster" in url else "Victor Frankenstein",
        summary=(
            "Victor Frankenstein creates Frankenstein's monster from assembled body parts."
            if "monster" in url
            else "Victor Frankenstein is a fictional scientist who creates Frankenstein's monster."
        ),
        excerpt=(
            "Victor Frankenstein creates Frankenstein's monster from assembled body parts."
            if "monster" in url
            else "Victor Frankenstein is a fictional scientist who creates Frankenstein's monster."
        ),
        focus_text=(
            "Victor Frankenstein creates Frankenstein's monster from assembled body parts."
            if "monster" in url
            else "Victor Frankenstein is a fictional scientist who creates Frankenstein's monster."
        ),
        query=query,
        evidence_sentences=[],
        text=(
            "Frankenstein's monster is a fictional character in Mary Shelley's novel. "
            "Victor Frankenstein creates Frankenstein's monster from assembled body parts."
            if "monster" in url
            else "Victor Frankenstein is a fictional scientist who creates Frankenstein's monster."
        ),
        html="<html><body><p>Victor Frankenstein creates Frankenstein's monster.</p></body></html>",
        metadata={"status_code": 200},
    )

    runtime = _runtime(
        reasoning_client=StubPrematureMixedRuntimeResponder(),
        tools=[*web_client.as_langgraph_tools(), *persistence_client.as_langgraph_tools()],
        system_prompt="You are a resilient orchestration agent.",
        checkpoint_engine=persistence_client.engine,
    )
    result = runtime.invoke(
        user_input="Find who creates Frankenstein's monster, persist the note, read it back, then answer.",
        context={
            "required_tool_names": [
                "web_search_mediawiki_search",
                "web_search_fetch_document",
                "persistence_upsert_provider_config",
                "persistence_get_provider_config",
            ],
            "required_mediawiki_base_url": "https://en.wikipedia.org",
            "required_search_query": "who creates Frankenstein's monster",
            "required_provider_name": "mixed-runtime-grounding-test",
        },
        max_steps=8,
    )

    assert result.error == ""
    assert result.final_output == "Victor Frankenstein is a fictional scientist who creates Frankenstein's monster."
    assert [record.tool_name for record in result.tool_history] == [
        "web_search_mediawiki_search",
        "web_search_fetch_document",
        "persistence_upsert_provider_config",
        "persistence_get_provider_config",
    ]
    assert result.tool_history[0].tool_input["max_results"] == 5
    assert result.tool_history[1].tool_input["url"] == "https://en.wikipedia.org/wiki/Victor_Frankenstein"
    persisted = persistence_client.provider_configs.get_provider_config("mixed-runtime-grounding-test")
    assert persisted is not None
    assert persisted["payload"]["summary"] == "Victor Frankenstein is a fictional scientist who creates Frankenstein's monster."


def test_langgraph_runtime_required_sequence_composes_retrieval_with_provider_operational_state(tmp_path: Path) -> None:
    persistence_profile = PersistenceProfile(
        name="test-retrieval-provider-state",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'retrieval-provider-state.sqlite3'}",
    )
    persistence_client = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=persistence_profile),
        profile=persistence_profile,
    )
    persistence_client.initialize()
    retrieval_client = RetrievalRuntimeClient(
        profile=RetrievalProfile(
            name="test_retrieval_provider_state",
            mode="document_index",
            embedding_model="stub-model",
            ollama_embed_url="http://localhost:11434/api/embed",
            batch_size=8,
        ),
        config=RetrievalRuntimeConfig(
            profile=RetrievalProfile(
                name="test_retrieval_provider_state",
                mode="document_index",
                embedding_model="stub-model",
                ollama_embed_url="http://localhost:11434/api/embed",
                batch_size=8,
            )
        ),
        embedder=lambda texts: [[float(index + 1)] * 4 for index, _ in enumerate(texts)],
        persistence_client=persistence_client,
    )
    index_payload = retrieval_client.ensure_document_index(
        series_id="series-provider-state",
        scope_key="scope-provider-state",
        documents=[
            {
                "document_id": "doc-1",
                "text": "Victor Frankenstein creates Frankenstein's monster from assembled body parts and abandons it immediately.",
                "summary": "Victor Frankenstein creates Frankenstein's monster.",
                "source_type": "scene",
                "metadata": {"characters": ["Victor Frankenstein", "Creature"]},
            }
        ],
    )
    index_ref = {
        "index_id": index_payload.get("index_id"),
        "series_id": index_payload.get("series_id"),
        "scope_key": index_payload.get("scope_key"),
        "fingerprint": index_payload.get("fingerprint"),
    }
    runtime = _runtime(
        reasoning_client=StubPrematureRetrievalProviderResponder(index_ref),
        tools=[*retrieval_client.as_langgraph_tools(), *persistence_client.as_langgraph_tools()],
        system_prompt="You are a resilient orchestration agent.",
        checkpoint_engine=persistence_client.engine,
    )
    result = runtime.invoke(
        user_input="Find who creates Frankenstein's monster, persist the evidence, update provider status, read the provider operational state, then answer.",
        context={
            "index_ref": index_ref,
            "required_tool_names": [
                "retrieval_query_documents",
                "persistence_upsert_provider_config",
                "persistence_upsert_provider_status",
                "persistence_get_provider_operational_state",
            ],
            "required_provider_name": "retrieval-provider-test",
            "required_provider_payload": {
                "runtime_state": {
                    "active_token_name": "member-01",
                    "active_api_url": "https://image.example/api",
                }
            },
            "required_status_label": "member-01",
            "required_provider_status_payload": {
                "last_health_ok": True,
                "last_request_ok": True,
                "api_url": "https://image.example/api",
            },
        },
        max_steps=8,
        thread_id="retrieval-provider-thread",
    )

    assert result.error == ""
    assert result.final_output == "Provider retrieval-provider-test with active label member-01, ready labels member-01"
    assert [record.tool_name for record in result.tool_history] == [
        "retrieval_query_documents",
        "persistence_upsert_provider_config",
        "persistence_upsert_provider_status",
        "persistence_get_provider_operational_state",
    ]
    assert len(result.planner_history) == 5
    assert {record.trace.run_id for record in result.tool_history} == {"retrieval-provider-thread"}
    assert result.summary.status == "ok"
    assert result.summary.thread_id == "retrieval-provider-thread"
    assert result.summary.run_id == "retrieval-provider-thread"
    assert result.summary.planner_steps == 5
    assert result.summary.tool_steps == 4
    assert result.summary.successful_tool_steps == 4
    assert result.summary.failed_tool_steps == 0
    assert result.summary.required_tools_total == 4
    assert result.summary.required_tools_completed == 4
    assert result.summary.remaining_required_tools == []
    assert result.summary.latest_tool_name == "persistence_get_provider_operational_state"
    assert result.tool_history[0].tool_output.data["request_metadata"]["operation"] == "query_documents"
    assert result.tool_history[0].tool_output.data["request_metadata"]["run_id"] == "retrieval-provider-thread"
    assert result.tool_history[1].tool_output.data["request_metadata"]["operation"] == "upsert_provider_config"
    assert result.tool_history[1].tool_output.data["request_metadata"]["run_id"] == "retrieval-provider-thread"
    assert result.tool_history[2].tool_output.data["request_metadata"]["operation"] == "upsert_provider_status"
    assert result.tool_history[2].tool_output.data["request_metadata"]["run_id"] == "retrieval-provider-thread"
    assert result.tool_history[3].tool_output.data["request_metadata"]["operation"] == "get_provider_operational_state"
    assert result.tool_history[3].tool_output.data["request_metadata"]["run_id"] == "retrieval-provider-thread"
    persisted = persistence_client.provider_configs.get_provider_config("retrieval-provider-test")
    assert persisted is not None
    assert persisted["payload"]["summary"] == "Victor Frankenstein creates Frankenstein's monster from assembled body parts and abandons it immediately."
    operational = persistence_client.provider_configs.get_provider_operational_state("retrieval-provider-test")
    assert operational["runtime_state"]["active_label"] == "member-01"
    assert operational["runtime_state"]["active_status_found"] is True
    assert operational["runtime_state"]["diagnostics"] == []
    assert operational["ready_labels"] == ["member-01"]


def test_langgraph_runtime_responds_after_required_sequence_instead_of_looping_tools(tmp_path: Path) -> None:
    persistence_profile = PersistenceProfile(
        name="test-required-sequence-loop",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'required-sequence-loop.sqlite3'}",
    )
    persistence_client = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=persistence_profile),
        profile=persistence_profile,
    )
    persistence_client.initialize()

    web_client = WebSearchRuntimeClient(
        profile=WebSearchProfile(name="test-web-search", mode="duckduckgo"),
        config=WebSearchRuntimeConfig(),
    )
    web_client.mediawiki_search = lambda base_url, query, max_results=5: [  # type: ignore[method-assign]
        SearchResult(
            title="Frankenstein's monster",
            url="https://en.wikipedia.org/wiki/Frankenstein%27s_monster",
            snippet="Frankenstein's monster is a fictional character.",
            source="wikipedia",
            rank=1,
        )
    ]
    web_client.fetch_document = lambda url, query="": WebDocument(  # type: ignore[method-assign]
        url=url,
        title="Frankenstein's monster",
        summary="Victor Frankenstein creates Frankenstein's monster.",
        excerpt="Victor Frankenstein creates Frankenstein's monster.",
        focus_text="Victor Frankenstein creates Frankenstein's monster.",
        query=query,
        evidence_sentences=[],
        text="Victor Frankenstein creates Frankenstein's monster.",
        html="",
        metadata={"status_code": 200, "source_type": "mediawiki"},
    )

    runtime = _runtime(
        reasoning_client=StubPostSequenceLoopPlanner(),
        tools=[*web_client.as_langgraph_tools(), *persistence_client.as_langgraph_tools()],
        system_prompt="You are a resilient orchestration agent.",
        checkpoint_engine=persistence_client.engine,
    )
    result = runtime.invoke(
        user_input="Find who creates Frankenstein's monster, persist the note, read it back, then answer.",
        context={
            "required_tool_names": [
                "web_search_mediawiki_search",
                "web_search_fetch_document",
                "persistence_upsert_provider_config",
                "persistence_get_provider_config",
            ],
            "required_mediawiki_base_url": "https://en.wikipedia.org",
            "required_search_query": "who creates Frankenstein's monster",
            "required_provider_name": "loop-test",
        },
        max_steps=8,
    )

    assert result.error == ""
    assert result.final_output == "Victor Frankenstein creates Frankenstein's monster."
    assert [record.tool_name for record in result.tool_history] == [
        "web_search_mediawiki_search",
        "web_search_fetch_document",
        "persistence_upsert_provider_config",
        "persistence_get_provider_config",
    ]
