import json
import uuid
from pathlib import Path

from integrations.comfyui.client import ModalComfyUIClient
from integrations.comfyui.pool_manager import ModalComfyUIPoolManager
from integrations.comfyui.runtime_helpers import load_workflow_json
from integrations.comfyui.runtime_helpers import warmup_prompt_identity
from saga.agents.visual_prompt_schema import compile_location_negative_prompt
from saga.services.comfyui_character_sheet_service import ComfyUICharacterSheetService
from saga.services.comfyui_character_sheet_service import DEFAULT_NEGATIVE_PROMPT
from saga.services.entity_visual_prompt_service import EntityVisualPromptService
from saga.storage.models import Book, CharacterVisualBaseline, Entity, Series, VisualPrompt
from saga.storage.persistence import SagaSQLiteStore


def _row(name, *, confidence="high", species="human", role="wizard", prompt="prompt", source="") -> dict:
    return {
        "entity_name": name,
        "positive_prompt": prompt,
        "confidence": confidence,
        "details": {
            "persistent_visual_profile": {
                "species_or_race": species,
                "role_or_archetype": role,
                "model_safe_identity": f"{species} {role}".strip(),
                "hair_description": "dark hair",
                "eye_description": "green eyes",
            }
        },
        "source_evidence": source,
    }


def test_collect_character_prompts_merges_alias_duplicates_and_skips_creatures(tmp_path):
    contract_path = tmp_path / "hp.contract.json"
    contract_payload = {
        "outputs": {
            "identity_result": {
                "alias_map": {
                    "Harry": ["Harry", "Harry Potter", "Harry wizard"],
                    "Hermione": ["Hermione", "Hermione Granger"],
                    "Professor McGonagall": ["Professor McGonagall", "Minerva McGonagall"],
                    "Dudley": ["Dudley", "Dudley Dursley"],
                    "Hagrid": ["Hagrid", "Rubeus Hagrid"],
                }
            },
            "entity_registry": [
                {"name": "Harry", "entity_type": "character", "descriptions": [{"description": "boy wizard", "description_type": "stable_trait"}]},
                {"name": "Hermione", "entity_type": "character", "descriptions": [{"description": "student witch", "description_type": "stable_trait"}]},
                {"name": "Professor McGonagall", "entity_type": "character", "descriptions": [{"description": "professor in emerald robes", "description_type": "stable_trait"}]},
                {"name": "Hagrid", "entity_type": "character", "descriptions": [{"description": "half-giant gamekeeper", "description_type": "stable_trait"}]},
                {"name": "Fang", "entity_type": "character", "descriptions": [{"description": "enormous black boarhound", "description_type": "stable_trait"}]},
                {"name": "Firenze", "entity_type": "character", "descriptions": [{"description": "centaur with palomino horse body", "description_type": "stable_trait"}]},
                {"name": "Giant", "entity_type": "object", "descriptions": [{"description": "giant of a man in a black overcoat", "description_type": "stable_trait"}]},
            ],
            "visual_prompt_sets": {
                "initial_characters": [
                    _row("Harry", confidence="high", species="human", role="boy wizard", prompt="strong harry prompt"),
                    _row("Harry Potter", confidence="medium", species="human", role="young wizard", prompt="weaker potter prompt"),
                    _row("Hermione", confidence="low", species="human", role="student", prompt="short hermione prompt"),
                    _row("Hermione Granger", confidence="high", species="human", role="student witch", prompt="best hermione prompt"),
                    _row("Professor McGonagall", confidence="high", species="human", role="wizard", prompt="mcgonagall prompt"),
                    _row("Minerva McGonagall", confidence="low", species="human", role="wizard", prompt="minerva prompt"),
                    _row("Hagrid", confidence="high", species="human", role="half-giant gamekeeper", prompt="hagrid prompt"),
                    _row("Rubeus Hagrid", confidence="high", species="human", role="gamekeeper", prompt="rubeus hagrid prompt"),
                    _row("Dudley", confidence="high", species="human", role="older brother", prompt="dudley prompt"),
                    _row("Dudley Dursley", confidence="low", species="human", role="child", prompt="dudley dursley prompt"),
                    _row("Fang", confidence="high", species="large dog", role="", prompt="fang prompt"),
                    _row("Firenze", confidence="high", species="centaur", role="centaur guide", prompt="firenze prompt"),
                    _row("Giant", confidence="high", species="human (giant stature)", role="mysterious benefactor", prompt="giant prompt"),
                ]
            },
        }
    }
    contract_path.write_text(json.dumps(contract_payload), encoding="utf-8")

    rows = ComfyUICharacterSheetService().collect_character_prompts(contract_path)
    names = [row["entity_name"] for row in rows]

    assert "Harry" in names
    assert "Hermione" in names
    assert "Hagrid" in names
    assert "Dudley" not in names
    assert "Fang" not in names
    assert "Firenze" not in names
    assert "Giant" not in names


def test_collect_entity_visual_prompts_uses_entity_registry_as_source_of_truth(tmp_path):
    contract_path = tmp_path / "saga.domain.entities.contract.json"
    contract_payload = {
        "outputs": {
            "identity_result": {"alias_map": {}},
            "entity_registry": [
                {
                    "name": "Harry Potter",
                    "entity_type": "character",
                    "first_seen": {"book_index": 1, "chapter_index": 1, "scene_index": 1},
                    "first_appearance_profile": {
                        "baseline_description": "thin boy with messy black hair and round glasses",
                        "typed_attributes": {
                            "appearance": ["thin build", "messy black hair", "round glasses"],
                            "outfit": ["school uniform"],
                            "body_language": ["neutral expression"],
                            "possessions": ["wand"],
                            "titles_or_roles": ["student wizard"],
                            "affiliations": ["Hogwarts"],
                        },
                    },
                    "descriptions": [{"description": "thin boy with messy black hair and round glasses", "description_type": "stable_trait"}],
                },
                {
                    "name": "Fang",
                    "entity_type": "character",
                    "first_seen": {"book_index": 1, "chapter_index": 6, "scene_index": 1},
                    "descriptions": [{"description": "enormous black boarhound with heavy paws", "description_type": "stable_trait"}],
                    "typed_attributes": {"appearance": ["enormous black boarhound"]},
                },
                {
                    "name": "Hogwarts",
                    "entity_type": "location",
                    "first_seen": {"book_index": 1, "chapter_index": 7, "scene_index": 1},
                    "descriptions": [{"description": "vast stone castle lit by torches", "description_type": "stable_trait"}],
                },
                {
                    "name": "Sorting Hat",
                    "entity_type": "object",
                    "first_seen": {"book_index": 1, "chapter_index": 7, "scene_index": 1},
                    "descriptions": [{"description": "old pointed hat with a wide tear like a mouth", "description_type": "stable_trait"}],
                },
            ],
            "visual_prompt_sets": {
                "initial_characters": [
                    _row("Harry", confidence="high", species="human", role="student wizard", prompt="harry sheet prompt", source="harry intro"),
                    _row("Fang", confidence="high", species="large dog", role="", prompt="fang wrong character prompt", source="fang intro"),
                ],
                "objects_creatures": [
                    {
                        "entity_name": "Sorting Hat",
                        "entity_type": "object",
                        "positive_prompt": "sorting hat object prompt",
                        "confidence": "high",
                        "source_evidence": "old pointed hat",
                        "details": {},
                    }
                ],
                "locations": [
                    {
                        "entity_name": "Hogwarts",
                        "entity_type": "location",
                        "positive_prompt": "hogwarts location prompt",
                        "confidence": "high",
                        "source_evidence": "stone castle",
                        "details": {},
                    }
                ],
            },
        }
    }
    contract_path.write_text(json.dumps(contract_payload), encoding="utf-8")

    rows = ComfyUICharacterSheetService().collect_entity_visual_prompts(contract_path)

    assert len(rows) == 4
    by_name = {row["entity_name"]: row for row in rows}
    assert by_name["Harry Potter"]["entity_type"] == "character"
    assert by_name["Harry Potter"]["workflow_mode"] == "character_sheet"
    assert "three-view layout" in by_name["Harry Potter"]["positive_prompt"].lower()
    assert by_name["Fang"]["entity_type"] == "creature"
    assert by_name["Fang"]["workflow_mode"] == "entity_generation"
    assert "creature reference image" in by_name["Fang"]["positive_prompt"].lower()
    assert by_name["Hogwarts"]["entity_type"] == "location"
    assert by_name["Hogwarts"]["workflow_mode"] == "entity_generation"
    assert "hogwarts location prompt" in by_name["Hogwarts"]["positive_prompt"].lower()
    assert by_name["Sorting Hat"]["entity_type"] == "object"
    assert by_name["Sorting Hat"]["workflow_mode"] == "entity_generation"


def test_build_render_manifest_emits_all_entity_types_with_per_item_workflows(tmp_path):
    contract_path = tmp_path / "manifest.contract.json"
    contract_payload = {
        "outputs": {
            "identity_result": {"alias_map": {}},
            "entity_registry": [
                {
                    "name": "Harry Potter",
                    "entity_type": "character",
                    "first_seen": {"book_index": 1, "chapter_index": 1, "scene_index": 1},
                    "descriptions": [{"description": "boy with glasses", "description_type": "stable_trait"}],
                    "typed_attributes": {"titles_or_roles": ["student wizard"]},
                },
                {
                    "name": "Hedwig",
                    "entity_type": "creature",
                    "first_seen": {"book_index": 1, "chapter_index": 5, "scene_index": 1},
                    "descriptions": [{"description": "snowy owl with bright amber eyes", "description_type": "stable_trait"}],
                },
                {
                    "name": "Hogwarts",
                    "entity_type": "location",
                    "first_seen": {"book_index": 1, "chapter_index": 7, "scene_index": 1},
                    "descriptions": [{"description": "castle with high towers and torchlit halls", "description_type": "stable_trait"}],
                },
                {
                    "name": "Sorting Hat",
                    "entity_type": "object",
                    "first_seen": {"book_index": 1, "chapter_index": 7, "scene_index": 1},
                    "descriptions": [{"description": "old pointed hat with a mouthlike tear", "description_type": "stable_trait"}],
                },
            ],
            "visual_prompt_sets": {},
        }
    }
    contract_path.write_text(json.dumps(contract_payload), encoding="utf-8")

    manifest = ComfyUICharacterSheetService().build_render_manifest(contract_path)
    renders = manifest["renders"]
    assert len(renders) == 4
    by_name = {row["entity_name"]: row for row in renders}
    assert by_name["Harry Potter"]["workflow_mode"] == "character_sheet"
    assert by_name["Harry Potter"]["width"] == 1504
    assert by_name["Harry Potter"]["height"] == 1024
    assert by_name["Hedwig"]["workflow_mode"] == "entity_generation"
    assert by_name["Hedwig"]["width"] == 1504
    assert by_name["Hedwig"]["height"] == 1024
    assert by_name["Hogwarts"]["workflow_mode"] == "entity_generation"
    assert by_name["Hogwarts"]["width"] == 1344
    assert by_name["Hogwarts"]["height"] == 768
    assert by_name["Harry Potter"]["negative_prompt"] == DEFAULT_NEGATIVE_PROMPT
    assert by_name["Hogwarts"]["negative_prompt"] == compile_location_negative_prompt()
    assert by_name["Hedwig"]["negative_prompt"]
    assert by_name["Sorting Hat"]["negative_prompt"]


def test_db_render_manifest_can_target_one_exact_entity_id(tmp_path):
    store = SagaSQLiteStore(tmp_path / "saga.sqlite")
    with store.session_factory() as session:
        series = Series(series_id="hp", title="Harry Potter", metadata_json={})
        session.add(series)
        session.flush()
        book = Book(series_fk=series.id, series_id="hp", book_index=1, title="HP1", run_status="ready")
        session.add(book)
        session.flush()
        harry = Entity(
            book_id=book.id,
            canonical_name="Harry Potter",
            entity_type="character",
            mention_count=10,
            first_seen_book_index=1,
            first_seen_chapter_index=1,
            first_seen_scene_index=1,
            first_appearance_profile={"persistent_traits": {"default_clothing_style": "school robes"}},
        )
        hermione = Entity(
            book_id=book.id,
            canonical_name="Hermione Granger",
            entity_type="character",
            mention_count=8,
            first_seen_book_index=1,
            first_seen_chapter_index=6,
            first_seen_scene_index=1,
            first_appearance_profile={"persistent_traits": {"default_clothing_style": "school robes"}},
        )
        session.add_all([harry, hermione])
        session.flush()
        session.add(
            CharacterVisualBaseline(
                book_id=book.id,
                entity_id=harry.id,
                gender_presentation="male",
                species_or_race="human",
                apparent_age_group="young boy",
                hair_color="black",
                hair_length_or_style="messy hair",
                eye_color="green eyes",
                default_clothing_style="black school robes",
                evidence_excerpt="Harry has messy black hair and green eyes.",
            )
        )
        session.add(
            CharacterVisualBaseline(
                book_id=book.id,
                entity_id=hermione.id,
                gender_presentation="female",
                species_or_race="human",
                apparent_age_group="young girl",
                hair_color="brown",
                hair_length_or_style="bushy hair",
                eye_color="brown eyes",
                default_clothing_style="black school robes",
                evidence_excerpt="Hermione has bushy brown hair.",
            )
        )
        session.add(
            VisualPrompt(
                book_id=book.id,
                entity_id=harry.id,
                entity_name="Harry Potter",
                entity_type="character",
                prompt_type="baseline_character_sheet",
                positive_prompt="wrong harry prompt",
                negative_prompt="",
                confidence="high",
            )
        )
        hermione_prompt = VisualPrompt(
            book_id=book.id,
            entity_id=hermione.id,
            entity_name="Hermione Granger",
            entity_type="character",
            prompt_type="baseline_character_sheet",
            positive_prompt="selected hermione prompt",
            negative_prompt="bad anatomy",
            confidence="high",
        )
        session.add(hermione_prompt)
        session.flush()
        target_id = hermione.id
        target_prompt_id = hermione_prompt.id
        book_ref = f"db://book/{book.id}"
        session.commit()

    service = ComfyUICharacterSheetService()
    service.sqlite_store = store
    service.entity_visual_prompt_service = EntityVisualPromptService(store)

    manifest = service.build_render_manifest(book_ref, entity_ids={target_id}, prompt_ids={target_prompt_id})

    assert len(manifest["renders"]) == 1
    assert manifest["renders"][0]["entity_id"] == target_id
    assert manifest["renders"][0]["prompt_id"] == target_prompt_id
    assert manifest["renders"][0]["entity_name"] == "Hermione Granger"
    assert manifest["renders"][0]["positive_prompt"] == "selected hermione prompt"


def test_render_single_payload_uses_comfy_pool_for_character_sheet(tmp_path):
    class _Pool:
        def __init__(self):
            self.calls = []

        def render(self, **kwargs):
            self.calls.append(kwargs)
            return {"image_bytes": b"png-bytes", "api_url": "https://example.modal.run"}

    pool = _Pool()

    output_path = tmp_path / "character.png"
    row = {
        "positive_prompt": "hero turnaround",
        "negative_prompt": "bad anatomy",
        "workflow_mode": "character_sheet",
        "output_path": str(output_path),
        "seed": 7,
        "steps": 11,
        "cfg": 1.5,
        "width": 1504,
        "height": 1024,
    }

    result = ComfyUICharacterSheetService(comfy_pool=pool).render_single_payload(row)

    assert result["status"] == "rendered"
    assert output_path.read_bytes() == b"png-bytes"
    assert pool.calls[0]["workflow_mode"] == "character_sheet"
    assert pool.calls[0]["prompt"] == "hero turnaround"
    assert pool.calls[0]["width"] == 1504


def test_active_modal_api_url_comes_from_pool():
    class _Pool:
        def ensure_live(self):
            return {"api_url": "https://example.modal.run/api", "token_name": "member-01"}

    api_url = ComfyUICharacterSheetService(comfy_pool=_Pool())._active_modal_api_url()

    assert api_url == "https://example.modal.run/api"


class _FakeResponse:
    def __init__(self, *, content=b"png-bytes", headers=None):
        self.content = content
        self.headers = headers or {"Content-Type": "image/png"}
        self.status_code = 200
        self.text = content.decode("utf-8", errors="replace")
        self.reason = "OK"

    def raise_for_status(self):
        return None


def test_modal_comfyui_client_renders_png(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr("integrations.comfyui.client.requests.get", fake_get)

    client = ModalComfyUIClient("https://example.modal.run/api", timeout_seconds=123)
    payload = client.render(prompt="hero turnaround", workflow_mode="character_sheet", width=1504, height=1024)

    assert payload["image_bytes"] == b"png-bytes"
    assert captured["url"] == "https://example.modal.run/api"
    assert captured["params"]["workflow_mode"] == "character_sheet"
    assert captured["timeout"] == 123


def test_modal_comfyui_pool_manager_uses_workspace_urls(monkeypatch, tmp_path: Path):
    state_path = tmp_path / "pool_state.json"
    from integrations.comfyui.token_pool import ModalToken

    tokens = [ModalToken(name="member-01", token_id="ak-test", token_secret="as-test")]

    monkeypatch.setattr(
        "integrations.comfyui.pool_manager.ensure_urls",
        lambda token, app_name, hf_token="": type(
            "Urls",
            (),
            {
                "api_url": "https://example.modal.run/api",
                "ui_url": "https://example.modal.run/ui",
                "health_url": "https://example.modal.run/health",
            },
        )(),
    )
    monkeypatch.setattr(
        "integrations.comfyui.pool_manager.requests.get",
        lambda url, timeout: type(
            "Response",
            (),
            {
                "raise_for_status": staticmethod(lambda: None),
                "json": staticmethod(lambda: {"ready": True, "service": "comfyui"}),
            },
        )(),
    )

    manager = ModalComfyUIPoolManager(tokens=tokens, state_path=state_path)
    live = manager.ensure_live()

    assert live["api_url"] == "https://example.modal.run/api"
    assert live["ui_url"] == "https://example.modal.run/ui"
    assert live["health_url"] == "https://example.modal.run/health"


def test_modal_comfyui_pool_manager_honors_account_app_override_and_hf_token(monkeypatch, tmp_path: Path):
    state_path = tmp_path / "pool_state.json"
    from integrations.comfyui.token_pool import ModalToken

    tokens = [
        ModalToken(
            name="member-10",
            token_id="ak-test",
            token_secret="as-test",
            app_name_override="saga-image-runtime-member-10",
        )
    ]
    captured = {}

    def fake_ensure_urls(token, app_name, *, hf_token=""):
        captured["token_name"] = token.name
        captured["app_name"] = app_name
        captured["hf_token"] = hf_token
        return type(
            "Urls",
            (),
            {
                "api_url": "https://example.modal.run/api",
                "ui_url": "https://example.modal.run/ui",
                "health_url": "https://example.modal.run/health",
            },
        )()

    monkeypatch.setattr("integrations.comfyui.pool_manager.ensure_urls", fake_ensure_urls)
    monkeypatch.setattr(
        "integrations.comfyui.pool_manager.requests.get",
        lambda url, timeout: type(
            "Response",
            (),
            {
                "raise_for_status": staticmethod(lambda: None),
                "json": staticmethod(lambda: {"ready": True, "service": "comfyui"}),
            },
        )(),
    )

    manager = ModalComfyUIPoolManager(
        tokens=tokens,
        state_path=state_path,
        app_name="saga-image-runtime",
        hf_token="hf_test_override",
    )
    live = manager.ensure_live()

    assert live["token_name"] == "member-10"
    assert captured == {
        "token_name": "member-10",
        "app_name": "saga-image-runtime-member-10",
        "hf_token": "hf_test_override",
    }


def test_modal_comfyui_pool_manager_reuses_persisted_warm_urls(monkeypatch, tmp_path: Path):
    state_path = tmp_path / "pool_state.json"
    from integrations.comfyui.token_pool import ModalToken, mark_render_success

    tokens = [ModalToken(name="member-01", token_id="ak-test", token_secret="as-test")]
    mark_render_success(
        "member-01",
        state_path=state_path,
        api_url="https://example.modal.run/api",
        ui_url="https://example.modal.run/ui",
        health_url="https://example.modal.run/health",
        live_payload={"ready": True, "service": "comfyui"},
    )

    def fail_ensure_urls(token, app_name):
        raise AssertionError("ensure_urls should not be called for persisted warm endpoint")

    monkeypatch.setattr("integrations.comfyui.pool_manager.ensure_urls", fail_ensure_urls)
    monkeypatch.setattr(
        "integrations.comfyui.pool_manager.requests.get",
        lambda url, timeout: type(
            "Response",
            (),
            {
                "raise_for_status": staticmethod(lambda: None),
                "json": staticmethod(lambda: {"ready": True, "service": "comfyui"}),
            },
        )(),
    )

    manager = ModalComfyUIPoolManager(tokens=tokens, state_path=state_path)
    live = manager.ensure_live()

    assert live["token_name"] == "member-01"
    assert live["api_url"] == "https://example.modal.run/api"
    assert live["ui_url"] == "https://example.modal.run/ui"
    assert live["health_url"] == "https://example.modal.run/health"


def test_modal_comfyui_pool_manager_render_uses_persisted_warm_endpoint_without_preflight(monkeypatch, tmp_path: Path):
    state_path = tmp_path / "pool_state.json"
    from integrations.comfyui.token_pool import ModalToken, mark_render_success

    tokens = [ModalToken(name="member-01", token_id="ak-test", token_secret="as-test")]
    mark_render_success(
        "member-01",
        state_path=state_path,
        api_url="https://example.modal.run/api",
        ui_url="https://example.modal.run/ui",
        health_url="https://example.modal.run/health",
        live_payload={"ready": True, "service": "comfyui"},
    )

    def fail_ensure_urls(token, app_name):
        raise AssertionError("ensure_urls should not be called for persisted warm render")

    monkeypatch.setattr("integrations.comfyui.pool_manager.ensure_urls", fail_ensure_urls)

    def fail_health(url, timeout):
        raise AssertionError("health preflight should not be called for persisted warm render")

    monkeypatch.setattr("integrations.comfyui.pool_manager.requests.get", fail_health)

    class _Client:
        def __init__(self, api_url, timeout_seconds):
            self.api_url = api_url

        def render(self, **kwargs):
            return {"image_bytes": b"png-bytes", "media_type": "image/png", "api_url": self.api_url}

    monkeypatch.setattr("integrations.comfyui.pool_manager.ModalComfyUIClient", _Client)

    manager = ModalComfyUIPoolManager(tokens=tokens, state_path=state_path)
    payload = manager.render(prompt="hero turnaround")

    assert payload["token_name"] == "member-01"
    assert payload["api_url"] == "https://example.modal.run/api"
    assert payload["image_bytes"] == b"png-bytes"


def test_modal_comfyui_pool_manager_exhausts_pool_without_recursion(monkeypatch, tmp_path: Path):
    state_path = tmp_path / "pool_state.json"
    from integrations.comfyui.token_pool import ModalToken

    tokens = [
        ModalToken(name="member-01", token_id="ak-test-1", token_secret="as-test-1"),
        ModalToken(name="member-02", token_id="ak-test-2", token_secret="as-test-2"),
    ]

    monkeypatch.setattr(
        "integrations.comfyui.pool_manager.ensure_urls",
        lambda token, app_name, hf_token="": type(
            "Urls",
            (),
            {
                "api_url": f"https://{token.name}.modal.run/api",
                "ui_url": f"https://{token.name}.modal.run/ui",
                "health_url": f"https://{token.name}.modal.run/health",
            },
        )(),
    )
    monkeypatch.setattr(
        "integrations.comfyui.pool_manager.requests.get",
        lambda url, timeout: type(
            "Response",
            (),
            {
                "raise_for_status": staticmethod(lambda: None),
                "json": staticmethod(lambda: {"ready": True}),
            },
        )(),
    )

    calls = []

    class _FailingClient:
        def __init__(self, api_url, timeout_seconds):
            self.api_url = api_url

        def render(self, **kwargs):
            calls.append(self.api_url)
            raise requests.RequestException("render failed")

    import requests

    monkeypatch.setattr("integrations.comfyui.pool_manager.ModalComfyUIClient", _FailingClient)

    manager = ModalComfyUIPoolManager(tokens=tokens, state_path=state_path)

    try:
        manager.render(prompt="hero turnaround")
        assert False, "Expected ModalComfyUIRotationError"
    except Exception as exc:
        assert "pool exhausted" in str(exc).lower()

    assert calls == [
        "https://member-01.modal.run/api",
        "https://member-02.modal.run/api",
    ]


def test_runtime_helper_load_workflow_accepts_utf8_bom(tmp_path: Path):
    workflow_path = tmp_path / "entity_generation_workflow.json"
    workflow_path.write_text('{"ok": true}', encoding="utf-8-sig")

    payload = load_workflow_json(str(workflow_path))

    assert payload == {"ok": True}


def test_runtime_helper_warmup_prompt_identity_uses_canonical_uuid_prompt_ids():
    entity_uuid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    character_uuid = uuid.UUID("22222222-2222-2222-2222-222222222222")

    captured = [
        warmup_prompt_identity("entity", entity_uuid),
        warmup_prompt_identity("character", character_uuid),
    ]

    assert captured == [
        (str(entity_uuid), "warmup-entity-11111111"),
        (str(character_uuid), "warmup-character-22222222"),
    ]
    for prompt_id, _ in captured:
        assert str(uuid.UUID(prompt_id)) == prompt_id
