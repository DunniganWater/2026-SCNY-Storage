#!/usr/bin/env python3
"""
Compute the LWA-inclusive variants of the single and four-zone methods.

Two-regime: the RMS-only tessellation governs 1999-2023 exactly as the base
methods; the LWA telemetry wells join only for 2024-2026 (the years they can
form a year-over-year delta). LWA is observed-only (no backcast). The RMS
analysis is unchanged; this script computes the *increment* the LWA
densification adds each of those years, which build_dashboard folds onto the
base results.

increment(method, y) = dense_delta(y) - rms_only_delta(y)
  where both re-tessellate the wells present in BOTH y-1 and y over the region
  (single) or each zone (four-zone), and dense adds the LWA wells to the RMS set.
  The RMS set is identical in both, so the increment isolates the LWA effect.

WY2026 is provisional (incomplete water year, no SVI type); its increment is
folded onto the cumulative but not into any year-type bucket.

Reads:  data/wells_resolved.json, data/measurements.json, data/lwa_wells.json,
        raw/scny_region.geojson, raw/scny_zones.geojson
Writes: data/lwa_increment.json   (per method: basin + per-zone increment, cum)
        js/lwa-cells-single.js, js/lwa-cells-four-zone.js
                                   (latest-year dense tessellation for the map)
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

WGS84, ALBERS = "EPSG:4326", "EPSG:3310"
ACRES_PER_M2 = 1.0 / 4046.8564224
START_YEAR, END_YEAR = 1999, 2026
LWA_YEARS = [2024, 2025, 2026]     # years LWA can form a year-over-year delta
ZONE_ORDER = ["CCWD", "RD108", "Dunnigan", "Other"]
SY = 0.10

_to_alb = Transformer.from_crs(WGS84, ALBERS, always_xy=True).transform
_to_wgs = Transformer.from_crs(ALBERS, WGS84, always_xy=True).transform


def rms_springs(wells, meas):
    site = {w["well_id"]: w.get("site_code") for w in wells}
    out = {}
    for w in wells:
        by = defaultdict(list)
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
                by[y].append(float(g))
        springs = {y: statistics.fmean(v) for y, v in by.items() if v}
        if springs:
            out[w["well_id"]] = {"lat": w["latitude"], "lon": w["longitude"],
                                 "zone": w.get("zone"), "source": "RMS",
                                 "springs": springs}
    return out


def build_pool():
    wells = json.loads((DATA / "wells_resolved.json").read_text())
    meas = json.loads((DATA / "measurements.json").read_text())
    pool = rms_springs(wells, meas)
    for w in json.loads((DATA / "lwa_wells.json").read_text()):
        pool[w["well_id"]] = {"lat": w["latitude"], "lon": w["longitude"],
                              "zone": w.get("zone"), "source": "LWA",
                              "springs": {int(y): v for y, v in w["springs"].items()}}
    for w in pool.values():
        w["_x"], w["_y"] = _to_alb(w["lon"], w["lat"])
    return pool


def cell_geoms(members, boundary):
    if not members:
        return {}
    if len(members) == 1:
        return {0: boundary}
    mp = MultiPoint([Point(m["_x"], m["_y"]) for m in members])
    cells = list(voronoi_polygons(mp, extend_to=boundary.envelope.buffer(5000),
                                  ordered=True).geoms)
    return {i: cells[i].buffer(0).intersection(boundary) for i in range(len(members))}


def delta_over(members, boundary, y):
    present = [m for m in members if (y - 1) in m["springs"] and y in m["springs"]]
    geoms = cell_geoms(present, boundary)
    total = 0.0
    for i, m in enumerate(present):
        area = geoms[i].area * ACRES_PER_M2
        total += (m["springs"][y] - m["springs"][y - 1]) * SY * area
    return total


def rings_latlng(geom_a):
    geom = set_precision(geom_a.buffer(0), 0.01)

    def parts(g):
        if g.is_empty:
            return []
        if g.geom_type == "Polygon":
            return [g]
        return [p for p in g.geoms if p.geom_type == "Polygon" and not p.is_empty]

    out = []
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
    zdf = gpd.read_file(ROOT / "raw" / "scny_zones.geojson").to_crs(ALBERS)
    zones_a = {r["zone"]: r.geometry.buffer(0) for _, r in zdf.iterrows()}

    result = {}
    for method in ("single", "four-zone"):
        if method == "single":
            groups = [("__ALL__", region_a, list(pool.values()))]
        else:
            groups = [(z, zones_a[z], [m for m in pool.values() if m["zone"] == z])
                      for z in ZONE_ORDER]

        basin_inc = {str(y): 0.0 for y in LWA_YEARS}
        zone_inc = {z: {str(y): 0.0 for y in LWA_YEARS} for z in ZONE_ORDER}
        for gname, boundary, members in groups:
            rms = [m for m in members if m["source"] == "RMS"]
            for y in LWA_YEARS:
                inc = delta_over(members, boundary, y) - delta_over(rms, boundary, y)
                basin_inc[str(y)] += inc
                if method == "four-zone":
                    zone_inc[gname][str(y)] += inc
        entry = {"basin": {y: round(v, 0) for y, v in basin_inc.items()},
                 "cum": round(sum(basin_inc.values()), 0)}
        if method == "four-zone":
            entry["zones"] = {z: {y: round(v, 0) for y, v in zi.items()}
                              for z, zi in zone_inc.items()}
        result[method] = entry

        # latest-year (END_YEAR) dense tessellation for the map: every well with
        # END_YEAR March data (shows the full network, incl. LWA telemetry).
        map_feats = []
        for gname, boundary, members in groups:
            present = [m for m in members if END_YEAR in m["springs"]]
            geoms = cell_geoms(present, boundary)
            for i, m in enumerate(present):
                wid = next(k for k, v in pool.items() if v is m)
                dgwe = (m["springs"].get(END_YEAR) - m["springs"].get(END_YEAR - 1)
                        if (END_YEAR - 1) in m["springs"] else None)
                map_feats.append({
                    "zone_label": wid, "source": m["source"], "mgmt_area": m["zone"],
                    "map_label": wid, "area_acres": round(geoms[i].area * ACRES_PER_M2, 1),
                    "dgwe_final_ft": round(dgwe, 2) if dgwe is not None else None,
                    "well_latlngs": [[m["lat"], m["lon"]]],
                    "rings": rings_latlng(geoms[i]),
                })
        suffix = method.replace("-", "_")
        JS.joinpath(f"lwa-cells-{method}.js").write_text(
            "// Auto-generated by scripts/build_lwa_methods.py - do not edit by hand.\n"
            f"// Latest-year ({END_YEAR}) dense tessellation (RMS+LWA), {len(map_feats)} cells.\n\n"
            f"const LWA_CELLS_{suffix.upper()} = " + json.dumps(map_feats) + ";\n")

    (DATA / "lwa_increment.json").write_text(json.dumps(result, indent=2))

    print("LWA increment (AF added to the base method by year):")
    for method, e in result.items():
        yrs = "  ".join(f"{y} {e['basin'][y]:>+9,.0f}" for y in map(str, LWA_YEARS))
        print(f"  {method:10} {yrs}  cum {e['cum']:>+10,.0f}")
        if "zones" in e:
            for z, zi in e["zones"].items():
                zz = "  ".join(f"{y} {zi[y]:>+9,.0f}" for y in map(str, LWA_YEARS))
                print(f"       {z:9} {zz}")
    print("Wrote data/lwa_increment.json, js/lwa-cells-*.js")


if __name__ == "__main__":
    main()
