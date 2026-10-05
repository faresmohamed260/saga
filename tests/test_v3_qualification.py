from pathlib import Path

import pytest

from packages.narrative_compiler.fingerprint import canonical_json
from packages.narrative_compiler.ir import EntityType, Mention, SourceSpan
from packages.narrative_compiler.qualification import digest_snapshot
from packages.narrative_compiler.stages import IdentityCandidate


def test_model_snapshot_digest_changes_when_model_bytes_change(tmp_path: Path):
    (tmp_path / "config.json").write_text("one", encoding="utf-8")
    nested = tmp_path / "weights"
    nested.mkdir()
    (nested / "model.bin").write_bytes(b"abc")
    one = digest_snapshot(model_id="fixture/model", revision="abc123", snapshot_path=tmp_path)
    two = digest_snapshot(model_id="fixture/model", revision="abc123", snapshot_path=tmp_path)
    assert one.aggregate_sha256 == two.aggregate_sha256
    assert one.file_count == 2
    assert one.total_bytes == 6

    (nested / "model.bin").write_bytes(b"abcd")
    changed = digest_snapshot(model_id="fixture/model", revision="abc123", snapshot_path=tmp_path)
    assert changed.aggregate_sha256 != one.aggregate_sha256


def test_ir_attribute_mapping_is_recursively_immutable_and_fingerprintable():
    mutable = {"kind": "proper"}
    mention = Mention.create(
        source_fingerprint="source",
        source_unit_key="unit",
        span=SourceSpan(0, 4),
        entity_type=EntityType.CHARACTER,
        text="Rhys",
        attributes=mutable,
    )
    mutable["kind"] = "changed"
    assert mention.attributes["kind"] == "proper"
    assert '"kind":"proper"' in canonical_json(mention)
    with pytest.raises(TypeError):
        mention.attributes["kind"] = "changed"


def test_identity_candidate_features_are_immutable():
    raw = {"lexical": 1.0}
    candidate = IdentityCandidate("mention", "entity", raw)
    raw["lexical"] = 0.0
    assert candidate.features["lexical"] == 1.0
    with pytest.raises(TypeError):
        candidate.features["lexical"] = 0.0
