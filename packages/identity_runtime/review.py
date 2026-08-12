"""Evidence-grounded contamination review for identity runtime outputs."""

from __future__ import annotations

import re
from typing import Any

from packages.identity_runtime.contracts import (
    IdentityAliasEvidence,
    IdentityCluster,
    IdentityGroundingReviewResult,
    IdentityMergeEvidence,
    IdentityQualityDiagnostic,
    ReviewedIdentityCluster,
)


GENERIC_LEADERS = {"the", "a", "an", "my", "your", "his", "her", "their", "our", "this", "that", "these", "those"}
GENERIC_ROLE_TERMS = {
    "boy",
    "girl",
    "man",
    "woman",
    "youngest",
    "eldest",
    "children",
    "child",
    "sister",
    "sisters",
    "brother",
    "brothers",
    "mother",
    "father",
    "parents",
    "queen",
    "king",
    "prince",
    "princess",
    "folk",
    "monster",
    "creature",
    "hero",
    "fiddler",
    "reveler",
    "revelers",
    "bride",
    "wife",
    "husband",
    "daughter",
    "son",
    "person",
    "people",
    "twins",
    "girls",
    "boys",
}
GENERIC_ENTITY_TERMS = {
    "castle",
    "house",
    "palace",
    "river",
    "lake",
    "bank",
    "body",
    "water",
    "woods",
    "forest",
    "land",
    "court",
    "kingdom",
    "world",
    "elfhame",
    "faerie",
    "home",
    "humans",
}
GENERIC_SINGLETON_TERMS = {"some", "there", "here", "someone", "something", "everyone", "everybody", "nobody", "nothing"}
TITLE_WORDS = {"mr", "mrs", "ms", "sir", "lord", "lady", "king", "queen", "prince", "princess", "general", "high"}
IDENTITY_TITLES = TITLE_WORDS | {"miss", "dr", "doctor", "captain"}
IDENTITY_DESCRIPTORS = {"little", "young", "old"}
PRONOUN_ONLY_FORMS = {
    "i",
    "me",
    "my",
    "myself",
    "we",
    "us",
    "our",
    "ourselves",
    "you",
    "your",
    "yourself",
    "yourselves",
    "he",
    "him",
    "his",
    "himself",
    "she",
    "her",
    "herself",
    "they",
    "them",
    "their",
    "themselves",
}


def review_identity_clusters(
    *,
    raw_clusters: list[dict[str, Any]],
    chapters: list[dict[str, Any]],
    scenes: list[dict[str, Any]],
) -> IdentityGroundingReviewResult:
    prepared_clusters = [_normalize_cluster(item) for item in raw_clusters]
    scene_texts = [
        {
            "scene_id": str(scene.get("scene_id") or "").strip(),
            "chapter_index": int(scene.get("chapter_index") or 0),
            "text": str(scene.get("text") or ""),
        }
        for scene in scenes
    ]
    chapter_texts = [
        {
            "chapter_index": int(chapter.get("chapter_index") or 0),
            "text": str(chapter.get("content") or ""),
        }
        for chapter in chapters
    ]
    canonical_names = {
        _normalize_name(_select_display_name(cluster)): _select_display_name(cluster)
        for cluster in prepared_clusters
        if _select_display_name(cluster)
    }
    alias_owner_counts: dict[str, list[str]] = {}
    for cluster in prepared_clusters:
        display_name = _select_display_name(cluster)
        if not display_name:
            continue
        candidates = _candidate_aliases(cluster, display_name=display_name)
        for alias in candidates:
            normalized_alias = _normalize_name(alias)
            if not normalized_alias:
                continue
            alias_owner_counts.setdefault(normalized_alias, []).append(display_name)

    reviewed: list[ReviewedIdentityCluster] = []
    diagnostics: list[IdentityQualityDiagnostic] = []
    for cluster in prepared_clusters:
        display_name = _select_display_name(cluster)
        cluster_diagnostics: list[IdentityQualityDiagnostic] = []
        cluster_alias_evidence: list[IdentityAliasEvidence] = []
        if not display_name:
            raw_display_name = _clean_name(cluster.display_name)
            dropped = _reviewed_cluster(
                cluster=cluster,
                display_name=raw_display_name,
                accepted_aliases=[],
                rejected_aliases=[],
                evidence=[],
                keep_cluster=False,
                diagnostics=[
                    IdentityQualityDiagnostic(
                        code="missing_display_name",
                        severity="error",
                        message="Cluster has no viable grounded display name.",
                        cluster_id=int(cluster.cluster_id or 0),
                        display_name=raw_display_name,
                    )
                ],
            )
            reviewed.append(dropped)
            diagnostics.extend(dropped.diagnostics)
            continue

        if _reject_cluster_name(display_name, canonical_names=canonical_names):
            dropped = _reviewed_cluster(
                cluster=cluster,
                display_name=display_name,
                accepted_aliases=[],
                rejected_aliases=_candidate_aliases(cluster, display_name=display_name),
                evidence=[],
                keep_cluster=False,
                diagnostics=[
                    IdentityQualityDiagnostic(
                        code="generic_or_non_character_cluster",
                        severity="warning",
                        message="Cluster name looks generic or non-character and was dropped.",
                        cluster_id=int(cluster.cluster_id or 0),
                        display_name=display_name,
                    )
                ],
            )
            reviewed.append(dropped)
            diagnostics.extend(dropped.diagnostics)
            continue

        accepted_aliases: list[str] = []
        rejected_aliases: list[str] = []
        for alias in _candidate_aliases(cluster, display_name=display_name):
            evidence = _build_alias_evidence(
                alias=alias,
                scene_texts=scene_texts,
                chapter_texts=chapter_texts,
                canonical_names=canonical_names,
            )
            cluster_alias_evidence.append(evidence)
            rejection_code = _reject_alias(
                alias=alias,
                display_name=display_name,
                evidence=evidence,
                alias_owner_counts=alias_owner_counts,
                canonical_names=canonical_names,
            )
            if rejection_code:
                rejected_aliases.append(alias)
                cluster_diagnostics.append(
                    IdentityQualityDiagnostic(
                        code=rejection_code,
                        severity="warning",
                        message=_diagnostic_message(rejection_code, alias=alias, display_name=display_name),
                        cluster_id=int(cluster.cluster_id or 0),
                        display_name=display_name,
                        alias=alias,
                        related_character_ids=list(evidence.matched_character_ids or []),
                        metadata={"support_count": evidence.support_count},
                    )
                )
                continue
            if alias != display_name:
                accepted_aliases.append(alias)

        reviewed_cluster = _reviewed_cluster(
            cluster=cluster,
            display_name=display_name,
            accepted_aliases=accepted_aliases,
            rejected_aliases=rejected_aliases,
            evidence=cluster_alias_evidence,
            keep_cluster=True,
            diagnostics=cluster_diagnostics,
        )
        reviewed.append(reviewed_cluster)
        diagnostics.extend(cluster_diagnostics)

    canonical_reviewed, merge_evidence = _canonicalize_reviewed_clusters(reviewed, prepared_clusters)
    return IdentityGroundingReviewResult(
        reviewed_clusters=canonical_reviewed,
        diagnostics=diagnostics,
        kept_cluster_count=sum(1 for item in canonical_reviewed if item.keep_cluster),
        dropped_cluster_count=sum(1 for item in reviewed if not item.keep_cluster),
        accepted_alias_count=sum(len(item.accepted_aliases) for item in canonical_reviewed),
        rejected_alias_count=sum(len(item.rejected_aliases) for item in reviewed),
        merge_count=sum(max(0, len(item.source_cluster_ids) - 1) for item in canonical_reviewed),
        merge_evidence=merge_evidence,
    )


def _normalize_cluster(raw: dict[str, Any]) -> IdentityCluster:
    return IdentityCluster.model_validate(
        {
            "cluster_id": int(raw.get("cluster_id") or 0),
            "display_name": str(raw.get("display_name") or "").strip(),
            "aliases": list(raw.get("aliases") or []),
            "mentions": list(raw.get("mentions") or []),
            "mention_count": int(raw.get("mention_count") or 0),
            "proper_mentions": list(raw.get("proper_mentions") or []),
            "pronoun_mentions": list(raw.get("pronoun_mentions") or []),
        }
    )


def _reviewed_cluster(
    *,
    cluster: IdentityCluster,
    display_name: str,
    accepted_aliases: list[str],
    rejected_aliases: list[str],
    evidence: list[IdentityAliasEvidence],
    keep_cluster: bool,
    diagnostics: list[IdentityQualityDiagnostic],
) -> ReviewedIdentityCluster:
    reviewed_cluster = IdentityCluster.model_validate(
        {
            **cluster.model_dump(),
            "display_name": display_name,
            "aliases": accepted_aliases,
            "proper_mentions": [item for item in _unique_strings([display_name, *accepted_aliases]) if item],
            "pronoun_mentions": [item for item in _unique_strings(list(cluster.pronoun_mentions or [])) if _normalize_name(item) not in PRONOUN_ONLY_FORMS],
        }
    )
    return ReviewedIdentityCluster(
        cluster=reviewed_cluster,
        source_cluster_ids=[int(cluster.cluster_id or 0)],
        keep_cluster=keep_cluster,
        accepted_aliases=accepted_aliases,
        rejected_aliases=rejected_aliases,
        evidence=evidence,
        diagnostics=diagnostics,
    )


def _canonicalize_reviewed_clusters(
    reviewed: list[ReviewedIdentityCluster],
    raw_clusters: list[IdentityCluster],
) -> tuple[list[ReviewedIdentityCluster], list[IdentityMergeEvidence]]:
    kept = [item for item in reviewed if item.keep_cluster]
    dropped = [item for item in reviewed if not item.keep_cluster]
    if len(kept) < 2:
        return reviewed, []

    raw_by_id = {int(item.cluster_id or 0): item for item in raw_clusters}
    parent = list(range(len(kept)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    pair_signals: dict[tuple[int, int], list[str]] = {}
    for left_index, left in enumerate(kept):
        for right_index in range(left_index + 1, len(kept)):
            right = kept[right_index]
            signals = _merge_signals(
                left.cluster,
                right.cluster,
                raw_by_id=raw_by_id,
            )
            if not signals:
                continue
            union(left_index, right_index)
            pair_signals[(left_index, right_index)] = signals

    groups: dict[int, list[int]] = {}
    for index in range(len(kept)):
        groups.setdefault(find(index), []).append(index)

    canonical: list[ReviewedIdentityCluster] = []
    evidence_rows: list[IdentityMergeEvidence] = []
    for indices in groups.values():
        members = [kept[index] for index in indices]
        if len(members) == 1:
            canonical.append(members[0])
            continue
        merged = _merge_reviewed_group(members)
        canonical.append(merged)
        signals = _unique_strings(
            [signal for pair, values in pair_signals.items() if pair[0] in indices and pair[1] in indices for signal in values]
        )
        evidence_rows.append(
            IdentityMergeEvidence(
                source_cluster_ids=merged.source_cluster_ids,
                source_display_names=_unique_strings([item.cluster.display_name for item in members]),
                canonical_display_name=merged.cluster.display_name,
                signals=signals,
            )
        )
    canonical.sort(key=lambda item: (-int(item.cluster.mention_count or 0), item.cluster.display_name.casefold()))
    return [*canonical, *dropped], evidence_rows


def _merge_signals(
    left: IdentityCluster,
    right: IdentityCluster,
    *,
    raw_by_id: dict[int, IdentityCluster],
) -> list[str]:
    left_name, right_name = _clean_name(left.display_name), _clean_name(right.display_name)
    if not left_name or not right_name:
        return []
    if _normalize_name(left_name) == _normalize_name(right_name):
        return ["same_normalized_display_name"]
    if len(left_name.split()) > 3 or len(right_name.split()) > 3:
        return []

    left_raw = raw_by_id.get(int(left.cluster_id or 0), left)
    right_raw = raw_by_id.get(int(right.cluster_id or 0), right)
    left_claims = {_normalize_name(item) for item in _candidate_aliases(left_raw, display_name=left_name)}
    right_claims = {_normalize_name(item) for item in _candidate_aliases(right_raw, display_name=right_name)}
    left_claims_right = _normalize_name(right_name) in left_claims
    right_claims_left = _normalize_name(left_name) in right_claims
    if not left_claims_right and not right_claims_left:
        return []

    left_core, left_modifier = _identity_name_parts(left_name)
    right_core, right_modifier = _identity_name_parts(right_name)
    if not left_core or not right_core:
        return []
    overlap = left_core & right_core
    if not overlap:
        return []
    if not (left_core <= right_core or right_core <= left_core):
        return []

    signals = ["provider_alias_claim", "compatible_name_structure"]
    if left_claims_right and right_claims_left:
        signals.append("reciprocal_provider_alias_claim")
    if left_modifier == "descriptor" or right_modifier == "descriptor":
        descriptor_claims = left_claims if left_modifier == "descriptor" else right_claims
        complete_core = right_core if left_modifier == "descriptor" else left_core
        if not any(_identity_name_parts(alias)[0] & (complete_core - overlap) for alias in descriptor_claims):
            return []
        signals.append("descriptor_linked_to_distinctive_name")
    elif left_modifier == "title" or right_modifier == "title":
        signals.append("title_or_honorific_variant")
    else:
        signals.append("partial_full_name_variant")
    return signals


def _identity_name_parts(value: str) -> tuple[set[str], str]:
    tokens = [token.casefold().strip(".") for token in _clean_name(value).split() if token]
    modifier = ""
    if tokens and tokens[0] in IDENTITY_TITLES:
        modifier = "title"
        tokens = tokens[1:]
    elif tokens and tokens[0] in IDENTITY_DESCRIPTORS:
        modifier = "descriptor"
        tokens = tokens[1:]
    return set(tokens), modifier


def _merge_reviewed_group(members: list[ReviewedIdentityCluster]) -> ReviewedIdentityCluster:
    canonical_member = sorted(members, key=_canonical_member_score)[0]
    display_name = canonical_member.cluster.display_name
    source_names = [item.cluster.display_name for item in members]
    accepted_aliases = _unique_strings(
        [*source_names, *[alias for item in members for alias in item.accepted_aliases]]
    )
    accepted_aliases = [alias for alias in accepted_aliases if _normalize_name(alias) != _normalize_name(display_name)]
    source_ids = sorted({cluster_id for item in members for cluster_id in item.source_cluster_ids})
    merged_cluster = IdentityCluster(
        cluster_id=min(source_ids),
        display_name=display_name,
        aliases=accepted_aliases,
        mentions=_unique_strings([mention for item in members for mention in item.cluster.mentions]),
        mention_count=max(int(item.cluster.mention_count or 0) for item in members),
        proper_mentions=_unique_strings([display_name, *source_names, *accepted_aliases]),
        pronoun_mentions=_unique_strings([mention for item in members for mention in item.cluster.pronoun_mentions]),
    )
    return ReviewedIdentityCluster(
        cluster=merged_cluster,
        source_cluster_ids=source_ids,
        keep_cluster=True,
        accepted_aliases=accepted_aliases,
        rejected_aliases=_unique_strings([alias for item in members for alias in item.rejected_aliases if alias not in source_names]),
        evidence=[evidence for item in members for evidence in item.evidence],
        diagnostics=[diagnostic for item in members for diagnostic in item.diagnostics],
    )


def _canonical_member_score(item: ReviewedIdentityCluster) -> tuple[int, int, int, int, str]:
    name = _clean_name(item.cluster.display_name)
    core, modifier = _identity_name_parts(name)
    modifier_penalty = 1 if modifier else 0
    descriptor_penalty = 1 if modifier == "descriptor" else 0
    return (descriptor_penalty, modifier_penalty, -len(core), -int(item.cluster.mention_count or 0), name.casefold())


def _select_display_name(cluster: IdentityCluster) -> str:
    raw_candidates = (
        [(cluster.display_name, 0)]
        + [(item, 1) for item in list(cluster.proper_mentions or [])]
        + [(item, 2) for item in list(cluster.aliases or [])]
    )
    seen: set[str] = set()
    viable: list[tuple[tuple[int, int, int, int, str], str]] = []
    for candidate, source_priority in raw_candidates:
        cleaned = _clean_name(candidate)
        if not _is_viable_name(cleaned):
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        viable.append((_display_name_score(cleaned, source_priority=source_priority), cleaned))
    if not viable:
        return ""
    scored = sorted(viable, key=lambda item: item[0])
    return scored[0][1] if scored else ""


def _candidate_aliases(cluster: IdentityCluster, *, display_name: str) -> list[str]:
    return [
        item
        for item in _unique_strings([display_name, *list(cluster.proper_mentions or []), *list(cluster.aliases or [])])
        if _clean_name(item)
    ]


def _build_alias_evidence(
    *,
    alias: str,
    scene_texts: list[dict[str, Any]],
    chapter_texts: list[dict[str, Any]],
    canonical_names: dict[str, str],
) -> IdentityAliasEvidence:
    normalized_alias = _normalize_name(alias)
    pattern = _alias_pattern(alias)
    support_scene_ids: list[str] = []
    support_chapters: list[int] = []
    support_count = 0
    for row in scene_texts:
        text = str(row.get("text") or "")
        matches = len(pattern.findall(text)) if pattern else 0
        if matches:
            support_count += matches
            scene_id = str(row.get("scene_id") or "").strip()
            if scene_id:
                support_scene_ids.append(scene_id)
            chapter_index = int(row.get("chapter_index") or 0)
            if chapter_index:
                support_chapters.append(chapter_index)
    if not support_count:
        for row in chapter_texts:
            text = str(row.get("text") or "")
            matches = len(pattern.findall(text)) if pattern else 0
            if matches:
                support_count += matches
                chapter_index = int(row.get("chapter_index") or 0)
                if chapter_index:
                    support_chapters.append(chapter_index)
    matched_character_ids: list[str] = []
    matched_display_names: list[str] = []
    if normalized_alias in canonical_names:
        display_name = canonical_names[normalized_alias]
        matched_display_names.append(display_name)
        matched_character_ids.append(f"char-{_slug(display_name)}")
    return IdentityAliasEvidence(
        alias=alias,
        support_count=support_count,
        chapter_indices=sorted(set(support_chapters)),
        scene_ids=_unique_strings(support_scene_ids),
        matched_character_ids=matched_character_ids,
        matched_display_names=matched_display_names,
    )


def _reject_cluster_name(display_name: str, *, canonical_names: dict[str, str]) -> bool:
    cleaned = _clean_name(display_name)
    tokens = [token.casefold().strip(".") for token in cleaned.split() if token]
    if not cleaned:
        return True
    if len(tokens) == 1 and tokens[0] in GENERIC_SINGLETON_TERMS:
        return True
    if cleaned.casefold() != cleaned and len(tokens) == 1 and tokens[0] in GENERIC_ENTITY_TERMS:
        return True
    if len(tokens) <= 3 and any(token in {"twins", "children", "folk", "people", "girls", "boys"} for token in tokens):
        return True
    if len(tokens) <= 4 and any(token in GENERIC_ROLE_TERMS for token in tokens) and not _is_titled_name(cleaned):
        return True
    if cleaned.casefold() == cleaned and len(tokens) <= 3:
        if any(token in GENERIC_ROLE_TERMS or token in GENERIC_ENTITY_TERMS for token in tokens):
            return True
    if tokens and tokens[0] in GENERIC_LEADERS and any(token in GENERIC_ROLE_TERMS or token in GENERIC_ENTITY_TERMS for token in tokens[1:]):
        return True
    normalized = _normalize_name(cleaned)
    owner = canonical_names.get(normalized, "")
    if owner and owner != cleaned:
        return True
    return False


def _reject_alias(
    *,
    alias: str,
    display_name: str,
    evidence: IdentityAliasEvidence,
    alias_owner_counts: dict[str, list[str]],
    canonical_names: dict[str, str],
) -> str:
    cleaned = _clean_name(alias)
    if not cleaned:
        return "empty_alias"
    if cleaned == display_name:
        return ""
    if not _is_viable_name(cleaned):
        return "malformed_alias_rejected"
    normalized = _normalize_name(cleaned)
    tokens = [token.casefold().strip(".") for token in cleaned.split() if token]
    if normalized in PRONOUN_ONLY_FORMS:
        return "pronoun_alias_rejected"
    if tokens and tokens[0] in {"this", "that", "these", "those"}:
        return "generic_role_alias_rejected"
    if tokens and tokens[0] in GENERIC_LEADERS and len(tokens) <= 3 and any(token in GENERIC_ROLE_TERMS for token in tokens[1:]):
        return "generic_role_alias_rejected"
    if len(tokens) <= 3 and any(token in GENERIC_ROLE_TERMS for token in tokens) and not _is_titled_name(cleaned):
        return "generic_role_alias_rejected"
    if cleaned.casefold() == cleaned and len(tokens) <= 3 and any(token in GENERIC_ROLE_TERMS or token in GENERIC_ENTITY_TERMS for token in tokens):
        return "generic_role_alias_rejected"
    canonical_owner = canonical_names.get(normalized, "")
    if canonical_owner and canonical_owner != display_name:
        return "cross_character_alias_rejected"
    owners = {name for name in alias_owner_counts.get(normalized, []) if name and name != display_name}
    if owners:
        return "ambiguous_alias_rejected"
    if evidence.support_count <= 0 and not _is_title_case_name(cleaned):
        return "ungrounded_alias_rejected"
    if len(tokens) == 1 and cleaned[:1].islower():
        return "generic_role_alias_rejected"
    return ""


def _diagnostic_message(code: str, *, alias: str, display_name: str) -> str:
    messages = {
        "pronoun_alias_rejected": f"Alias '{alias}' was rejected because it is pronoun-like, not a stable character surface form.",
        "generic_role_alias_rejected": f"Alias '{alias}' was rejected because it is too generic to safely bind to '{display_name}'.",
        "cross_character_alias_rejected": f"Alias '{alias}' was rejected because it maps to another stronger character identity.",
        "ambiguous_alias_rejected": f"Alias '{alias}' was rejected because multiple clusters claim it.",
        "ungrounded_alias_rejected": f"Alias '{alias}' was rejected because it lacked grounded evidence in the text.",
        "malformed_alias_rejected": f"Alias '{alias}' was rejected because it does not look like a stable character surface form.",
        "empty_alias": "An empty alias candidate was rejected.",
    }
    return messages.get(code, f"Alias '{alias}' was rejected during identity contamination review.")


def _is_viable_name(value: str) -> bool:
    cleaned = _clean_name(value)
    if not cleaned:
        return False
    if len(cleaned) < 2 or len(cleaned) > 60:
        return False
    if any(symbol in cleaned for symbol in {",", ":", ";", "?", "!", "\"", "“", "”", "’ll", "’m", "—", "–"}):
        return False
    if re.search(r"[^A-Za-z0-9 .'\-]", cleaned):
        return False
    tokens = [token.casefold().strip(".") for token in cleaned.split() if token]
    if not tokens or len(tokens) > 5:
        return False
    if tokens[0] in PRONOUN_ONLY_FORMS:
        return False
    if "named" in tokens or "called" in tokens:
        return False
    if any(token in {"because", "otherwise", "recalled", "talk", "marry", "window", "story", "fun"} for token in tokens):
        return False
    if cleaned.casefold() == cleaned and any(token in GENERIC_ENTITY_TERMS for token in tokens):
        return False
    return True


def _display_name_score(value: str, *, source_priority: int) -> tuple[int, int, int, int, str]:
    cleaned = _clean_name(value)
    tokens = [token.casefold().strip(".") for token in cleaned.split() if token]
    penalty = 0
    if tokens and tokens[0] in GENERIC_LEADERS:
        penalty += 4
    if any(token in GENERIC_ROLE_TERMS for token in tokens):
        penalty += 2
    if any(token in TITLE_WORDS for token in tokens):
        penalty -= 2
    if len(tokens) >= 2 and _is_title_case_name(cleaned):
        penalty -= 1
    return (penalty, source_priority, len(tokens), -len(cleaned), cleaned.casefold())


def _is_title_case_name(value: str) -> bool:
    words = _clean_name(value).split()
    return any(word[:1].isupper() for word in words if word)


def _is_titled_name(value: str) -> bool:
    words = _clean_name(value).split()
    if len(words) < 2:
        return False
    leader = words[0].casefold().strip(".")
    if leader not in TITLE_WORDS:
        return False
    return all(word[:1].isupper() for word in words[1:] if word)


def _clean_name(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "").replace("\n", " ").replace("\r", " ").strip())
    cleaned = cleaned.strip(" ,.;:!?\"'()[]{}")
    return cleaned


def _normalize_name(value: str) -> str:
    return _clean_name(value).casefold()


def _alias_pattern(value: str):
    cleaned = _clean_name(value)
    if not cleaned:
        return None
    return re.compile(rf"(?<![A-Za-z0-9]){re.escape(cleaned)}(?![A-Za-z0-9])", flags=re.IGNORECASE)


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return cleaned or "identity"


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for value in values:
        cleaned = _clean_name(value)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        results.append(cleaned)
    return results
