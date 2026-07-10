# SCNY Storage Dashboard — Project Notes

A drought-conditioned groundwater storage dashboard for the **SCNY region**,
built with the same methodology as the Vina Subbasin dashboard
(`butte_github/2027-BC-Storage`), adapted to a **4-zone** framework.

## Zones (4)
CCWD, RD108, Dunnigan, and **Other** (SCNY residual = region minus the three
named districts). Analogous to Vina's three management areas, but four.

## Two-layer architecture (mirrors Vina)
- **Layer 1 — Network build** (Vina's `2027-BC-prop-network`): well roster +
  boundaries → Voronoi polygons (single basin-wide + per-zone), wells JS,
  measurements JS.
- **Layer 2 — Storage build** (Vina's `2027-BC-Storage`): polygons + SVSim
  Sy + measurements → ΔStorage, SVI year-type buckets, year-type-weighted
  normalization, 2042 project portfolio, single-file `index.html` with a
  **single ↔ 4-zone toggle**.

Ported into one self-contained SCNY repo (no separate prop-network repo) to
avoid maintaining two coupled repos for a new agency.

## Progress
- [x] Confirmed scope with user: full replica, 4 zones, SCNY-wide.
- [x] `scripts/build_boundaries.py` → `raw/scny_zones.geojson` (4 disjoint
      zones, clipped to SCNY, tiling exactly) + `raw/scny_region.geojson`.
- [x] Well roster: `scripts/build_wells.py` reads `../Colusa_Yolo_RMS.xlsx`
      (106 RMS wells, all "SGMA Representative"), spatially filters to SCNY
      → **27 wells inside** (79 excluded, in `data/wells_excluded.csv`),
      zone-assigned. `data/wells_resolved.json`.
      Zones: Other 13 / RD108 7 / CCWD 6 / **Dunnigan 1**.
- [x] Measurements: `scripts/fetch_measurements.py` pulls DWR CKAN periodic
      GWL for the 27 site_codes → `data/measurements.json` (24,391 records,
      all 27 wells; every well has ≥1 Good-QA March record).
- [x] Polygons: `scripts/build_polygons.py` builds BOTH methods with
      `shapely.voronoi_polygons` (ordered), clipped to region / zone
      boundaries, Dunnigan (1 well) as a dissolved aggregate. Output
      `js/polygons-data-single.js` + `js/polygons-data-four-zone.js`.
      Both: 27 polygons, geometrically valid, total area = 296,958 ac exactly.
      Rings emitted as nested multipolygon+holes (Leaflet convention);
      lightly simplified for display (15 m tol, drop <2 ac slivers/holes) —
      area_acres computed from FULL unsimplified Albers geometry.
- [x] Sy: `scripts/build_sy_svsim.py` (requests download to temp, nested-rings
      loader) → `data/polygon_sy_svsim_{single,four_zone}.csv`. All 27 polygons
      got a real SVSim Sy (0 fallbacks), range ~0.056–0.099.
- [x] JS wrappers: `scripts/build_js.py` → `js/wells-data.js` +
      `js/measurements-data.js`.
- [x] Ported `build_dashboard.py` + `build_html.py` (copied from Vina, then
      edited: local paths, METHODS=[single,four-zone], `flatten_rings()` shim
      for nested rings + fill-rule:evenodd, SCNY labels/titles, placeholder
      constants). **`index.html` builds and renders** — toggle works, 6 charts,
      2 interactive Leaflet maps (54 polys), headline numbers compute.
- [~] Constants: researched — Colusa Subbasin GSP gives storage 26–140 MAF over
      the WHOLE 723,823-ac subbasin (not the 297k-ac SCNY footprint); no
      published sub-region sustainable yield. So still PLACEHOLDER
      (SY=200k AFY, storage=10 MAF). Needs a project-specific basis
      (area-scale the subbasin figure to the SCNY footprint, or a GSP number).

## RESULT (WY 1999–2025, uniform Sy=0.10, no project portfolio yet)
| | single | four-zone |
|---|---:|---:|
| Region net observed (AF) | −451,810 | −460,903 |
| Normalized cum 2025 (AF) | −438,402 | −410,732 |
| Observed avg loss rate (AF/yr) | 21,397 | 21,534 |

**Sy = 0.10 uniform** (user decision 2026-07-09), replacing SVSim per-polygon
(0.0565–0.0986, area-weighted mean 0.0766/0.0771). Storage scales linearly with
Sy, so this raised the deficit ~32% (was −342,376 / −353,193 AF).
`build_sy_svsim.py` still runs and writes `data/polygon_sy_svsim_*.csv` for
reference; the dashboard no longer consumes it (`load_sy()` returns SY_UNIFORM).

**Map labels** now follow the Vina convention: `zone[6:11]` → `07G00`.
Aggregates keep their name (`Dunnigan`) rather than copying Vina's bug, where
`"02-Vina-Chico"[6:11]` renders as `a-Chi`. The Vina slice still collides for
`10N02E03R002M` / `12N01E03R002M` (both `03R00`), so those keep a township
prefix: `10N 03R00` / `12N 03R00`. 27/27 unique.
Preview: `python -m http.server` in the repo, open index.html (launch.json
"scny-storage" in butte_github/.claude). NOTE: screenshot tool stalls on
Leaflet CDN tiles — verified structurally instead; renders in a real browser.

## LIVE
GitHub Pages: https://cferg2568.github.io/2026-SCNY-Storage/
(`.nojekyll` commit was what triggered the first Pages build.)

## LWA telemetry wells (`../stn_scny/`) — EVALUATED, PARKED 2026-07-09
41 LWA telemetry stations + 22,432 measurements (`stn_scny.shp`,
`stn_scny_meas.xlsx`, joined on `well_code`). 40 inside SCNY, 1 outside,
`COL_120` has no measurements. No CASGEM overlap with the 27 RMS wells.
Zone split inside: RD108 16 / Dunnigan 10 / CCWD 9 / Other 5.

**Not incorporated.** Reasons (re-check these when final data arrives):
- **QA:** 100% of rows are "Provisional transducer data; reference point
  accuracy TBD" — the storage pipeline is Good-QA-only.
- **Record length:** dataset spans Oct 2022–Jul 2026, but wells came online in
  waves (2 in 2022, 8 in 2023, 5 in 2024, **25 in 2025**); median per-well span
  is 1.47 yr. Within the WY1999–2025 window only **10 of 40** can form even one
  year-over-year ΔStorage step; 25 are baseline-only (contribute exactly zero).
- **Area dilution:** as Voronoi seeds they capture **103,518 ac = 34.9%** of
  SCNY, shrinking RMS polygons 296,958 → 193,440 ac. Since basin cumulative is
  a sum of per-polygon cumulatives and these cells contribute ~0 before 2023
  (user directed: no backcasting/filling for provisional data), the historical
  deficit would mechanically drop ~1/3 (≈ −342k → ≈ −222k AF) as an *artifact*.
- **Conclusion:** historical (1999–2025) analysis should stay on the 27-RMS
  tessellation (full coverage, long records). The 66-seed tessellation is the
  right basis for a *recent-period* (2023–2026) product, where all wells have
  data — but WY2026 has no official SVI year type yet.
- Data flag: `wlm_org_name` reads "LWA for Siskiyou GSA" on all 22,432 rows,
  which looks like a copy/paste artifact for Colusa/Yolo wells. Worth confirming.

## Remaining to go from draft → final
- Real agency constants (above).
- `data/project_portfolio.json` (per-well AF/yr) for the 2042 framing —
  currently empty, so recovery margins show as pure deficit.
- Prose scrub: ~21 Vina-isms left in `build_html.py` ("basin" → "region", etc.).
- ~~Fix map section-letter labels~~ DONE (section+letter, township prefix on collisions).
- ~~Rangeland holes~~ N/A — the region is a single solid polygon with ZERO holes.

## Map rendering — fixed 2026-07-09
Three separate defects, all in the rendering layer (storage numbers unaffected):
1. **Geometry.** Per-cell `simplify(15m)` made neighbours disagree on shared
   edges → 81-112 ac of gaps in ~600 pieces + 18.9 ac overlap (four-zone), and
   naive lat/lon rounding self-intersected 2 parts of `13N01W07G001M`.
   Fix: snap to a uniform 1 cm grid in EPSG:3310 before reprojecting, emit at
   7 decimals, `make_valid()` net. Now 0 invalid, gaps ~0.1 ac, overlap 0.01 ac.
   Removed MIN_PART_ACRES/MIN_HOLE_ACRES — measured to drop nothing.
2. **Zoom.** `initMap` ran `fitBounds` before layout; later `invalidateSize()`
   re-measured the container but KEPT the stale zoom, so the region sat as a
   small blob using ~30% of the frame. Fix: `fitMapExtent()` = invalidateSize +
   re-fit, guarded by `map._needsFit` so a user's pan/zoom isn't clobbered.
   Region now fills 92% of map height.
3. **Legibility.** No way to see the zones; 27 cells all wore the same dark
   0.8px stroke. Added: "Color by" mode (loss-rate ramp ↔ categorical zone) and
   a zone-boundary overlay (2.6px `#1a1612`, toggleable, **four-zone only** —
   single-method cells cross zone lines by design). Cells share their edges,
   divided by a fine muted hairline (`#5b5547` @0.6, opacity 0.9), bold
   (`#1a1612` @2.4) on hover/flash. A surface-colour hairline was tried first
   and reverted: on a choropleth adjacency IS the data, and a light stroke
   straddling a shared edge reads as a gap where the tessellation has none.
   Zone palette validated with the dataviz six checks (`--pairs all`, surface
   `#fafaf7`): CVD ΔE 13.3, all four ≥3:1 contrast.
   Other=#2a78d6 blue, CCWD=#4a3aa7 violet, RD108=#008300 green,
   Dunnigan=#e34948 red. Legend swaps with the mode.
`build_polygons.py` now also emits `js/zone-boundaries.js` (the 4 zone outlines).
- Note: several RMS wells stop reporting early (13N01W22P002M ends 2008,
  13N02W15J001M 2014, 14N02W29J001M 2015) — those polygons freeze and contribute
  nothing after their last reading. Same drag, opposite end of the record.

## Storage-basis note (needs a nod from user)
Storage is computed over the **`02_SCNY_Region_v3_no_rangeland` footprint =
296,958 ac** (rangeland excluded). The workbook's full SCNY attribute is
342,779 ac, but only the no_rangeland geometry exists as a shapefile.
Storage volumes scale with polygon area, so this footprint IS the storage
basis. If a full-area (incl. rangeland) basis is wanted, provide that boundary.

## Roster caveats to resolve with user
- Only 27 of 106 workbook wells fall inside SCNY. Nearest excluded well
  (`10N03E33B011M`) is just 108 m outside the boundary — confirm exclude.
- **Dunnigan zone = 1 well** (`12N01W05B001M`). Like Vina's Chico, this zone
  becomes a single dissolved polygon driven by one well.
- Several wells end their record early (March spans ending 2008–2022) — same
  late-baseline/gap issue Vina's normalization addresses.
- Agency constants still needed (sustainable yield, total storage, GSP cite).

## Zone geometry notes / caveats
- Named districts poke ~1,199 ac outside the SCNY `no_rangeland` boundary;
  `build_boundaries.py` clips them to SCNY so zones tile with zero gap.
- Areas after clip: CCWD 45,765 / RD108 58,714 / Dunnigan 10,421 /
  Other 182,058 / SCNY 296,958 acres.
- Dunnigan area: use the shapefile GEOMETRY area (11,060 ac raw / 10,421
  clipped) — confirmed correct by user. The `.dbf acres_lwa` (5,586) is the
  inaccurate one and is ignored (we never read it). RESOLVED.
- SCNY `.dbf lwa_acres` (342,779) > geometry area (296,958) because the
  `_no_rangeland` shapefile has rangeland removed. Using geometry area.

## Source of truth
Reference implementation:
`butte_github/2027-BC-Storage/` (README.md has the full methodology) and
`butte_github/2027-BC-prop-network/` (polygon + measurement builds).

## Per-zone storage summaries (four-zone only) — added 2026-07-09
`compute_method()` now rolls polygons up by `mgmt_area` into `zone_summaries`
(also written to `data/zone_summaries_{single,four_zone}.json`). Aggregated the
same way as the region totals: cumulative = sum of each polygon's endpoint
cumulative; avg loss rate = sum of each polygon's own avg rate (NOT cum/span,
which is wrong with staggered baselines).

Rendered inside the "Annual region time series" details, four-zone only —
in the single tessellation cells cross zone lines, so a cell's storage can't be
attributed wholly to one zone. Two additions: a per-zone summary table (polys,
area, observed + normalized cumulative, observed + normalized loss rate, and the
5 SVI year-type buckets) with a Region-total row, and per-zone ΔStor columns in
the annual table. Verified: zone sums reconcile to region totals to ±1 AF.

| zone | polys | area ac | cum AF | norm AF | rate AF/yr |
|---|--:|--:|--:|--:|--:|
| CCWD | 6 | 45,765 | −180,538 | −186,176 | 9,595 |
| RD108 | 7 | 58,714 | −46,532 | −54,159 | 1,895 |
| Dunnigan | 1 | 10,421 | −42,789 | −42,789 | 1,646 |
| Other | 13 | 182,058 | −191,045 | −127,608 | 8,398 |
| **Region** | **27** | **296,958** | **−460,903** | **−410,732** | **21,534** |

Note CCWD carries 39% of the deficit on 15% of the area; Other has 61% of the
area but 41% of the deficit.

## Third method: Annual dynamic network — added 2026-07-09
User asked to bring in the LWA telemetry wells via a NEW approach (not gap-fill
or normalized): re-tessellate every year on only the wells available that year,
so every year covers the full region. Directly answers the area-drift critique
(observed method's coverage swings 65-95%/yr; this is 100% every year).

Decisions (user, 2026-07-09): chained year-over-year (each step = wells present
in BOTH that year and the prior, tessellated fresh, ΔStorage summed); March
spring composite (match RMS); window stays WY 1999-2025; Sy = 0.10.

New scripts:
- `build_lwa_wells.py`: stn_scny.shp + stn_scny_meas.xlsx -> data/lwa_wells.json.
  40 stations inside SCNY; 35 have in-window March data (2 in 2023, 10 in 2024,
  35 in 2025). QA relaxed (provisional transducer data). well_id = well_code.
- `build_dynamic.py`: chained YoY over RMS+LWA pool -> data/annual_dynamic.json
  (26-row time series, every year 100% area) + js/dynamic-latest.js (the
  2024->2025 tessellation, 27 cells = 17 RMS + 10 LWA, validated 0 invalid).

Result: chained cumulative to 2025 = **-271,621 AF**, avg 10,865 AF/yr — notably
smaller than observed (-451,810) or normalized (-438,402) for single. It's a
different estimator, not more precise. Caveats surfaced on the page:
- Low-well-year noise: 2004/2006/2011/2012 rest on ≤8 wells over the whole
  region (min 3 in 2006); a few wells swing a full-region number (e.g. 2023
  Wet +362k on 8 wells).
- LWA only enters the final steps: chained needs 2 consecutive years and most
  LWA March data is 2025/2026, so only ~10 LWA wells reach the 2024->2025 step
  within the 2025 window.

Integration: third toggle button + section (banner, headline, caveat, 26-row
annual table, latest-year map colored by source RMS=blue/LWA=orange).
build_html gained _render_dynamic_section() and a dynamic branch in
buildPopupHtml(); initMap reused (tolerant of the controls dynamic omits).
NOTE: could not live-test the third Leaflet map (chrome ext disconnected);
verified statically (section content, 26 rows, tessellation validity).
