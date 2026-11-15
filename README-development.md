# GCP Billing Monitor — development branch

This branch is a prototype, not deployed. No existing GCP service is modified.

## Sources
- Tesla: `tesla-charge-hub.gcp_billing_monitor`
- My Map: `taycan-evcc.gcp_billing_monitor`

Both datasets must contain standard Cloud Billing export tables (`gcp_billing_export_v1_...`). Until then, the API returns `pending` instead of zero.

## Architecture
FastAPI backend queries BigQuery using Application Default Credentials and a server-side service identity. Static frontend uses HTTPS and a manually entered read token; Scriptable uses the same endpoint. Never place a Google service account key, token, or real billing export in this public repository.

## Deployment prerequisites (not yet performed)
1. Review the least-privilege BigQuery permissions for both projects, without changing the existing evcc service account.
2. Choose an isolated backend runtime and HTTPS endpoint.
3. Configure `BILLING_READ_TOKEN` and `ALLOWED_ORIGINS` privately.
4. Configure rate limiting / scheduled caching before production traffic.
5. Validate cost/credit calculations against Cloud Billing reports and consider invoice-month adjustments.

## Limitations of this first prototype
- No scheduled cache, budget notifications, monthly forecast, service breakdown, or automated tests yet.
- Usage-month cost plus credits is not always equal to final invoice amount; taxes, adjustments, and invoice-month accounting can differ.
- The frontend is not deployed. No production API URL is available.
- Do not enable GitHub Pages for a sensitive dashboard without reviewing its exposure.
