from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from packages.reasoning_runtime.contracts import ReasoningRequestMetadata
from packages.runtime_common import RuntimeToolEnvelope, RuntimeTrace


class AgentPlannerDecision(BaseModel):
    action: Literal["tool", "respond"] = Field(description="Whether to use a tool next or respond to the user.")
    rationale: str = Field(default="", description="Short explanation for the chosen next step.")
    response: str = Field(default="", description="Final response to return when action is 'respond'.")
    tool_name: str = Field(default="", description="Tool to invoke when action is 'tool'.")
    tool_input: dict[str, Any] = Field(default_factory=dict, description="Structured arguments for the selected tool.")


class AgentPlannerDecisionResponseFormat(BaseModel):
    type: Literal["json_schema"] = "json_schema"
    json_schema: dict[str, Any] = Field(default_factory=dict)


class ToolExecutionRecord(BaseModel):
    tool_name: str
    tool_input: dict[str, Any] = Field(default_factory=dict)
    tool_output: RuntimeToolEnvelope
    rationale: str = ""
    trace: RuntimeTrace


class PlannerExecutionRecord(BaseModel):
    step_index: int = 0
    prompt: str = ""
    decision: AgentPlannerDecision | None = None
    metadata: ReasoningRequestMetadata = Field(default_factory=ReasoningRequestMetadata)
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    error: str = ""


class AgentExecutionSummary(BaseModel):
    run_id: str = ""
    thread_id: str = ""
    status: Literal["ok", "error", "max_steps_exceeded"] = "ok"
    planner_steps: int = 0
    tool_steps: int = 0
    successful_tool_steps: int = 0
    failed_tool_steps: int = 0
    latest_tool_name: str = ""
    latest_trace_id: str = ""
    required_tools_total: int = 0
    required_tools_completed: int = 0
    remaining_required_tools: list[str] = Field(default_factory=list)


class AgentExecutionReport(BaseModel):
    report_type: Literal["agent_execution_report"] = "agent_execution_report"
    final_output: str = ""
    error: str = ""
    summary: AgentExecutionSummary = Field(default_factory=AgentExecutionSummary)
    planner_history: list[PlannerExecutionRecord] = Field(default_factory=list)
    tool_history: list[ToolExecutionRecord] = Field(default_factory=list)
    last_decision: AgentPlannerDecision | None = None


class AgentExecutionResult(BaseModel):
    final_output: str
    steps: int = 0
    planner_history: list[PlannerExecutionRecord] = Field(default_factory=list)
    tool_history: list[ToolExecutionRecord] = Field(default_factory=list)
    last_decision: AgentPlannerDecision | None = None
    error: str = ""
    summary: AgentExecutionSummary = Field(default_factory=AgentExecutionSummary)

    def to_report_payload(self) -> dict[str, Any]:
        return AgentExecutionReport(
            final_output=self.final_output,
            error=self.error,
            summary=self.summary,
            planner_history=self.planner_history,
            tool_history=self.tool_history,
            last_decision=self.last_decision,
        ).model_dump()
