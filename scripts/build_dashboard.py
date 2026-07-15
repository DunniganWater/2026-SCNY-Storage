#!/usr/bin/env python3
"""
Build the 2027 BC RMS drought-conditioned storage dashboard.

Reads (from sibling 2027-BC-prop-network/, never modifies):
  - js/polygons-data-single.js     Single region-wide Voronoi tessellation
  - js/polygons-data-three-zone.js Three-zone per-mgmt-area tessellation
  - js/wells-data.js               Wells, including site_code resolution
  - js/measurements-data.js        DWR periodic GWL records, keyed by site_code

Reads (local):
  - data/polygon_sy_svsim.csv  Polygon-by-polygon Sy (from build_sy_svsim.py)
  - data/project_portfolio.json (optional) Project allocations per polygon

Computes per polygon:
    GWE_p,y      = spring composite of the polygon's RMS well
                   (March mean for SWN; Feb–Apr mean for CWSCH; Good QA)
    Cum_p,y      = (GWE_p,y - GWE_p,baseline) × Sy_p × Area_p
                   where baseline = first year with Good spring data
    ΔStorage_p,y = year-over-year delta, gap-attributed evenly across DWR gaps
    Bucket attribution by Sacramento Valley Index water-year type

Writes:
  - data/condition_analysis.json       per-polygon bucket totals + basin totals
  - data/sustainability_2042.json      per-polygon and basin 2042 framing
  - data/basin_annual.json             basin year-over-year ΔStorage
  - data/polygon_storage_2025.csv      per-polygon WY 2025 detail
  - data/storage_timeseries.csv        basin cumulative time series
  - data/model_data.json               per-polygon annual GWE + storage
  - data/polygon_map.svg               interactive map (coverage)
  - data/basin_buckets_chart.svg       bar chart by water-year type
  - data/basin_cumulative_chart.svg    cumulative time series with SVI bands
  - data/storage_context.svg           proportion view vs 16 MAF total
  - index.html                         single-file briefing
"""

from __future__ import annotations

import copy
import csv
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

# --- paths ----------------------------------------------------------------
HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parent
DATA_DIR = WORKTREE / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

JS_DIR = WORKTREE / "js"
POLY_JS_BY_METHOD = {
    "single":    (JS_DIR / "polygons-data-single.js",    "RMS_POLYGONS_SINGLE"),
    "four-zone": (JS_DIR / "polygons-data-four-zone.js", "RMS_POLYGONS_FOUR_ZONE"),
}
WELLS_JS = JS_DIR / "wells-data.js"
MEAS_JS  = JS_DIR / "measurements-data.js"
METHODS = ["single", "four-zone"]
METHOD_LABEL = {
    "single":    "Single region-wide tessellation",
    "four-zone": "Four-zone (per management zone) tessellation",
}
METHOD_SUFFIX = {"single": "single", "four-zone": "four_zone"}

# --- constants ------------------------------------------------------------
START_YEAR = 1999
END_YEAR = 2026           # observed window end
TYPED_END_YEAR = 2025     # last year with an official Sacramento Valley Index type
PROJECTS_ONLINE_YEAR = 2032
# WY2026 is an incomplete water year with no official SVI type yet (user
# decision 2026-07-09: keep it separate and provisional, unassigned). It is
# included in the OBSERVED cumulative but excluded from the year-type buckets
# and from the normalization's per-type rate estimation.

# TODO(constants): PLACEHOLDER values pending SCNY-area GSP lookup
# (Colusa Subbasin / Yolo Subbasin). Swap real figures + citation before
# anything goes external. Volumetric AF/yr results do NOT depend on these;
# they are headline denominators / context only.
SUSTAINABLE_YIELD_AFY = 200_000       # PLACEHOLDER
TOTAL_FRESH_STORAGE_AF = 10_000_000   # PLACEHOLDER
TOTAL_STORAGE_LABEL = "10 MAF"        # PLACEHOLDER display string
SOURCE_GSP_LABEL = "SCNY-area GSP (PLACEHOLDER — pending citation)"
REGION_NAME = "SCNY region"

# Categorical palette for the map's "colour by zone" mode. Validated with the
# data-viz six checks against this page's #fafaf7 surface, --pairs all (any two
# zones can touch on a choropleth): worst-case CVD separation ΔE 13.3 (deutan;
# 19.6 tritan), and all four clear 3.0:1 contrast. Hues are assigned by role —
# Other is the 61%-of-area residual so it takes the calm blue and recedes;
# Dunnigan is the smallest so it takes the red and pops.
ZONE_ORDER = ["CCWD", "RD108", "Dunnigan", "Other"]
ZONE_COLORS = {
    "Other":    "#2a78d6",   # blue
    "CCWD":     "#4a3aa7",   # violet
    "RD108":    "#008300",   # green
    "Dunnigan": "#e34948",   # red
}
ZONE_BOUNDARY_INK = "#1a1612"

# Annual-dynamic map: colour cells by network source (validated categorical
# slots — blue vs orange, worst-pair CVD ΔE well clear of the target).
DYNAMIC_SOURCE_COLORS = {"RMS": "#2a78d6", "LWA": "#eb6834"}

# Specific yield: a UNIFORM Sy is applied to every polygon (user decision,
# 2026-07-09). scripts/build_sy_svsim.py still derives per-polygon Sy from DWR
# SVSim Texture Data and writes data/polygon_sy_svsim_*.csv for reference, but
# the dashboard no longer consumes it. The SVSim area-weighted mean was 0.0766
# (single) / 0.0771 (four-zone), so a flat 0.10 scales storage by ~1.30x.
SY_UNIFORM = 0.10
SY_SOURCE_LABEL = f"uniform {SY_UNIFORM:.2f}"

# Sacramento Valley Index water-year types (DWR Northern Sierra 8-Station Index).
SVI_YEAR_TYPE = {
    1999: "Wet",            2000: "Above Normal",   2001: "Dry",
    2002: "Dry",            2003: "Above Normal",   2004: "Below Normal",
    2005: "Above Normal",   2006: "Wet",            2007: "Dry",
    2008: "Critical",       2009: "Dry",            2010: "Below Normal",
    2011: "Wet",            2012: "Below Normal",   2013: "Dry",
    2014: "Critical",       2015: "Critical",       2016: "Below Normal",
    2017: "Wet",            2018: "Below Normal",   2019: "Wet",
    2020: "Dry",            2021: "Critical",       2022: "Critical",
    2023: "Wet",            2024: "Above Normal",   2025: "Above Normal",
    2026: "Provisional",    # WY2026 — incomplete water year, no official type
}
SVI_TYPE_KEY = {
    "Wet": "wet",            "Above Normal": "an",   "Below Normal": "bn",
    "Dry": "dry",            "Critical": "critical",
}
SVI_TYPE_COLOR = {
    "Wet":           "#2e6f3f",
    "Above Normal":  "#7eb585",
    "Below Normal":  "#d99a4f",
    "Dry":           "#c75a35",
    "Critical":      "#a32d2d",
}
SVI_SHADE = {
    "Wet":           (None, 0.0),
    "Above Normal":  (None, 0.0),
    "Below Normal":  ("#d99a4f", 0.20),
    "Dry":           ("#c75a35", 0.26),
    "Critical":      ("#a32d2d", 0.32),
}


def classify_year(y: int):
    """Bucket key for year y, or None if the year has no SVI type (e.g. the
    provisional WY2026). None-typed years are excluded from the year-type
    buckets and from the normalization's per-type rates."""
    return SVI_TYPE_KEY.get(SVI_YEAR_TYPE.get(y))


def year_type_full(y: int) -> str:
    return SVI_YEAR_TYPE.get(y, "Provisional")


# --- JS const loader ------------------------------------------------------
def load_js_const(path: Path, name: str):
    text = path.read_text()
    m = re.search(rf"const\s+{name}\s*=\s*(.*?);\s*$", text, re.DOTALL | re.MULTILINE)
    if not m:
        raise RuntimeError(f"could not find const {name} in {path}")
    return json.loads(m.group(1))


# --- geometry -------------------------------------------------------------
def flatten_rings(rings):
    """Return a flat list of point-rings from SCNY's nested multipolygon rings.

    SCNY polygons store rings as [ polygon, ... ] where each polygon is
    [ exterior_ring, hole_ring, ... ] and each ring is [[lat,lng], ...].
    This yields every ring (exteriors + holes) across all parts. Tolerant of
    the older flat schema (a plain list of rings) too.
    """
    if not rings:
        return []
    first = rings[0]
    # flat schema: rings[0] is a ring (list of [lat,lng] points)
    if first and isinstance(first[0][0], (int, float)):
        return list(rings)
    # nested schema: rings[0] is a polygon (list of rings)
    return [ring for polygon in rings for ring in polygon]


def ring_area_acres(ring, ref_lat: float) -> float:
    M_PER_DEG_LAT = 110540.0
    M_PER_DEG_LON = 111320.0 * math.cos(math.radians(ref_lat))
    s = 0.0
    n = len(ring)
    for i in range(n):
        lat1, lon1 = ring[i]
        lat2, lon2 = ring[(i + 1) % n]
        x1 = lon1 * M_PER_DEG_LON
        y1 = lat1 * M_PER_DEG_LAT
        x2 = lon2 * M_PER_DEG_LON
        y2 = lat2 * M_PER_DEG_LAT
        s += x1 * y2 - x2 * y1
    return abs(s) * 0.5 / 4046.8564224


def polygon_area_acres(rings) -> float:
    if not rings:
        return 0.0
    flat_rings = flatten_rings(rings)
    flat = [pt for r in flat_rings for pt in r]
    ref_lat = sum(p[0] for p in flat) / len(flat)
    return sum(ring_area_acres(r, ref_lat) for r in flat_rings)


def polygon_centroid(rings):
    flat = [pt for r in flatten_rings(rings) for pt in r]
    return (sum(p[0] for p in flat) / len(flat),
            sum(p[1] for p in flat) / len(flat))


# Map label: the Vina convention — SWN "13N01W07G001M" -> "07G00", i.e. the
# zone[6:11] slice (section + tract letter + the first two sequence digits).
# Aggregate polygons keep their own name ("Dunnigan"); Vina slices those too,
# which is why its Chico cell renders as "a-Chi".
SWN_RE = re.compile(r"^\d{2}[NS]\d{2}[EW]\d{2}[A-Z]\d{3}[A-Z]?$")


def polygon_label(zone: str) -> str:
    return zone[6:11] if SWN_RE.match(zone) else zone


def build_label_map(polygons_meta) -> dict:
    """{zone_label: short map label}, disambiguating collisions.

    The Vina slice is not unique across townships — 10N02E03R002M and
    12N01E03R002M both reduce to "03R00" — so colliding SWN labels get their
    township prefixed: "10N 03R00" / "12N 03R00".
    """
    base = {p["zone_label"]: polygon_label(p["zone_label"]) for p in polygons_meta}
    counts = Counter(base.values())
    return {z: (f"{z[:3]} {lab}" if counts[lab] > 1 and SWN_RE.match(z) else lab)
            for z, lab in base.items()}


# --- spring composites ---------------------------------------------------
def is_cwsch(well_name: str) -> bool:
    return well_name.upper().startswith("CWSCH")


def well_spring_year(well_name: str, recs):
    """{year: spring_GWE}.  SWN = March mean (Good); CWSCH = Feb–Apr mean (Good)."""
    months = {2, 3, 4} if is_cwsch(well_name) else {3}
    by_year = defaultdict(list)
    for r in recs:
        qa = (r.get("qa") or "").strip().lower()
        if "good" not in qa:
            continue
        gwe = r.get("gwe")
        if gwe is None:
            continue
        d = r.get("d") or ""
        try:
            y = int(d[:4])
            m = int(d[5:7])
        except ValueError:
            continue
        if m in months:
            by_year[y].append(float(gwe))
    return {y: statistics.fmean(v) for y, v in by_year.items() if v}


def polygon_annual_gwe(well_year_maps):
    yset = set()
    for m in well_year_maps:
        yset.update(m.keys())
    out = {}
    for y in yset:
        vals = [m[y] for m in well_year_maps if y in m]
        if vals:
            out[y] = statistics.fmean(vals)
    return out


# --- gap-filled cumulative ------------------------------------------------
def fill_cumulative(annual_storage: dict, baseline_year: int, end_year: int) -> dict:
    if not annual_storage:
        return {}
    known = {int(y): float(v) for y, v in annual_storage.items()
             if baseline_year <= int(y) <= end_year}
    if not known:
        return {}
    known[baseline_year] = 0.0
    years = sorted(known)
    last_year = years[-1]
    out = dict(known)
    for i in range(len(years) - 1):
        y1, y2 = years[i], years[i + 1]
        v1, v2 = known[y1], known[y2]
        if y2 - y1 > 1:
            for y in range(y1 + 1, y2):
                out[y] = v1 + (v2 - v1) * (y - y1) / (y2 - y1)
    return {y: out[y] for y in range(baseline_year, last_year + 1)}


def yoy_deltas(cumulative: dict) -> dict:
    deltas = {}
    for y in sorted(cumulative):
        if (y - 1) in cumulative:
            deltas[y] = cumulative[y] - cumulative[y - 1]
    return deltas


# --- Sy loader -----------------------------------------------------------
def load_sy(polygons_meta: list) -> dict:
    """Returns {zone_label: Sy} — a uniform SY_UNIFORM for every polygon.

    The SVSim-derived per-polygon values are still produced by
    scripts/build_sy_svsim.py into data/polygon_sy_svsim_*.csv for reference,
    but are deliberately not consumed here.
    """
    return {p["zone_label"]: SY_UNIFORM for p in polygons_meta}


# --- color ramp -----------------------------------------------------------
def loss_color(loss_rate_afy: float) -> str:
    """Color a polygon by its avg observed loss rate (AF/yr).

    loss_rate_afy is the *positive* loss magnitude (hold-steady need): 0 means
    the polygon is gaining storage, larger means losing faster.
    """
    if loss_rate_afy <= 0:
        return "#a8c8b0"   # gaining storage
    if loss_rate_afy < 250:
        return "#f0d9a8"   # near-zero loss
    if loss_rate_afy < 750:
        return "#e3a76f"
    if loss_rate_afy < 1500:
        return "#cb7740"
    if loss_rate_afy < 2500:
        return "#a84a2c"
    return "#7c2820"       # severe loss


# --- SVG projection -------------------------------------------------------
def project_factory(rings_all, width: float, height: float, margin: float):
    flat = [pt for r in rings_all for pt in r]
    lats = [p[0] for p in flat]
    lons = [p[1] for p in flat]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    ref_lat = (min_lat + max_lat) / 2

    def xy(lat, lon):
        return ((lon - min_lon) * math.cos(math.radians(ref_lat)),
                (max_lat - lat))

    xs = [xy(*p)[0] for p in flat]
    ys = [xy(*p)[1] for p in flat]
    x_extent = max(xs) - min(xs)
    y_extent = max(ys) - min(ys)
    avail_w = width - 2 * margin
    avail_h = height - 2 * margin
    scale = min(avail_w / x_extent, avail_h / y_extent)
    pad_x = (avail_w - x_extent * scale) / 2
    pad_y = (avail_h - y_extent * scale) / 2

    def proj(lat, lon):
        x, y = xy(lat, lon)
        return (margin + pad_x + x * scale, margin + pad_y + y * scale)

    return proj


def rings_to_path(rings, proj) -> str:
    parts = []
    for ring in flatten_rings(rings):
        coords = [proj(lat, lon) for lat, lon in ring]
        parts.append("M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in coords) + " Z")
    return " ".join(parts)


# --- formatting -----------------------------------------------------------
def fmt_int_signed(v):
    if v is None:
        return "n/a"
    return f"{v:+,.0f}".replace("+-", "-")


# --- bar chart ------------------------------------------------------------
def render_bar_chart(buckets, n_by_type, basin_net, n_polygons):
    width, height = 880, 420
    zero_y = 200
    bar_w = 110
    layout = [
        ("Wet",          "wet",      "#2e6f3f"),
        ("Above Normal", "an",       "#7eb585"),
        ("Below Normal", "bn",       "#d99a4f"),
        ("Dry",          "dry",      "#c75a35"),
        ("Critical",     "critical", "#a32d2d"),
    ]
    max_abs = max(abs(buckets[k]) for _, k, _ in layout) or 1.0
    bar_max_h = 110.0
    def bar_h(v):
        return abs(v) * bar_max_h / max_abs

    n_crit = n_by_type["critical"] or 1
    n_wet_an = (n_by_type["wet"] + n_by_type["an"]) or 1
    crit_per_yr = abs(buckets["critical"]) / n_crit
    wet_per_yr = abs(buckets["wet"] + buckets["an"]) / n_wet_an
    crit_x = crit_per_yr / wet_per_yr if wet_per_yr else 0

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        'style="background:#fafaf7;font-family:\'Inter\',ui-sans-serif,system-ui;'
        'width:100%;height:auto;display:block;">',
        f'<text x="{width/2}" y="24" text-anchor="middle" font-size="14" font-weight="700" fill="#1a1612">'
        'Region storage change since baseline, by Sacramento Valley Index year type</text>',
        f'<text x="{width/2}" y="42" text-anchor="middle" font-size="11" fill="#5b5547" font-style="italic">'
        f'Sum across all {n_polygons} polygons (WY 2000–2025). '
        f'Critical years remove about {crit_x:.1f}× per year what Wet+Above-Normal years recover.</text>',
        f'<line x1="60" y1="{zero_y}" x2="{width - 60}" y2="{zero_y}" stroke="#5b5547" stroke-width="0.9"/>',
        f'<text x="{width - 52}" y="{zero_y + 4}" font-size="11" fill="#5b5547">0 AF</text>',
    ]
    n_centers = len(layout)
    spacing = (width - 100) / n_centers
    centers = [50 + spacing * (i + 0.5) for i in range(n_centers)]
    for (label, key, color), cx in zip(layout, centers):
        val = buckets[key]
        n = n_by_type[key]
        bh = bar_h(val)
        x = cx - bar_w / 2
        if val >= 0:
            y = zero_y - bh
            out.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" '
                       f'fill="{color}" stroke="#1a1612" stroke-width="0.6"/>')
            out.append(f'<text x="{cx}" y="{y - 14}" text-anchor="middle" '
                       f'font-size="14" font-weight="800" fill="#2e6f3f">{val:+,.0f}</text>')
            out.append(f'<text x="{cx}" y="{y - 2}" text-anchor="middle" font-size="11" fill="#5b5547">AF</text>')
        else:
            y = zero_y
            out.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" '
                       f'fill="{color}" stroke="#1a1612" stroke-width="0.6"/>')
            out.append(f'<text x="{cx}" y="{y + bh + 16}" text-anchor="middle" '
                       f'font-size="14" font-weight="800" fill="#a32d2d">{val:+,.0f}</text>')
            out.append(f'<text x="{cx}" y="{y + bh + 32}" text-anchor="middle" font-size="11" fill="#5b5547">AF</text>')
        out.append(f'<text x="{cx}" y="358" text-anchor="middle" font-size="12" font-weight="700" fill="#1a1612">{label}</text>')
        out.append(f'<text x="{cx}" y="376" text-anchor="middle" font-size="11" fill="#5b5547">({n} years)</text>')
    out.append(f'<text x="{width/2}" y="406" text-anchor="middle" font-size="13" fill="#5b5547">'
               f'Net region total since baseline: '
               f'<tspan font-weight="800" fill="#a32d2d">{basin_net:+,.0f} AF</tspan>'
               '</text>')
    out.append("</svg>")
    return "\n".join(out)


# --- cumulative time series chart -----------------------------------------
def render_timeseries(ts, ts_normalized=None, n_polygons=None):
    """`ts` is the observed time series.  `ts_normalized` is the optional
    year-type-weighted backcast series — drawn as a second line if provided."""
    width, height = 760, 380
    plot_x0, plot_y0 = 92, 32
    plot_x1, plot_y1 = 736, 324
    out = []
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
               'style="background:#fafaf7;font-family:\'Inter\',ui-sans-serif,system-ui;'
               'width:100%;height:auto;display:block;">')
    out.append('<defs><clipPath id="ts-clip"><rect x="92" y="32" width="644" height="292"/></clipPath></defs>')
    out.append(f'<text x="{width/2}" y="20" text-anchor="middle" font-size="13" font-weight="700" fill="#1a1612">'
               f'Region cumulative ΔStorage ({n_polygons}-polygon network), shaded by hydrologic condition</text>')

    cum_vals = [t["cumulative_AF"] for t in ts]
    if ts_normalized:
        cum_vals = cum_vals + [t["cumulative_AF"] for t in ts_normalized]
    y_min = min(min(cum_vals), 0)
    y_max = max(max(cum_vals), 0)
    step = 50_000
    y_lo = math.floor(y_min / step) * step
    y_hi = math.ceil(y_max / step) * step
    if y_hi == y_lo:
        y_hi = y_lo + step

    def yscale(v):
        return plot_y0 + (y_hi - v) * (plot_y1 - plot_y0) / (y_hi - y_lo)

    def xscale(year):
        years = [t["year"] for t in ts]
        return plot_x0 + (year - years[0]) * (plot_x1 - plot_x0) / (years[-1] - years[0])

    for y in range(START_YEAR, END_YEAR + 1):
        full_type = SVI_YEAR_TYPE.get(y)
        if full_type is None:
            continue
        color, opacity = SVI_SHADE.get(full_type, (None, 0.0))
        if color is None:
            continue
        x_lo = xscale(y - 0.5)
        x_hi = xscale(y + 0.5)
        out.append(f'<rect x="{x_lo:.1f}" y="{plot_y0}" width="{x_hi-x_lo:.1f}" '
                   f'height="{plot_y1-plot_y0}" fill="{color}" fill-opacity="{opacity}"/>')

    v = y_lo
    while v <= y_hi:
        y_px = yscale(v)
        out.append(f'<line x1="{plot_x0}" y1="{y_px:.1f}" x2="{plot_x1}" y2="{y_px:.1f}" stroke="#e7e1cf" stroke-width="0.5"/>')
        out.append(f'<text x="{plot_x0 - 8}" y="{y_px + 3:.1f}" text-anchor="end" font-size="10" fill="#5b5547">{v:,}</text>')
        v += step
    out.append(f'<line x1="{plot_x0}" y1="{yscale(0):.1f}" x2="{plot_x1}" y2="{yscale(0):.1f}" stroke="#5b5547" stroke-width="0.8"/>')

    for tick_year in [2000, 2005, 2010, 2015, 2020, 2025]:
        x_px = xscale(tick_year)
        out.append(f'<line x1="{x_px:.1f}" y1="{plot_y1}" x2="{x_px:.1f}" y2="{plot_y1+4}" stroke="#5b5547" stroke-width="0.5"/>')
        out.append(f'<text x="{x_px:.1f}" y="{plot_y1+18}" text-anchor="middle" font-size="10" fill="#5b5547">{tick_year}</text>')

    out.append(f'<text x="22" y="{(plot_y0+plot_y1)/2}" transform="rotate(-90,22,{(plot_y0+plot_y1)/2})" text-anchor="middle" '
               'font-size="11" fill="#5b5547" font-weight="600">Cumulative storage change (AF)</text>')

    # Observed (solid) line + endpoint marker
    pts = " ".join(f"{xscale(t['year']):.1f},{yscale(t['cumulative_AF']):.1f}" for t in ts)
    out.append(f'<polyline points="{pts}" fill="none" stroke="#1f3a5f" stroke-width="2.4" clip-path="url(#ts-clip)"/>')
    last = ts[-1]
    obs_x, obs_y = xscale(last["year"]), yscale(last["cumulative_AF"])
    out.append(f'<circle cx="{obs_x:.1f}" cy="{obs_y:.1f}" r="3.2" fill="#1f3a5f"/>')

    # Normalized (dashed) line + endpoint marker
    last_n = ts_normalized[-1] if ts_normalized else None
    if ts_normalized:
        pts_n = " ".join(f"{xscale(t['year']):.1f},{yscale(t['cumulative_AF']):.1f}"
                          for t in ts_normalized)
        out.append(f'<polyline points="{pts_n}" fill="none" stroke="#7c4a86" stroke-width="2.0" '
                   f'stroke-dasharray="6,4" clip-path="url(#ts-clip)"/>')
        norm_x, norm_y = xscale(last_n["year"]), yscale(last_n["cumulative_AF"])
        out.append(f'<circle cx="{norm_x:.1f}" cy="{norm_y:.1f}" r="3.0" fill="#7c4a86"/>')

    # Endpoint labels sit right by their points — normalized above its point,
    # observed below its point — each with a short leader. If the two points are
    # close in y, the offsets are grown so the labels don't collide.
    def _endlabel(endp_x, endp_y, label_y, txt, color):
        near_y = label_y + (4 if label_y < endp_y else -9)   # stop leader at text
        out.append(f'<line x1="{endp_x:.1f}" y1="{endp_y - 3 if label_y < endp_y else endp_y + 3:.1f}" '
                   f'x2="{endp_x:.1f}" y2="{near_y:.1f}" stroke="{color}" stroke-width="0.8" opacity="0.6"/>')
        out.append(f'<text x="{endp_x - 2:.1f}" y="{label_y:.1f}" text-anchor="end" '
                   f'font-size="11" font-weight="700" fill="{color}">{txt}</text>')

    if ts_normalized:
        gap = 14 - ((obs_y + 20) - (norm_y - 13))   # extra push if they'd collide
        extra = max(0, gap)
        norm_label_y = norm_y - 13 - extra
        obs_label_y = obs_y + 20 + extra
        _endlabel(norm_x, norm_y, norm_label_y,
                  f'{last_n["cumulative_AF"]:+,.0f} AF (norm.)', "#7c4a86")
        _endlabel(obs_x, obs_y, obs_label_y,
                  f'{last["cumulative_AF"]:+,.0f} AF (obs.)', "#1f3a5f")
    else:
        _endlabel(obs_x, obs_y, obs_y + 20,
                  f'{last["cumulative_AF"]:+,.0f} AF (obs.)', "#1f3a5f")

    legend_w = 320
    legend_h = 132 if ts_normalized else 102
    legend_x = plot_x0 + 8
    legend_y = plot_y1 - legend_h - 6
    out.append(f'<g transform="translate({legend_x},{legend_y + 22})">')
    out.append(f'<rect x="-8" y="-22" width="{legend_w}" height="{legend_h}" fill="#fafaf7" fill-opacity="0.92" stroke="#cfc9b8" stroke-width="0.5" rx="2"/>')
    out.append('<line x1="0" y1="-10" x2="22" y2="-10" stroke="#1f3a5f" stroke-width="2.4"/>')
    out.append('<text x="28" y="-7" font-size="11" fill="#1a1612"><tspan font-weight="700">Observed</tspan> (years each polygon measured)</text>')
    swatch_y = 2
    if ts_normalized:
        out.append(f'<line x1="0" y1="{swatch_y+5}" x2="22" y2="{swatch_y+5}" stroke="#7c4a86" stroke-width="2.0" stroke-dasharray="6,4"/>')
        out.append(f'<text x="28" y="{swatch_y+9}" font-size="11" fill="#1a1612"><tspan font-weight="700">Normalized</tspan> (year-type-weighted backcast)</text>')
        swatch_y += 18
    for full, color, opacity in [
        ("Critical",      "#a32d2d", 0.32),
        ("Dry",           "#c75a35", 0.26),
        ("Below Normal",  "#d99a4f", 0.20),
        ("Wet / Above N.", None,     0),
    ]:
        if color:
            out.append(f'<rect x="0" y="{swatch_y}" width="22" height="10" fill="{color}" fill-opacity="{opacity}"/>')
        else:
            out.append(f'<rect x="0" y="{swatch_y}" width="22" height="10" fill="#fafaf7" stroke="#cfc9b8" stroke-width="0.5"/>')
        out.append(f'<text x="28" y="{swatch_y+9}" font-size="11" fill="#1a1612">{full}</text>')
        swatch_y += 16
    out.append('</g>')
    out.append("</svg>")
    return "\n".join(out)


# --- storage context (16 MAF proportion) ----------------------------------
def render_storage_context(basin_cum_2025, worst_year_deficit, worst_year):
    """Single-panel full-scale view: deficit as a sliver of the 16 MAF basin
    storage.  Both the WY 2025 cumulative deficit and the WY {worst_year}
    trough are shown in true proportion — no zoom (which optically inflates
    the deficit relative to total storage)."""
    width, height = 760, 210
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        'style="background:#fafaf7;font-family:\'Inter\',ui-sans-serif,system-ui;'
        'width:100%;height:auto;display:block;">',
        f'<text x="{width/2}" y="22" text-anchor="middle" font-size="14" font-weight="700" fill="#1a1612">'
        'How big is the deficit, relative to total fresh groundwater in storage?</text>',
        f'<text x="{width/2}" y="40" text-anchor="middle" font-size="11" fill="#5b5547" font-style="italic">'
        f'{REGION_NAME} total fresh GW in storage: ~{TOTAL_STORAGE_LABEL} ({SOURCE_GSP_LABEL})</text>',
    ]

    bar_x, bar_y = 50, 80
    bar_w, bar_h = width - 100, 36
    out.append(f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" '
               'fill="#e6f0e8" stroke="#5b5547" stroke-width="0.7"/>')
    # Trough first (lighter shade behind), then WY 2025 deficit (dark red on top).
    trough_frac = worst_year_deficit / TOTAL_FRESH_STORAGE_AF
    deficit_frac_2025 = abs(basin_cum_2025) / TOTAL_FRESH_STORAGE_AF
    trough_w = max(1.5, bar_w * trough_frac)
    deficit_w_2025 = max(1.5, bar_w * deficit_frac_2025)
    out.append(f'<rect x="{bar_x}" y="{bar_y}" width="{trough_w:.2f}" height="{bar_h}" '
               f'fill="#c75a35" fill-opacity="0.55"/>')
    out.append(f'<rect x="{bar_x}" y="{bar_y}" width="{deficit_w_2025:.2f}" height="{bar_h}" '
               'fill="#a32d2d"/>')
    # End-of-storage tick
    out.append(f'<line x1="{bar_x + bar_w}" y1="{bar_y - 6}" x2="{bar_x + bar_w}" y2="{bar_y + bar_h + 6}" '
               'stroke="#5b5547" stroke-width="0.8"/>')
    out.append(f'<text x="{bar_x + bar_w - 4}" y="{bar_y - 10}" text-anchor="end" '
               f'font-size="10" fill="#5b5547">{TOTAL_FRESH_STORAGE_AF:,.0f} AF</text>')
    out.append(f'<text x="{bar_x + 4}" y="{bar_y - 10}" font-size="10" fill="#5b5547">0</text>')

    # Two data lines below the bar
    out.append(f'<text x="{bar_x}" y="{bar_y + bar_h + 24}" font-size="13" fill="#1a1612">'
               f'<tspan font-weight="700" fill="#a32d2d">●</tspan> WY 2025 cumulative deficit '
               f'= <tspan font-weight="700" fill="#a32d2d">{deficit_frac_2025*100:.2f}%</tspan> '
               f'of {TOTAL_STORAGE_LABEL} ({abs(basin_cum_2025):,.0f} AF)</text>')
    out.append(f'<text x="{bar_x}" y="{bar_y + bar_h + 44}" font-size="13" fill="#1a1612">'
               f'<tspan font-weight="700" fill="#c75a35">●</tspan> WY {worst_year} trough '
               f'(deepest observed) = <tspan font-weight="700" fill="#c75a35">'
               f'{trough_frac*100:.2f}%</tspan> of {TOTAL_STORAGE_LABEL} ({worst_year_deficit:,.0f} AF)</text>')

    out.append("</svg>")
    return "\n".join(out)


# --- polygon map ---------------------------------------------------------
def render_polygon_map(polygons_meta, pol_summaries, well_lookup, sy_lookup,
                       projects):
    width, height, margin = 700, 1080, 30
    rings_all = [r for p in polygons_meta for r in flatten_rings(p["rings"])]
    proj = project_factory(rings_all, width, height, margin)
    label_map = build_label_map(polygons_meta)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'style="background:#fafaf7;font-family:ui-sans-serif,system-ui;'
        f'width:100%;height:auto;display:block;">',
        '<defs><style>'
        '.poly{stroke:#5b5547;stroke-width:0.7;cursor:pointer;fill-rule:evenodd;}'
        '.poly:hover{stroke-width:2;filter:brightness(1.05);}'
        '.well{fill:#1f1f1f;pointer-events:none;}'
        '.label{font-size:8.5px;fill:#332e22;text-anchor:middle;font-weight:500;pointer-events:none;}'
        '.title{font-size:13px;font-weight:700;fill:#1a1612;text-anchor:middle;}'
        '.subtitle{font-size:11px;fill:#5b5547;text-anchor:middle;font-style:italic;}'
        '.legend-text{font-size:10.5px;fill:#332e22;}'
        '.legend-title{font-size:11px;font-weight:700;fill:#1a1612;}'
        '.legend-bg{fill:#fafaf7;fill-opacity:0.97;stroke:#cfc9b8;stroke-width:0.6;}'
        '</style></defs>',
        f'<text class="title" x="{width/2}" y="18">'
        f'{REGION_NAME} RMS network ({len(polygons_meta)} polygons) — Observed avg storage loss rate (AF/yr)</text>',
        f'<text class="subtitle" x="{width/2}" y="32">'
        'Click any polygon for detail. Color = polygon avg loss rate (positive = losing storage).</text>',
    ]

    summary_by_zone = {s["zone_label"]: s for s in pol_summaries}
    for poly in polygons_meta:
        zone = poly["zone_label"]
        s = summary_by_zone[zone]
        d_attr = rings_to_path(poly["rings"], proj)
        fill = loss_color(s["hold_steady_need_AF_per_yr"])
        late_baseline = s["baseline_year"] > START_YEAR
        attrs = {
            "class": "poly",
            "fill": fill,
            "data-short": zone,
            "data-ma": s["ma"],
            "data-base-year": str(s["baseline_year"]),
            "data-end-year": str(s["endpoint_year"]),
            "data-span": str(s["span_years"]),
            "data-area": f"{s['area_ac']:,.0f}",
            "data-rms-wells": ";".join(s["rms_wells_2026"]),
            "data-sy": f"{s['sy']:.4f}",
            "data-sy-source": s["sy_source"],
            "data-avg-dgwe": f"{s['avg_dgwe_ft_per_yr']:+.2f}",
            "data-cum-stor": fmt_int_signed(s["endpoint_cum_storage_AF"]),
            "data-avg-rate": fmt_int_signed(s["avg_rate_AF_per_yr"]),
            "data-critdry-share": f"{s['crit_dry_share_of_drawdown_pct']:.0f}%",
            "data-crit-share": f"{s['crit_share_of_drawdown_pct']:.0f}%",
            "data-bucket-wet": fmt_int_signed(s["bucket_storage_AF"]["wet"]),
            "data-bucket-an": fmt_int_signed(s["bucket_storage_AF"]["an"]),
            "data-bucket-bn": fmt_int_signed(s["bucket_storage_AF"]["bn"]),
            "data-bucket-dry": fmt_int_signed(s["bucket_storage_AF"]["dry"]),
            "data-bucket-critical": fmt_int_signed(s["bucket_storage_AF"]["critical"]),
            "data-hold": f"{int(round(s['hold_steady_need_AF_per_yr'])):,}",
            "data-project": f"{int(round(s['project_alloc_AF_per_yr'])):,}",
            "data-project-name": s.get("project_name", ""),
            "data-coverage": fmt_int_signed(s["coverage_net_AF_per_yr"]),
            "data-late": "1" if late_baseline else "",
        }
        attr_str = " ".join(f'{k}="{v}"' for k, v in attrs.items())
        svg.append(f'<path d="{d_attr}" {attr_str}>'
                   f'<title>Click for {zone} detail</title></path>')

    for poly in polygons_meta:
        zone = poly["zone_label"]
        s = summary_by_zone[zone]
        for wname in s["rms_wells_2026"]:
            wmeta = well_lookup.get(wname)
            if not wmeta or wmeta.get("latitude") is None:
                continue
            cx, cy = proj(wmeta["latitude"], wmeta["longitude"])
            svg.append(f'<circle class="well" cx="{cx:.1f}" cy="{cy:.1f}" r="3.0"/>')
        lat_c, lon_c = polygon_centroid(poly["rings"])
        cx, cy = proj(lat_c, lon_c)
        # Show the section-letter shorthand to keep labels readable.
        section_label = label_map[zone]
        svg.append(f'<text class="label" x="{cx:.1f}" y="{cy:.1f}">{section_label}</text>')

    # Legend
    legend_x, legend_y = 16, height - 90
    legend_swatches = [
        ("Gaining",        "#a8c8b0"),
        ("Loss < 250",     "#f0d9a8"),
        ("Loss < 750",     "#e3a76f"),
        ("Loss < 1,500",   "#cb7740"),
        ("Loss < 2,500",   "#a84a2c"),
        ("Loss ≥ 2,500",   "#7c2820"),
    ]
    swatch_w, col_w = 60, 82
    legend_w = 8 + col_w * len(legend_swatches) + 175
    svg.append(f'<g transform="translate({legend_x},{legend_y})">')
    svg.append(f'<rect class="legend-bg" x="-8" y="-22" width="{legend_w}" height="86"/>')
    svg.append('<text class="legend-title" x="0" y="-6">Polygon avg observed storage loss rate (AF/yr)</text>')
    svg.append('<text class="legend-text" x="0" y="9" font-style="italic" font-size="9.5" fill="#5b5547">light green = gaining storage  ·  oranges → reds = loss magnitude per year</text>')
    swatch_y = 18
    for i, (label, color) in enumerate(legend_swatches):
        sx = i * col_w + (col_w - swatch_w) / 2
        cx = i * col_w + col_w / 2
        svg.append(f'<rect x="{sx:.1f}" y="{swatch_y}" width="{swatch_w}" height="18" fill="{color}" stroke="#332e22" stroke-width="0.4"/>')
        svg.append(f'<text class="legend-text" x="{cx:.1f}" y="{swatch_y + 30}" text-anchor="middle">{label}</text>')
    well_x = len(legend_swatches) * col_w + 16
    svg.append(f'<circle cx="{well_x}" cy="{swatch_y + 4}" r="3"/>')
    svg.append(f'<text class="legend-text" x="{well_x + 10}" y="{swatch_y + 8}">Proposed 2027 RMS well</text>')
    svg.append('</g>')
    svg.append("</svg>")
    return "\n".join(svg)


# --- per-method analysis --------------------------------------------------
def compute_method(method, wells_meta, meas, portfolio):
    """Run the full storage analysis for one polygon method.

    Loads the method-specific polygons + Sy CSV, computes per-polygon and
    basin totals (observed + normalized), writes method-suffixed JSON/CSV/SVG
    outputs, and returns a dict of all numbers the HTML build needs.
    """
    poly_js, poly_var = POLY_JS_BY_METHOD[method]
    suffix = METHOD_SUFFIX[method]
    polygons = load_js_const(poly_js, poly_var)

    site_by_name = {w["well_name"]: w.get("site_code") or w["well_name"]
                    for w in wells_meta}
    well_lookup = {w["well_name"]: w for w in wells_meta}

    sy_lookup = load_sy(polygons)

    project_by_zone = {p["polygon"]: p for p in portfolio.get("projects", [])}
    project_total_afy = sum(p["af_per_yr"] for p in portfolio.get("projects", []))

    # --- compute per-polygon GWE + storage ---
    pol_summaries = []
    BUCKET_KEYS = ["wet", "an", "bn", "dry", "critical"]
    basin_buckets = {k: 0.0 for k in BUCKET_KEYS}
    basin_cumulative_2025 = 0.0
    basin_avg_rate_sum = 0.0
    basin_yoy = defaultdict(float)
    polygon_models = []     # for model_data.json

    # Year-type counts in the full WY 2000–2025 transition window (26 years).
    # Used in the year-type-weighted normalization (Option A).
    N_BY_TYPE_FULL = {k: sum(1 for y in range(START_YEAR + 1, END_YEAR + 1)
                              if classify_year(y) == k)
                      for k in BUCKET_KEYS}
    SPAN_YEARS_FULL = sum(N_BY_TYPE_FULL.values())  # = 26
    basin_normalized_yoy = defaultdict(float)
    basin_normalized_cumulative_2025 = 0.0
    basin_normalized_typed_cum = 0.0   # excludes provisional WY2026, for the rate

    # Per-zone rollups, aggregated exactly like the region totals: cumulative is
    # the sum of each polygon's endpoint cumulative, and the loss rate is the
    # sum of each polygon's own avg rate (NOT cum / span, which would be wrong
    # with staggered baselines).
    zone_yoy = defaultdict(lambda: defaultdict(float))
    zone_buckets = defaultdict(lambda: {k: 0.0 for k in BUCKET_KEYS})
    zone_cum_2025 = defaultdict(float)
    zone_avg_rate_sum = defaultdict(float)
    zone_normalized_cum = defaultdict(float)
    zone_normalized_typed_cum = defaultdict(float)
    zone_meta = defaultdict(lambda: {"n_polygons": 0, "area_ac": 0.0})

    for poly in polygons:
        zone = poly["zone_label"]
        rms_wells = [poly.get("rms_well_swn")] if poly.get("rms_well_swn") else []
        # Aggregate polygon (e.g., dissolved Chico): use the full nested-completion list.
        if not rms_wells and poly.get("rms_well_swns"):
            rms_wells = poly["rms_well_swns"]
        # Fallback if the older multi-well key is used.
        if not rms_wells and poly.get("rms_wells_2026"):
            rms_wells = poly["rms_wells_2026"]
        well_year_maps = []
        per_well_summary = []
        for wname in rms_wells:
            site = site_by_name.get(wname, wname)
            recs = meas.get(site, [])
            ymap = well_spring_year(wname, recs)
            well_year_maps.append(ymap)
            per_well_summary.append({
                "well_name": wname,
                "site_code": site,
                "n_spring_years": len(ymap),
                "earliest_year": min(ymap) if ymap else None,
                "latest_year": max(ymap) if ymap else None,
            })
        annual = polygon_annual_gwe(well_year_maps)
        annual_in_window = {y: v for y, v in annual.items()
                            if START_YEAR <= y <= END_YEAR}
        sy_p = sy_lookup[zone]
        area = poly.get("area_acres") or polygon_area_acres(poly["rings"])

        if not annual_in_window:
            print(f"  ! {zone}: no spring measurements in {START_YEAR}–{END_YEAR}")
            continue

        baseline_year = min(annual_in_window)
        baseline_gwe = annual_in_window[baseline_year]
        annual_storage = {y: (g - baseline_gwe) * sy_p * area
                          for y, g in annual_in_window.items()}
        cumulative = fill_cumulative(annual_storage, baseline_year, END_YEAR)
        deltas = yoy_deltas(cumulative)
        for y, d in deltas.items():
            basin_yoy[y] += d

        # Bucket attribution. Untyped years (provisional WY2026) are NOT
        # bucketed and NOT used to estimate per-type rates; their observed
        # ΔStorage is held aside as `prov_delta` and appended to the cumulative.
        buckets = {k: 0.0 for k in BUCKET_KEYS}
        bucket_years = {k: 0 for k in BUCKET_KEYS}
        prov_delta = 0.0
        for y, d in deltas.items():
            klass = classify_year(y)
            if klass is None:
                prov_delta += d
                continue
            buckets[klass] += d
            bucket_years[klass] += 1

        endpoint_year = max(cumulative)
        endpoint_cum = cumulative[endpoint_year]      # through 2026 if observed
        endpoint_gwe = annual_in_window.get(endpoint_year)
        span_years = endpoint_year - baseline_year
        avg_dgwe = ((endpoint_gwe - baseline_gwe) / span_years
                    if (endpoint_gwe is not None and span_years > 0) else 0.0)
        # Avg rate is computed over the TYPED record (through 2025); the
        # provisional WY2026 only extends the cumulative, not the rate.
        typed_end = min(endpoint_year, TYPED_END_YEAR)
        typed_cum = cumulative.get(typed_end, endpoint_cum)
        typed_span = typed_end - baseline_year
        avg_rate = typed_cum / typed_span if typed_span > 0 else 0.0
        hold_steady_need = max(0.0, -avg_rate)

        # --- year-type-weighted normalization (Option A) ---------------
        # For each year type t the polygon observed, rate_t = sum of polygon's
        # year-type-t deltas / count of year-type-t years observed.  If the
        # polygon never observed a year-type (late-baseline edge cases like
        # 07H001M never seeing a Below-Normal year), fall back to the polygon's
        # *own* overall avg rate.  Then synthesize a full WY 1999–2025 record
        # by applying the polygon's per-type rates to the basin's actual year-
        # type mix (N_BY_TYPE_FULL).  This corrects the late-baseline drag:
        # every polygon contributes to every year, using only its own data.
        rate_per_bucket = {}
        rate_source = {}
        for k in BUCKET_KEYS:
            if bucket_years[k] > 0:
                rate_per_bucket[k] = buckets[k] / bucket_years[k]
                rate_source[k] = "observed"
            else:
                rate_per_bucket[k] = avg_rate  # polygon's own overall avg
                rate_source[k] = "fallback (polygon overall avg — type not observed)"
        # Typed-year backcast over 2000–2025, then the observed provisional
        # WY2026 delta appended (it has no type, so it can't be backcast).
        normalized_typed = sum(N_BY_TYPE_FULL[k] * rate_per_bucket[k]
                               for k in BUCKET_KEYS)
        normalized_cum_2025 = normalized_typed + prov_delta
        normalized_avg_rate = normalized_typed / SPAN_YEARS_FULL
        normalized_hold_need = max(0.0, -normalized_avg_rate)

        # Polygon contribution to basin normalized YoY series: backcast rate for
        # typed years; observed delta for the untyped provisional year(s).
        for y in range(START_YEAR + 1, END_YEAR + 1):
            k = classify_year(y)
            basin_normalized_yoy[y] += (deltas.get(y, 0.0) if k is None
                                        else rate_per_bucket[k])
        basin_normalized_cumulative_2025 += normalized_cum_2025
        basin_normalized_typed_cum += normalized_typed

        # Project allocation
        proj_info = project_by_zone.get(zone)
        project_afy = float(proj_info["af_per_yr"]) if proj_info else 0.0
        project_name = proj_info["name"] if proj_info else ""

        coverage_net = project_afy - hold_steady_need

        gross_drawdown = sum(d for d in deltas.values() if d < 0)
        crit_dry_loss = sum(d for y, d in deltas.items()
                            if d < 0 and classify_year(y) in ("critical", "dry"))
        crit_dry_share = (crit_dry_loss / gross_drawdown * 100.0
                          if gross_drawdown < 0 else 0.0)
        crit_loss = sum(d for y, d in deltas.items()
                        if d < 0 and classify_year(y) == "critical")
        crit_share = (crit_loss / gross_drawdown * 100.0
                      if gross_drawdown < 0 else 0.0)

        pol_summaries.append({
            "zone_label": zone,
            "name": zone,
            "ma": poly.get("mgmt_area") or poly.get("ma") or "",
            "ma_full": poly.get("mgmt_area_full", ""),
            "area_ac": area,
            "rms_wells_2026": rms_wells,
            "wells_summary": per_well_summary,
            "baseline_year": baseline_year,
            "endpoint_year": endpoint_year,
            "span_years": span_years,
            "baseline_gwe": baseline_gwe,
            "endpoint_gwe": endpoint_gwe,
            "sy": round(sy_p, 4),
            "sy_source": SY_SOURCE_LABEL,
            "endpoint_cum_storage_AF": round(endpoint_cum, 0),
            "avg_dgwe_ft_per_yr": round(avg_dgwe, 3),
            "avg_rate_AF_per_yr": round(avg_rate, 1),
            "bucket_storage_AF": {k: round(v, 0) for k, v in buckets.items()},
            "bucket_polygon_years": bucket_years,
            "crit_dry_share_of_drawdown_pct": round(crit_dry_share, 1),
            "crit_share_of_drawdown_pct": round(crit_share, 1),
            "hold_steady_need_AF_per_yr": round(hold_steady_need, 0),
            "project_alloc_AF_per_yr": round(project_afy, 0),
            "project_name": project_name,
            "coverage_net_AF_per_yr": round(coverage_net, 0),
            "sustainability_2042_need_AF_per_yr": round(hold_steady_need, 0),
            "pct_of_basin_SY": round(hold_steady_need / SUSTAINABLE_YIELD_AFY * 100, 3),
            "rate_per_bucket_AF_per_yr": {k: round(v, 1) for k, v in rate_per_bucket.items()},
            "rate_per_bucket_source": rate_source,
            "normalized_cum_2025_AF": round(normalized_cum_2025, 0),
            "normalized_avg_rate_AF_per_yr": round(normalized_avg_rate, 1),
            "normalized_hold_need_AF_per_yr": round(normalized_hold_need, 0),
        })
        for k in basin_buckets:
            basin_buckets[k] += buckets[k]
        basin_cumulative_2025 += endpoint_cum
        basin_avg_rate_sum += avg_rate

        # --- per-zone rollup ------------------------------------------
        ma = poly.get("mgmt_area") or ""
        zone_meta[ma]["n_polygons"] += 1
        zone_meta[ma]["area_ac"] += area
        zone_cum_2025[ma] += endpoint_cum
        zone_avg_rate_sum[ma] += avg_rate
        zone_normalized_cum[ma] += normalized_cum_2025
        zone_normalized_typed_cum[ma] += normalized_typed
        for y, d in deltas.items():
            zone_yoy[ma][y] += d
        for k in BUCKET_KEYS:
            zone_buckets[ma][k] += buckets[k]

        polygon_models.append({
            "zone_label": zone,
            "name": zone,
            "ma": poly.get("mgmt_area", ""),
            "area_acres": area,
            "rms_wells_2026": rms_wells,
            "baseline_year": baseline_year,
            "baseline_gwe": round(baseline_gwe, 2),
            "gwe_2025": round(annual_in_window.get(END_YEAR), 2) if END_YEAR in annual_in_window else None,
            "annual_gwe": {str(y): round(v, 2) for y, v in annual_in_window.items()},
            "annual_storage_AF": {str(y): round(v, 1) for y, v in annual_storage.items()},
            "sy": round(sy_p, 4),
            "wells_summary": per_well_summary,
        })

    basin_polygon_summed_need = sum(s["hold_steady_need_AF_per_yr"] for s in pol_summaries)
    basin_loss_rate = -basin_avg_rate_sum  # positive when basin losing
    basin_portfolio_margin = project_total_afy - basin_loss_rate

    # --- per-zone storage summaries ---------------------------------
    zone_summaries = []
    for z in [zz for zz in ZONE_ORDER if zz in zone_meta]:
        annual = {}
        running = 0.0
        for y in range(START_YEAR + 1, END_YEAR + 1):
            running += zone_yoy[z].get(y, 0.0)
            annual[y] = running
        zone_summaries.append({
            "zone": z,
            "n_polygons": zone_meta[z]["n_polygons"],
            "area_ac": round(zone_meta[z]["area_ac"], 1),
            "cum_2025_AF": round(zone_cum_2025[z], 0),
            "normalized_cum_2025_AF": round(zone_normalized_cum[z], 0),
            "avg_loss_rate_AF_per_yr": round(-zone_avg_rate_sum[z], 0),
            "normalized_avg_loss_rate_AF_per_yr": round(
                -zone_normalized_typed_cum[z] / SPAN_YEARS_FULL, 0),
            "bucket_storage_AF": {k: round(zone_buckets[z][k], 0)
                                  for k in BUCKET_KEYS},
            "annual_delta_AF": {str(y): round(zone_yoy[z].get(y, 0.0), 0)
                                for y in range(START_YEAR + 1, END_YEAR + 1)},
            "annual_cumulative_AF": {str(y): round(v, 0) for y, v in annual.items()},
        })

    # --- normalized basin totals (Option A) -------------------------
    basin_normalized_avg_rate = -basin_normalized_typed_cum / SPAN_YEARS_FULL
    basin_normalized_polygon_summed_need = sum(s["normalized_hold_need_AF_per_yr"]
                                                for s in pol_summaries)
    basin_normalized_portfolio_margin = project_total_afy - basin_normalized_avg_rate

    # --- basin annual gap-attributed time series ----------------------
    basin_annual = {str(y): round(basin_yoy.get(y, 0.0), 0)
                    for y in range(START_YEAR + 1, END_YEAR + 1)}
    basin_annual_normalized = {str(y): round(basin_normalized_yoy.get(y, 0.0), 0)
                                for y in range(START_YEAR + 1, END_YEAR + 1)}

    # --- write JSON outputs --------------------------------------------
    condition_out = {
        "year_type_classification": "Sacramento Valley Index (Northern Sierra 8-Station Index)",
        "year_types_by_year": SVI_YEAR_TYPE,
        "polygons": [
            {k: v for k, v in s.items()
             if k in {"zone_label", "name", "ma", "ma_full", "area_ac",
                      "baseline_year", "endpoint_year", "span_years",
                      "baseline_gwe", "endpoint_gwe", "endpoint_cum_storage_AF",
                      "avg_dgwe_ft_per_yr", "bucket_storage_AF",
                      "bucket_polygon_years", "sy", "sy_source"}}
            for s in pol_summaries
        ],
        "basin_total_by_condition_AF": {k: round(v, 0) for k, v in basin_buckets.items()},
        "basin_total_net_AF": round(basin_cumulative_2025, 0),
        "notes": (
            "Year-over-year storage deltas from each polygon's cumulative "
            "storage series; multi-year DWR gaps distributed evenly across "
            f"the gap before bucketing. {len(pol_summaries)} polygons in the 2027 BC RMS network; "
            "baseline years are staggered per first Good-quality spring "
            "measurement."
        ),
    }
    (DATA_DIR / f"condition_analysis_{suffix}.json").write_text(json.dumps(condition_out, indent=2), encoding="utf-8")

    sustainability_out = {
        "framing": ("Hold current conditions: each polygon's sustainability "
                    "need is its average annual loss rate; project portfolio "
                    "supplies recharge / surface-water substitution to offset "
                    "that loss starting ~2032."),
        "endpoint_year": END_YEAR,
        "projects_online_year": PROJECTS_ONLINE_YEAR,
        "sustainable_yield_AF_per_yr": SUSTAINABLE_YIELD_AFY,
        "sustainable_yield_source": SOURCE_GSP_LABEL,
        "total_fresh_storage_AF": TOTAL_FRESH_STORAGE_AF,
        "basin_total_cum_2025_AF": round(basin_cumulative_2025, 0),
        "basin_pct_of_total_storage": round(basin_cumulative_2025 / TOTAL_FRESH_STORAGE_AF * 100, 3),
        "basin_buckets_AF": {k: round(v, 0) for k, v in basin_buckets.items()},
        "basin_avg_loss_rate_AF_per_yr": round(basin_loss_rate, 0),
        "basin_polygon_summed_hold_need_AF_per_yr": round(basin_polygon_summed_need, 0),
        "basin_normalized_cum_2025_AF": round(basin_normalized_cumulative_2025, 0),
        "basin_normalized_avg_loss_rate_AF_per_yr": round(basin_normalized_avg_rate, 0),
        "basin_normalized_polygon_summed_hold_need_AF_per_yr": round(basin_normalized_polygon_summed_need, 0),
        "basin_normalized_portfolio_margin_AF_per_yr": round(basin_normalized_portfolio_margin, 0),
        "normalization_method": ("Year-type-weighted backcast: per polygon, avg ΔStorage per "
                                  "SVI year-type using only the polygon's own observations; "
                                  "fallback to polygon's overall avg rate for any year-type "
                                  "not observed. Applied to the basin's WY 2000–2025 year-type "
                                  "mix (6 Wet, 4 AN, 5 BN, 6 Dry, 5 Critical = 26 transition years)."),
        "project_portfolio_total_AF_per_yr": project_total_afy,
        "project_portfolio_basin_margin_AF_per_yr": round(basin_portfolio_margin, 0),
        "project_portfolio": portfolio.get("projects", []),
        "polygons": [
            {
                "zone_label": s["zone_label"],
                "name": s["name"],
                "ma": s["ma"],
                "baseline_year": s["baseline_year"],
                "endpoint_year": s["endpoint_year"],
                "span_years": s["span_years"],
                "sy": s["sy"],
                "sy_source": s["sy_source"],
                "endpoint_cum_storage_AF": s["endpoint_cum_storage_AF"],
                "avg_rate_AF_per_yr": s["avg_rate_AF_per_yr"],
                "hold_steady_need_AF_per_yr": s["hold_steady_need_AF_per_yr"],
                "project_alloc_AF_per_yr": s["project_alloc_AF_per_yr"],
                "project_name": s.get("project_name", ""),
                "coverage_net_AF_per_yr": s["coverage_net_AF_per_yr"],
                "crit_dry_share_of_drawdown_pct": s["crit_dry_share_of_drawdown_pct"],
                "crit_share_of_drawdown_pct": s["crit_share_of_drawdown_pct"],
                "bucket_storage_AF": s["bucket_storage_AF"],
            }
            for s in pol_summaries
        ],
    }
    (DATA_DIR / f"sustainability_2042_{suffix}.json").write_text(json.dumps(sustainability_out, indent=2), encoding="utf-8")

    (DATA_DIR / f"basin_annual_{suffix}.json").write_text(json.dumps({
        "observed": basin_annual,
        "normalized_year_type_weighted": basin_annual_normalized,
        "method_note": ("'observed' = each polygon contributes only years it observed. "
                        "'normalized_year_type_weighted' = each polygon's avg ΔStorage per SVI "
                        "year-type (using only its own observations) applied across the basin's full "
                        "WY 2000–2025 year-type mix. See README §Year-type-weighted normalization.")
    }, indent=2), encoding="utf-8")

    (DATA_DIR / f"zone_summaries_{suffix}.json").write_text(json.dumps({
        "zones": zone_summaries,
        "method_note": ("Per-management-zone rollup. 'cum_2025_AF' sums each "
                        "polygon's endpoint cumulative; 'avg_loss_rate_AF_per_yr' "
                        "sums each polygon's own avg rate (not cum/span, which "
                        "would be wrong with staggered baselines).")
    }, indent=2), encoding="utf-8")

    # model_data.json (for downstream / debug use)
    (DATA_DIR / f"model_data_{suffix}.json").write_text(json.dumps({
        "constants": {"start_year": START_YEAR, "end_year": END_YEAR,
                       "n_polygons": len(polygon_models), "method": method},
        "polygons": polygon_models,
    }, indent=2), encoding="utf-8")

    # polygon_storage_2025.csv
    with (DATA_DIR / f"polygon_storage_2025_{suffix}.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["zone_label", "mgmt_area", "rms_well", "area_acres", "sy",
                    "sy_source", "baseline_year", "baseline_gwe",
                    "endpoint_year", "endpoint_gwe",
                    "dgwe_endpoint_minus_baseline_ft",
                    "cumulative_storage_endpoint_AF",
                    "avg_rate_AF_per_yr",
                    "hold_steady_need_AF_per_yr",
                    "project_AF_per_yr", "project_name",
                    "coverage_net_AF_per_yr"])
        for s in pol_summaries:
            w.writerow([s["zone_label"], s["ma"],
                        s["rms_wells_2026"][0] if s["rms_wells_2026"] else "",
                        f"{s['area_ac']:.1f}", s["sy"], s["sy_source"],
                        s["baseline_year"], f"{s['baseline_gwe']:.2f}",
                        s["endpoint_year"],
                        f"{s['endpoint_gwe']:.2f}" if s["endpoint_gwe"] is not None else "",
                        f"{s['endpoint_gwe'] - s['baseline_gwe']:+.2f}" if s["endpoint_gwe"] is not None else "",
                        f"{s['endpoint_cum_storage_AF']:.0f}",
                        f"{s['avg_rate_AF_per_yr']:.0f}",
                        f"{s['hold_steady_need_AF_per_yr']:.0f}",
                        f"{s['project_alloc_AF_per_yr']:.0f}",
                        s.get("project_name", ""),
                        f"{s['coverage_net_AF_per_yr']:+.0f}"])

    # storage_timeseries.csv
    cum_running = 0.0
    with (DATA_DIR / f"storage_timeseries_{suffix}.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["year", "year_type", "yoy_delta_AF", "cumulative_AF"])
        for y in range(START_YEAR, END_YEAR + 1):
            delta = basin_yoy.get(y, 0.0)
            cum_running += delta
            w.writerow([y, SVI_YEAR_TYPE.get(y, "?"),
                        f"{delta:.0f}", f"{cum_running:.0f}"])

    # --- render SVGs ----------------------------------------------------
    polygon_map_svg = render_polygon_map(polygons, pol_summaries, well_lookup,
                                          sy_lookup, portfolio.get("projects", []))
    (DATA_DIR / f"polygon_map_{suffix}.svg").write_text(polygon_map_svg, encoding="utf-8")

    n_by_type = {k: sum(1 for y in range(START_YEAR + 1, END_YEAR + 1)
                        if classify_year(y) == k)
                 for k in ["wet", "an", "bn", "dry", "critical"]}
    bar_svg = render_bar_chart(basin_buckets, n_by_type, basin_cumulative_2025,
                               n_polygons=len(pol_summaries))
    (DATA_DIR / f"basin_buckets_chart_{suffix}.svg").write_text(bar_svg, encoding="utf-8")

    cum_running = 0.0
    ts = []
    for y in range(START_YEAR, END_YEAR + 1):
        if y == START_YEAR:
            ts.append({"year": y, "cumulative_AF": 0.0})
        else:
            cum_running += basin_yoy.get(y, 0.0)
            ts.append({"year": y, "cumulative_AF": round(cum_running, 0)})
    cum_norm = 0.0
    ts_norm = []
    for y in range(START_YEAR, END_YEAR + 1):
        if y == START_YEAR:
            ts_norm.append({"year": y, "cumulative_AF": 0.0})
        else:
            cum_norm += basin_normalized_yoy.get(y, 0.0)
            ts_norm.append({"year": y, "cumulative_AF": round(cum_norm, 0)})
    ts_svg = render_timeseries(ts, ts_norm, n_polygons=len(pol_summaries))
    (DATA_DIR / f"basin_cumulative_chart_{suffix}.svg").write_text(ts_svg, encoding="utf-8")

    trough_cum = 0.0
    trough_year = START_YEAR
    cum_run = 0.0
    for y_str, delta in basin_annual.items():
        cum_run += delta
        if cum_run < trough_cum:
            trough_cum = cum_run
            trough_year = int(y_str)
    context_svg = render_storage_context(basin_cumulative_2025,
                                          abs(trough_cum), trough_year)
    (DATA_DIR / f"storage_context_{suffix}.svg").write_text(context_svg, encoding="utf-8")

    # --- polygon-with-meta payload for Leaflet (embedded in JS) ----------
    polygons_for_js = []
    js_label_map = build_label_map(polygons)
    for p_meta in polygons:
        zone = p_meta["zone_label"]
        s = next((x for x in pol_summaries if x["zone_label"] == zone), None)
        if not s:
            continue
        seed_latlng = p_meta.get("seed_latlng") or [None, None]
        # One lat/lon pair per RMS well in the polygon's network membership.
        # For single-well polygons this is just the seed; for the Chico
        # aggregate it's all 10 nested completions at their actual locations.
        well_latlngs = []
        for wname in s["rms_wells_2026"]:
            wmeta = well_lookup.get(wname)
            if wmeta and wmeta.get("latitude") is not None:
                well_latlngs.append([wmeta["latitude"], wmeta["longitude"]])
        polygons_for_js.append({
            "zone_label": zone,
            "map_label": js_label_map[zone],
            "ma": s["ma"],
            "ma_full": s.get("ma_full", ""),
            "workbook_ma": p_meta.get("workbook_mgmt_area", ""),
            "reassigned": bool(p_meta.get("reassigned", False)),
            "area_ac": round(s["area_ac"], 1),
            "rms_wells": s["rms_wells_2026"],
            "is_aggregate": bool(p_meta.get("is_aggregate", False)),
            "rms_label": p_meta.get("rms_label") or "",
            "baseline_year": s["baseline_year"],
            "endpoint_year": s["endpoint_year"],
            "span_years": s["span_years"],
            "baseline_gwe": round(s["baseline_gwe"], 2),
            "endpoint_gwe": round(s["endpoint_gwe"], 2) if s["endpoint_gwe"] is not None else None,
            "avg_dgwe": s["avg_dgwe_ft_per_yr"],
            "sy": s["sy"],
            "sy_source": s["sy_source"],
            "cum_2025": s["endpoint_cum_storage_AF"],
            "avg_rate": s["avg_rate_AF_per_yr"],
            "norm_cum": s["normalized_cum_2025_AF"],
            "norm_avg": s["normalized_avg_rate_AF_per_yr"],
            "buckets": s["bucket_storage_AF"],
            "crit_dry_share": s["crit_dry_share_of_drawdown_pct"],
            "crit_share": s["crit_share_of_drawdown_pct"],
            "hold": s["hold_steady_need_AF_per_yr"],
            "project_afy": s["project_alloc_AF_per_yr"],
            "project_name": s.get("project_name", ""),
            "coverage": s["coverage_net_AF_per_yr"],
            "late_baseline": s["baseline_year"] > START_YEAR,
            "rings": p_meta.get("rings", []),
            "seed_latlng": seed_latlng,
            "well_latlngs": well_latlngs,
            "fill_color": loss_color(s["hold_steady_need_AF_per_yr"]),
        })

    # Per-method console summary
    print()
    print(f"=== [{method}] Basin totals (WY 2000–2025) ===")
    for k, full in [("wet", "Wet"), ("an", "Above Normal"), ("bn", "Below Normal"),
                    ("dry", "Dry"), ("critical", "Critical")]:
        n = n_by_type[k]
        avg = basin_buckets[k] / n if n else 0
        print(f"  {full:<14}: {basin_buckets[k]:>+12,.0f} AF "
              f"({n} years; avg {avg:>+8,.0f}/yr)")
    print(f"  region net     : {basin_cumulative_2025:>+12,.0f} AF "
          f"({basin_cumulative_2025 / TOTAL_FRESH_STORAGE_AF * 100:+.2f}% of {TOTAL_STORAGE_LABEL})")
    print(f"  observed avg loss rate    : {basin_loss_rate:>+12,.0f} AF/yr")
    print(f"  normalized cum 2025       : {basin_normalized_cumulative_2025:>+12,.0f} AF")
    print(f"  normalized avg loss rate  : {basin_normalized_avg_rate:>+12,.0f} AF/yr")
    print(f"  portfolio margin (obs/nrm): {basin_portfolio_margin:>+12,.0f} / "
          f"{basin_normalized_portfolio_margin:>+,.0f} AF/yr")

    return {
        "method": method,
        "polygons_meta": polygons,
        "well_lookup": well_lookup,
        "sy_lookup": sy_lookup,
        "pol_summaries": pol_summaries,
        "basin_buckets": basin_buckets,
        "basin_cumulative_2025": basin_cumulative_2025,
        "basin_polygon_summed_need": basin_polygon_summed_need,
        "basin_loss_rate": basin_loss_rate,
        "basin_portfolio_margin": basin_portfolio_margin,
        "basin_annual": basin_annual,
        "zone_summaries": zone_summaries,
        "basin_annual_normalized": basin_annual_normalized,
        "basin_normalized_cumulative_2025": basin_normalized_cumulative_2025,
        "basin_normalized_avg_rate": basin_normalized_avg_rate,
        "basin_normalized_polygon_summed_need": basin_normalized_polygon_summed_need,
        "basin_normalized_portfolio_margin": basin_normalized_portfolio_margin,
        "polygon_map_svg": polygon_map_svg,
        "bar_svg": bar_svg,
        "ts_svg": ts_svg,
        "context_svg": context_svg,
        "trough_cum": trough_cum,
        "trough_year": trough_year,
        "n_by_type": n_by_type,
        "n_by_type_full": N_BY_TYPE_FULL,
        "project_total_afy": project_total_afy,
        "polygons_for_js": polygons_for_js,
    }


# --- main analysis --------------------------------------------------------
def make_lwa_variant(base, base_method, inc, dense_cells):
    """Derive a '{method}-lwa' result by folding the LWA increment onto a copy
    of the base (RMS-only) result.

    Two-regime: 1999-2023 is the base result unchanged; the LWA densification
    adds `inc` (dense minus RMS-only delta) in 2024, 2025 (Above Normal) and
    2026 (provisional/untyped). The increment is applied to BOTH the observed
    and normalized cumulative; the typed years (2024, 2025) also enter the AN
    bucket and the loss-rate, while the provisional 2026 only extends the
    cumulative.
    """
    r = dict(base)
    r["method"] = base_method + "-lwa"
    span = TYPED_END_YEAR - START_YEAR       # 26 typed years, for the rate
    i24, i25, i26 = (inc["basin"].get("2024", 0), inc["basin"].get("2025", 0),
                     inc["basin"].get("2026", 0))
    ityped, iprov = i24 + i25, i26
    icum = ityped + iprov

    ba = dict(base["basin_annual"])
    for y, v in (("2024", i24), ("2025", i25), ("2026", i26)):
        ba[y] = ba.get(y, 0) + v
    r["basin_annual"] = ba
    ban = dict(base["basin_annual_normalized"])
    for y, v in (("2024", i24), ("2025", i25), ("2026", i26)):
        ban[y] = ban.get(y, 0) + v
    r["basin_annual_normalized"] = ban

    buckets = dict(base["basin_buckets"]); buckets["an"] += ityped
    r["basin_buckets"] = buckets

    r["basin_cumulative_2025"] = base["basin_cumulative_2025"] + icum
    r["basin_normalized_cumulative_2025"] = base["basin_normalized_cumulative_2025"] + icum
    r["basin_loss_rate"] = base["basin_loss_rate"] - ityped / span
    r["basin_normalized_avg_rate"] = base["basin_normalized_avg_rate"] - ityped / span
    r["basin_portfolio_margin"] = base["project_total_afy"] - r["basin_loss_rate"]
    r["basin_normalized_portfolio_margin"] = (base["project_total_afy"]
                                              - r["basin_normalized_avg_rate"])

    if base.get("zone_summaries") and "zones" in inc:
        zs = copy.deepcopy(base["zone_summaries"])
        for z in zs:
            zi = inc["zones"].get(z["zone"])
            if not zi:
                continue
            z24, z25, z26 = zi.get("2024", 0), zi.get("2025", 0), zi.get("2026", 0)
            ztyped = z24 + z25
            for y, v in (("2024", z24), ("2025", z25), ("2026", z26)):
                z["annual_delta_AF"][y] = z["annual_delta_AF"].get(y, 0) + v
            run = 0.0
            for y in range(START_YEAR + 1, END_YEAR + 1):
                run += z["annual_delta_AF"].get(str(y), 0)
                z["annual_cumulative_AF"][str(y)] = round(run, 0)
            z["cum_2025_AF"] += ztyped + z26
            z["normalized_cum_2025_AF"] += ztyped + z26
            z["bucket_storage_AF"]["an"] += ztyped
            z["avg_loss_rate_AF_per_yr"] = round(z["avg_loss_rate_AF_per_yr"] - ztyped / span)
            z["normalized_avg_loss_rate_AF_per_yr"] = round(
                z["normalized_avg_loss_rate_AF_per_yr"] - ztyped / span)
        r["zone_summaries"] = zs

    lwa_avg = ityped / span
    lwa_area = sum(c.get("area_acres", 0) for c in dense_cells
                   if c.get("source") == "LWA")
    r["pol_summaries"] = list(base["pol_summaries"]) + [{
        "zone_label": "LWA network (2024–2026)", "ma": "LWA",
        "baseline_year": 2023, "endpoint_year": END_YEAR, "span_years": 3,
        "sy": SY_UNIFORM, "sy_source": SY_SOURCE_LABEL,
        "endpoint_cum_storage_AF": icum, "avg_rate_AF_per_yr": lwa_avg,
        "normalized_cum_2025_AF": icum, "normalized_avg_rate_AF_per_yr": lwa_avg,
        "bucket_storage_AF": {"wet": 0, "an": ityped, "bn": 0, "dry": 0, "critical": 0},
        "crit_dry_share_of_drawdown_pct": 0.0, "crit_share_of_drawdown_pct": 0.0,
        "hold_steady_need_AF_per_yr": max(0.0, -lwa_avg),
        "project_alloc_AF_per_yr": 0.0, "project_name": "",
        "coverage_net_AF_per_yr": -max(0.0, -lwa_avg),
        "area_ac": lwa_area, "rate_per_bucket_source": {},
    }]

    r["polygons_for_js"] = [{
        "zone_label": c["zone_label"], "ma": c.get("mgmt_area", ""),
        "map_label": c.get("map_label", c["zone_label"]), "rings": c["rings"],
        "well_latlngs": c.get("well_latlngs", []),
        "fill_color": DYNAMIC_SOURCE_COLORS.get(c.get("source"), "#b0b0b0"),
        "simple": True, "source": c.get("source", ""),
        "area_ac": c.get("area_acres", 0), "dgwe_final_ft": c.get("dgwe_final_ft"),
    } for c in dense_cells]

    n_poly = len(base["pol_summaries"])
    r["bar_svg"] = render_bar_chart(buckets, base["n_by_type"],
                                    r["basin_cumulative_2025"], n_polygons=n_poly)
    ts, run, tsn, runn = [], 0.0, [], 0.0
    for y in range(START_YEAR, END_YEAR + 1):
        if y == START_YEAR:
            ts.append({"year": y, "cumulative_AF": 0.0})
            tsn.append({"year": y, "cumulative_AF": 0.0})
        else:
            run += ba.get(str(y), 0.0); ts.append({"year": y, "cumulative_AF": round(run, 0)})
            runn += ban.get(str(y), 0.0); tsn.append({"year": y, "cumulative_AF": round(runn, 0)})
    r["ts_svg"] = render_timeseries(ts, tsn, n_polygons=n_poly)
    trough_cum, trough_year, cum_run = 0.0, START_YEAR, 0.0
    for y_str, d in ba.items():
        cum_run += d
        if cum_run < trough_cum:
            trough_cum, trough_year = cum_run, int(y_str)
    r["context_svg"] = render_storage_context(r["basin_cumulative_2025"],
                                              abs(trough_cum), trough_year)
    r["trough_cum"], r["trough_year"] = trough_cum, trough_year
    return r


def main():
    wells_meta = load_js_const(WELLS_JS, "WELLS")
    meas = load_js_const(MEAS_JS, "MEASUREMENTS")
    print(f"loaded {len(wells_meta)} wells, {len(meas)} measurement series")

    portfolio_path = DATA_DIR / "project_portfolio.json"
    if portfolio_path.exists():
        portfolio = json.loads(portfolio_path.read_text())
    else:
        portfolio = {"projects": [], "notes": "no project portfolio loaded"}

    results_by_method = {}
    for method in METHODS:
        print(f"\n=== Running method: {method} ===")
        results_by_method[method] = compute_method(method, wells_meta, meas, portfolio)

    zone_boundaries_js = JS_DIR / "zone-boundaries.js"
    zone_boundaries = (load_js_const(zone_boundaries_js, "ZONE_BOUNDARIES")
                       if zone_boundaries_js.exists() else [])
    if not zone_boundaries:
        print("(js/zone-boundaries.js missing; zone overlay disabled — "
              "run scripts/build_polygons.py)")

    # --- LWA-inclusive variants (two-regime: RMS 1999-2023, +LWA 2024-2026) --
    inc_json = DATA_DIR / "lwa_increment.json"
    if inc_json.exists():
        increments = json.loads(inc_json.read_text())
        for base_method in ("single", "four-zone"):
            if base_method not in results_by_method:
                continue
            cells_js = JS_DIR / f"lwa-cells-{base_method}.js"
            const = "LWA_CELLS_" + METHOD_SUFFIX[base_method].upper()
            dense_cells = load_js_const(cells_js, const) if cells_js.exists() else []
            variant = make_lwa_variant(results_by_method[base_method], base_method,
                                       increments[base_method], dense_cells)
            results_by_method[base_method + "-lwa"] = variant
            e = increments[base_method]
            print(f"\n=== [{base_method}-lwa] LWA increment folded in ===")
            print(f"  region net (through 2026): "
                  f"{variant['basin_cumulative_2025']:>+12,.0f} AF "
                  f"(base + {e['cum']:+,.0f} LWA)")
    else:
        print("(data/lwa_increment.json missing; LWA methods skipped — "
              "run scripts/build_lwa_methods.py)")

    # --- index.html with toggle ----------------------------------------
    try:
        from build_html import write_index_html
        write_index_html(WORKTREE / "index.html", results_by_method,
                         portfolio, zone_boundaries, ZONE_COLORS,
                         ZONE_BOUNDARY_INK)
    except ImportError:
        print("(build_html.py not yet present; index.html skipped)")


if __name__ == "__main__":
    main()
