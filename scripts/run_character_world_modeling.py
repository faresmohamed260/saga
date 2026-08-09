from __future__ import annotations

import json
import sys

from packages.character_world_modeling import CharacterWorldModelingRunRequest, CharacterWorldModelingService


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_character_world_modeling.py <series_id> [thread_id]")
        return 1
    series_id = str(sys.argv[1]).strip()
    thread_id = str(sys.argv[2]).strip() if len(sys.argv) > 2 else "character-world-modeling"
    service = CharacterWorldModelingService.from_env()
    result = service.run(CharacterWorldModelingRunRequest(series_id=series_id, thread_id=thread_id))
    quality = service.build_quality_audit(result=result)
    report = service.persist_runtime_report(
        request=CharacterWorldModelingRunRequest(series_id=series_id, thread_id=thread_id),
        result=result,
        quality_audit=quality,
    )
    print(
        json.dumps(
            {
                "series_id": series_id,
                "character_profile_count": len(result.character_profiles),
                "stable_character_state_count": len(result.stable_character_states),
                "world_state_count": len(result.world_states),
                "quality_audit": quality,
                "report": report,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
