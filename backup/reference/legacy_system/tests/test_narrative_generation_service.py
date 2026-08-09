from saga.services.narrative_generation_service import NarrativeGenerationService

from tests.test_narrative_context_service import _sample_contract
from saga.retrieval.narrative_context_service import NarrativeContextService


class _StubLLMClient:
    def __init__(self):
        self.json_calls = 0
        self.prompts = []
        self.text_prompts = []

    def generate_json(self, prompt: str, strict: bool = False, validator=None):
        self.json_calls += 1
        self.prompts.append(prompt)
        payload = _blueprint()
        if validator and not validator(payload):
            return {"error": "validation_failed", "raw_output": payload}
        return payload

    def generate_text(self, prompt: str, **kwargs):
        self.text_prompts.append(prompt)
        return "Elain Archeron stood in the garden and listened to the night breathing through the roses. " * 12


def _blueprint(**overrides):
    total_chapters = overrides.get("total_chapters", 25)
    if total_chapters <= 1:
        acts = [
            {
                "label": "Part One",
                "chapter_range": "1-1",
                "narrative_goal": "Set up and resolve the branch.",
                "ends_with": "The ending lands.",
                "dominant_arcs": [],
            }
        ]
    elif total_chapters == 2:
        acts = [
            {
                "label": "Part One",
                "chapter_range": "1-1",
                "narrative_goal": "Set up.",
                "ends_with": "The first turn lands.",
                "dominant_arcs": [],
            },
            {
                "label": "Part Two",
                "chapter_range": "2-2",
                "narrative_goal": "Resolve.",
                "ends_with": "The final consequence settles.",
                "dominant_arcs": [],
            },
        ]
    else:
        first_end = max(1, total_chapters // 3)
        second_end = max(first_end + 1, (2 * total_chapters) // 3)
        second_end = min(second_end, total_chapters - 1)
        acts = [
            {
                "label": "Part One",
                "chapter_range": f"1-{first_end}",
                "narrative_goal": "Set up the conflict.",
                "ends_with": "The first major turn lands.",
                "dominant_arcs": [],
            },
            {
                "label": "Part Two",
                "chapter_range": f"{first_end + 1}-{second_end}",
                "narrative_goal": "Escalate the pressure.",
                "ends_with": "The midpoint breaks the old plan.",
                "dominant_arcs": [],
            },
            {
                "label": "Part Three",
                "chapter_range": f"{second_end + 1}-{total_chapters}",
                "narrative_goal": "Resolve the branch.",
                "ends_with": "The final consequence settles.",
                "dominant_arcs": [],
            },
        ]
    payload = {
        "title": "Fresh Blueprint",
        "premise": "A sequel premise.",
        "structure_type": "linear",
        "canon_placement": "post_canon",
        "continuity_anchor": "",
        "divergence_anchor": "",
        "canon_elements_preserved": [],
        "new_plot_thread": "",
        "relationship_targets": [],
        "total_chapters": total_chapters,
        "central_conflict": "Conflict",
        "primary_arcs": [],
        "acts": acts,
        "world_threads_activated": [],
        "tone": "dramatic",
    }
    payload.update(overrides)
    return payload


def test_narrative_generation_service_compile_context_shapes_story_bible():
    retrieval = NarrativeContextService().build_from_contract(_sample_contract())
    service = NarrativeGenerationService(llm_client=_StubLLMClient())

    compiled = service.compile_context(retrieval, "Focus on Harry and Hermione growing closer.")

    assert compiled["book_title"] == "Harry Potter and the Order of the Phoenix"
    assert compiled["user_prompt"] == "Focus on Harry and Hermione growing closer."
    assert compiled["story_ending"]["critical_events"]
    assert any(item["name"] == "Harry Potter" for item in compiled["characters"])
    assert any("Harry Potter" in item["between"] for item in compiled["relationships"])
    assert compiled["unresolved_threads"]
    assert compiled["causal_chains"]


def test_narrative_generation_service_prefers_exported_blueprint_when_present():
    contract = _sample_contract()
    exported = _blueprint(
        title="Cached Blueprint",
        premise="Cached premise.",
        total_chapters=25,
        central_conflict="Cached conflict",
        tone="tense",
    )
    contract["outputs"]["sequel_artifacts"] = {
        "context": NarrativeContextService().build_from_contract(contract, prefer_exported=False),
        "blueprint": exported,
    }
    llm = _StubLLMClient()
    service = NarrativeGenerationService(llm_client=llm)

    retrieval, blueprint = service.build_or_load_blueprint(
        contract,
        user_prompt="Keep the sequel intimate.",
    )

    assert retrieval["meta"]["book_title"] == "Harry Potter and the Order of the Phoenix"
    assert blueprint == exported
    assert llm.json_calls == 0


def test_narrative_generation_service_regenerates_blueprint_when_forced():
    contract = _sample_contract()
    exported = _blueprint(
        title="Cached Blueprint",
        premise="Cached premise.",
        total_chapters=20,
        central_conflict="Cached conflict",
        tone="tense",
    )
    contract["outputs"]["sequel_artifacts"] = {
        "context": NarrativeContextService().build_from_contract(contract, prefer_exported=False),
        "blueprint": exported,
    }
    llm = _StubLLMClient()
    service = NarrativeGenerationService(llm_client=llm)

    _, blueprint = service.build_or_load_blueprint(
        contract,
        user_prompt="Force a new blueprint.",
        prefer_exported_blueprint=False,
    )

    assert blueprint["title"] == "Fresh Blueprint"
    assert llm.json_calls == 1


def test_narrative_generation_service_builds_retrieval_context_from_neo4j(monkeypatch):
    expected = {"meta": {"series_id": "harry-potter"}}

    class _DummyGraphService:
        def build_from_graph(self, **kwargs):
            assert kwargs["series_id"] == "harry-potter"
            assert kwargs["book_titles"] == ["Harry Potter and the Goblet of Fire"]
            return expected

        def close(self):
            return None

    service = NarrativeGenerationService(llm_client=_StubLLMClient())
    monkeypatch.setattr(service, "neo4j_context_service", _DummyGraphService())

    result = service.build_retrieval_context_from_neo4j(
        series_id="harry-potter",
        book_titles=["Harry Potter and the Goblet of Fire"],
    )

    assert result == expected


def test_narrative_generation_service_repairs_invalid_blueprint_json():
    class _RepairingLLM:
        def __init__(self):
            self.json_calls = 0
            self.prompts = []

        def generate_json(self, prompt: str, strict: bool = False, validator=None):
            self.json_calls += 1
            self.prompts.append(prompt)
            if self.json_calls == 1:
                payload = _blueprint(
                    title="Broken Blueprint",
                    premise="Missing central conflict and tone.",
                    total_chapters=12,
                )
                payload.pop("central_conflict")
                payload.pop("tone")
                if validator and not validator(payload):
                    return {"error": "validation_failed", "raw_output": payload}
                return payload
            payload = _blueprint(
                title="Recovered Blueprint",
                premise="A repaired sequel premise.",
                total_chapters=12,
                central_conflict="Recovered conflict",
            )
            if validator and not validator(payload):
                return {"error": "validation_failed", "raw_output": payload}
            return payload

        def generate_text(self, prompt: str, **kwargs):
            return ""

    retrieval = NarrativeContextService().build_from_contract(_sample_contract())
    service = NarrativeGenerationService(llm_client=_RepairingLLM())

    blueprint = service.generate_blueprint(
        service.compile_context(retrieval, "Continue the story.", generation_controls={"chapter_count": 12})
    )

    assert blueprint["title"] == "Recovered Blueprint"
    assert blueprint["central_conflict"] == "Recovered conflict"
    assert "SCHEMA REPAIR MODE (blueprint)" in service.llm.prompts[1]


def test_narrative_generation_service_validates_chapter_outline_and_repairs():
    class _OutlineRepairLLM:
        def __init__(self):
            self.json_calls = 0
            self.prompts = []

        def generate_json(self, prompt: str, strict: bool = False, validator=None):
            self.json_calls += 1
            self.prompts.append(prompt)
            if self.json_calls == 1:
                payload = {
                    "chapter_number": 1,
                    "chapter_title": "Broken Chapter",
                    "pov_character": "Harry Potter",
                    "location": "Hogwarts",
                    "scenes": [],
                    "arc_progress": {},
                    "world_state_changes": [],
                    "chapter_closes_on": "",
                }
                if validator and not validator(payload):
                    return {"error": "validation_failed", "raw_output": payload}
                return payload
            payload = {
                "chapter_number": 1,
                "chapter_title": "Recovered Chapter",
                "pov_character": "Harry Potter",
                "location": "Hogwarts",
                "scenes": [
                    {
                        "scene_number": 1,
                        "summary": "Harry learns something dangerous.",
                        "characters_present": ["Harry Potter", "Hermione Granger"],
                        "purpose": "Advance the mystery.",
                        "ends_on": "Harry realizes the threat is closer than expected.",
                    }
                ],
                "arc_progress": {"Harry's arc": "He accepts the new burden."},
                "world_state_changes": ["Harry now knows the enemy has returned."],
                "chapter_closes_on": "Harry stares into the dark corridor.",
            }
            if validator and not validator(payload):
                return {"error": "validation_failed", "raw_output": payload}
            return payload

        def generate_text(self, prompt: str, **kwargs):
            return ""

    retrieval = NarrativeContextService().build_from_contract(_sample_contract())
    service = NarrativeGenerationService(llm_client=_OutlineRepairLLM())
    compiled = service.compile_context(retrieval, "Continue the story.")
    blueprint = _blueprint(
        title="Recovered Blueprint",
        premise="A repaired sequel premise.",
        total_chapters=12,
        central_conflict="Recovered conflict",
    )

    outline = service.generate_chapter_outline(
        blueprint=blueprint,
        compiled_context=compiled,
        world_state=service.initialise_world_state(compiled),
        previous_summaries=[],
        chapter_number=1,
    )

    assert outline["chapter_title"] == "Recovered Chapter"
    assert outline["scenes"][0]["scene_number"] == 1
    assert "SCHEMA REPAIR MODE (chapter_outline_1)" in service.llm.prompts[1]


def test_narrative_generation_service_regenerates_when_exported_blueprint_conflicts_with_controls():
    contract = _sample_contract()
    exported = _blueprint(
        title="Cached Blueprint",
        premise="Cached premise.",
        total_chapters=20,
        central_conflict="Cached conflict",
        tone="tense",
    )
    contract["outputs"]["sequel_artifacts"] = {
        "context": NarrativeContextService().build_from_contract(contract, prefer_exported=False),
        "blueprint": exported,
    }
    class _ControlAwareLLM(_StubLLMClient):
        def generate_json(self, prompt: str, strict: bool = False, validator=None):
            self.json_calls += 1
            self.prompts.append(prompt)
            payload = _blueprint(
                canon_placement="mid_canon_insert",
                continuity_anchor="after book 3 and before book 4",
                total_chapters=15,
            )
            if validator and not validator(payload):
                return {"error": "validation_failed", "raw_output": payload}
            return payload

    llm = _ControlAwareLLM()
    service = NarrativeGenerationService(llm_client=llm)

    _, blueprint = service.build_or_load_blueprint(
        contract,
        user_prompt="Force a 15 chapter mid-canon book.",
        generation_controls={"chapter_count": 15, "canon_position": "mid_canon_insert"},
        prefer_exported_blueprint=True,
    )

    assert blueprint["title"] == "Fresh Blueprint"
    assert llm.json_calls == 1


def test_narrative_generation_service_repairs_blueprint_until_control_match():
    class _ControlRepairLLM:
        def __init__(self):
            self.json_calls = 0
            self.prompts = []

        def generate_json(self, prompt: str, strict: bool = False, validator=None):
            self.json_calls += 1
            self.prompts.append(prompt)
            if self.json_calls == 1:
                payload = _blueprint(total_chapters=25)
                if validator and not validator(payload):
                    return {"error": "validation_failed", "raw_output": payload}
                return payload
            payload = _blueprint(total_chapters=10)
            if validator and not validator(payload):
                return {"error": "validation_failed", "raw_output": payload}
            return payload

        def generate_text(self, prompt: str, **kwargs):
            return ""

    retrieval = NarrativeContextService().build_from_contract(_sample_contract())
    service = NarrativeGenerationService(llm_client=_ControlRepairLLM())
    compiled = service.compile_context(
        retrieval,
        "Continue the story.",
        generation_controls={"chapter_count": 10},
    )

    blueprint = service.generate_blueprint(compiled)

    assert blueprint["total_chapters"] == 10
    assert service.llm.json_calls == 1


def test_narrative_generation_service_locally_repairs_blueprint_chapter_count_and_act_ranges():
    service = NarrativeGenerationService(llm_client=_StubLLMClient())
    repaired = service._repair_blueprint_to_controls(
        _blueprint(
            total_chapters=25,
            acts=[
                {
                    "label": "Part One",
                    "chapter_range": "1-7",
                    "narrative_goal": "Set up.",
                    "ends_with": "Turn.",
                    "dominant_arcs": [],
                },
                {
                    "label": "Part Two",
                    "chapter_range": "8-16",
                    "narrative_goal": "Escalate.",
                    "ends_with": "Break.",
                    "dominant_arcs": [],
                },
                {
                    "label": "Part Three",
                    "chapter_range": "17-25",
                    "narrative_goal": "Resolve.",
                    "ends_with": "Finish.",
                    "dominant_arcs": [],
                },
            ],
        ),
        {
            "chapter_count": 10,
            "canon_position": "post_canon",
            "primary_pov_character": "Elain Archeron",
        },
    )

    assert repaired["total_chapters"] == 10
    assert [act["chapter_range"] for act in repaired["acts"]] == ["1-4", "5-7", "8-10"]
    assert "Elain Archeron" in repaired["continuity_anchor"]


def test_narrative_generation_service_normalizes_scene_prose_headings():
    service = NarrativeGenerationService(llm_client=_StubLLMClient())
    normalized = service._normalize_scene_prose_output(
        "**A Court of Silver Flames**\n**Chapter One: The Weight of Shadows**\n\nElain stood at the window."
    )

    assert normalized == "Elain stood at the window."


def test_narrative_generation_service_accepts_first_name_for_pov_presence():
    service = NarrativeGenerationService(llm_client=_StubLLMClient())
    error = service._scene_prose_validation_error(
        ("Elain stood at the window and listened to the house settle around her. " * 12).strip(),
        chapter_outline={"pov_character": "Elain Archeron"},
        scene_outline={"summary": "Elain wakes and listens to the house settle around her."},
        controls={"primary_pov_character": "Elain Archeron"},
        narrative_voice="third_person_limited",
    )

    assert error == ""


def test_narrative_generation_service_sanitizes_noisy_character_descriptions():
    service = NarrativeGenerationService(llm_client=_StubLLMClient())
    cleaned = service._sanitize_character_descriptions([
        "moonwhite silk robe, pale skin like fresh snow, iron engagement ring on finger",
        "quiet, observant, emotionally withdrawn, uncomfortable with the mating bond",
        "fawn-brown jacket with gold thread",
    ])

    assert cleaned == ["quiet, observant, emotionally withdrawn, uncomfortable with the mating bond"]


def test_narrative_generation_service_enforces_assigned_plot_beat_on_outline():
    service = NarrativeGenerationService(llm_client=_StubLLMClient())
    error = service._chapter_outline_validation_error(
        {
            "chapter_number": 1,
            "chapter_title": "Quiet Morning",
            "pov_character": "Elain Archeron",
            "location": "Velaris",
            "scenes": [
                {
                    "scene_number": 1,
                    "summary": "Elain tends the garden and avoids conversation.",
                    "characters_present": ["Elain Archeron"],
                    "purpose": "Set a mood.",
                    "ends_on": "She goes back inside.",
                }
            ],
            "arc_progress": {"Elain": "She remains withdrawn."},
            "world_state_changes": [],
            "chapter_closes_on": "She closes the door on the day.",
        },
        chapter_number=1,
        controls={
            "chapter_count": 10,
            "primary_pov_character": "Elain Archeron",
            "required_plot_beats": ["Elain begins experiencing increasingly violent prophetic visions connected to Koschei."],
            "relationship_directions": [],
        },
    )

    assert error == "chapter_required_plot_beat_missing"


def test_narrative_generation_service_does_not_duplicate_required_plot_beats_across_early_long_book_chapters():
    service = NarrativeGenerationService(llm_client=_StubLLMClient())

    error = service._chapter_outline_validation_error(
        {
            "chapter_number": 2,
            "chapter_title": "Quiet Interlude",
            "pov_character": "Elain Archeron",
            "location": "Velaris",
            "scenes": [
                {
                    "scene_number": 1,
                    "summary": "Elain withdraws after the first vision and avoids the others.",
                    "characters_present": ["Elain Archeron"],
                    "purpose": "Hold emotional aftermath without introducing a new major beat.",
                    "ends_on": "She resolves to keep the vision secret for now.",
                }
            ],
            "arc_progress": {"Elain": "She retreats inward after the shock."},
            "world_state_changes": [],
            "chapter_closes_on": "She decides silence is safer than confession.",
        },
        chapter_number=2,
        controls={
            "chapter_count": 30,
            "primary_pov_character": "Elain Archeron",
            "required_plot_beats": [
                "Elain begins experiencing increasingly violent prophetic visions connected to Koschei.",
                "Strange magical activity emerges near the human lands.",
                "Azriel investigates Koschei-related threats while growing closer to Elain.",
            ],
            "relationship_directions": [],
        },
    )

    assert error == ""


def test_narrative_generation_service_balances_required_plot_beats_without_frontloading_first_chapter():
    service = NarrativeGenerationService(llm_client=_StubLLMClient())

    chapter_1_controls = service._chapter_controls_for_generation(
        blueprint={"total_chapters": 10},
        controls={
            "chapter_count": 10,
            "required_plot_beats": [
                "Beat 1",
                "Beat 2",
                "Beat 3",
                "Beat 4",
                "Beat 5",
                "Beat 6",
                "Beat 7",
                "Beat 8",
                "Beat 9",
                "Beat 10",
                "Beat 11",
            ],
            "relationship_directions": [],
        },
        chapter_number=1,
    )
    chapter_2_controls = service._chapter_controls_for_generation(
        blueprint={"total_chapters": 10},
        controls={
            "chapter_count": 10,
            "required_plot_beats": [
                "Beat 1",
                "Beat 2",
                "Beat 3",
                "Beat 4",
                "Beat 5",
                "Beat 6",
                "Beat 7",
                "Beat 8",
                "Beat 9",
                "Beat 10",
                "Beat 11",
            ],
            "relationship_directions": [],
        },
        chapter_number=2,
    )

    assert chapter_1_controls["assigned_plot_beats"] == ["Beat 1"]
    assert chapter_2_controls["assigned_plot_beats"] == ["Beat 2"]


def test_narrative_generation_service_repairs_outline_to_include_missing_required_plot_beat():
    service = NarrativeGenerationService(llm_client=_StubLLMClient())

    repaired = service._repair_chapter_outline_to_controls(
        {
            "chapter_number": 10,
            "chapter_title": "Quiet Interlude",
            "pov_character": "Elain Archeron",
            "location": "Velaris",
            "scenes": [
                {
                    "scene_number": 1,
                    "summary": "Elain retreats to the garden and tries to calm herself.",
                    "characters_present": ["Elain Archeron"],
                    "purpose": "Show emotional aftermath from the earlier vision.",
                    "ends_on": "She steadies herself enough to face the others.",
                }
            ],
            "arc_progress": {"Elain": "She regains some control after the first shock."},
            "world_state_changes": [],
            "chapter_closes_on": "She leaves the garden with reluctant resolve.",
        },
        chapter_number=10,
        controls={
            "chapter_count": 10,
            "primary_pov_character": "Elain Archeron",
            "required_plot_beats": [
                "Elain begins experiencing increasingly violent prophetic visions connected to Koschei.",
                "Strange magical activity emerges near the human lands.",
                "Azriel investigates Koschei-related threats while growing closer to Elain.",
            ],
            "relationship_directions": [],
        },
    )

    assert repaired is not None
    assert "Azriel investigates Koschei-related threats while growing closer to Elain." in repaired["scenes"][0]["purpose"]


def test_narrative_generation_service_marks_lucien_release_as_payoff_then_aftermath():
    service = NarrativeGenerationService(llm_client=_StubLLMClient())
    controls = {
        "chapter_count": 10,
        "required_plot_beats": [
            "Elain begins experiencing increasingly violent prophetic visions connected to Koschei.",
            "Strange magical activity emerges near the human lands.",
            "Azriel investigates Koschei-related threats while growing closer to Elain.",
            "The mating bond between Lucien and Elain becomes emotionally and magically unstable.",
            "Nesta, Gwyn, and the Valkyries uncover ancient information about Made Seers and hidden gates between worlds.",
            "Political conflict grows in the Autumn Court and Day Court.",
            "Koschei attempts to use Elain’s powers to locate or open interworld gateways.",
            "Azriel is captured during the conflict.",
            "Elain fully embraces her Seer abilities and plays a major role in the final battle.",
            "Lucien ultimately releases Elain from the emotional expectation of the mating bond.",
            "The story ends with hints of larger crossover-level threats connected to other worlds and ancient fae history.",
        ],
        "relationship_directions": [
            {
                "characters": ["Elain Archeron", "Lucien Vanserra"],
                "relationship_type": "other",
                "desired_direction": "the bond becomes unstable and Lucien ultimately releases Elain from its emotional expectation",
                "notes": "politically and emotionally consequential",
            }
        ],
    }

    chapter_9 = service._chapter_controls_for_generation(
        blueprint={"total_chapters": 10},
        controls=controls,
        chapter_number=9,
    )
    chapter_10 = service._chapter_controls_for_generation(
        blueprint={"total_chapters": 10},
        controls=controls,
        chapter_number=10,
    )

    assert chapter_9["relationship_focus"][0]["stage"] == "payoff"
    assert chapter_10["relationship_focus"][0]["stage"] == "aftermath"


def test_narrative_generation_service_adds_lucien_characterization_guardrails_to_prose_calibration():
    service = NarrativeGenerationService(llm_client=_StubLLMClient())
    packet = service._prose_calibration_packet(
        controls={},
        chapter_controls={
            "relationship_focus": [
                {
                    "characters": ["Elain Archeron", "Lucien Vanserra"],
                    "relationship_type": "other",
                    "desired_direction": "release bond expectations",
                    "stage": "aftermath",
                }
            ],
            "assigned_plot_beats": [],
        },
        scene_outline={"characters_present": ["Elain Archeron", "Lucien Vanserra"]},
        scene_context_packet={"pov_character_packet": {"name": "Elain Archeron"}},
    )

    assert any("Lucien" in note for note in packet["avoid"])
    assert any("already completed" in note for note in packet["relationship_execution_notes"])


def test_narrative_generation_service_rejects_blueprint_with_act_ranges_beyond_total_chapters():
    service = NarrativeGenerationService(llm_client=_StubLLMClient())
    blueprint = _blueprint(
        total_chapters=10,
        acts=[
            {
                "label": "Part One",
                "chapter_range": "1-7",
                "narrative_goal": "Set up.",
                "ends_with": "Turn.",
                "dominant_arcs": [],
            },
            {
                "label": "Part Two",
                "chapter_range": "8-16",
                "narrative_goal": "Escalate.",
                "ends_with": "Break.",
                "dominant_arcs": [],
            },
        ],
    )

    error = service._blueprint_validation_error(blueprint, controls={"chapter_count": 10, "canon_position": "post_canon"})

    assert error == "act_ranges_do_not_match_total_chapters"


def test_narrative_generation_service_requires_divergence_anchor_for_divergent_mid_canon():
    service = NarrativeGenerationService(llm_client=_StubLLMClient())

    try:
        service.normalize_generation_controls(
            user_prompt="Rewrite the branch.",
            generation_controls={"canon_position": "mid_canon_divergent", "chapter_count": 12},
        )
    except ValueError as exc:
        assert "divergence_anchor is required" in str(exc)
    else:
        raise AssertionError("Expected divergent mid-canon controls to require a divergence anchor.")


def test_narrative_generation_service_infers_primary_pov_and_canon_preservation_from_prompt():
    service = NarrativeGenerationService(llm_client=_StubLLMClient())

    controls = service.normalize_generation_controls(
        user_prompt=(
            "Main focus:\n"
            "- Elain Archeron as the primary POV character\n\n"
            "Required canon continuity:\n"
            "- Feyre and Rhys are married with Nyx\n"
            "- Koschei remains imprisoned but influential\n"
        ),
        generation_controls={"chapter_count": 10},
    )

    assert controls["primary_pov_character"] == "Elain Archeron"
    assert controls["canon_elements_to_preserve"] == [
        {"event_id": "", "description": "Feyre and Rhys are married with Nyx"},
        {"event_id": "", "description": "Koschei remains imprisoned but influential"},
    ]


def test_narrative_generation_service_infers_relationship_and_style_controls_from_prompt():
    service = NarrativeGenerationService(llm_client=_StubLLMClient())

    controls = service.normalize_generation_controls(
        user_prompt=(
            "Core relationship expectations:\n"
            "- Elain Archeron and Azriel develop a forbidden romantic relationship\n"
            "- Lucien struggles with the rejected mating bond\n\n"
            "Tone and style requirements:\n"
            "- emotionally intense character-driven fantasy\n"
            "- slow-burn romance\n\n"
            "Important consistency requirements:\n"
            "- maintain accurate character personalities and speech patterns\n"
            "- keep court politics internally consistent\n"
        ),
        generation_controls={"chapter_count": 10},
    )

    assert controls["relationship_directions"][0]["characters"] == ["Elain Archeron", "Azriel"]
    assert controls["relationship_directions"][0]["relationship_type"] == "romance"
    assert any(item["characters"] == ["Elain Archeron", "Lucien"] for item in controls["relationship_directions"])
    assert controls["style_requirements"] == [
        "emotionally intense character-driven fantasy",
        "slow-burn romance",
    ]
    assert controls["consistency_requirements"] == [
        "maintain accurate character personalities and speech patterns",
        "keep court politics internally consistent",
    ]


def test_narrative_generation_service_enforces_primary_pov_on_outline():
    service = NarrativeGenerationService(llm_client=_StubLLMClient())

    error = service._chapter_outline_validation_error(
        {
            "chapter_number": 1,
            "chapter_title": "Shifted Voice",
            "pov_character": "Lucien",
            "location": "Velaris",
            "scenes": [
                {
                    "scene_number": 1,
                    "summary": "Lucien reflects on the bond.",
                    "characters_present": ["Lucien", "Elain Archeron"],
                    "purpose": "Shift away from Elain.",
                    "ends_on": "He decides to act.",
                }
            ],
            "arc_progress": {"Bond": "It frays."},
            "world_state_changes": ["Lucien makes a choice."],
            "chapter_closes_on": "Lucien steps into the dark.",
        },
        chapter_number=1,
        controls={"primary_pov_character": "Elain Archeron"},
    )

    assert error == "primary_pov_outline_mismatch"


def test_narrative_generation_service_accepts_loose_canon_preservation_matches():
    service = NarrativeGenerationService(llm_client=_StubLLMClient())
    blueprint = _blueprint(
        canon_elements_preserved=[
            "Feyre and Rhys remain married and are raising Nyx together.",
            "Koschei is still imprisoned but remains dangerous and influential.",
        ]
    )

    error = service._blueprint_validation_error(
        blueprint,
        controls={
            "chapter_count": 25,
            "canon_position": "post_canon",
            "canon_elements_to_preserve": [
                {"event_id": "", "description": "Feyre and Rhys are married with Nyx"},
                {"event_id": "", "description": "Koschei remains imprisoned but influential"},
            ],
        },
    )

    assert error == ""


def test_narrative_generation_service_scene_prompt_includes_scene_memory():
    class _TextCaptureLLM(_StubLLMClient):
        def generate_text(self, prompt: str, **kwargs):
            self.text_prompts.append(prompt)
            return "Harry Potter crossed the library stacks and listened for the scrape behind the shelves. " * 12

    service = NarrativeGenerationService(llm_client=_TextCaptureLLM())
    world_state = {
        "characters": [{"name": "Harry Potter"}, {"name": "Hermione Granger"}],
        "relationships": [{"between": "Harry Potter ↔ Hermione Granger"}],
        "active_threads": [],
        "events_so_far": [],
    }
    scene_memory = {
        "scene_count_completed": 2,
        "chapter_so_far_summary": "Harry learns the map is missing and Hermione notices the library lock has changed.",
        "prior_scene_summaries": [
            {"scene_number": 1, "summary": "Harry learns the map is missing."},
            {"scene_number": 2, "summary": "Hermione notices the library lock has changed."},
        ],
        "recent_scene_endings": [
            {"scene_number": 2, "ending": "A scrape echoes from behind the stacks."},
        ],
        "recent_prose_tail": [
            {"scene_number": 2, "tail": "The sound came again, closer this time."},
        ],
        "characters_seen_so_far": ["Harry Potter", "Hermione Granger"],
    }

    service.generate_scene_prose(
        scene_outline={
            "scene_number": 3,
            "summary": "Harry and Hermione investigate the forbidden aisle.",
            "characters_present": ["Harry Potter", "Hermione Granger"],
            "purpose": "Escalate the mystery.",
            "ends_on": "A hidden door opens.",
        },
        chapter_outline={
            "chapter_number": 1,
            "chapter_title": "The Hidden Door",
            "pov_character": "Harry Potter",
            "location": "Hogwarts Library",
        },
        world_state=world_state,
        previous_scene_ending="A scrape echoes from behind the stacks.",
        book_title="Harry Potter and the Order of the Phoenix",
        scene_memory=scene_memory,
        generation_controls={
            "primary_pov_character": "Harry Potter",
            "canon_elements_to_preserve": [{"event_id": "", "description": "Harry and Hermione remain allies."}],
            "required_plot_beats": ["Harry and Hermione investigate the forbidden aisle."],
        },
    )

    prompt = service.llm.text_prompts[0]
    assert "FOCUSED SCENE CONTEXT PACKET" in prompt
    assert "PROSE CALIBRATION PACKET" in prompt
    assert "CHAPTER MEMORY SO FAR" in prompt
    assert "Harry learns the map is missing" in prompt
    assert "The sound came again, closer this time." in prompt
    assert "Harry and Hermione remain allies." in prompt
    assert "NARRATIVE VOICE: third_person_limited" in prompt


def test_narrative_generation_service_carries_scene_memory_forward_between_scenes(tmp_path):
    retrieval = NarrativeContextService().build_from_contract(_sample_contract())

    class _SceneMemoryLLM:
        def __init__(self):
            self.json_calls = 0
            self.text_prompts = []

        def generate_json(self, prompt: str, strict: bool = False, validator=None):
            self.json_calls += 1
            if self.json_calls == 1:
                payload = _blueprint(
                    title="Memory Blueprint",
                    premise="Premise",
                    total_chapters=1,
                )
            else:
                payload = {
                    "chapter_number": 1,
                    "chapter_title": "Memory Chapter",
                    "pov_character": "Harry Potter",
                    "location": "Hogwarts",
                    "scenes": [
                        {
                            "scene_number": 1,
                            "summary": "Harry finds a coded note.",
                            "characters_present": ["Harry Potter"],
                            "purpose": "Start the mystery.",
                            "ends_on": "He recognizes the handwriting.",
                        },
                        {
                            "scene_number": 2,
                            "summary": "Hermione helps decode the note.",
                            "characters_present": ["Harry Potter", "Hermione Granger"],
                            "purpose": "Advance the mystery.",
                            "ends_on": "They realize the note points underground.",
                        },
                    ],
                    "arc_progress": {"Mystery": "The clue becomes actionable."},
                    "world_state_changes": ["Harry and Hermione commit to follow the clue."],
                    "chapter_closes_on": "They head toward the hidden passage.",
                }
            if validator and not validator(payload):
                return {"error": "validation_failed", "raw_output": payload}
            return payload

        def generate_text(self, prompt: str, **kwargs):
            self.text_prompts.append(prompt)
            scene_index = len(self.text_prompts)
            return (
                f"Harry Potter moved carefully through the corridor while Hermione Granger tracked the hidden clue. "
                f"Scene {scene_index} prose kept the mystery taut until the final image lingered in the air. "
            ) * 8

    service = NarrativeGenerationService(llm_client=_SceneMemoryLLM(), target_chapters=1)
    output_dir = service.generate_sequel(
        retrieval,
        user_prompt="Continue carefully.",
        output_dir=tmp_path / "sequel",
        generation_controls={"chapter_count": 1},
    )

    assert output_dir.exists()
    assert len(service.llm.text_prompts) == 2
    second_prompt = service.llm.text_prompts[1]
    assert "Harry finds a coded note." in second_prompt
    assert '"scene_count_completed": 1' in second_prompt


def test_narrative_generation_service_repairs_scene_prose_when_first_person_drifts():
    class _ProseRepairLLM(_StubLLMClient):
        def __init__(self):
            super().__init__()
            self.text_calls = 0

        def generate_text(self, prompt: str, **kwargs):
            self.text_prompts.append(prompt)
            self.text_calls += 1
            if self.text_calls == 1:
                return ("I walked into the garden and I felt the world split around me. " * 20).strip()
            return ("Elain Archeron moved through the garden in careful silence, watching the shadows gather between the roses. " * 10).strip()

    service = NarrativeGenerationService(llm_client=_ProseRepairLLM())
    prose = service.generate_scene_prose(
        scene_outline={
            "scene_number": 1,
            "summary": "Elain senses the rift opening again in the garden.",
            "characters_present": ["Elain Archeron", "Azriel"],
            "purpose": "Re-establish the threat.",
            "ends_on": "A crack of dark light opens above the roses.",
        },
        chapter_outline={
            "chapter_number": 1,
            "chapter_title": "The Whispering Rift",
            "pov_character": "Elain Archeron",
            "location": "Velaris garden",
        },
        world_state={
            "characters": [{"name": "Elain Archeron"}, {"name": "Azriel"}],
            "relationships": [{"between": "Elain Archeron <-> Azriel"}],
            "active_threads": [],
            "events_so_far": [],
        },
        previous_scene_ending="The night air trembles over the roses.",
        book_title="A Court of Silver Flames.epub",
        generation_controls={"primary_pov_character": "Elain Archeron"},
    )

    assert "Elain Archeron" in prose
    assert "PROSE REPAIR MODE" in service.llm.text_prompts[1]


def test_narrative_generation_service_rejects_ornamental_repetition():
    service = NarrativeGenerationService(llm_client=_StubLLMClient())

    error = service._scene_prose_validation_error(
        (
            "Elain stood in her moon-white silk robe, the iron band on her finger glinting in the dark. "
            "The moon-white silk robe whispered again, and the iron band on her finger felt heavier than breath. "
        ) * 8,
        chapter_outline={"pov_character": "Elain Archeron"},
        scene_outline={
            "summary": "Elain steadies herself after a vision.",
            "purpose": "Ground her emotionally.",
            "ends_on": "She goes inside.",
        },
        controls={"primary_pov_character": "Elain Archeron"},
        narrative_voice="third_person_limited",
        scene_context_packet={"required_plot_beats": []},
    )

    assert error == "scene_prose_repetitive_ornamental_detail"


def test_narrative_generation_service_outline_prompt_includes_story_position():
    retrieval = NarrativeContextService().build_from_contract(_sample_contract())
    class _OutlineCaptureLLM(_StubLLMClient):
        def generate_json(self, prompt: str, strict: bool = False, validator=None):
            self.json_calls += 1
            self.prompts.append(prompt)
            payload = {
                "chapter_number": 2,
                "chapter_title": "The Next Turn",
                "pov_character": "Harry Potter",
                "location": "Hogwarts",
                "scenes": [
                    {
                        "scene_number": 1,
                        "summary": "Harry follows the corridor clue.",
                        "characters_present": ["Harry Potter"],
                        "purpose": "Advance the next turn.",
                        "ends_on": "A hidden lock answers him.",
                    }
                ],
                "arc_progress": {"Harry": "Presses forward."},
                "world_state_changes": ["Harry commits to the corridor mystery."],
                "chapter_closes_on": "A hidden lock answers him.",
            }
            if validator and not validator(payload):
                return {"error": "validation_failed", "raw_output": payload}
            return payload

    service = NarrativeGenerationService(llm_client=_OutlineCaptureLLM())
    compiled = service.compile_context(retrieval, "Continue the story.")
    blueprint = _blueprint(total_chapters=3)

    service.generate_chapter_outline(
        blueprint=blueprint,
        compiled_context=compiled,
        world_state=service.initialise_world_state(compiled),
        previous_summaries=["Chapter 1 - Turning Point: Harry chooses action. [Closes on: The corridor opens.]"],
        chapter_number=2,
        current_story_position={
            "source_book_ending": compiled["story_ending"],
            "latest_generated_ending": "The corridor opens.",
            "latest_chapter_summary": "Chapter 1 - Turning Point: Harry chooses action.",
            "chapters_completed": 1,
        },
    )

    prompt = service.llm.prompts[-1]
    assert "FOCUSED CHAPTER CONTEXT PACKET" in prompt
    assert "The corridor opens." in prompt


def test_narrative_generation_service_carries_forward_previous_generated_ending(tmp_path):
    retrieval = NarrativeContextService().build_from_contract(_sample_contract())
    compiled = NarrativeGenerationService(llm_client=_StubLLMClient()).compile_context(
        retrieval,
        "Continue the story.",
        generation_controls={"chapter_count": 2, "primary_pov_character": "Harry Potter"},
    )
    source_ending = compiled["story_ending"]["last_scene_summary"]

    class _SequencedService(NarrativeGenerationService):
        def __init__(self):
            super().__init__(llm_client=_StubLLMClient())
            self.first_scene_endings = []

        def generate_blueprint(self, compiled_context):
            return _blueprint(
                total_chapters=2,
                continuity_anchor="Primary POV: Harry Potter.",
            )

        def generate_chapter_outline(self, *, chapter_number, **kwargs):
            return {
                "chapter_number": chapter_number,
                "chapter_title": f"Chapter {chapter_number}",
                "pov_character": "Harry Potter",
                "location": "Hogwarts",
                "scenes": [
                    {
                        "scene_number": 1,
                        "summary": f"Scene {chapter_number} happens.",
                        "characters_present": ["Harry Potter"],
                        "purpose": "Advance the story.",
                        "ends_on": f"Ending beat {chapter_number}.",
                    }
                ],
                "arc_progress": {"Harry": "Moves forward."},
                "world_state_changes": [f"Chapter {chapter_number} change."],
                "chapter_closes_on": f"Ending beat {chapter_number}.",
            }

        def generate_scene_prose(self, *, previous_scene_ending, chapter_outline, **kwargs):
            if chapter_outline.get("chapter_number") in (1, 2):
                self.first_scene_endings.append(previous_scene_ending)
            return (
                f"Harry Potter stood in the corridor and listened to the castle breathe. "
                f"Scene for chapter {chapter_outline.get('chapter_number')} closes on Ending beat {chapter_outline.get('chapter_number')}."
            )

    service = _SequencedService()
    output_dir = tmp_path / "generated"
    service.generate_sequel(
        retrieval,
        user_prompt="Continue the story.",
        output_dir=output_dir,
        generation_controls={"chapter_count": 2, "primary_pov_character": "Harry Potter"},
    )

    assert len(service.first_scene_endings) == 2
    assert service.first_scene_endings[0] == source_ending
    assert "Ending beat 1" in service.first_scene_endings[1]
