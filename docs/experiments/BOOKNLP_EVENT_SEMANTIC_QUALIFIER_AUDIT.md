# BookNLP Event Semantic Qualifier Coverage Audit

Status: **PUBLIC FAILURE-MODE AUDIT COMPLETE — KEEP STRICT QUALIFIER POLICY**

Issue: #235

This experiment explains the low public coverage of the first source-grounded event semantic qualifier policy from #233 / PR #234 **without changing that policy**.

## Question

The first qualifier layer marks only `53 / 7,445` BookNLP event triggers (`0.71%`) with an explicit negation, modal or conditional cue. The audit asks whether known cue tokens near event triggers reveal a coherent structural omission that justifies widening the dependency policy.

This is a structural coverage/failure-mode audit, not a factuality benchmark. LitBank has event-trigger gold but no S.A.G.A.-style polarity/modality/realis gold.

## Evidence identity

Exact measured audit head:

`95034eef9cfaeb9935756d05fcfc1f3b60dfa2a8`

Dedicated workflow:

- run: `34777329193`
- job: `103777724459`
- LitBank commit: `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`
- attempted/completed/failed: **`100 / 100 / 0`**
- typecheck: **pass**
- analysis-worker tests: **`177 / 177` pass**, up from `168 / 168` before the audit contract
- new model inference: **none**
- preserved BookNLP source run: `34727310506`
- preserved native artifact SHA256: `006875873bd58ec53cc976a46d000313107228f4d4dbf6c5dc450cf9b7ba4f6a`
- audit report fingerprint: `90843ffdd8ecb3aa5d5a8075e04481c4b5e36f72c68631f2648ec1296bfcfc69`
- aggregate artifact ID: `10324132438`
- aggregate artifact digest: `sha256:47d7dddff62b67d22d8bb0cec26f0efa93d7d36eafa7a2bb26aa9a84ca18244b`

The test-count increase is regression/contract coverage only. It is not a semantic-quality gain.

## Trigger regression gate

The fixed event-trigger baseline did not change:

- predicted triggers: **`7,445`**
- precision: `0.8002686367`
- recall: `0.7590775895`
- F1: `0.7791290702` = **`0.7791` rounded**
- trigger-count delta: `0`

No trigger or participant policy changed.

## Audit policy

Candidate cue families:

- negation: every explicit `neg` dependency token plus lexical `not` / `never` candidates;
- modality: `can`, `could`, `may`, `might`, `must`, `shall`, `should`, `will`, `would`;
- conditionals: `if`, `unless`.

Each cue token in an event-bearing sentence is associated deterministically with the nearest event trigger by undirected dependency-graph distance. Ties use absolute token distance, trigger token ID and trigger evidence ID. Cross-sentence traversal is prohibited.

The classifier records these structural categories:

- `captured_direct_trigger_child`;
- `captured_auxiliary_child`;
- `direct_child_nonqualifying`;
- `descendant_depth_2_plus`;
- `parent_or_ancestor`;
- `sibling_shared_head`;
- `other_connected_same_sentence`;
- `disconnected_same_sentence`.

No raw source text is emitted in the committed or uploaded aggregate report.

## Corpus-level result

Across all 100 documents:

- candidate cue tokens: **`4,261`**;
- cue tokens in sentences containing at least one event trigger: **`1,528`** (`35.86%` of candidates);
- cue tokens in sentences without an event trigger: **`2,733`**;
- same-sentence cue↔trigger pairs before nearest-trigger selection: **`3,246`**;
- nearest-trigger cue associations: **`1,528`**;
- captured by the current strict policy: **`53`** (`3.47%` of associated cues);
- uncaptured associated cues: **`1,475`** (`96.53%`).

The denominator distinction matters: `4,261` is a unique cue-token count, while `3,246` is a cue↔trigger pair count before deterministic nearest-trigger selection.

### Structural placement

| Structural category | Count | Share of associated cues |
| --- | ---: | ---: |
| deeper descendant, depth >= 2 | **961** | **62.89%** |
| other connected same-sentence | **354** | **23.17%** |
| sibling / shared head | **149** | **9.75%** |
| captured direct trigger child | **53** | **3.47%** |
| direct child but nonqualifying | **9** | **0.59%** |
| parent / ancestor | **2** | **0.13%** |
| captured through auxiliary child | **0** | **0.00%** |
| disconnected same-sentence | **0** | **0.00%** |

Only **`11 / 1,528`** associated cues are one-hop structural cases not already captured (`9` nonqualifying children + `2` parent/ancestor). The dominant uncaptured mass is not a simple one-edge omission.

Dependency distances reinforce that result:

- distance 1: `64`;
- distance 2: `674`;
- distance 3: `392`;
- distance 4: `191`;
- distance 5+: `207` combined.

## Cue-family result

| Family | Candidate tokens | Associated | Captured | Captured among associated |
| --- | ---: | ---: | ---: | ---: |
| negation | `1,580` | `566` | **`3`** | **`0.53%`** |
| modal | `2,236` | `785` | **`45`** | **`5.73%`** |
| conditional | `445` | `177` | **`5`** | **`2.82%`** |

### Negation

Among the `566` associated negative cues:

- captured direct trigger child: `3`;
- direct child nonqualifying: `1`;
- deeper descendant: **`334`**;
- sibling/shared head: `82`;
- other connected same-sentence: `146`.

Lemma-level counts:

- `not`: `1,290` candidates, `475` associated, `3` captured; `279` are deeper descendants;
- `never`: `238` candidates, `69` associated, `0` captured; `40` are deeper descendants and only `1` is a direct nonqualifying child;
- `no`: `52` candidates, `22` associated, `0` captured. These are included because BookNLP assigned them an explicit `neg` dependency relation; they are not an added lexical-negative rule.

This does **not** justify propagating negation down arbitrary descendant paths. A nearby negative cue can scope a different predicate or clause, and LitBank provides no qualifier-scope gold to validate such propagation.

### Modality

Among `785` associated modal cues:

- captured: `45`;
- deeper descendant: **`487`**;
- sibling/shared head: `66`;
- other connected same-sentence: `178`;
- direct nonqualifying child: `7`;
- parent/ancestor: `2`.

The strongest strict captures remain `could` (`24`) and `can` (`11`). Several modal lemmas have many same-sentence associations but no strict captures (`would 183`, `might 81`, `should 66`, `may 47` associated). Those numbers show structural proximity, not semantic scope correctness.

### Conditionals

Among `177` associated conditional cues:

- captured: `5`;
- deeper descendant: **`140`**;
- other connected same-sentence: `30`;
- sibling/shared head: `1`;
- direct nonqualifying child: `1`.

`if` accounts for `174` associations and all `5` strict captures; `unless` has only `3` associations and no strict captures.

## Interpretation

The audit does **not** reveal a dominant one-hop parser/policy defect. Instead, the low first-policy coverage is mostly explained by the fact that broad cue lemmas occur elsewhere in event-bearing sentences and dependency subtrees.

A generic rule such as "inherit a cue from any descendant", "inherit from siblings", or "use the nearest cue in the sentence" would dramatically raise coverage but would also erase semantic scope boundaries. The public dataset cannot measure the resulting factuality contamination.

The tiny one-hop remainder (`9` direct-child nonqualifying plus `2` parent/ancestor cases) is too small to justify a policy expansion without gold or a targeted manual/private audit.

## Decision

**Keep the current strict event semantic qualifier policy unchanged.**

Specifically:

- keep explicit direct dependency evidence only;
- keep unmarked polarity/modality/realis states `undetermined`;
- do not propagate negation, modality or conditionals through arbitrary descendants, siblings, shared heads, nearest-sentence cues or ancestors;
- do not claim the current `3` negation hits represent negation recall;
- do not treat this structural audit as semantic correctness evidence;
- do not change production adoption.

A future qualifier expansion requires suitable factuality/scope annotations or a narrowly defined structural hypothesis with independent correctness evidence. The next Phase-3 work should therefore move to another source-neutral narrative capability rather than tuning this public cue policy post hoc.

## Constraints preserved

- no paid API or hosted inference;
- no Modal textual analysis;
- normal CI remains model-light;
- no copyrighted private prose in Git/artifacts;
- no trigger or participant policy change;
- no factual/realis default for unmarked events;
- no production adoption change.
