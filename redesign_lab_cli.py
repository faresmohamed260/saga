"""Separate CLI entrypoint for redesign, benchmark, and research utilities.

Production encode/retrieval/generation work should go through `saga_tools.py`.
This CLI remains for redesign-lab experiments, benchmark harnesses, and
supporting BookNLP identity preparation utilities.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Redesign-lab CLI (research/benchmark utilities plus BookNLP support tasks)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bench = subparsers.add_parser("benchmark-all", help="[research] Run redesign subtask benchmarks on ACOTAR slices.")
    bench.add_argument("--output-root", default="redesign_lab/reports")

    dry = subparsers.add_parser("run-dry", help="[research] Run a redesign dry pass on a small ACOTAR slice.")
    dry.add_argument("--output-root", default="redesign_lab/outputs")
    dry.add_argument("--llm-mode", default="general_compute")
    dry.add_argument("--model-override", default="deepseek-v3.1")

    full = subparsers.add_parser("run-end-to-end", help="[research] Run the full redesign end-to-end ACOTAR pipeline.")
    full.add_argument("--output-root", default="redesign_lab/outputs")
    full.add_argument("--prompt", required=True)
    full.add_argument("--generation-controls", default="")
    full.add_argument("--identity-provider-mode", default="redesign_inventory")
    full.add_argument("--identity-json-path", default="")

    compare = subparsers.add_parser("compare", help="[research] Generate redesign vs baseline comparison report.")
    compare.add_argument("--baseline-root", default="analysis_outputs")
    compare.add_argument("--redesign-root", default="redesign_lab/outputs")
    compare.add_argument("--output-path", default="redesign_lab/reports/comparison_report.json")

    clean_booknlp = subparsers.add_parser("clean-booknlp-identity", help="[production-support] Clean BookNLP identity output into production tiers.")
    clean_booknlp.add_argument("--input-json", required=True)
    clean_booknlp.add_argument("--output-json", required=True)
    clean_booknlp.add_argument("--report-md", required=True)

    smoke_booknlp = subparsers.add_parser("smoke-booknlp-identity-integration", help="[production-support] Load cleaned BookNLP identity into the pipeline-facing schema and run a downstream smoke test.")
    smoke_booknlp.add_argument("--input-json", required=True)
    smoke_booknlp.add_argument("--contract-json", required=True)
    smoke_booknlp.add_argument("--output-json", required=True)
    smoke_booknlp.add_argument("--report-md", required=True)

    build_series_booknlp = subparsers.add_parser("build-booknlp-series-identity", help="[production-support] Generate BookNLP small raw/clean/pipeline identities and a conservative series identity index.")
    build_series_booknlp.add_argument("--books-config", required=True)
    build_series_booknlp.add_argument("--output-root", required=True)
    build_series_booknlp.add_argument("--audit-json", required=True)
    build_series_booknlp.add_argument("--audit-md", required=True)
    build_series_booknlp.add_argument("--series-output-json", required=True)

    args = parser.parse_args()

    if args.command == "benchmark-all":
        from redesign_lab.benchmarks.run_all import run_all_benchmarks

        report = run_all_benchmarks(args.output_root)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if args.command == "run-dry":
        from redesign_lab.pipeline.orchestrator import RedesignOrchestrator

        orchestrator = RedesignOrchestrator(output_root=args.output_root)
        report = orchestrator.run_dry(llm_mode=args.llm_mode, model_override=args.model_override)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if args.command == "run-end-to-end":
        from redesign_lab.pipeline.orchestrator import RedesignOrchestrator

        orchestrator = RedesignOrchestrator(output_root=args.output_root)
        generation_controls = json.loads(args.generation_controls) if args.generation_controls else {}
        report = orchestrator.run_end_to_end(
            user_prompt=args.prompt,
            generation_controls=generation_controls,
            identity_provider_mode=args.identity_provider_mode,
            identity_json_path=args.identity_json_path or None,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if args.command == "compare":
        from redesign_lab.pipeline.comparison import generate_comparison_report

        payload = generate_comparison_report(
            baseline_root=args.baseline_root,
            redesign_root=args.redesign_root,
            output_path=args.output_path,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.command == "clean-booknlp-identity":
        from redesign_lab.identity.booknlp_identity_adapter import clean_booknlp_identity

        payload = clean_booknlp_identity(
            input_json=args.input_json,
            output_json=args.output_json,
            report_md=args.report_md,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.command == "smoke-booknlp-identity-integration":
        from redesign_lab.identity.identity_provider import run_booknlp_identity_integration_smoke

        payload = run_booknlp_identity_integration_smoke(
            input_json=args.input_json,
            contract_json=args.contract_json,
            output_json=args.output_json,
            report_md=args.report_md,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.command == "build-booknlp-series-identity":
        from redesign_lab.identity.series_identity_provider import (
            build_series_pipeline_identity,
            generate_book_identity_bundle,
            write_series_identity_audit,
        )

        config = json.loads(Path(args.books_config).read_text(encoding="utf-8"))
        book_summaries = []
        for index, book in enumerate(config.get("books") or [], start=1):
            summary = generate_book_identity_bundle(
                book=book,
                book_index=index,
                output_root=args.output_root,
                reuse_book1_seed=True,
            )
            book_summaries.append(summary)
        audit = write_series_identity_audit(
            book_summaries=book_summaries,
            output_root=args.output_root,
            audit_json_path=args.audit_json,
            audit_md_path=args.audit_md,
        )
        series_identity = build_series_pipeline_identity(
            book_summaries=book_summaries,
            output_json=args.series_output_json,
        )
        print(json.dumps({
            "book_summaries": book_summaries,
            "audit_json": str(args.audit_json),
            "audit_md": str(args.audit_md),
            "series_output_json": str(args.series_output_json),
            "series_identity_character_count": len(series_identity.get("characters") or []),
            "series_alias_count": len(series_identity.get("alias_index") or {}),
            "audit_book_count": len(audit.get("books") or []),
        }, ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
