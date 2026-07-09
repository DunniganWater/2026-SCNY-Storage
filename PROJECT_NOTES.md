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

## FIRST DRAFT RESULT (WY 1999–2025, no project portfolio yet)
| | single | four-zone |
|---|---:|---:|
| Basin net observed (AF) | −342,376 | −353,193 |
| Normalized cum 2025 (AF) | −336,518 | −321,098 |
| Observed avg loss rate (AF/yr) | 16,265 | 16,573 |
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
   0.8px stroke. Added: "Color by" mode (loss-rate ramp ↔ categorical zone),
   a zone-boundary overlay (2.6px `#1a1612`, toggleable), and a surface-colour
   hairline between cells (`#fafaf7` @0.9) so cells read as tiles.
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
