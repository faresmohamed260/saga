from packages.narrative_compiler.litbank import convert_litbank_tsv_document, oracle_person_mentions


def test_litbank_tsv_adapter_preserves_codepoint_spans_and_clusters():
    text = "Alice met Bob\nShe smiled"
    annotation = "\n".join(
        [
            "MENTION\tm1\t0\t0\t0\t0\tAlice\tPER\tPROP",
            "MENTION\tm2\t0\t2\t0\t2\tBob\tPER\tPROP",
            "MENTION\tm3\t1\t0\t1\t0\tShe\tPER\tPRON",
            "COREF\tm1\tc1",
            "COREF\tm3\tc1",
            "COREF\tm2\tc2",
        ]
    )
    document = convert_litbank_tsv_document(document_id="fixture", text=text, annotation=annotation)
    assert [item.surface_text for item in document.gold.mentions] == ["Alice", "Bob", "She"]
    assert document.gold.mentions[0].gold_character_id == "c1"
    assert document.gold.mentions[2].mention_kind == "pronoun"
    assert document.source.normalized_text == text
    oracle = oracle_person_mentions(document)
    assert [item.text for item in oracle] == ["Alice", "Bob", "She"]
    assert all(item.evidence.source_fingerprint == document.source.source_fingerprint for item in oracle)
