# S.A.G.A. v3 Model / Dependency License Ledger

Status: **INITIAL AUDIT — VERIFY AGAIN AT PIN TIME**

This ledger is a release gate, not legal advice. Exact checkpoint/revision licenses must be re-verified when artifacts are pinned because repository/package and model-weight licenses can differ.

| Candidate | Intended role | Current observed license | Production posture |
|---|---|---|---|
| BookNLP package | v2 literary NLP baseline | MIT | eligible package; audit weights/data separately |
| GLiNER2 library/family | semantic lexer | Apache-2.0 | eligible subject to exact checkpoint audit |
| Ettin reranker family | linker/scorer/classifier backbone | Apache-2.0 | eligible subject to exact checkpoint audit |
| NuMind NuExtract3 | structured extraction escalation | Apache-2.0 | eligible subject to exact revision audit |
| Qwen3.5 9B / Base | bounded reasoning fallback | Apache-2.0 | eligible subject to exact revision audit |
| xCoRe | research identity reference | CC BY-NC-SA 4.0 | research-only under current policy |

## Rules

1. A permissively licensed library does not imply its downloaded model weights are permissive.
2. A permissive model does not imply all training/evaluation datasets can be redistributed.
3. Private copyrighted books used for qualification must never be committed as training/evaluation text.
4. Research-only models can be used to establish quality ceilings without becoming production dependencies.
5. Every pinned production model requires:
   - source URL/repository;
   - exact revision/hash;
   - artifact fingerprint;
   - license identifier;
   - local copy of license/notice where required;
   - commercial-use assessment;
   - redistribution assessment;
   - training-data caveats if material to product risk.

## Pending explicit checks

Before implementation promotion, verify exact revisions for:

- selected GLiNER2/2.5 checkpoint;
- selected Ettin encoder/reranker sizes;
- exact NuExtract3 revision;
- Qwen3.5 quantized artifact source and quantizer license/metadata;
- any ModernBookNLP/speaker model used for benchmarking;
- any Maverick/CorPipe/BOOKCOREF artifacts used in research qualification;
- embedding models selected for candidate generation.

## Rejection condition

If licensing is ambiguous, non-commercial, field-of-use restricted, or incompatible with the intended public/commercial future of S.A.G.A., the dependency cannot become the default production path without an explicit owner decision.
