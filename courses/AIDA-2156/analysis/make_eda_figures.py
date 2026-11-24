"""Generate reproducible, colourblind-safe SVG figures for the formal AIDA 2156 EDA.

Uses Python 3.13 standard library only (no third-party plotting packages).
Reads the verified outputs of analysis/analysis.py from output/final_eda/ and
writes labelled vector figures with embedded <title>/<desc> accessibility text
to output/final_eda/figures/.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import math
from pathlib import Path

COURSE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR = COURSE_DIR / "output" / "final_eda"

# Okabe-Ito colourblind-safe palette
C_BLUE = "#0072B2"
C_ORANGE = "#D55E00"
C_GREEN = "#009E73"
C_PURPLE = "#CC79A7"
C_SKY = "#56B4E9"
C_YELLOW = "#E69F00"
C_DARK = "#1F2937"
C_MUTED = "#4B5563"
C_GRID = "#E5E7EB"
C_BG = "#FFFFFF"
C_PANEL = "#F9FAFB"

STATION_NAMES = {
    "05CB007": "Dickson Dam (05CB007)",
    "05CB001": "Little Red Deer (05CB001)",
    "05CC007": "Medicine River (05CC007)",
    "05CC002": "Red Deer (05CC002)",
    "05CC003": "Sylvan Lake (05CC003)",
}


def esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def svg_header(width: int, height: int, title: str, desc: str) -> list[str]:
    return [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="fig-title fig-desc">',
        f"  <title id=\"fig-title\">{esc(title)}</title>",
        f"  <desc id=\"fig-desc\">{esc(desc)}</desc>",
        "  <style>",
        "    text { font-family: 'Segoe UI', Arial, Helvetica, sans-serif; fill: #1F2937; }",
        "    .title { font-size: 18px; font-weight: 700; }",
        "    .subtitle { font-size: 12px; fill: #4B5563; }",
        "    .axis-title { font-size: 12px; font-weight: 600; fill: #1F2937; }",
        "    .tick { font-size: 11px; fill: #374151; }",
        "    .label { font-size: 11px; font-weight: 600; }",
        "    .small { font-size: 10px; fill: #4B5563; }",
        "    .footer { font-size: 10px; fill: #6B7280; }",
        "  </style>",
        f'  <rect x="0" y="0" width="{width}" height="{height}" fill="{C_BG}" />',
    ]


def coverage_fill(frac: float) -> tuple[str, str]:
    """Return (fill_hex, text_hex) using a luminance-monotonic blue scale."""
    if frac <= 0.0001:
        return "#F3F4F6", "#6B7280"
    if frac < 0.25:
        return "#FEE2E2", "#991B1B"
    if frac < 0.80:
        return "#FDE68A", "#78350F"
    if frac < 0.95:
        return "#BAE6FD", "#0C4A6E"
    if frac < 0.995:
        return "#38BDF8", "#082F49"
    return "#0369A1", "#FFFFFF"


def build_fig1_monthly_coverage(in_dir: Path, out_dir: Path) -> Path:
    rows = list(csv.DictReader((in_dir / "coverage.csv").open(encoding="utf-8")))
    series_order = [
        ("05CB007", "discharge", "Dickson Dam Q (05CB007)"),
        ("05CB001", "discharge", "Little Red Deer Q (05CB001)"),
        ("05CC007", "discharge", "Medicine River Q (05CC007)"),
        ("05CC002", "discharge", "Red Deer Q (05CC002)"),
        ("05CC003", "level", "Sylvan Lake Level (05CC003)"),
    ]
    months = sorted({r["month_utc"] for r in rows})
    lookup = {
        (r["station"], r["parameter"], r["month_utc"]): float(r["numeric_grid_coverage_fraction"])
        for r in rows
    }

    w, h = 1120, 410
    left, top = 215, 95
    cell_w, cell_h = 45, 42
    lines = svg_header(
        w,
        h,
        "Monthly 5-Minute Grid Coverage by Station (May 2025 – Nov 2026 UTC)",
        "Heatmap matrix showing monthly numeric grid coverage percentages for four Red Deer River "
        "discharge gauges and Sylvan Lake water level. River gauges stay near 79–100% each month, "
        "whereas Sylvan Lake drops to 1.0% in Nov 2025, 0.0% from Dec 2025 to Mar 2026, and 4.1% in Apr 2026.",
    )
    lines.append('  <text x="24" y="34" class="title">Figure 1. Monthly 5-Minute Grid Coverage by Station (UTC)</text>')
    lines.append(
        '  <text x="24" y="54" class="subtitle">'
        "Percentage of inferred 5-minute UTC slots with numeric values (2025-05-03 to 2026-11-03). "
        "Sylvan Lake has a 6-month winter gap (Nov 2025 – Apr 2026)."
        "</text>"
    )

    # Month column headers
    for ci, m in enumerate(months):
        cx = left + ci * cell_w + cell_w / 2
        short_m = m[2:]  # e.g., 25-05
        lines.append(f'  <text x="{cx:.1f}" y="{top - 10}" text-anchor="middle" class="tick">{esc(short_m)}</text>')

    # Cells
    for ri, (st, param, label) in enumerate(series_order):
        y = top + ri * cell_h
        lines.append(
            f'  <text x="{left - 12}" y="{y + cell_h / 2 + 4:.1f}" text-anchor="end" class="label">{esc(label)}</text>'
        )
        for ci, m in enumerate(months):
            x = left + ci * cell_w
            frac = lookup[(st, param, m)]
            fill, txt_col = coverage_fill(frac)
            pct = frac * 100.0
            pct_str = "0%" if pct == 0 else ("100%" if pct >= 99.95 else f"{pct:.0f}%")
            if 0 < pct < 10:
                pct_str = f"{pct:.1f}%"
            lines.append(
                f'  <rect x="{x + 1}" y="{y + 1}" width="{cell_w - 2}" height="{cell_h - 2}" '
                f'rx="3" fill="{fill}" stroke="#FFFFFF" stroke-width="1" />'
            )
            lines.append(
                f'  <text x="{x + cell_w / 2:.1f}" y="{y + cell_h / 2 + 4:.1f}" '
                f'text-anchor="middle" style="font-size:10px;font-weight:600;fill:{txt_col};">{esc(pct_str)}</text>'
            )

    # Highlight Sylvan Lake winter gap outline
    gap_start = months.index("2025-11")
    gap_end = months.index("2026-04")
    gx = left + gap_start * cell_w
    gy = top + 4 * cell_h
    gw = (gap_end - gap_start + 1) * cell_w
    lines.append(
        f'  <rect x="{gx}" y="{gy}" width="{gw}" height="{cell_h}" fill="none" '
        f'stroke="{C_ORANGE}" stroke-width="2.5" stroke-dasharray="5,3" rx="4" />'
    )
    lines.append(
        f'  <text x="{gx + gw / 2:.1f}" y="{gy + cell_h + 18}" text-anchor="middle" '
        f'style="font-size:11px;font-weight:700;fill:{C_ORANGE};">'
        "Winter lake gap: removes 48,571 river-only timestamps on non-lake dates"
        "</text>"
    )

    # Legend
    ly = 352
    legend_items = [
        ("#F3F4F6", "#6B7280", "0%"),
        ("#FEE2E2", "#991B1B", "0.1–24.9%"),
        ("#FDE68A", "#78350F", "25–79.9%"),
        ("#BAE6FD", "#0C4A6E", "80–94.9%"),
        ("#38BDF8", "#082F49", "95–99.4%"),
        ("#0369A1", "#FFFFFF", "99.5–100%"),
    ]
    lines.append(f'  <text x="24" y="{ly + 13}" class="small" style="font-weight:600;">Coverage band:</text>')
    lx = 118
    for fill, txt_col, txt in legend_items:
        lines.append(f'  <rect x="{lx}" y="{ly}" width="18" height="16" rx="2" fill="{fill}" stroke="#D1D5DB" />')
        lines.append(f'  <text x="{lx + 24}" y="{ly + 12}" class="small">{esc(txt)}</text>')
        lx += 96

    lines.append(
        '  <text x="24" y="392" class="footer">'
        "Source: Frozen WSC/ECCC 5-min archive (output/final_eda/coverage.csv; denominator = 158,112 inferred UTC slots; 2026-11 is partial through Nov 3). "
        "Exact percentages printed in every cell so no value depends on colour."
        "</text>"
    )
    lines.append("</svg>")
    out = out_dir / "fig1_monthly_coverage.svg"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def build_fig2_discharge_distributions(in_dir: Path, out_dir: Path) -> Path:
    rows = [
        r
        for r in csv.DictReader((in_dir / "distributions.csv").open(encoding="utf-8"))
        if r["parameter"] == "discharge" and r["cohort"] == "historical_screen"
    ]
    order = ["05CC002", "05CB007", "05CB001", "05CC007"]
    by_st = {r["station"]: r for r in rows}

    w, h = 1020, 424
    left, right, top, bottom = 215, 700, 92, 310
    plot_w = right - left
    log_min, log_max = math.log10(0.05), math.log10(400.0)

    def x_pos(val: float) -> float:
        return left + (math.log10(val) - log_min) / (log_max - log_min) * plot_w

    lines = svg_header(
        w,
        h,
        "River Discharge Distributions (Historical Screen, Log Scale)",
        "Horizontal quantile plots on a logarithmic discharge axis (m³/s) for Red Deer (05CC002), "
        "Dickson Dam (05CB007), Little Red Deer (05CB001), and Medicine River (05CC007). "
        "All four stations are strongly right-skewed: Red Deer median is 22.3 m³/s versus mean 36.0 m³/s and max 284.0 m³/s.",
    )
    lines.append('  <text x="24" y="34" class="title">Figure 2. Skewed River Discharge Distributions (Historical Screen)</text>')
    lines.append(
        '  <text x="24" y="54" class="subtitle">'
        "Log10 scale in m³/s showing Min–Max whiskers, P10–P90 bar, P25–P75 IQR box, Median line, and Mean diamond. "
        "Mean exceeds median at every station due to rare high-flow tails."
        "</text>"
    )
    lines.append(f'  <rect x="{left}" y="{top}" width="{plot_w}" height="{bottom - top}" fill="{C_PANEL}" stroke="{C_GRID}" />')

    # Vertical grid lines on log scale
    for tick in [0.1, 0.5, 1, 5, 10, 50, 100, 300]:
        tx = x_pos(tick)
        lines.append(f'  <line x1="{tx:.1f}" y1="{top}" x2="{tx:.1f}" y2="{bottom}" stroke="{C_GRID}" stroke-width="1" />')
        lbl = f"{tick:g}"
        lines.append(f'  <text x="{tx:.1f}" y="{bottom + 18}" text-anchor="middle" class="tick">{lbl}</text>')
    lines.append(
        f'  <text x="{(left + right) / 2:.1f}" y="{bottom + 38}" text-anchor="middle" class="axis-title">'
        "Observed Discharge (m³/s, logarithmic scale)"
        "</text>"
    )

    # Summary table header on right
    lines.append(f'  <text x="{right + 20}" y="{top - 10}" class="small" style="font-weight:700;">Median</text>')
    lines.append(f'  <text x="{right + 82}" y="{top - 10}" class="small" style="font-weight:700;">Mean</text>')
    lines.append(f'  <text x="{right + 144}" y="{top - 10}" class="small" style="font-weight:700;">P90</text>')
    lines.append(f'  <text x="{right + 206}" y="{top - 10}" class="small" style="font-weight:700;">Max</text>')
    lines.append(f'  <text x="{right + 258}" y="{top - 10}" class="small" style="font-weight:700;">n</text>')

    row_step = (bottom - top) / len(order)
    for idx, st in enumerate(order):
        r = by_st[st]
        cy = top + (idx + 0.5) * row_step
        vmin = float(r["min"])
        p10 = float(r["p10"])
        p25 = float(r["p25"])
        med = float(r["median"])
        mean = float(r["mean"])
        p75 = float(r["p75"])
        p90 = float(r["p90"])
        vmax = float(r["max"])
        n = int(r["n"])

        lines.append(f'  <text x="{left - 12}" y="{cy + 4:.1f}" text-anchor="end" class="label">{esc(STATION_NAMES[st])}</text>')
        # Min-Max whisker
        lines.append(
            f'  <line x1="{x_pos(vmin):.1f}" y1="{cy:.1f}" x2="{x_pos(vmax):.1f}" y2="{cy:.1f}" '
            f'stroke="{C_MUTED}" stroke-width="1.5" />'
        )
        lines.append(f'  <line x1="{x_pos(vmin):.1f}" y1="{cy - 6:.1f}" x2="{x_pos(vmin):.1f}" y2="{cy + 6:.1f}" stroke="{C_MUTED}" stroke-width="1.5" />')
        lines.append(f'  <line x1="{x_pos(vmax):.1f}" y1="{cy - 6:.1f}" x2="{x_pos(vmax):.1f}" y2="{cy + 6:.1f}" stroke="{C_MUTED}" stroke-width="1.5" />')
        # P10-P90 band
        lines.append(
            f'  <rect x="{x_pos(p10):.1f}" y="{cy - 6:.1f}" width="{x_pos(p90) - x_pos(p10):.1f}" height="12" '
            f'fill="{C_SKY}" fill-opacity="0.45" rx="2" />'
        )
        # P25-P75 IQR box
        lines.append(
            f'  <rect x="{x_pos(p25):.1f}" y="{cy - 12:.1f}" width="{x_pos(p75) - x_pos(p25):.1f}" height="24" '
            f'fill="{C_BLUE}" fill-opacity="0.85" stroke="#0C4A6E" stroke-width="1" rx="2" />'
        )
        # Median white vertical line
        lines.append(
            f'  <line x1="{x_pos(med):.1f}" y1="{cy - 13:.1f}" x2="{x_pos(med):.1f}" y2="{cy + 13:.1f}" '
            f'stroke="#FFFFFF" stroke-width="2.5" />'
        )
        # Mean orange diamond
        mx = x_pos(mean)
        lines.append(
            f'  <polygon points="{mx:.1f},{cy - 7:.1f} {mx + 6:.1f},{cy:.1f} {mx:.1f},{cy + 7:.1f} {mx - 6:.1f},{cy:.1f}" '
            f'fill="{C_ORANGE}" stroke="#FFFFFF" stroke-width="1.2" />'
        )

        # Right-side exact numeric table
        def fmt(v: float) -> str:
            return f"{v:.3f}" if v < 1 else (f"{v:.2f}" if v < 10 else f"{v:.1f}")

        lines.append(f'  <text x="{right + 20}" y="{cy + 4:.1f}" class="tick">{fmt(med)}</text>')
        lines.append(f'  <text x="{right + 82}" y="{cy + 4:.1f}" class="tick">{fmt(mean)}</text>')
        lines.append(f'  <text x="{right + 144}" y="{cy + 4:.1f}" class="tick">{fmt(p90)}</text>')
        lines.append(f'  <text x="{right + 206}" y="{cy + 4:.1f}" class="tick">{fmt(vmax)}</text>')
        lines.append(f'  <text x="{right + 258}" y="{cy + 4:.1f}" class="small">{n:,}</text>')

    # Legend
    ly = 382
    lines.append(f'  <rect x="215" y="{ly - 8}" width="16" height="10" fill="{C_SKY}" fill-opacity="0.45" />')
    lines.append(f'  <text x="236" y="{ly}" class="small">P10–P90</text>')
    lines.append(f'  <rect x="305" y="{ly - 10}" width="16" height="14" fill="{C_BLUE}" fill-opacity="0.85" />')
    lines.append(f'  <text x="326" y="{ly}" class="small">IQR (P25–P75)</text>')
    lines.append(f'  <line x1="425" y1="{ly - 10}" x2="425" y2="{ly + 4}" stroke="{C_DARK}" stroke-width="2.5" />')
    lines.append(f'  <text x="433" y="{ly}" class="small">Median</text>')
    lines.append(
        f'  <polygon points="502,{ly - 9} 508,{ly - 3} 502,{ly + 3} 496,{ly - 3}" fill="{C_ORANGE}" />'
    )
    lines.append(f'  <text x="514" y="{ly}" class="small">Mean</text>')
    lines.append(f'  <line x1="565" y1="{ly - 3}" x2="585" y2="{ly - 3}" stroke="{C_MUTED}" stroke-width="1.5" />')
    lines.append(f'  <text x="592" y="{ly}" class="small">Min–Max (rare high-flow extrema; not independent flood count)</text>')

    lines.append(
        '  <text x="24" y="410" class="footer">'
        "Source: output/final_eda/distributions.csv (historical_screen). Sylvan Lake (05CC003) records lake level (m) only, not discharge, and is excluded here."
        "</text>"
    )
    lines.append("</svg>")
    out = out_dir / "fig2_discharge_distributions.svg"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def build_fig3_lagged_correlations(in_dir: Path, out_dir: Path) -> Path:
    rows = list(csv.DictReader((in_dir / "lagged_relationships.csv").open(encoding="utf-8")))
    lags = [0, 6, 12, 24, 30, 48]
    series_cfg = [
        ("05CB007", "Dickson Dam (05CB007, n=147,699)", C_BLUE, "", "circle", -4.0),
        ("05CB001", "Little Red Deer (05CB001, n=153,543)", C_ORANGE, "7,4", "square", 0.0),
        ("05CC007", "Medicine River (05CC007, n=150,025)", C_GREEN, "2,3", "triangle", 4.0),
    ]
    by_key = {(r["upstream_station"], int(r["lag_h"])): r for r in rows}

    w, h = 980, 460
    left, right, top, bottom = 84, 720, 88, 372
    plot_w, plot_h = right - left, bottom - top

    def x_pos(lag: int, dx: float = 0.0) -> float:
        return left + 36 + (lag / 48.0) * (plot_w - 72) + dx

    def y_pos(val: float) -> float:
        return bottom - ((val - 0.15) / (1.02 - 0.15)) * plot_h

    lines = svg_header(
        w,
        h,
        "Lagged Upstream-to-Red-Deer Discharge Correlation with 95% 7-Day Block Intervals",
        "Line plot with error bars showing Pearson r between upstream discharge Q(t-lag) and Red Deer 05CC002 Q(t) "
        "across lags 0, 6, 12, 24, 30, and 48 hours, with 95% seven-day UTC block bootstrap intervals. "
        "Dickson stays near 0.91–0.95 (flat peak at 12 h), Little Red Deer peaks near 0.726 at 30 h, and Medicine shows a wide interval (0.25–0.81) rising to the 48 h boundary.",
    )
    lines.append('  <text x="24" y="34" class="title">Figure 3. Lagged Upstream vs. Red Deer (05CC002) Discharge Correlation</text>')
    lines.append(
        '  <text x="24" y="54" class="subtitle">'
        "Pearson r across illustrative upstream lead times with 95% 7-day UTC block bootstrap intervals (1,000 resamples). "
        "Wide or flat curves show covariation, not validated flood transit time."
        "</text>"
    )
    lines.append(f'  <rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="{C_PANEL}" stroke="{C_GRID}" />')

    # Horizontal grid
    for yv in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        yy = y_pos(yv)
        lines.append(f'  <line x1="{left}" y1="{yy:.1f}" x2="{right}" y2="{yy:.1f}" stroke="{C_GRID}" stroke-width="1" />')
        lines.append(f'  <text x="{left - 10}" y="{yy + 4:.1f}" text-anchor="end" class="tick">{yv:.1f}</text>')

    # Vertical ticks for lags
    for lag in lags:
        xx = x_pos(lag)
        lines.append(f'  <line x1="{xx:.1f}" y1="{top}" x2="{xx:.1f}" y2="{bottom}" stroke="{C_GRID}" stroke-dasharray="3,3" />')
        lines.append(f'  <text x="{xx:.1f}" y="{bottom + 18}" text-anchor="middle" class="tick">{lag} h</text>')

    lines.append(
        f'  <text x="{(left + right) / 2:.1f}" y="{bottom + 40}" text-anchor="middle" class="axis-title">'
        "Upstream Lead Time (hours before Red Deer 05CC002 timestamp)"
        "</text>"
    )
    lines.append(
        f'  <text x="26" y="{(top + bottom) / 2:.1f}" text-anchor="middle" class="axis-title" '
        f'transform="rotate(-90 26 {(top + bottom) / 2:.1f})">Pearson Correlation r (with 95% 7-day block CI)</text>'
    )

    # Plot each station
    for st, lbl, col, dash, shape, dx in series_cfg:
        pts = []
        for lag in lags:
            r = by_key[(st, lag)]
            rv = float(r["pearson_r"])
            lo = float(r["block_ci_2_5"])
            hi = float(r["block_ci_97_5"])
            xx = x_pos(lag, dx)
            yy, ylo, yhi = y_pos(rv), y_pos(lo), y_pos(hi)
            pts.append((xx, yy, rv, lag))
            # Error bar
            lines.append(f'  <line x1="{xx:.1f}" y1="{ylo:.1f}" x2="{xx:.1f}" y2="{yhi:.1f}" stroke="{col}" stroke-width="1.6" stroke-opacity="0.7" />')
            lines.append(f'  <line x1="{xx - 4:.1f}" y1="{ylo:.1f}" x2="{xx + 4:.1f}" y2="{ylo:.1f}" stroke="{col}" stroke-width="1.4" stroke-opacity="0.7" />')
            lines.append(f'  <line x1="{xx - 4:.1f}" y1="{yhi:.1f}" x2="{xx + 4:.1f}" y2="{yhi:.1f}" stroke="{col}" stroke-width="1.4" stroke-opacity="0.7" />')

        path_d = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y, _, _) in enumerate(pts))
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        lines.append(f'  <path d="{path_d}" fill="none" stroke="{col}" stroke-width="2.4"{dash_attr} />')

        for xx, yy, rv, lag in pts:
            if shape == "circle":
                lines.append(f'  <circle cx="{xx:.1f}" cy="{yy:.1f}" r="4.5" fill="{col}" stroke="#FFFFFF" stroke-width="1.2" />')
            elif shape == "square":
                lines.append(f'  <rect x="{xx - 4:.1f}" y="{yy - 4:.1f}" width="8" height="8" fill="{col}" stroke="#FFFFFF" stroke-width="1.2" />')
            else:
                lines.append(
                    f'  <polygon points="{xx:.1f},{yy - 5.5:.1f} {xx + 5:.1f},{yy + 4.5:.1f} {xx - 5:.1f},{yy + 4.5:.1f}" '
                    f'fill="{col}" stroke="#FFFFFF" stroke-width="1.2" />'
                )

    # Direct peak annotations
    lines.append(f'  <text x="{x_pos(12, -4):.1f}" y="{y_pos(0.953) - 18:.1f}" text-anchor="middle" style="font-size:10px;font-weight:700;fill:{C_BLUE};">12 h max: 0.953 (only +0.012 vs 0 h)</text>')
    lines.append(f'  <text x="{x_pos(30):.1f}" y="{y_pos(0.726) - 42:.1f}" text-anchor="middle" style="font-size:10px;font-weight:700;fill:{C_ORANGE};">30 h max: 0.726</text>')
    lines.append(f'  <text x="{x_pos(48, 4) - 14:.1f}" y="{y_pos(0.614) + 18:.1f}" text-anchor="end" style="font-size:10px;font-weight:700;fill:{C_GREEN};">48 h boundary: 0.614 [0.253, 0.815]</text>')

    # Legend & takeaway box on right
    bx, by = 740, 96
    lines.append(f'  <rect x="{bx}" y="{by}" width="224" height="278" rx="6" fill="{C_PANEL}" stroke="{C_GRID}" />')
    lines.append(f'  <text x="{bx + 12}" y="{by + 24}" class="label">Upstream Stations</text>')
    ly = by + 48
    for st, lbl, col, dash, shape, _ in series_cfg:
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        lines.append(f'  <line x1="{bx + 12}" y1="{ly}" x2="{bx + 42}" y2="{ly}" stroke="{col}" stroke-width="2.4"{dash_attr} />')
        if shape == "circle":
            lines.append(f'  <circle cx="{bx + 27}" cy="{ly}" r="4" fill="{col}" />')
        elif shape == "square":
            lines.append(f'  <rect x="{bx + 23}" y="{ly - 4}" width="8" height="8" fill="{col}" />')
        else:
            lines.append(f'  <polygon points="{bx + 27},{ly - 5} {bx + 32},{ly + 4} {bx + 22},{ly + 4}" fill="{col}" />')
        short = lbl.split(" (")[0]
        sub = "(" + lbl.split(" (")[1]
        lines.append(f'  <text x="{bx + 50}" y="{ly - 1}" class="label" style="fill:{col};">{esc(short)}</text>')
        lines.append(f'  <text x="{bx + 50}" y="{ly + 12}" class="small">{esc(sub)}</text>')
        ly += 38

    lines.append(f'  <line x1="{bx + 12}" y1="{ly + 4}" x2="{bx + 208}" y2="{ly + 4}" stroke="{C_GRID}" />')
    lines.append(f'  <text x="{bx + 12}" y="{ly + 24}" class="label">Why timing is withheld:</text>')
    notes = [
        "• Shared seasonality & persistence",
        "  flatten lag curves.",
        "• Intervals overlap across lags.",
        "• Not a verified flood travel time",
        "  or operational warning lead.",
    ]
    ny = ly + 42
    for note in notes:
        lines.append(f'  <text x="{bx + 12}" y="{ny}" class="small">{esc(note)}</text>')
        ny += 15

    lines.append(
        '  <text x="24" y="444" class="footer">'
        "Source: output/final_eda/lagged_relationships.csv (78–79 seven-day UTC blocks; common target support within each upstream station; separate descriptive intervals)."
        "</text>"
    )
    lines.append("</svg>")
    out = out_dir / "fig3_lagged_correlations.svg"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def build_fig4_sensitivity_rules(in_dir: Path, out_dir: Path) -> Path:
    summary = json.loads((in_dir / "summary.json").read_text(encoding="utf-8"))
    blocks = list(csv.DictReader((in_dir / "time_blocks.csv").open(encoding="utf-8")))

    w, h = 1080, 520
    lines = svg_header(
        w,
        h,
        "Formal Sensitivity Analyses P-S1 (Strict Final Approval) and P-S2 (Sylvan Lake Missingness)",
        "Two-panel figure. Panel A compares cohort sizes: river-only all dates (144,289 rows, 541 days), "
        "river-only on shared lake dates (95,718 rows, 361 days), lake-complete (95,053 rows, 361 days), "
        "and strict all-Final P-S1 (0 rows). Panel B plots weekly 7-day mean Red Deer discharge across 79 blocks, "
        "highlighting the 6-month winter lake gap where 48,571 river-only timestamps would be dropped.",
    )
    lines.append('  <text x="24" y="34" class="title">Figure 4. Sensitivity Analyses: Approval Rule (P-S1) and Lake Missingness (P-S2)</text>')
    lines.append(
        '  <text x="24" y="54" class="subtitle">'
        "How data-inclusion rules alter sample coverage versus same-date Red Deer (05CC002) discharge summaries."
        "</text>"
    )

    # Panel A: Sample counts bar chart
    p1_x, p1_y, p1_w, p1_h = 24, 74, 1032, 166
    lines.append(f'  <rect x="{p1_x}" y="{p1_y}" width="{p1_w}" height="{p1_h}" rx="6" fill="{C_PANEL}" stroke="{C_GRID}" />')
    lines.append(f'  <text x="{p1_x + 14}" y="{p1_y + 22}" class="axis-title">Panel A. Cohort Denominators Under Changed Inclusion Rules (Exact 5-Minute UTC Timestamps)</text>')

    bars = [
        ("River-only, all dates (main cohort)", summary["cohort_timestamps"]["river_only_all_dates"], "541 UTC days", C_BLUE),
        ("River-only, shared lake dates (P-S2 ref)", summary["cohort_timestamps"]["river_only_shared_dates"], "361 UTC days · mean 39.704 m³/s", C_SKY),
        ("Lake-complete, 5 stations (P-S2 alt)", summary["cohort_timestamps"]["lake_complete"], "361 UTC days · mean 39.827 m³/s (+0.123)", C_GREEN),
        ("Strict All-Final, 9 values (P-S1 alt)", summary["cohort_timestamps"]["all_final_lake_complete"], "0 UTC days · 05CB001 & 05CC007 have 0 Final rows", C_ORANGE),
    ]
    bar_left = 295
    bar_max_w = 470
    max_n = 150000.0
    for i, (lbl, n, note, col) in enumerate(bars):
        by = p1_y + 38 + i * 30
        bw = max(3.0 if n == 0 else (n / max_n) * bar_max_w, 3.0)
        lines.append(f'  <text x="{bar_left - 10}" y="{by + 14}" text-anchor="end" class="label">{esc(lbl)}</text>')
        lines.append(f'  <rect x="{bar_left}" y="{by + 2}" width="{bw:.1f}" height="18" rx="3" fill="{col}" />')
        lines.append(
            f'  <text x="{bar_left + bw + 8:.1f}" y="{by + 15}" class="small" style="font-weight:600;fill:{C_DARK};">'
            f"{n:,}  ({esc(note)})</text>"
        )

    # Panel B: Weekly endpoint discharge timeline with winter lake gap shaded
    p2_x, p2_y, p2_w, p2_h = 24, 256, 1032, 224
    lines.append(f'  <rect x="{p2_x}" y="{p2_y}" width="{p2_w}" height="{p2_h}" rx="6" fill="{C_PANEL}" stroke="{C_GRID}" />')
    lines.append(
        f'  <text x="{p2_x + 14}" y="{p2_y + 22}" class="axis-title">'
        "Panel B. Weekly 7-Day Mean Red Deer Discharge Across All 79 UTC Blocks — Shaded Band Shows Winter Sylvan Lake Gap"
        "</text>"
    )

    gx_l, gx_r, gy_t, gy_b = 84, 1036, 294, 440
    gw, gh = gx_r - gx_l, gy_b - gy_t
    y_max = 170.0
    n_blk = len(blocks)

    def bx(i: int) -> float:
        return gx_l + (i + 0.5) / n_blk * gw

    def by_q(q: float) -> float:
        return gy_b - (q / y_max) * gh

    # Identify contiguous blocks with lake_complete_n == 0
    zero_indices = [i for i, b in enumerate(blocks) if int(b["lake_complete_n"]) == 0]
    if zero_indices:
        z0, z1 = min(zero_indices), max(zero_indices)
        sx0 = gx_l + (z0 / n_blk) * gw
        sx1 = gx_l + ((z1 + 1) / n_blk) * gw
        lines.append(
            f'  <rect x="{sx0:.1f}" y="{gy_t}" width="{sx1 - sx0:.1f}" height="{gh}" '
            f'fill="{C_ORANGE}" fill-opacity="0.14" stroke="{C_ORANGE}" stroke-dasharray="4,3" stroke-width="1.2" />'
        )
        lines.append(
            f'  <text x="{(sx0 + sx1) / 2:.1f}" y="{gy_t + 18}" text-anchor="middle" '
            f'style="font-size:11px;font-weight:700;fill:{C_ORANGE};">Sylvan Lake absent (Nov 2025 – Apr 2026)</text>'
        )
        lines.append(
            f'  <text x="{(sx0 + sx1) / 2:.1f}" y="{gy_t + 33}" text-anchor="middle" '
            f'style="font-size:10px;fill:#9A3412;">48,571 river-only timestamps excluded by 5-station join</text>'
        )

    # Y grid
    for qv in [0, 40, 80, 120, 160]:
        yy = by_q(qv)
        lines.append(f'  <line x1="{gx_l}" y1="{yy:.1f}" x2="{gx_r}" y2="{yy:.1f}" stroke="{C_GRID}" />')
        lines.append(f'  <text x="{gx_l - 8}" y="{yy + 4:.1f}" text-anchor="end" class="tick">{qv}</text>')
    lines.append(
        f'  <text x="40" y="{(gy_t + gy_b) / 2:.1f}" text-anchor="middle" class="small" style="font-weight:600;" '
        f'transform="rotate(-90 40 {(gy_t + gy_b) / 2:.1f})">7-day Mean Q (m³/s)</text>'
    )

    # River-only line + lake-complete markers
    river_pts = []
    for i, b in enumerate(blocks):
        q = float(b["river_only_all_dates_endpoint_q_mean_m3_s"])
        river_pts.append((bx(i), by_q(q)))
    path_r = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(river_pts))
    lines.append(f'  <path d="{path_r}" fill="none" stroke="{C_BLUE}" stroke-width="2.2" />')

    for i, b in enumerate(blocks):
        if int(b["lake_complete_n"]) > 0:
            q_l = float(b["lake_complete_endpoint_q_mean_m3_s"])
            lines.append(f'  <circle cx="{bx(i):.1f}" cy="{by_q(q_l):.1f}" r="2.6" fill="{C_GREEN}" />')

    # X axis labels every ~10 blocks
    for i in range(0, n_blk, 10):
        lbl = blocks[i]["block_start_utc"][:7]
        lines.append(f'  <text x="{bx(i):.1f}" y="{gy_b + 16}" text-anchor="middle" class="tick">{esc(lbl)}</text>')

    # Callout box for P-S2 paired block CI (placed in open space above Jul–Oct 2025)
    cx, cy = 205, 298
    lines.append(f'  <rect x="{cx}" y="{cy}" width="224" height="58" rx="4" fill="#FFFFFF" stroke="{C_GREEN}" stroke-width="1.3" />')
    lines.append(f'  <text x="{cx + 8}" y="{cy + 16}" class="small" style="font-weight:700;fill:{C_GREEN};">P-S2 Shared-Date Check (361 d):</text>')
    lines.append(f'  <text x="{cx + 8}" y="{cy + 32}" class="small">Mean diff: +0.123 m³/s (99.3% kept)</text>')
    lines.append(f'  <text x="{cx + 8}" y="{cy + 47}" class="small">95% paired block CI: [−0.002, +0.315]</text>')

    # Panel B legend
    lines.append(f'  <line x1="84" y1="468" x2="110" y2="468" stroke="{C_BLUE}" stroke-width="2.4" />')
    lines.append('  <text x="116" y="472" class="small">River-only weekly mean Q (all 79 blocks)</text>')
    lines.append(f'  <circle cx="350" cy="468" r="3.5" fill="{C_GREEN}" />')
    lines.append('  <text x="360" y="472" class="small">Blocks with Sylvan Lake data present (55 blocks)</text>')

    lines.append(
        '  <text x="24" y="505" class="footer">'
        "Source: summary.json, sensitivity-results.csv &amp; time_blocks.csv. "
        "Decision: keep 4 river stations for main coverage; label lake summaries conditional."
        "</text>"
    )
    lines.append("</svg>")
    out = out_dir / "fig4_sensitivity_rules.svg"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate standard-library SVG figures for AIDA 2156 formal EDA.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    in_dir = args.input_dir.resolve()
    out_dir = (args.output_dir or (in_dir / "figures")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    outputs = [
        build_fig1_monthly_coverage(in_dir, out_dir),
        build_fig2_discharge_distributions(in_dir, out_dir),
        build_fig3_lagged_correlations(in_dir, out_dir),
        build_fig4_sensitivity_rules(in_dir, out_dir),
    ]
    for path in outputs:
        print(f"Wrote {path.name} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
