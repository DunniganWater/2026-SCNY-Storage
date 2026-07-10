#!/usr/bin/env python3
"""
Annual-dynamic storage method (chained year-over-year, moving well network).

Rationale: the fixed-polygon methods compute each year's storage over only the
polygons whose well was measured that year, so the *area represented drifts*
(65-95% of the region, never 100%). This method instead re-tessellates every
year on exactly the wells available that year, so every year covers the full
region with real data — no gap-fill, no backcast.

Because the polygons change shape year to year, storage CHANGE is computed as a
chained year-over-year difference (user decision 2026-07-09):

  for each consecutive pair (Y-1, Y):
      wells = wells with a March composite in BOTH Y-1 and Y
      tessellate those wells (Voronoi) over the SCNY region
      dStorage(Y) = sum_w (GWE_w,Y - GWE_w,Y-1) * SY * area(cell_w)
  cumulative(Y) = sum of dStorage up to Y

Wells: RMS (Good-QA March, from measurements.json) + LWA telemetry (provisional,
QA relaxed, from lwa_wells.json). March spring composite, uniform Sy = 0.10,
window WY 1999-2025.

Reads:  data/wells_resolved.json, data/measurements.json, data/lwa_wells.json,
        raw/scny_region.geojson
Writes: data/annual_dynamic.json   (time series + per-year well/area metadata)
        js/dynamic-latest.js        (latest year's tessellation, for the map)
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
from pyproj import Transformer
from shapely import set_precision, voronoi_polygons
from shapely.geometry import MultiPoint, Point, Polygon
from shapely.ops import transform
from shapely.validation import make_valid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data"
JS = ROOT / "js"

WGS84 = "EPSG:4326"
ALBERS = "EPSG:3310"
ACRES_PER_M2 = 1.0 / 4046.8564224
START_YEAR, END_YEAR = 1999, 2025
SY = 0.10

SVI_YEAR_TYPE = {
    1999: "Wet", 2000: "Above Normal", 2001: "Dry", 2002: "Dry",
    2003: "Above Normal", 2004: "Below Normal", 2005: "Above Normal",
    2006: "Wet", 2007: "Dry", 2008: "Critical", 2009: "Dry",
    2010: "Below Normal", 2011: "Wet", 2012: "Below Normal", 2013: "Dry",
    2014: "Critical", 2015: "Critical", 2016: "Below Normal", 2017: "Wet",
    2018: "Below Normal", 2019: "Wet", 2020: "Dry", 2021: "Critical",
    2022: "Critical", 2023: "Wet", 2024: "Above Normal", 2025: "Above Normal",
}

_to_alb = Transformer.from_crs(WGS84, ALBERS, always_xy=True).transform
_to_wgs = Transformer.from_crs(ALBERS, WGS84, always_xy=True).transform


# --- RMS spring composites (Good-QA March mean), mirrors build_dashboard ----
def rms_springs(wells, meas):
    site = {w["well_id"]: w.get("site_code") for w in wells}
    out = {}
    for w in wells:
        by_year = defaultdict(list)
        for r in meas.get(site[w["well_id"]], []):
            if "good" not in (r.get("qa") or "").strip().lower():
                continue
            g = r.get("gwe")
            if g is None:
                continue
            d = r.get("d") or ""
            try:
                y, m = int(d[:4]), int(d[5:7])
            except ValueError:
                continue
            if m == 3 and START_YEAR <= y <= END_YEAR:
                by_year[y].append(float(g))
        springs = {y: statistics.fmean(v) for y, v in by_year.items() if v}
        if springs:
            out[w["well_id"]] = {
                "lat": w["latitude"], "lon": w["longitude"],
                "zone": w.get("zone"), "source": "RMS", "springs": springs,
            }
    return out


def build_pool():
    wells = json.loads((DATA / "wells_resolved.json").read_text())
    meas = json.loads((DATA / "measurements.json").read_text())
    pool = rms_springs(wells, meas)
    for w in json.loads((DATA / "lwa_wells.json").read_text()):
        pool[w["well_id"]] = {
            "lat": w["latitude"], "lon": w["longitude"], "zone": w.get("zone"),
            "source": "LWA", "springs": {int(y): v for y, v in w["springs"].items()},
        }
    # project seeds once
    for w in pool.values():
        w["_x"], w["_y"] = _to_alb(w["lon"], w["lat"])
    return pool


def voronoi_cell_geoms(seeds_xy, region_a):
    """Return list of clipped cell geometries (Albers), aligned to seeds_xy."""
    mp = MultiPoint([Point(x, y) for x, y in seeds_xy])
    if len(seeds_xy) == 1:
        return [region_a]
    cells = voronoi_polygons(mp, extend_to=region_a.envelope.buffer(5000),
                             ordered=True)
    cells = list(cells.geoms)
    return [c.buffer(0).intersection(region_a) for c in cells]


def rings_latlng(geom_a):
    geom = set_precision(geom_a.buffer(0), 0.01)
    out = []

    def parts(g):
        if g.is_empty:
            return []
        if g.geom_type == "Polygon":
            return [g]
        return [p for p in g.geoms if p.geom_type == "Polygon" and not p.is_empty]

    for p in parts(transform(_to_wgs, geom)):
        pr = Polygon([(round(c[0], 7), round(c[1], 7)) for c in p.exterior.coords],
                     [[(round(c[0], 7), round(c[1], 7)) for c in i.coords]
                      for i in p.interiors])
        if not pr.is_valid:
            pr = make_valid(pr)
        for q in parts(pr):
            out.append([[[round(c[1], 6), round(c[0], 6)] for c in q.exterior.coords]]
                       + [[[round(c[1], 6), round(c[0], 6)] for c in i.coords]
                          for i in q.interiors])
    return out


def main() -> None:
    pool = build_pool()
    region_a = (gpd.read_file(ROOT / "raw" / "scny_region.geojson")
                .to_crs(ALBERS).geometry.union_all().buffer(0))
    region_ac = region_a.area * ACRES_PER_M2

    series = []
    cumulative = 0.0
    latest_cells = None
    for y in range(START_YEAR + 1, END_YEAR + 1):
        pair = [(wid, w) for wid, w in pool.items()
                if (y - 1) in w["springs"] and y in w["springs"]]
        if not pair:
            continue
        seeds = [(w["_x"], w["_y"]) for _, w in pair]
        geoms = voronoi_cell_geoms(seeds, region_a)
        delta = 0.0
        area_cov = 0.0
        cell_info = []
        for (wid, w), cell in zip(pair, geoms):
            area = cell.area * ACRES_PER_M2
            dgwe = w["springs"][y] - w["springs"][y - 1]
            delta += dgwe * SY * area
            area_cov += area
            cell_info.append((wid, w, cell, area, dgwe))
        cumulative += delta
        n_rms = sum(1 for wid, w in pair if w["source"] == "RMS")
        n_lwa = len(pair) - n_rms
        series.append({
            "year": y, "svi_type": SVI_YEAR_TYPE.get(y, "?"),
            "n_wells": len(pair), "n_rms": n_rms, "n_lwa": n_lwa,
            "area_ac": round(area_cov, 0),
            "area_pct": round(area_cov / region_ac * 100, 1),
            "delta_af": round(delta, 0),
            "cumulative_af": round(cumulative, 0),
        })
        latest_cells = (y, cell_info)

    span = series[-1]["year"] - series[0]["year"] if series else 0
    avg_rate = (-series[-1]["cumulative_af"] / span) if span else 0.0

    out = {
        "method": "annual-dynamic",
        "sy": SY,
        "window": [START_YEAR, END_YEAR],
        "region_area_ac": round(region_ac, 0),
        "cumulative_2025_af": series[-1]["cumulative_af"] if series else 0,
        "avg_loss_rate_af_per_yr": round(avg_rate, 0),
        "n_lwa_wells_total": sum(1 for w in pool.values() if w["source"] == "LWA"),
        "n_rms_wells_total": sum(1 for w in pool.values() if w["source"] == "RMS"),
        "series": series,
        "method_note": ("Chained year-over-year. Each annual step re-tessellates "
                        "on the wells present in both that year and the prior "
                        "year, so every step covers the full region. Sy=0.10, "
                        "March spring composite, WY 1999-2025."),
    }
    (DATA / "annual_dynamic.json").write_text(json.dumps(out, indent=2))

    # latest-year tessellation for the map
    if latest_cells:
        ly, cells = latest_cells
        feats = []
        for wid, w, cell, area, dgwe in cells:
            feats.append({
                "zone_label": wid, "well_id": wid, "source": w["source"],
                "mgmt_area": w["zone"], "map_label": wid,
                "area_acres": round(area, 1),
                "dgwe_final_ft": round(dgwe, 2),
                "well_latlngs": [[w["lat"], w["lon"]]],
                "rings": rings_latlng(cell),
            })
        JS.joinpath("dynamic-latest.js").write_text(
            "// Auto-generated by scripts/build_dynamic.py - do not edit by hand.\n"
            f"// Tessellation for the latest year-pair ({ly-1}->{ly}); "
            f"{len(feats)} cells.\n\n"
            "const DYNAMIC_LATEST_YEAR = " + str(ly) + ";\n"
            "const DYNAMIC_LATEST = " + json.dumps(feats) + ";\n")

    # report
    print(f"pool: {out['n_rms_wells_total']} RMS + {out['n_lwa_wells_total']} LWA wells")
    print(f"{'yr':>5} {'type':>13} {'wells':>5} {'RMS':>4} {'LWA':>4} "
          f"{'area%':>6} {'dStor(AF)':>12} {'cum(AF)':>13}")
    for s in series:
        print(f"{s['year']:>5} {s['svi_type']:>13} {s['n_wells']:>5} {s['n_rms']:>4} "
              f"{s['n_lwa']:>4} {s['area_pct']:>5.0f}% {s['delta_af']:>12,.0f} "
              f"{s['cumulative_af']:>13,.0f}")
    print(f"\ncumulative to {END_YEAR}: {out['cumulative_2025_af']:,.0f} AF")
    print(f"avg loss rate: {out['avg_loss_rate_af_per_yr']:,.0f} AF/yr")


if __name__ == "__main__":
    main()
