# Local reasoning completion audit

This audit treats the persistent qualification objective as authoritative. `Proven` means current tracked artifacts or live runtime evidence satisfy the requirement. `Pending` means completion may not be claimed.

| Requirement | Status | Authoritative evidence |
| --- | --- | --- |
| Provider-neutral reusable reasoning runtime | Proven | `packages/reasoning_runtime/contracts.py`, `client.py`, `factory.py`, and qualification tests |
| Native Ollama and LM Studio engines using shared contracts | Proven | Loopback-only `ollama_local` and `lm_studio_local` modes; shared qualifier and scorecards |
| No cloud fallback during local qualification | Proven | Local profiles reject non-loopback URLs, disable rotation, and force `allow_cross_provider_fallback = False` |
| Model storage off system NVMe | Proven | Ollama and LM Studio model roots are on `B:`; host inventory is in `docs/local_reasoning_qualification.md` |
| Versioned corpus from at least three real books | Proven | `benchmarks/reasoning/local_books_v1.json` and canonical corpus fingerprint |
| All nine required task families | Proven | Corpus manifest and `benchmarks/reasoning/task_suite.py` |
| Reviewed extraction precision/recall evidence | Proven | `local_extraction_gold_v1.json`; exact-corpus gold evaluator and incumbent scorecard |
| Mistral 7B evaluation | Proven | Full current-suite incumbent scorecard with repeated trials across all families and early elimination |
| Llama 3.1 8B evaluation | Proven | Repeated current-suite challenger funnel plus failed full planning promotion |
| Qwen2.5 14B evaluation | Proven by early elimination | Three bounded current-suite entity deadline failures under safe hybrid placement; earlier cross-family baseline checkpoints remain preserved |
| GPT-OSS 20B evaluation | Proven | Official hash-verified artifact; three repeated current-suite entity, planning, and tool trials |
| Qwen3 14B evaluation | Proven | Official hash-verified artifact; repeated current-suite entity, planning, and tool trials |
| Qwen3 30B-A3B evaluation | Pending | Official identity and fit are verified; durable acquisition is 9,723,125,098 / 18,556,685,824 bytes (52.40%), but inference evidence is absent |
| Schema, evidence, hallucination, contradiction, completeness, reliability, TTFT, throughput, wall, RAM/VRAM, and context evidence | Proven for evaluated routes | Aggregated `quality_metrics`, `provider_metrics`, resource peaks, failure modes, and context variants in tracked scorecards |
| Failure recovery | Proven | Exact checkpoint planning skips model loading; real Qwen3 14B resume returned in 7.76 seconds at baseline VRAM |
| Per-task routing, SLOs, and single-machine queue policy | Proven | `local_production_routes_v1.json`, `routing.py`, and `queueing.py` |
| Colibri written go/no-go decision | Proven | Storage/I/O preflight records a no-go without downloading frontier weights |
| Final model scorecard and readiness decision | Pending | Incumbent and challenger scorecards exist; final scorecard cannot include Qwen3 30B evidence yet |

## Current decision

Local reasoning is **partial ready**. Structured JSON and native tool use are qualified through Mistral 7B. All semantic families fail closed. The full objective remains incomplete until Qwen3 30B-A3B receives bounded real-book evaluation and the final scorecard/readiness audit is regenerated.
