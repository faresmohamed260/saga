from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.agent_runtime.graph import AgentGraphRuntime
from packages.reasoning_runtime.contracts import ReasoningClient
from saga.providers.reasoning_runtime_adapter import MODE_GPT_OSS, create_runtime_client


class SmokePlanner(ReasoningClient):
    mode = "smoke_planner"

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
                "rationale": "Use the packaged reasoning runtime to answer the prompt.",
                "response": "",
                "tool_name": "reasoning_generate_text",
                "tool_input": {
                    "prompt": "In one sentence, explain why LangGraph is useful for stateful AI agent workflows.",
                    "system_prompt": "Return one concise sentence with no bullets.",
                    "temperature": 0.0,
                    "max_tokens": 80,
                },
            }
        return {
            "action": "respond",
            "rationale": "Return the live reasoning result as the final smoke output.",
            "response": "Reasoning tool executed successfully.",
            "tool_name": "",
            "tool_input": {},
        }

    def generate_text(self, prompt: str, *, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 4096) -> str:
        return "unused"

    def provider_name(self) -> str:
        return "smoke_planner"

    def resolved_model_name(self) -> str:
        return "smoke_planner"

    def last_request_metadata(self) -> dict[str, object]:
        return {}


def main() -> None:
    reasoning_runtime = create_runtime_client(
        mode=MODE_GPT_OSS,
        timeout=60,
        max_retries=1,
        allow_account_rotation=False,
        allow_cross_provider_fallback=False,
    )
    runtime = AgentGraphRuntime(
        reasoning_client=SmokePlanner(),
        tools=reasoning_runtime.as_langgraph_tools(),
        system_prompt="You are running a live LangGraph smoke test for the packaged reasoning runtime.",
    )
    result = runtime.invoke(
        user_input="Run the reasoning runtime smoke test.",
        context={"smoke_test": "langgraph_reasoning_runtime_live"},
        max_steps=4,
        thread_id="langgraph-reasoning-live-smoke",
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
