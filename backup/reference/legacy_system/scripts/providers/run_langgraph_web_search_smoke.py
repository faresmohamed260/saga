from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.agent_runtime.graph import AgentGraphRuntime
from packages.reasoning_runtime.contracts import ReasoningClient
from saga.providers.web_search_runtime_adapter import create_runtime_web_search_client, resolve_mediawiki_base_url


class WebSearchSmokePlanner(ReasoningClient):
    mode = "web_search_smoke_planner"

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
                "rationale": "Use the packaged web-search runtime to fetch real search results.",
                "response": "",
                "tool_name": "web_search_search",
                "tool_input": {
                    "query": "LangGraph stateful agents",
                    "max_results": 3,
                    "site": "langchain.com",
                },
            }
        if self.calls == 2:
            return {
                "action": "tool",
                "rationale": "Fetch a live page through the same web runtime.",
                "response": "",
                "tool_name": "web_search_fetch_document",
                "tool_input": {
                    "url": "https://www.langchain.com/langgraph",
                },
            }
        if self.calls == 3:
            return {
                "action": "tool",
                "rationale": "Exercise the MediaWiki search surface too.",
                "response": "",
                "tool_name": "web_search_mediawiki_search",
                "tool_input": {
                    "base_url": resolve_mediawiki_base_url("acotar"),
                    "query": "Feyre Archeron",
                    "max_results": 3,
                },
            }
        return {
            "action": "respond",
            "rationale": "The web-search runtime executed inside the LangGraph loop.",
            "response": "Web search tool executed successfully.",
            "tool_name": "",
            "tool_input": {},
        }

    def generate_text(self, prompt: str, *, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 4096) -> str:
        return "unused"

    def provider_name(self) -> str:
        return "web_search_smoke_planner"

    def resolved_model_name(self) -> str:
        return "web_search_smoke_planner"

    def last_request_metadata(self) -> dict[str, object]:
        return {}


def main() -> None:
    web_search_runtime = create_runtime_web_search_client(timeout=20, max_results=5)
    runtime = AgentGraphRuntime(
        reasoning_client=WebSearchSmokePlanner(),
        tools=web_search_runtime.as_langgraph_tools(),
        system_prompt="You are running a live LangGraph smoke test for the packaged web-search runtime.",
    )
    result = runtime.invoke(
        user_input="Run the web-search runtime smoke test.",
        context={"smoke_test": "langgraph_web_search_runtime_live"},
        max_steps=6,
        thread_id="langgraph-web-search-live-smoke",
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
