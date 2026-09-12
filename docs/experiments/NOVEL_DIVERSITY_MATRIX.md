# Novel Diversity Benchmark Matrix

Status: **ACTIVE EXPERIMENT GOVERNANCE**

This matrix prevents S.A.G.A. from adopting a narrative-analysis provider because it performs well on one aggregate literary score while failing on a particular kind of novel.

## Rule

Character/entity providers must be evaluated at three levels:

1. **gold aggregate quality** — overall LitBank and other gold benchmark metrics;
2. **stratified literary quality** — the same gold results sliced by genre, narrative form, cast structure, language style, and identity stressor;
3. **whole-novel operational stress** — complete books covering materially different narrative structures, with runtime/RAM/VRAM/model-size/failure/repeatability evidence.

An aggregate score is not sufficient for production adoption.

## Gold-labelled LitBank strata

The machine-readable source is:

- `services/analysis-worker/benchmarks/litbank-novel-diversity.v1.json`

It pins LitBank commit `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8` and defines these overlapping evaluation strata:

- romance / social novel;
- gothic / horror;
- detective / mystery;
- adventure;
- speculative / science fiction;
- children's / youth fiction;
- historical / war;
- western / frontier;
- satire / comedy;
- modernist / experimental prose;
- first-person narration;
- epistolary / document-framed narration;
- multiple / nested narrators;
- large ensemble casts;
- non-human protagonists;
- archaic / eighteenth-century prose;
- alias / title / honorific-heavy identity.

Documents may belong to more than one stratum. These are **evaluation stress labels**, not claims that a work has one exclusive literary genre.

The reusable `stratified-identity-benchmark` evaluator aggregates raw counts before deriving rates, so small documents do not receive the same weight as large documents merely because both are one file.

## Complete-novel stress suite

The matrix also pins a minimum complete-book suite using Project Gutenberg keys without vendoring the source text into S.A.G.A.:

| Work | Main stressors |
|---|---|
| *Pride and Prejudice* | social/romance, honorifics, family surnames |
| *Dracula* | gothic, epistolary, multi-narrator, supernatural |
| *The Hound of the Baskervilles* | detective, first-person, dialogue, aliases |
| *Treasure Island* | adventure, first-person, crew/nicknames |
| *The War of the Worlds* | science fiction, first-person, non-person entities |
| *Alice's Adventures in Wonderland* | children's fantasy, personified non-humans, unusual names |
| *The Red Badge of Courage* | war, ranks, groups, role nouns |
| *Desert Gold* | western/frontier, nicknames, action-heavy prose |
| *Ulysses* | modernist/experimental, stream-of-consciousness |
| *Black Beauty* | non-human protagonist, first-person animal identity |
| *Middlemarch* | large ensemble, repeated family/social references |
| *The Moonstone* | mystery, multi-narrator, embedded documents, identity reveal |

Dedicated/manual runs must record exact downloaded source digests. Source retrieval must obey Project Gutenberg terms and copyright law applicable to the execution jurisdiction.

## Contemporary/private coverage

Public-domain canonical fiction is not enough to claim broad production reliability. Before a final provider stack is called production-grade, S.A.G.A. should also run a **private, non-committed** evaluation suite using legally available/user-owned books across:

- contemporary fantasy / romantasy;
- contemporary romance;
- thriller / crime;
- modern science fiction;
- contemporary literary fiction;
- young adult;
- progression fantasy / LitRPG or web-serial style;
- fanfiction;
- English translated fiction;
- very large ensemble / series installments.

Copyrighted source text from that suite must never be committed or redistributed. The repo stores only non-reconstructive benchmark metadata/results that are safe to retain.

## Supplemental datasets

### BOOKCOREF

BOOKCOREF is useful because it evaluates coreference on **full books**, with average document lengths reported above 200,000 tokens. S.A.G.A. pins upstream repository commit:

- `SapienzaNLP/bookcoref`
- `9283951b92978f97ae6cd60eeefe79bd3a7cb34c`

Upstream licensing/source terms require care. Treat BOOKCOREF as **evaluation-only** until its data/source licensing implications are accepted for the intended use. It is not a runtime dependency and its annotations must not be copied into product tables.

### GOLEMcoref

GOLEMcoref provides complete fictional works/fanfiction and multilingual coreference coverage. Its non-commercial license likewise makes it **evaluation-only**. It is useful as a supplemental robustness benchmark, not production training data or a runtime dependency.

## Adoption interpretation

The objective is not for every stratum to have identical scores. The objective is to make weak regions visible and decide deliberately whether:

- the candidate should be rejected;
- it should be restricted to a narrower evidence role;
- another provider should handle the weak stratum;
- a deterministic rule can safely cover the failure mode;
- an escalation model is justified.

Reliability and downstream correctness outrank model size or speed. Resource efficiency becomes a selection advantage only after the quality/failure profile is acceptable.

## Repeatability

A provider configuration is not considered repeatable from one successful run. At least two completed runs are required, and deterministic stages must produce the same semantic fingerprints unless the experiment explicitly documents an expected source of nondeterminism.
