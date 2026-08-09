from __future__ import annotations

import json
import os
import uuid
from difflib import get_close_matches
from typing import Any, TypedDict

from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from packages.agent_runtime.checkpointing import SqlCheckpointSaver
from packages.agent_runtime.models import (
    AgentExecutionResult,
    AgentExecutionSummary,
    AgentPlannerDecision,
    AgentPlannerDecisionResponseFormat,
    PlannerExecutionRecord,
    ToolExecutionRecord,
)
from packages.reasoning_runtime.contracts import ReasoningRequestMetadata
from packages.reasoning_runtime.contracts import ReasoningClient
from packages.runtime_common import RuntimeToolEnvelope, trace_scope


class AgentGraphState(TypedDict, total=False):
    user_input: str
    context: dict[str, Any]
    final_output: str
    last_decision: dict[str, Any]
    planner_history: list[dict[str, Any]]
    tool_history: list[dict[str, Any]]
    step_count: int
    max_steps: int
    error: str


def build_agent_graph(
    *,
    reasoning_client: ReasoningClient,
    tools: list[BaseTool],
    system_prompt: str = "",
    checkpointer: BaseCheckpointSaver | None = None,
    checkpoint_engine: Any | None = None,
    checkpoint_database_url: str = "",
    allow_in_memory_checkpointer: bool = False,
):
    tool_map = {tool.name: tool for tool in tools}
    resolved_checkpointer = _resolve_agent_checkpointer(
        checkpointer=checkpointer,
        checkpoint_engine=checkpoint_engine,
        checkpoint_database_url=checkpoint_database_url,
        allow_in_memory_checkpointer=allow_in_memory_checkpointer,
    )

    def planner_node(state: AgentGraphState) -> dict[str, Any]:
        planner_step = _plan_next_step(
            reasoning_client=reasoning_client,
            tool_map=tool_map,
            user_input=str(state.get("user_input") or ""),
            context=state.get("context") or {},
            tool_history=state.get("tool_history") or [],
            planner_history=state.get("planner_history") or [],
            system_prompt=system_prompt,
        )
        return {
            "last_decision": planner_step.decision.model_dump() if planner_step.decision else {},
            "planner_history": [*(state.get("planner_history") or []), planner_step.model_dump()],
            "step_count": int(state.get("step_count") or 0) + 1,
        }

    def execute_tool_node(state: AgentGraphState) -> dict[str, Any]:
        decision = AgentPlannerDecision.model_validate(state.get("last_decision") or {})
        tool = tool_map.get(decision.tool_name)
        if tool is None:
            return {"error": f"unknown_tool:{decision.tool_name}"}
        parent_trace_id = ""
        if state.get("tool_history"):
            last_trace = ((state.get("tool_history") or [])[-1] or {}).get("trace") or {}
            parent_trace_id = str(last_trace.get("trace_id") or "").strip()
        with trace_scope(run_id=str((state.get("context") or {}).get("run_id") or ""), parent_trace_id=parent_trace_id):
            payload = tool.invoke(decision.tool_input or {})
        normalized_payload = _normalize_tool_output(payload)
        record = ToolExecutionRecord(
            tool_name=decision.tool_name,
            tool_input=dict(decision.tool_input or {}),
            tool_output=RuntimeToolEnvelope.model_validate(normalized_payload),
            rationale=decision.rationale,
            trace=(normalized_payload.get("trace") or {}),
        )
        return {"tool_history": [*(state.get("tool_history") or []), record.model_dump()]}

    def finalize_node(state: AgentGraphState) -> dict[str, Any]:
        decision = AgentPlannerDecision.model_validate(state.get("last_decision") or {})
        return {"final_output": decision.response}

    def fail_node(state: AgentGraphState) -> dict[str, Any]:
        error = str(state.get("error") or "agent_execution_failed")
        if not error.startswith("max_steps_exceeded"):
            return {"final_output": f"Agent execution failed: {error}"}
        return {"final_output": "Agent execution stopped because it exceeded the configured step limit."}

    def route_after_planner(state: AgentGraphState) -> str:
        if state.get("error"):
            return "fail"
        if int(state.get("step_count") or 0) > max(1, int(state.get("max_steps") or 6)):
            return "fail"
        decision = AgentPlannerDecision.model_validate(state.get("last_decision") or {})
        if decision.action == "respond":
            return "finalize"
        if decision.action == "tool" and decision.tool_name in tool_map:
            return "execute_tool"
        return "fail"

    def route_after_tool(state: AgentGraphState) -> str:
        if state.get("error"):
            return "fail"
        if int(state.get("step_count") or 0) >= max(1, int(state.get("max_steps") or 6)):
            return "fail"
        return "planner"

    builder = StateGraph(AgentGraphState)
    builder.add_node("planner", planner_node)
    builder.add_node("execute_tool", execute_tool_node)
    builder.add_node("finalize", finalize_node)
    builder.add_node("fail", fail_node)
    builder.add_edge(START, "planner")
    builder.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "execute_tool": "execute_tool",
            "finalize": "finalize",
            "fail": "fail",
        },
    )
    builder.add_conditional_edges(
        "execute_tool",
        route_after_tool,
        {
            "planner": "planner",
            "fail": "fail",
        },
    )
    builder.add_edge("finalize", END)
    builder.add_edge("fail", END)
    return builder.compile(checkpointer=resolved_checkpointer)


class AgentGraphRuntime:
    def __init__(
        self,
        *,
        reasoning_client: ReasoningClient,
        tools: list[BaseTool],
        system_prompt: str = "",
        checkpointer: BaseCheckpointSaver | None = None,
        checkpoint_engine: Any | None = None,
        checkpoint_database_url: str = "",
        allow_in_memory_checkpointer: bool = False,
    ) -> None:
        self.reasoning_client = reasoning_client
        self.tools = list(tools or [])
        self.system_prompt = system_prompt
        self.checkpointer = _resolve_agent_checkpointer(
            checkpointer=checkpointer,
            checkpoint_engine=checkpoint_engine,
            checkpoint_database_url=checkpoint_database_url,
            allow_in_memory_checkpointer=allow_in_memory_checkpointer,
        )
        self.graph = build_agent_graph(
            reasoning_client=reasoning_client,
            tools=self.tools,
            system_prompt=system_prompt,
            checkpointer=self.checkpointer,
        )

    def invoke(
        self,
        *,
        user_input: str,
        context: dict[str, Any] | None = None,
        max_steps: int = 6,
        thread_id: str = "",
    ) -> AgentExecutionResult:
        config = {"configurable": {"thread_id": str(thread_id or f"agent-{uuid.uuid4().hex}")}}
        snapshot = self.graph.get_state(config)
        existing = dict(snapshot.values or {})
        is_resume = bool(existing)
        current_steps = int(existing.get("step_count") or 0) if is_resume else 0
        merged_context = dict(existing.get("context") or {}) if is_resume else {}
        merged_context.update(dict(context or {}))
        run_id = str(thread_id or f"agent-{uuid.uuid4().hex}")
        merged_context["run_id"] = run_id
        with trace_scope(run_id=run_id):
            state = self.graph.invoke(
                {
                    "user_input": str(user_input or existing.get("user_input") or "").strip(),
                    "context": merged_context,
                    "final_output": "",
                    "planner_history": list(existing.get("planner_history") or []),
                    "tool_history": list(existing.get("tool_history") or []),
                    "step_count": current_steps,
                    "max_steps": current_steps + max(1, int(max_steps)),
                    "error": "",
                },
                config=config,
            )
        decision = None
        if state.get("last_decision"):
            decision = AgentPlannerDecision.model_validate(state["last_decision"])
        planner_history = [PlannerExecutionRecord.model_validate(item) for item in (state.get("planner_history") or [])]
        history = [ToolExecutionRecord.model_validate(item) for item in (state.get("tool_history") or [])]
        error = str(state.get("error") or "")
        step_count = int(state.get("step_count") or 0)
        max_allowed_steps = max(1, int(state.get("max_steps") or max_steps))
        if step_count > max_allowed_steps:
            error = error or "max_steps_exceeded"
        elif decision and decision.action == "tool" and step_count >= max_allowed_steps:
            error = error or "max_steps_exceeded"
        final_output = str(state.get("final_output") or "")
        if error == "max_steps_exceeded":
            final_output = "Agent execution stopped because it exceeded the configured step limit."
        return AgentExecutionResult(
            final_output=final_output,
            steps=step_count,
            planner_history=planner_history,
            tool_history=history,
            last_decision=decision,
            error=error,
            summary=_build_execution_summary(
                run_id=run_id,
                thread_id=str(config["configurable"]["thread_id"] or ""),
                context=merged_context,
                planner_history=planner_history,
                tool_history=history,
                error=error,
            ),
        )


def _resolve_agent_checkpointer(
    *,
    checkpointer: BaseCheckpointSaver | None,
    checkpoint_engine: Any | None,
    checkpoint_database_url: str,
    allow_in_memory_checkpointer: bool,
) -> BaseCheckpointSaver:
    if checkpointer is not None:
        return checkpointer
    explicit_database_url = str(checkpoint_database_url or "").strip()
    env_database_url = str(os.getenv("SAGA_AGENT_RUNTIME_DB_URL", "") or "").strip()
    resolved_database_url = explicit_database_url or env_database_url
    if checkpoint_engine is not None or resolved_database_url:
        return SqlCheckpointSaver(engine=checkpoint_engine, database_url=resolved_database_url)
    if allow_in_memory_checkpointer:
        return InMemorySaver()
    raise ValueError(
        "AgentGraphRuntime requires a durable checkpointer by default. "
        "Pass checkpointer=..., checkpoint_engine=..., checkpoint_database_url=..., "
        "or set SAGA_AGENT_RUNTIME_DB_URL. Use allow_in_memory_checkpointer=True only for explicit test/debug scenarios."
    )


def _plan_next_step(
    *,
    reasoning_client: ReasoningClient,
    tool_map: dict[str, BaseTool],
    user_input: str,
    context: dict[str, Any],
    tool_history: list[dict[str, Any]],
    planner_history: list[dict[str, Any]],
    system_prompt: str,
) -> PlannerExecutionRecord:
    remaining_required_tools = _remaining_required_tools(context, tool_history)
    tools_payload = []
    for tool in tool_map.values():
        schema = {}
        if getattr(tool, "args_schema", None) is not None and hasattr(tool.args_schema, "model_json_schema"):
            schema = tool.args_schema.model_json_schema()
        tools_payload.append(
            {
                "name": tool.name,
                "description": getattr(tool, "description", "") or "",
                "json_schema": schema,
            }
        )
    prompt = (
        f"{system_prompt.strip()}\n\n" if system_prompt.strip() else ""
    ) + (
        "You are an orchestration agent running inside LangGraph.\n"
        "Decide whether to call one tool or return the final answer now.\n"
        "Return JSON only with keys: action, rationale, response, tool_name, tool_input.\n"
        "Rules:\n"
        "- action must be either 'tool' or 'respond'.\n"
        "- If action is 'respond', fill response and leave tool_name empty.\n"
        "- If action is 'tool', choose exactly one listed tool and provide valid tool_input.\n"
        "- Do not invent tools or fields.\n"
        "- If required tools remain, do not respond yet.\n"
        "- If retrieval results already exist in tool history, prefer the highest-ranked result unless combining results is clearly necessary.\n"
        "- Preserve retrieval ranking when forming the final answer.\n\n"
        f"User input:\n{user_input}\n\n"
        f"Context JSON:\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
        f"Required tools remaining JSON:\n{json.dumps(remaining_required_tools, ensure_ascii=False, indent=2)}\n\n"
        f"Tool history JSON:\n{json.dumps(tool_history, ensure_ascii=False, indent=2)}\n\n"
        f"Latest evidence JSON:\n{json.dumps(_latest_evidence_payload(tool_history), ensure_ascii=False, indent=2)}\n\n"
        f"Available tools JSON:\n{json.dumps(tools_payload, ensure_ascii=False, indent=2)}"
    )

    def _validator(payload: dict[str, Any]) -> bool:
        try:
            decision = AgentPlannerDecision.model_validate(payload)
        except Exception:
            return False
        if decision.action == "tool":
            if decision.tool_name not in tool_map:
                return False
            if remaining_required_tools:
                return decision.tool_name == remaining_required_tools[0]
            return True
        return bool(decision.response.strip()) and not remaining_required_tools

    payload = reasoning_client.generate_json(
        prompt,
        strict=True,
        validator=_validator,
        max_tokens=1200,
        response_format=_planner_response_format(),
    )
    if isinstance(payload, dict) and "error" not in payload and not _validator(payload):
        payload = {"error": "validation_failed", "raw_output": dict(payload or {})}
    metadata = ReasoningRequestMetadata.model_validate(reasoning_client.last_request_metadata())
    step_index = len(planner_history) + 1
    if payload.get("error"):
        coerced = _coerce_planner_payload(
            payload.get("raw_output"),
            tool_map=tool_map,
            user_input=user_input,
            context=context,
        )
        if coerced is not None and _validator(coerced):
            decision = AgentPlannerDecision.model_validate(coerced)
            return PlannerExecutionRecord(
                step_index=step_index,
                prompt=prompt,
                decision=decision,
                metadata=metadata,
                raw_payload=dict(payload or {}),
                error=str(payload.get("error") or ""),
            )
        synthesized = _synthesize_required_tool_decision(
            remaining_required_tools=remaining_required_tools,
            user_input=user_input,
            context=context,
            tool_history=tool_history,
        )
        if synthesized is not None and _validator(synthesized):
            decision = AgentPlannerDecision.model_validate(synthesized)
            return PlannerExecutionRecord(
                step_index=step_index,
                prompt=prompt,
                decision=decision,
                metadata=metadata,
                raw_payload=dict(payload or {}),
                error=str(payload.get("error") or ""),
            )
        fallback_response = _tool_history_fallback_response(tool_history)
        if fallback_response and not remaining_required_tools:
            decision = AgentPlannerDecision(
                action="respond",
                rationale="Planner failed after a successful tool call; returning the latest tool result.",
                response=fallback_response,
            )
            return PlannerExecutionRecord(
                step_index=step_index,
                prompt=prompt,
                decision=decision,
                metadata=metadata,
                raw_payload=dict(payload or {}),
                error=str(payload.get("error") or ""),
            )
        decision = AgentPlannerDecision(
            action="respond",
            rationale="Planner failed to produce a valid tool decision.",
            response=f"Planner error: {payload.get('error')}",
        )
        return PlannerExecutionRecord(
            step_index=step_index,
            prompt=prompt,
            decision=decision,
            metadata=metadata,
            raw_payload=dict(payload or {}),
            error=str(payload.get("error") or ""),
        )
    decision = AgentPlannerDecision.model_validate(payload)
    if decision.action == "tool":
        if not remaining_required_tools and (context.get("required_tool_names") or []):
            grounded_runtime = _preferred_runtime_grounded_response(tool_history)
            if grounded_runtime and decision.tool_name in _successful_tool_names(tool_history):
                decision = AgentPlannerDecision(
                    action="respond",
                    rationale="Required runtime tool sequence already completed; returning the latest grounded runtime result.",
                    response=grounded_runtime,
                )
        if decision.action == "tool":
            decision = AgentPlannerDecision(
                action=decision.action,
                rationale=decision.rationale,
                response=decision.response,
                tool_name=decision.tool_name,
                tool_input=_hydrate_tool_input(
                    decision.tool_name,
                    tool_input=dict(decision.tool_input or {}),
                    user_input=user_input,
                    context=context,
                ),
            )
    if decision.action == "respond":
        decision = _ground_response_decision(decision, tool_history)
    if decision.action == "tool" and _is_repeated_tool_invocation(decision, tool_history):
        fallback_response = _tool_history_fallback_response(tool_history)
        if fallback_response:
            decision = AgentPlannerDecision(
                action="respond",
                rationale="Planner repeated the same successful tool call; returning the latest tool result instead.",
                response=fallback_response,
            )
    return PlannerExecutionRecord(
        step_index=step_index,
        prompt=prompt,
        decision=decision,
        metadata=metadata,
        raw_payload=dict(payload or {}),
        error="",
    )


def _normalize_tool_output(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return RuntimeToolEnvelope.model_validate(payload).model_dump()
    raise TypeError("Runtime tools must return a RuntimeToolEnvelope-compatible payload.")


def _build_execution_summary(
    *,
    run_id: str,
    thread_id: str,
    context: dict[str, Any],
    planner_history: list[PlannerExecutionRecord],
    tool_history: list[ToolExecutionRecord],
    error: str,
) -> AgentExecutionSummary:
    required_tools = [
        str(name or "").strip()
        for name in (context.get("required_tool_names") or [])
        if str(name or "").strip()
    ]
    successful_tool_names = {
        record.tool_name
        for record in (tool_history or [])
        if bool(record.tool_output.ok) and str(record.tool_name or "").strip()
    }
    remaining_required_tools = [name for name in required_tools if name not in successful_tool_names]
    latest_tool = tool_history[-1] if tool_history else None
    if error == "max_steps_exceeded":
        status = "max_steps_exceeded"
    elif error:
        status = "error"
    else:
        status = "ok"
    return AgentExecutionSummary(
        run_id=str(run_id or "").strip(),
        thread_id=str(thread_id or "").strip(),
        status=status,
        planner_steps=len(planner_history or []),
        tool_steps=len(tool_history or []),
        successful_tool_steps=sum(1 for record in (tool_history or []) if bool(record.tool_output.ok)),
        failed_tool_steps=sum(1 for record in (tool_history or []) if not bool(record.tool_output.ok)),
        latest_tool_name=str((latest_tool.tool_name if latest_tool else "") or "").strip(),
        latest_trace_id=str((latest_tool.trace.trace_id if latest_tool else "") or "").strip(),
        required_tools_total=len(required_tools),
        required_tools_completed=len(required_tools) - len(remaining_required_tools),
        remaining_required_tools=remaining_required_tools,
    )


def _remaining_required_tools(context: dict[str, Any], tool_history: list[dict[str, Any]]) -> list[str]:
    required = [
        str(name or "").strip()
        for name in (context.get("required_tool_names") or [])
        if str(name or "").strip()
    ]
    if not required:
        return []
    used = {
        str(item.get("tool_name") or "").strip()
        for item in (tool_history or [])
        if str(item.get("tool_name") or "").strip()
        and bool((((item.get("tool_output") or {}).get("ok"))))
    }
    return [name for name in required if name not in used]


def _synthesize_required_tool_decision(
    *,
    remaining_required_tools: list[str],
    user_input: str,
    context: dict[str, Any],
    tool_history: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not remaining_required_tools:
        return None
    next_tool = str(remaining_required_tools[0] or "").strip()
    if not next_tool:
        return None
    tool_input = _default_required_tool_input(
        tool_name=next_tool,
        user_input=user_input,
        context=context,
        tool_history=tool_history,
    )
    if tool_input is None:
        return None
    return {
        "action": "tool",
        "rationale": "Advancing the required tool sequence after a premature planner response.",
        "response": "",
        "tool_name": next_tool,
        "tool_input": tool_input,
    }


def _default_required_tool_input(
    *,
    tool_name: str,
    user_input: str,
    context: dict[str, Any],
    tool_history: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if tool_name == "web_search_mediawiki_search":
        return {
            "base_url": str(context.get("required_mediawiki_base_url") or "https://en.wikipedia.org").strip(),
            "query": str(context.get("required_search_query") or user_input).strip(),
            "max_results": max(1, int(context.get("required_search_max_results") or 1)),
        }
    if tool_name == "web_search_fetch_document":
        latest = _latest_evidence_payload(tool_history)
        preview = latest.get("data_preview") if isinstance(latest.get("data_preview"), dict) else {}
        results = preview.get("results") if isinstance(preview.get("results"), list) else []
        selected = _select_best_search_result(results, query_text=str(latest.get("query_text") or user_input))
        url = str(context.get("required_document_url") or selected.get("url") or "").strip()
        if not url:
            return None
        return {"url": url, "query": str(context.get("required_search_query") or latest.get("query_text") or user_input).strip()}
    if tool_name == "persistence_upsert_provider_config":
        provider_name = str(context.get("required_provider_name") or context.get("provider_name") or "").strip()
        if not provider_name:
            return None
        payload = dict(context.get("required_provider_payload") or {})
        latest = _latest_evidence_payload(tool_history)
        summary = _derive_required_summary(tool_history=tool_history, user_input=user_input)
        title = str(latest.get("title") or "").strip()
        if summary and not str(payload.get("summary") or "").strip():
            payload["summary"] = summary
        elif title and not str(payload.get("summary") or "").strip():
            payload["summary"] = title
        if not payload:
            return None
        return {"provider_name": provider_name, "payload": payload}
    if tool_name == "persistence_get_provider_config":
        provider_name = str(context.get("required_provider_name") or context.get("provider_name") or "").strip()
        if not provider_name:
            return None
        return {"provider_name": provider_name}
    if tool_name == "persistence_upsert_provider_status":
        provider_name = str(context.get("required_provider_name") or context.get("provider_name") or "").strip()
        label = str(context.get("required_status_label") or context.get("status_label") or "").strip()
        payload = dict(context.get("required_provider_status_payload") or context.get("provider_status_payload") or {})
        if not provider_name or not label or not payload:
            return None
        return {"provider_name": provider_name, "label": label, "payload": payload}
    if tool_name == "persistence_get_provider_operational_state":
        provider_name = str(context.get("required_provider_name") or context.get("provider_name") or "").strip()
        if not provider_name:
            return None
        return {"provider_name": provider_name}
    return None


def _planner_response_format() -> dict[str, Any]:
    return AgentPlannerDecisionResponseFormat(
        json_schema={
            "name": "agent_planner_decision",
            "schema": AgentPlannerDecision.model_json_schema(),
        }
    ).model_dump()


def _coerce_planner_payload(
    raw_payload: Any,
    *,
    tool_map: dict[str, BaseTool],
    user_input: str,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    if not isinstance(raw_payload, dict):
        return None
    normalized = dict(raw_payload)
    action = _normalize_planner_action(normalized.get("action"))
    if not action:
        return None

    rationale = str(normalized.get("rationale") or "").strip()
    response = str(normalized.get("response") or "").strip()
    tool_name = _resolve_tool_name(normalized.get("tool_name"), tool_map)
    tool_input = _coerce_tool_input(normalized.get("tool_input"))

    if action == "tool":
        if not tool_name:
            return None
        tool_input = _hydrate_tool_input(tool_name, tool_input=tool_input, user_input=user_input, context=context)
        return {
            "action": "tool",
            "rationale": rationale or "Coerced tool decision from planner output.",
            "response": "",
            "tool_name": tool_name,
            "tool_input": tool_input,
        }
    return {
        "action": "respond",
        "rationale": rationale or "Coerced response decision from planner output.",
        "response": response or rationale or "Unable to complete the request.",
        "tool_name": "",
        "tool_input": {},
    }


def _normalize_planner_action(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"tool", "run", "call", "tool_call", "use_tool", "invoke"}:
        return "tool"
    if normalized in {"respond", "response", "answer", "final", "done"}:
        return "respond"
    return ""


def _resolve_tool_name(raw_tool_name: Any, tool_map: dict[str, BaseTool]) -> str:
    available = list(tool_map.keys())
    candidate = str(raw_tool_name or "").strip()
    if candidate in tool_map:
        return candidate
    if not candidate and len(available) == 1:
        return available[0]
    lowered = {name.lower(): name for name in available}
    direct = lowered.get(candidate.lower())
    if direct:
        return direct
    candidate_lower = candidate.lower()
    if "query" in candidate_lower:
        query_tools = [name for name in available if "query" in name.lower()]
        if len(query_tools) == 1:
            return query_tools[0]
    close = get_close_matches(candidate.lower(), list(lowered.keys()), n=1, cutoff=0.55)
    if close:
        return lowered[close[0]]
    if len(available) == 1:
        return available[0]
    return ""


def _coerce_tool_input(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _hydrate_tool_input(tool_name: str, *, tool_input: dict[str, Any], user_input: str, context: dict[str, Any]) -> dict[str, Any]:
    hydrated = dict(tool_input or {})
    if tool_name == "web_search_mediawiki_search":
        if str(context.get("required_mediawiki_base_url") or "").strip():
            hydrated["base_url"] = str(context.get("required_mediawiki_base_url") or "").strip()
        if str(context.get("required_search_query") or "").strip():
            hydrated["query"] = str(context.get("required_search_query") or "").strip()
        minimum_results = max(1, int(context.get("required_search_max_results") or 5))
        hydrated["max_results"] = max(minimum_results, int(hydrated.get("max_results") or minimum_results))
    if tool_name == "web_search_fetch_document":
        if str(context.get("required_search_query") or "").strip():
            hydrated["query"] = str(context.get("required_search_query") or "").strip()
        else:
            hydrated.setdefault("query", str(user_input or "").strip())
    if tool_name == "retrieval_query_documents":
        if "index_ref" not in hydrated and isinstance(context.get("index_ref"), dict):
            hydrated["index_ref"] = dict(context["index_ref"])
        hydrated.setdefault("query_text", str(user_input or "").strip())
        hydrated.setdefault("top_k", 3)
        hydrated["allowed_types"] = list(hydrated.get("allowed_types") or [])
        hydrated["character_bias"] = list(hydrated.get("character_bias") or [])
        metadata_filters = dict(hydrated.get("metadata_filters") or {})
        if set(metadata_filters).issubset({"title", "type", "properties", "default"}) and "type" in metadata_filters:
            metadata_filters = {}
        hydrated["metadata_filters"] = metadata_filters
    return hydrated


def _tool_history_fallback_response(tool_history: list[dict[str, Any]]) -> str:
    if not tool_history:
        return ""
    last = dict(tool_history[-1] or {})
    tool_output = last.get("tool_output") if isinstance(last, dict) else None
    if not isinstance(tool_output, dict) or not tool_output.get("ok"):
        return ""
    data = tool_output.get("data")
    if not isinstance(data, dict):
        return ""
    operational_summary = _provider_operational_state_summary(data)
    if operational_summary:
        return operational_summary
    provider_summary = _provider_config_summary(data)
    if provider_summary:
        return provider_summary
    focus_text = str(data.get("focus_text") or "").strip()
    if focus_text:
        return focus_text
    summary = str(data.get("summary") or "").strip()
    if summary:
        return summary
    excerpt = str(data.get("excerpt") or "").strip()
    if excerpt:
        return excerpt
    text = str(data.get("text") or "").strip()
    if text:
        return text
    results = data.get("results")
    if isinstance(results, list) and results:
        first = results[0] if isinstance(results[0], dict) else {"value": results[0]}
        excerpt = str(first.get("excerpt") or "").strip()
        if excerpt:
            return excerpt
        summary = str(first.get("summary") or "").strip()
        if summary:
            return summary
        return json.dumps(first, ensure_ascii=False)
    message = str(data.get("message") or "").strip()
    if message:
        return message
    return json.dumps(data, ensure_ascii=False)


def _latest_evidence_payload(tool_history: list[dict[str, Any]]) -> dict[str, Any]:
    if not tool_history:
        return {}
    last = dict(tool_history[-1] or {})
    tool_name = str(last.get("tool_name") or "").strip()
    tool_output = last.get("tool_output") if isinstance(last, dict) else None
    if not isinstance(tool_output, dict) or not tool_output.get("ok"):
        return {}
    data = tool_output.get("data")
    if not isinstance(data, dict):
        return {}
    if tool_name == "retrieval_query_documents":
        results = data.get("results") if isinstance(data.get("results"), list) else []
        if not results:
            return {"tool_name": tool_name, "result_count": 0}
        top = results[0] if isinstance(results[0], dict) else {}
        return {
            "tool_name": tool_name,
            "query_text": str(data.get("query_text") or ""),
            "result_count": len(results),
            "top_result": {
                "document_id": str(top.get("document_id") or ""),
                "summary": str(top.get("summary") or ""),
                "excerpt": str(top.get("excerpt") or ""),
                "score": float(top.get("score") or 0.0),
                "metadata": dict(top.get("metadata") or {}),
            },
        }
    if tool_name == "web_search_fetch_document":
        return {
            "tool_name": tool_name,
            "url": str(data.get("url") or ""),
            "title": str(data.get("title") or ""),
            "focus_text": str(data.get("focus_text") or ""),
            "summary": str(data.get("summary") or ""),
            "excerpt": str(data.get("excerpt") or ""),
        }
    if tool_name == "persistence_get_provider_config":
        return {
            "tool_name": tool_name,
            "provider_name": str(data.get("provider_name") or ""),
            "found": bool(data.get("found")),
            "summary": _provider_config_summary(data),
        }
    if tool_name == "persistence_get_provider_operational_state":
        return {
            "tool_name": tool_name,
            "provider_name": str(data.get("provider_name") or ""),
            "found": bool(data.get("found")),
            "summary": _provider_operational_state_summary(data),
            "active_label": str(((data.get("runtime_state") or {}).get("active_label")) or ""),
            "healthy_labels": list(data.get("healthy_labels") or []),
            "ready_labels": list(data.get("ready_labels") or []),
        }
    return {
        "tool_name": tool_name,
        "data_preview": data,
        "query_text": str(data.get("query") or ""),
    }


def _ground_response_decision(decision: AgentPlannerDecision, tool_history: list[dict[str, Any]]) -> AgentPlannerDecision:
    retrieval_results = _latest_retrieval_results(tool_history)
    response = str(decision.response or "").strip()
    grounded_runtime = _preferred_runtime_grounded_response(tool_history)
    if not retrieval_results:
        if grounded_runtime and (not response or not _response_matches_runtime_grounding(response, grounded_runtime)):
            return AgentPlannerDecision(
                action="respond",
                rationale=decision.rationale or "Grounded the final answer in the latest successful runtime result.",
                response=grounded_runtime,
            )
        return decision
    if not response:
        grounded = _preferred_grounded_response(retrieval_results) or grounded_runtime
        if grounded:
            return AgentPlannerDecision(
                action="respond",
                rationale=decision.rationale or "Grounded the final answer in the highest-ranked retrieval result.",
                response=grounded,
            )
        return decision
    best_index = _best_matching_retrieval_result_index(response, retrieval_results)
    if best_index == 0:
        if grounded_runtime and not _response_matches_runtime_grounding(response, grounded_runtime):
            return AgentPlannerDecision(
                action="respond",
                rationale=decision.rationale or "Grounded the final answer in the latest successful runtime result.",
                response=grounded_runtime,
            )
        return decision
    grounded = _preferred_grounded_response(retrieval_results) or grounded_runtime
    if grounded:
        return AgentPlannerDecision(
            action="respond",
            rationale=(
                decision.rationale
                or "Grounded the final answer in the highest-ranked retrieval result."
            ),
            response=grounded,
        )
    return decision


def _latest_retrieval_results(tool_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not tool_history:
        return []
    last = dict(tool_history[-1] or {})
    if str(last.get("tool_name") or "").strip() != "retrieval_query_documents":
        return []
    tool_output = last.get("tool_output") if isinstance(last, dict) else None
    if not isinstance(tool_output, dict) or not tool_output.get("ok"):
        return []
    data = tool_output.get("data")
    if not isinstance(data, dict):
        return []
    results = data.get("results")
    if not isinstance(results, list):
        return []
    return [dict(row or {}) for row in results if isinstance(row, dict)]


def _preferred_grounded_response(results: list[dict[str, Any]]) -> str:
    if not results:
        return ""
    top = dict(results[0] or {})
    excerpt = str(top.get("excerpt") or "").strip()
    if excerpt:
        return excerpt
    summary = str(top.get("summary") or "").strip()
    if summary:
        return summary
    return json.dumps(top, ensure_ascii=False)


def _preferred_runtime_grounded_response(tool_history: list[dict[str, Any]]) -> str:
    if not tool_history:
        return ""
    last = dict(tool_history[-1] or {})
    tool_output = last.get("tool_output") if isinstance(last, dict) else None
    if not isinstance(tool_output, dict) or not tool_output.get("ok"):
        return ""
    data = tool_output.get("data")
    if not isinstance(data, dict):
        return ""
    operational_summary = _provider_operational_state_summary(data)
    if operational_summary:
        return operational_summary
    provider_summary = _provider_config_summary(data)
    if provider_summary:
        return provider_summary
    focus_text = str(data.get("focus_text") or "").strip()
    if focus_text:
        return focus_text
    summary = str(data.get("summary") or "").strip()
    if summary:
        return summary
    excerpt = str(data.get("excerpt") or "").strip()
    if excerpt:
        return excerpt
    return ""


def _derive_required_summary(*, tool_history: list[dict[str, Any]], user_input: str) -> str:
    if not tool_history:
        return ""
    last = dict(tool_history[-1] or {})
    tool_output = last.get("tool_output") if isinstance(last, dict) else None
    if not isinstance(tool_output, dict) or not tool_output.get("ok"):
        return ""
    data = tool_output.get("data")
    if not isinstance(data, dict):
        return ""
    results = data.get("results")
    if isinstance(results, list) and results:
        first = results[0] if isinstance(results[0], dict) else {}
        excerpt = str(first.get("excerpt") or "").strip()
        summary = str(first.get("summary") or "").strip()
        if excerpt and _line_is_meaningful(excerpt):
            return excerpt
        if summary and _line_is_meaningful(summary):
            return summary
    candidates: list[str] = []
    focus_text = str(data.get("focus_text") or "").strip()
    summary = str(data.get("summary") or "").strip()
    excerpt = str(data.get("excerpt") or "").strip()
    text = str(data.get("text") or "").strip()
    if focus_text and _line_is_meaningful(focus_text):
        return focus_text
    if summary and _line_is_meaningful(summary):
        candidates.append(summary)
    if excerpt and _line_is_meaningful(excerpt) and excerpt not in candidates:
        candidates.append(excerpt)
    candidates.extend(
        sentence
        for sentence in _candidate_sentences(text)
        if _line_is_meaningful(sentence) and sentence not in candidates
    )
    if not candidates:
        return ""
    return max(candidates, key=lambda candidate: _score_candidate_against_query(candidate, user_input=user_input))


def _provider_config_summary(payload: dict[str, Any]) -> str:
    config = payload.get("config")
    if not isinstance(config, dict):
        return ""
    config_payload = config.get("payload")
    if not isinstance(config_payload, dict):
        return ""
    return str(config_payload.get("summary") or "").strip()


def _provider_operational_state_summary(payload: dict[str, Any]) -> str:
    runtime_state = payload.get("runtime_state")
    if not isinstance(runtime_state, dict):
        return ""
    provider_name = str(payload.get("provider_name") or "").strip()
    active_label = str(runtime_state.get("active_label") or "").strip()
    healthy_labels = [str(item or "").strip() for item in (payload.get("healthy_labels") or []) if str(item or "").strip()]
    ready_labels = [str(item or "").strip() for item in (payload.get("ready_labels") or []) if str(item or "").strip()]
    if not provider_name and not active_label and not healthy_labels and not ready_labels:
        return ""
    parts: list[str] = []
    if provider_name:
        parts.append(f"Provider {provider_name}")
    if active_label:
        parts.append(f"active label {active_label}")
    if ready_labels:
        parts.append(f"ready labels {', '.join(ready_labels)}")
    elif healthy_labels:
        parts.append(f"healthy labels {', '.join(healthy_labels)}")
    if not parts:
        return ""
    return " with ".join([parts[0], ", ".join(parts[1:])]) if len(parts) > 1 else parts[0]


def _best_matching_sentence(text: str, *, user_input: str) -> str:
    query_terms = set(_normalize_terms(user_input))
    candidates = [sentence for sentence in _candidate_sentences(text) if _line_is_meaningful(sentence)]
    if not candidates:
        return ""
    best_sentence = candidates[0]
    best_score = -1.0
    for sentence in candidates:
        terms = set(_normalize_terms(sentence))
        if not terms:
            continue
        score = _score_candidate_against_query(sentence, user_input=user_input)
        if score > best_score:
            best_score = score
            best_sentence = sentence
    return best_sentence


def _select_best_search_result(results: list[Any], *, query_text: str) -> dict[str, Any]:
    rows = [dict(row or {}) for row in results if isinstance(row, dict)]
    if not rows:
        return {}
    query = str(query_text or "").strip()
    query_lower = query.lower()
    best_row = rows[0]
    best_score = -1.0
    for row in rows:
        title = str(row.get("title") or "").strip()
        snippet = str(row.get("snippet") or "").strip()
        title_lower = title.lower()
        title_terms = set(_normalize_terms(title))
        snippet_terms = set(_normalize_terms(snippet))
        query_terms = set(_normalize_terms(query))
        title_overlap = len(query_terms & title_terms) / max(1, len(title_terms)) if title_terms else 0.0
        snippet_overlap = len(query_terms & snippet_terms) / max(1, len(query_terms)) if query_terms else 0.0
        who_question = query_lower.startswith("who ")
        phrase_bonus = 0.0 if who_question else (0.6 if title and title.lower() in query.lower() else 0.0)
        creator_bonus = 0.2 if "creat" in snippet.lower() or "creat" in title.lower() else 0.0
        person_bonus = 1.2 if who_question and _looks_like_person_title(title) else 0.0
        list_penalty = 0.5 if title_lower.startswith("list of ") else 0.0
        adaptation_penalty = 0.25 if any(token in title_lower for token in ("comics", "(character)", "film", "films")) else 0.0
        creature_penalty = 0.4 if who_question and any(token in title_lower for token in ("monster", "creature")) and not _looks_like_person_title(title) else 0.0
        score = (title_overlap * 2.0) + snippet_overlap + phrase_bonus + creator_bonus + person_bonus - list_penalty - adaptation_penalty - creature_penalty
        if score > best_score:
            best_score = score
            best_row = row
    return best_row


def _line_is_meaningful(value: str) -> bool:
    text = " ".join(str(value or "").split()).strip()
    if len(text) < 24:
        return False
    if text.startswith("|") or text.count("|") >= 2:
        return False
    lowered = text.lower()
    if lowered in {"contents", "references", "external links", "see also", "bibliography"}:
        return False
    return True


def _candidate_sentences(text: str) -> list[str]:
    normalized = " ".join(str(text or "").replace("\r", "\n").split())
    if not normalized:
        return []
    normalized = normalized.replace(". ", ".\n").replace("? ", "?\n").replace("! ", "!\n")
    return [
        sentence.strip()
        for sentence in normalized.split("\n")
        if sentence.strip()
    ]


def _score_candidate_against_query(sentence: str, *, user_input: str) -> float:
    query_terms = set(_normalize_terms(user_input))
    terms = set(_normalize_terms(sentence))
    if not terms:
        return -1.0
    overlap = len(query_terms & terms) / max(1, len(query_terms)) if query_terms else 0.0
    lowered = sentence.lower()
    creator_bonus = 0.25 if "created by" in lowered or "creator" in lowered or "creates" in lowered else 0.0
    brevity_bonus = 0.15 if len(sentence) <= 220 else 0.0
    brevity_penalty = min(0.25, max(0, len(sentence) - 320) / 1000.0)
    return overlap + creator_bonus + brevity_bonus - brevity_penalty


def _best_matching_retrieval_result_index(response: str, results: list[dict[str, Any]]) -> int:
    response_terms = set(_normalize_terms(response))
    if not response_terms:
        return 0
    best_index = 0
    best_score = -1.0
    for index, row in enumerate(results):
        candidate_terms = set(_normalize_terms(f"{row.get('summary') or ''} {row.get('excerpt') or ''}"))
        if not candidate_terms:
            continue
        overlap = len(response_terms & candidate_terms) / max(1, len(response_terms))
        if overlap > best_score:
            best_score = overlap
            best_index = index
    return best_index if best_score > 0 else 0


def _response_matches_runtime_grounding(response: str, grounded: str) -> bool:
    response_terms = set(_normalize_terms(response))
    grounded_terms = set(_normalize_terms(grounded))
    if not response_terms or not grounded_terms:
        return False
    overlap = len(response_terms & grounded_terms) / max(1, len(grounded_terms))
    return overlap >= 0.6


def _normalize_terms(text: str) -> list[str]:
    return [
        token
        for token in "".join(ch.lower() if ch.isalnum() else " " for ch in str(text or "")).split()
        if token
    ]


def _looks_like_person_title(title: str) -> bool:
    tokens = [token for token in str(title or "").replace("-", " ").split() if token]
    if len(tokens) < 2 or len(tokens) > 4:
        return False
    for token in tokens:
        if not token[0].isupper():
            return False
        if not any(char.isalpha() for char in token):
            return False
    return True


def _is_repeated_tool_invocation(decision: AgentPlannerDecision, tool_history: list[dict[str, Any]]) -> bool:
    if decision.action != "tool" or not tool_history:
        return False
    last = dict(tool_history[-1] or {})
    if str(last.get("tool_name") or "").strip() != decision.tool_name:
        return False
    last_input = dict(last.get("tool_input") or {})
    if last_input != dict(decision.tool_input or {}):
        return False
    tool_output = last.get("tool_output") if isinstance(last, dict) else None
    return isinstance(tool_output, dict) and bool(tool_output.get("ok"))


def _successful_tool_names(tool_history: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for item in tool_history or []:
        tool_name = str((item or {}).get("tool_name") or "").strip()
        tool_output = (item or {}).get("tool_output") if isinstance(item, dict) else None
        if tool_name and isinstance(tool_output, dict) and bool(tool_output.get("ok")):
            names.add(tool_name)
    return names
