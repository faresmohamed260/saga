# Local Commit Triage

Audit date: 2026-09-10

This document triages the 43 commits present on `origin/codex/transaction-pool-rc36` that are not in the current GitHub `main`.

The old branch cannot be merged or replayed directly. Compared with current `main`, it would remove many newer GitHub files, including Studio workflows, Studio application files, Modal worker fleet workflows, Qwen/FLUX/LTX integration files, and the newly merged recovery/governance documentation. Recovery must therefore port useful ideas forward file-by-file.

## Overall decision

Do not merge PR #54 / `codex/transaction-pool-rc36` as-is.

Preserve it as historical recovery evidence and use it as a source for future focused PRs only. The durable facts from the branch are now represented in:

- `docs/recovery/LOCAL_TO_GITHUB_HANDOFF_INVENTORY.md`
- `docs/validation/REPRODUCIBILITY.md`
- `docs/operations/GITHUB_ACTIONS_SECRETS.md`
- `docs/operations/PROTECTED_TEST_ASSETS.md`
- `docs/operations/MODEL_PROVIDER_MANIFEST.md`

## Commit-by-commit triage

| Commit | Subject | Primary area | Decision |
| --- | --- | --- | --- |
| `3b725f1` | Use Supavisor transaction pooling by default | persistence/deployment | Candidate for focused future port only after comparison with current Supabase runtime. Do not cherry-pick blindly. |
| `ad4bb24` | Harden narrative grounding and identity resolution | analysis/identity | Candidate for focused future port. Preserve as identity-quality evidence; current identity docs already warn not to mask upstream defects downstream. |
| `e2f3495` | Attribute provider usage to projects | usage/accounting | Candidate for future port if current usage-governance schema still lacks project attribution. Requires migration comparison. |
| `8342162` | Enforce calibrated visual quality policy | visual QA | Candidate for future port. Current docs preserve the visual-quality hardening need; do not replace current visual stack without evidence. |
| `c91b052` | Separate administrative database connections | deployment/persistence | Candidate for focused audit. Requires Supabase/runtime security review before porting. |
| `88ae0c2` | Enforce bounded qualification stage deadlines | qualification | Candidate for future port. Concept is preserved in reproducibility/live-gate docs. |
| `2f2f6f8` | Bound and attribute canon extraction | canon/usage | Candidate for future port only with current canon extraction tests. |
| `70b4356` | Establish local reasoning qualification runtime | local reasoning | Historical/evaluation-only. Do not make local workstation qualification a normal CI dependency. |
| `11bab8b` | Materialize reproducible local book corpus | protected assets | Metadata preserved; do not commit commercial books. Use protected-asset manifest and gated acquisition. |
| `b4dff50` | Add bounded local reasoning qualification suite | local reasoning | Historical/evaluation-only. May inform a self-hosted/live workflow later. |
| `9bacbef` | Separate local model preload from qualification | local reasoning | Historical/evaluation-only. Keep as candidate design for self-hosted qualification. |
| `9b1a790` | Enforce resource-safe local model qualification | local reasoning | Historical/evaluation-only. Resource-safety principle preserved. |
| `d53209a` | Gate local candidates by workstation fit | local reasoning | Historical/evaluation-only; not portable to GitHub-hosted runners. |
| `c1d4694` | Reject local qualification on busy hosts | local reasoning | Historical/evaluation-only; may inform self-hosted runner docs. |
| `2f3bfed` | Measure local reasoning time to first token | benchmarking | Historical/evaluation-only. Keep metrics as evidence if copied into compact reports later. |
| `21b9c09` | Add source-safe extraction gold evaluation | evaluation | Candidate for future port if fixtures contain no protected copyrighted text. |
| `8a007dc` | Add bounded reasoning runtime admission | reasoning runtime | Candidate for future port; compare against current queue/execution runtime before changing code. |
| `988180d` | Require reviewed exact-corpus gold labels | evaluation | Candidate for future port if fixtures remain source-safe. |
| `79a4813` | Gate local routes on production evidence | reasoning runtime | Candidate principle; code port requires current provider-routing audit. |
| `b8c7962` | Add native LM Studio qualification engine | local reasoning | Historical/evaluation-only. Do not introduce LM Studio as a required remote dependency. |
| `b228acc` | Make local engine qualification explicit | local reasoning | Historical/evaluation-only. Principle preserved in model/provider manifest. |
| `a114f89` | Make local model qualification engine aware | local reasoning | Historical/evaluation-only. |
| `78d6807` | Record bounded local model shootout | evaluation evidence | Historical evidence. Port only compact summaries, not model artifacts. |
| `e7fe31b` | Record local planning reliability results | evaluation evidence | Historical evidence. Port only compact summaries if still relevant. |
| `a235388` | Record Qwen semantic route elimination | reasoning/provider choice | Historical evidence; current Qwen/Studio work is a separate surface. |
| `e22397f` | Wire qualified local reasoning routes | reasoning runtime | Candidate only after current provider-route audit. Do not make local routes default. |
| `f80aa06` | Bound local model qualification scope | local reasoning | Historical/evaluation-only. |
| `9bcad89` | Add reviewed local extraction benchmark gold | evaluation fixture | Candidate for future port if source-safe and license-safe. |
| `c002a31` | Record Qwen3 artifact integrity gate | model acquisition | Historical evidence; no large model files should be committed. |
| `ef4f671` | Bound local model qualification execution | local reasoning | Historical/evaluation-only. |
| `800c249` | Expose local reasoning qualification evidence | docs/evidence | Historical evidence. Current manifests preserve the need to migrate compact evidence, not raw outputs. |
| `351c39c` | Record repeated local model challenger evidence | docs/evidence | Historical evidence. |
| `e92bd7a` | Skip model loads for completed qualification plans | local reasoning | Candidate behavior for self-hosted qualification only. |
| `8980dc3` | Audit local reasoning qualification completion | docs/evidence | Historical evidence. |
| `fe5ef95` | Checkpoint durable Qwen3 30B acquisition | model acquisition | Historical evidence; do not commit model weights. |
| `5c377a8` | Record Qwen3 30B acquisition milestone | model acquisition | Historical evidence. |
| `30900bf` | Record Qwen3 30B midpoint acquisition | model acquisition | Historical evidence. |
| `cca36d6` | Record Qwen3 30B three-quarter milestone | model acquisition | Historical evidence. |
| `ef8515a` | Close bounded local reasoning qualification | local reasoning | Historical evidence; not a current clean-source qualification. |
| `d9a5cc5` | Mark local book pipeline not ready | qualification | Durable finding preserved: do not claim local book pipeline ready without clean-source evidence. |
| `7107607` | Start real-book local vertical slice | qualification | Historical evidence. Requires protected assets and clean-source rerun before production claim. |
| `21716fd` | Bound and resume local canon modeling | qualification | Historical evidence/candidate behavior. |
| `0294bb2` | Complete local real-book generation slice | qualification | Historical evidence only; not promotable because it is bound to divergent local state. |

## File-family decisions

| File family from old branch | Decision |
| --- | --- |
| `benchmarks/reasoning/*` | Do not port immediately. These are useful local-evaluation candidates but may encode workstation/model assumptions. Reintroduce through a focused benchmark PR only after fixture/source-safety review. |
| `packages/reasoning_runtime/qualification.py`, `queueing.py`, `routing.py` | Candidate source code. Compare against current `reasoning_runtime`, `execution_runtime`, and provider-config docs before porting. |
| `packages/identity_runtime/canonicalization_evaluation.py` and related identity review edits | Candidate identity-quality work. Port only with current fixtures/tests and no book-specific shortcuts. |
| `packages/visual_generation/evaluation.py`, `policy.py` | Candidate visual QA work. Preserve as a likely next hardening slice after baseline recovery. |
| `scripts/build_local_reasoning_*`, `scripts/qualify_local_reasoning.py` | Historical/local tooling. Do not require in GitHub-hosted CI. May become a self-hosted/manual workflow later. |
| `tests/fixtures/*once_upon_a_broken_heart*` | Candidate fixtures only if they are source-safe and contain no protected text beyond acceptable snippets. |
| `migrations/versions/202608120100_usage_project_attribution.py` | Candidate migration. Must be compared against current migration head `202608090400` and any later usage-governance schema before porting. |
| `deploy/production/.env.example` old-branch edits | Do not replay. Current main now includes handoff placeholders and must remain the baseline. |
| deletions of current Studio/workflow files visible in old-branch diff | Reject. They are an artifact of branch age, not a recovery instruction. |

## Follow-up sequence

1. Leave PR #54 open as historical/draft evidence unless the maintainer chooses to close it.
2. Create focused future PRs for any accepted code port:
   - usage attribution/migration;
   - reasoning admission/routing;
   - identity/narrative grounding evaluation;
   - visual quality policy;
   - self-hosted local reasoning qualification.
3. Each focused PR must run the relevant Tier 1 gates and update the owning docs.
