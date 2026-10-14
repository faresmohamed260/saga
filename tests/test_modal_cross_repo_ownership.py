from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.modal_cross_repo_ownership import (
    EXPECTED_MODAL_UNIVERSE,
    assert_cross_repo_modal_ownership,
    find_cross_repo_modal_ownership_problems,
)


SAGA_MANIFEST = json.loads(
    Path("config/modal-project-ownership.json").read_text(encoding="utf-8")
)
RENDERLAB_MANIFEST = {
    "project": "renderlab",
    "ownedAccountLabels": ["modal-01", "modal-02", *[f"modal-{n:02d}" for n in range(42, 48)]],
    "reservedForOtherProjects": {
        "saga": [f"modal-{n:02d}" for n in range(3, 42)]
    },
}


def test_reciprocal_modal_manifests_cover_all_accounts_once() -> None:
    assert len(EXPECTED_MODAL_UNIVERSE) == 47
    assert_cross_repo_modal_ownership(
        saga_manifest=SAGA_MANIFEST, renderlab_manifest=RENDERLAB_MANIFEST
    )


def test_renderlab_reservation_drift_fails_closed() -> None:
    drifted = json.loads(json.dumps(RENDERLAB_MANIFEST))
    drifted["reservedForOtherProjects"]["saga"] = drifted["reservedForOtherProjects"]["saga"][1:]
    problems = find_cross_repo_modal_ownership_problems(
        saga_manifest=SAGA_MANIFEST, renderlab_manifest=drifted
    )
    assert any("disagree" in problem for problem in problems)


def test_overlap_and_incomplete_coverage_fail_closed() -> None:
    drifted = json.loads(json.dumps(RENDERLAB_MANIFEST))
    drifted["ownedAccountLabels"][0] = "modal-03"
    problems = find_cross_repo_modal_ownership_problems(
        saga_manifest=SAGA_MANIFEST, renderlab_manifest=drifted
    )
    assert any("overlaps" in problem for problem in problems)
    assert any("modal-01 through modal-47" in problem for problem in problems)


@pytest.mark.parametrize("project", [None, "studio", "renderlab"])
def test_wrong_saga_project_identity_fails(project: str | None) -> None:
    drifted = json.loads(json.dumps(SAGA_MANIFEST))
    drifted["project"] = project
    with pytest.raises(RuntimeError, match="project=saga"):
        assert_cross_repo_modal_ownership(
            saga_manifest=drifted, renderlab_manifest=RENDERLAB_MANIFEST
        )
