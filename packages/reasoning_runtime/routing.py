"""Fail-closed production routing from qualification scorecards."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .factory import create_reasoning_client
from .models import ReasoningProfile, ReasoningRuntimeConfig
from .queueing import QueuedReasoningClient, ReasoningQueuePolicy


class UnqualifiedReasoningRouteError(RuntimeError):
    """Raised when production inference is requested for an unqualified family."""


@dataclass(frozen=True)
class LocalReasoningDeploymentPolicy:
    context_window_tokens: int = 4096
    timeout_seconds: int = 90
    keep_alive: str = "5m"
    ollama_gpu_layers: int = 32
    ollama_threads: int = 4
    ollama_thinking: bool | str = False
    lm_studio_reasoning_effort: str = "low"
    queue: ReasoningQueuePolicy = field(default_factory=ReasoningQueuePolicy)


class QualifiedReasoningRouter:
    """Resolve task families to local clients proven by a scorecard."""

    LOCAL_PROVIDERS = {"ollama_local", "lm_studio_local"}

    def __init__(
        self,
        *,
        scorecard: Mapping[str, Any],
        config: ReasoningRuntimeConfig,
        policy: LocalReasoningDeploymentPolicy | None = None,
    ) -> None:
        scorecard_policy = dict(scorecard.get("policy") or {})
        if scorecard_policy.get("allow_unqualified_fallback") is not False:
            raise ValueError("Production scorecard must explicitly disable unqualified fallback.")
        self._routes = {
            str(family): dict(route)
            for family, route in dict(scorecard.get("routes") or {}).items()
        }
        self._config = config
        self._policy = policy or LocalReasoningDeploymentPolicy()
        self._clients: dict[tuple[str, str], QueuedReasoningClient] = {}
        self._validate_qualified_routes()

    def qualified_families(self) -> tuple[str, ...]:
        return tuple(sorted(
            family for family, route in self._routes.items()
            if route.get("status") == "qualified"
        ))

    def client_for(self, task_family: str) -> QueuedReasoningClient:
        route = self._routes.get(str(task_family))
        if not route or route.get("status") != "qualified":
            raise UnqualifiedReasoningRouteError(
                f"No qualified local reasoning route for task family '{task_family}'."
            )
        provider = str(route.get("provider") or "")
        model = str(route.get("model") or "")
        key = (provider, model)
        if key not in self._clients:
            profile = self._profile(provider=provider, model=model)
            client = create_reasoning_client(
                profile_name=profile.name,
                profile=profile,
                config=self._config,
                queue_policy=self._policy.queue,
            )
            if not isinstance(client, QueuedReasoningClient):
                raise TypeError("Qualified local route must use bounded queue admission.")
            self._clients[key] = client
        return self._clients[key]

    def _validate_qualified_routes(self) -> None:
        for family, route in self._routes.items():
            if route.get("status") != "qualified":
                continue
            provider = str(route.get("provider") or "")
            model = str(route.get("model") or "")
            if provider not in self.LOCAL_PROVIDERS:
                raise ValueError(
                    f"Qualified route '{family}' uses non-local provider '{provider}'."
                )
            if not model:
                raise ValueError(f"Qualified route '{family}' is missing its exact model.")

    def _profile(self, *, provider: str, model: str) -> ReasoningProfile:
        common = {
            "name": f"qualified:{provider}:{model}",
            "timeout_seconds": self._policy.timeout_seconds,
            "max_retries": 1,
            "allow_account_rotation": False,
            "context_window_tokens": self._policy.context_window_tokens,
        }
        if provider == "ollama_local":
            return ReasoningProfile(
                **common,
                mode="ollama_local",
                ollama_model=model,
                ollama_keep_alive=self._policy.keep_alive,
                ollama_gpu_layers=self._policy.ollama_gpu_layers,
                ollama_threads=self._policy.ollama_threads,
                ollama_thinking=self._policy.ollama_thinking,
                ollama_stream_metrics=True,
            )
        return ReasoningProfile(
            **common,
            mode="lm_studio_local",
            lm_studio_model=model,
            lm_studio_reasoning_effort=self._policy.lm_studio_reasoning_effort,
            lm_studio_stream_metrics=True,
        )
