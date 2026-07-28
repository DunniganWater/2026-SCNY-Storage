# SCNY Storage Dashboard — Data Contract

What the storage pipeline needs from you before Layer-1 (network) and
Layer-2 (storage) can run. Drop these into `raw/` and tell me; I'll wire
up and test the build scripts against them.

Modeled on the Vina build (`butte_github/2027-BC-prop-network` +
`2027-BC-Storage`), adapted to the SCNY **4-zone** framework.

---

## 1. Well roster  → `raw/scny_wells.csv` (or .xlsx)

One row per well. Every RMS well becomes a Voronoi seed / polygon; other
wells can ride along as supplemental context. **Required** columns:

| Column | Example | Notes |
|---|---|---|
| `well_id` | `13N02W15A001M` | State Well Number or a stable unique name |
| `latitude` | 38.9123 | decimal degrees, WGS84 |
| `longitude` | -121.9876 | decimal degrees, WGS84 (negative = West) |
| `site_code` | `389123N1219876W001` | DWR CASGEM site code — the join key to measurements |
| `zone` | `CCWD` | one of: `CCWD`, `RD108`, `Dunnigan`, `Other` |
| `is_rms` | `TRUE` | TRUE = drives a polygon; FALSE = supplemental context |

**Optional but useful** (carried into the dashboard if present):
`well_depth`, `well_use`, `gse` (ground-surface elev, ft),
`rpe` (reference-point elev, ft), `screen_intervals`, `well_type`.

Notes:
- `zone` is the *network-design* assignment. If a well sits physically in
  one zone but is designed to represent another, put the design zone here —
  I'll preserve the physical-vs-assigned audit trail exactly like Vina did
  for its reassigned wells.
- If you don't have `site_code`, give me `well_id` + lat/lon and I can
  resolve site codes against DWR's station list.

## 2. Measurements — pick ONE

**Option A (you provide):** `raw/scny_gwl.csv` — DWR periodic GWL export
format is ideal (same columns as Vina's `raw/GWLevel_*.csv`):
`SITE_CODE, MSMT_DATE, RPE, GSE, RPE_WSE, WSE, GSE_WSE, WLM_QA_DESC, ...`.
The pipeline reads `SITE_CODE`, `MSMT_DATE`, `WSE` (groundwater elevation),
and `WLM_QA_DESC` (uses **Good** QA only for storage, per Vina methodology).

**Option B (I fetch):** give me just the roster with `site_code`s and I'll
pull periodic GWL from DWR CKAN by site code, same as Vina's
`fetch_dwr_measurements.py`.

## 3. Specific yield

A **uniform Sy = 0.10** is applied to every polygon (user decision). It sits
within the Colusa Subbasin GSP's cited unconfined specific-yield range of
0.034–0.185 (Olmsted & Davis 1961; Bulletin 118 point value 0.071). Storage
scales linearly with Sy.

## 4. Agency constants — confirm these numbers

Used for the headline framing (denominators only; volumetric AF/yr results
don't depend on them):

| Constant | Vina value | SCNY value |
|---|---|---|
| Sustainable yield (AF/yr) | 233,500 | **?** |
| Total fresh groundwater storage (AF) | 16,000,000 | **?** |
| GSP citation label | "Vina Subbasin GSP (Dec 15, 2021), p. ES-5" | **?** |
| Water-year-type index | Sacramento Valley Index (8-station) | same? (SCNY is Sac Valley) |
| Baseline / analysis window | WY 1999–2025 | same? |
| Project portfolio (per-zone AF/yr) | 15,500 total | **? (or defer)** |

## 5. Project portfolio (optional, editable later)

`data/project_portfolio.json` — per-well AF/yr recharge/conjunctive-use
allocations for the 2042 sustainability framing. Can be added/edited any
time and rebuilt; not needed for the first pass.

---

## Status of inputs I already have

- ✅ **Zone boundaries** — built from your shapefiles into
  `raw/scny_zones.geojson` (CCWD, RD108, Dunnigan, Other) and
  `raw/scny_region.geojson`. Run `scripts/build_boundaries.py` to refresh.
- ⬜ Well roster (item 1)
- ⬜ Measurements (item 2)
- ⬜ Agency constants (item 4)
