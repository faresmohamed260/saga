# Protected Test Assets

This document records private or copyrighted assets used for S.A.G.A. validation. It intentionally stores metadata, not the asset bytes.

Machine-readable asset metadata lives in `docs/operations/protected_assets.manifest.json`. Current external-readiness evidence is recorded in `../validation/PHASE_0_EXTERNAL_READINESS_2026-09-10.md`.

## Rules

- Do not commit commercial EPUB/PDF/book files to the public repository.
- Do not upload protected books as public workflow artifacts.
- GitHub Actions may use protected books only through an authorized S.A.G.A.-owned private storage path, verify SHA-256, run the gated test, and delete the temporary copy.
- Tests that require protected assets must skip or fail with a bounded diagnostic reason when the asset is unavailable.
- Secret-name presence alone is not proof that credentials belong to the S.A.G.A. protected-assets bucket.

## Assets observed locally during recovery

| Filename | Format | SHA-256 | Purpose | Redistributable | Intended CI storage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `Once Upon a Broken Heart.epub` | EPUB | `89F8E1A7DD808A8D40280608F5499F520FDF16AA01206F7A5F62AFED9247B7A5` | Historical full production qualification input | No | S.A.G.A.-owned private object storage | Metadata recorded; historical run means freshness must be rechecked against production persistence. |
| `The Lost Sisters.epub` | EPUB | `38AC0F672B820EB3D9347BA4587FDE9AD1859F87C46434561D253D391F46AF90` | Identity/runtime/live validation reference | No | S.A.G.A.-owned private object storage | Metadata recorded; current private availability not yet proven. |
| `A Court of Thorns and Roses.epub` | EPUB | `FAFCB0E4420BA70C6E1F78749882CBFF2E3B6D2207A62305F10F9996A1033BCF` | Local ACOTAR pipeline configuration | No | S.A.G.A.-owned private object storage if corpus remains active | Metadata recorded; current private availability not yet proven. |
| `A Court of Mist and Fury.epub` | EPUB | `10A2CBB71FFEA040CEA51BCC2D6D20F1602B3D3BD731F0436022F5C82A194FBB` | Local ACOTAR pipeline configuration | No | S.A.G.A.-owned private object storage if corpus remains active | Metadata recorded; current private availability not yet proven. |
| `A Court of Wings and Ruin.epub` | EPUB | `4D8D79FE1B0B3DF3F01F335BB79C78D41CBD8B1765280E820A657CBFD1FB7A0F` | Local ACOTAR pipeline configuration | No | S.A.G.A.-owned private object storage if corpus remains active | Metadata recorded; current private availability not yet proven. |
| `A Court of Frost and Starlight.epub` | EPUB | `5A02FA8D59425B265A86D022BED9025D3BA3B29E30D892D777300B7758812FB3` | Local ACOTAR pipeline configuration | No | S.A.G.A.-owned private object storage if corpus remains active | Metadata recorded; current private availability not yet proven. |
| `A Court of Silver Flames.epub` | EPUB | `D1A17DFE07AFBA50097519A3267099B75EFEFDB2056B53E2901D6935AB905E60` | Local ACOTAR pipeline configuration | No | S.A.G.A.-owned private object storage if corpus remains active | Metadata recorded; current private availability not yet proven. |

## Secure CI acquisition pattern

1. Workflow checks that protected-storage credentials are present.
2. Workflow selects the matching Cloudflare R2 jurisdiction endpoint.
3. Workflow verifies that configured credentials can list the exact manifest prefix without printing the listing.
4. Workflow distinguishes account/bucket/credential/jurisdiction access failure from a missing object.
5. Workflow downloads the exact selected object into runner temporary storage.
6. Workflow computes SHA-256 and compares it to the committed manifest.
7. Workflow deletes the temporary file in an always-run cleanup step.
8. Clean-source qualification separately proves the selected source is fresh against S.A.G.A. production persistence before live provider work.

Current paths:

- `.github/workflows/protected-asset-verification.yml`
- `scripts/check_protected_asset_storage.py`
- `scripts/verify_protected_assets.py`
- `.github/workflows/production-qualification.yml`
- `scripts/check_production_qualification_readiness.py`

Protected asset verification is manual-only through `workflow_dispatch`. It supports `default`, `eu`, `us`, and `fedramp` R2 jurisdiction endpoints, never uploads protected bytes as artifacts, and removes temporary files.

## Diagnostic categories

The storage helper intentionally emits only bounded categories and selected manifest metadata. It does not print R2 credentials, account ids, bucket names, object listings, or protected bytes.

- `access_failed` — configured credentials could not list the protected manifest prefix; verify account, bucket, jurisdiction, token scope, and Object Read/List access.
- `object_missing` — listing succeeded but the exact manifest object key is absent.
- `download_failed` — the object was visible but GetObject/download failed.
- successful download — independent SHA-256 verification must still pass.

## Current remote evidence — 2026-09-10

### Historical pre-PR-141 result

Run `34432226628`, dispatched for `once-upon-a-broken-heart`, reached the old R2 path and received `403 Forbidden` from `HeadObject`. That result was ambiguous and must not be interpreted as proof that the object was missing.

### Revised bounded diagnostic

After PR #145, read-only diagnostic run `34514460132` used the current bounded helper with the configured repository R2 secret names across every supported jurisdiction:

| Jurisdiction | Result |
| --- | --- |
| `default` | `access_failed` |
| `eu` | `access_failed` |
| `us` | `access_failed` |
| `fedramp` | `access_failed` |

Aggregate:

```text
R2_PROBE_RESULT status=no_accessible_jurisdiction
```

The failure is therefore **before individual object diagnosis**. Current evidence supports an account/bucket/credential/token-scope access blocker. Do not label any manifest object `object_missing` until bucket listing succeeds on the correct endpoint.

No asset bytes were published, and no paid providers were called by this diagnostic.

## R2 namespace provenance

Historical pre-retirement source at commit `1944ea3a1c7d6733236869cec2e030dad4fdd470` shows retired `apps/studio/api/_r2.js` used exactly:

- `R2_ACCOUNT_ID`
- `R2_BUCKET_NAME`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`

and defaulted `R2_BUCKET_NAME` to `saga-studio-media`.

This proves the **configuration namespace was used by the retired Studio product**. It does not prove the current GitHub secret values are identical because GitHub does not expose secret values. These generic names must be deliberately reconfigured/rotated to a S.A.G.A.-owned protected-assets target instead of being trusted merely because they are populated.

## Current blocker / repair path

Issue #142 remains open.

Before clean-source qualification:

1. configure/rotate R2 credentials so a S.A.G.A.-owned private bucket/prefix is accessible with bounded List/Get permissions;
2. rerun `Protected Asset Verification` and obtain a successful bucket-access category;
3. classify the selected object's presence/download state only after bucket access works;
4. verify SHA-256 against the committed manifest;
5. configure the real S.A.G.A. production persistence path and prove the selected source is unseen by filename/SHA;
6. if every current manifest asset is stale in production, add metadata for another authorized unseen source and place only its bytes in private storage;
7. only then separately authorize paid/live production qualification.

The earlier generic `SAGA_PROTECTED_ASSET_STORAGE_*` naming remains a future provider-neutral option if explicitly adopted. The current workflows use `R2_*`, but those names now carry an explicit ownership warning because of their Studio-era provenance.