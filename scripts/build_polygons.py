#!/usr/bin/env python3
"""
Build the SCNY RMS polygon tessellations (Layer-1), two methods:

  single    One Voronoi tessellation across all 27 in-boundary RMS wells,
            clipped to the SCNY region boundary. One cell per well.

  four-zone Four INDEPENDENT tessellations, one per zone (CCWD, RD108,
            Dunnigan, Other), each clipped to its own zone boundary. Cells do
            not cross zone lines. A zone with a single well (Dunnigan) becomes
            one dissolved polygon = the whole zone boundary (is_aggregate).

Reads:
  - data/wells_resolved.json   (from build_wells.py — well_id, lat/lon, zone)
  - raw/scny_region.geojson
  - raw/scny_zones.geojson

Writes (Vina-compatible schema, consumed by build_dashboard.py):
  - js/polygons-data-single.js     const RMS_POLYGONS_SINGLE = [...]
  - js/polygons-data-four-zone.js  const RMS_POLYGONS_FOUR_ZONE = [...]

Polygon record fields:
  zone_label   unique polygon id  (= well_id; = zone name for an aggregate)
  rms_well_swn driving well_id     (null for an aggregate)
  rms_well_swns [well_ids]         (aggregate list)
  mgmt_area    zone (CCWD/RD108/Dunnigan/Other)
  is_aggregate bool
  area_acres   polygon area, EPSG:3310 equal-area
  rings        [[[lat, lng], ...]]  Leaflet convention
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
from shapely import set_precision, voronoi_polygons
from shapely.geometry import GeometryCollection, MultiPoint, Point, Polygon
from shapely.validation import make_valid
from shapely.ops import transform
from pyproj import Transformer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WELLS = ROOT / "data" / "wells_resolved.json"
REGION = ROOT / "raw" / "scny_region.geojson"
ZONES = ROOT / "raw" / "scny_zones.geojson"
JS_DIR = ROOT / "js"
JS_DIR.mkdir(exist_ok=True)

WGS84 = "EPSG:4326"
ALBERS = "EPSG:3310"
ACRES_PER_M2 = 1.0 / 4046.8564224
ZONE_ORDER = ["CCWD", "RD108", "Dunnigan", "Other"]

_to_wgs = Transformer.from_crs(ALBERS, WGS84, always_xy=True).transform


# Rings are exported at full clipped extent — no simplification, no sliver or
# hole filtering.
#
# An earlier version simplified each cell independently (15 m tolerance) and
# dropped sub-2-acre parts/holes. Simplifying cells independently makes
# neighbours disagree along their shared edge, which produced ~600 hairline
# gap slivers (81-112 ac) and, in the four-zone method, 18.9 ac of polygon
# overlap. The sliver filters turned out to drop nothing (81 parts / 19 holes
# either way), so they were pure risk. Exact geometry is topologically perfect
# (0 gaps, 0 overlap) and costs only ~5.5k-8k vertices.
#
# Naive coordinate rounding is NOT safe on its own: it can pinch a thin ribbon
# into a self-intersection (this happened to two parts of 13N01W07G001M's
# 27-part cell). So we snap on a uniform 1 cm grid in projected metres first —
# uniform because a shared vertex must land on the same grid node in both
# neighbours — then emit at 7 decimals (~1.1 cm), matching the grid.
# make_valid() is kept as a belt-and-suspenders net.
SNAP_M = 0.01           # Albers grid, metres
COORD_DECIMALS = 7      # ~1.1 cm, matches SNAP_M


def _ring_coords(ring):
    return [[round(c[1], COORD_DECIMALS), round(c[0], COORD_DECIMALS)]
            for c in ring.coords]


def _polygon_parts(geom):
    if geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    return [p for p in geom.geoms
            if p.geom_type == "Polygon" and not p.is_empty and p.area > 0]


def rings_latlng(geom_albers):
    """Reproject to WGS84 and return nested multipolygon rings for rendering.

    Structure: [ polygon, polygon, ... ] where each polygon is
    [ exterior_ring, hole_ring, ... ] and each ring is [[lat,lng], ...].
    This matches Leaflet's L.polygon(multipolygon-with-holes) nesting.
    """
    geom = set_precision(geom_albers.buffer(0), SNAP_M)
    polys_out = []

    for part in _polygon_parts(transform(_to_wgs, geom)):
        rounded = Polygon(
            [(round(c[0], COORD_DECIMALS), round(c[1], COORD_DECIMALS))
             for c in part.exterior.coords],
            [[(round(c[0], COORD_DECIMALS), round(c[1], COORD_DECIMALS))
              for c in i.coords] for i in part.interiors],
        )
        if not rounded.is_valid:
            rounded = make_valid(rounded)
        for p in _polygon_parts(rounded):
            polys_out.append([_ring_coords(p.exterior)]
                             + [_ring_coords(i) for i in p.interiors])
    return polys_out


def voronoi_cells(seed_pts, boundary):
    """Return {seed_index: clipped cell geometry} for seeds inside boundary.

    seed_pts: list of shapely Points (Albers). boundary: shapely (Albers).
    Uses ordered Voronoi so output cell i maps to input point i.
    """
    mp = MultiPoint(seed_pts)
    env = boundary.envelope.buffer(5000)  # pad so edge cells extend past boundary
    cells = voronoi_polygons(mp, extend_to=env, ordered=True)
    cells = list(cells.geoms) if isinstance(cells, GeometryCollection) else [cells]
    out = {}
    for i, cell in enumerate(cells):
        clipped = cell.buffer(0).intersection(boundary)
        if not clipped.is_empty and clipped.area > 0:
            out[i] = clipped
    return out


def build_method(method, wells, region_a, zones_a):
    """Return list of polygon records for the given method."""
    recs = []
    if method == "single":
        groups = [("__ALL__", region_a, wells)]
    else:
        groups = [(z, zones_a[z], [w for w in wells if w["zone"] == z])
                  for z in ZONE_ORDER]

    for gname, boundary, gw in groups:
        if not gw:
            continue
        if len(gw) == 1 and method == "four-zone":
            # single-well zone -> one dissolved aggregate polygon = zone boundary
            w = gw[0]
            recs.append({
                "zone_label": gname,
                "rms_well_swn": None,
                "rms_well_swns": [w["well_id"]],
                "mgmt_area": gname,
                "is_aggregate": True,
                "area_acres": round(boundary.area * ACRES_PER_M2, 1),
                "rings": rings_latlng(boundary),
            })
            continue

        seeds = [Point(w["_x"], w["_y"]) for w in gw]
        cells = voronoi_cells(seeds, boundary)
        for i, w in enumerate(gw):
            cell = cells.get(i)
            if cell is None:
                print(f"  ! {method}/{gname}: no cell for {w['well_id']}")
                continue
            recs.append({
                "zone_label": w["well_id"],
                "rms_well_swn": w["well_id"],
                "rms_well_swns": [w["well_id"]],
                "mgmt_area": w["zone"],
                "is_aggregate": False,
                "area_acres": round(cell.area * ACRES_PER_M2, 1),
                "rings": rings_latlng(cell),
            })
    return recs


def write_js(path, varname, recs, header):
    lines = [header, "", f"const {varname} = " + json.dumps(recs) + ";", ""]
    path.write_text("\n".join(lines))


def main() -> None:
    wells = json.loads(WELLS.read_text())
    # project seeds to Albers once
    to_alb = Transformer.from_crs(WGS84, ALBERS, always_xy=True).transform
    for w in wells:
        w["_x"], w["_y"] = to_alb(w["longitude"], w["latitude"])

    region_a = gpd.read_file(REGION).to_crs(ALBERS).geometry.union_all().buffer(0)
    zdf = gpd.read_file(ZONES).to_crs(ALBERS)
    zones_a = {r["zone"]: r.geometry.buffer(0) for _, r in zdf.iterrows()}

    for method, var, fname in [
        ("single",    "RMS_POLYGONS_SINGLE",    "polygons-data-single.js"),
        ("four-zone", "RMS_POLYGONS_FOUR_ZONE", "polygons-data-four-zone.js"),
    ]:
        recs = build_method(method, wells, region_a, zones_a)
        hdr = (f"// Auto-generated by scripts/build_polygons.py - do not edit by hand.\n"
               f"// Method: {method}. {len(recs)} polygon entries from "
               f"{len(wells)} RMS wells.\n"
               f"// rings are arrays of [lat, lng] pairs (Leaflet convention).")
        write_js(JS_DIR / fname, var, recs, hdr)
        area = sum(r["area_acres"] for r in recs)
        n_agg = sum(1 for r in recs if r["is_aggregate"])
        print(f"{method:10s}: {len(recs):2d} polygons ({n_agg} aggregate), "
              f"total {area:,.0f} ac  -> js/{fname}")
        by_zone = {}
        for r in recs:
            by_zone[r["mgmt_area"]] = by_zone.get(r["mgmt_area"], 0) + 1
        print("            zones:", dict(by_zone))


if __name__ == "__main__":
    main()
