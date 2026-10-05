# S.A.G.A. v3 Model / Dependency License Ledger

Status: **V3.0 CHALLENGER PINS AUDITED — VERIFY AGAIN AT PROMOTION TIME**

This ledger is a release gate, not legal advice. Repository/package and model-weight licenses can differ, so each exact checkpoint is audited separately and must be rechecked before production promotion.

## V3.0 pinned qualification challengers

| Candidate | Exact revision / package pin | Intended role | Observed license | Production posture |
|---|---|---|---|---|
| `fastino/gliner2.5-base-v1` | model `ca906247640776a07753514055be9726f9080ead`; `gliner2[local]==2.0.0` | semantic lexer | Apache-2.0 model + Apache-2.0 library | eligible challenger; **not adopted** |
| `cross-encoder/ettin-reranker-68m-v1` | model `d166fa88ddde3c42bc3ee92f7df476d941c8204a`; `sentence-transformers==6.1.0` | identity candidate scorer experiment | Apache-2.0 model; Sentence Transformers package used through its standard local API | eligible challenger; **not adopted** |

The exact pins above are mirrored in `packages/narrative_compiler/model_manifest.py`. The model adapters load those revisions rather than unpinned Hugging Face `main`.

Important qualification caveat: the public Ettin checkpoint is trained as a text reranker/relevance scorer, **not literary coreference**. Its score is experimental evidence only. It must not become a merge probability or production identity policy without S.A.G.A.-owned calibration/quality evidence.

GLiNER2.5 is likewise a local semantic-lexer candidate, not a book-global identity system. Its long-document API scans overlapping local chunks; global resolution remains a separate S.A.G.A. stage.

## Other candidates / reference systems

| Candidate | Intended role | Current observed license | Production posture |
|---|---|---|---|
| BookNLP package | v2 literary NLP baseline | MIT | baseline package; audit weights/data separately |
| NuMind NuExtract3 | structured extraction escalation | Apache-2.0 | eligible subject to exact revision audit |
| Qwen3.5 9B / Base | bounded reasoning fallback | Apache-2.0 | eligible subject to exact revision audit |
| xCoRe | research identity reference | CC BY-NC-SA 4.0 | research-only under current policy |

## Pinning rules

1. A permissively licensed library does not imply its downloaded model weights are permissive.
2. A permissive model does not imply all training/evaluation datasets can be redistributed.
3. Private copyrighted books used for qualification must never be committed as training/evaluation text.
4. Research-only models can establish quality ceilings without becoming production dependencies.
5. Normal/model-light CI must not install the `v3-lexer`, `v3-linker`, or `v3-models` extras.
6. Every production-promoted model requires:
   - source URL/repository;
   - exact revision/hash;
   - downloaded artifact fingerprint;
   - license identifier;
   - local license/notice where required;
   - commercial-use assessment;
   - redistribution assessment;
   - training-data caveats if material to product risk;
   - S.A.G.A. qualification results on the representative product corpus.

## Sources checked for the V3.0 pins

- GLiNER2 repository: `https://github.com/fastino-ai/GLiNER2`
- GLiNER2 PyPI package: `https://pypi.org/project/gliner2/`
- GLiNER2.5 base checkpoint: `https://huggingface.co/fastino/gliner2.5-base-v1`
- Sentence Transformers: `https://github.com/huggingface/sentence-transformers`
- Ettin 68M checkpoint: `https://huggingface.co/cross-encoder/ettin-reranker-68m-v1`

## Pending explicit checks

Before later-stage implementation promotion, verify exact revisions for:

- NuExtract3;
- Qwen3.5 quantized artifact source and quantizer license/metadata;
- any ModernBookNLP/speaker model used for benchmarking;
- any Maverick/CorPipe/BOOKCOREF artifacts used in research qualification;
- embedding models selected for candidate generation;
- any S.A.G.A.-trained/fine-tuned checkpoint and its training-data provenance.

## Rejection condition

If licensing is ambiguous, non-commercial, field-of-use restricted, or incompatible with the intended public/commercial future of S.A.G.A., the dependency cannot become the default production path without an explicit owner decision.
