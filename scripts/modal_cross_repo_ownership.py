from __future__ import annotations

EXPECTED_MODAL_UNIVERSE = [f"modal-{n:02d}" for n in range(1, 48)]


def find_cross_repo_modal_ownership_problems(
    *, saga_manifest: dict, renderlab_manifest: dict
) -> list[str]:
    problems: list[str] = []
    if saga_manifest.get("project") != "saga":
        problems.append("S.A.G.A. ownership manifest must declare project=saga.")
    if renderlab_manifest.get("project") != "renderlab":
        problems.append("RenderLab ownership manifest must declare project=renderlab.")

    saga_owned = saga_manifest.get("ownedAccountLabels")
    saga_renderlab = (saga_manifest.get("reservedForOtherProjects") or {}).get("renderlab")
    renderlab_owned = renderlab_manifest.get("ownedAccountLabels")
    renderlab_saga = (renderlab_manifest.get("reservedForOtherProjects") or {}).get("saga")

    if saga_owned != renderlab_saga:
        problems.append("S.A.G.A.-owned accounts disagree with RenderLab's S.A.G.A. reservation.")
    if saga_renderlab != renderlab_owned:
        problems.append("RenderLab-owned accounts disagree with S.A.G.A.'s RenderLab reservation.")

    if isinstance(saga_owned, list) and isinstance(renderlab_owned, list):
        if set(saga_owned).intersection(renderlab_owned):
            problems.append("Cross-repository Modal ownership overlaps.")
        if sorted([*saga_owned, *renderlab_owned]) != sorted(EXPECTED_MODAL_UNIVERSE):
            problems.append(
                "Combined cross-repository ownership must cover exactly modal-01 through modal-47 once."
            )
    else:
        problems.append("Cross-repository Modal ownership lists must be arrays.")

    return problems


def assert_cross_repo_modal_ownership(*, saga_manifest: dict, renderlab_manifest: dict) -> None:
    problems = find_cross_repo_modal_ownership_problems(
        saga_manifest=saga_manifest, renderlab_manifest=renderlab_manifest
    )
    if problems:
        raise RuntimeError(
            "Cross-repository Modal ownership verification failed:\n- " + "\n- ".join(problems)
        )
