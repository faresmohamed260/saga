# S.A.G.A. Narrative Compiler Package

This package is the model-light Python foundation for Phase V3.0.

It currently owns:

- typed V3.0 Narrative IR primitives;
- exact adaptation of the existing TypeScript normalization result;
- content/config/stage and upstream-dependent artifact fingerprints;
- semantic-lexer and identity-linker interfaces;
- a conservative deterministic identity reference linker;
- V2 identity-result projection without repair/re-resolution;
- a V2-compatible identity benchmark contract;
- a LitBank TSV public-gold adapter;
- pinned, lazy GLiNER2.5 and Ettin challenger adapters;
- dedicated resource/model-artifact qualification utilities.

## Normal CI

Normal CI is deliberately model-light. Importing `packages.narrative_compiler` does not import GLiNER2, Sentence Transformers or Torch and does not download weights.

The full repository pytest suite covers the compiler contracts with deterministic/fake adapters.

## Heavy public qualification

Create a separate environment and install:

```bash
python -m pip install -r requirements/v3-qualification.txt
```

Run the linker-isolation floor with oracle LitBank person mentions:

```bash
python -m scripts.run_v3_litbank_identity_benchmark \
  --root /path/to/litbank \
  --out artifacts/v3-oracle-exact.json \
  --mode oracle-exact
```

Run the pinned GLiNER2.5 lexer challenger:

```bash
python -m scripts.run_v3_litbank_identity_benchmark \
  --root /path/to/litbank \
  --out artifacts/v3-gliner25-exact.json \
  --mode gliner25-exact \
  --device cuda
```

For heavyweight runs the harness downloads the **exact pinned revision**, hashes every file in the resolved model snapshot, loads from that hashed local snapshot, and records the aggregate artifact SHA-256 plus Python/package/CUDA environment and peak memory/wall time.

A manual-only GitHub Actions workflow is also provided for reproducible CPU public-corpus qualification. It does not run on pushes or pull requests.

## Interpretation

Neither GLiNER2.5 nor Ettin is production-adopted by this package. GLiNER2.5 is a local semantic-lexer challenger; the public Ettin reranker is experimental scoring evidence and is not treated as a coreference probability or merge decision.

Authoritative contracts live in `docs/v3/` and `docs/phases/PHASE_V3_0_NARRATIVE_COMPILER_FOUNDATION.md`.
