This directory contains the isolated legacy and transitional system code.

Isolation rule used for this pass:
- if a slice was not part of the clean rebuild surface, it was moved here
- compatibility adapters and old orchestration code were treated as legacy
- breaking the old runtime was acceptable by design for this cleanup

Active source tree after isolation:
- `packages/`
- `integrations/comfyui/` minus legacy provider wrapper
- `integrations/kokoro_tts/` minus legacy provider wrapper
- `integrations/xcore_litbank/` minus legacy provider wrapper
- `apps/dashboard_pro/`
- `docs/MIGRATION_REFERENCE.md`
- `docs/agent_framework.md`
- `docs/dashboard_pro.md`
- `tests/test_reasoning_runtime.py`
- `tests/test_langgraph_runtime.py`
- `tests/test_xcore_litbank_client.py`
- `saga/providers/modal_state.py`

Everything else that still represented the old SAGA architecture, transitional adapter glue, SQLite-first pipeline code, old dashboard API code, or legacy tests/docs/scripts was moved here as reference material.
