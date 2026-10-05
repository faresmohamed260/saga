from dataclasses import replace

import pytest

from packages.narrative_compiler.benchmark import score_identity_clusters
from packages.narrative_compiler.fingerprint import artifact_fingerprint, config_fingerprint
from packages.narrative_compiler.ir import AcceptanceState, EntityType, Mention, SourceSpan
from packages.narrative_compiler.linker import ExactSurfaceCharacterLinker
from packages.narrative_compiler.source import NormalizedSource


def source_payload():
    text = "Rhys arrived. Rhys smiled. She left."
    return {
        "normalizationVersion": "test-v1",
        "configFingerprint": "cfg-source",
        "normalizedSha256": "a" * 64,
        "outputFingerprint": "b" * 64,
        "normalizedText": text,
        "sections": [
            {
                "stable_key": "chapter:0",
                "ordinal": 0,
                "section_kind": "chapter",
                "title": "One",
                "source_locator": "chapter-1",
                "start_offset": 0,
                "end_offset": len(text),
                "normalized_text": text,
            }
        ],
    }


def mention(source, text, start):
    return Mention.create(
        source_fingerprint=source.source_fingerprint,
        source_unit_key="chapter:0",
        span=SourceSpan(start, start + len(text)),
        entity_type=EntityType.CHARACTER,
        text=text,
    )


def test_source_adapter_binds_exact_v2_offsets():
    source = NormalizedSource.from_v2_payload(source_payload())
    assert source.source_fingerprint == "b" * 64
    assert source.sections[0].normalized_text == source.normalized_text
    assert source.section_for_offset(2).stable_key == "chapter:0"


def test_source_adapter_rejects_offset_text_mismatch():
    payload = source_payload()
    payload["sections"][0]["normalized_text"] = "different"
    with pytest.raises(ValueError, match="text/offset mismatch"):
        NormalizedSource.from_v2_payload(payload)


def test_source_span_rejects_invalid_bounds():
    with pytest.raises(ValueError):
        SourceSpan(-1, 2)
    with pytest.raises(ValueError):
        SourceSpan(3, 2)


def test_config_fingerprint_is_mapping_order_independent():
    assert config_fingerprint({"b": 2, "a": 1}) == config_fingerprint({"a": 1, "b": 2})


def test_artifact_fingerprint_changes_when_semantics_change():
    base = dict(
        source_fingerprint="source",
        stage_name="lexer",
        stage_version="1",
        config={"threshold": 0.5},
        upstream_fingerprints=("upstream",),
    )
    first = artifact_fingerprint(**base)
    second = artifact_fingerprint(**{**base, "config": {"threshold": 0.6}})
    third = artifact_fingerprint(**{**base, "stage_version": "2"})
    assert first != second
    assert first != third


def test_mentions_have_deterministic_source_bound_ids():
    source = NormalizedSource.from_v2_payload(source_payload())
    one = mention(source, "Rhys", 0)
    two = mention(source, "Rhys", 0)
    moved = mention(source, "Rhys", 14)
    assert one.mention_id == two.mention_id
    assert one.mention_id != moved.mention_id


def test_exact_surface_linker_groups_only_exact_names_and_keeps_pronoun_unresolved():
    source = NormalizedSource.from_v2_payload(source_payload())
    first = mention(source, "Rhys", 0)
    second = mention(source, "Rhys", 14)
    pronoun = mention(source, "She", 27)

    result = ExactSurfaceCharacterLinker().link(source=source, mentions=[pronoun, second, first])

    linked = [entity for entity in result.entities if entity.acceptance is AcceptanceState.CANDIDATE]
    unresolved = [entity for entity in result.entities if entity.acceptance is AcceptanceState.UNRESOLVED]
    assert len(linked) == 1
    assert set(linked[0].mention_ids) == {first.mention_id, second.mention_id}
    assert len(unresolved) == 1
    assert result.unresolved_mention_ids == (pronoun.mention_id,)


def test_identity_metric_contract_penalizes_cross_gold_merge():
    source = NormalizedSource.from_v2_payload(source_payload())
    one = mention(source, "Rhys", 0)
    two = mention(source, "Rhys", 14)
    other = mention(source, "She", 27)
    result = ExactSurfaceCharacterLinker().link(source=source, mentions=[one, two, other])

    # Force the unresolved third mention into the Rhys cluster to model a bad merge.
    linked = next(entity for entity in result.entities if entity.acceptance is AcceptanceState.CANDIDATE)
    bad = replace(linked, mention_ids=linked.mention_ids + (other.mention_id,))
    metrics = score_identity_clusters(
        gold_entity_by_mention={
            one.mention_id: "rhys",
            two.mention_id: "rhys",
            other.mention_id: "feyre",
        },
        predicted_entities=[bad],
    )
    assert metrics.mention_attachment_precision < 1.0
    assert metrics.incorrect_merge_rate > 0.0
