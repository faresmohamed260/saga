# Phase 3A — GLiNER Small v2.1 + F-Coref Five-Document Smoke

Date: 2026-09-12
Status: **TECHNICALLY VALID SMOKE — FULL-CORPUS COMPONENT QUALIFICATION REQUIRED**

## Provenance

Successful run: `34706511198`
S.A.G.A. source head: `42d842e767c43f1a06f44aeea9a477caba0f61ef`
Artifact:

- ID: `10302485293`
- name: `saga-phase3-gliner-fcoref-smoke`
- digest: `sha256:76ebbe74b002a1215a249db6e453ab9c98c528281143596dfa0ecfb4eb9a7353`

Pinned corpus:

- `dbamman/litbank@3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`
- first five sorted `coref/tsv` documents

Pinned candidate configuration:

- GLiNER code `urchade/GLiNER@cf9e5f7d9fb99158b592132a9ec7cbfabb43a9a0`
- GLiNER model `urchade/gliner_small-v2.1@f23104c107e3c57f5c7aa36d53a9667c67b4b866`
- F-Coref code `Digital-Insight-Technologies-Ltd/fastcoref@8888e51d97d4818a25dd5f5d8b541d397fad9362`
- F-Coref model `biu-nlp/f-coref@d5a382c8bfe1105cee1a73007525ee08ab693d9a`
- GLiNER threshold `0.5`
- GLiNER code-point window `1400`, overlap `180`
- F-Coref max tokens per batch `3500`
- CPU-only PyTorch `2.3.1`
- Transformers `4.51.3`
- Python `3.10.21`
- Click `8.1.7`
- protobuf `5.29.6`

No candidate quality/configuration knob changed after the two prior environment-only failures.

## Technical result

All `5/5` attempted documents completed. Worker typecheck and all `33` deterministic worker tests passed in the same job.

Provider runtime:

- model download: `15.68 s`
- initialization: `5.39 s`
- provider wall clock: `34.94 s`
- peak RSS: `1,991.1 MiB`
- GPU / VRAM: none
- downloaded model artifacts: `1,337,560,935` bytes (approximately `1.25 GiB`)

The measured artifact set includes GLiNER's ~611 MB model and both safetensors and PyTorch weight files in the pinned F-Coref snapshot. This footprint is benchmark evidence, not an optimized production packaging claim.

## GLiNER typed-span result

Counts across the five documents:

- gold person mentions: `1,055`
- predicted person mentions: `158`
- exact correct person mentions: `112`
- gold proper-name person mentions: `137`
- predicted proper-name person mentions: `118`
- exact correct proper-name person mentions: `90`

Metrics:

- person-span precision: `0.7089`
- person-span recall: `0.1062`
- proper-person precision: `0.7627`
- proper-person recall: `0.6569`
- typed-span precision: `0.6579`
- typed-span recall: `0.1166`

Interpretation: at the fixed threshold, GLiNER is conservative over all person mentions but materially stronger on the proper-name subset that is relevant to S.A.G.A. canonical seeding. Five documents are insufficient to adopt or reject the front-door role; this must be measured over the full corpus and novel-diversity strata.

## F-Coref with oracle mentions

This experiment keeps LitBank gold mention boundaries/person typing and replaces only gold coreference cluster IDs with real F-Coref cluster evidence. It therefore isolates clustering/attachment behavior from NER.

Metrics:

- canonical precision: `0.7800`
- canonical recall: `0.8889`
- false-canonical rate: `0.0000`
- incorrect-merge rate: `0.1800`
- contaminated-canonical rate: `0.0600`
- fragmentation rate: `0.6111`
- linked-mention precision: `0.3805`
- linked-mention recall: `0.2192`
- non-person quarantine: `1.0000`
- cluster purity: `0.9111`

Semantic fingerprint:

`b0f27bad111da4eb87beec3c9d7ea98ba323daa54307a4f2c5813e161b528d24`

Interpretation: F-Coref shows useful attachment signal when mention boundaries/types are perfect, but the smoke still contains substantial incorrect merges and fragmentation. It is not safe to promote F-Coref clusters directly into canon.

## Fully real combined stack

Real GLiNER evidence and real F-Coref clusters were passed through S.A.G.A.'s unchanged resolver. F-Coref-only mentions remained supporting evidence and could not mint canonicals.

Metrics:

- canonical precision: `0.4118`
- canonical recall: `0.5000`
- false-canonical rate: `0.1569`
- incorrect-merge rate: `0.1569`
- contaminated-canonical rate: `0.5490`
- fragmentation rate: `0.4722`
- linked-mention precision: `0.0764`
- linked-mention recall: `0.0616`
- non-person quarantine: `1.0000`
- cluster purity: `0.8263`

Semantic fingerprint:

`ceea6c7ebc6fe40ecdc265cdb2918f6d709c7fb82265b8d6ca0d8770c2bfc952`

The combined configuration is **not production-acceptable from this smoke**. In particular, linked-mention precision is worse than the already-rejected BookNLP-small smoke and canonical contamination remains high.

## Promotion decision

Do **not** adopt the combined configuration.

Do continue to the full 100-document benchmark because the decomposed component results answer separate architectural questions that five documents cannot settle:

1. whether GLiNER proper-name/person admission is consistently useful across novel types;
2. whether F-Coref can be retained as narrowly constrained attachment evidence despite merge/fragmentation pressure;
3. whether the combined failure is systematic or concentrated in specific genres/forms;
4. whether either component warrants a different pairing later.

The full run must keep the exact candidate configuration fixed and report:

- aggregate GLiNER typed-span metrics;
- aggregate F-Coref oracle-mention identity metrics;
- aggregate combined identity metrics;
- all 17 novel-diversity strata for both typed spans and identity;
- full runtime/RAM/model footprint;
- semantic fingerprints for F-Coref and combined identity.

A second identical full run is required only if a component remains a viable adoption candidate after the first full-corpus result.
