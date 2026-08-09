from __future__ import annotations

import json
import os
import sys
from uuid import uuid4

from packages.agent_runtime.graph import AgentGraphRuntime
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.reasoning_runtime import create_reasoning_client
from packages.reasoning_runtime.models import ReasoningProfile, ReasoningRuntimeConfig
from packages.reasoning_runtime.provider_config import summarize_reasoning_provider_configs
from packages.retrieval_runtime.client import RetrievalRuntimeClient
from packages.retrieval_runtime.models import RetrievalProfile, RetrievalRuntimeConfig
from packages.web_search_runtime.client import WebSearchRuntimeClient
from packages.web_search_runtime.models import WebSearchProfile, WebSearchRuntimeConfig


def _require_env(name: str) -> str:
    value = str(os.getenv(name, "") or "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def run_validation() -> dict[str, object]:
    _require_env("SAGA_SUPABASE_DB_URL")
    _require_env("SAGA_SUPABASE_SERVICE_ROLE_KEY")
    _require_env("SAGA_SUPABASE_API_URL")

    run_suffix = uuid4().hex[:10]
    provider_name = f"runtime-stack-validation-{run_suffix}"
    artifact_filename = f"stack-validation-{run_suffix}.json"

    persistence_profile = PersistenceProfile(
        name="real-runtime-stack-validation",
        provider="supabase",
        mode="supabase_postgres",
        application_name="saga-real-runtime-stack-validation",
    )
    persistence_client = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=persistence_profile),
        profile=persistence_profile,
    )
    persistence_client.initialize()
    reasoning_model = str(os.getenv("SAGA_REAL_REASONING_MODEL") or "llama3.1:8b").strip() or "llama3.1:8b"
    reasoning_summary = summarize_reasoning_provider_configs(persistence_client)
    local_ollama_base = str(os.getenv("SAGA_REAL_OLLAMA_BASE_URL") or os.getenv("OLLAMA_HOST") or "http://127.0.0.1:11434").strip().rstrip("/")
    local_ollama_ok = False
    try:
        import requests

        local_ollama_ok = requests.get(f"{local_ollama_base}/api/tags", timeout=5).status_code == 200
    except Exception:
        local_ollama_ok = False
    if local_ollama_ok:
        reasoning_client = create_reasoning_client(
            profile_name="real-runtime-reasoning",
            config=ReasoningRuntimeConfig(
                profiles={
                    "real-runtime-reasoning": ReasoningProfile(
                        name="real-runtime-reasoning",
                        mode="gpt_oss",
                        timeout_seconds=120,
                        max_retries=1,
                        model_override=reasoning_model,
                    )
                },
                ollama_local_url=f"{local_ollama_base}/api/generate",
            ),
        )
        reasoning_transport = "local_ollama"
    else:
        if not reasoning_summary["ollama"]["configured"]:
            raise RuntimeError("Ollama provider config is not stored in persistence runtime.")
        persisted_ollama_env = os.environ.pop("OLLAMA_API_KEY", None)
        persisted_general_compute_env = os.environ.pop("GENERAL_COMPUTE_API_KEY", None)
        try:
            reasoning_client = create_reasoning_client(
                profile_name="real-runtime-reasoning",
                config=ReasoningRuntimeConfig(
                    profiles={
                        "real-runtime-reasoning": ReasoningProfile(
                            name="real-runtime-reasoning",
                            mode="gpt_oss",
                            timeout_seconds=120,
                            max_retries=1,
                            model_override=reasoning_model,
                        )
                    }
                ),
                persistence_client=persistence_client,
            )
        finally:
            if persisted_ollama_env is not None:
                os.environ["OLLAMA_API_KEY"] = persisted_ollama_env
            if persisted_general_compute_env is not None:
                os.environ["GENERAL_COMPUTE_API_KEY"] = persisted_general_compute_env
        reasoning_transport = "persistence_ollama"
    reasoning_text = reasoning_client.generate_text(
        "Reply with the single word READY.",
        system_prompt="Return only the requested answer. No explanations.",
        temperature=0.0,
        max_tokens=24,
    )
    reasoning_json = reasoning_client.generate_json(
        "Return a JSON object with keys answer and confidence. What is 6 multiplied by 7?",
        strict=True,
        max_tokens=128,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "simple_math_response",
                "schema": {
                    "type": "object",
                    "properties": {
                        "answer": {"type": ["string", "number"]},
                        "confidence": {"type": ["number", "string"]},
                    },
                    "required": ["answer", "confidence"],
                    "additionalProperties": False,
                },
            },
        },
    )
    answer_value = str(reasoning_json.get("answer") or "").strip()
    if answer_value != "42":
        raise AssertionError(f"Unexpected reasoning JSON answer: {reasoning_json}")
    if "ready" not in reasoning_text.lower():
        raise AssertionError(f"Unexpected reasoning text output: {reasoning_text!r}")

    retrieval_profile = RetrievalProfile(
        name="real-runtime-retrieval",
        mode="document_index",
        embedding_model=str(os.getenv("SAGA_REAL_EMBEDDING_MODEL") or "nomic-embed-text:latest").strip() or "nomic-embed-text:latest",
        ollama_embed_url=str(os.getenv("SAGA_REAL_OLLAMA_EMBED_URL") or "http://localhost:11434/api/embed").strip() or "http://localhost:11434/api/embed",
        batch_size=4,
    )
    retrieval_client = RetrievalRuntimeClient(
        profile=retrieval_profile,
        config=RetrievalRuntimeConfig(
            profile=retrieval_profile,
            persistence_profile=persistence_profile,
            persistence_config=PersistenceRuntimeConfig(profile=persistence_profile),
        ),
        persistence_client=persistence_client,
    )
    index_payload = retrieval_client.ensure_document_index(
        series_id=f"real-runtime-{run_suffix}",
        scope_key="frankenstein-facts",
        documents=[
            {
                "document_id": f"doc-{run_suffix}-1",
                "text": "Victor Frankenstein creates Frankenstein's monster from assembled body parts in Mary Shelley's novel.",
                "summary": "Victor Frankenstein creates the monster.",
                "source_type": "fact",
                "metadata": {"characters": ["Victor Frankenstein", "Creature"], "topic": "creator"},
            },
            {
                "document_id": f"doc-{run_suffix}-2",
                "text": "Robert Walton writes letters describing his polar expedition.",
                "summary": "Robert Walton writes letters.",
                "source_type": "fact",
                "metadata": {"characters": ["Robert Walton"], "topic": "letters"},
            },
        ],
    )
    retrieval_results = retrieval_client.query_documents(
        index_ref={
            "index_id": index_payload.get("index_id"),
            "series_id": index_payload.get("series_id"),
            "scope_key": index_payload.get("scope_key"),
            "fingerprint": index_payload.get("fingerprint"),
        },
        query_text="Who creates Frankenstein's monster?",
        top_k=1,
        metadata_filters={"topic": "creator"},
    )
    if not retrieval_results:
        raise AssertionError("Live retrieval query returned no results.")
    if str(retrieval_results[0].get("document_id") or "") != f"doc-{run_suffix}-1":
        raise AssertionError(f"Unexpected retrieval top result: {retrieval_results[0]}")

    web_client = WebSearchRuntimeClient(
        profile=WebSearchProfile(name="real-runtime-web-search", mode="duckduckgo", timeout_seconds=20, max_results=5),
        config=WebSearchRuntimeConfig(),
    )
    mediawiki_results = web_client.mediawiki_search("https://en.wikipedia.org", "Victor Frankenstein", max_results=3)
    if not mediawiki_results:
        raise AssertionError("Live MediaWiki search returned no results.")
    web_document = web_client.fetch_document(
        "https://en.wikipedia.org/wiki/Victor_Frankenstein",
        query="Who creates Frankenstein's monster?",
    )
    if "victor frankenstein" not in str(web_document.title or "").lower():
        raise AssertionError(f"Unexpected web document title: {web_document.title!r}")
    if len(str(web_document.text or "").strip()) < 500:
        raise AssertionError("Live web document text was unexpectedly short.")
    if str(web_document.metadata.source_type or "").strip() != "mediawiki":
        raise AssertionError(f"Unexpected web document source type: {web_document.metadata.source_type!r}")

    agent_runtime = AgentGraphRuntime(
        reasoning_client=reasoning_client,
        tools=retrieval_client.as_langgraph_tools(),
        system_prompt="You are a strict orchestration agent.",
        checkpoint_engine=persistence_client.engine,
    )
    agent_result = agent_runtime.invoke(
        user_input="Who creates Frankenstein's monster?",
        context={
            "index_ref": {
                "index_id": index_payload.get("index_id"),
                "series_id": index_payload.get("series_id"),
                "scope_key": index_payload.get("scope_key"),
                "fingerprint": index_payload.get("fingerprint"),
            },
            "required_tool_names": ["retrieval_query_documents"],
        },
        max_steps=4,
        thread_id=f"real-runtime-agent-{run_suffix}",
    )
    if agent_result.error:
        raise AssertionError(f"Live agent runtime returned an error: {agent_result.error}")
    if "victor frankenstein" not in str(agent_result.final_output or "").lower():
        raise AssertionError(f"Unexpected live agent final output: {agent_result.final_output!r}")
    if [record.tool_name for record in agent_result.tool_history] != ["retrieval_query_documents"]:
        raise AssertionError(f"Unexpected live agent tool history: {[record.tool_name for record in agent_result.tool_history]}")

    artifact = persistence_client.artifacts.store_json(
        artifact_type="runtime_report",
        filename=artifact_filename,
        payload={
            "reasoning": {
                "text": reasoning_text,
                "json": reasoning_json,
                "request_metadata": reasoning_client.last_request_metadata(),
            },
            "retrieval": {
                "top_result": retrieval_results[0],
                "request_metadata": retrieval_client.last_request_metadata(),
            },
            "web_search": {
                "result_title": mediawiki_results[0].title,
                "document_title": web_document.title,
                "document_metadata": web_document.metadata.model_dump(),
                "request_metadata": web_client.last_request_metadata(),
            },
            "agent_runtime": {
                "final_output": agent_result.final_output,
                "summary": agent_result.summary.model_dump(),
                "tool_history": [record.model_dump() for record in agent_result.tool_history],
            },
        },
        provider_name=provider_name,
        report_kind="real-runtime-stack-validation",
        metadata={"validation_run": run_suffix},
    )

    return {
        "reasoning_model": reasoning_model,
        "reasoning_provider_configured": reasoning_summary["ollama"]["configured"],
        "reasoning_transport": reasoning_transport,
        "reasoning_text": reasoning_text,
        "reasoning_answer": answer_value,
        "retrieval_top_document_id": str(retrieval_results[0].get("document_id") or ""),
        "retrieval_request_status": retrieval_client.last_request_metadata().get("status", ""),
        "web_search_first_result": mediawiki_results[0].title,
        "web_document_title": web_document.title,
        "web_request_status": web_client.last_request_metadata().get("status", ""),
        "agent_final_output": agent_result.final_output,
        "agent_tool_steps": agent_result.summary.tool_steps,
        "agent_status": agent_result.summary.status,
        "artifact_bucket": artifact["bucket_name"],
        "artifact_object_path": artifact["object_path"],
    }


def main() -> int:
    result = run_validation()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REAL_RUNTIME_STACK_VALIDATION_FAILED: {exc}", file=sys.stderr)
        raise
