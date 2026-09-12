# BookNLP Quote / Speaker / Event Challenger

Status: **PUBLIC COMPONENT QUALIFICATION COMPLETE AND REPEATABLE — PRIVATE PRODUCT GATE PENDING**

This experiment narrows BookNLP-small to roles that remain open after its rejection as S.A.G.A.'s primary character-identity provider: quotation/speaker evidence, literary event triggers, and dependency/syntax evidence used by later deterministic grounding.

The wrapper is not a production-provider decision.

## Pinned provenance

The measured compatibility lineage remains unchanged:

- upstream repository: `booknlp/booknlp`;
- official base commit: `3d900fc2224e55960c3363826ae28539b77b4204`;
- compatibility commit: `8875a1b616d764b7d13d1e30e9949cc21ca303c1` (`bert.embeddings.position_ids` state-dict compatibility fix);
- package metadata version: `1.0.7`;
- code license: MIT;
- model: `small`;
- pipeline: `entity,quote,event,coref`;
- model-weight license: **unverified** and therefore still an adoption blocker.

The pinned upstream implementation requires entity tagging for quotation attribution and requires quotation attribution plus entities for coreference, which is why the challenger pipeline keeps `entity`, `quote`, and `coref` together while adding `event`.

## S.A.G.A. boundary

The challenger uses the merged `saga-local-literary-subprocess-v1` boundary from PR #207.

S.A.G.A. owns:

- outer provider/configuration/input fingerprints;
- subprocess limits and retryability classification;
- temporary source/output workspace lifecycle;
- exact Unicode/source evidence validation;
- provider-neutral evidence contracts;
- downstream identity/speaker/event policy.

BookNLP owns only model inference and its native output files.

The TypeScript provider process reuses `src/local-analysis/booknlp-output.ts` to normalize:

- `.tokens` -> source-anchored event/syntax evidence;
- `.entities` -> typed entity + identity evidence;
- `.quotes` -> quote/speaker evidence.

No second BookNLP evidence schema is introduced.

## Real runner contract

`providers/booknlp_runner.py` is intentionally installation-free. An operator must prepare the exact compatibility environment and model artifacts first.

The runner:

1. verifies installed package version `1.0.7`;
2. requires an explicit pre-populated `--model-path`;
3. verifies the three BookNLP-small model files expected by the pinned upstream source;
4. initializes `BookNLP("en", {"pipeline":"entity,quote,event,coref", "model":"small", "model_path": ...})`;
5. processes the temporary normalized-text file;
6. writes ordinary BookNLP `.tokens`, `.entities`, `.quotes`, and other native outputs to the temporary output directory.

The wrapper removes the temporary workspace after each request.

## Network / artifact policy

Pinned BookNLP 1.0.7 contains direct model-download behavior when its model files are missing. The S.A.G.A. provider runner therefore fails before BookNLP initialization unless all required files already exist in the explicitly configured model directory.

The controlled GitHub benchmark harness is a separate experiment runner and may download/install its pinned experimental dependencies and artifacts before inference. That must not be confused with the production/local provider contract.

The provider child environment also sets:

- `HF_HUB_OFFLINE=1`;
- `TRANSFORMERS_OFFLINE=1`;
- `TOKENIZERS_PARALLELISM=false`;
- `CUDA_VISIBLE_DEVICES=` for this CPU baseline.

This is defense in depth, not a general operating-system network sandbox.

## Configuration fingerprint

The runtime configuration fingerprint includes:

- S.A.G.A. BookNLP adapter version;
- provider descriptor and exact pinned upstream commits;
- expected package version;
- pipeline and model;
- required model filenames;
- runner executable;
- runner argument vector;
- configured model-directory path.

A different executable, wrapper path, model path, pipeline/provenance constant, or compatibility revision produces a different configuration fingerprint.

## Model-light CI qualification

Normal CI does **not** install or download BookNLP.

A model-light fixture runner implements the same inner-runner CLI and emits representative `.tokens`, `.entities`, and `.quotes` files. End-to-end tests exercise:

- generic S.A.G.A. subprocess client;
- BookNLP-specific protocol process;
- exact runner-command/model-path configuration fingerprint;
- temporary-file path;
- existing BookNLP TSV normalizer;
- returned quote/speaker and event evidence;
- wrong pinned package version;
- missing required output files.

This proves wrapper/control-plane behavior only.

## Public component qualification

PR #212 added the direct 100-document pinned LitBank component benchmark. Two independent CPU runs on exact benchmark head `f013f23f11d2883e8ef1f2e70f9e181e8556df08` produced the exact same semantic report fingerprint:

`e0ec94d8d1f678f98057a29117d365926a3253a4a6d5e6e0f7c96e36cab3bef9`

Measured results:

- BookNLP quote P/R/F1: `0.7706 / 0.8640 / 0.8146`;
- deterministic quote P/R/F1: `0.8570 / 0.8555 / 0.8563`;
- BookNLP matched-known-speaker accuracy: `0.7830`;
- BookNLP end-to-end speaker recall: `0.6765`;
- BookNLP cross-character contamination: `0.1889`;
- BookNLP event-trigger P/R/F1: `0.8003 / 0.7591 / 0.7791`;
- lexical Tier-0 event-trigger P/R/F1: `0.4914 / 0.0585 / 0.1045`.

Operational evidence:

- run 1: `452.68 s`, `1123.8 MiB` peak RSS;
- run 2: `293.66 s`, `1157.2 MiB` peak RSS;
- model artifacts: `160,398,571 bytes`;
- both runs completed `100 / 100` documents with zero failures;
- heavyweight workflow typecheck + `111 / 111` tests passed on both attempts.

The full benchmark interpretation lives in `BOOKNLP_COMPONENT_BENCHMARK.md`.

## Component decision

The public evidence narrows BookNLP rather than promoting it wholesale:

- primary identity remains **rejected**;
- deterministic quote boundaries remain preferred over BookNLP quote detection;
- BookNLP speaker attribution is a **strong challenger** but needs confidence gating because `18.89%` contamination remains material;
- BookNLP event triggering is the leading measured trigger challenger;
- event participant grounding remains unmeasured and must be developed separately.

Follow-up combined speaker work is tracked in `#213`; dependency-aware event grounding is tracked in `#214`.

## Important limitations

BookNLP's speaker/event models use LitBank-derived literary annotations, so this public benchmark is strong regression/component evidence but not an independent modern-fiction generalization test.

The owner-controlled modern-fiction suite remains the production promotion gate, and the required private EPUB binaries are still unavailable to the current execution environment.

No production adoption is possible while the model-weight license remains unverified.
