#!/usr/bin/env python3
"""
Ingest the LWA telemetry stations for the annual-dynamic storage method.

Locations come from ../stn_scny/stn_scny.shp; water levels from
../stn_scny/stn_scny_meas.xlsx (joined on well_code). These are provisional
transducer data (QA relaxed by user decision — all rows used). Only the
March spring composite per year is kept, to match the RMS methodology.

Reads (never modifies):
  - ../stn_scny/stn_scny.shp        41 telemetry stations
  - ../stn_scny/stn_scny_meas.xlsx  ~22k readings (well_code, date, wse_ft)
  - raw/scny_region.geojson, raw/scny_zones.geojson

Writes:
  - data/lwa_wells.json   [ {well_id, latitude, longitude, zone,
                             springs: {year: march_mean_gwe}} ]
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
STN_DIR = (ROOT / ".." / "stn_scny").resolve()
SHP = STN_DIR / "stn_scny.shp"
MEAS = STN_DIR / "stn_scny_meas.xlsx"
REGION = ROOT / "raw" / "scny_region.geojson"
ZONES = ROOT / "raw" / "scny_zones.geojson"
OUT = ROOT / "data" / "lwa_wells.json"

WGS84 = "EPSG:4326"
ALBERS = "EPSG:3310"
START_YEAR, END_YEAR = 1999, 2025


def main() -> None:
    stn = gpd.read_file(SHP).to_crs(WGS84)

    region = gpd.read_file(REGION).to_crs(WGS84).geometry.union_all()
    inside = stn[stn.geometry.within(region)].copy()

    zones = gpd.read_file(ZONES).to_crs(ALBERS)
    inside_a = inside.to_crs(ALBERS)

    def zone_of(pt_a):
        hit = zones[zones.geometry.contains(pt_a)]
        if len(hit):
            return hit.iloc[0]["zone"]
        d = zones.geometry.distance(pt_a)
        return zones.loc[d.idxmin(), "zone"]

    inside["zone"] = [zone_of(p) for p in inside_a.geometry]

    # March composites from the measurements workbook.
    m = pd.read_excel(MEAS)
    m["date"] = pd.to_datetime(m["date"], utc=True, errors="coerce")
    m = m.dropna(subset=["date", "wse_ft"])
    m["year"] = m["date"].dt.year
    m["month"] = m["date"].dt.month
    march = m[m["month"] == 3]
    # {well_code: {year: mean wse_ft}}, window only
    springs_by_well: dict[str, dict[str, float]] = {}
    for (wc, yr), grp in march.groupby(["well_code", "year"]):
        if START_YEAR <= yr <= END_YEAR:
            springs_by_well.setdefault(wc, {})[str(int(yr))] = round(
                float(grp["wse_ft"].mean()), 2)

    records = []
    n_no_data = 0
    for _, r in inside.iterrows():
        wc = r["well_code"]
        springs = springs_by_well.get(wc, {})
        if not springs:
            n_no_data += 1
            continue
        records.append({
            "well_id": wc,
            "latitude": round(float(r["latitude"]), 6),
            "longitude": round(float(r["longitude"]), 6),
            "zone": r["zone"],
            "source": "LWA telemetry (provisional)",
            "springs": dict(sorted(springs.items())),
        })

    OUT.write_text(json.dumps(records, indent=2))

    # report
    yr_counts: dict[str, int] = {}
    for rec in records:
        for y in rec["springs"]:
            yr_counts[y] = yr_counts.get(y, 0) + 1
    print(f"stations in shapefile: {len(stn)}  inside SCNY: {len(inside)}")
    print(f"LWA wells with in-window March data: {len(records)} "
          f"(dropped {n_no_data} with no March reading in {START_YEAR}-{END_YEAR})")
    print("zone split:", inside.loc[inside['well_code'].isin(
        {r['well_id'] for r in records})]['zone'].value_counts().to_dict())
    print("LWA wells with a March composite, by year:")
    for y in sorted(yr_counts):
        print(f"  {y}: {yr_counts[y]}")
    print(f"Wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
