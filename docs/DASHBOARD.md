# S.A.G.A. Dashboard Guide

The main UI is [story_dashboard.py](/B:/Documents/PyCharm/graduationProject/story_dashboard.py).

## Purpose

The dashboard is no longer just a review tool. It is the primary operational surface for:

- ingesting books
- running the pipeline
- observing progress
- reviewing outputs
- exporting the current run
- querying indexed story data

## Main Controls

- Upload books
- Reorder books
- Select scene analysis model
- Select identity model
- Select analysis mode
- Choose target scene size in words
- Run pipeline
- Reset results
- Export JSON contract

## Scene Sizing

- `0` means one full chapter per scene
- any value above `0` is treated as a target word count
- nonzero target sizes can produce chunks that span chapter boundaries
- chunks still respect paragraph boundaries and do not break mid-paragraph or mid-sentence

## Key Tabs

- `Status`
  Run progress and execution timing
- `Books`
  Current ordered inputs
- `Chapters`
  Chapter extraction output
- `Scenes`
  Per-scene analysis output, local evidence, compare-mode differences, and tool-runtime telemetry
- `Entity Registry`
  Tracked entities and mention counts
- `State Transitions`
  State change log and latest state
- `Canon Snapshot`
  State at the current point in reading order
- `Timeline`
  Ordered event timeline
- `Character Timelines`
  Per-character event grouping plus character profile inspection
- `Alias Map`
  Canonicals and aliases
- `Identity Decisions`
  Identity reasoning outcomes
- `Causal Graph`
  Causal events and links
- `Causal Metrics`
  Graph-level summary metrics
- `Story Search`
  Search over indexed outputs

## Export

Use the `Export JSON Contract` button in the sidebar after the pipeline run completes. The file is meant to be stable enough for handoff to downstream tools and integrations.

## Review Workflow

- Start on `Status` to check run health, warnings, compare-mode divergence, and tool-runtime filtering.
- Use `Scenes` for flagged-scene review and local-evidence inspection.
- Use `Character Timelines` for character profiles, alias inspection, and state/history review.
- Use `Alias Map` and `Identity Decisions` to inspect merge/rejection quality.
