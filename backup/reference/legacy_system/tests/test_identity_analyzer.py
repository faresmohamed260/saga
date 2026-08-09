from saga.agents.identity_analyzer import IdentityAnalyzer


class StubLLMClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def generate_json(self, prompt: str, strict: bool = False, validator=None):
        self.calls += 1
        response = self.responses[min(self.calls - 1, len(self.responses) - 1)]
        if validator and isinstance(response, dict) and "error" not in response and not validator(response):
            return {"error": "validation_failed", "raw_output": response}
        return response


def build_sample_scene():
    return {
        "book_index": 1,
        "chapter_index": 1,
        "scene_index": 1,
        "length": 180,
        "text": "Feyre stalks through the snow. The huntress nocks an ash arrow. Tomas Mandray is mentioned in passing.",
    }


def test_identity_analyzer_normalizes_and_retries():
    invalid = {"canonical_characters": []}
    valid = {
        "canonical_characters": [
            {
                "name": "Feyre",
                "role": "huntress",
                "is_new_character": False,
                "names_used": ["Feyre", "the huntress"],
            },
            {
                "name": "Tomas Mandray",
                "role": "",
                "is_new_character": True,
                "names_used": ["Tomas Mandray"],
            },
        ],
        "character_mentions": [
            {
                "mention_text": "the huntress",
                "mention_type": "title",
                "canonical_name": "Feyre",
                "is_consequential_character": True,
            }
        ],
        "alias_updates": [
            {
                "alias": "the huntress",
                "canonical_name": "Feyre",
                "action": "map_alias",
                "reasoning": "The scene clearly uses the huntress to refer to Feyre.",
            }
        ],
        "rejected_identity_candidates": ["doe"],
    }

    stub = StubLLMClient([invalid, valid])
    analyzer = IdentityAnalyzer(llm_client=stub, max_attempts=2)
    result = analyzer.analyze(build_sample_scene())

    assert stub.calls == 2
    assert result["canonical_characters"][0]["name"] == "Feyre"
    assert any(item["name"] == "Tomas Mandray" for item in result["canonical_characters"])
    assert result["character_mentions"][0]["canonical_name"] == "Feyre"
    assert result["rejected_identity_candidates"] == ["doe"]


def test_identity_analyzer_tool_mode_builds_identity_fields():
    tool_response = {
        "tool_calls": [
            {"tool": "add_canonical_character", "arguments": {"name": "Feyre", "role": "huntress", "is_new_character": False, "names_used": ["Feyre", "the huntress"]}},
            {"tool": "add_canonical_character", "arguments": {"name": "Tomas Mandray", "role": "", "is_new_character": True, "names_used": ["Tomas Mandray"]}},
            {"tool": "add_character_mention", "arguments": {"mention_text": "the huntress", "mention_type": "title", "canonical_name": "Feyre", "is_consequential_character": True}},
            {"tool": "add_alias_update", "arguments": {"alias": "the huntress", "canonical_name": "Feyre", "action": "map_alias", "reasoning": "Scene support is explicit."}},
        ]
    }

    stub = StubLLMClient([tool_response])
    analyzer = IdentityAnalyzer(llm_client=stub, max_attempts=1)
    result = analyzer.analyze(
        build_sample_scene(),
        local_evidence={"candidate_characters": [{"name": "Tomas Mandray"}]},
        analysis_mode="tool",
    )

    assert any(item["name"] == "Tomas Mandray" for item in result["canonical_characters"])
    assert result["character_mentions"][0]["canonical_name"] == "Feyre"
    assert result["alias_updates"][0]["canonical_name"] == "Feyre"
    assert result["tool_runtime"]["tool_calls_seen"] >= 1
