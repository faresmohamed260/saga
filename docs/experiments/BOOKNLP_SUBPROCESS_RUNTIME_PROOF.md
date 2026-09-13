# BookNLP Generic Subprocess Runtime Proof

Status: **MEASURED PHASE-3B RUNTIME EVIDENCE — NOT A MODEL-QUALITY PROMOTION**

Issue: #224

This experiment proves that the real pinned BookNLP-small runtime can execute through S.A.G.A.'s generic `saga-local-literary-subprocess-v1` boundary while preserving provider-neutral semantic evidence exactly. It also measures one-shot startup/process cost and compares it with a single loaded BookNLP instance so transport decisions are based on evidence rather than architecture preference.

## Scope

This experiment does **not** change quote, speaker, event-trigger, identity or participant quality metrics. The existing 100-document LitBank component results remain authoritative for model quality. It does not adopt BookNLP for production, satisfy the private modern-fiction gate, or verify the BookNLP model-weight license.

Normal CI remains model-light. The heavyweight proof runs only in the dedicated Phase-3B workflow.

## Pinned runtime

- BookNLP package: `1.0.7`
- BookNLP base commit: `3d900fc2224e55960c3363826ae28539b77b4204`
- compatibility commit: `8875a1b616d764b7d13d1e30e9949cc21ca303c1`
- PyTorch: `2.3.1+cpu`
- transformers: `4.43.4`
- spaCy: `3.7.5`
- spaCy model: `en_core_web_sm 3.7.1`
- provider protocol: `saga-local-literary-subprocess-v1`
- LitBank revision: `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`
- measured document: `1023_bleak_house_brat`
- source bytes/code points: `11,738 / 11,738`

The workflow prepares BookNLP task weights and Hugging Face caches before inference, then verifies the three BERT bases and spaCy model with `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`.

## Exact semantic transport result

The generic path is:

`SubprocessLocalLiteraryEvidenceProvider -> BookNLP provider process -> pinned Python runner -> TypeScript normalization/validation`.

Direct preserved BookNLP native output and generic subprocess output produced the exact same provider-neutral evidence fingerprint:

`8be0f789a80ecf47c0b902b51e0492c17ef016023c3e215df6a4d57ff3e27add`

Evidence counts also matched exactly:

- identity mentions: `230`
- typed entities: `230`
- quotes: `5`
- event triggers: `20`
- syntax tokens: `2,319`

The semantic comparison fingerprint was:

`e2c5bf310df9e9f5c8f7c9ec2d645e7989f7c555ba0b58f08366b77cd2fe4466`

Therefore the generic boundary introduces **no measured semantic transport drift** on this pinned real-model proof.

## One-shot generic subprocess measurement

Second exact-head proof run (`34759959737`) measured:

- generic `health()` wall clock: `2.847 s`
- generic `analyze()` wall clock: `8.930 s`
- whole measured process-tree wall clock: `12.678 s`
- peak aggregate process-tree RSS: `1040.5 MiB`
- typecheck: pass
- analysis-worker tests: `139 / 139` pass
- heavyweight workflow: success
- evidence artifact ID: `10318109017`
- artifact digest: `sha256:dbb49b34a31e0a711052c72cc19b8bce6d628114dde96d1897b9daf9791fd8a2`

The earlier proof run (`34759798966`) also succeeded with the same semantic evidence fingerprint and counts. Its measured `health()` / `analyze()` times were `2.578 s / 6.314 s`, with `1037.2 MiB` peak aggregate process-tree RSS. Runtime varies by host/run; semantics did not.

## Prepared offline runtime footprint

The historical `160,398,571 byte` measurement remains correct for BookNLP's three task-model files, but it is not the complete offline runtime footprint.

Measured preparation for this proof:

- BookNLP task-model artifacts: `160,398,571 bytes` (~`153.0 MiB`)
- Hugging Face transformer cache: `284,705,427 bytes` (~`271.5 MiB`)
- spaCy model: `15,242,123 bytes` (~`14.5 MiB`)
- total prepared artifacts: `460,346,121 bytes` (~`439.0 MiB`)

Whole cache-directory manifest hashes changed between independent preparations even though individual pinned task-weight digests and semantic output stayed stable. The cache directories include mutable ecosystem bookkeeping, so their whole-directory hashes are **not** treated as stable model identities. Stable provenance should rely on pinned model IDs/revisions, package versions and immutable artifact/file digests where available.

## Warm loaded-runtime comparison

A separate measurement used one BookNLP instance for repeated processing of the same document:

- initialization: `1.229 s`
- warm process repeat 1: `4.505 s`
- warm process repeat 2: `4.140 s`
- repeated native output fingerprint: identical across both passes
- peak resident memory: `732.0 MiB`

On the same workflow run, generic one-shot `analyze()` took `8.930 s`. Relative to the second warm pass, the one-shot generic path was about `2.16x` slower.

This does **not** imply that JSON serialization or the TypeScript wrapper alone costs the difference. The current protocol launches a fresh provider process per request, and the BookNLP provider path constructs a fresh Python model runtime for analysis. The evidence therefore supports testing a **persistent loaded Python provider process/service**, not merely keeping the outer Node wrapper alive.

## Decision

1. **Generic subprocess correctness is validated for one real pinned BookNLP document.** Exact provider-neutral evidence survives the complete runtime boundary unchanged.
2. **The current one-process-per-request lifecycle has material measured overhead.** A persistent loaded Python BookNLP runtime is justified as the next transport/runtime experiment.
3. **Subprocess is not yet rejected.** It remains the simplest validated baseline and may still be acceptable for low-throughput/offline work.
4. **Do not implement a distributed/network-visible service.** Any persistent challenger remains localhost/private-only and must preserve the same versioned request/evidence validation boundary, resource guards, source fingerprints and secret isolation.
5. **No BookNLP production adoption follows.** Private modern-fiction qualification and production-compatible model-weight licensing are still mandatory.

## Existing quality baseline remains unchanged

- deterministic quote F1: `0.8563`
- BookNLP quote F1: `0.8146`
- combined speaker V2: matched-known accuracy `0.7007`, E2E recall `0.5994`, contamination `0.1709`
- BookNLP event-trigger F1: `0.7791`
- lexical Tier-0 event-trigger F1: `0.1045`
- BookNLP primary identity: rejected

The runtime proof changes only the **transport/runtime experiment decision**: persistent loaded Python execution is now worth measuring.
