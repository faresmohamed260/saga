# S.A.G.A. v3 Narrative Ontology

Status: **DRAFT v0 — SEMANTIC DEFINITIONS**

This document defines the semantic boundaries that models and reviewers must share. The goal is to prevent different pipeline stages from using the same words to mean different things.

## 1. Mention vs entity

A **mention** is text. An **entity** is the story-world identity inferred from one or more mentions.

Example:

- `Feyre`
- `she`
- `the High Lady`

These are three mentions and may resolve to one entity.

Rules:

- pronouns are mentions, not aliases;
- titles/descriptions may be mentions and may become aliases only after sufficient evidence;
- unresolved mentions are valid;
- one surface form may refer to different entities in different contexts;
- one entity may have many surface forms.

## 2. Alias vs descriptive reference

An **alias** is a reusable label that identifies an entity beyond one local syntactic context.

`Feyre Archeron` -> `Feyre` is an alias relation.

`the woman near the door` is ordinarily a descriptive mention, not a persistent alias.

Titles such as `High Lady` require contextual qualification because they may be role names shared by multiple entities over time.

## 3. Entity types

Initial canonical classes:

- `character`
- `location`
- `object`
- `organization`
- `faction`
- `creature`
- `concept`
- `other`

Subtyping is permitted as metadata. Do not create incompatible top-level entity classes merely because a model exposes more labels.

A named fictional species may be a concept/taxonomic entity while an individual member remains a character/creature entity.

## 4. Character

A character is an individuated story-world agent capable of persistent identity across mentions and time.

Characters may be:

- human;
- non-human;
- artificial;
- supernatural;
- unnamed but persistent.

Groups are not characters unless the narrative treats the group itself as an individuated actor; otherwise use organization/faction/group semantics.

## 5. Event mention vs event

An **event mention** is a local textual expression of an occurrence.

An **event** is the consolidated story-world occurrence that one or more event mentions refer to.

Example:

- `the explosion`
- `when the tower blew apart`
- `the blast`

may be three mentions of one event.

Do not merge solely on lexical similarity.

## 6. Event vs state

An **event** is bounded change/occurrence.

A **state** holds over an interval.

Examples:

- `Feyre opened the door` -> event.
- `The door was open` -> state observation.
- opening may produce a `closed -> open` state delta.

## 7. Event vs action

An action is one event subtype. Other events include:

- movement;
- communication;
- perception;
- cognition;
- appearance/disappearance;
- acquisition/loss;
- state change;
- creation/destruction;
- social interaction;
- conflict;
- revelation;
- physiological events.

The ontology should remain coarse enough to be learnable and useful. Fine-grained labels belong in extensible subtypes.

## 8. Event participant

Participants represent semantic roles in an event, not arbitrary nearby entities.

Initial roles:

- actor
- patient
- recipient
- experiencer
- instrument
- location
- source
- destination
- possessor
- other

A participant may reference a mention before canonical entity resolution completes.

## 9. Proposition

A proposition is the smallest semantically useful claim that can be supported or contradicted.

Examples:

- Feyre has blue-grey eyes.
- Rhys is in Velaris.
- Nesta distrusts Cassian.

A proposition preserves:

- polarity;
- modality;
- epistemic context;
- provenance.

`Feyre might be injured` and `Feyre is injured` are not equivalent propositions.

## 10. Observation vs accepted fact

An **observation** is evidence extracted/interpreted from source text.

An **accepted fact** is a canonical conclusion that has passed policy/constraint validation.

Example:

Text: `Rhys stepped between Feyre and the attacker.`

Safe observation:

- Rhys intervened between Feyre and an attacker.

Unsafe immediate fact:

- Rhys has the stable personality trait `protective`.

Stable traits/relationships/state may require multiple observations and counterevidence.

## 11. Explicit vs inferred

Every observation should distinguish:

- `explicit`: directly stated in source;
- `structurally_inferred`: supported by syntax/grammar;
- `behaviorally_inferred`: interpretation of an action;
- `reported`: attributed to a character/narrator claim;
- `reasoned`: requires semantic inference beyond local syntax.

Inference type is separate from confidence.

## 12. Attribute vs trait vs state

### Attribute

A descriptive property. May be stable or temporary.

Examples:

- eye color;
- height;
- occupation;
- title.

### Trait

A persistent behavioral/personality tendency reconstructed across evidence.

Examples:

- protective;
- impulsive;
- distrustful.

Traits should generally be aggregated, not emitted from one observation.

### State

A property valid during an interval.

Examples:

- alive/dead;
- injured/healthy;
- located in Velaris;
- owns sword X.

## 13. Relationship observation vs relationship state

A relationship observation records a source-supported interaction/relation signal.

A relationship state is a derived interpretation over time.

Example observations:

- A says `I love B`;
- A kisses B;
- A betrays B.

These may update a time-aware relationship model but should not be collapsed into one timeless label.

## 14. Quote vs dialogue act

A **quote** is structural text bounded by quotation typography/rules.

A **dialogue act** is semantic communication.

Quotes may contain:

- spoken dialogue;
- written material;
- quoted memory;
- nested quotation;
- non-speech quotation.

Speaker attribution applies only when the quote is determined to represent an attributable communication act.

## 15. Narrative order vs story-world time

### Narrative order

Deterministic source position: the order in which the reader encounters material.

### Story-world time

The temporal order of events in the fictional world.

Flashbacks, flash-forwards, memories and retellings make these different.

Never derive story-world order merely from chapter/offset order.

## 16. Temporal relation

Temporal relations are partial constraints, not necessarily a total sequence.

Supported initial relations:

- before
- after
- during
- contains
- overlaps
- simultaneous
- starts
- finishes
- unknown

The system may know `A before B` while leaving A vs C unresolved.

## 17. Causal relation

Causality requires stronger evidence than temporal adjacency.

Initial relations:

- causes
- enables
- prevents
- motivates
- contributes_to
- consequence_of
- unknown

`A happened before B` must never imply `A caused B`.

## 18. Identity scope

Canonical identity can exist at:

- document scope;
- series scope.

Series-level promotion must be evidence-driven. Two books containing `the King` do not automatically refer to the same entity.

## 19. Epistemic scope

S.A.G.A. must eventually distinguish:

- narrator assertion;
- character belief;
- quoted claim;
- hypothetical/conditional;
- dream/vision;
- known lie/deception where supported.

A character saying `X is dead` is not automatically canonical proof that X is dead.

## 20. Canonical uncertainty states

Semantic decisions support at least:

- `candidate`
- `accepted`
- `rejected`
- `unresolved`
- `superseded`
- `contradicted`

`unresolved` is a successful outcome when evidence is insufficient.

## 21. Precision principle

For canonical story facts:

> Missing information is preferable to fabricated certainty.

The system may maximize recall at the candidate-evidence layer while maintaining a much higher precision threshold for canonical promotion.
