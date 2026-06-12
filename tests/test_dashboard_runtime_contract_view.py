from pathlib import Path

from dashboard_runtime.app import EncodeRequest, build_encode_command, contract_view


def test_build_encode_command_supports_max_chapters():
    request = EncodeRequest(
        books=["C:\\books\\sample.epub"],
        max_chapters=5,
        skip_ingest=True,
        no_progress=True,
    )

    command = build_encode_command(request)

    assert "--max-chapters" in command
    assert command[command.index("--max-chapters") + 1] == "5"


def test_contract_view_exposes_scene_world_state(tmp_path: Path):
    contract_path = tmp_path / "sample.contract.json"
    contract_path.write_text(
        """
{
  "outputs": {
    "resolved_scene_analyses": [
      {
        "book_index": 1,
        "chapter_index": 1,
        "scene_index": 1,
        "scene_summary": "Feyre enters the forest.",
        "text": "Feyre enters the forest.",
        "location": {"name": "forest", "entity_type": "location", "description": "dark woods"},
        "visual_analysis": {"characters": [{"entity_name": "Feyre"}], "objects": [], "creatures": [], "locations": [], "scene_compositions": []},
        "entity_world_state": {
          "entities": [
            {
              "entity_name": "Feyre",
              "entity_type": "character",
              "baseline_description": "a gaunt huntress",
              "typed_attributes": {"appearance": ["gaunt"], "outfit": ["worn cloak"]}
            }
          ]
        },
        "state_changes": [],
        "relationship_changes": []
      }
    ],
    "event_ledger": [],
    "entity_registry": [],
    "timeline": [],
    "character_profiles": [],
    "stable_character_states": []
  }
}
        """.strip(),
        encoding="utf-8",
    )

    payload = contract_view(contract_path, limit=50)

    assert payload["counts"]["scene_world_state"] == 1
    assert payload["outputs"]["scene_world_state"][0]["entity_world_state"]["entities"][0]["entity_name"] == "Feyre"
