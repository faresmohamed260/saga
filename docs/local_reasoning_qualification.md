# Local reasoning qualification

## Direction

Local inference is the required production baseline. Cloud LLM providers are excluded from model qualification and may not be used as hidden fallback paths. Agents continue to depend only on the reasoning runtime contract; model engines and task routing remain runtime-owned concerns.

The evaluation order is:

1. Ollama local inference using conventional quantized models.
2. LM Studio comparison for the top two models only when it can isolate an engine effect.
3. Colibri research preflight only when conventional models fail quality thresholds.

Model selection is per task. A model that is strong at extraction is not assumed to be suitable for narrative generation.

## Host inventory

- CPU: Intel Xeon E5-2680 v4, 14 cores / 28 logical processors.
- RAM: 128 GiB DDR4.
- GPU: NVIDIA RTX 3060, 12 GiB VRAM.
- Ollama: 0.32.5.
- Ollama model storage: `B:\.ollama\models` on a 2 TB SATA SSD.
- Existing Ollama blobs: 131.89 GiB.
- Free space on `B:` at inventory time: approximately 108 GiB.
- System NVMe `C:` free space: approximately 3 GiB; it must not receive model weights.

The planned Qwen3 14B, Qwen3 30B-A3B, and GPT-OSS 20B downloads require approximately 42 GiB and fit on `B:` without moving existing weights. Existing models are not deleted automatically.

## Colibri decision

Status: **deferred, do not download**.

Colibri is an experimental multi-tier MoE engine rather than a general replacement for Ollama. Its relevant model families require roughly 142 GiB or more of model storage, while the reference GLM-5.2 container is roughly 372 GiB. The only currently spacious local volume is a mechanical HDD, which is unsuitable for expert streaming. Colibri remains eligible only after conventional candidates fail quality gates and a dedicated NVMe capacity and random-read preflight passes.

## Initial runtime evidence

The reasoning runtime now has an explicit `ollama_local` mode. It enforces a loopback endpoint, never reads cloud credentials, does not rotate accounts, and has no fallback provider. Local profiles specify both model and context window.

`qwen2.5:14b` structured-output probe at 4K context:

- Result: schema-valid `{"status":"ready","sum":42}`.
- Cold wall time: 88.2 seconds.
- Cold model startup observed in Ollama logs: 59.1 seconds.
- Provider compute: 25.5 seconds.
- Warm wall time: 1.2 seconds.
- Warm provider compute: 0.62 seconds.
- Cloud fallback or rotation: none.

An uncontrolled 32K context probe exhausted the 170-second request deadline while allocating about 6 GiB of KV cache and driving total VRAM use to roughly 11 GiB. This established that context size must be an explicit task-level benchmark parameter.

## Reproducibility

The corpus manifest is `benchmarks/reasoning/local_books_v1.json`. It contains source paths, SHA-256 identities, chapter counts, and deterministic sampling instructions only. Source text remains outside the repository.

Every model/task/repetition produces one atomic checkpoint. Completed trials are reused by stable identity, and models can be eliminated only by an explicit minimum-trial acceptance policy. Individual reasoning requests are capped at five minutes.

The executable qualification entrypoint is `scripts/qualify_local_reasoning.py`. It separates bounded model preload from task inference, pins the qualified model for the requested session, records cold-load evidence, and samples host RAM and GPU VRAM through local NVML. Screening runs one passage per task family and cannot eliminate a model before every family is represented. Full qualification runs every family against all three books and is reserved for models that pass at least one relevant screening route.

## Qualification findings

The initial qwen2.5 14B load failures were caused by context allocation, not inference. A preload without explicit `num_ctx` used Ollama's 32K model default, allocated approximately 6 GiB of KV buffers, reduced GPU offload to 33 of 49 layers, and exceeded 180 seconds. The corrected 4K preload completed in 47.4 seconds with full GPU placement. Warm structured output then completed in 1.83 seconds.

Native tool use passed on real corpus metadata in 1.84 seconds. Canon-event extraction is fast and stable but currently below the strict grounding gate: three of three trials were rejected, with the first versioned evaluator run producing five items at 0.80 verbatim evidence precision. Typographic quote normalization is evaluator-owned and versioned; paraphrased evidence remains a model error.

Official Ollama candidate tags and default artifact sizes verified for this host are `qwen3:14b` (9.3 GB), `qwen3:30b-a3b-instruct-2507-q4_K_M` (19 GB), and `gpt-oss:20b` (14 GB). Downloads remain staged one model at a time.

## Baseline decision

The installed-model screening matrix completed for Mistral 7B Instruct, Llama 3.1 8B, and Qwen2.5 14B across all nine task families. Full three-book qualification currently establishes only these provisional routes:

- Qwen2.5 14B: relationship extraction, 9/9 accepted, 10.71-second median warm task time.
- Mistral 7B Instruct: exact structured JSON, 9/9 accepted, 0.70-second median; native tool use, 9/9 accepted, 0.90-second median.

Llama 3.1 8B planning passed its screening passage but failed 3/3 on the first full-book case and was eliminated. No installed model currently qualifies for events, entities, character/world modeling, planning, continuity, or narrative generation. Extraction completeness is only a minimum-item proxy because the corpus does not yet have human-labeled gold sets; true precision/recall remains a production-readiness blocker.

Candidate acquisition is externally constrained. The Ollama registry delivered approximately 0.25 MB/s on a bounded range test; direct Hugging Face delivered approximately 0.45 MB/s. Hugging Face Xet transferred no data and returned HTTP 416 from its CAS reconstruction endpoint. Partial downloads remain resumable. Qwen3.5 9B is being acquired as one below-normal-priority Ollama transfer; qualification does not begin until the transfer completes and host admission passes.

## Workstation resource policy

Desktop responsiveness is a hard qualification SLO. Earlier qwen2.5 14B runs reached 11.03 GiB of the 12 GiB GPU and made the workstation nearly unusable. Models are now unloaded between sessions, and the Ollama server is configured for one resident model, one parallel request, queue depth 8, 2 GiB reserved VRAM, 4K request context, q8 KV cache, flash attention, cloud disabled, and below-normal process priority.

The reasoning package also provides optional provider-neutral bounded admission. Production agent compositions can cap concurrent inference, bound waiting requests, reject overload immediately, enforce queue deadlines and cancellation, and record per-request queue outcomes without coupling agents to Ollama. This boundary prevents unbounded agent fan-out even if the backing engine's own queue configuration changes.

Qualification defaults to at most 32 GPU layers and 8 CPU threads, rejects trials above 10 GiB total VRAM or 112 GiB host RAM, and includes allocation settings in checkpoint identity. A safe qwen2.5 14B trial used 7.28 GiB VRAM but fell to 0.95 tokens/second due to CPU offload, so that model is not suitable for interactive desktop work under the headroom policy. The next preferred candidate is `qwen3.5:9b-q4_K_M`: its official 6.6 GB artifact and 32-layer architecture should fit fully on this GPU under the safety limits. Suitability must still be proven by measured load, responsiveness, and real-book quality tests.
