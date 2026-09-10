# Protected Test Assets

This document records private or copyrighted assets used for S.A.G.A. validation. It intentionally stores metadata, not the asset bytes.

Machine-readable asset metadata lives in `docs/operations/protected_assets.manifest.json`.

## Rules

- Do not commit commercial EPUB/PDF/book files to the public repository.
- Do not upload protected books as public workflow artifacts.
- GitHub Actions may use protected books only through an authorized private storage path, verify SHA-256, run the gated test, and delete the temporary copy.
- Tests that require protected assets must skip with a clear reason when the asset is unavailable.

## Assets observed locally

| Filename | Format | SHA-256 | Purpose | Redistributable | Intended CI storage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `Once Upon a Broken Heart.epub` | EPUB | `89F8E1A7DD808A8D40280608F5499F520FDF16AA01206F7A5F62AFED9247B7A5` | Last recorded full production qualification input | No, commercial book | Private object storage bucket/prefix configured through protected-asset secrets | Metadata recorded; bytes not migrated. |
| `The Lost Sisters.epub` | EPUB | `38AC0F672B820EB3D9347BA4587FDE9AD1859F87C46434561D253D391F46AF90` | Identity/runtime/live validation reference | No, commercial book | Private object storage bucket/prefix configured through protected-asset secrets | Metadata recorded; bytes not migrated. |
| `A Court of Thorns and Roses.epub` | EPUB | `FAFCB0E4420BA70C6E1F78749882CBFF2E3B6D2207A62305F10F9996A1033BCF` | Local ACOTAR pipeline configuration | No, commercial book | Private object storage if this corpus remains active | Metadata recorded; bytes not migrated. |
| `A Court of Mist and Fury.epub` | EPUB | `10A2CBB71FFEA040CEA51BCC2D6D20F1602B3D3BD731F0436022F5C82A194FBB` | Local ACOTAR pipeline configuration | No, commercial book | Private object storage if this corpus remains active | Metadata recorded; bytes not migrated. |
| `A Court of Wings and Ruin.epub` | EPUB | `4D8D79FE1B0B3DF3F01F335BB79C78D41CBD8B1765280E820A657CBFD1FB7A0F` | Local ACOTAR pipeline configuration | No, commercial book | Private object storage if this corpus remains active | Metadata recorded; bytes not migrated. |
| `A Court of Frost and Starlight.epub` | EPUB | `5A02FA8D59425B265A86D022BED9025D3BA3B29E30D892D777300B7758812FB3` | Local ACOTAR pipeline configuration | No, commercial book | Private object storage if this corpus remains active | Metadata recorded; bytes not migrated. |
| `A Court of Silver Flames.epub` | EPUB | `D1A17DFE07AFBA50097519A3267099B75EFEFDB2056B53E2901D6935AB905E60` | Local ACOTAR pipeline configuration | No, commercial book | Private object storage if this corpus remains active | Metadata recorded; bytes not migrated. |

## Secure CI acquisition pattern

1. Workflow checks for protected-asset secrets.
2. Workflow downloads the exact object from private storage into a temporary path.
3. Workflow computes SHA-256 and compares it to this manifest.
4. Workflow runs only the tests explicitly requiring that asset.
5. Workflow deletes the temporary file in an always-run cleanup step.

Current workflow:

- `.github/workflows/protected-asset-verification.yml`

It is manual-only through `workflow_dispatch`. It uses the existing Cloudflare R2 repository secret names, downloads selected objects into `$RUNNER_TEMP`, verifies hashes with `scripts/verify_protected_assets.py`, and removes the temporary directory in an `always()` cleanup step. It does not upload protected assets as artifacts.

First remote verification evidence:

- GitHub Actions run `34432226628`, dispatched on 2026-09-10 for `once-upon-a-broken-heart`, reached the R2 download step with the required repository secrets present.
- R2 returned `403 Forbidden` on `HeadObject` for the documented object key. Treat protected-asset CI as wired but not yet operational until the R2 object key and read permissions are corrected, then rerun the workflow.

Supported workflow variables:

- `R2_ACCOUNT_ID`
- `R2_BUCKET_NAME`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`

The earlier generic `SAGA_PROTECTED_ASSET_STORAGE_*` names remain acceptable aliases if the repository later abstracts away from Cloudflare R2, but the current workflow uses the observed R2 secrets.
