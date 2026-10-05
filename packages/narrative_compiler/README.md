# S.A.G.A. Narrative Compiler Package

This package is the model-light Python foundation for Phase V3.0.

It currently owns:

- the typed V3.0 Narrative IR subset;
- exact adaptation of the existing TypeScript normalization result;
- content/config/stage fingerprints;
- semantic-lexer and identity-linker interfaces;
- a conservative deterministic identity reference linker;
- a shared identity benchmark contract.

Heavy model adapters are intentionally optional and are not imported by the package root. Normal CI must never download model weights.

Authoritative contracts live in `docs/v3/` and `docs/phases/PHASE_V3_0_NARRATIVE_COMPILER_FOUNDATION.md`.
