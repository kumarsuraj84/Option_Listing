# Option Listing — review build

A new preview application based on the agreed option-first rules. The original scripts remain untouched. No original credentials, production extracts or uploaded source files are included.

## Run locally

Python 3.12+ and Node 20.19+ are required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
export OPTION_LISTING_API_KEY="your-generated-secret"
python -m uvicorn app.api:create_app --factory --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/ui/ and enter the configured access key. The frontend keeps the key only in page memory. API documentation is at /docs. SQLite is used for a local preview unless DATABASE_URL is supplied. For PostgreSQL use the environment template; create the database before starting. Do not expose this review build publicly.

For frontend development run `npm run dev` inside frontend; Vite proxies the API to port 8000. The scarcity example is loaded automatically. Upload normalized Supply, Demand and Targets CSV files to replace it. CSV headers are the same field names as the JSON model; sample files are in examples/.

## Agreed allocation rules

- An option is the product/concept identity. Color is a separate field; family groups related colors. Do not use a color-bearing legacy concept string as the product identifier without an approved mapping.
- Required color quantity is grid_sets × pack_size for PLANNED and twice that for READY.
- Every new target gets a first-family coverage attempt before any optional extra families or colors.
- One individual color must supply the full minimum. Partial colors cannot be combined to make a qualifying listing.
- A previous YES store-option stays active and receives no duplicate new listing allocation. Replenishment is a separate workflow.
- PLANNED is processed before READY. Within a phase, scarce options are processed first, then store priority. Color selection uses supplied rank, available quantity and stable identifiers.
- Each demand_group represents one shared store quantity budget across its options and colors. Define it from department, article/price range, MRP, size group and display type. Identifiers must be stable and unambiguous.
- Holdback is outside the eligible allocation pool. It is not automatically a store reserve. Rates are editable and saved with the run.
- Store reserve is assigned quantity minus initial dispatch. The dispatch fraction defaults to unspecified; previews then show no invented reserve quantities. When configured, dispatch rounds down to full packs.
- Additional families and colors are separate opt-in settings, both disabled initially.

## API contract

All operational endpoints require `Authorization: Bearer <key>`.

| Endpoint | Purpose |
| --- | --- |
| GET /health | Connectivity check |
| POST /imports/validate | Validate three CSV strings into normalized inputs |
| POST /runs | Persist an immutable allocation preview; Idempotency-Key header required |
| GET /runs/{id} | Retrieve the saved result |

Repeated identical requests with the same idempotency key return the same run. Different inputs with that key return HTTP 409. A new key creates a new preview, not a dispatch or stock commitment. All runs preserve their policy and input snapshot. Supply, demand and target duplicates are rejected; aggregate source data before import.

## Validation

```bash
python -m pytest -q -s
cd frontend
npm test
npm run build
```

Backend checks cover the scarce-option regression, READY multiplier, multi-color families, minimum quantities, holdback, existing YES, configurable splits, extras, quantity conservation, input order independence, persistent retrieval, concurrent idempotency, authentication, CSV imports and 200 stores. Randomized tests exercise 100 additional quantity scenarios. Frontend tests cover validation, policy submission, results, filtering and stale-result notices.

## Scope and limitations

This is a reviewable allocation preview foundation, not a production rollout. PostgreSQL configuration is included; automated database tests currently use SQLite. The engine is a deterministic greedy heuristic, not a solver guaranteeing the maximum feasible coverage under all competing demand and supply constraints. Uncovered targets are reported explicitly.

Pack size is currently the total unit count from prepack. Exact barcode/size composition validation requires a separate pack-component dataset. Grid sets must be supplied explicitly for each target; grade-to-grid master integration is pending and missing grids are rejected.

Oracle extraction and legacy product identity mapping, grade/grid source joins, LY ranking and eligibility holds, READY family limits, buyer exclusions, durable store reserve balances, actual dispatch/replenishment, release/reassignment rules, roles, approval flow and migrations are pending integrations. Existing YES snapshots must be provided by the caller; the preview does not infer live inventory or subtract historical quantities. Demand inputs must already represent current new-allocation headroom.

Before enabling transactions, confirm the dispatch/reserve policy, family expansion policy and product mapping against representative real data. Production stock commitments need transactional locking and a ledger independent of immutable previews.
