# Contributing

## Bounded execution

Development tasks should produce reviewable evidence early instead of accumulating an open-ended research scope.

- Give each task one primary outcome and define its acceptance check before implementation.
- Produce the first inspectable result within 15 minutes. If that is impossible, split the task before continuing.
- Bound external commands and provider calls to five minutes or less, with additional cleanup margin around inner deadlines.
- Retry a failed operation at most once, and only after identifying a concrete cause and changing the attempt.
- Stop and re-scope after two failed approaches or 30 minutes without new evidence.
- Keep optional comparisons, unrelated cleanup, downloads, and achievement/streak work outside the critical path.
- Commit completed evidence or behavior, not download percentages or progress-only milestones.
- A failed qualification is a valid result. Record the decision and move on instead of forcing every candidate to succeed.

## Dashboard Pro workflow

Use GitHub issues and pull requests for all `apps/dashboard_pro` work.

1. Open or assign a `Dashboard Pro task` issue.
2. Create a branch from `main` using `feat/dashboard-pro-...` or `fix/dashboard-pro-...`.
3. Open a draft pull request early and link it to exactly one issue.
4. Run:
   - `npm --prefix apps/dashboard_pro run build`
5. Verify the changed UI locally and attach screenshots for visible changes.
6. Wait for review and green CI before merging.
7. If two people worked on the same change, use co-authored commits so the merged PR records both contributors.

## Pairing and co-authored commits

When pairing on a Dashboard Pro change, add a co-author trailer to the commit message:

```text
Co-authored-by: Ammar Yasser <167142494+AmmarYasser72@users.noreply.github.com>
```

Use the matching GitHub noreply address for any other co-author as well. This keeps authorship visible on the merged PR history.

## Review policy

- `main` should stay releasable.
- Dashboard Pro pull requests should be reviewed before merge.
- The required GitHub check is the Dashboard Pro production build.
- Prefer squash merges so the history stays readable.

## Ownership

- `apps/dashboard_pro` reviews route to `@AmmarYasser72` and `@faresmohamed260` through `CODEOWNERS`.
