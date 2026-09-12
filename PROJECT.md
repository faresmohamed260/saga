# S.A.G.A. Project

S.A.G.A. is being rebuilt as a web-first storytelling-intelligence platform. The active architecture is the S.A.G.A. v2 rebuild; pre-v2 runtime material is historical/reference only unless a current v2 decision deliberately re-adopts an idea behind a v2-owned contract.

This file is the short source-of-truth handoff for current work.

## Current Status

**Phase 1 — Closed-Demo Main Site, Accounts & Invitations: COMPLETE.**

**Phase 2 — Story Intake & Character Identity Foundation: REPOSITORY FOUNDATION COMPLETE; ORIGINAL HOSTED-PROVIDER PATH SUPERSEDED.**

- 2A Product/Data Foundation — COMPLETE
- 2B Source Storage & Deterministic Ingestion — COMPLETE
- 2C Character Identity Engine — COMPLETE
- 2D Repository/CI Qualification — COMPLETE
- Phase-2 hosted Supabase migrations — APPLIED AND VERIFIED 2026-09-12
- the experimental Modal/xCoRe worker/provider proof — SUPERSEDED by the owner’s 2026-09-12 local-first analysis decision

**Phase 3 — Local-First Narrative Analysis Rebaseline: ACTIVE.**

Authoritative Phase-3 contract:

- `docs/phases/PHASE_V2_3_LOCAL_FIRST_NARRATIVE_ANALYSIS.md`

Authoritative textual-analysis architecture:

- `docs/v2/ANALYSIS_ARCHITECTURE_2026.md`

Durable owner decisions:

- D-026 — textual book analysis is local-first and subscription-free
- D-027 — Modal is reserved for image/media generation, not textual analysis
- D-028 — analysis uses a cost-aware evidence cascade
- D-029 — providers are adopted by product quality **and** resource measurements
- D-030 — local analysis workers use the existing durable Supabase/B2 control plane

## Product Goal

S.A.G.A. is not a book summarizer. Its analysis runtime should progressively reverse-engineer a novel or series into an evidence-linked narrative model that can support:

- source/book/chapter/scene structure;
- canonical characters, aliases and mentions;
- dialogue and speaker attribution;
- locations, organizations, objects, creatures, factions and other entities;
- atomic events and grounded participants;
- relationships and how they change;
- character/world state over time;
- narrative order plus story-world chronology and flashbacks;
- causal links, motivations and consequences;
- higher-level arcs, tension, conflict, themes and summaries;
- later canon-aware retrieval, visualization, media and generation.

Keep three conceptual layers distinct:

1. **source layer** — immutable text/structure and exact evidence spans;
2. **resolved layer** — identities, references, speakers and other confidence-gated interpretation;
3. **derived intelligence layer** — events, relationships, state, timeline, causality and higher narrative models.

Do not rewrite source text when later evidence changes interpretation.

## Phase 3 Architecture Direction

The default textual-analysis topology is:

```text
apps/web
  -> Supabase durable analysis jobs
      -> local S.A.G.A. analysis worker
          -> B2 source bytes
          -> deterministic orchestration / evidence bookkeeping
          -> local Python literary-NLP provider(s)
          -> optional localhost llama.cpp structured reasoning
          -> structured evidence/results back to Supabase
```

The analysis host should require outbound HTTPS only. No public inbound home-server port is required.

The existing TypeScript `services/analysis-worker` remains the preferred job/orchestration owner unless measurements prove there is a better reason to change it. Model-specific Python code belongs behind a narrow local sidecar/provider boundary rather than inside Next.js.

### Analysis cascade

For every stage, prefer:

```text
Tier 0 deterministic structure/rules
  -> Tier 1 lightweight local NLP
  -> Tier 2 specialized local model for unresolved ambiguity
  -> Tier 3 small local generative reasoning over bounded evidence packets only
```

Do not repeatedly pass an entire raw novel through a large LLM merely because the context window permits it.

Provider/model outputs are evidence. S.A.G.A. deterministic code owns canonical IDs, admission/merge policy, provenance, job state, persistence, validation and accepted/uncertain/rejected status.

## Phase 3A — Immediate Work

The first implementation slice is **benchmark-before-adoption**, not another provider deployment.

Evaluate:

### Broad literary baseline

- **BookNLP small** — literary entities, events, coreference/name clustering and quote speaker attribution in one local pipeline.

### Typed entity challenger

- **GLiNER small v2.x** — configurable PERSON/location/organization/object/faction/etc. spans, prioritizing CPU/ONNX/INT8.

### Coreference challengers

- **F-Coref** first as the cheap permissive candidate;
- **LingMess** only if its larger footprint earns a meaningful quality gain;
- xCoRe/Maverick remain research comparisons by default because their released LitBank weights are non-commercial.

### Dialogue

Compare deterministic quote/speech-verb attribution, BookNLP speaker attribution, and a combined candidate-restriction path.

### Events

Compare dependency/verb candidates, BookNLP literary event triggers, their combination, then optionally a **Qwen3.5-4B** local schema-constrained normalizer over surviving candidates only.

### Local structured reasoning

Initial benchmark candidates:

- Qwen3.5-4B quantized — default small reasoning candidate;
- Qwen3.5-9B quantized — quality escalation candidate;
- `llama.cpp` — initial local serving/JSON-schema constraint layer.

No local LLM is adopted until measured against a non-generative baseline.

## Benchmark Rules

Every provider comparison must report both product quality and resource cost.

At minimum record:

- exact source digest and provider/model revision;
- task metrics / false-positive contamination;
- whole-book wall-clock time;
- peak RAM;
- peak VRAM where applicable;
- model/download size;
- license;
- output determinism/reproducibility;
- operational complexity;
- percentage of evidence requiring expensive escalation.

Reuse the existing LitBank evaluation layer where applicable, plus small deterministic fixtures for normal CI and at least one complete public-domain novel for dedicated whole-book resource qualification.

Normal CI must not download heavyweight models on every change.

## Existing Phase-2 Foundations To Preserve

### Phase 2A

PR #177 / merge `7a053697e874d8fb6e0b03571b7cf0f2e885dd61` established member-owned projects/sources, forced RLS, durable lease-based jobs, immutable runs and private Projects/Library surfaces.

### Phase 2B

PR #179 / merge `fad0b8e5a3cc5c0e819d86fb41f50fe587574aab` established provider-neutral B2 source contracts, upload verification, worker-side hashing, deterministic TXT/EPUB normalization and a separate v2 analysis worker.

### Phase 2C

PR #181 / merge `191e2e4ab4ad9d4023f198b295922b5675e8d269` established provider-neutral identity evidence, precision-first canonical admission, unresolved/quarantine policy, deterministic stabilization and immutable character/alias/mention evidence.

### Phase 2D repository qualification

PR #183 / merge `8463f1686b4ab24cbec2fae67e027b96bd87497f` qualified the repository and added the full 100-document LitBank oracle-policy benchmark plus lifecycle hardening.

Qualified resolver-policy baseline under oracle evidence:

- canonical precision `0.9516`
- canonical recall `0.9970`
- incorrect-merge rate `0.0000`
- fragmentation rate `0.1422`
- linked-mention precision `0.9942`
- linked-mention recall `0.7566`
- non-person quarantine rate `1.0000`
- cluster purity `1.0000`

This is a resolver ceiling/policy reference, not a production-provider score.

## Hosted Resources / Current Reality

### Supabase

Dedicated S.A.G.A. project:

- ref: `scmeqnpmhomzcwecjdtu`
- organization: `Fares Home Lab`
- region: `eu-central-1`
- API URL: `https://scmeqnpmhomzcwecjdtu.supabase.co`
- public signup disabled
- custom Resend SMTP active

All five repository-qualified Phase-2 migrations were applied to this hosted project on 2026-09-12 and the Phase-2 tables/RLS/service-function boundaries were verified.

### Backblaze B2

Dedicated private bucket:

- bucket: `saga-v2-faresmohamed260-1207062480`
- region: `us-east-005`
- endpoint: `https://s3.us-east-005.backblazeb2.com`

The master credential remains bootstrap/operator-only. Runtime access must use scoped non-master application keys.

### Analysis runtime

`services/analysis-worker/` is the active v2 analysis control-plane runtime.

The `ops/phase2-hosted-proof` branch contains experimental Modal/xCoRe qualification work from before the owner reset. It is **not authoritative and must not be merged as the text-analysis runtime**. Modal is now reserved for image/media generation.

### Vercel

Dedicated project:

- project: `saga`
- root: `apps/web`
- current temporary production alias: `https://saga-pi-two.vercel.app`

Automatic Git-triggered deployments are disabled.

**Deployment rule:** before any Vercel deployment, state why it is needed, Preview vs Production, and exact commit/SHA, then obtain fresh explicit owner approval. The 2026-09-12 analysis reset does not authorize a Vercel deployment.

## Current Execution Order

1. merge the Phase-3 local-first contract/governance update;
2. create a fresh Phase-3A implementation branch from the resulting `main`;
3. build provider adapters + resource instrumentation before changing production analysis policy;
4. benchmark BookNLP-small, GLiNER and coreference/dialogue/event alternatives through common S.A.G.A. contracts;
5. choose the cheapest acceptable defaults and explicit escalation conditions from measurements;
6. wire the adopted local provider stack into the durable worker;
7. prove one real whole-book queued run with paid APIs and Modal text inference disabled;
8. use those measurements to specify the next Event / State / Timeline Narrative Graph phase.

## Working Convention

Every substantial session starts from:

1. `AGENTS.md`
2. `PROJECT.md`
3. `docs/README.md`
4. `docs/DECISIONS.md`
5. `docs/phases/PHASE_V2_3_LOCAL_FIRST_NARRATIVE_ANALYSIS.md`
6. `docs/v2/ANALYSIS_ARCHITECTURE_2026.md`
7. other relevant `docs/v2/` contracts

GitHub is authoritative. Chat history is secondary context only.
