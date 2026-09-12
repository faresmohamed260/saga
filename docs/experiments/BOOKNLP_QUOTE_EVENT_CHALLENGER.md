# BookNLP Quote / Speaker / Event Challenger

Status: **EXPERIMENT WRAPPER READY — REAL MODEL QUALIFICATION NOT YET RUN**

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

The pinned upstream README documents `BookNLP("en", model_params)` followed by `.process(input_file, output_directory, book_id)` and explicitly supports selecting a subset of pipeline elements. The pinned implementation requires entity tagging for quotation attribution and requires quotation attribution plus entities for coreference, which is why the challenger pipeline keeps `entity`, `quote`, and `coref` together while adding `event`.

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

The TypeScript provider process then reuses `src/local-analysis/booknlp-output.ts` to normalize:

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

Pinned BookNLP 1.0.7 contains direct model-download behavior when its model files are missing. The S.A.G.A. runner therefore **fails before BookNLP initialization unless all three required model files already exist** in the explicitly configured model directory.

The child environment also sets:

- `HF_HUB_OFFLINE=1`;
- `TRANSFORMERS_OFFLINE=1`;
- `TOKENIZERS_PARALLELISM=false`;
- `CUDA_VISIBLE_DEVICES=` for this CPU baseline.

This is defense in depth, not a general operating-system network sandbox. The experiment host must have all required package/model/cache artifacts installed before execution.

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

For a real measured run, the experiment record must additionally capture the environment/lock digest and artifact sizes/digests where practical. Package version alone does not prove that an installation contains the exact compatibility commit.

## CI qualification

Normal CI does **not** install or download BookNLP.

A model-light fixture runner implements the same inner-runner CLI and emits representative `.tokens`, `.entities`, and `.quotes` files for the existing Unicode BookNLP fixture. End-to-end tests exercise:

- generic S.A.G.A. subprocess client;
- BookNLP-specific protocol process;
- exact runner-command/model-path configuration fingerprint;
- temporary-file path;
- existing BookNLP TSV normalizer;
- returned quote/speaker and event evidence;
- wrong pinned package version;
- missing required output files.

This proves wrapper/control-plane behavior only. It is not model-quality evidence.

## Existing negative evidence remains binding

BookNLP-small remains **not adopted for primary character identity** based on the reproducible 100-document LitBank result documented in `2026-09-12_character_identity_booknlp-small.md`.

This challenger must not use its quote/event usefulness to silently reverse that decision.

## Next measured work

Once a compatible local environment is available:

1. health-check the wrapper against the exact pinned BookNLP environment;
2. run source-neutral/public quote/event smoke material first;
3. record startup time, per-document/whole-book wall time, peak RAM/VRAM, model artifact size and semantic fingerprints;
4. compare BookNLP quote/speaker evidence against the deterministic dialogue floor through `DIALOGUE_SPEAKER_BENCHMARK.md`;
5. compare BookNLP event triggers against the lexical event floor through `EVENT_CANDIDATE_BENCHMARK.md`;
6. preserve failures and false positives rather than patching the benchmark around them;
7. when the private EPUB suite becomes reachable, use those books as the production promotion gate.

No production adoption is possible while the model-weight license remains unverified.
