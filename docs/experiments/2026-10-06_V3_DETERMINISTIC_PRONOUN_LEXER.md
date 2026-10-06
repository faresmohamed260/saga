# 2026-10-06 — V3 Deterministic Character-Pronoun Lexer

Status: **MEASURED — `plus_plural` supported as the leading English pronoun-span provider**

The GLiNER2.5 calibration showed that semantic prompting is unnecessary and weak for pronoun span discovery. This experiment tests whether a closed lexical class can detect English character-pronoun mentions cheaply while leaving identity resolution to the separate V3 retrieval/ranking pipeline.

## Fixed basis

LitBank:

- repository: `dbamman/litbank`
- commit: `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`
- annotation layer: `coref/tsv`
- documents: all `100`
- gold person-pronoun mentions: `15,451`
- license: CC BY 4.0

Provider:

- model-free regex/token scan
- case-insensitive closed pronoun lexicon
- no confidence score emitted
- every emitted mention is tagged `mention_kind=pronoun`
- identity/link selection is explicitly out of scope

## Profiles

`strict` includes first/second-person and singular gendered personal/possessive/reflexive forms (`I`, `me`, `we`, `you`, `he`, `she`, `her`, `his`, etc.).

`plus_plural` adds the `they/them/their/theirs/themself/themselves` family.

`plus_neuter` additionally adds `it/its/itself`.

## Provenance

Workflow run: `37485794243`

Artifact:

- ID: `11423306574`
- digest: `sha256:b9de9ef783efcf8c6369c6148d487ce2dc94cd92341b29faf83e1dd265fff481`
- qualification head: `fddd74c13643e378c3ba083bf38e79f6123ed7ef`

The reported precision below is exact-span precision against **gold person-pronoun mentions only**.

## Results

| Profile | Precision | Recall | F1 | Predicted | Gold | True positive | Runtime |
|---|---:|---:|---:|---:|---:|---:|---:|
| `strict` | **0.9827** | 0.9227 | 0.9518 | 14,508 | 15,451 | 14,257 | 0.202 s |
| `plus_plural` | 0.9601 | **0.9952** | **0.9773** | 16,016 | 15,451 | **15,377** | 0.209 s |
| `plus_neuter` | 0.8408 | 0.9970 | 0.9123 | 18,322 | 15,451 | 15,405 | 0.239 s |

## Interpretation

`plus_plural` gives the best operating point for S.A.G.A.:

- it recovers `15,377 / 15,451` gold person pronouns (`99.52%` recall);
- exact pronoun precision remains `96.01%`;
- F1 is `97.73%`;
- the entire 100-document corpus is scanned in about `0.21 s` on the hosted CPU runner;
- no model weights, network call, or probabilistic threshold are required.

Adding neuter `it/its/itself` is not justified as a default character-pronoun rule. It recovers only `28` additional gold pronouns while increasing predictions by `2,306`, dropping precision from `96.01%` to `84.08%` and F1 from `97.73%` to `91.23%`.

The `strict` profile is very precise (`98.27%`) but unnecessarily loses `1,120` true plural pronouns relative to `plus_plural`.

## Decision

For English narrative text, adopt `plus_plural` as the leading deterministic **pronoun-span detection** provider.

This does **not** mean every detected token should be linked to a character. The provider only marks candidate pronoun spans. V3's hybrid candidate retrieval, pronoun-specific Ettin routing, and future merge/abstain policy remain responsible for identity adjudication.

Recommended mention architecture:

`explicit-name provider` + `supplemental GLiNER mixed-reference provider` + **deterministic plus_plural pronoun provider** + `future nominal provider` → composite grounded-span union → hybrid identity retrieval → mention-kind-aware ranking → conservative merge / abstain.

`it/its/itself` should remain excluded by default and may later be handled by a contextual challenger if creature/non-human character coverage requires it.
