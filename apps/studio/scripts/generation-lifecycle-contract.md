# Generation lifecycle validation

Iteration 12 is covered by `check-generation-lifecycle-contract.mjs` for source wiring and by `capture-video-output-preview.mjs` for View Job, Cancel, failover feedback, and running-job settings guidance.

The Playwright lifecycle mocks are registered on the shared browser context so the View Job and independent Cancel scenarios use the same deterministic backend contract without sharing UI busy state.
