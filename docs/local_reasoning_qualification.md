# Local reasoning qualification

## Direction

Local inference is the required production baseline. Cloud LLM providers are excluded from model qualification and may not be used as hidden fallback paths. Agents continue to depend only on the reasoning runtime contract; model engines and task routing remain runtime-owned concerns.

Engine selection is evidence-driven and explicit; the qualification CLI has no default engine:

1. LM Studio is the primary controlled desktop engine for compatible conventional models. Its load API exposes memory estimation, GPU offload, context length, Flash Attention, KV-cache placement, MoE expert count, TTL, and explicit unload behavior.
2. Ollama is a supported lightweight engine and cross-engine reference. It is not the architectural default and may be selected when its model compatibility or measured behavior is better.
3. Colibri is an isolated MoE weight-streaming research engine. It must pass model-support, fast-storage capacity, I/O throughput, and latency preflight before integration; it is not treated as a generic GGUF engine.

The reasoning runtime contract remains engine-neutral. Production routes bind a task profile to a qualified engine and exact model artifact; agents do not select engines directly.

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

Status: **no-go on current storage, do not download**.

Colibri is an experimental model-specific multi-tier MoE engine rather than a general GGUF replacement for Ollama or LM Studio. Its official GLM-5.2 path requires approximately 380 GB on fast NVMe and streams roughly 11 GB of expert weights per token. This workstation has 71.9 GiB free on its NVMe; the spacious drives are HDDs and are unsuitable for the documented disk-bound path. Colibri remains eligible only after a dedicated NVMe capacity and random-read preflight passes. Weight streaming is useful for capacity, but it does not improve interactive latency on the current disks.

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

Llama 3.1 8B planning passed its screening passage but failed 3/3 on the first full-book case and was eliminated. No installed model currently qualifies for events, entities, character/world modeling, planning, continuity, or narrative generation. Extraction completeness is only a minimum-item proxy because the corpus does not yet have human-labeled gold sets; true precision/recall remains a production-readiness blocker. Gold-backed qualification is bound to the exact corpus artifact and fails closed for missing, empty, pending, or stale annotations.

Candidate acquisition is externally constrained. The Ollama registry delivered approximately 0.25 MB/s on a bounded range test; direct Hugging Face delivered approximately 0.45 MB/s. Hugging Face Xet transferred no data and returned HTTP 416 from its CAS reconstruction endpoint. Partial downloads remain resumable. Qwen3.5 9B is installed and verified through Ollama. The official `openai/gpt-oss-20b` artifact is being acquired through LM Studio's managed download API, whose job endpoint exposes byte progress, transfer rate, and completion estimate without blocking qualification tooling.

## Workstation resource policy

Desktop responsiveness is a hard qualification SLO. Earlier qwen2.5 14B runs reached 11.03 GiB of the 12 GiB GPU and made the workstation nearly unusable. Models are now unloaded between sessions, and the Ollama server is configured for one resident model, one parallel request, queue depth 8, 2 GiB reserved VRAM, 4K request context, q8 KV cache, flash attention, cloud disabled, and below-normal process priority.

The reasoning package also provides optional provider-neutral bounded admission. Production agent compositions can cap concurrent inference, bound waiting requests, reject overload immediately, enforce queue deadlines and cancellation, and record per-request queue outcomes without coupling agents to Ollama. This boundary prevents unbounded agent fan-out even if the backing engine's own queue configuration changes.

LM Studio is now a native loopback-only reasoning provider using the same JSON, text, tool, LangGraph, checkpoint, and evaluation contracts. The shared qualifier controls GPU offload ratio, context, parallelism, TTL, lifecycle polling, and resource gates without duplicating task logic. An installed GPT-OSS 20B Q5_1 derivative at 50% GPU placement used 9.38 GiB total VRAM. Warm real-book structured JSON passed in 5.40 seconds with 5.20-second TTFT at low reasoning effort; the same streamed request took 59.76 seconds at the model's uncontrolled reasoning behavior. Native tool use passed in 11.65 seconds. Cold loading from file cache completed in 4.29 seconds, while an earlier CLI-attached load exceeded 120 seconds despite the server completing the load; lifecycle polling now detects server readiness directly.

These LM Studio measurements establish engine feasibility, not production model qualification. The installed artifact is an abliterated community derivative and is excluded from production routing. A fair Ollama-versus-LM Studio comparison still requires the same official model artifact or equivalent quantization on both engines.

The exact Qwen3.5 9B Q4_K_M GGUF was exposed to both engines through hard links, with no duplicated model bytes. LM Studio estimated 7.63 GB including 4K context and had more than 11 GB free VRAM, but both its selected llama.cpp CUDA runtime 2.27.1 and the stable update 2.28.2 returned a worker `load-error`. The artifact remains valid in Ollama. This engine/model pair is classified unsupported, not resource-rejected, and is not retried further. Engine versions are now included in load evidence and checkpoint identity.

With Ollama thinking explicitly disabled, Qwen3.5 9B passed the real-book structured-JSON screening case exactly. Cold load completed in 37.53 seconds; warm task wall time was 2.92 seconds, TTFT 1.77 seconds, and decode throughput 19.20 tokens/second. Peak total VRAM was 6.32 GiB and peak host RAM was 81.39 GiB. This is one accepted contract task, not a production route. The host CPU baseline was already 96% because unrelated Plex transcodes and WSL workloads were active, so broader quality testing was deferred rather than competing with user workloads.

The versioned candidate manifest now separates canonical model identity from engine-specific artifacts. It records engine compatibility, placement fraction, full-GPU fit, and controlled-hybrid fit. Pre-download projections cannot qualify a route: every selected engine/model pair still requires LM Studio or Ollama load evidence plus measured per-task RAM, VRAM, latency, reliability, and quality checkpoints. Scorecards group by `(task family, provider, model)` so evidence from different engines can never be merged.

Qualification defaults to at most 32 GPU layers and 8 CPU threads, rejects trials above 10 GiB total VRAM or 112 GiB host RAM, and includes allocation settings in checkpoint identity. A safe qwen2.5 14B trial used 7.28 GiB VRAM but fell to 0.95 tokens/second due to CPU offload, so that model is not suitable for interactive desktop work under the headroom policy. The next preferred candidate is `qwen3.5:9b-q4_K_M`: its official 6.6 GB artifact and 32-layer architecture should fit fully on this GPU under the safety limits. Suitability must still be proven by measured load, responsiveness, and real-book quality tests.

Production scorecard generation requires complete per-trial resource evidence and applies the same 10 GiB VRAM and 112 GiB host-RAM ceilings. Extraction routes additionally require reviewed exact-corpus gold metrics. Rebuilding the scorecard from the current 30 full-scope real-book trials leaves only Mistral 7B structured JSON and native tool use qualified; no unqualified fallback is permitted.

## Fast empirical funnel

Model discovery now precedes full qualification. Each candidate first receives one bounded trial on entity extraction, generation planning, and native tool use. A request is capped at 90 seconds; poor quality or latency eliminates the route before repeated nine-family testing. Only the top one or two candidates proceed to three-source repeated qualification.

The first equal-task shootout produced:

| Model | Accepted | Cold load | Median task | Entity evidence | Planning evidence | Tool use |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Qwen3.5 9B Q4_K_M | 1/3 | 13.16 s | 14.52 s | 0.17 | 0.33 | pass |
| Mistral 7B Instruct | 2/3 | 19.55 s | 13.86 s | 0.90 | 1.00 | pass |
| Llama 3.1 8B | 2/3 | 24.80 s | 14.87 s | 0.00 | 1.00 | pass |

All three stayed below 6.4 GiB total VRAM during inference and were unloaded immediately afterward. The Qwen failures were genuine grounding errors: it merged dialogue separated by narration and inserted ellipses into purported verbatim quotations. Llama is eliminated because its entity evidence precision was zero. Qwen2.5 14B is also eliminated for this workstation: prior checkpoints show inconsistent schema/grounding, failed planning, and approximately 10.17 GiB VRAM in its responsive configuration; safer partial placement fell below one token/second.

Mistral's repeated planning promotion attempt accepted 6/9 trials. It passed all repetitions for *A Court of Thorns and Roses* and *The Cruel Prince*, but failed all three *Caraval* trials by paraphrasing every required verbatim quote. Qwen3.5 then accepted the same *Caraval* case 3/3 with a 17.09-second median, but its earlier ACOTAR planning result failed. Neither model qualifies as a family-wide planning route, and no model-chain workaround is introduced. The official GPT-OSS 20B LM Studio artifact is the next and final discovery candidate before selecting the repeated-qualification shortlist.
