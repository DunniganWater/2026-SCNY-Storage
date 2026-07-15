# SCNY Region — A Drought-Conditioned Look at Groundwater Storage

**DRAFT.** A groundwater-storage briefing for the SCNY region, prepared by
Larry Walker Associates. It replicates the methodology of the Vina Subbasin
storage dashboard, adapted to a **four-zone** framework (CCWD, RD108,
Dunnigan, and the SCNY residual "Other" area).

> **Placeholder constants.** The headline *denominators* — sustainable yield
> and total fresh groundwater in storage — are **placeholders** pending a
> defensible SCNY-footprint basis (see [Headline constants](#headline-constants)).
> They are context only; the volumetric storage-change results (AF and AF/yr)
> do **not** depend on them.

## Four tabs, one dashboard

A toggle at the top switches between four tabs. The first two build a fixed set
of polygons from the 27 RMS wells; the last two are identical in method but add
the LWA telemetry wells to the network for the recent years.

| Tab | How polygons are built | Cells cross zone lines? |
|---|---|---|
| **Single region-wide tessellation** | One Voronoi tessellation across all 27 RMS wells, clipped to the SCNY region boundary | Yes |
| **Four-zone (per management zone)** | Four independent Voronoi tessellations — one per zone (CCWD, RD108, Dunnigan, Other) — each clipped to its own zone boundary | No — hard seams at zone lines |
| **Single + LWA telemetry** | Single method, plus LWA wells added for 2024–2026 | Yes |
| **Four-zone + LWA telemetry** | Four-zone method, plus LWA wells added for 2024–2026 | No |

**The two LWA tabs** run the identical pipeline (observed gap-fill **and**
year-type-normalized, per-zone summaries, all charts) as their base tab, with a
**two-regime** well network: the RMS-only tessellation governs 1999–2023 exactly
as the base method; the LWA telemetry stations (provisional QA, observed-only,
never backcast) join the tessellation only for **2024–2026**.

**Window: WY 1999–2026.** WY 2026 is an incomplete water year with no official
Sacramento Valley Index type, so it is kept **provisional** — included in the
observed cumulative but excluded from the year-type buckets and from the
normalization's per-type rates (those stay over the 26 typed years, 2000–2025).
The full LWA telemetry network first forms a year-over-year step in the 2025→2026
year, so the LWA tabs' recent-year signal is concentrated there.

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

Loss is concentrated in drought years, not uniform. Region net observed
cumulative through WY 2026 (2026 provisional); avg loss rates are computed over
the typed record (2000–2025):

| Metric | Single | Four-zone | Single + LWA | Four-zone + LWA |
|---|--:|--:|--:|--:|
| Region net observed (AF) | −481,345 | −491,871 | −446,633 | −470,888 |
| Observed avg loss rate (AF/yr, typed) | 21,397 | 21,534 | ~21.2k | ~21.3k |

The LWA tabs differ from their base tab only in 2024–2026 (the years LWA wells
form a step); the 2025→2026 LWA step is a strong recovery (+40k AF single), so
the LWA-inclusive cumulative is a smaller net deficit.

Storage change by Sacramento Valley Index water-year type (single method,
typed years only):

| Condition | Years | Total ΔStorage (AF) | Avg per year |
|---|--:|--:|--:|
| Wet | 5 | **+305,035** | +61,007 |
| Above Normal | 5 | **+172,963** | +34,593 |
| Below Normal | 5 | **−181,380** | −36,276 |
| Dry | 6 | **−325,690** | −54,282 |
| Critical | 5 | **−422,738** | −84,548 |
| Region net (WY 2000–2025) | 26 | **−451,810** | — |

Year-type classification uses DWR's official **Sacramento Valley Index**
(Northern Sierra 8-Station Index).

## Method, in brief

- **Storage:** ΔStorage<sub>p,y</sub> = (GWE<sub>p,y</sub> − GWE<sub>p,baseline</sub>) × Sy<sub>p</sub> × Area<sub>p</sub>.
- **GWE:** spring composite (March mean, Good-quality DWR records only) of the
  polygon's RMS well. Each polygon is baseline-anchored to the first WY
  1999–2025 year with a Good March measurement.
- **Specific yield:** a **uniform Sy = 0.10** is applied to every polygon.
  A per-polygon Sy derived from DWR's SVSim Texture Data (Sacramento Valley
  Simulation Model — coarse-grained sediments → 0.15, fine-grained → 0.05,
  area-weighted by borehole lithology over the 0–500 ft below-ground window,
  ≥200 ft of valid lithology per borehole) is still computed by
  `scripts/build_sy_svsim.py` and written to `data/polygon_sy_svsim_*.csv`
  for reference. All 27 polygons resolve there (no fallbacks), ranging
  **0.0565–0.0986** with an area-weighted mean of **≈0.077**. That basis is
  *not* used for the numbers on this page. Storage scales linearly with Sy,
  so the SVSim basis would give a deficit roughly **30% smaller**.
- **Area:** computed in EPSG:3310 (NAD-83 California Albers, equal-area),
  honoring holes and multipart geometry. Storage is computed over the
  `no_rangeland` SCNY footprint (296,958 ac).
- **Gap attribution:** multi-year gaps in a polygon's Good measurements are
  distributed evenly across the missing years and bucketed by each year's
  hydrologic condition.

## Year-type-weighted normalization

Not every polygon has a Good March measurement in WY 1999; several baseline
later (or end their record early), so the raw **observed** region cumulative
*understates* the deficit — late/short-record polygons can't register their
full drawdown. The **normalized** series corrects this: for each polygon we
compute an average ΔStorage rate *per SVI year type* using only that
polygon's own observations, then apply those per-type rates to the region's
full WY 2000–2025 year-type mix (5 Wet, 5 Above Normal, 5 Below Normal,
6 Dry, 5 Critical = 26 transition years). Each polygon uses only its own
data — no proxying from neighbors, no model fill.

## Headline constants

Two numbers frame the deficit but do **not** enter the storage math:

| Constant | Draft placeholder | Real basis needed |
|---|--:|---|
| Sustainable yield (AF/yr) | 200,000 | SCNY-footprint yield (no published sub-region value) |
| Total fresh GW in storage | 10 MAF | Colusa Subbasin GSP reports 26–140 MAF over the whole 723,823-ac subbasin; SCNY is ~297k ac of that — needs area-scaling or a project figure |

Sustainable yield is used only to express rates as a percent of yield. Total
storage is used only in the "how big is the deficit relative to total
storage" proportion figure. Swap real figures + a GSP citation before this
goes external.

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
| `scripts/build_polygons.py` | Voronoi tessellations, both methods |
| `scripts/build_sy_svsim.py` | Per-polygon Sy from SVSim Texture Data |
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
python scripts/build_sy_svsim.py         # -> data/polygon_sy_svsim_*.csv
python scripts/build_js.py               # -> js/wells-data.js, js/measurements-data.js
python scripts/build_lwa_wells.py        # -> data/lwa_wells.json (LWA telemetry, March composites)
python scripts/build_lwa_methods.py      # -> data/lwa_increment.json, js/lwa-cells-*.js
python scripts/build_dashboard.py        # -> index.html + data/*
```

## Status

Independent draft prepared by Larry Walker Associates for internal review.
Data source: `Colusa_Yolo_RMS.xlsx` (106 RMS wells, filtered to the 27 inside
the SCNY region) and DWR CKAN periodic groundwater levels. Comments and
corrections welcomed.
