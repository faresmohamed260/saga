"""Factory helpers for portable reasoning clients."""

from __future__ import annotations

from packages.reasoning_runtime.client import ReasoningRuntimeClient
from packages.reasoning_runtime.models import ReasoningProfile, ReasoningRuntimeConfig
from packages.reasoning_runtime.provider_config import apply_persistence_provider_configs
from packages.reasoning_runtime.queueing import QueuedReasoningClient, ReasoningQueuePolicy


def create_reasoning_client(
    *,
    profile_name: str,
    config: ReasoningRuntimeConfig,
    profile: ReasoningProfile | None = None,
    persistence_client=None,
    queue_policy: ReasoningQueuePolicy | None = None,
) -> ReasoningRuntimeClient | QueuedReasoningClient:
    resolved_profile = profile or config.profiles.get(profile_name)
    if resolved_profile is None:
        raise KeyError(f"Unknown reasoning profile '{profile_name}'.")
    resolved_config = config
    if persistence_client is not None:
        resolved_config = apply_persistence_provider_configs(config, persistence_client=persistence_client)
    client = ReasoningRuntimeClient(profile=resolved_profile, config=resolved_config)
    return QueuedReasoningClient(client, policy=queue_policy) if queue_policy else client
