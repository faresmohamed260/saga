import pytest

from scripts.compare_v2_v3_identity_reports import _assert_comparable


BASE = {
    "repository": "dbamman/litbank",
    "commit": "3e50db0ffc033d7ccbb94f4d88f6b99210328ed8",
    "annotationLayer": "coref/tsv",
}


def test_comparator_accepts_frozen_booknlp_document_count_shape():
    v2 = {
        "dataset": {
            **BASE,
            "attemptedDocumentCount": 100,
            "completedDocumentCount": 100,
            "failedDocumentCount": 0,
        }
    }
    v3 = {"dataset": {**BASE, "documentCount": 100}}
    _assert_comparable(v2, v3)


def test_comparator_rejects_partial_v2_provider_run():
    v2 = {
        "dataset": {
            **BASE,
            "attemptedDocumentCount": 100,
            "completedDocumentCount": 99,
            "failedDocumentCount": 1,
        }
    }
    v3 = {"dataset": {**BASE, "documentCount": 99}}
    with pytest.raises(ValueError, match="failed documents"):
        _assert_comparable(v2, v3)


def test_comparator_rejects_different_corpus_size():
    v2 = {"dataset": {**BASE, "documentCount": 100}}
    v3 = {"dataset": {**BASE, "documentCount": 20}}
    with pytest.raises(ValueError, match="document count differs"):
        _assert_comparable(v2, v3)
