# SCNY Region — A Drought-Conditioned Look at Groundwater Storage

**DRAFT.** A groundwater-storage briefing for the SCNY region, prepared by
Larry Walker Associates. It applies a spatial groundwater-storage accounting
methodology (ΔGWE × Sy × Area, sliced by hydrologic year type) in a
**four-zone** framework (CCWD, RD108, Dunnigan, and the SCNY residual
"Other" area).

> **Headline denominators** — sustainable yield (200,000 AF/yr) and total fresh
> groundwater in storage (~10 MAF) — are area-weighted from the Colusa and Yolo
> Subbasin GSPs, scaled to the SCNY footprint (see
> [Headline constants](#headline-constants)). They are context only; the
> volumetric storage-change results (AF and AF/yr) do **not** depend on them.

## Four tabs, one dashboard

A toggle at the top switches between four tabs. The first two build a fixed set
of polygons from the 27 RMS wells; the last two are identical in method but add
the LWA telemetry wells to the network for the recent years.

| Tab | How polygons are built | Cells cross zone lines? |
|---|---|---|
| **Single region-wide tessellation** | One Thiessen tessellation across all 27 RMS wells, clipped to the SCNY region boundary | Yes |
| **Four-zone (per management zone)** | Four independent Thiessen tessellations — one per zone (CCWD, RD108, Dunnigan, Other) — each clipped to its own zone boundary | No — hard seams at zone lines |
| **Single + LWA telemetry** | Single method, plus LWA wells added for 2024–2026 | Yes |
| **Four-zone + LWA telemetry** | Four-zone method, plus LWA wells added for 2024–2026 | No |

All four tabs present a **single hybrid storage timeseries** (see
[The storage timeseries](#the-storage-timeseries)) — there is no separate
observed vs. normalized line. **The two LWA tabs** run the identical pipeline as
their base tab, with a **two-regime** well network: the RMS-only tessellation
governs 1999–2023 exactly as the base method; the LWA telemetry stations
(provisional QA, observed-only) join the tessellation only for **2024–2026**.

**Window: WY 1999–2026.** WY 2026 is an incomplete water year with no official
Sacramento Valley Index type, so it is kept **provisional Above Normal**: its
gaps are filled with the Above-Normal per-type average and it extends the
cumulative, but it is **excluded** from the year-type buckets and from the
per-type averages (those stay over the 26 typed years, 2000–2025).

The four-zone method is the more SMC-defensible framework: a polygon's
hydrology rolls up to the zone where the well physically sits rather than
across boundaries. A zone with a single RMS well (**Dunnigan**, 1 well)
is represented as one dissolved polygon equal to the whole zone boundary.

### Zones and polygon counts

| Zone | Single | Four-zone | Area (acres) |
|---|--:|--:|--:|
| CCWD (Colusa County WD) | 6 | 6 | 45,765 |
| RD108 (Reclamation District 108) | 7 | 7 | 58,714 |
| Dunnigan (Dunnigan WD) | 1 | 1 (aggregate) | 10,421 |
| Other (SCNY residual) | 13 | 13 | 182,058 |
| **SCNY total** | **27** | **27** | **296,958** |

## The two questions this dashboard answers

> **When and where is the region losing water, and what would it take to hold
> the line?**

## Headline finding (WY 1999–2026, 2026 provisional)

Loss is concentrated in drought years, not uniform. Figures are the single
**hybrid** series: region net cumulative through WY 2026 (2026 provisional); avg
loss rates over the typed record (2000–2025):

| Metric | Single | Four-zone | Single + LWA | Four-zone + LWA |
|---|--:|--:|--:|--:|
| Region net (AF) | −423,693 | −377,480 | −423,551 | −377,488 |
| Avg loss rate (AF/yr, typed) | 15,750 | 13,970 | ~16.0k | ~14.5k |

The LWA tabs differ from their base tab only in 2024–2026. With the Feb–April
spring composite, the net LWA increment is small (+143 AF single, −8 AF
four-zone), so the LWA-inclusive totals sit very close to their base tabs.

Storage change by Sacramento Valley Index water-year type (single method,
hybrid series, typed years only):

| Condition | Years | Total ΔStorage (AF) | Avg per year |
|---|--:|--:|--:|
| Wet | 5 | **+625,612** | +125,122 |
| Above Normal | 5 | **+217,809** | +43,562 |
| Below Normal | 5 | **−166,213** | −33,243 |
| Dry | 6 | **−563,990** | −93,998 |
| Critical | 5 | **−522,728** | −104,546 |
| Region net (WY 2000–2025, typed) | 26 | **−409,510** | — |

Year-type classification uses DWR's official **Sacramento Valley Index**
(Northern Sierra 8-Station Index). The typed net (−409,510 AF) plus the
provisional WY2026 step (filled as Above Normal) gives the −423,693 AF region
net above.

## Method, in brief

- **Storage (annual change):** ΔStorage<sub>p,y</sub> = (GWE<sub>p,y</sub> − GWE<sub>p,y-1</sub>) × Sy<sub>p</sub> × Area<sub>p</sub>, summed across polygons into one region series.
- **GWE:** spring composite = **Feb–April mean** of Good-quality DWR records,
  for **every** well (SCNY has no CWSCH wells, so all are treated identically).
- **Specific yield:** a **uniform Sy = 0.10** is applied to every polygon.
  This sits within the Colusa Subbasin GSP's cited unconfined specific-yield
  range of **0.034–0.185** (Olmsted & Davis 1961; Bulletin 118 point value
  0.071). Storage scales linearly with Sy.
- **Area:** computed in EPSG:3310 (NAD-83 California Albers, equal-area),
  honoring holes and multipart geometry. Storage is computed over the
  `no_rangeland` SCNY footprint (296,958 ac).

## The storage timeseries

The dashboard presents **one** cumulative-storage series on every tab — a
**hybrid** of observed and normalized data. Each polygon-year's ΔStorage is
**exactly one of two things**:

1. a **straight observed delta** — used whenever the polygon's well has a Good
   Feb–April spring composite in **both** the year and the year before it
   (consecutive measured years); or
2. a **normalized per-year-type average** — used to fill **every** gap (any year
   without a consecutive observed pair).

The per-year-type averages are built from the polygon's **observed data only** —
the mean of its real consecutive-year deltas within each SVI year type, with
**no interpolation or gap-filling** in the averaging step. Where a type was never
observed, the polygon's overall observed average is used. Each polygon uses only
its own data — no proxying from neighbors, no model fill. This lets every polygon
contribute to every year of the WY 2000–2025 record (year-type mix: 5 Wet,
5 Above Normal, 5 Below Normal, 6 Dry, 5 Critical = 26 transition years),
correcting the drag from late or gappy records without discarding any real
measurement. **WY2026 is provisional Above Normal:** its gaps are filled with the
Above-Normal average and it extends the cumulative, but 2026 is excluded from the
per-type averages and from the typed record (so the 26-year buckets and avg loss
rate are unaffected by it).

## Headline constants

Two numbers frame the deficit but do **not** enter the storage math. Both are
**area-weighted from the two containing subbasins' GSPs**, scaled to the SCNY
footprint. SCNY straddles the Colusa Subbasin (5‑021.52) and the Yolo Subbasin
(5‑021.67): 65% of SCNY's area sits in Colusa (= 26.68% of that subbasin) and
35% in Yolo (= 19.26% of that subbasin).

| Constant | SCNY value | Derivation |
|---|--:|---|
| Sustainable yield | **200,000 AF/yr** | 0.2668 × 500,000 (Colusa GSP §3.3.7) + 0.1926 × 346,000 (Yolo GSP §2.3.7) = 200,021 |
| Total fresh GW in storage | **~10 MAF** | low end of the Colusa GSP freshwater range (26 MAF, §3.2.3) + Yolo GSP (14 MAF, §2.3.6), area-scaled = 9.6 MAF, rounded to 10 (conservative) |

Sources: Colusa Subbasin GSP (Dec 2021, revised Apr 2024; Colusa GA + Glenn GA)
and Yolo Subbasin GSP (2022). Sustainable yield is used only to express rates as
a percent of yield; total storage only in the "how big is the deficit relative
to total storage" proportion figure. The Colusa GSP's freshwater storage range
is wide (26–140 MAF); the low end is used as a conservative denominator.

## Project portfolio

Not yet loaded. Add `data/project_portfolio.json` (per-well AF/yr recharge /
conjunctive-use allocations) and rebuild to populate the 2042 hold-the-line
framing and per-polygon net-coverage map. Until then, recovery margins read
as pure deficit.

## What's in this repo

| Path | Purpose |
|---|---|
| `index.html` | The dashboard — single-file, all SVGs + JS inlined |
| `raw/scny_region.geojson`, `raw/scny_zones.geojson` | SCNY boundary + 4 zones |
| `scripts/build_boundaries.py` | Shapefiles → boundary geojson (derives "Other") |
| `scripts/build_wells.py` | `Colusa_Yolo_RMS.xlsx` → in-boundary, zone-assigned roster |
| `scripts/fetch_measurements.py` | DWR CKAN periodic GWL for the 27 wells |
| `scripts/build_polygons.py` | Thiessen tessellations, both methods |
| `scripts/build_js.py` | `wells-data.js` + `measurements-data.js` |
| `scripts/build_dashboard.py` | Main analysis → per-method JSON/CSV/SVG |
| `scripts/build_html.py` | Single-file `index.html` template (called by build_dashboard) |
| `data/*_{single,four_zone}.*` | Per-method analysis outputs |

## Reproducing

```bash
pip install geopandas shapely pyproj scipy requests pandas openpyxl markdown

python scripts/build_boundaries.py       # shapefiles -> raw/*.geojson
python scripts/build_wells.py            # xlsx -> data/wells_resolved.json (27 in SCNY)
python scripts/fetch_measurements.py     # DWR CKAN -> data/measurements.json
python scripts/build_polygons.py         # -> js/polygons-data-{single,four-zone}.js
python scripts/build_js.py               # -> js/wells-data.js, js/measurements-data.js
python scripts/build_lwa_wells.py        # -> data/lwa_wells.json (LWA telemetry, Feb–Apr composites)
python scripts/build_lwa_methods.py      # -> data/lwa_increment.json, js/lwa-cells-*.js
python scripts/build_dashboard.py        # -> index.html + data/*
```

## Status

Independent draft prepared by Larry Walker Associates for internal review.
Data source: `Colusa_Yolo_RMS.xlsx` (106 RMS wells, filtered to the 27 inside
the SCNY region) and DWR CKAN periodic groundwater levels. Comments and
corrections welcomed.
