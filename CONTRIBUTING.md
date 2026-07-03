# Contributing

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
