# 2026-10-06 — V3 Composite Mention Layer

Status: **SUPPORTED ARCHITECTURE — model-independent grounded mention composition**

The GLiNER2.5 calibration tranche established that no single measured semantic-lexer configuration provides adequate literary mention coverage. GLiNER is useful for explicit character/name seeding and as a supplemental mixed-reference detector, while nominal/reference coverage requires additional providers.

V3 therefore needs a provider-neutral composition boundary before identity resolution.

## Contract

`CompositeSemanticLexer` combines already-grounded child lexer results and does **not** perform identity resolution or fuzzy span reconciliation.

For every child mention it verifies:

- the source fingerprint matches the current normalized source;
- the source unit exists;
- the span is contained by that source unit; and
- the mention text exactly matches the normalized source slice.

Exact duplicate mentions are keyed by canonical V3 `mention_id`, which is already bound to source fingerprint, source unit, span, and entity type. Mentions sharing a surface span but representing different entity types remain distinct.

## Duplicate policy

When multiple providers emit the same canonical mention:

- one primary observation is selected deterministically, preferring the highest available confidence and then stable stage/artifact ordering;
- all provider observations are retained in `composite_provenance`;
- all observed lexer labels are retained in `lexer_labels`;
- child stage names are retained in `composite_sources`; and
- the exposed mention confidence is the maximum child confidence.

The maximum confidence is only an observation-selection convenience. **It is not a calibrated probability across providers and must not be used directly as a merge/link threshold.** Downstream identity ranking and merge/abstention remain separate stages.

## Reproducibility

The composite stage is order-invariant. Its artifact fingerprint is bound to the sorted child stage configuration and every child artifact fingerprint, so changing any provider output/configuration changes the composite artifact identity.

## Validation provenance

Before the history cleanup, the exact adapter and contract-test implementation passed the model-light `V3 Composite Lexer CI` workflow:

- workflow run: `37475712697`
- qualification head: `7f2360431a1a6caec71e76ea49f9516947e46957`
- result: success

The production PR is rebuilt directly on current `main`; normal repository PR CI remains the merge gate.

## Architectural consequence

The supported mention path is now:

`explicit-name provider` + `supplemental GLiNER mixed-reference provider` + `future nominal/pronoun/reference provider(s)` → **deterministic composite grounded-span union** → hybrid identity candidate retrieval → mention-kind-aware ranking → conservative merge / abstain policy.

This layer enables future provider experiments without coupling the narrative compiler to one model and without letting provider confidence semantics leak into canonical identity policy.
