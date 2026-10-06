# 2026-10-06 — V3 Character-Nominal Detection Sweep

Status: **MEASURED — exact spaCy noun chunks + book-held-out linear classification lead the tested nominal challengers; no production nominal provider adopted**

This record closes the first V3.0 character-nominal detection sweep after the GLiNER2.5 reference-label experiments showed that prompt/label changes did not provide useful nominal recall.

The goal is deliberately narrower than character identity: detect source-grounded nominal character-reference spans such as `the doctor`, `my mother`, or `the old man`. Canonical identity attachment remains a later linker decision.

## Fixed public evaluation basis

LitBank:

- repository: `dbamman/litbank`
- commit: `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`
- annotation layer: `coref/tsv`
- documents: all `100`
- person nominal mentions: `6,064`
- license: CC BY 4.0

This is public regression/qualification evidence only. LitBank is not a substitute for the protected contemporary-fiction product suite, and no result in this record promotes a production provider.

## Executive decision

The leading measured first-wave nominal challenger is:

```text
spaCy en_core_web_sm noun chunks
    -> lightweight span/person classifier
    -> nominal candidate evidence only
```

The strongest tested classification result uses exact spaCy noun chunks plus a book-held-out linear classifier. It achieves out-of-fold average precision `0.8115` and ROC AUC `0.9720`; at a fixed `0.85` benchmark threshold it yields `80.90%` precision and `46.03%` recall against all gold person nominals.

This configuration is **not production adopted** because:

1. exact noun-chunk boundaries cap public-corpus recall at `62.81%`;
2. no tested operating point approaches the V3 product-level `>=97%` precision preference;
3. the classifier is trained/evaluated within LitBank, albeit with book-held-out folds;
4. representative private modern-fiction qualification is unavailable in this execution environment;
5. a stable trained artifact, resource envelope, and deployment dependency decision have not been qualified.

The sweep also rejects two tempting shortcuts:

- WordNet person-head filtering is too weak as a standalone detector;
- brute-force boundary expansion raises theoretical recall but materially worsens ranking quality and candidate volume.

## 1. What LitBank person nominals look like

Qualification:

- workflow run: `37486871211`
- qualification head: `7d6f3261b1e015a5dd15f4020238cbcf419babb6`
- artifact ID: `11423352792`
- artifact digest: `sha256:65d47e213a0a91696a1355985b9e526a83e4c782db64eac853838c29635b1088`

Corpus shape:

- determiner-started: `3,092 / 6,064` = `50.99%`;
- possessive-started: `1,095 / 6,064` = `18.06%`;
- initial-capital: `866 / 6,064` = `14.28%`;
- single-token: `795 / 6,064` = `13.11%`;
- one-to-three-token mentions: `4,399 / 6,064` = `72.54%`.

Frequent heads include `man`, `mother`, `father`, `men`, `boy`, `people`, `woman`, `child`, `wife`, `family`, and `girl`.

Interpretation: nominal discovery is primarily a noun-phrase/span-classification problem, not a good reason to introduce a whole-book generative extractor.

## 2. spaCy noun-chunk boundary coverage

Provider qualification:

- spaCy: `3.8.16`
- model: `en_core_web_sm`
- model revision/version: `3.8.0`
- workflow run: `37487358770`
- qualification head: `f92e06c845bf9cd52a950a67a3f28215b9bed88d`
- artifact ID: `11424316625`
- artifact digest: `sha256:d6682bd840839336209feedc97eaf93ea1a16057ba4bc007cbf5a1fdb1cee68f`

Results over all 100 documents:

| Metric | Result |
|---|---:|
| Gold person nominals | 6,064 |
| noun-chunk candidates | 50,989 |
| exact matches | 3,809 |
| exact boundary recall | **0.6281** |
| gold contained by a chunk | 4,308 |
| containment coverage | 0.7104 |
| any-overlap gold mentions | 5,730 |
| overlap coverage | **0.9449** |
| runtime | 15.79 s |

Exact recall is strongest on the common short forms:

| Gold length | Exact recall |
|---|---:|
| 1 token | 0.6667 |
| 2 tokens | **0.8253** |
| 3 tokens | **0.8096** |
| 4+ tokens | 0.1928 |

Possessive-started nominals are especially compatible with noun chunks (`0.7991` exact recall).

Decision: spaCy noun chunks are useful **candidate spans**, but cannot be treated as the complete nominal detector.

## 3. WordNet semantic-head filter — rejected standalone detector

Qualification:

- spaCy `3.8.16` + `en_core_web_sm 3.8.0`
- NLTK `3.10.3` / WordNet 3.0
- workflow run: `37487799927`
- qualification head: `dcb16f08e663e195b0d6d0689dd9a2ee69d0ce19`
- artifact ID: `11424580407`
- artifact digest: `sha256:a06ca5a9ac8e98246b439427221a3034d661bcaead1da2d28924a0c806a5bf87`

| Filter | Precision | Recall | F1 | Predicted | TP |
|---|---:|---:|---:|---:|---:|
| `person_first_sense` | 0.5817 | 0.5094 | **0.5432** | 5,310 | 3,089 |
| `person_any_sense` | 0.3304 | 0.5391 | 0.4097 | 9,893 | 3,269 |
| `person_majority_senses` | **0.6055** | 0.4733 | 0.5313 | 4,740 | 2,870 |
| `person_or_group_any_sense` | 0.2395 | **0.5735** | 0.3379 | 14,524 | 3,478 |

Decision: reject WordNet synset membership as a standalone nominal provider. Its precision/recall tradeoff is not competitive enough to justify semantic-sense tuning. WordNet-like information may still be useful as one feature in a later classifier.

## 4. Book-held-out linear noun-chunk classifier — leading challenger

Qualification design:

- candidate spans: exact spaCy noun chunks;
- `5` document-held-out folds by sorted document index;
- each fold: `80` train books / `20` unseen test books;
- classifier: `LogisticRegression(C=1, class_weight=balanced, solver=liblinear)`;
- features: head/edge lemmas, POS/tag/dependency, noun-chunk length/start shape, and local lexical/POS context;
- spaCy `3.8.16` / `en_core_web_sm 3.8.0`;
- scikit-learn `1.7.2`.

Provenance:

- workflow run: `37490018077`
- qualification head: `00ef994cd46415a3e11a4619371870e0d56d2e02`
- artifact ID: `11425485991`
- artifact digest: `sha256:b89030b0395388f50367fc582f7312e26fd3f8afdc4a01f16ac53ff120416019`

Ranking quality:

- out-of-fold average precision: **`0.8115`**;
- out-of-fold ROC AUC: **`0.9720`**;
- exact-span candidate ceiling: `3,809 / 6,064 = 0.6281` full-corpus recall;
- runtime: about `28.84 s` for the full 100-document benchmark on the hosted CPU runner.

Fixed benchmark operating points:

| Threshold | Precision | Full-corpus recall | F1 | Predicted | TP | FP |
|---:|---:|---:|---:|---:|---:|---:|
| 0.50 | 0.6559 | 0.5407 | 0.5928 | 4,999 | 3,279 | 1,720 |
| 0.70 | 0.7380 | **0.5110** | **0.6039** | 4,199 | 3,099 | 1,100 |
| 0.85 | **0.8090** | 0.4603 | 0.5867 | 3,450 | 2,791 | 659 |
| 0.95 | **0.8725** | 0.3452 | 0.4946 | 2,399 | 2,093 | 306 |

Interpretation:

- literary person-vs-non-person nominal signal is learnable with cheap local features;
- the held-out design is materially stronger evidence than a fitted in-sample lexicon;
- classification quality is no longer the first bottleneck—the noun-chunk span ceiling is;
- benchmark thresholds are **not** canonical-link/identity probabilities and are not production merge thresholds.

Current status: **leading public nominal-span challenger, not production provider**.

## 5. Brute-force head-anchored boundary expansion — higher ceiling, worse usable ranking

A candidate-generation sweep expanded contiguous spans around spaCy noun-chunk heads.

Provenance:

- workflow run: `37490454562`
- qualification head: `35f01d16eea6d39c4add8bd050feb0b5e6b77538`
- artifact ID: `11425426832`
- artifact digest: `sha256:8048cb4a49302e3dfa5fc3130d2f6a922bb19f1eaf5ec8da2d41ba70d46f73e1`

| Candidate profile | Candidates | × noun chunks | Exact recall ceiling |
|---|---:|---:|---:|
| exact noun chunks | 50,989 | 1.00× | 0.6281 |
| root subspans, max 6 | 90,690 | 1.78× | 0.6504 |
| ±1 window, max 6 | 212,957 | 4.18× | 0.6605 |
| ±2 window, max 8 | 400,022 | 7.85× | 0.7183 |
| ±3 window, max 10 | 606,334 | **11.89×** | **0.7784** |

The largest profile recovers short/medium gold spans well (`91.54%` for 3-token and `92.70%` for 4–5-token nominals), but candidate volume becomes extreme.

### Expanded-span held-out classifier

The `root_window3_10` candidate pool was then tested with a separate 5-fold book-held-out hashed linear classifier.

Provenance:

- workflow run: `37490991547`
- qualification head: `177d2d8170a6021d268d447c8210d2c5783b9964`
- artifact ID: `11425353071`
- artifact digest: `sha256:378be8e62a6349657e53f02fec2443cf2199c67581e3456c60bf09627a2eb146`

Results:

- candidates: `606,334`;
- exact-boundary upper-bound recall: `0.7784`;
- out-of-fold average precision: **`0.5985`**;
- ROC AUC: `0.9868`;
- runtime: `78.39 s`.

Fixed thresholds:

| Threshold | Precision | Full-corpus recall | F1 |
|---:|---:|---:|---:|
| 0.50 | 0.2479 | 0.6680 | 0.3616 |
| 0.70 | 0.3266 | 0.6377 | 0.4320 |
| 0.85 | 0.4221 | 0.6008 | 0.4958 |
| 0.95 | 0.5552 | 0.5214 | **0.5378** |

Ranking-only operating points are also weaker than the simple noun-chunk classifier: the top `2,000` expanded predictions reach `77.65%` precision but only `25.61%` full-corpus recall.

Decision: **reject brute-force span expansion**. The higher candidate recall creates too many overlapping hard negatives, materially reducing average precision and usable precision/recall while increasing runtime and candidate volume.

## 6. Boundary mismatch geometry

Qualification:

- workflow run: `37491907527`
- qualification head: `1b607e14b98ad413334aa4cbe6833eaec87b216b`
- artifact ID: `11426121380`
- artifact digest: `sha256:4131f586b14b9f75d9acb30b73836958fb7f5c1616507e03e82240a4c9798aaf`

Of the `2,255` person nominals that are not exact spaCy noun chunks:

| Relation to nearest noun chunk | Count |
|---|---:|
| gold contains noun chunk | **1,390** |
| noun chunk contains gold | 499 |
| no overlap | 334 |
| partial overlap | 32 |

All `2,255` misses are token-aligned. Their boundary differences are not predominantly tiny noise:

| Symmetric bound around nearest chunk | Misses covered |
|---|---:|
| ±1 token | 214 / 2,255 = **9.49%** |
| ±2 tokens | 848 / 2,255 = **37.61%** |
| ±3 tokens | 1,323 / 2,255 = **58.67%** |
| ±4 tokens | 1,553 / 2,255 = 68.87% |
| ±5 tokens | 1,730 / 2,255 = 76.72% |

Common mismatch shapes are one-sided, for example:

- same start, gold ends 2 tokens before the chunk: `241` cases;
- same start, gold extends 6+ tokens beyond the chunk: `197` cases;
- same start, gold extends 2 tokens beyond the chunk: `182` cases;
- gold starts 3 tokens before the chunk, same end: `154` cases;
- same start, gold extends 3 tokens beyond the chunk: `148` cases.

Interpretation: the remaining problem is not well modeled as a tiny global trim/expand rule. The next boundary challenger should learn or derive syntactic span structure rather than enumerate every nearby contiguous span.

## 7. Decision matrix

| Approach | Decision | Reason |
|---|---|---|
| GLiNER2.5 nominal prompt labels | **Rejected for nominal discovery** | Earlier measured nominal recall remained extremely low; label tuning did not solve the class. |
| spaCy noun chunks | **Retain as candidate boundary source** | Cheap, strong on common 2–3 token forms, 62.81% exact ceiling, 94.49% overlap coverage. |
| WordNet person-head filtering | **Reject standalone** | Best F1 only 0.5432; no useful precision/recall operating point. |
| exact noun chunk + held-out linear classifier | **Leading challenger** | AP 0.8115 / AUC 0.9720 with strong cheap discriminative signal. |
| brute-force ±3/max-10 span expansion | **Reject** | 11.9× candidates, AP falls to 0.5985, worse practical curve and runtime. |
| learned/syntactic span-boundary model | **Next challenger** | Failure geometry indicates structural one-sided and long-range boundary differences. |

## 8. Architecture consequence

The V3 mention architecture remains compositional:

```text
explicit-name provider
    + deterministic plus_plural pronoun provider
    + supplemental GLiNER reference evidence
    + nominal candidate provider/challenger
        -> CompositeSemanticLexer
        -> identity candidate retrieval
        -> mention-kind-aware learned ranking
        -> conservative attach / merge / unresolved policy
```

Nominal span classification does not establish character identity. A surface such as `the doctor` may be a valid character-reference candidate while still remaining unresolved until the global linker has sufficient evidence.

## 9. Next experiment

Do **not** continue tuning WordNet senses or wider lexical span windows.

The next nominal-boundary experiment should compare a learned or syntax-aware span model against the exact-noun-chunk baseline, for example:

- a small S.A.G.A.-owned span classifier / spaCy SpanCategorizer-style challenger;
- a compact encoder boundary classifier if the lighter span model cannot materially improve supported coverage;
- dependency/constituency-derived candidate spans only if they reduce candidate explosion and are independently measured.

Evaluation must remain book-held-out and should report:

- exact nominal span precision/recall/F1;
- supported coverage at high precision;
- candidate volume;
- wall time / peak RAM / VRAM where applicable;
- model/dependency/license provenance;
- private-fiction generalization when the protected corpus is available.

## 10. Adoption boundary

No nominal model/provider is production-adopted by this sweep.

The current public evidence supports only these narrower conclusions:

1. deterministic lexical pronoun detection can remain separate from nominal detection;
2. nominal person classification is feasible with small local discriminative models;
3. exact noun-chunk boundary recall is the current leading challenger's main public bottleneck;
4. indiscriminate boundary expansion is counterproductive;
5. the next improvement should target **span structure**, not a larger generative model.

Production promotion remains blocked on representative protected-fiction qualification and the normal V3 end-to-end identity safety gates.
