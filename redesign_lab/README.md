# Redesign Lab

This subtree contains an isolated redesign track for the narrative pipeline.

Goals:
- reuse proven repo components through redesign-local adapters
- keep the current production pipeline untouched
- benchmark real ACOTAR subtasks before assigning winners
- assemble a redesign-only end-to-end run after subtask selection

Nothing in this subtree should mutate current production defaults in:
- `saga_tools.py`
- `story_dashboard.py`
- `services/encoder_persistence_service.py`
- `services/narrative_generation_service.py`

Use:
- `python redesign_lab_cli.py benchmark-all`
- `python redesign_lab_cli.py run-dry`
- `python redesign_lab_cli.py run-end-to-end`
- `python redesign_lab_cli.py compare`

