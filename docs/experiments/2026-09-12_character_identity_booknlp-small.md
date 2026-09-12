# 2026-09-12 — Character Identity Candidate: BookNLP Small

Status: **CANDIDATE — primary identity role currently unsupported by results**

Capability under test: character/entity evidence, coreference attachment, quote-speaker evidence, literary event triggers.

This record preserves successful and failed attempts. BookNLP is not a production dependency merely because it is benchmarked.

## Fixed comparison basis

LitBank:

- repository: `dbamman/litbank`
- commit: `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`
- identity gold: `coref/tsv`
- license: CC BY 4.0

S.A.G.A. oracle-evidence policy baseline over all 100 documents:

- canonical precision: `0.9516`
- canonical recall: `0.9970`
- incorrect-merge rate: `0.0000`
- fragmentation rate: `0.1422`
- linked-mention precision: `0.9942`
- non-person quarantine rate: `1.0000`

The oracle baseline isolates S.A.G.A.'s resolver policy from real-provider recall/error.

## Candidate provenance

Official BookNLP base:

- repository: `booknlp/booknlp`
- base commit: `3d900fc2224e55960c3363826ae28539b77b4204`
- package metadata version: `1.0.7`
- code license: MIT

Compatibility patch used for successful experiments:

- upstream open PR: `booknlp/booknlp#25`
- exact compatibility commit: `8875a1b616d764b7d13d1e30e9949cc21ca303c1`

Model-weight license: **unverified**. The official code repository downloads the Berkeley model files but S.A.G.A. has not verified an authoritative separate model-weight license. This remains an adoption blocker.

## Experiment 1 — official base with unconstrained 2026 dependencies

Run: `34699510439`
S.A.G.A. head: `30feff55b8da5c44b4f14aab7c4fc9a6717601a4`

Result: **FAILED before inference**.

The environment resolved BookNLP `1.0.7`, spaCy `3.8.16`, PyTorch `2.14.0`, TensorFlow `2.21.0`, and Transformers `5.17.0`, then failed loading the old BookNLP state dictionary:

```text
Unexpected key(s) in state_dict: "bert.embeddings.position_ids".
```

Operationally, unconstrained installation also downloaded multiple large CUDA/TensorFlow/PyTorch artifacts on a CPU runner. This configuration is retained as a negative result and is not a credible production install strategy.

## Experiment 2 — compatibility patch + CPU-bounded environment

Run: `34699861942`
S.A.G.A. head: `068734bbe05511ee6146bd0c5c3cf12cced53c80`

Pinned CPU-only PyTorch and bounded NLP dependencies avoided the dependency explosion. The attempt then failed during environment setup because spaCy's CLI dependency `click` was absent.

Classification: **benchmark-environment configuration failure**, not provider-quality evidence.

## Experiment 3 — 5-document successful smoke

Run: `34699944924`
S.A.G.A. head: `b961a06f65c61a43828971b8d642f8ec51514124`

Artifact:

- ID `10299318866`
- digest `sha256:1dd92ea2d03f2abc8ed1dd2ad054e715f2bbaf37309e033c125d0b26ddc22e69`

Environment:

- Python `3.10.21`
- PyTorch `2.3.1+cpu`
- Click `8.1.7`
- spaCy `3.7.5`
- Transformers `4.43.4`
- no TensorFlow
- BookNLP `small`

Quality:

- canonical precision `0.3115`
- canonical recall `0.4722`
- incorrect-merge rate `0.1639`
- contaminated-canonical rate `0.6230`
- fragmentation rate `0.4167`
- linked-mention precision `0.2508`
- linked-mention recall `0.1359`
- non-person quarantine rate `0.9583`
- cluster purity `0.8510`

Resources:

- initialization `15.57 s`
- total 5-document wall clock `32.78 s`
- peak RAM `883.6 MiB`
- GPU/VRAM none
- model artifacts `160,398,571 bytes` (~153 MiB)

Smoke fingerprint:

- `fa96751cbdb4d45e99e758187c83bdccd57eaee37fdae8ca1ec9fc796b188a5a`

Interpretation: operational footprint is attractive; identity quality is not.

## Experiment 4 — full 100-document LitBank

Run: `34700149009`
S.A.G.A. head: `f4a264a33735741e518d3b44cb6f34a4e119715d`

Artifact:

- ID `10299538833`
- digest `sha256:5f2f7110244226a27b3d3de32b3064f3086a1e8f93cc82d7dcf962f3ec4a0838`

All `100/100` documents completed with zero provider/evaluator failures.

Counts:

- gold seed-eligible characters: `675`
- predicted canonicals: `1060`
- pure canonicals: `489`
- false canonicals: `280`
- incorrect merges: `205`
- contaminated canonicals: `424`
- represented gold characters: `407`
- fragmentation excess: `311`
- relevant gold mentions: `13,932`
- predicted mentions: `28,640`
- correct linked mentions: `1,618`
- linked mentions: `7,496`

Quality:

- canonical precision: `0.4613`
- canonical recall: `0.6030`
- false-canonical rate: `0.2642`
- incorrect-merge rate: `0.1934`
- contaminated-canonical rate: `0.4000`
- fragmentation rate: `0.4607`
- linked-mention precision: `0.2158`
- linked-mention recall: `0.1161`
- unresolved relevant mention rate: `0.4985`
- quarantined relevant mention rate: `0.0030`
- non-person quarantine rate: `0.9415`
- cluster purity: `0.8667`

Resources:

- initialization: `11.67 s`
- total wall clock: `420.21 s`
- runner logical CPUs: `4`
- peak resident memory: `1,164.5 MiB`
- GPU/VRAM: none
- model artifacts: `160,398,571 bytes`

Full-corpus semantic output fingerprint:

- `01e78b6b539fbe0e8529e38bb61b1d17fb7734126218b507cb1da5014d3d0413`

### Current conclusion

The 100-document result confirms the smoke warning. BookNLP-small is **not supported as S.A.G.A.'s primary character-identity provider** in the measured configuration. The key blockers are low canonical/mention precision, substantial incorrect merges/contamination, and high fragmentation.

This is not a package-wide rejection. BookNLP's quote/speaker, event, syntax, or auxiliary mention evidence remain candidates for separate task-specific experiments.

The next identical full run is used for repeatability and for the new novel-diversity strata. If its semantic fingerprint differs, that instability becomes additional negative evidence.

## Diversity requirement

Future interpretation must use `docs/experiments/NOVEL_DIVERSITY_MATRIX.md` and the machine-readable LitBank strata. Aggregate scores alone are no longer sufficient.

BookNLP and every challenger must be inspected across genre/form/cast stressors, and later on complete novels plus a private contemporary-fiction suite.

## Decision rule

No provider is adopted from reputation, published benchmark scores, one successful run, or resource efficiency alone.

Before adoption S.A.G.A. requires:

1. real quality results on pinned gold literary evaluation;
2. stratified novel-type results;
3. complete-book runtime/RAM/VRAM/model-size evidence;
4. at least two completed repeatability runs;
5. failure-mode documentation;
6. direct challenger comparison;
7. acceptable operational maintainability;
8. verified code/model licensing for runtime artifacts.

A larger/slower candidate may win if it is materially more reliable. A lightweight candidate is rejected or narrowed if its downstream correctness is not production-grade.
