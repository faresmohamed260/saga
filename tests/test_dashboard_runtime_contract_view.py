from pathlib import Path

from dashboard_runtime.app import EncodeRequest, build_encode_command, contract_view, derive_scene_quality


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
    assert command[:3] == ["python", "-u", "saga_tools.py"] or command[1:3] == ["-u", "saga_tools.py"]
    assert "--export-contracts" not in command


def test_build_encode_command_supports_export_contracts():
    request = EncodeRequest(
        books=["C:\\books\\sample.epub"],
        export_contracts=True,
    )

    command = build_encode_command(request)

    assert "--export-contracts" in command


def test_build_character_render_command_is_unbuffered():
    from dashboard_runtime.app import CharacterRenderRequest, build_character_render_command

    request = CharacterRenderRequest(contract_path="analysis_outputs\\sample.contract.json", overwrite=True)

    command = build_character_render_command(request)

    assert command[1:3] == ["-u", "saga_tools.py"]
    assert "--overwrite" in command


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


def test_derive_scene_quality_falls_back_to_scene_status():
    rows = [
        {"final_status": "success", "scene_summary": "A"},
        {"final_status": "failed", "error_category": "provider_exhausted"},
        {"scene_summary": "C"},
    ]

    payload = derive_scene_quality(rows, {})

    assert payload == {
        "successful_scenes": 2,
        "failed_scenes": 1,
        "total_scenes": 3,
    }
