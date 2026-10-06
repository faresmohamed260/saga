# 2026-10-06 — V3 Nominal Boundary-Correction Follow-up

Status: **MEASURED — held-out correction patterns improve candidate-span recall efficiently, but the tested lightweight classifier does not exploit the larger candidate set well enough to replace the exact noun-chunk challenger**

This follow-up tests the next hypothesis from `2026-10-06_V3_NOMINAL_DETECTION_SWEEP.md`: whether the structural boundary mismatches around spaCy noun chunks can be recovered with a small, book-held-out set of learned boundary corrections instead of brute-force nearby-span enumeration.

The task remains **nominal span detection only**. No score or threshold in this record is a character-identity merge/link probability.

## Fixed evaluation basis

LitBank:

- repository: `dbamman/litbank`
- commit: `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`
- annotation layer: `coref/tsv`
- documents: all `100`
- gold person nominals: `6,064`
- split: `5` document-held-out folds by sorted document index (`80` train books / `20` unseen test books per fold)
- license: CC BY 4.0

Syntax basis:

- spaCy `3.8.16`
- `en_core_web_sm 3.8.0`
- exact noun-chunk baseline candidates: `50,989`
- exact noun-chunk gold-span ceiling: `3,809 / 6,064 = 62.81%`

## 1. Train-book-only boundary corrections

For each held-out fold, the experiment learns the most frequent boundary deltas between a gold person nominal and its nearest overlapping noun chunk **from the 80 training books only**. The correction set is then applied to the 20 unseen books.

The exact noun chunk `(0, 0)` remains available in every profile; the profile size below counts additional non-exact corrections.

Qualification provenance:

- workflow run: `37493097805`
- qualification head: `fa2b9d9ea4104da4bb8d084b5297318ed321b2e4`
- artifact ID: `11426516238`
- artifact digest: `sha256:a0ed7f6cbf5c6532e42626696f76fd9d9a2d96e4201a21a9fb1ad541d73e778f`
- runtime: `36.69 s`

### Candidate coverage

| Learned non-exact corrections | Candidates | × noun chunks | Exact matches | Exact recall ceiling |
|---:|---:|---:|---:|---:|
| 4 | 190,308 | 3.73× | 4,417 | **72.84%** |
| 8 | 318,366 | 6.24× | 4,733 | **78.05%** |
| 16 | 523,803 | 10.27× | 4,983 | **82.17%** |
| 32 | 848,176 | 16.63× | 5,169 | **85.24%** |

The correction patterns generalize consistently enough to raise the held-out boundary ceiling. Frequent non-exact patterns include right extensions such as `(0, +2)` / `(0, +3)` and left extensions such as `(-3, 0)`.

### Comparison with brute-force expansion

The earlier brute `±3 / max-10` candidate generator produced:

- `606,334` candidates;
- `77.84%` exact-span ceiling.

The held-out **top-8 correction set** reaches a slightly higher ceiling (`78.05%`) with only `318,366` candidates—roughly half the brute-force candidate volume.

Decision at this stage: learned correction patterns are a **materially better candidate generator than indiscriminate sliding expansion**. That alone does not prove they are a better final nominal detector.

## 2. Corrected-span lightweight classifier

The next experiment applies the same held-out correction discipline and trains a lightweight hashed linear classifier separately for the top-4 and top-8 candidate profiles.

Classifier:

- `SGDClassifier(loss=log_loss, alpha=1e-5, class_weight=balanced)`;
- hashed lexical/syntax/span-geometry features;
- correction delta/rank/frequency features;
- training and correction discovery both restricted to the 80 training books in each fold;
- test scoring only on the 20 unseen books.

Qualification provenance:

- workflow run: `37493593246`
- qualification head: `235cf6b76295e2a2d342bc6542e1dbc23bab7229`
- artifact ID: `11426403088`
- artifact digest: `sha256:5d462aadfe2020b035934b6b7c9b4ca01405a06c36271582ed947aa727b7050d`
- runtime: `90.91 s`

### Ranking comparison

| Candidate/classifier path | Candidate ceiling | OOF AP | ROC AUC | Best measured F1 |
|---|---:|---:|---:|---:|
| exact noun chunks + linear classifier | 62.81% | **0.8115** | 0.9720 | **0.6039** |
| top-4 corrections + hashed linear | 72.84% | 0.6482 | 0.9766 | 0.5575 |
| top-8 corrections + hashed linear | **78.05%** | 0.5322 | 0.9762 | 0.5060 |

The corrected profiles have high ROC AUC but substantially worse average precision because the added overlapping spans create a much harder and more imbalanced ranking problem.

### Top-4 operating points

| Threshold | Precision | Full-corpus recall | F1 |
|---:|---:|---:|---:|
| 0.50 | 0.3929 | **0.6064** | 0.4768 |
| 0.70 | 0.4840 | 0.5782 | 0.5269 |
| 0.85 | 0.5777 | 0.5356 | 0.5559 |
| 0.95 | **0.6854** | 0.4509 | 0.5439 |

Top-ranked slices:

| Top K | Precision | Full-corpus recall | F1 |
|---:|---:|---:|---:|
| 2,000 | **0.8000** | 0.2639 | 0.3968 |
| 3,000 | 0.7480 | 0.3701 | 0.4951 |
| 4,000 | 0.6853 | 0.4520 | 0.5447 |
| 5,000 | 0.6168 | **0.5086** | **0.5575** |

### Top-8 operating points

| Threshold | Precision | Full-corpus recall | F1 |
|---:|---:|---:|---:|
| 0.50 | 0.2469 | **0.6671** | 0.3604 |
| 0.70 | 0.3116 | 0.6323 | 0.4174 |
| 0.85 | 0.3895 | 0.5876 | 0.4685 |
| 0.95 | **0.5047** | 0.5074 | **0.5060** |

Top-ranked slices:

| Top K | Precision | Full-corpus recall | F1 |
|---:|---:|---:|---:|
| 2,000 | **0.7030** | 0.2319 | 0.3487 |
| 3,000 | 0.6537 | 0.3234 | 0.4327 |
| 4,000 | 0.6058 | 0.3996 | 0.4815 |
| 5,000 | 0.5524 | **0.4555** | **0.4993** |

## Decision

**Do not promote either corrected-span linear classifier.**

The exact-noun-chunk + lightweight linear classifier remains the leading simple public nominal challenger because it preserves a materially better precision/ranking curve:

- AP `0.8115` vs `0.6482` top-4 and `0.5322` top-8;
- best measured F1 `0.6039` vs `0.5575` and `0.5060`;
- only `50,989` candidate spans instead of `190,308` or `318,366`.

At the same time, **do not discard the learned correction generator**. The top-8 held-out correction set demonstrates that structural candidate generation can raise the boundary ceiling to `78.05%` more efficiently than brute-force expansion. It is useful evidence for a stronger span-specific model.

The correct interpretation is therefore:

```text
boundary correction patterns: useful candidate evidence
current linear classifier over corrected candidates: rejected
exact noun-chunk linear classifier: still leading lightweight baseline
```

## Architecture consequence

The nominal path should not accumulate more lexical/linear ranking heuristics over increasingly large overlapping candidate pools. That family is showing diminishing returns: more candidate recall is being converted into worse average precision rather than better supported coverage.

The next challenger should learn **span structure directly**, using the existing local/open spaCy boundary if possible before escalating to a larger encoder.

Preferred next test:

1. a S.A.G.A.-owned spaCy `SpanCategorizer` / equivalent compact span-classification experiment under 5-fold book-held-out evaluation;
2. compare direct span exact P/R/F1, high-precision supported coverage, candidate volume, wall time, RAM, and artifact size against the exact noun-chunk baseline;
3. if that fails materially, escalate to a compact encoder span/boundary classifier (e.g. the already-proposed ModernBERT class of challenger), not another rule-window sweep.

The learned top-4/top-8 correction sets may be used as **measured candidate suggesters** inside that experiment, but should not be treated as production rules.

## Adoption boundary

No production nominal provider or identity threshold is adopted here.

Public LitBank results remain component evidence only. Promotion still requires representative protected contemporary-fiction qualification plus normal V3 end-to-end identity contamination/merge/abstention gates.
