# Scene Segmentation Benchmark Protocol

Status: **ACTIVE PHASE-3 EXPERIMENT CONTRACT**

## Product definition

A scene is a contiguous narrative span that remains materially coherent across the dimensions most relevant to story understanding:

- time;
- location/space;
- ongoing action or local narrative objective;
- active character constellation / point-of-view context.

A scene boundary is annotated at the first paragraph of the new scene. Chapter boundaries are already structural boundaries and are evaluated separately from within-chapter scene changes.

The definition is intentionally close to current computational-literary scene-segmentation research while remaining aligned with S.A.G.A.'s downstream needs: event isolation, timeline reconstruction, tension profiling, relationship/state changes, and visual scene generation.

## Why this is a separate benchmark

The historical prototype first tried TextTiling and regex/formatting rules and found them inconsistent across books. It then used an LLM to propose scene-start phrases and deterministic source anchoring to cut the original text.

That history establishes two lessons:

1. formatting-only segmentation is not sufficient for S.A.G.A.;
2. semantic proposals must resolve back to exact source boundaries rather than rewriting or summarizing source text.

The Phase-3 goal is to retain semantic quality while replacing repeated paid/cloud LLM calls with a measured local cascade.

## Reference representation

Gold/reference annotations use only source fingerprints, section stable keys, paragraph counts, and paragraph indices. Copyrighted prose is never committed.

For every annotated section:

- paragraph `0` is the implicit first scene start;
- `sceneStartParagraphs` contains high-confidence scene starts;
- `ambiguousSceneStartParagraphs` contains defensible but disputed boundaries;
- ambiguous boundaries are not required gold and predictions near them are not counted as false positives.

The underlying paragraph IDs are deterministically derived from S.A.G.A.'s normalized source sections:

`<section-stable-key>:p:<zero-padded-paragraph-index>`

Every benchmark run must match the exact normalized-input fingerprint and source digest used during annotation.

## Annotation protocol

Annotators should mark a new scene when there is a material discontinuity in one or more of the four dimensions and the new state persists beyond a brief aside:

- **time:** meaningful jump/flashback/return to a different narrative time;
- **space:** move to a materially different setting rather than movement within the same local action;
- **action:** previous local action resolves/halts and a distinct action or objective begins;
- **character/POV constellation:** sustained switch to a different focal group or viewpoint context.

Do **not** create a new scene for:

- a brief memory or hypothetical sentence that immediately returns to the same action;
- normal dialogue turns;
- a new paragraph alone;
- a minor camera-like shift within one continuous action/location;
- formatting decoration that does not correspond to a semantic change.

If two reasonable annotators could defend different boundaries because the transition is gradual, place the candidate in `ambiguousSceneStartParagraphs` rather than forcing false certainty.

## Primary annotation sampling

Once the private EPUBs are available, annotate selected chapters from the primary fiction suite before running scene-model comparisons. Coverage must deliberately include:

- dialogue-heavy chapters;
- action/fight chapters;
- travel/location transitions;
- explicit time jumps;
- subtle unmarked time/location transitions;
- flashbacks/recollections;
- chapters with multiple POV/focal-character changes where applicable;
- chapters with decorative section breaks;
- long continuous scenes that should **not** be over-segmented.

At minimum, the initial scene set should include chapters from:

- *Harry Potter and the Philosopher's Stone*;
- *The Cruel Prince*;
- *Caraval*;
- *A Court of Frost and Starlight*;

and later expand across the rest of ACOTAR before production adoption.

Do not create gold labels without the actual source. Historical scene counts are reference evidence only, never substitute annotations.

## Metrics

Every candidate reports both strict and relaxed boundary metrics:

### Exact boundary

A prediction is correct only when it selects the exact gold scene-start paragraph.

Report:

- precision;
- recall;
- F1;
- false positives;
- false negatives.

### Tolerant boundary

A prediction can match a gold boundary within the configured paragraph tolerance. Initial default: **±1 paragraph**.

Matching is one-to-one. Report:

- precision;
- recall;
- F1;
- mean absolute matched-boundary error in paragraphs;
- extra predictions;
- missed gold boundaries;
- predictions ignored because they fall only in an ambiguous annotation zone.

Exact and tolerant metrics must both be retained. Relaxed scoring must never hide systematic over-segmentation.

### Whole-book operational metrics

For complete books also report:

- scene count distribution by chapter;
- median/mean paragraphs and words per scene;
- extremely short scene rate;
- extremely long scene rate;
- wall-clock time;
- peak RAM;
- peak VRAM if used;
- model/download size;
- deterministic output fingerprint where expected.

## Candidate cascade

No candidate is adopted in advance. Initial experiments should test increasingly expensive tiers independently.

### Tier 0 — deterministic structural baseline

Use only strong structural evidence, such as explicit section ornaments/breaks that survive normalized source extraction. This establishes a high-precision/low-recall floor.

### Tier 1 — cheap local semantic-change baseline

Evaluate paragraph/sentence representations plus local change-point scoring. Candidate embeddings must be small, locally runnable, permissively licensed, and benchmarked against Tier 0. Thresholds/configuration are fingerprinted experiments rather than silently tuned.

### Tier 2 — dedicated local scene classifier

Current scene-segmentation research shows that trained BERT-style classifiers remain competitive and can outperform prompted LLMs overall. Any implementation/model must be independently licensed for production use and tested on the private suite; published academic performance is not enough.

### Tier 3 — bounded local semantic adjudication

Only ambiguous candidate windows are sent to a small local structured-reasoning model. The model chooses a paragraph ID/boundary from supplied candidates; it must not rewrite source text or freely invent an offset.

This tier is justified only if it improves real-book boundary quality enough to warrant its compute.

## Current research notes

### Zehe, Fischer & Hotho — NAACL 2025

The paper defines literary scenes through continuity in time, space, action, and character constellation. It reports that exact boundary scoring can underestimate reasonable predictions and uses relaxed evaluation. Their improved sequential sentence classification substantially raises performance, and their experiments find BERT-based models slightly stronger overall while Llama models generalize somewhat better across text types.

Paper: `https://aclanthology.org/2025.naacl-long.500/`

The associated `LSX-UniWue/scene-segmentation` repository is a useful research reference, but GitHub currently exposes **no declared repository license**. S.A.G.A. must not copy/adopt that implementation as production code without clarified licensing.

### Guhr, Mao & Lin — 2025

Work on 20th-century US romance fiction uses manual annotations and a fine-tuned BERT-family scene-change classifier. The public repository describes the result as promising work in progress, not a final reliable solution, and the repository is GPL-3.0. Treat it as evidence that domain-specific supervised scene classification is viable, not as a production dependency by default.

Repository: `https://github.com/literarylab/scene_segmentation`

### LumberChunker — EMNLP Findings 2024

LumberChunker iteratively asks an LLM to identify semantic shifts among sequential passages. It is aimed at semantically coherent retrieval chunks rather than narrative-theory scene labels, but its **bounded passages -> choose a boundary** pattern resembles S.A.G.A.'s historical semantic-proposal/source-anchor design.

Its public repository currently exposes no declared license and examples depend on hosted Gemini/ChatGPT APIs, so it is a design reference only for Phase 3. We can reproduce the boundary-selection idea with a local model if experiments justify it.

Paper: `https://aclanthology.org/2024.findings-emnlp.377/`

## Promotion rule

A scene-segmentation approach cannot become the production default from public research results or classical literature alone.

It must:

1. beat or materially complement cheaper tiers on manually annotated primary-suite chapters;
2. remain stable across the different modern-fantasy transition styles in the private suite;
3. preserve exact source anchoring;
4. avoid unacceptable over-segmentation of dialogue/action;
5. record quality and resource cost;
6. pass at least two repeatability runs for deterministic configurations;
7. have production-compatible software/model licensing.
