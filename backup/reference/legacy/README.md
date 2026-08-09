This directory holds isolated legacy and compatibility code that is no longer part of the active clean-architecture import graph.

Rules for this area:
- Do not import from here in active runtime code.
- Keep it only as migration reference or recovery material.
- New work should target `packages/`, `saga/persistence/`, and runtime-facing service surfaces.

Initial isolated set:
- compatibility wrappers replaced by direct builder/runtime usage
- legacy-only references preserved for audit and migration history
- moved wrappers live under mirrored source paths below this directory

Still live and not yet safe to move:
- SQLite-first persistence and tests under `saga/storage/` and `tests/*sqlite*`
- BookNLP-clean identity flow under `saga/identity/`
- dashboard and agent code paths that still read through SQLite-backed services

Those slices need replacement, not relocation, before they can leave the active tree.
