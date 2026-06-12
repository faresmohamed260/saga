# Redesign Lab

This subtree contains the BookNLP identity work, evaluation utilities, and experimental pipeline helpers that were developed during the redesign/hardening track.

## Important Current Reality

This subtree is no longer fully isolated from production.

Production code now directly depends on parts of `redesign_lab`, especially:

- [redesign_lab/identity/booknlp_identity_adapter.py](/B:/Documents/PyCharm/graduationProject/redesign_lab/identity/booknlp_identity_adapter.py)
- [redesign_lab/identity/identity_provider.py](/B:/Documents/PyCharm/graduationProject/redesign_lab/identity/identity_provider.py)
- [redesign_lab/identity/series_identity_provider.py](/B:/Documents/PyCharm/graduationProject/redesign_lab/identity/series_identity_provider.py)

The old assumption that nothing here mutates production defaults is no longer true for identity.

## What Still Belongs Here

This subtree is still the right place for:

- benchmark utilities
- candidate comparison code
- training-data preparation utilities
- experimental orchestration helpers
- non-production evaluation reports

## What Is Production-Relevant Now

These areas are production-relevant:

- `redesign_lab/identity`
- selected contract schemas in `redesign_lab/pipeline/contracts`
- series identity support used by production encode flows

## CLI

Main redesign-lab CLI:

- [redesign_lab_cli.py](/B:/Documents/PyCharm/graduationProject/redesign_lab_cli.py)

Examples:

```powershell
python redesign_lab_cli.py benchmark-all
python redesign_lab_cli.py run-dry
python redesign_lab_cli.py run-end-to-end
python redesign_lab_cli.py compare
```

## Notes

- local reports, model weights, and training-data artifacts are intentionally kept out of Git by default
- this subtree should still be treated carefully when promoting experimental code into production paths
