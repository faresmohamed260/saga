# BookNLP Persistent Loaded Runtime Proof

Status: **MEASURED PHASE-3B RUNTIME DECISION — PERSISTENT STDIO PREFERRED FOR BOOKNLP**

Issue: #226

This experiment tests one narrow question: after the real one-shot BookNLP subprocess boundary was validated in issue #224 / PR #225, is it worth keeping the Python BookNLP runtime loaded between requests?

It does **not** re-score BookNLP model quality and does not promote BookNLP into production.

## Baseline

The validated one-shot generic subprocess proof on pinned LitBank document `1023_bleak_house_brat` established:

- exact provider-neutral semantic fingerprint: `8be0f789a80ecf47c0b902b51e0492c17ef016023c3e215df6a4d57ff3e27add`;
- evidence counts: `230` identity mentions, `230` entities, `5` quotes, `20` event triggers, `2,319` syntax tokens;
- independent one-shot `analyze()` timings: `6.314 s` and `8.930 s`;
- second-run one-shot `health()`: `2.847 s`;
- second-run peak aggregate process-tree RSS: `1040.5 MiB`;
- complete prepared offline runtime footprint: approximately `439 MiB`.

The one-shot boundary remains the correctness reference.

## Challenger design

The challenger keeps one **local Python BookNLP process loaded** and communicates over bounded line-delimited JSON on stdio. There is no HTTP server or listening port.

S.A.G.A. TypeScript remains the orchestration owner and retains:

- provider/configuration/input fingerprints;
- request IDs;
- source-span and structural-locator validation;
- provider-neutral normalization;
- timeout/input/output/stderr limits;
- retryability/failure classification;
- secret stripping;
- downstream canonical truth and persistence policy.

The Python process owns only pinned BookNLP model loading and inference.

The persistent transport has a distinct configuration fingerprint from the one-shot transport so provenance cannot silently collapse the two runtime modes.

## Model-light qualification

Normal CI remains heavyweight-model-free.

The persistent fixture tests prove:

- one child is reused across health + repeated analyze requests;
- provider-neutral evidence exactly matches the one-shot fixture;
- a structured per-request error does not poison the process;
- a crashed request is **not** silently retried, while a later request may start a fresh child;
- package/configuration/output drift fails closed;
- ambient S.A.G.A. secrets are stripped;
- timeout is explicit;
- shutdown is terminal and cleanup occurs even when shutdown validation fails.

Qualification result:

- typecheck: pass;
- analysis-worker tests: **`145 / 145` pass**;
- previous merged baseline before the persistence tests: `139 / 139`;
- delta: `+6` lifecycle/failure tests with no regression.

An intermediate implementation exposed a real cleanup defect: an invalid shutdown response could reject before terminating the child. The final provider kills/clears the child in cleanup even if shutdown validation fails. The failed intermediate CI is retained in GitHub Actions history.

## Real BookNLP benchmark

Exact implementation/benchmark head:

`2fa30b185cb037180f3e7762f2166067096e08c5`

Workflow run:

`34762397330`

The job was executed twice on the exact same SHA on separate GitHub-hosted runners.

### Attempt 1

Artifact:

- ID `10319696420`;
- digest `sha256:4d064dd228fa6d1ec8b812de3e7b42db778aec3d76671911154da46c78badbc8`.

Measured result:

- startup/health: `3.694 s`;
- analyze passes: `4.977 s`, `4.627 s`, `4.368 s`;
- median analyze: **`4.627 s`**;
- speedup vs one-shot `6.314 s`: `1.36x`;
- speedup vs one-shot `8.930 s`: `1.93x`;
- peak aggregate process-tree RSS: `1007.1 MiB`;
- semantic evidence fingerprint on all three passes: `8be0f789a80ecf47c0b902b51e0492c17ef016023c3e215df6a4d57ff3e27add`;
- semantic comparison fingerprint: `4da56c28895486da135deea7023d0f7709eea264945a0136fec8366f8dcb1a8a`;
- report fingerprint: `f9245ee7eea5561eb13b1fe056117dfec52bc894717089d1f7486e83ed9e7b81`;
- malformed-request recovery: pass;
- controlled shutdown: pass;
- typecheck: pass;
- tests: `145 / 145` pass.

### Attempt 2 — independent repeatability run

Artifact:

- ID `10319368057`;
- digest `sha256:0e3462ed6a35ef758f1163f5cb78625df0086c40c37d9ab626ef37326e698456`.

Measured result:

- startup/health: `3.134 s`;
- analyze passes: `3.039 s`, `2.745 s`, `2.853 s`;
- median analyze: **`2.853 s`**;
- speedup vs one-shot `6.314 s`: `2.21x`;
- speedup vs one-shot `8.930 s`: `3.13x`;
- peak aggregate process-tree RSS: `1028.7 MiB`;
- semantic evidence fingerprint on all three passes: `8be0f789a80ecf47c0b902b51e0492c17ef016023c3e215df6a4d57ff3e27add`;
- semantic comparison fingerprint: `4da56c28895486da135deea7023d0f7709eea264945a0136fec8366f8dcb1a8a`;
- report fingerprint: `c147399cc72d4a838f8f626c4677c39880e49f1fdd8a8fc22ec4bad118eab5a2`;
- malformed-request recovery: pass;
- controlled shutdown: pass;
- typecheck: pass;
- tests: `145 / 145` pass.

## Interpretation

### Semantic repeatability

The strongest result is not the timing. All six real persistent analyses across two independent runs reproduced the **exact validated one-shot provider-neutral evidence fingerprint** and exact counts.

The semantic comparison fingerprint was also identical across both persistent runs. Runtime report fingerprints differ, as expected, because wall-clock/resource measurements are host-dependent.

### Runtime benefit

Persistent median analyze latency was `4.627 s` and `2.853 s` across the two runs, compared with one-shot measurements of `6.314 s` and `8.930 s`.

Even the slower persistent run materially beats both measured one-shot analyses. The faster repeat demonstrates that host variance is substantial, but it strengthens rather than weakens the conclusion that repeated model recreation is avoidable overhead.

Cold startup/health is not faster: persistent startup measured `3.694 s` and `3.134 s` versus the measured one-shot health call at `2.847 s`. Persistence therefore benefits **repeated analyses after startup**, not a single health-only call.

### Memory

Peak aggregate process-tree RSS was `1007.1 MiB` and `1028.7 MiB`, versus `1040.5 MiB` for the second one-shot proof. That is only a small reduction and should **not** be presented as a material memory win.

The durable operational benefit is model reuse / lower repeated latency.

### Artifact footprint / provenance

The three immutable BookNLP task weights remain `160,398,571 bytes` with the same individual SHA-256 digests.

Whole prepared cache totals varied slightly (`460,346,523` vs `460,346,121` bytes) because Hugging Face/cache bookkeeping is mutable. Whole cache-directory size/hash is therefore not model identity. Provenance continues to rely on pinned model IDs/revisions, package versions and immutable file digests.

## Decision

**Adopt persistent local stdio as the preferred BookNLP runtime transport when BookNLP evidence is invoked by S.A.G.A.**

Keep the one-shot generic subprocess path as the simple correctness/reference implementation and fallback development harness, not the preferred repeated-analysis runtime.

Do **not** add an HTTP sidecar for BookNLP at this stage: the measured requirement is model lifetime, and local stdio solves it without a listening port or another service boundary.

This transport decision does **not** change any BookNLP model-quality decision:

- BookNLP remains rejected for primary character identity;
- deterministic quote boundaries remain the public-gold quote leader (`0.8563` F1 vs BookNLP `0.8146`);
- combined speaker V2 remains the public speaker challenger;
- BookNLP event triggers remain the strongest measured public trigger challenger (`0.7791` F1);
- participant correctness still lacks suitable gold;
- BookNLP model-weight licensing remains unverified;
- private modern-fiction qualification remains mandatory before production adoption.

No paid inference, Modal textual analysis, Vercel deployment, or copyrighted private-book prose was introduced by this experiment.