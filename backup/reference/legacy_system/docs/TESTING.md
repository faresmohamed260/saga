# S.A.G.A. Testing Guide

The project uses lightweight regression-style tests in [tests](/B:/Documents/PyCharm/graduationProject/tests).

## Purpose

These tests focus on the pipeline's most important contracts:

- scene analysis normalization and retries
- identity analysis normalization
- scene extraction and indexing behavior
- entity/state/canon services
- identity resolution and query behavior
- causal graph generation and indexing

## Run All Tests

```powershell
pytest tests
```

## Run A Single Module

```powershell
pytest tests/test_causal_graph.py
```

## Notes

- The tests are intentionally small and deterministic.
- Most of them use stub LLM clients instead of real network calls.
- Root-level `*_test.py` files are compatibility wrappers, not the source of truth.
