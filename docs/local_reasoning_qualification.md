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
