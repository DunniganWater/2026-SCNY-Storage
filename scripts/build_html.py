#!/usr/bin/env python3
"""
Single-file index.html generator for the SCNY drought-storage dashboard.
Builds two method-specific content sections (single region-wide tessellation
+ four-zone per-zone tessellation) and wires up a toggle UI at the top to
switch between them.

Called by scripts/build_dashboard.py with a `results_by_method` dict
keyed by 'single' and 'four-zone'.
"""

from __future__ import annotations
from collections import defaultdict as _dd

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
    2026: "Provisional",
}
START_YEAR = 1999
END_YEAR = 2026
TYPED_END_YEAR = 2025
PROJECTS_ONLINE_YEAR = 2032
# PLACEHOLDER constants — see build_dashboard.py (pending SCNY-area GSP lookup).
SUSTAINABLE_YIELD_AFY = 200_000
TOTAL_FRESH_STORAGE_AF = 10_000_000
TOTAL_STORAGE_LABEL = "10 MAF"
REGION_NAME = "SCNY region"
SOURCE_GSP_LABEL = "SCNY-area GSP (PLACEHOLDER — pending citation)"
ZONE_ORDER = ["CCWD", "RD108", "Dunnigan", "Other"]

METHODS = ["single", "four-zone", "single-lwa", "four-zone-lwa"]
METHOD_LABEL = {
    "single":        "Single region-wide tessellation",
    "four-zone":     "Four-zone (per management zone)",
    "single-lwa":    "Single + LWA telemetry",
    "four-zone-lwa": "Four-zone + LWA telemetry",
}
METHOD_SHORT = {"single": "Single", "four-zone": "Four-zone",
                "single-lwa": "Single + LWA", "four-zone-lwa": "Four-zone + LWA"}


def year_type_full(y: int) -> str:
    return SVI_YEAR_TYPE.get(y, "Wet")


def loss_or_gain_span(v, decimals=0):
    cls = "gain" if v > 0 else "loss" if v < 0 else ""
    fmt = f"{{:+,.{decimals}f}}".format(v) if v != 0 else f"{{:,.{decimals}f}}".format(v)
    return f'<span class="{cls}">{fmt}</span>' if cls else fmt


INDEX_CSS = """
:root {
  --bg: #faf8f3; --bg-card: #ffffff; --ink: #1a1612; --ink-muted: #5b5547;
  --rule: #cfc9b8; --accent: #1f3a5f; --warn: #a32d2d; --tan: #7c6a3e;
  --tan-soft: #d99a4f; --grey-soft: #c8cdc6; --good: #2e6f3f;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: 'Spectral', 'Iowan Old Style', 'Palatino', Georgia, 'Times New Roman', serif;
  font-size: 17px; line-height: 1.55; color: var(--ink); background: var(--bg);
  -webkit-font-smoothing: antialiased;
}
h1, h2, h3, h4 {
  font-family: 'Inter', -apple-system, ui-sans-serif, system-ui, sans-serif;
  font-weight: 700; letter-spacing: -0.012em; line-height: 1.2; color: var(--ink);
}
h1 { font-size: 30px; margin: 0 0 4px 0; }
h2 { font-size: 22px; margin: 36px 0 14px 0; padding-top: 18px; border-top: 1.5px solid var(--rule); }
h3 { font-size: 17px; margin: 22px 0 8px 0; }
h4 { font-size: 14px; margin: 14px 0 6px 0; text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-muted); }
p { margin: 0 0 14px 0; }
ul, ol { margin: 8px 0 16px 0; padding-left: 24px; }
li { margin-bottom: 5px; }
em { font-style: italic; color: var(--ink); }
strong { font-weight: 700; }
code { font-family: 'JetBrains Mono', 'SF Mono', ui-monospace, monospace; font-size: 0.92em; background: #f1ede2; padding: 1px 5px; border-radius: 3px; color: var(--ink); }
.container { max-width: 980px; margin: 0 auto; padding: 36px 28px 80px 28px; }
.subtitle { color: var(--ink-muted); font-size: 14px; font-family: 'Inter', sans-serif; margin: 0 0 18px 0; }
.lead { font-size: 18px; line-height: 1.55; color: var(--ink); }
.headline { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin: 28px 0 18px 0; }
@media (max-width: 720px) { .headline { grid-template-columns: 1fr; } }
.stat { background: var(--bg-card); border: 1px solid var(--rule); padding: 20px 22px; border-left-width: 4px; }
.stat.warn { border-left-color: var(--warn); }
.stat.acc { border-left-color: var(--accent); }
.stat.tan { border-left-color: var(--tan-soft); }
.stat.good { border-left-color: var(--good); }
.stat .num { font-family: 'Inter', sans-serif; font-size: 32px; font-weight: 800; letter-spacing: -0.02em; line-height: 1.05; color: var(--ink); }
.stat .num.warn { color: var(--warn); }
.stat .num.acc { color: var(--accent); }
.stat .num.tan { color: var(--tan); }
.stat .num.good { color: var(--good); }
.stat .lab { font-family: 'Inter', sans-serif; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--ink-muted); margin-top: 8px; }
.stat .det { font-size: 13px; color: var(--ink-muted); margin-top: 8px; line-height: 1.5; }
.callout { background: #f5f1e8; border-left: 4px solid var(--accent); padding: 18px 22px; margin: 22px 0; font-size: 16px; line-height: 1.55; }
.callout.warn { border-left-color: var(--warn); background: #fbf3ee; }
.callout.tan { border-left-color: var(--tan); background: #f7f1e1; }
.callout.good { border-left-color: var(--good); background: #ecf3ed; }
table { border-collapse: collapse; width: 100%; font-family: 'Inter', sans-serif; font-size: 13px; margin: 14px 0 22px 0; background: var(--bg-card); }
th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--rule); }
th { background: #f1ede2; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em; font-size: 11px; color: var(--ink); }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
tr:hover td { background: #f9f6ee; }
.gain { color: var(--good); font-weight: 600; }
.loss { color: var(--warn); font-weight: 600; }
.late { color: var(--tan); font-style: italic; font-weight: 500; }
.fallback { color: #8a5a18; font-style: italic; font-size: 11px; }
.reassigned-tag { color: #7c4a86; font-style: italic; font-size: 11px; }
.figure { margin: 18px 0 6px 0; }
.figure svg { display: block; max-width: 100%; height: auto; border: 1px solid var(--rule); background: #fafaf7; }
.figcaption { font-size: 12px; color: var(--ink-muted); margin: 6px 0 18px 2px; font-style: italic; }
.bigstat { background: var(--bg-card); border: 1px solid var(--rule); padding: 28px 32px; border-left: 4px solid var(--good); margin: 24px 0; }
.bigstat .row { display: flex; gap: 36px; align-items: baseline; flex-wrap: wrap; }
.bigstat .num { font-family: 'Inter', sans-serif; font-size: 44px; font-weight: 800; letter-spacing: -0.02em; line-height: 1; color: var(--good); }
.bigstat .lab { font-family: 'Inter', sans-serif; font-size: 13px; color: var(--ink-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; margin-top: 6px; }
.bigstat .pct { font-family: 'Inter', sans-serif; font-size: 28px; font-weight: 700; color: var(--ink); }
.bigstat .desc { flex: 1 1 280px; font-size: 14px; color: var(--ink); line-height: 1.55; }
.map-wrap { position: relative; }
.leaflet-map { width: 100%; height: 900px; border: 1px solid var(--rule); background: #fafaf7; border-radius: 2px; }
.leaflet-map .polygon-label { font-family: 'Inter', sans-serif; font-size: 9.5px; font-weight: 600; color: #332e22; text-align: center; text-shadow: 0 0 2px rgba(255,255,255,0.85), 0 0 2px rgba(255,255,255,0.85); pointer-events: none; line-height: 1; white-space: nowrap; }
.map-toolbar { display: flex; flex-wrap: wrap; gap: 16px; padding: 10px 14px; margin: 10px 0 4px 0; background: var(--bg-card); border: 1px solid var(--rule); border-radius: 4px; font-family: 'Inter', sans-serif; font-size: 12px; align-items: center; }
.map-toolbar-label { font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--ink-muted); }
.map-toggle { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; color: var(--ink); user-select: none; }
.map-toggle input { cursor: pointer; }
.map-basemap-select { font-family: 'Inter', sans-serif; font-size: 12px; padding: 3px 6px; border: 1px solid var(--rule); border-radius: 3px; background: #fff; color: var(--ink); cursor: pointer; }
.map-basemap-select:hover { border-color: var(--ink-muted); }
.readme-section { margin-top: 28px; }
.readme-section > summary { font-family: 'Inter', sans-serif; font-size: 16px; font-weight: 700; color: var(--ink); padding: 12px 16px; background: var(--bg-card); border: 1px solid var(--rule); border-radius: 4px; cursor: pointer; list-style: none; }
.readme-section > summary::-webkit-details-marker { display: none; }
.readme-section > summary::before { content: '▸  '; display: inline-block; transition: transform 0.15s; }
.readme-section[open] > summary::before { content: '▾  '; }
.readme-section > summary:hover { background: #f1efe6; }
.readme-content { padding: 18px 22px; background: var(--bg-card); border: 1px solid var(--rule); border-top: none; border-radius: 0 0 4px 4px; max-width: none; font-family: 'Inter', sans-serif; font-size: 14px; line-height: 1.6; color: var(--ink); }
.readme-content h1 { font-family: 'Spectral', serif; font-size: 22px; margin: 16px 0 8px 0; color: var(--ink); }
.readme-content h2 { font-family: 'Inter', sans-serif; font-size: 17px; font-weight: 700; margin: 22px 0 8px 0; padding-bottom: 4px; border-bottom: 1px solid var(--rule); color: var(--ink); }
.readme-content h3 { font-family: 'Inter', sans-serif; font-size: 14.5px; font-weight: 700; margin: 18px 0 6px 0; color: var(--ink); }
.readme-content h4 { font-family: 'Inter', sans-serif; font-size: 13.5px; font-weight: 700; margin: 14px 0 4px 0; color: var(--ink); }
.readme-content p { margin: 6px 0 10px 0; }
.readme-content ul, .readme-content ol { margin: 6px 0 10px 0; padding-left: 24px; }
.readme-content li { margin: 3px 0; }
.readme-content code { font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px; background: #f0ede2; padding: 1px 5px; border-radius: 2px; color: #5b4a1f; }
.readme-content pre { background: #f0ede2; border: 1px solid var(--rule); padding: 10px 12px; border-radius: 3px; overflow-x: auto; font-size: 12px; line-height: 1.45; }
.readme-content pre code { background: transparent; padding: 0; color: var(--ink); font-size: 12px; }
.readme-content blockquote { margin: 10px 0; padding: 8px 14px; border-left: 3px solid var(--accent); background: #f7f3e8; color: var(--ink-muted); font-style: italic; }
.readme-content table { border-collapse: collapse; margin: 8px 0 14px 0; font-size: 12.5px; }
.readme-content th, .readme-content td { border: 1px solid var(--rule); padding: 5px 9px; }
.readme-content th { background: #f1efe6; font-weight: 700; text-align: left; }
.readme-content tr:nth-child(even) td { background: #fbf9f1; }
.readme-content a { color: #1f3a5f; text-decoration: underline; }
.readme-content a:hover { color: #2e6f3f; }
.readme-content hr { border: none; border-top: 1px solid var(--rule); margin: 18px 0; }
.readme-stale-callout { background: #faedda; border-left: 4px solid #c75a35; padding: 10px 14px; margin: 0 0 16px 0; font-size: 13px; color: var(--ink); border-radius: 2px; }
.readme-stale-callout strong { color: #8a3a18; }
.map-legend-row { padding: 10px 14px; margin: 4px 0 4px 0; background: var(--bg-card); border: 1px solid var(--rule); border-radius: 4px; font-family: 'Inter', sans-serif; font-size: 11px; color: var(--ink); }
.map-legend-title { font-weight: 700; font-size: 11px; color: var(--ink); margin-bottom: 6px; }
.map-legend-swatches { display: flex; flex-wrap: wrap; gap: 10px 18px; }
.map-legend-swatches > div { display: inline-flex; align-items: center; gap: 5px; }
.map-legend-swatches .sw { display: inline-block; width: 18px; height: 11px; border: 0.5px solid #332e22; }
.map-legend-swatches .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; border: 1.5px solid #fafaf7; }
.map-legend-swatches .zoneline { display: inline-block; width: 18px; height: 0; border-top: 2.6px solid #1a1612; }
.leaflet-popup-content { font-family: 'Inter', sans-serif; font-size: 13px; min-width: 280px; max-width: 360px; }
.leaflet-popup-content h4 { margin: 0 0 8px 0; font-family: 'Inter', sans-serif; font-size: 14px; font-weight: 700; }
.leaflet-popup-content .popup-row { display: flex; justify-content: space-between; gap: 14px; padding: 3px 0; border-bottom: 1px dashed #e7e1cf; }
.leaflet-popup-content .popup-row:last-child { border-bottom: none; }
.leaflet-popup-content .popup-row .k { color: var(--ink-muted); font-weight: 500; }
.leaflet-popup-content .popup-row .v { font-weight: 700; font-variant-numeric: tabular-nums; }
.leaflet-popup-content .popup-row .v.gain { color: var(--good); }
.leaflet-popup-content .popup-row .v.loss { color: var(--warn); }
.leaflet-popup-content .popup-section { font-weight: 700; font-size: 11px; text-transform: uppercase; color: var(--ink-muted); margin-top: 10px; letter-spacing: 0.03em; }
.leaflet-popup-content .popup-need { background: #ecf3ed; padding: 10px 12px; margin-top: 10px; border-radius: 3px; font-size: 13px; line-height: 1.4; border-left: 3px solid var(--good); }
.leaflet-popup-content .popup-need .big { font-size: 22px; font-weight: 800; display: block; margin-top: 2px; }
.leaflet-popup-content .popup-late { background: #faf1dc; color: #6e5615; padding: 8px 10px; margin-top: 10px; border-radius: 3px; font-size: 12px; line-height: 1.4; }

table tr[data-zone-label] { cursor: pointer; }
table tr[data-zone-label]:hover td { background: #fff1cc; }
table tr[data-zone-label]:hover td:first-child::before { content: '➤ '; color: var(--accent); font-weight: 700; }
details { margin: 16px 0; padding: 12px 18px; background: var(--bg-card); border: 1px solid var(--rule); border-left: 4px solid var(--tan); }
details summary { cursor: pointer; font-family: 'Inter', sans-serif; font-weight: 600; font-size: 14px; color: var(--ink); }
details[open] summary { margin-bottom: 12px; }
.footer { margin-top: 60px; padding-top: 18px; border-top: 1.5px solid var(--rule); font-size: 13px; color: var(--ink-muted); font-family: 'Inter', sans-serif; line-height: 1.5; }
a { color: var(--accent); text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 2px; }
a:hover { background: #fff1cc; }

/* Method toggle */
.method-toggle {
  display: flex;
  align-items: center;
  gap: 0;
  margin: 18px 0 32px 0;
  border: 1px solid var(--rule);
  border-radius: 6px;
  background: var(--bg-card);
  padding: 4px;
  font-family: 'Inter', sans-serif;
  flex-wrap: nowrap;
  overflow-x: auto;
  max-width: 100%;
}
.method-toggle button {
  background: transparent;
  border: none;
  padding: 8px 13px;
  font-family: 'Inter', sans-serif;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-muted);
  cursor: pointer;
  border-radius: 4px;
  white-space: nowrap;
  transition: background 0.12s, color 0.12s;
}
.method-toggle button:hover { background: #f1ede2; color: var(--ink); }
.method-toggle button.active {
  background: var(--accent);
  color: white;
}
.method-toggle-label {
  font-family: 'Inter', sans-serif;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--ink-muted);
  font-weight: 600;
  margin-right: 12px;
  align-self: center;
}
.method-content { display: block; }
.method-content.hidden { display: none; }
.method-banner {
  font-family: 'Inter', sans-serif;
  font-size: 13px;
  color: var(--ink-muted);
  padding: 6px 0 0 2px;
  margin-bottom: 6px;
}
.method-banner strong { color: var(--ink); }
"""

MAP_JS = r"""
(function() {
  if (typeof L === 'undefined') {
    console.warn('Leaflet not loaded; map cannot render.');
    return;
  }

  const BASEMAPS = {
    'carto': {
      url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
      options: {
        subdomains: 'abcd',
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="https://carto.com/attributions">CARTO</a>',
      },
    },
    'esri-topo': {
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
      options: {
        maxZoom: 19,
        attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ, TomTom, USGS, NPS, and the GIS User Community',
      },
    },
    'esri-sat': {
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      options: {
        maxZoom: 19,
        attribution: 'Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, USDA, USGS, AeroGRID, IGN, and the GIS User Community',
      },
    },
    'osm': {
      url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      options: {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      },
    },
  };

  function fmtSigned(v) {
    if (v === null || v === undefined) return 'n/a';
    const n = Math.round(v);
    if (n > 0) return '+' + n.toLocaleString();
    if (n < 0) return '-' + Math.abs(n).toLocaleString();
    return '0';
  }
  function fmtSignedFt(v) {
    if (v === null || v === undefined) return 'n/a';
    const s = v >= 0 ? '+' : '';
    return s + v.toFixed(2);
  }
  function gainLossClass(v) {
    if (v > 0) return 'gain';
    if (v < 0) return 'loss';
    return '';
  }

  function buildPopupHtml(p) {
    if (p.simple) {
      const yr = window.LWA_LATEST_YEAR || '2026';
      let h = `<h4>${p.zone_label}</h4>`;
      h += `<div class="popup-row"><span class="k">Network</span><span class="v">${p.source} well</span></div>`;
      h += `<div class="popup-row"><span class="k">Zone</span><span class="v">${p.ma}</span></div>`;
      h += `<div class="popup-row"><span class="k">Cell area (${yr})</span><span class="v">${p.area_ac.toLocaleString()} ac</span></div>`;
      if (p.dgwe_final_ft != null)
        h += `<div class="popup-row"><span class="k">ΔGWE, latest step</span><span class="v ${gainLossClass(p.dgwe_final_ft)}">${fmtSignedFt(p.dgwe_final_ft)} ft</span></div>`;
      h += `<div class="popup-late">This map shows the ${yr} network (RMS + LWA). LWA wells join the tessellation only for 2024–2026; the historical storage series (1999–2023) uses the RMS-only network.</div>`;
      return h;
    }
    let html = `<h4>${p.zone_label} (${p.ma})</h4>`;
    if (p.reassigned) {
      html += `<div class="popup-row"><span class="k">Zone (spatial)</span><span class="v" style="color:#7c4a86;">${p.ma_full} — reassigned from ${p.workbook_ma}</span></div>`;
    }
    if (p.is_aggregate && p.rms_label) {
      html += `<div class="popup-row"><span class="k">RMS wells</span><span class="v">${p.rms_label}</span></div>`;
      html += `<div class="popup-row"><span class="k">Completions</span><span class="v" style="font-size:10px;color:#5b5547;">${(p.rms_wells || []).join(', ')}</span></div>`;
    } else {
      html += `<div class="popup-row"><span class="k">RMS well(s)</span><span class="v">${(p.rms_wells || []).join(', ')}</span></div>`;
    }
    html += `<div class="popup-row"><span class="k">Area</span><span class="v">${p.area_ac.toLocaleString()} ac</span></div>`;
    html += `<div class="popup-row"><span class="k">Span</span><span class="v">${p.baseline_year}–${p.endpoint_year} (${p.span_years} yr)</span></div>`;
    html += `<div class="popup-row"><span class="k">Avg ΔGWE/yr</span><span class="v ${gainLossClass(p.avg_dgwe)}">${fmtSignedFt(p.avg_dgwe)} ft</span></div>`;
    html += `<div class="popup-row"><span class="k">Cumulative ΔStorage</span><span class="v ${gainLossClass(p.cum_2025)}">${fmtSigned(p.cum_2025)} AF</span></div>`;
    html += `<div class="popup-row"><span class="k">Avg storage rate</span><span class="v ${gainLossClass(p.avg_rate)}">${fmtSigned(p.avg_rate)} AF/yr</span></div>`;
    html += `<div class="popup-row"><span class="k">Normalized cum 2025</span><span class="v ${gainLossClass(p.norm_cum)}">${fmtSigned(p.norm_cum)} AF</span></div>`;
    html += `<div class="popup-row"><span class="k">Critical+Dry share of drawdown</span><span class="v">${Math.round(p.crit_dry_share)}%</span></div>`;
    html += `<div class="popup-section">By Sac Valley Index year type</div>`;
    html += `<div class="popup-row"><span class="k">Wet</span><span class="v ${gainLossClass(p.buckets.wet)}">${fmtSigned(p.buckets.wet)} AF</span></div>`;
    html += `<div class="popup-row"><span class="k">Above Normal</span><span class="v ${gainLossClass(p.buckets.an)}">${fmtSigned(p.buckets.an)} AF</span></div>`;
    html += `<div class="popup-row"><span class="k">Below Normal</span><span class="v ${gainLossClass(p.buckets.bn)}">${fmtSigned(p.buckets.bn)} AF</span></div>`;
    html += `<div class="popup-row"><span class="k">Dry</span><span class="v ${gainLossClass(p.buckets.dry)}">${fmtSigned(p.buckets.dry)} AF</span></div>`;
    html += `<div class="popup-row"><span class="k">Critical</span><span class="v ${gainLossClass(p.buckets.critical)}">${fmtSigned(p.buckets.critical)} AF</span></div>`;
    const syExtra = ' <span style="color:#8a5a18;font-style:italic;font-size:11px;">(' + (p.sy_source || 'uniform') + ')</span>';
    html += `<div class="popup-row"><span class="k">Specific yield</span><span class="v">${p.sy.toFixed(4)}${syExtra}</span></div>`;
    if (p.late_baseline) {
      html += `<div class="popup-late">Late baseline: this polygon's RMS well wasn't measured in 1999, so its record starts at ${p.baseline_year}. Pre-${p.baseline_year} drawdown is not captured.</div>`;
    }
    return html;
  }

  // Cells share their edges — adjacency IS the data on a choropleth — so they
  // are divided by a fine muted hairline, not a surface-coloured gap. A light
  // stroke straddling the shared edge reads as a gap between polygons, which
  // is wrong: the tessellation has no gaps. Bold only on hover / flash.
  const CELL_STROKE = '#5b5547';
  const CELL_WEIGHT = 0.6;
  const CELL_OPACITY = 0.9;
  const FILL_OPACITY = 0.72;
  const ZONE_WEIGHT = 2.6;
  const HOVER_INK = '#1a1612';
  const HOVER_WEIGHT = 2.4;

  function polyFill(p, mode) {
    if (mode === 'zone') return (window.ZONE_COLORS || {})[p.ma] || '#b0b0b0';
    return p.fill_color;
  }

  function sectionLabel(zone) {
    // Vina convention: SWN like 13N01W07G001M -> "07G00".
    // Aggregates (e.g. "Dunnigan") keep their name. Only a fallback — the
    // build supplies a disambiguated p.map_label.
    return /^\d{2}[NS]\d{2}[EW]\d{2}[A-Z]\d{3}[A-Z]?$/.test(zone)
      ? zone.substring(6, 11) : zone;
  }

  const MAPS = {};

  function initMap(method) {
    if (MAPS[method]) return MAPS[method];
    const container = document.getElementById(`map-${method}`);
    if (!container) return null;
    const polys = window.POLYGONS_BY_METHOD[method] || [];

    const map = L.map(container, {
      zoomSnap: 0.25,
      zoomDelta: 0.5,
      attributionControl: true,
      preferCanvas: false,
    });

    // Build all available basemap layers up-front; only one is added at a time.
    const basemapLayers = {};
    Object.entries(BASEMAPS).forEach(([key, def]) => {
      basemapLayers[key] = L.tileLayer(def.url, def.options);
    });
    let currentBasemap = null;

    const polyLayer = L.featureGroup();
    const labelLayer = L.layerGroup();
    const wellLayer = L.layerGroup();

    polys.forEach(p => {
      const poly = L.polygon(p.rings, {
        color: CELL_STROKE,
        weight: CELL_WEIGHT,
        opacity: CELL_OPACITY,
        fillColor: polyFill(p, 'loss'),
        fillOpacity: FILL_OPACITY,
      });
      poly._meta = p;
      poly.bindPopup(buildPopupHtml(p), { maxWidth: 380, autoPan: true });
      poly.on('mouseover', function() {
        this.setStyle({ weight: HOVER_WEIGHT, color: HOVER_INK, opacity: 1 });
        this.bringToFront();
      });
      poly.on('mouseout', function() {
        if (!this._isFlashing) this.setStyle({
          weight: CELL_WEIGHT, color: CELL_STROKE, opacity: CELL_OPACITY });
      });
      polyLayer.addLayer(poly);

      // Centroid label
      const ll = poly.getBounds().getCenter();
      const label = L.marker(ll, {
        icon: L.divIcon({
          className: 'polygon-label-wrap',
          html: `<div class="polygon-label">${p.map_label || sectionLabel(p.zone_label)}</div>`,
          iconSize: [56, 14],
          iconAnchor: [28, 7],
        }),
        interactive: false,
      });
      labelLayer.addLayer(label);

      // Proposed 2027 RMS well markers — one per well in the polygon's
      // network membership (10 for the Chico aggregate, 1 for the others).
      (p.well_latlngs || []).forEach(latlng => {
        const wellMarker = L.circleMarker(latlng, {
          radius: 3,
          color: '#fafaf7',
          weight: 0.8,
          fillColor: '#1f1f1f',
          fillOpacity: 0.95,
          interactive: false,
        });
        wellLayer.addLayer(wellMarker);
      });
    });

    // Zone outlines: the structural layer, drawn over the cell fills but under
    // the well markers and labels. Only meaningful for the four-zone method —
    // in the single tessellation the cells deliberately cross zone lines, so
    // drawing those lines would imply a structure the polygons do not have.
    const zoneLayer = L.layerGroup();
    if (method.indexOf('four-zone') === 0) {
      (window.ZONE_BOUNDARIES || []).forEach(z => {
        zoneLayer.addLayer(L.polygon(z.rings, {
          fill: false,
          color: window.ZONE_BOUNDARY_INK || '#1a1612',
          weight: ZONE_WEIGHT,
          opacity: 0.95,
          interactive: false,
        }));
      });
    }

    polyLayer.addTo(map);
    if (method.indexOf('four-zone') === 0) zoneLayer.addTo(map);
    wellLayer.addTo(map);
    labelLayer.addTo(map);
    map.fitBounds(polyLayer.getBounds(), { padding: [14, 14] });
    // The container may not have its final size yet (fonts/layout, or a hidden
    // method section). invalidateSize() alone re-measures but KEEPS the stale
    // zoom, so callers must re-fit — see fitMapExtent().
    map._needsFit = true;

    const basemapSelect = document.getElementById(`basemap-select-${method}`);
    const fillToggle = document.getElementById(`fill-toggle-${method}`);
    const labelToggle = document.getElementById(`label-toggle-${method}`);
    if (basemapSelect) basemapSelect.addEventListener('change', () => {
      if (currentBasemap) {
        map.removeLayer(currentBasemap);
        currentBasemap = null;
      }
      const key = basemapSelect.value;
      if (key !== 'none' && basemapLayers[key]) {
        currentBasemap = basemapLayers[key];
        currentBasemap.addTo(map);
        // Keep polygons / labels / wells on top.
        currentBasemap.bringToBack();
      }
    });
    if (fillToggle) fillToggle.addEventListener('change', () => {
      polyLayer.eachLayer(l => l.setStyle({ fillOpacity: fillToggle.checked ? FILL_OPACITY : 0 }));
    });
    if (labelToggle) labelToggle.addEventListener('change', () => {
      if (labelToggle.checked) labelLayer.addTo(map); else map.removeLayer(labelLayer);
    });

    const zoneToggle = document.getElementById(`zone-toggle-${method}`);
    if (zoneToggle) zoneToggle.addEventListener('change', () => {
      if (zoneToggle.checked) zoneLayer.addTo(map); else map.removeLayer(zoneLayer);
    });

    // Colour mode: sequential loss-rate ramp, or categorical zone identity.
    // The legend swaps with it, so identity is never carried by colour alone.
    const colorSelect = document.getElementById(`colormode-select-${method}`);
    const legendLoss = document.getElementById(`legend-loss-${method}`);
    const legendZone = document.getElementById(`legend-zone-${method}`);
    function applyColorMode(mode) {
      polyLayer.eachLayer(l => {
        if (l._meta && !l._isFlashing) l.setStyle({ fillColor: polyFill(l._meta, mode) });
      });
      if (legendLoss) legendLoss.hidden = (mode !== 'loss');
      if (legendZone) legendZone.hidden = (mode !== 'zone');
    }
    if (colorSelect) colorSelect.addEventListener('change', () => applyColorMode(colorSelect.value));

    MAPS[method] = { map, basemapLayers, polyLayer, zoneLayer, labelLayer, wellLayer };
    return MAPS[method];
  }

  function flashPolygon(method, zoneLabel) {
    // Make sure the right method is visible
    const targetContent = document.querySelector('.method-content.method-' + method);
    if (!targetContent || targetContent.classList.contains('hidden')) {
      const btn = document.querySelector(`.method-toggle button[data-method="${method}"]`);
      if (btn) btn.click();
    }

    setTimeout(() => {
      const M = initMap(method);
      if (!M) return;
      M.map.invalidateSize();
      let target = null;
      M.polyLayer.eachLayer(l => {
        if (l._meta && l._meta.zone_label === zoneLabel) target = l;
      });
      if (!target) return;
      const container = document.getElementById(`map-${method}`);
      container.scrollIntoView({ behavior: 'smooth', block: 'start' });

      const origStyle = {
        color: target.options.color,
        weight: target.options.weight,
        fillOpacity: target.options.fillOpacity,
      };
      target._isFlashing = true;
      target.setStyle({ color: '#ffd700', weight: 5, fillOpacity: 0.95 });
      target.bringToFront();
      M.map.fitBounds(target.getBounds().pad(0.5), { maxZoom: 14, animate: true });

      setTimeout(() => {
        target.setStyle(origStyle);
        target._isFlashing = false;
      }, 1600);
    }, 100);
  }

  // Re-measure the container AND re-fit to the polygon extent. invalidateSize()
  // on its own keeps the old zoom, which leaves the region as a small blob in
  // the middle of the map.
  function fitMapExtent(M) {
    if (!M) return;
    M.map.invalidateSize();
    M.map.fitBounds(M.polyLayer.getBounds(), { padding: [14, 14] });
    M.map._needsFit = false;
  }

  window.addEventListener('resize', () => {
    Object.values(MAPS).forEach(M => M && M.map.invalidateSize());
  });

  // Expose for table row handlers
  window.flashPolygon = flashPolygon;
  window.initMap = initMap;
  window.MAPS = MAPS;

  // Initialize the currently visible method
  document.addEventListener('DOMContentLoaded', () => {
    const active = document.querySelector('.method-content:not(.hidden)');
    if (active) {
      const cls = Array.from(active.classList).find(c => c.startsWith('method-') && c !== 'method-content');
      const method = cls ? cls.replace('method-', '') : 'single';
      const M = initMap(method);
      if (M) setTimeout(() => fitMapExtent(M), 80);
    }
  });

  // Method toggle: ensure target map is initialized and sized
  document.querySelectorAll('.method-toggle button').forEach(btn => {
    btn.addEventListener('click', () => {
      const m = btn.dataset.method;
      document.querySelectorAll('.method-toggle button').forEach(b =>
        b.classList.toggle('active', b === btn));
      document.querySelectorAll('.method-content').forEach(c =>
        c.classList.toggle('hidden', !c.classList.contains('method-' + m)));
      setTimeout(() => {
        const M = initMap(m);
        // Only re-fit the first time a map is shown; afterwards respect the
        // user's pan/zoom.
        if (M) { if (M.map._needsFit) fitMapExtent(M); else M.map.invalidateSize(); }
        const visible = document.querySelector('.method-content:not(.hidden)');
        if (visible) visible.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 60);
    });
  });

  // Table row → flash polygon
  document.querySelectorAll('tr[data-zone-label]').forEach(row => {
    row.title = 'Click to locate on the map';
    row.addEventListener('click', () => {
      const methodContent = row.closest('.method-content');
      let method = 'single';
      if (methodContent) {
        const cls = Array.from(methodContent.classList).find(c => c.startsWith('method-') && c !== 'method-content');
        if (cls) method = cls.replace('method-', '');
      }
      flashPolygon(method, row.dataset.zoneLabel);
    });
  });
})();
"""


def _map_block(method, method_pretty, is_lwa, has_zone_overlay,
               zone_toggle_html, zone_boundary_key, zone_legend_swatches,
               zone_boundary_sentence):
    """Map toolbar + Leaflet div + legend + caption. Fixed methods color by
    loss-rate (with a zone option); the LWA variants show the latest-year dense
    network coloured by source (RMS vs LWA), so they get a source legend and no
    loss/zone color-by control."""
    basemap = f"""  <span class="map-toolbar-label">Basemap:</span>
  <select class="map-basemap-select" id="basemap-select-{method}">
    <option value="none" selected>None</option>
    <option value="carto">CartoDB Positron</option>
    <option value="esri-topo">Esri World Topo</option>
    <option value="esri-sat">Satellite (Esri World Imagery)</option>
    <option value="osm">OpenStreetMap</option>
  </select>"""
    if is_lwa:
        return f"""<p>The map shows the <strong>WY 2026 network</strong> — RMS wells (<span style="color:#2a78d6;font-weight:700;">blue</span>) plus the LWA telemetry wells (<span style="color:#eb6834;font-weight:700;">orange</span>) that reported that year. The LWA wells join the tessellation only for the recent years; the historical storage series (1999–2023) uses the RMS-only network from the base method.{zone_boundary_sentence}</p>
<div class="map-toolbar">
{basemap}
  <span class="map-toolbar-label" style="margin-left:8px;">Layers:</span>
  <label class="map-toggle"><input type="checkbox" id="fill-toggle-{method}" checked/><span>Polygon fill</span></label>
  {zone_toggle_html}
  <label class="map-toggle"><input type="checkbox" id="label-toggle-{method}" checked/><span>Well labels</span></label>
</div>
<div id="map-{method}" class="leaflet-map" aria-label="WY 2026 RMS+LWA network for {method_pretty}"></div>
<div class="map-legend-row">
  <div class="map-legend-title">WY 2026 network (RMS + LWA telemetry)</div>
  <div class="map-legend-swatches">
    <div><span class="sw" style="background:#2a78d6"></span> RMS-well cell</div>
    <div><span class="sw" style="background:#eb6834"></span> LWA-well cell</div>
    {zone_boundary_key}
    <div><span class="dot" style="background:#1f1f1f"></span> Well</div>
  </div>
</div>
<div class="figcaption">Figure 4. Snapshot of the WY 2026 tessellation with the LWA telemetry wells included. The polygons here are the recent-year network; the storage numbers use the RMS-only geometry for 1999–2023 and add the LWA wells for 2024–2026. Click a cell for its network and area.</div>"""
    return f"""<p>The map below colors each polygon by its <strong>average observed storage loss rate</strong> (AF/yr) across its measurement record. Light green = polygon is gaining storage; oranges → reds = magnitude of average annual loss. Switch <strong>Color by</strong> to <em>Management zone</em> to see which zone each cell belongs to instead.{zone_boundary_sentence} Hover a polygon to bring its outline forward; click it for full detail including the year-type-normalized rate.</p>
<div class="map-toolbar">
  <span class="map-toolbar-label">Color by:</span>
  <select class="map-basemap-select" id="colormode-select-{method}">
    <option value="loss" selected>Storage loss rate</option>
    <option value="zone">Management zone</option>
  </select>
  <span class="map-toolbar-label" style="margin-left:8px;">Basemap:</span>
  <select class="map-basemap-select" id="basemap-select-{method}">
    <option value="none" selected>None</option>
    <option value="carto">CartoDB Positron</option>
    <option value="esri-topo">Esri World Topo</option>
    <option value="esri-sat">Satellite (Esri World Imagery)</option>
    <option value="osm">OpenStreetMap</option>
  </select>
  <span class="map-toolbar-label" style="margin-left:8px;">Layers:</span>
  <label class="map-toggle">
    <input type="checkbox" id="fill-toggle-{method}" checked/>
    <span>Polygon fill</span>
  </label>
  {zone_toggle_html}
  <label class="map-toggle">
    <input type="checkbox" id="label-toggle-{method}" checked/>
    <span>Section labels</span>
  </label>
</div>
<div id="map-{method}" class="leaflet-map" aria-label="Interactive polygon map for {method_pretty}"></div>
<div class="map-legend-row" id="legend-loss-{method}">
  <div class="map-legend-title">Polygon avg observed storage loss rate (AF/yr)</div>
  <div class="map-legend-swatches">
    <div><span class="sw" style="background:#a8c8b0"></span> Gaining</div>
    <div><span class="sw" style="background:#f0d9a8"></span> Loss &lt; 250</div>
    <div><span class="sw" style="background:#e3a76f"></span> Loss &lt; 750</div>
    <div><span class="sw" style="background:#cb7740"></span> Loss &lt; 1,500</div>
    <div><span class="sw" style="background:#a84a2c"></span> Loss &lt; 2,500</div>
    <div><span class="sw" style="background:#7c2820"></span> Loss ≥ 2,500</div>
    {zone_boundary_key}
    <div><span class="dot" style="background:#1f1f1f"></span> RMS well</div>
  </div>
</div>
<div class="map-legend-row" id="legend-zone-{method}" hidden>
  <div class="map-legend-title">Management zone (polygon count)</div>
  <div class="map-legend-swatches">
    {zone_legend_swatches}
    {zone_boundary_key}
    <div><span class="dot" style="background:#1f1f1f"></span> RMS well</div>
  </div>
</div>
<div class="figcaption">Figure 4. Click any polygon for full detail. <strong>Color by</strong> switches between the loss-rate ramp and categorical zone colors. Toggle the basemap on to see streets / parcels / hydrology under the cells; toggle the fill off to see what's underneath without re-coloring. Click any row in the tables below to fly to that polygon and flash it briefly.</div>"""


def _render_method_section(method, results, portfolio, zone_colors=None):
    """Build the per-method HTML content block.  Returns an HTML string
    (no <html>/<body> wrappers — to be inserted inside method-content div)."""
    pol_summaries = results["pol_summaries"]
    basin_buckets = results["basin_buckets"]
    basin_net = results["basin_cumulative_2025"]
    basin_polygon_summed_need = results["basin_polygon_summed_need"]
    basin_loss_rate = results["basin_loss_rate"]
    basin_portfolio_margin = results["basin_portfolio_margin"]
    basin_annual = results["basin_annual"]
    polygon_map_svg = results["polygon_map_svg"]
    bar_svg = results["bar_svg"]
    ts_svg = results["ts_svg"]
    context_svg = results["context_svg"]
    sy_lookup = results["sy_lookup"]
    trough_cum = results["trough_cum"]
    trough_year = results["trough_year"]
    n_by_type = results["n_by_type"]
    basin_normalized_cum_2025 = results["basin_normalized_cumulative_2025"]
    basin_normalized_avg_rate = results["basin_normalized_avg_rate"]
    basin_normalized_summed_need = results["basin_normalized_polygon_summed_need"]
    basin_normalized_margin = results["basin_normalized_portfolio_margin"]
    n_by_type_full = results["n_by_type_full"]
    project_total_afy = results["project_total_afy"]

    worst_year_deficit_int = int(round(abs(trough_cum)))
    abs_2022_cushion_int = int(round(abs(trough_cum) - abs(basin_net)))
    sorted_pols = sorted(pol_summaries,
                         key=lambda s: -s["hold_steady_need_AF_per_yr"])
    short_pols = [s for s in pol_summaries if s["coverage_net_AF_per_yr"] < 0]
    short_pols.sort(key=lambda s: s["coverage_net_AF_per_yr"])
    over_pols  = [s for s in pol_summaries if s["coverage_net_AF_per_yr"] > 0
                  and s["project_alloc_AF_per_yr"] > 0]
    over_pols.sort(key=lambda s: -s["coverage_net_AF_per_yr"])

    n_polygons = len(pol_summaries)

    detail_rows = []
    for s in sorted_pols:
        late_marker = (' <span class="late" title="Baseline year > 1999">'
                       f'(record starts {s["baseline_year"]})</span>'
                       if s["baseline_year"] > START_YEAR else "")
        # Sy is uniform across all polygons, so no per-row provenance marker.
        sy_marker = ""
        cum = s["endpoint_cum_storage_AF"]
        avg = s["avg_rate_AF_per_yr"]
        norm_cum = s.get("normalized_cum_2025_AF", 0)
        norm_avg = s.get("normalized_avg_rate_AF_per_yr", 0)
        hold = s["hold_steady_need_AF_per_yr"]
        proj = s["project_alloc_AF_per_yr"]
        net = s["coverage_net_AF_per_yr"]
        net_str = (f'<span class="gain">+{int(net):,}</span>' if net > 0
                   else (f'<span class="loss">{int(net):,}</span>' if net < 0 else "0"))
        proj_str = f"{int(proj):,}" if proj > 0 else "—"
        crit_dry_af = s["bucket_storage_AF"]["critical"] + s["bucket_storage_AF"]["dry"]
        fallback_types = [k for k, src in (s.get("rate_per_bucket_source") or {}).items()
                          if "fallback" in src]
        fallback_marker = (f' <span class="fallback" title="Year-type(s) not observed; '
                          f'using polygon overall avg as fallback: {", ".join(fallback_types)}">'
                          f'(fb)</span>' if fallback_types else "")
        detail_rows.append(f"""<tr data-zone-label="{s['zone_label']}">
      <td><strong>{s["zone_label"]}</strong> <span style="color:#8a8a8a;font-size:11px;">{s["ma"]}</span>{late_marker}</td>
      <td class="num">{s["span_years"]} yr ({s["baseline_year"]}–{s["endpoint_year"]})</td>
      <td class="num">{s["sy"]:.4f}{sy_marker}</td>
      <td class="num">{loss_or_gain_span(cum, 0)}</td>
      <td class="num">{loss_or_gain_span(avg, 0)}</td>
      <td class="num">{loss_or_gain_span(norm_cum, 0)}{fallback_marker}</td>
      <td class="num">{loss_or_gain_span(norm_avg, 0)}</td>
      <td class="num">{loss_or_gain_span(crit_dry_af, 0)}</td>
      <td class="num">{s["crit_dry_share_of_drawdown_pct"]:.0f}%</td>
    </tr>""")

    project_rows = []
    for proj in portfolio.get("projects", []):
        zone = proj["polygon"]
        afy = proj["af_per_yr"]
        name = proj["name"]
        s = next((p for p in pol_summaries if p["zone_label"] == zone), None)
        if s is None:
            continue
        loss = s["hold_steady_need_AF_per_yr"]
        net = s["coverage_net_AF_per_yr"]
        net_str = (f'<span class="gain">+{int(net):,}</span>' if net > 0
                   else (f'<span class="loss">{int(net):,}</span>' if net < 0 else "0"))
        project_rows.append(f"""<tr data-zone-label="{zone}">
      <td><strong>{zone}</strong> <span style="color:#8a8a8a;font-size:11px;">{s['ma']}</span></td>
      <td>{name}</td>
      <td class="num">{int(afy):,}</td>
      <td class="num">{int(loss):,}</td>
      <td class="num">{net_str}</td>
    </tr>""")

    short_rows = []
    for s in short_pols:
        short_rows.append(f"""<tr data-zone-label="{s['zone_label']}">
      <td><strong>{s["zone_label"]}</strong> <span style="color:#8a8a8a;font-size:11px;">{s['ma']}</span></td>
      <td class="num">{int(s["hold_steady_need_AF_per_yr"]):,}</td>
      <td class="num">{int(s["project_alloc_AF_per_yr"]):,}</td>
      <td class="num"><span class="loss">{int(s["coverage_net_AF_per_yr"]):,}</span></td>
    </tr>""")
    short_total = sum(s["coverage_net_AF_per_yr"] for s in short_pols)

    basin_running = 0.0
    # Per-zone rollups are only meaningful for the four-zone method; in the
    # single tessellation cells cross zone lines, so a cell's storage cannot be
    # attributed wholly to one zone.
    is_four_zone = method.startswith("four-zone")
    zone_summaries = results.get("zone_summaries", []) if is_four_zone else []
    zone_cols = [zs["zone"] for zs in zone_summaries]
    zone_annual = {zs["zone"]: zs["annual_delta_AF"] for zs in zone_summaries}
    annual_zone_head = "".join(f'<th class="num">{z} ΔStor</th>' for z in zone_cols)

    annual_rows = []
    SVI_BADGE_STYLE = {
        "Wet":           "background:#e6f0e8;color:#2e6f3f;",
        "Above Normal":  "background:#eef5ee;color:#3a8050;",
        "Below Normal":  "background:#f7e8d2;color:#8a5a18;",
        "Dry":           "background:#fadcc9;color:#9c4521;",
        "Critical":      "background:#fbe6e6;color:#a32d2d;",
    }
    for y_str, delta in basin_annual.items():
        y = int(y_str)
        full = year_type_full(y)
        style = SVI_BADGE_STYLE.get(full, "background:#eee;color:#333;")
        basin_running += delta
        zone_cells = "".join(
            f'<td class="num">{loss_or_gain_span(zone_annual[z].get(y_str, 0), 0)}</td>'
            for z in zone_cols)
        annual_rows.append(
            f'<tr><td class="num">{y}</td>'
            f'<td><span style="{style}padding:1px 6px;border-radius:3px;font-size:11px;font-weight:600;">{full}</span></td>'
            f'{zone_cells}'
            f'<td class="num">{loss_or_gain_span(delta, 0)}</td>'
            f'<td class="num">{loss_or_gain_span(basin_running, 0)}</td></tr>'
        )

    n_critical = n_by_type["critical"]
    n_dry      = n_by_type["dry"]
    n_bn       = n_by_type["bn"]
    n_an       = n_by_type["an"]
    n_wet      = n_by_type["wet"]
    crit_per_yr = abs(basin_buckets["critical"] / n_critical) if n_critical else 0
    dry_per_yr  = abs(basin_buckets["dry"] / n_dry) if n_dry else 0
    crit_dry_total = basin_buckets["critical"] + basin_buckets["dry"]
    wet_an_total   = basin_buckets["wet"] + basin_buckets["an"]

    late_polys = [s for s in pol_summaries if s["baseline_year"] > START_YEAR]
    late_summary = "; ".join(f"{s['zone_label']} ({s['baseline_year']})" for s in late_polys)
    _late_years = [s["baseline_year"] for s in late_polys]
    late_min = min(_late_years) if _late_years else START_YEAR
    late_max = max(_late_years) if _late_years else START_YEAR

    sy_uniform = sy_lookup[pol_summaries[0]["zone_label"]] if pol_summaries else 0.10

    zone_counts = {z: sum(1 for s in pol_summaries if s["ma"] == z) for z in ZONE_ORDER}
    zone_breakdown = " · ".join(f"{n} {z}" for z, n in zone_counts.items() if n)


    # Reassignment notice — only for the zoned method
    reassigned_polys = [s for s in pol_summaries
                        if any(p.get("reassigned") and p.get("zone_label") == s["zone_label"]
                                for p in results["polygons_meta"])]
    reassigned_meta = [p for p in results["polygons_meta"] if p.get("reassigned")]
    reassignment_callout = ""
    if reassigned_meta and method.startswith("four-zone"):
        items = "; ".join(
            f"<code>{p['zone_label']}</code> (workbook tag: {p.get('workbook_mgmt_area', '?')} → spatial: {p.get('mgmt_area_full')})"
            for p in reassigned_meta
        )
        reassignment_callout = (
            f'<div class="callout tan"><strong>Spatial zone reassignment.</strong> '
            f'In the four-zone method, polygons are assigned to zones by '
            f'<em>spatial containment</em> in the management-area boundary polygons, not by '
            f'workbook tag. {len(reassigned_meta)} polygon{"s" if len(reassigned_meta) != 1 else ""} '
            f'reassigned: {items}. This is a deliberate on-the-record boundary call for SMC '
            f'defensibility (where the well physically sits matters for subsidence/SMC).</div>'
        )

    # Category breakdown
    cat_totals = _dd(int)
    recharge_by_name = _dd(int)
    for proj in portfolio.get("projects", []):
        cat_totals[proj.get("category", "other")] += int(proj.get("af_per_yr", 0))
        if proj.get("category") == "recharge":
            recharge_by_name[proj.get("name", "Recharge project")] += int(proj.get("af_per_yr", 0))
    portfolio_breakdown_parts = []
    if cat_totals.get("conjunctive-use"):
        portfolio_breakdown_parts.append(
            f"{cat_totals['conjunctive-use']:,} AF/yr conjunctive use (surface water replaces groundwater)")
    for name, afy in recharge_by_name.items():
        portfolio_breakdown_parts.append(f"{afy:,} AF/yr {name}")
    portfolio_breakdown = " + ".join(portfolio_breakdown_parts) if portfolio_breakdown_parts else f"{project_total_afy:,} AF/yr"

    svi_years_listing = []
    for label in ["Wet", "Above Normal", "Below Normal", "Dry", "Critical"]:
        yrs = [str(y) for y, t in SVI_YEAR_TYPE.items() if t == label]
        svi_years_listing.append(
            f'<li><strong>{label}:</strong> {", ".join(yrs)} ({len(yrs)} years)</li>')

    zone_colors = zone_colors or {}
    is_lwa = method.endswith("-lwa")
    # The zone-boundary overlay applies to the four-zone method (and its LWA
    # variant); in the single tessellation the cells cross zone lines by design.
    has_zone_overlay = method.startswith("four-zone")
    zone_toggle_html = (
        '<label class="map-toggle">'
        f'<input type="checkbox" id="zone-toggle-{method}" checked/>'
        '<span>Zone boundaries</span></label>'
    ) if has_zone_overlay else ""
    zone_boundary_key = (
        '<div><span class="zoneline"></span> Zone boundary</div>'
    ) if has_zone_overlay else ""
    zone_legend_swatches = "".join(
        f'<div><span class="sw" style="background:{zone_colors[z]}"></span> {z}'
        f' <span style="color:var(--ink-muted);">({zone_counts.get(z, 0)})</span></div>'
        for z in ZONE_ORDER if z in zone_colors
    )
    # Per-zone storage summary table (four-zone only).
    zone_summary_html = ""
    if zone_summaries:
        zs_rows = []
        for zs in zone_summaries:
            b = zs["bucket_storage_AF"]
            swatch = (f'<span class="sw" style="background:'
                      f'{zone_colors.get(zs["zone"], "#999")};'
                      f'display:inline-block;width:12px;height:9px;'
                      f'border:0.5px solid #332e22;margin-right:5px;"></span>')
            zs_rows.append(
                f'<tr><td>{swatch}<strong>{zs["zone"]}</strong></td>'
                f'<td class="num">{zs["n_polygons"]}</td>'
                f'<td class="num">{zs["area_ac"]:,.0f}</td>'
                f'<td class="num">{loss_or_gain_span(zs["cum_2025_AF"], 0)}</td>'
                f'<td class="num">{loss_or_gain_span(zs["normalized_cum_2025_AF"], 0)}</td>'
                f'<td class="num">{zs["avg_loss_rate_AF_per_yr"]:,.0f}</td>'
                f'<td class="num">{zs["normalized_avg_loss_rate_AF_per_yr"]:,.0f}</td>'
                f'<td class="num">{loss_or_gain_span(b["wet"], 0)}</td>'
                f'<td class="num">{loss_or_gain_span(b["an"], 0)}</td>'
                f'<td class="num">{loss_or_gain_span(b["bn"], 0)}</td>'
                f'<td class="num">{loss_or_gain_span(b["dry"], 0)}</td>'
                f'<td class="num">{loss_or_gain_span(b["critical"], 0)}</td></tr>'
            )
        tot_area = sum(zs["area_ac"] for zs in zone_summaries)
        tot_poly = sum(zs["n_polygons"] for zs in zone_summaries)
        zs_rows.append(
            f'<tr style="font-weight:700;border-top:2px solid var(--rule);">'
            f'<td>Region total</td><td class="num">{tot_poly}</td>'
            f'<td class="num">{tot_area:,.0f}</td>'
            f'<td class="num">{loss_or_gain_span(basin_net, 0)}</td>'
            f'<td class="num">{loss_or_gain_span(basin_normalized_cum_2025, 0)}</td>'
            f'<td class="num">{basin_loss_rate:,.0f}</td>'
            f'<td class="num">{-basin_normalized_avg_rate:,.0f}</td>'
            f'<td class="num">{loss_or_gain_span(basin_buckets["wet"], 0)}</td>'
            f'<td class="num">{loss_or_gain_span(basin_buckets["an"], 0)}</td>'
            f'<td class="num">{loss_or_gain_span(basin_buckets["bn"], 0)}</td>'
            f'<td class="num">{loss_or_gain_span(basin_buckets["dry"], 0)}</td>'
            f'<td class="num">{loss_or_gain_span(basin_buckets["critical"], 0)}</td></tr>'
        )
        zone_summary_html = f"""
<h3 style="margin-top:6px;">Storage summary by management zone</h3>
<p style="font-size:13px;color:var(--ink-muted);">Each polygon rolls up to the zone
it sits in (four-zone cells never cross zone lines). <strong>Cumulative</strong> sums
each polygon's endpoint cumulative; <strong>avg loss rate</strong> sums each polygon's
own average rate — not cumulative ÷ span, which would be wrong with staggered
baselines. Positive loss rate = zone is losing storage.</p>
<div style="overflow-x:auto;">
<table>
  <thead>
    <tr>
      <th rowspan="2">Zone</th><th class="num" rowspan="2">Polys</th>
      <th class="num" rowspan="2">Area (ac)</th>
      <th class="num" colspan="2">Cumulative ΔStorage to 2025 (AF)</th>
      <th class="num" colspan="2">Avg loss rate (AF/yr)</th>
      <th class="num" colspan="5">ΔStorage by SVI year type (AF)</th>
    </tr>
    <tr>
      <th class="num">Observed</th><th class="num">Normalized</th>
      <th class="num">Observed</th><th class="num">Normalized</th>
      <th class="num">Wet</th><th class="num">Above N</th><th class="num">Below N</th>
      <th class="num">Dry</th><th class="num">Critical</th>
    </tr>
  </thead>
  <tbody>{chr(10).join(zs_rows)}</tbody>
</table>
</div>
"""

    zone_boundary_sentence = (
        ' The heavy dark outline is the <strong>zone boundary</strong> '
        '(CCWD, RD108, Dunnigan, Other); polygons within a zone are divided by '
        'a fine hairline.'
        if has_zone_overlay else
        ' Polygons are divided by a fine hairline; cells here are one basin-wide '
        'tessellation and deliberately cross zone lines, so no zone boundary is drawn.'
    )

    method_pretty = METHOD_LABEL[method]
    lwa_note = (
        " <strong>+ LWA telemetry.</strong> Two-regime: the RMS network above governs "
        "1999–2023 exactly as the base method; the LWA telemetry wells (provisional QA) "
        "join the tessellation only for 2024–2026, observed-only (not backcast). WY2026 "
        "is provisional (incomplete water year, no SVI type) — included in the cumulative "
        "but excluded from the year-type buckets."
        if is_lwa else "")
    method_summary = (
        f"<strong>{method_pretty}.</strong> "
        + (f"All {n_polygons} polygons built as one Voronoi tessellation clipped to the region boundary; "
           "cells can cross management-area lines."
           if method.startswith("single") else
           "Four independent Voronoi tessellations (one per zone), each clipped to "
           "its own boundary; cells do NOT cross zone lines. Single-well zones "
           "(Dunnigan) are one dissolved polygon.")
        + f" {n_polygons} polygons total ({zone_breakdown})."
        + lwa_note
    )

    map_block = _map_block(method, method_pretty, is_lwa, has_zone_overlay,
                           zone_toggle_html, zone_boundary_key,
                           zone_legend_swatches, zone_boundary_sentence)

    return f"""<div class="method-banner">{method_summary}</div>

<p class="lead">Across WY 1999–2025, loss is sharply concentrated in <strong>Critical and Dry</strong> water-year types, with <strong>Wet and Above-Normal</strong> years doing the recovery work. The region's <strong>observed</strong> net deficit is <strong>{abs(basin_net)/1000:.0f}k AF — about {abs(basin_net)/TOTAL_FRESH_STORAGE_AF*100:.2f}% of the {int(TOTAL_FRESH_STORAGE_AF/1_000_000)}+ MAF in regional storage</strong>; the <strong>year-type-normalized</strong> deficit is <strong>{abs(basin_normalized_cum_2025)/1000:.0f}k AF</strong> ({abs(basin_normalized_cum_2025)/TOTAL_FRESH_STORAGE_AF*100:.2f}%). Region avg loss rate: <strong>{basin_loss_rate:,.0f} AF/yr observed</strong> / <strong>{-basin_normalized_avg_rate:,.0f} AF/yr normalized</strong>.</p>

{reassignment_callout}

<div class="headline">
  <div class="stat warn">
    <div class="num warn">{crit_dry_total:+,.0f}</div>
    <div class="lab">AF lost in Critical + Dry years</div>
    <div class="det">{n_critical} Critical + {n_dry} Dry years ({(n_critical+n_dry)*100/(n_wet+n_an+n_bn+n_dry+n_critical):.0f}% of the record). Critical years alone removed {basin_buckets["critical"]:+,.0f} AF.</div>
  </div>
  <div class="stat tan">
    <div class="num tan">{basin_buckets["bn"]:+,.0f}</div>
    <div class="lab">AF in Below-Normal years</div>
    <div class="det">{n_bn} Below-Normal years. Mixed contribution — typically small net loss.</div>
  </div>
  <div class="stat acc">
    <div class="num acc">{wet_an_total:+,.0f}</div>
    <div class="lab">AF gained in Wet + Above-Normal years</div>
    <div class="det">{n_wet} Wet + {n_an} Above-Normal years. The region is already recharging — just not fast enough to keep up with Critical years on its own.</div>
  </div>
</div>

<div class="callout"><strong>The picture in one sentence.</strong> Across 1999–2025, Critical and Dry years removed about <strong>{abs(crit_dry_total):,.0f} AF</strong>, Below-Normal years moved storage by <strong>{basin_buckets["bn"]:+,.0f} AF</strong>, and Wet + Above-Normal years recovered <strong>{wet_an_total:+,.0f} AF</strong>. Net region deficit through 2025: <strong>{basin_net:+,.0f} AF observed / {basin_normalized_cum_2025:+,.0f} AF year-type-normalized</strong>, summed across all {n_polygons} polygons.</div>

<h2>Method, in brief</h2>
<p>Per polygon: ΔStorage<sub>p,y</sub> = (GWE<sub>p,y</sub> − GWE<sub>p,baseline</sub>) × Sy<sub>p</sub> × Area<sub>p</sub>. GWE<sub>p,y</sub> is the polygon's RMS well's spring composite (March mean for SWN-named wells), Good-quality DWR records only. Each polygon is anchored to WY 1999 if it has a Good spring composite that year; otherwise to the polygon's first observation after 1999. We then take the per-polygon cumulative storage time series, compute year-over-year deltas (distributing multi-year DWR gaps evenly), and bucket each year by its <strong>official Sacramento Valley Index water-year type</strong>.</p>

<p><strong>Specific yield is uniform: Sy = {sy_uniform:.2f}</strong> for every polygon. A per-polygon Sy derived from DWR's SVSim Texture Data (Sacramento Valley Simulation Model v1.0) is still computed by <code>scripts/build_sy_svsim.py</code> and written to <code>data/polygon_sy_svsim_*.csv</code> for reference — it ranged 0.0565–0.0986 with an area-weighted mean of ≈0.077 — but the storage numbers on this page use the flat 0.10. Storage scales linearly with Sy, so the SVSim basis would give a deficit roughly 30% smaller.</p>


<p>Year-type classification uses DWR's Sacramento Valley Index (Northern Sierra 8-Station Index):</p>
<ul>
{chr(10).join(svi_years_listing)}
</ul>

<p><strong>Baseline asymmetry.</strong> Polygons anchored to WY 1999: those whose RMS well had a Good March measurement that year ({n_polygons - len(late_polys)} of {n_polygons}). The rest baseline later: {late_summary}.</p>

<h2>When and where the region loses water</h2>

<div class="figure">{bar_svg}</div>
<div class="figcaption">Figure 1. Sum across all {n_polygons} polygons, gap-attributed by year, bucketed by official Sacramento Valley Index water-year type. Critical years alone average {crit_per_yr:,.0f} AF/yr of loss — about {(crit_per_yr/dry_per_yr if dry_per_yr else 0):.1f}× the per-year loss rate of Dry years.</div>

<div class="figure">{ts_svg}</div>
<div class="figcaption">Figure 2. Basin cumulative ΔStorage. <strong>Solid blue line = observed</strong> (each polygon contributes only years its RMS well actually measured). <strong>Dashed purple line = year-type-weighted normalized</strong> (corrects for late-baseline drag — see callout below).</div>

<div class="callout warn"><strong>Late-baseline drag and the year-type-weighted normalization.</strong> Of the {n_polygons} polygons, only {n_polygons - len(late_polys)} have a Good March measurement in WY 1999. The other {len(late_polys)} baseline later — between {late_min} and {late_max} — because their RMS well wasn't measured in 1999. Late-baseline polygons cannot register their pre-baseline drawdown, so the <strong>observed</strong> region cumulative ({basin_net:+,.0f} AF through 2025) <em>understates</em> what the region would show if every polygon had a full record.<br><br>The <strong>year-type-weighted normalized</strong> series corrects this. For each polygon, we compute its average ΔStorage <em>per Sacramento Valley Index year type</em> using <em>only its own observations</em>. We then synthesize what that polygon would have contributed across the full WY 1999–2025 record by applying its per-type rates to the region's actual year-type mix ({n_by_type_full["wet"]} Wet, {n_by_type_full["an"]} AN, {n_by_type_full["bn"]} BN, {n_by_type_full["dry"]} Dry, {n_by_type_full["critical"]} Critical = 26 transition years). Summed across all {n_polygons} polygons, that gives the normalized region total: <strong>{basin_normalized_cum_2025:+,.0f} AF</strong> through 2025 — an avg loss rate of <strong>{-basin_normalized_avg_rate:,.0f} AF/yr</strong>, vs. the observed {basin_loss_rate:,.0f} AF/yr.</div>

<h3>Putting the deficit in proportion</h3>
<div class="figure">{context_svg}</div>
<div class="figcaption">Figure 3. The bar is the full {TOTAL_STORAGE_LABEL} of fresh groundwater in storage (<strong>PLACEHOLDER</strong> pending {SOURCE_GSP_LABEL}). The dark-red sliver is the WY 2025 cumulative deficit; the lighter orange behind it is the WY {trough_year} trough (deepest observed deficit). Both are shown at true scale — the deficit is real and worth managing, but small relative to total storage.</div>

<h2>Where the region loses storage — by polygon</h2>

{map_block}

<h2>Per-polygon detail (technical)</h2>
<table>
  <thead>
    <tr>
      <th>Polygon</th>
      <th class="num">Span</th>
      <th class="num">Sy</th>
      <th class="num">Cum 2025 obs (AF)</th>
      <th class="num">Avg obs (AF/yr)</th>
      <th class="num">Cum 2025 norm (AF)</th>
      <th class="num">Avg norm (AF/yr)</th>
      <th class="num">Crit+Dry (AF)</th>
      <th class="num">Crit+Dry share</th>
    </tr>
  </thead>
  <tbody>{chr(10).join(detail_rows)}</tbody>
  <tfoot>
    <tr>
      <th>Basin (sum)</th><th class="num">—</th><th class="num">—</th>
      <th class="num"><strong>{basin_net:+,.0f}</strong></th>
      <th class="num">{-basin_loss_rate:+,.0f}</th>
      <th class="num"><strong>{basin_normalized_cum_2025:+,.0f}</strong></th>
      <th class="num">{-basin_normalized_avg_rate:+,.0f}</th>
      <th class="num">{crit_dry_total:+,.0f}</th><th class="num">—</th>
    </tr>
  </tfoot>
</table>

<details>
<summary>Annual region time series (2000–2025), gap-attributed</summary>
{zone_summary_html}
<h3 style="margin-top:6px;">Annual ΔStorage</h3>
<p style="font-size:13px;color:var(--ink-muted);">Sum of all {n_polygons} polygons' year-over-year storage change, uniform Sy = {sy_uniform:.2f}.</p>
<div style="overflow-x:auto;">
<table>
  <thead><tr><th class="num">Year</th><th>Condition</th>{annual_zone_head}<th class="num">Region ΔStor (AF)</th><th class="num">Cumulative (AF)</th></tr></thead>
  <tbody>{chr(10).join(annual_rows)}</tbody>
</table>
</div>
</details>
"""


def write_index_html(out_path, results_by_method, portfolio,
                     zone_boundaries=None, zone_colors=None,
                     zone_boundary_ink="#1a1612"):
    """Build the toggle-able single-file dashboard."""
    import json as _json

    zone_boundaries = zone_boundaries or []
    zone_colors = zone_colors or {}

    method_sections = {
        m: _render_method_section(m, r, portfolio, zone_colors)
        for m, r in results_by_method.items()
    }

    polygons_by_method = {
        m: r.get("polygons_for_js", []) for m, r in results_by_method.items()
    }

    method_order = [m for m in ("single", "four-zone", "single-lwa",
                                "four-zone-lwa") if m in method_sections]

    polygons_json = _json.dumps(polygons_by_method, separators=(",", ":"))
    zone_boundaries_json = _json.dumps(zone_boundaries, separators=(",", ":"))
    zone_colors_json = _json.dumps(zone_colors, separators=(",", ":"))

    toggle_buttons = []
    for m in method_order:
        if m in method_sections:
            active = " active" if m == "single" else ""
            toggle_buttons.append(
                f'<button data-method="{m}" class="{active.strip()}" title="{METHOD_LABEL[m]}">{METHOD_SHORT[m]}</button>'
            )
    toggle_html = (
        '<div class="method-toggle">'
        '<span class="method-toggle-label">Method:</span>'
        + "".join(toggle_buttons)
        + '</div>'
    )

    sections_html = []
    for m in method_order:
        if m in method_sections:
            hidden = "" if m == "single" else " hidden"
            sections_html.append(
                f'<div class="method-content method-{m}{hidden}">'
                + method_sections[m]
                + '</div>'
            )

    # Polygon count for the subtitle; both methods produce the same count today.
    n_polygons_total = max(
        (len(r.get("polygons_for_js", [])) for r in results_by_method.values()),
        default=0,
    )

    # Render README.md → HTML for the embedded methodology section.
    readme_html = ""
    readme_path = out_path.parent / "README.md"
    if readme_path.exists():
        try:
            import markdown as _md
            md_text = readme_path.read_text(encoding="utf-8")
            body = _md.markdown(
                md_text,
                extensions=["tables", "fenced_code", "sane_lists"],
                output_format="html5",
            )
            readme_html = (
                '<details class="readme-section" open>'
                '<summary>Methodology — full README</summary>'
                '<div class="readme-content">'
                + body +
                '</div>'
                '</details>'
            )
        except Exception as _e:
            readme_html = (
                f'<div class="readme-stale-callout">README render failed: {_e}</div>'
            )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>SCNY Region: Groundwater Storage — RMS Network (DRAFT)</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
<style>{INDEX_CSS}</style>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Spectral:wght@400;500;700&family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
</head>
<body>
<div class="container">

<h1>SCNY Region — A Drought-Conditioned Look at Groundwater Storage (DRAFT)</h1>
<div class="callout warn"><strong>DRAFT.</strong> Headline denominators (sustainable yield, total storage in {TOTAL_STORAGE_LABEL}) are <strong>PLACEHOLDERS</strong> pending the SCNY-area GSP citation. Volumetric AF/yr results do not depend on them.</div>
<p class="subtitle">July 2026 · Larry Walker Associates · {n_polygons_total} polygons · 27 RMS wells · polygon-by-polygon Sy from DWR SVSim Texture Data · WY 1999–2025 · ΔGWE × Sy<sub>p</sub> × Area<sub>p</sub>, sliced by hydrologic condition · observed vs. year-type-normalized cumulative storage change.</p>

{toggle_html}

{chr(10).join(sections_html)}

{readme_html}

<div class="footer">
<p><strong>Files in this folder.</strong> <code>index.html</code> (this page) · <code>data/condition_analysis_{{single,four_zone}}.json</code> · <code>data/sustainability_2042_{{single,four_zone}}.json</code> · <code>data/basin_annual_{{single,four_zone}}.json</code> (observed + normalized) · <code>data/model_data_{{single,four_zone}}.json</code> · <code>data/polygon_storage_2025_{{single,four_zone}}.csv</code> · <code>data/storage_timeseries_{{single,four_zone}}.csv</code> · <code>data/polygon_sy_svsim_{{single,four_zone}}.csv</code> · <code>data/project_portfolio.json</code> (editable input) · per-method SVGs (<code>polygon_map_*.svg</code>, <code>basin_buckets_chart_*.svg</code>, <code>basin_cumulative_chart_*.svg</code>, <code>storage_context_*.svg</code>).</p>
<p><strong>Upstream.</strong> RMS wells come from <code>Colusa_Yolo_RMS.xlsx</code>, spatially filtered to the SCNY region boundary (27 of 106 wells inside). DWR periodic GWL measurements are pulled from the DWR CKAN datastore. Polygons are built locally by <code>scripts/build_polygons.py</code> — both <code>polygons-data-single.js</code> (single region-wide tessellation) and <code>polygons-data-four-zone.js</code> (four independent tessellations per zone).</p>
<p><strong>Status.</strong> Independent analysis revised by Larry Walker Associates. Comments and corrections welcomed.</p>
</div>

</div>

<script>
window.POLYGONS_BY_METHOD = {polygons_json};
window.ZONE_BOUNDARIES = {zone_boundaries_json};
window.ZONE_COLORS = {zone_colors_json};
window.ZONE_BOUNDARY_INK = "{zone_boundary_ink}";
window.LWA_LATEST_YEAR = "{END_YEAR}";
</script>
<script>{MAP_JS}</script>

</body>
</html>
"""
    out_path.write_text(html, encoding="utf-8")
