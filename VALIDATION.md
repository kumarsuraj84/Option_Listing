# Review build validation

Executed 2026-10-03 against synthetic data. Original production scripts were not changed.

| Check | Result |
| --- | --- |
| Engine and API tests | 26 passed |
| Randomized conservation scenarios within the tests | 100 scenarios passed |
| React interaction tests | 3 passed |
| TypeScript check and frontend build | Passed |
| Synthetic scale | 200 stores, 600 targets, 7,200 assigned units, full coverage |
| Concurrent identical API requests | Eight requests returned one saved run |
| Scarce-option regression | Both stores received A, B and C with one full color each |

The test API database is SQLite. PostgreSQL execution, Oracle connectivity, production extracts, real size composition, browser visual UAT and warehouse dispatch have not been validated. These results establish a preview foundation, not production readiness.

## Scarcity example

PLANNED pack 12, grid 1, shared demand 36 per store. A has 200 units per color, B 180, C 20. With 40% holdback, C has exactly 12 Black and 12 White units eligible.

| Store | Option A | Option B | Option C | Assigned |
| --- | --- | --- | --- | --- |
| S0 | Black 12 | Black 12 | Black 12 | 36 |
| S1 | Black 12 | Black 12 | White 12 | 36 |

Both stores cover all three options. The original engine gave the second store an extra B family while C was uncovered in this scenario. The new engine processes scarce C first, and completes coverage attempts before extras.

## Remaining decisions and integration

- Confirm initial dispatch fraction and how store reserves may be released or reassigned.
- Approve the product ID mapping separately from colors and families.
- Confirm which optional extra families/colors policies should be enabled.
- Connect current stock, existing listings, pack components and grade/grid data.
- Implement a transactional reserve ledger and dispatch/replenishment workflow before operational use.
