# Dialogue / Speaker Attribution Benchmark Protocol

Status: **ACTIVE PHASE-3 EXPERIMENT CONTRACT**

## Purpose

This benchmark establishes a provider-neutral, source-grounded dialogue/speaker evaluation layer before S.A.G.A. adopts any quote or speaker-attribution provider.

It is deliberately source-neutral so repository work can continue while the private primary-fiction EPUBs are unavailable. It does **not** authorize a production default. Product promotion still requires the private Harry Potter / The Cruel Prince / Caraval / ACOTAR suite.

## Product contract

Dialogue analysis has two separable tasks:

1. detect exact quoted-speech spans in normalized source text;
2. attribute a detected quote to a canonical S.A.G.A. character when the evidence is strong enough.

Quote evidence belongs to the source/resolved layer. Speaker identity must reference a canonical character key rather than invent a provider-owned identity.

Every quote prediction records:

- section stable key;
- absolute Unicode code-point start/end offsets;
- deterministic quote ID;
- canonical `speakerKey` or `null` when unresolved;
- a bounded decision reason;
- provider/model/revision provenance;
- normalized-input fingerprint and semantic output fingerprint.

No committed benchmark artifact needs source prose.

## Reference annotations

`saga-dialogue-reference-v1` annotations store only:

- source SHA-256;
- normalized-input fingerprint;
- section key;
- exact quote offsets;
- annotation protocol version;
- speaker status: `known`, `unknown`, or `ambiguous`;
- canonical speaker label/key only when status is `known`.

`unknown` and `ambiguous` speaker labels are intentionally not forced into false ground truth.

When the primary EPUBs are available, representative annotation must cover at least:

- ordinary `Name said, “…”` and `“…” Name said` tags;
- pronoun speech tags;
- dialogue exchanges with omitted tags;
- interruptions and multi-sentence quotes;
- nested quotations;
- paragraph-spanning dialogue conventions;
- shouted/whispered/murmured/etc. speech verbs;
- dialogue around multiple nearby characters;
- unattributed/ambiguous speakers;
- quoted text that is not spoken dialogue.

## Metrics

### Quote detection

Exact quote-span precision, recall and F1 are primary.

A quote is correct only when section key and absolute start/end offsets match the reference exactly. This prevents a provider from receiving credit for paraphrased or approximately anchored text.

### Speaker attribution

Speaker metrics are computed separately from quote detection so failure modes remain visible.

For correctly matched quotes with a known gold speaker, report:

- strict speaker accuracy on matched quotes;
- resolved-speaker accuracy, excluding unresolved predictions;
- unresolved speaker rate;
- cross-character contamination rate;
- end-to-end speaker recall, which also penalizes missed quote spans.

Predictions on gold `unknown` or `ambiguous` speakers are reported as unscored assignments rather than silently counted correct or incorrect.

## Tier-0 deterministic baseline

The first baseline is intentionally conservative and dependency-free.

### Quote spans

It recognizes complete paired English double-quotation forms:

- curly `“ … ”`;
- straight `" … "`.

Single quotes are not treated as dialogue delimiters in v1 because apostrophes and contractions make a naive single-quote parser too contamination-prone.

Unmatched opening quotes are ignored rather than fabricating an end boundary.

Known limitations that must remain visible in later evaluation include:

- paragraph-spanning dialogue where opening quotation marks repeat and a closing mark occurs only at the final paragraph;
- typographic variants outside the initial English double-quote forms;
- nested quotation edge cases;
- non-dialogue quoted material.

### Speaker sieve

The deterministic attribution baseline consumes already-resolved S.A.G.A. identity mentions. It does not mint character identities.

For each quote it searches a bounded context on the same side of the quote for:

- a linked character mention;
- a configured speech verb such as `said`, `asked`, `replied`, `whispered`, `shouted`, etc.;
- sufficiently close mention/verb evidence.

Candidate ranking strongly favors character mentions adjacent to the speech verb rather than merely the name closest to the quotation mark. This prevents cases such as `Alice said to Bob, “…”` from being naively assigned to Bob.

The baseline returns unresolved when:

- no speech-verb/linked-character pair exists;
- competing character candidates are too close in score;
- only unsupported evidence is available.

Pronoun mentions are disabled by default in this deterministic floor. A dependency-aware or sequence-aware challenger can test whether pronouns improve recall without unacceptable contamination.

## Next challengers

No challenger is adopted in advance.

Planned comparisons:

1. deterministic quote/speech-verb baseline;
2. dependency-aware deterministic/local-NLP sieve;
3. BookNLP quote/speaker evidence normalized into the same prediction contract;
4. combined candidate restriction/stabilization;
5. bounded local semantic adjudication only for unresolved cases if cheaper methods leave a measured gap.

Normal CI must not download heavyweight models.

## Promotion rule

A dialogue/speaker method cannot become the production default from synthetic tests, LitBank, BookNLP published metrics, or one modern-fiction excerpt alone.

Promotion requires:

1. deterministic merge-gate tests pass;
2. source/model/config fingerprints are preserved;
3. primary-suite chapters are manually annotated and scored;
4. quote precision/recall, speaker accuracy, unresolved rate and cross-character contamination are reviewed together;
5. whole-book runtime/RAM/VRAM/model-size/license evidence is recorded where applicable;
6. repeatability is demonstrated;
7. the chosen software/model license is production-compatible.

The private modern-fiction suite governs the product decision if it disagrees with public benchmark evidence.

## Architecture boundaries

- no paid AI API is required;
- no Modal textual inference is permitted;
- provider output remains evidence, not canonical truth;
- canonical speaker identity comes from the S.A.G.A. resolved character layer;
- exact source offsets remain immutable evidence anchors;
- dependency/model challengers must remain replaceable behind the same benchmark contract.

Tracks #196 and parent Phase-3 tracker #185.
