from __future__ import annotations

import pytest

from packages.reasoning_runtime import (
    QualifiedReasoningRouter,
    ReasoningRuntimeConfig,
    UnqualifiedReasoningRouteError,
)


def _scorecard():
    return {
        "policy": {"allow_unqualified_fallback": False},
        "routes": {
            "structured_json": {
                "status": "qualified",
                "provider": "ollama_local",
                "model": "mistral:7b-instruct",
            },
            "tool_use": {
                "status": "qualified",
                "provider": "ollama_local",
                "model": "mistral:7b-instruct",
            },
            "canon_entities": {"status": "unqualified", "model": None},
        },
    }


def test_router_reuses_one_bounded_local_client_for_shared_model():
    router = QualifiedReasoningRouter(
        scorecard=_scorecard(),
        config=ReasoningRuntimeConfig(),
    )

    json_client = router.client_for("structured_json")
    tool_client = router.client_for("tool_use")

    assert json_client is tool_client
    assert json_client.policy.max_concurrency == 1
    assert json_client.policy.queue_capacity == 8
    assert json_client.client.profile.mode == "ollama_local"
    assert json_client.client.profile.ollama_model == "mistral:7b-instruct"
    assert json_client.client.profile.allow_account_rotation is False
    assert json_client.client.profile.max_retries == 1
    assert router.qualified_families() == ("structured_json", "tool_use")


def test_router_fails_closed_for_unqualified_or_unknown_family():
    router = QualifiedReasoningRouter(
        scorecard=_scorecard(),
        config=ReasoningRuntimeConfig(),
    )

    with pytest.raises(UnqualifiedReasoningRouteError, match="canon_entities"):
        router.client_for("canon_entities")
    with pytest.raises(UnqualifiedReasoningRouteError, match="narrative_generation"):
        router.client_for("narrative_generation")


def test_router_rejects_cloud_provider_and_implicit_fallback():
    with pytest.raises(ValueError, match="disable unqualified fallback"):
        QualifiedReasoningRouter(
            scorecard={"policy": {}, "routes": {}},
            config=ReasoningRuntimeConfig(),
        )

    scorecard = _scorecard()
    scorecard["routes"]["structured_json"]["provider"] = "mistral"
    with pytest.raises(ValueError, match="non-local provider"):
        QualifiedReasoningRouter(
            scorecard=scorecard,
            config=ReasoningRuntimeConfig(),
        )
