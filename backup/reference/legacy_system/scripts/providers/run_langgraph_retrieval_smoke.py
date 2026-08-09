from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.agent_runtime.graph import AgentGraphRuntime
from packages.reasoning_runtime.contracts import ReasoningClient
from saga.providers.retrieval_runtime_adapter import create_runtime_retrieval_client


class RetrievalSmokePlanner(ReasoningClient):
    mode = "retrieval_smoke_planner"

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
    ) -> dict[str, object]:
        self.calls += 1
        if self.calls == 1:
            return {
                "action": "tool",
                "rationale": "Build a portable retrieval index through the packaged runtime.",
                "response": "",
                "tool_name": "retrieval_ensure_document_index",
                "tool_input": {
                    "series_id": "smoke-acotar",
                    "scope_key": "langgraph-retrieval-smoke",
                    "documents": [
                        {
                            "document_id": "scene-1",
                            "text": "Feyre practiced archery in the forest while hunting for food for her family.",
                            "summary": "Feyre trains and hunts in the forest.",
                            "source_type": "scene",
                            "metadata": {"characters": ["Feyre Archeron"], "location": "forest"},
                        },
                        {
                            "document_id": "scene-2",
                            "text": "Rhysand briefed the Inner Circle in the town house war room before sunrise.",
                            "summary": "Rhysand leads a strategic meeting.",
                            "source_type": "scene",
                            "metadata": {"characters": ["Rhysand"], "location": "town house"},
                        },
                        {
                            "document_id": "scene-3",
                            "text": "Cassian drilled Nesta in the training ring until her stance finally stabilized.",
                            "summary": "Cassian trains Nesta in combat.",
                            "source_type": "scene",
                            "metadata": {"characters": ["Cassian", "Nesta Archeron"], "location": "training ring"},
                        },
                    ],
                },
            }
        if self.calls == 2:
            tool_history = self._tool_history_from_prompt(prompt)
            index_ref = {}
            if tool_history:
                first_output = (tool_history[-1].get("tool_output") or {}) if isinstance(tool_history[-1], dict) else {}
                if isinstance(first_output, dict):
                    index_ref = dict(first_output.get("index_ref") or {})
            return {
                "action": "tool",
                "rationale": "Query the same packaged retrieval runtime through its native LangGraph tool.",
                "response": "",
                "tool_name": "retrieval_query_documents",
                "tool_input": {
                    "index_ref": index_ref,
                    "query_text": "Who was being trained in combat practice?",
                    "top_k": 2,
                    "character_bias": ["Nesta Archeron"],
                },
            }
        return {
            "action": "respond",
            "rationale": "The retrieval runtime executed inside the LangGraph loop.",
            "response": "Retrieval tool executed successfully.",
            "tool_name": "",
            "tool_input": {},
        }

    def generate_text(self, prompt: str, *, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 4096) -> str:
        return "unused"

    def provider_name(self) -> str:
        return "retrieval_smoke_planner"

    def resolved_model_name(self) -> str:
        return "retrieval_smoke_planner"

    def last_request_metadata(self) -> dict[str, object]:
        return {}

    @staticmethod
    def _tool_history_from_prompt(prompt: str) -> list[dict[str, object]]:
        marker = "Tool history JSON:\n"
        suffix = "\n\nAvailable tools JSON:"
        if marker not in prompt or suffix not in prompt:
            return []
        payload = prompt.split(marker, 1)[1].split(suffix, 1)[0].strip()
        try:
            parsed = json.loads(payload)
        except Exception:
            return []
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        return []


def main() -> None:
    retrieval_runtime = create_runtime_retrieval_client(
        base_dir="analysis_outputs/langgraph_retrieval_smoke",
        embedding_model="nomic-embed-text:latest",
        batch_size=8,
    )
    runtime = AgentGraphRuntime(
        reasoning_client=RetrievalSmokePlanner(),
        tools=retrieval_runtime.as_langgraph_tools(),
        system_prompt="You are running a live LangGraph smoke test for the packaged retrieval runtime.",
    )
    result = runtime.invoke(
        user_input="Run the retrieval runtime smoke test.",
        context={"smoke_test": "langgraph_retrieval_runtime_live"},
        max_steps=5,
        thread_id="langgraph-retrieval-live-smoke",
    )
    tool_history = [step.model_dump() for step in result.tool_history]
    payload = {
        "final_output": result.final_output,
        "steps": result.steps,
        "error": result.error,
        "tool_history": tool_history,
    }
    print(json.dumps(payload, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
