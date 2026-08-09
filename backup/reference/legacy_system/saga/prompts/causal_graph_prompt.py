from typing import List


def causal_graph_prompt(
    event_lines: List[str],
    scene_lines: List[str],
    character_lines: List[str],
    state_lines: List[str],
    relationship_lines: List[str],
) -> str:
    timeline_text = "\n".join(event_lines)
    scene_text = "\n".join(scene_lines)
    character_text = "\n".join(character_lines) if character_lines else "None"
    state_text = "\n".join(state_lines) if state_lines else "None"
    relationship_text = "\n".join(relationship_lines) if relationship_lines else "None"

    return f"""
You are a narrative causality analyst.

Your task is to build a grounded causal graph from the provided story saga.domain.timeline.

Use ONLY the listed event IDs. Do NOT invent new events. If causality is unclear, leave arrays empty.

EVENT TIMELINE:
{timeline_text}

SCENE CONTEXT:
{scene_text}

CHARACTER CONTEXT:
{character_text}

STATE-CHANGE CONTEXT:
{state_text}

RELATIONSHIP CONTEXT:
{relationship_text}

Return STRICT JSON with this schema:
{{
  "events": [
    {{
      "id": "t_1",
      "description": "short factual description copied or paraphrased from the timeline event",
      "event_type": "ACTION | DISCOVERY | DECISION | REVELATION | CONFLICT | TRANSFORMATION",
      "story_impact": 1,
      "reversibility": 1,
      "caused_by": [
        {{
          "event_id": "t_0",
          "relationship": "ENABLES | REQUIRES | TRIGGERS",
          "explanation": "short grounded reason"
        }}
      ],
      "causes": [
        {{
          "event_id": "t_2",
          "relationship": "ENABLES | REQUIRES | TRIGGERS",
          "explanation": "short grounded reason"
        }}
      ],
      "prevents": [
        {{
          "alternative": "what this event prevented",
          "why_blocked": "why it was blocked"
        }}
      ],
      "required_for": [
        {{
          "event_id": "t_3",
          "why_required": "why needed"
        }}
      ]
    }}
  ],
  "critical_path": [
    {{
      "event_id": "t_1",
      "criticality_score": 1,
      "why_critical": "reason"
    }}
  ],
  "flexible_events": [
    {{
      "event_id": "t_2",
      "flexibility_score": 1,
      "why_flexible": "reason"
    }}
  ],
  "causal_chains": [
    {{
      "chain_id": "chain_1",
      "description": "what this chain represents",
      "event_sequence": ["t_1", "t_2", "t_3"],
      "chain_type": "LINEAR | BRANCHING | CONVERGENT",
      "story_function": "narrative purpose"
    }}
  ],
  "divergence_points": [
    {{
      "event_id": "t_2",
      "decision_made": "what choice happened",
      "alternatives": ["alt1", "alt2"],
      "divergence_potential": 1,
      "alternate_timeline": "what might have happened otherwise"
    }}
  ]
}}

Rules:
- Only reference IDs that appear in the timeline
- Keep story_impact and reversibility on a 1-10 scale
- If unsure, use empty arrays
- Prefer fewer, stronger causal links over weak guesses
- Use the extra context only to clarify causality for the listed events
- Do not invent off-batch events, relationships, or state changes
"""
