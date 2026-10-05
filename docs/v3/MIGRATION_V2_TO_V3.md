# S.A.G.A. v2 -> v3 Migration Strategy

Status: **DRAFT — SHADOW MIGRATION**

The reboot must not replace the current analysis system in one cutover. v3 is introduced as a parallel compiler and promoted stage-by-stage only after measured qualification.

## 1. Branching/freeze

Frozen v2 baseline:

- branch: `archive/v2-analysis-baseline-2026-10-05`
- commit: `e9d24d54d351f9bf7c1cfa582a01db819efdb2fe`

v3 preparation:

- branch: `v3/reboot-preparation`

`main` remains the production/development integration line until a qualified v3 migration PR exists.

## 2. Shadow architecture

During qualification:

```text
uploaded source
     |
     +------> v2 analysis ------> v2 artifacts
     |
     +------> v3 compiler ------> v3 Narrative IR
                                 |
                                 v
                         comparison reports
```

v3 outputs do not replace user-visible canonical results during early qualification.

## 3. Migration units

Promote capabilities independently where dependencies allow.

Suggested order:

1. source/Narrative IR contracts;
2. semantic mention/entity candidate layer;
3. global character linker;
4. dialogue/speaker attribution;
5. scene segmentation;
6. event mentions/participants;
7. event coreference;
8. attributes/relationships/state observations;
9. temporal constraints/solver;
10. causality;
11. derived graph/retrieval/generative views.

## 4. Compatibility boundary

During migration, v3 should expose adapters capable of producing temporary v2-compatible views where necessary for the existing frontend/API.

Do not distort Narrative IR to mimic v2 tables. Compatibility belongs in an adapter/projection layer.

## 5. Data migration

Existing v2 analysis runs remain immutable historical artifacts.

Do not bulk-convert old semantic results into v3 canonical facts without source re-evaluation.

Where useful, import v2 results as explicitly tagged candidate evidence:

- producer = `saga-v2-import`;
- architecture version = frozen v2 version;
- acceptance status = candidate/unverified unless requalified.

## 6. Neo4j migration

If current graph data contains information not independently represented in canonical storage:

1. inventory it;
2. identify reconstructible vs non-reconstructible information;
3. export any required historical evidence;
4. build a v3 projection generator from Postgres Narrative IR;
5. verify graph-equivalent product queries;
6. only then stop treating old graph state as authoritative.

## 7. Frontend/API migration

Product surfaces should migrate to stable semantic API contracts rather than direct storage tables.

Prepare views/RPC/API types for:

- characters/entities;
- evidence-linked facts;
- events;
- timeline;
- relationships;
- provenance inspection.

This keeps storage/schema evolution behind the API boundary.

## 8. Cutover gate per stage

A stage is promoted only when:

- v3 benchmark passes its quality/safety gate;
- whole-book runtime/resource behavior is acceptable;
- output provenance is complete;
- failures and unresolved cases are visible;
- production license status is cleared;
- v2 regressions have been reviewed;
- downstream invalidation behavior is tested.

## 9. Rollback

Each promoted v3 stage needs a feature/config switch that can restore the previous qualified implementation without data loss.

Rollback switches are temporary migration tooling, not permanent dual-maintenance policy.

## 10. Completion condition

The v2 semantic stack can be retired when:

- every product-visible semantic capability has a qualified v3 path;
- v3 is the canonical writer for Narrative IR;
- old provider-specific IDs are no longer required by product code;
- Neo4j/vector/materialized views rebuild from v3 canonical data;
- v2 baseline remains reproducible from its frozen branch/artifacts;
- the compatibility layer can be removed without breaking supported clients.
