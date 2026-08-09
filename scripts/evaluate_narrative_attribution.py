from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from packages.analysis_foundation.attribution_evaluation import AttributionGoldCase, evaluate_attribution
from packages.analysis_foundation.store import AnalysisFoundationStore
from packages.canon_extraction.store import CanonExtractionStore
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate narrative attribution metrics for a persisted series.")
    parser.add_argument("--series-id", required=True)
    parser.add_argument("--cases-json", required=True)
    parser.add_argument("--database-url", default="")
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()

    database_url = str(args.database_url or "").strip()
    profile = PersistenceProfile(
        name="narrative-attribution-evaluation",
        provider="supabase",
        mode="supabase_postgres" if database_url else "test_harness",
        database_url=database_url,
        application_name="narrative-attribution-evaluation",
        local_storage_root_dir="analysis_outputs/unified_storage",
    )
    persistence = create_persistence_client(profile=profile, config=PersistenceRuntimeConfig(profile=profile))
    persistence.initialize()
    analysis = AnalysisFoundationStore(persistence)
    canon = CanonExtractionStore(persistence)
    bundle = analysis.load_identity_bundle(series_id=args.series_id)
    if bundle is None:
        raise ValueError(f"No identity bundle found for series '{args.series_id}'.")
    cases_payload = json.loads(Path(args.cases_json).read_text(encoding="utf-8"))
    cases = [AttributionGoldCase.model_validate(item) for item in list(cases_payload.get("cases") or [])]
    result = evaluate_attribution(
        events=[item.model_dump() for item in canon.list_events(series_id=args.series_id)],
        gold_cases=cases,
        valid_character_refs={character.character_id for character in bundle.characters},
    )
    payload = {"series_id": args.series_id, "metrics": result.model_dump()}
    if str(args.output_json or "").strip():
        Path(args.output_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
