from __future__ import annotations

from packages.identity_runtime import review_identity_clusters


def test_identity_review_rejects_cross_character_and_generic_aliases():
    review = review_identity_clusters(
        raw_clusters=[
            {
                "cluster_id": 1,
                "display_name": "Locke",
                "aliases": ["the prince", "Madoc"],
                "proper_mentions": ["Locke", "Madoc"],
                "pronoun_mentions": ["he", "his"],
                "mention_count": 24,
            },
            {
                "cluster_id": 2,
                "display_name": "Prince Cardan",
                "aliases": ["Locke", "the prince", "Cardan"],
                "proper_mentions": ["Prince Cardan", "Locke", "Cardan"],
                "pronoun_mentions": ["he", "him"],
                "mention_count": 19,
            },
            {
                "cluster_id": 3,
                "display_name": "my sister",
                "aliases": [],
                "proper_mentions": [],
                "pronoun_mentions": ["she", "her"],
                "mention_count": 12,
            },
        ],
        chapters=[
            {
                "chapter_index": 1,
                "content": "Locke confronted Prince Cardan. Cardan mocked Jude. Her sister watched.",
            }
        ],
        scenes=[
            {
                "scene_id": "scene-001",
                "chapter_index": 1,
                "text": "Locke confronted Prince Cardan. Cardan mocked Jude. Her sister watched.",
            }
        ],
    )

    kept = [item for item in review.reviewed_clusters if item.keep_cluster]
    dropped = [item for item in review.reviewed_clusters if not item.keep_cluster]

    assert [item.cluster.display_name for item in kept] == ["Locke", "Prince Cardan"]
    assert [item.cluster.display_name for item in dropped] == ["my sister"]

    cardan = next(item for item in kept if item.cluster.display_name == "Prince Cardan")
    assert "Cardan" in cardan.accepted_aliases
    assert "Locke" in cardan.rejected_aliases
    assert "the prince" in cardan.rejected_aliases
    assert any(item.code == "cross_character_alias_rejected" for item in cardan.diagnostics)


def test_identity_review_keeps_grounded_named_aliases():
    review = review_identity_clusters(
        raw_clusters=[
            {
                "cluster_id": 1,
                "display_name": "Princess Rhyia",
                "aliases": ["Rhyia", "the princess"],
                "proper_mentions": ["Princess Rhyia", "Rhyia"],
                "pronoun_mentions": ["she", "her"],
                "mention_count": 8,
            }
        ],
        chapters=[{"chapter_index": 1, "content": "Princess Rhyia spoke. Rhyia smiled at the court."}],
        scenes=[{"scene_id": "scene-001", "chapter_index": 1, "text": "Princess Rhyia spoke. Rhyia smiled at the court."}],
    )

    kept = [item for item in review.reviewed_clusters if item.keep_cluster]
    assert len(kept) == 1
    assert kept[0].cluster.display_name == "Princess Rhyia"
    assert kept[0].accepted_aliases == ["Rhyia"]
    assert "the princess" in kept[0].rejected_aliases


def test_identity_review_rejects_long_non_name_alias_spans():
    review = review_identity_clusters(
        raw_clusters=[
            {
                "cluster_id": 1,
                "display_name": "Taryn",
                "aliases": [
                    "you ought to marry me even if neither of those things were true",
                    "a girl named Taryn",
                ],
                "proper_mentions": ["Taryn"],
                "pronoun_mentions": ["I", "me"],
                "mention_count": 15,
            }
        ],
        chapters=[{"chapter_index": 1, "content": "Taryn looked away."}],
        scenes=[{"scene_id": "scene-001", "chapter_index": 1, "text": "Taryn looked away."}],
    )

    kept = [item for item in review.reviewed_clusters if item.keep_cluster]
    assert len(kept) == 1
    assert kept[0].cluster.display_name == "Taryn"
    assert "you ought to marry me even if neither of those things were true" in kept[0].rejected_aliases
    assert "a girl named Taryn" in kept[0].rejected_aliases
    assert any(item.code == "malformed_alias_rejected" for item in kept[0].diagnostics)


def test_identity_review_rejects_generic_surface_aliases_and_pronoun_pollution():
    review = review_identity_clusters(
        raw_clusters=[
            {
                "cluster_id": 1,
                "display_name": "Jude",
                "aliases": ["Twin sister", "this Heather"],
                "proper_mentions": ["Jude", "Twin sister", "this Heather"],
                "pronoun_mentions": ["I", "You", "she", "her", "herself"],
                "mention_count": 21,
            },
            {
                "cluster_id": 2,
                "display_name": "Heather",
                "aliases": ["that Heather"],
                "proper_mentions": ["Heather", "that Heather"],
                "pronoun_mentions": ["her", "She", "himself", "themselves"],
                "mention_count": 9,
            },
        ],
        chapters=[{"chapter_index": 1, "content": "Jude argued with Heather. Heather looked away."}],
        scenes=[{"scene_id": "scene-001", "chapter_index": 1, "text": "Jude argued with Heather. Heather looked away."}],
    )

    jude = next(item for item in review.reviewed_clusters if item.cluster.display_name == "Jude")
    heather = next(item for item in review.reviewed_clusters if item.cluster.display_name == "Heather")

    assert "Twin sister" in jude.rejected_aliases
    assert "this Heather" in jude.rejected_aliases
    assert "that Heather" in heather.rejected_aliases
    assert jude.cluster.pronoun_mentions == []
    assert heather.cluster.pronoun_mentions == []
    assert any(item.code == "generic_role_alias_rejected" for item in jude.diagnostics)


def test_identity_review_drops_non_character_clusters():
    review = review_identity_clusters(
        raw_clusters=[
            {
                "cluster_id": 1,
                "display_name": "Wicked girl",
                "aliases": [],
                "proper_mentions": [],
                "pronoun_mentions": ["she"],
                "mention_count": 4,
            },
            {
                "cluster_id": 2,
                "display_name": "Some",
                "aliases": [],
                "proper_mentions": [],
                "pronoun_mentions": [],
                "mention_count": 3,
            },
            {
                "cluster_id": 3,
                "display_name": "the body",
                "aliases": [],
                "proper_mentions": [],
                "pronoun_mentions": [],
                "mention_count": 2,
            },
            {
                "cluster_id": 4,
                "display_name": "Prince Cardan",
                "aliases": ["Cardan"],
                "proper_mentions": ["Prince Cardan", "Cardan"],
                "pronoun_mentions": ["he"],
                "mention_count": 8,
            },
        ],
        chapters=[{"chapter_index": 1, "content": "Prince Cardan laughed. Cardan turned away."}],
        scenes=[{"scene_id": "scene-001", "chapter_index": 1, "text": "Prince Cardan laughed. Cardan turned away."}],
    )

    kept_names = [item.cluster.display_name for item in review.reviewed_clusters if item.keep_cluster]
    dropped_names = [item.cluster.display_name for item in review.reviewed_clusters if not item.keep_cluster]

    assert kept_names == ["Prince Cardan"]
    assert sorted(dropped_names) == ["Some", "Wicked girl", "the body"]
