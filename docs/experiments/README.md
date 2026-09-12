# S.A.G.A. Analysis Experiment Ledger

This directory is the durable record for analysis-provider/model experiments used to make production architecture decisions.

The rule is simple: **results decide; preference does not**.

## Why this exists

S.A.G.A. is expected to remain understandable months after an experiment was run. Successful, failed, rejected, and deferred candidates all provide useful evidence. Future sessions must be able to answer:

- what was tested;
- on which exact source/dataset revision;
- with which model/provider/revision/configuration;
- on what hardware;
- what quality was measured;
- how long it took and how much RAM/VRAM/model storage it used;
- whether reruns were stable;
- what failed or degraded;
- what candidate it was compared with;
- why it was adopted, rejected, or deferred.

Do not delete negative results merely because a candidate lost. They prevent repeated dead ends and document the trade-offs behind the production stack.

## Two evidence classes are required

A production candidate needs both.

### 1. Quality evidence

Use task-appropriate gold/annotated corpora or carefully versioned product fixtures. Examples include LitBank identity/coreference evidence, speaker-attribution truth sets, event/participant annotations, and adversarial contamination cases.

Measure product-level behavior, not only upstream model scores. For identity this includes S.A.G.A. resolver outcomes such as false canonicals, incorrect merges, fragmentation, mention precision/recall, contamination, and non-person quarantine.

### 2. Operational evidence

Run representative complete-book workloads and record at minimum:

- source SHA-256 and size;
- exact S.A.G.A. commit;
- provider/model/package revision;
- configuration fingerprint;
- hardware and execution mode;
- wall-clock time;
- peak resident RAM;
- peak VRAM when relevant;
- model artifact/download size;
- license;
- output counts;
- rerun fingerprints/failures.

A strong score on a short benchmark does not prove that a candidate is practical for full novels. A fast whole-book run does not prove that its output is reliable enough for canon.

## Production adoption rule

A candidate may become a production default only after:

1. repeatable quality evidence exists;
2. representative whole-book operational evidence exists;
3. known failure modes are documented;
4. license/redistribution/use constraints are understood;
5. downstream S.A.G.A. behavior is compared with the current baseline/challengers;
6. the decision rationale is committed to the repository.

There is no universal rule that the smallest or fastest model wins. Reliability and consistency are the primary product constraints. Resource cost is optimized **subject to** meeting the required quality and operational reliability.

If a larger or slower local model materially improves correctness or eliminates dangerous failure modes, the experiment record should say so and the production decision may legitimately choose it.

## Machine-readable record

`services/analysis-worker/src/evaluation/experiment-record.ts` defines `saga-analysis-experiment-v1`.

Each durable record includes:

- candidate identity, implementation, license and source;
- the benchmark/resource manifest;
- one or more quality datasets and metric maps;
- attempted/completed run counts;
- output fingerprints and derived repeatability;
- failure codes;
- decision status (`candidate`, `adopted`, `rejected`, `deferred`);
- comparison targets, limitations and notes;
- deterministic record fingerprint.

The schema intentionally stores metric names as an extensible map because identity, dialogue, events and later narrative reasoning need different quality measures. Phase-specific validation documents must still define what each metric means.

## File convention

Use one Markdown summary plus machine-readable JSON artifacts when a real benchmark is completed.

Recommended naming:

```text
docs/experiments/
  YYYY-MM-DD_<capability>_<candidate>.md
analysis-artifacts/
  experiments/<experiment-id>.json
```

Large/raw model outputs should not be committed merely to prove an experiment. Store bounded result artifacts or workflow artifacts and record immutable digests/links where appropriate.

## Current Phase 3A candidates

These are challengers, not selections:

- BookNLP small — broad literary baseline for entities, coreference, quote speakers, syntax and event triggers;
- GLiNER small — configurable typed-span challenger;
- F-Coref — lightweight coreference challenger;
- LingMess — evaluate only if cheaper candidates leave a meaningful quality gap;
- small local structured-reasoning models — later bounded escalation experiments only.

The experiment ledger, not this candidate list, determines what ultimately becomes production architecture.
