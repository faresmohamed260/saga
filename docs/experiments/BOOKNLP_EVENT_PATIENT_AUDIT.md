# BookNLP Event Patient Candidate Audit

Status: **PUBLIC FAILURE-MODE AUDIT COMPLETE — KEEP STRICT CHARACTER GROUNDING**

This audit explains why the first direct dependency participant challenger grounds only about one third of syntactic patient opportunities. It does not introduce a new model, rerun BookNLP, or score participant correctness.

The goal is to distinguish a genuine S.A.G.A. identity/attachment failure from a broader syntactic-domain effect: a direct object (`dobj`) or passive subject (`nsubjpass`) is not necessarily a character participant.

## Evidence source

- LitBank repository commit: `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`
- documents attempted/completed/failed: `100 / 100 / 0`
- preserved BookNLP inference run: `34727310506`
- preserved BookNLP artifact SHA-256: `006875873bd58ec53cc976a46d000313107228f4d4dbf6c5dc450cf9b7ba4f6a`
- dependency-grounding report fingerprint: `d2392c11869bf42d92d244af3cc58b4b39d360257726f8c6dc27587ff08f2ba0`
- audit workflow run: `34758675274`
- exact audit head: `dc71151491e8fafb8f92f3fad98921bdb57d1c2d`
- audit report fingerprint: `c8f36fb6a0af333c70c038e7dbe42ef94d78c3d1daf5b41fae24d6e4d412a571`
- artifact ID: `10316914749`
- artifact ZIP digest: `sha256:930dfb6844be99dad6fbdf4c8fd37382eadce56d3c232946bea978c8a727fc81`
- typecheck: pass
- analysis-worker tests: `139 / 139` pass

The scorer reuses the same raw BookNLP output as the prior component and grounding experiments. No heavyweight model inference is repeated.

## Audit scope

The audit inspects every direct syntactic patient candidate created by the merged policy:

- `dobj` child of an event trigger;
- `nsubjpass` child of an event trigger.

For each candidate it asks, in order:

1. was this exact identity mention already emitted as the patient?;
2. did the same character get emitted through another mention for the same event?;
3. is there one or more linked S.A.G.A./oracle character identities covering the token?;
4. is there a structural-locator mismatch?;
5. does LitBank gold contain a linked or unresolved person mention?;
6. does LitBank gold contain a non-person mention?;
7. does BookNLP entity evidence label the span as person or non-person?;
8. otherwise, what POS/fine-POS shape does the candidate have?

No raw source surfaces are emitted in the report. The final unresolved bucket exposes POS counts only.

## Results

Total patient candidate tokens: **`2,546`** across **`2,476`** events.

Events with more than one patient candidate: `67`.

### Dependency relation mix

| Relation | Candidates | Share |
| --- | ---: | ---: |
| `dobj` | 2,304 | 90.49% |
| `nsubjpass` | 242 | 9.51% |

The original aggregate `33.20%` patient-opportunity grounding yield is therefore dominated by direct objects, not passive subjects.

### Candidate categories

| Category | Count | Share |
| --- | ---: | ---: |
| grounded character | 824 | 32.36% |
| same character already grounded through another mention | 4 | 0.16% |
| linked character not grounded | **0** | **0.00%** |
| ambiguous linked character | 17 | 0.67% |
| structural-locator mismatch | **0** | **0.00%** |
| gold-linked person missing from identity | **0** | **0.00%** |
| unresolved person gold | 8 | 0.31% |
| non-person gold | 142 | 5.58% |
| provider non-person only | 15 | 0.59% |
| provider person only | 33 | 1.30% |
| no identity/entity evidence | 1,503 | 59.03% |

The four apparent linked-character misses from the first version of the audit were not implementation failures. All four are duplicate syntactic candidates for a character already emitted through another mention for the same event. After distinguishing that case, **true linked-character grounding misses are zero**.

There are also **zero** structural-locator failures and **zero** gold-linked person mentions missing from the oracle identity layer after the benchmark-locator correction merged in PR #222.

### Relation-specific behavior

For `dobj` candidates (`2,304`):

- grounded character: `686` (`29.77%`);
- same-character dedup: `4` (`0.17%`);
- ambiguous linked character: `15` (`0.65%`);
- unresolved person gold: `8` (`0.35%`);
- non-person gold: `133` (`5.77%`);
- provider non-person only: `13` (`0.56%`);
- provider person only: `29` (`1.26%`);
- no identity/entity evidence: `1,416` (`61.46%`);
- true linked-character miss: `0`.

For `nsubjpass` candidates (`242`):

- grounded character: `138` (`57.02%`);
- ambiguous linked character: `2` (`0.83%`);
- non-person gold: `9` (`3.72%`);
- provider non-person only: `2` (`0.83%`);
- provider person only: `4` (`1.65%`);
- no identity/entity evidence: `87` (`35.95%`);
- true linked-character miss: `0`.

Passive subjects are therefore much more character-oriented than direct objects under this corpus and annotation setup.

## No-entity POS profile

The largest bucket is the `1,503` patient candidates with no LitBank identity/entity mention and no BookNLP entity span covering the candidate. Their coarse POS distribution is:

| POS | Count | Share of no-entity bucket |
| --- | ---: | ---: |
| `NOUN` | 1,216 | 80.90% |
| `PRON` | 226 | 15.04% |
| `ADJ` | 28 | 1.86% |
| `NUM` | 8 | 0.53% |
| `PROPN` | **7** | **0.47%** |
| `VERB` | 7 | 0.47% |
| `SCONJ` | 6 | 0.40% |
| other | 5 | 0.33% |

Fine-POS is dominated by common nouns: `NN=927`, `NNS=303`. Only `7` candidates are `NNP`.

This does not prove that every unannotated common noun/pronoun is semantically non-character. It does show that the low aggregate patient coverage is not hiding a large population of obvious proper-name character mentions that the identity attachment layer failed to connect.

## Provider non-person evidence

Only `15` candidates are covered exclusively by provider non-person entity evidence:

- facility: `8`;
- vehicle: `5`;
- location: `2`.

This is too small to justify broad non-character entity attachment merely to raise the current coverage number. Non-character participants remain a separate future evidence layer requiring an explicit entity-grounding contract and suitable evaluation.

## Decision

The audit **strengthens the current strict policy** rather than motivating broader attachment rules.

Keep:

- direct character grounding only through already-linked S.A.G.A. identity;
- ambiguous candidates unresolved;
- structural-locator equality;
- no provider cluster IDs as canonical identity;
- no `dative` expansion merely to increase coverage;
- no conjunction inheritance merely to increase coverage.

Do **not** interpret `dobj` presence as a character-patient expectation. In future documentation/metrics, call these **direct-object patient candidates/opportunities**, not generic patient opportunities, so the denominator does not imply that every syntactic object should resolve to a character.

The current evidence shows **zero true linked-character attachment misses** among the measured direct patient candidates. The remaining uncertainty is mainly candidate semantics and missing participant gold, not an identified deterministic identity-grounding bug.

## Adoption consequence

No production adoption changes:

- BookNLP remains the strongest measured public event-trigger challenger (`0.7791` F1 vs lexical `0.1045`);
- merged direct dependency grounding remains the current public participant-grounding challenger infrastructure;
- participant correctness is still unmeasured because LitBank event annotations do not provide S.A.G.A.-style actor/patient gold;
- the private modern-fiction suite remains the production promotion gate;
- BookNLP model-weight licensing remains unverified.

The next useful event work should target **new semantic capability**, not synthetic coverage inflation: explicit non-character entity participants, negation/modality/realis, or private actor/patient annotations when source access returns.
