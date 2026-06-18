from saga.retrieval.story_index_service import StoryIndexService
from saga.domain.timeline.causal_graph_service import CausalGraphService


class StubLLMClient:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def generate_json(self, prompt: str, strict: bool = False, validator=None):
        self.calls += 1
        response = self.response
        if validator and isinstance(response, dict) and "error" not in response and not validator(response):
            return {"error": "validation_failed", "raw_output": response}
        return response


def build_timeline():
    return [
        {
            "time_index": 1,
            "book_index": 1,
            "chapter_index": 1,
            "scene_index": 1,
            "event_id": "evt_1",
            "summary": "Feyre kills the wolf.",
            "characters": ["Feyre"],
        },
        {
            "time_index": 2,
            "book_index": 1,
            "chapter_index": 1,
            "scene_index": 2,
            "event_id": "evt_1",
            "summary": "Tamlin confronts Feyre about the wolf.",
            "characters": ["Tamlin", "Feyre"],
        },
    ]


def build_scene_analyses():
    return [
        {"book_index": 1, "chapter_index": 1, "scene_index": 1, "scene_summary": "Feyre hunts and kills a wolf.", "events": [], "text": "Feyre kills the wolf."},
        {"book_index": 1, "chapter_index": 1, "scene_index": 2, "scene_summary": "Tamlin arrives because of the wolf killing.", "events": [], "text": "Tamlin confronts Feyre."},
    ]


def test_causal_graph_service():
    stub = StubLLMClient(
        {
            "events": [
                {
                    "id": "t_1",
                    "description": "Feyre kills the wolf.",
                    "event_type": "ACTION",
                    "story_impact": 8,
                    "reversibility": 2,
                    "caused_by": [],
                    "causes": [{"event_id": "t_2", "relationship": "TRIGGERS", "explanation": "Tamlin comes because of the wolf's death."}],
                    "prevents": [],
                    "required_for": [{"event_id": "t_2", "why_required": "The confrontation depends on the wolf being killed."}],
                },
                {
                    "id": "t_2",
                    "description": "Tamlin confronts Feyre about the wolf.",
                    "event_type": "CONFLICT",
                    "story_impact": 9,
                    "reversibility": 4,
                    "caused_by": [{"event_id": "t_1", "relationship": "TRIGGERS", "explanation": "The killing draws Tamlin to her."}],
                    "causes": [],
                    "prevents": [],
                    "required_for": [],
                },
            ],
            "critical_path": [{"event_id": "t_1", "criticality_score": 9, "why_critical": "It initiates the chain."}],
            "flexible_events": [],
            "causal_chains": [{"chain_id": "chain_1", "description": "Wolf death to confrontation", "event_sequence": ["t_1", "t_2"], "chain_type": "LINEAR", "story_function": "inciting arc"}],
            "divergence_points": [],
        }
    )
    service = CausalGraphService(llm_client=stub)
    result = service.build(build_timeline(), build_scene_analyses())

    assert result["metrics"]["total_events"] == 2
    assert result["metrics"]["critical_path_length"] == 1
    assert result["graph"]["events"][0]["id"] == "t_1"
    assert result["graph"]["events"][1]["caused_by"][0]["event_id"] == "t_1"


def test_causal_graph_indexing():
    causal_graph_result = {
        "graph": {
            "events": [
                {
                    "id": "t_1",
                    "description": "Feyre kills the wolf.",
                    "source_summary": "Feyre kills the wolf.",
                    "characters": ["Feyre"],
                    "time_index": 1,
                    "book_index": 1,
                    "chapter_index": 1,
                    "scene_index": 1,
                    "caused_by": [],
                    "causes": [{"event_id": "t_2"}],
                }
            ]
        },
        "metrics": {
            "total_events": 1,
            "total_links": 1,
            "avg_links_per_event": 1.0,
            "critical_path_length": 1,
            "causal_chain_count": 1,
            "divergence_count": 0,
            "flexible_event_count": 0,
        },
    }
    index = StoryIndexService()
    result = index.build(causal_graph_result=causal_graph_result)
    assert result["document_count"] == 2
    matches = index.query("Feyre kills the wolf", min_similarity=0.01, max_results=4)
    assert matches
    assert any(item["item_type"] == "causal_event" for item in matches)
