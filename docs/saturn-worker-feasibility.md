# Saturn Cloud GPU worker feasibility

Date: 2026-08-25
Branch: `experiment/saturn-worker`

## Outcome

Saturn Cloud authentication and the current API/recipe schema were validated successfully, but the current Saturn Community account cannot start GPU resources. The account currently has a maximum resource-hours quota of `0`, so Saturn is not a usable live worker backend for SAGA under the current plan.

No paid resource was started, and the experiment did not touch production.

## Evidence

### Authentication and inventory

The refreshed `SATURN_TOKEN` authenticated successfully against:

`https://app.community.saturnenterprise.io`

The authenticated instance inventory exposed community GPU shapes including:

- `g4dnxlarge` — 1x NVIDIA T4, 4 CPU cores, 16 GB RAM, listed at $0.795/hour.
- `g5xlarge` — 1x NVIDIA A10G, 4 CPU cores, 16 GB RAM, listed at $1.50/hour.
- Additional larger T4 and A10G shapes were also listed by the API.

Inventory visibility is not the same as account entitlement.

### A10G entitlement probe

Run: `32791672707`

The probe selected `g5xlarge` (A10G). Saturn rejected creation for this account with an instance-size limit indicating that only `g4dnxlarge` was currently allowed and that the organization limit for the requested A10G size was `0`.

The Workspace fallback was also unavailable because the organization Workspace disk quota is `0 GiB`.

### Allowed T4 deployment probe

Run: `32791768238`
Job: `97634564514`

The probe selected the account-allowed `g4dnxlarge` T4 shape and Saturn accepted the recipe far enough to create a Deployment object. Starting that Deployment was then rejected by the account plan with:

- code: `organizationResourceHoursExceeded`
- current usage: `0`
- maximum: `0`
- message: `Your current plan does not allow you to start resources`

The Workspace fallback again failed because the Workspace disk organization limit is `0 GiB`.

The temporary Deployment object was cleaned up by the probe. The delete request returned HTTP `204`.

### Final orphan-resource check

Run: `32791946142`

A final read-only authenticated inventory looked specifically for resources whose names contain `saga-worker-probe`.

Result:

- probe resource count: `0`
- probe resources: `[]`

No temporary Saturn probe resources remain.

## Conclusion

The technical integration path is viable at the API level: authentication works, the current Saturn client works, the recipe is accepted, and a Deployment object can be created. The blocker is account entitlement, not application code.

Saturn Community cannot currently replace the existing GPU worker backend because the account has zero runnable resource-hours. A live HTTP worker endpoint and an LTX generation benchmark therefore cannot be produced on this account without enabling a plan/quota that permits GPU resource-hours.

No paid or external-cluster allocation was attempted.
