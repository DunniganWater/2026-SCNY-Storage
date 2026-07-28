#!/usr/bin/env python3
"""
Reproduce the SCNY headline denominators (sustainable yield, total fresh GW in
storage) by area-scaling each containing subbasin's GSP figure to the SCNY
footprint. Documents the numbers hard-coded in build_dashboard.py.

SCNY straddles two DWR B118 subbasins:
  - Colusa Subbasin 5-021.52  (Colusa Subbasin GSP, Dec 2021 rev. Apr 2024)
      sustainable yield 500,000 AF/yr (§3.3.7); fresh storage 26-140 MAF (§3.2.3)
  - Yolo Subbasin   5-021.67  (Yolo Subbasin GSP, 2022)
      sustainable yield 346,000 AF/yr (§2.3.7); storage capacity ~14 MAF (§2.3.6)

SCNY_value = sum over subbasins of (SCNY-area-in-subbasin / subbasin-area) x figure.

Reads:  raw/shapefiles/yolo_colusa.shp   (both subbasins, one feature each)
        raw/scny_region.geojson
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ACRE = 1.0 / 4046.8564224
ALBERS = "EPSG:3310"

GSP = {
    "5-021.52": {"name": "Colusa", "sy": 500_000, "storage_lo": 26e6, "storage_hi": 140e6},
    "5-021.67": {"name": "Yolo",   "sy": 346_000, "storage_lo": 14e6, "storage_hi": 14e6},
}


def main() -> None:
    sub = gpd.read_file(ROOT / "raw" / "shapefiles" / "yolo_colusa.shp").to_crs(ALBERS)
    scny = (gpd.read_file(ROOT / "raw" / "scny_region.geojson")
            .to_crs(ALBERS).geometry.union_all().buffer(0))

    sy_total = 0.0
    stor_lo = stor_hi = 0.0
    print(f"{'subbasin':10} {'SCNY in it':>12} {'subbasin':>12} {'ratio':>8} "
          f"{'+SY (AF/yr)':>12}")
    for _, r in sub.iterrows():
        code = r["Basin_Subb"]
        if code not in GSP:
            continue
        g = r.geometry.buffer(0)
        sc_in = scny.intersection(g).area * ACRE
        tot = g.area * ACRE
        ratio = sc_in / tot
        gsp = GSP[code]
        sy_total += ratio * gsp["sy"]
        stor_lo += ratio * gsp["storage_lo"]
        stor_hi += ratio * gsp["storage_hi"]
        print(f"{gsp['name']:10} {sc_in:>12,.0f} {tot:>12,.0f} {ratio:>8.4f} "
              f"{ratio*gsp['sy']:>12,.0f}")

    print(f"\nSCNY sustainable yield  = {sy_total:,.0f} AF/yr  -> use 200,000")
    print(f"SCNY total storage      = {stor_lo/1e6:.1f} - {stor_hi/1e6:.1f} MAF "
          f"(freshwater basis)  -> use ~10 MAF (conservative low end)")


if __name__ == "__main__":
    main()
