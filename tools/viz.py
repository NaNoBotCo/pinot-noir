#!/usr/bin/env python3
"""viz.py — the maps, the diagrams and the arithmetic.

Everything here is computed from the corpus at build time. Nothing is decorative: each
picture is the shortest way to say a thing the words would take a paragraph to say.

  locator_svg      one cellar or vineyard, its neighbours, and the coastline behind them
  timeline_svg     when something happened, one stem per event
  bars_svg         horizontal bars, one hue, value at the end
  open_days        a published opening-hours string, read into seven days
  day_strip        those seven days as boxes — filled open, hollow closed, DASHED unknown
  kin_matrix_svg   which kinds of page point at which

Colour: one hue, with position or lightness carrying the magnitude. The sequential ramp
below runs one wine hue from pale to dark with monotone lightness, which is what a
continuous scale needs; every use of it ships a numbered legend or a table twin.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import worldmap

RAMP = ["#f3e3e7", "#e0bfc8", "#cd99a8", "#b47287", "#954e66", "#722f48", "#4a172c"]
WINE = "#7b2038"
E = __import__("html").escape


def hexrgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def locator_svg(lat, lon, others: list, w=760, span_km=90.0, label=""):
    """One place at the centre, its neighbours around it, and enough furniture to read the
    picture: a coastline where this project has one, a degree grid where it does not, and
    a scale bar always. A map of a wine region with no scale is a decoration."""
    fit = worldmap.fit_box(lat, lon, span_km, w, aspect=2.1)
    h = fit["h"]
    b = fit["box"]
    out = [f'<svg viewBox="0 0 {w} {h:.0f}" role="img" aria-label="Map of the country around {E(label or "this place")}">',
           f'<rect width="{w}" height="{h:.0f}" fill="var(--chip)" rx="10"/>']
    # a degree grid, stepped so a small window gets tenths and a large one gets whole degrees
    step = 0.1 if span_km <= 60 else (0.25 if span_km <= 160 else 1.0)
    g0 = math.floor(b[0] / step) * step
    while g0 <= b[2]:
        x, _ = worldmap.project_box(g0, lat, fit)
        out.append(f'<line x1="{x:.1f}" y1="0" x2="{x:.1f}" y2="{h:.0f}" stroke="var(--line)" stroke-width=".8" opacity=".8"/>')
        g0 += step
    g1 = math.floor(b[1] / step) * step
    while g1 <= b[3]:
        _, y0 = worldmap.project_box(lon, g1, fit)
        out.append(f'<line x1="0" y1="{y0:.1f}" x2="{w}" y2="{y0:.1f}" stroke="var(--line)" stroke-width=".8" opacity=".8"/>'
                   f'<text x="6" y="{y0 - 4:.1f}" fill="var(--mute)" style="font:600 10px var(--ui,sans-serif)">'
                   f'{abs(g1):.2f}°{"N" if g1 >= 0 else "S"}</text>')
        g1 += step
    for d in worldmap.clip_lines(worldmap.load_coast().get("lines", []), fit):
        out.append(f'<path d="{d}" fill="none" stroke="var(--mute)" stroke-width="1.8" opacity=".85"/>')
    near = []
    for o in others:
        if o.get("lat") is None:
            continue
        if not (b[0] <= o["lon"] <= b[2] and b[1] <= o["lat"] <= b[3]):
            continue
        x, y = worldmap.project_box(o["lon"], o["lat"], fit)
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.6" fill="var(--mute)" opacity=".85">'
                   f'<title>{E(o["name"])}</title></circle>')
        near.append((x, y, o["name"]))
    cx, cy = worldmap.project_box(lon, lat, fit)
    # name the neighbours, skipping any whose word would land on another
    placed = [(cx, cy)]
    for nx, ny, nm in sorted(near, key=lambda t: abs(t[0] - cx) + abs(t[1] - cy)):
        if any(abs(nx - px) < 88 and abs(ny - py) < 16 for px, py in placed):
            continue
        placed.append((nx, ny))
        out.append(f'<text x="{nx:.1f}" y="{ny - 8:.1f}" text-anchor="middle" fill="var(--mute)" '
                   f'style="font:600 10.5px var(--ui,sans-serif);paint-order:stroke;stroke:var(--chip);stroke-width:3px">{E(nm)}</text>')
    out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="16" fill="var(--wine)" opacity=".2"/>'
               f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="7" fill="var(--wine)" stroke="var(--panel)" stroke-width="2.5"/>'
               f'<text x="{cx:.1f}" y="{cy - 17:.1f}" text-anchor="middle" fill="var(--ink)" '
               f'style="font:700 13.5px var(--display,serif);paint-order:stroke;stroke:var(--chip);stroke-width:3.5px">{E(label)}</text>')
    bar = w * 0.22
    out.append(f'<line x1="16" y1="{h-16:.0f}" x2="{16+bar:.0f}" y2="{h-16:.0f}" stroke="var(--ink)" stroke-width="2.4"/>'
               f'<line x1="16" y1="{h-20:.0f}" x2="16" y2="{h-12:.0f}" stroke="var(--ink)" stroke-width="2.4"/>'
               f'<line x1="{16+bar:.0f}" y1="{h-20:.0f}" x2="{16+bar:.0f}" y2="{h-12:.0f}" stroke="var(--ink)" stroke-width="2.4"/>'
               f'<text x="16" y="{h-22:.0f}" style="font:600 11px var(--ui,sans-serif)" fill="var(--mute)">'
               f'{span_km*0.22:.0f} km</text>')
    out.append("</svg>")
    return "".join(out)


# ------------------------------------------------------------------ charts

def timeline_svg(rows: list, w=760):
    """One stem per pit, by the year it opened. Rows stack where years collide."""
    if not rows:
        return ""
    years = [y for y, _ in rows]
    lo, hi = min(years) // 10 * 10, (max(years) // 10 + 1) * 10
    h, base = 300, 232
    px = lambda y: 52 + (y - lo) / (hi - lo) * (w - 96)
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="When the pits opened, {lo} to {hi}">']
    for t in range(lo, hi + 1, 10):
        out.append(f'<line x1="{px(t):.1f}" y1="34" x2="{px(t):.1f}" y2="{base}" stroke="var(--line)" stroke-width="1"/>'
                   f'<text x="{px(t):.1f}" y="{base + 22}" text-anchor="middle" fill="var(--mute)" '
                   f'style="font:600 12px -apple-system,sans-serif">{t}</text>')
    seen: dict = {}
    for y, name in sorted(rows):
        k = round(px(y) / 9)
        lvl = seen.get(k, 0)
        seen[k] = lvl + 1
        yy = base - 14 - lvl * 15
        out.append(f'<line x1="{px(y):.1f}" y1="{base}" x2="{px(y):.1f}" y2="{yy:.1f}" stroke="var(--sauce)" stroke-width="2" opacity=".55"/>'
                   f'<circle cx="{px(y):.1f}" cy="{yy:.1f}" r="5" fill="var(--sauce)"><title>{E(name)} — {y}</title></circle>')
    out.append(f'<line x1="40" y1="{base}" x2="{w - 30}" y2="{base}" stroke="var(--ink)" stroke-width="2"/>')
    out.append("</svg>")
    return "".join(out)


def bars_svg(rows: list, w=760, unit="", rowh=30, left=190):
    """Horizontal bars, one hue, value at the end of each. The plainest honest form."""
    if not rows:
        return ""
    top = max(v for _, v in rows)
    h = len(rows) * rowh + 16
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{E(unit or "counts")}">']
    for i, (label, v) in enumerate(rows):
        y = 8 + i * rowh
        bw = (w - left - 74) * v / top
        out.append(f'<text x="{left - 12}" y="{y + rowh * 0.62:.0f}" text-anchor="end" fill="var(--ink)" '
                   f'style="font:600 14px -apple-system,sans-serif">{E(label)}</text>'
                   f'<rect x="{left}" y="{y + 4}" width="{max(bw, 2):.1f}" height="{rowh - 12}" rx="4" fill="var(--sauce)"/>'
                   f'<text x="{left + bw + 10:.1f}" y="{y + rowh * 0.62:.0f}" fill="var(--mute)" '
                   f'style="font:600 13px -apple-system,sans-serif">{v}</text>')
    out.append("</svg>")
    return "".join(out)


DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
DAY_NAME = {"Mo": "Monday", "Tu": "Tuesday", "We": "Wednesday", "Th": "Thursday", "Fr": "Friday", "Sa": "Saturday", "Su": "Sunday"}


def open_days(hours_strings: list) -> dict:
    """Expand OpenStreetMap opening_hours into a count per weekday. Ranges like Mo-Sa are
    expanded; a day named with 'off' is removed again."""
    count = {d: 0 for d in DAYS}
    for s in hours_strings:
        days = set()
        for part in s.split(";"):
            part = part.strip()
            spec = re.findall(r"\b(Mo|Tu|We|Th|Fr|Sa|Su)\b(?:\s*-\s*(Mo|Tu|We|Th|Fr|Sa|Su))?", part)
            got = set()
            for a, b in spec:
                if b:
                    i, j = DAYS.index(a), DAYS.index(b)
                    got |= set(DAYS[i:j + 1] if i <= j else DAYS[i:] + DAYS[:j + 1])
                else:
                    got.add(a)
            if "off" in part.lower() or "closed" in part.lower():
                days -= got
            elif got:
                days |= got
            elif re.search(r"24/7", part):
                days |= set(DAYS)
        for d in days:
            count[d] += 1
    return count


def kin_matrix_svg(edges: list, types: list, labels: dict, w=700):
    """Which kind of page points at which. A square of cells, one hue, darker where more
    links run — the shape of the site's own argument."""
    n = len(types)
    cell = (w - 150) / n
    h = int(cell * n + 150)
    m: dict = {}
    for e in edges:
        m[(e["from_type"], e["to_type"])] = m.get((e["from_type"], e["to_type"]), 0) + 1
    top = max(m.values()) if m else 1
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="A matrix of which kinds of page link to which">']
    for i, a in enumerate(types):
        y = 96 + i * cell
        out.append(f'<text x="{140 - 10}" y="{y + cell * 0.62:.0f}" text-anchor="end" fill="var(--ink)" '
                   f'style="font:600 13px -apple-system,sans-serif">{E(labels.get(a, a))}</text>')
        for j, b in enumerate(types):
            x = 140 + j * cell
            v = m.get((a, b), 0)
            t = (v / top) ** 0.55
            col = RAMP[min(len(RAMP) - 1, int(t * (len(RAMP) - 1) + 0.0001))] if v else "var(--chip)"
            out.append(f'<rect x="{x + 1.5:.1f}" y="{y + 1.5:.1f}" width="{cell - 3:.1f}" height="{cell - 3:.1f}" rx="3" '
                       f'fill="{col}"><title>{E(labels.get(a, a))} → {E(labels.get(b, b))}: {v}</title></rect>')
            if v and t > 0.45:
                out.append(f'<text x="{x + cell / 2:.1f}" y="{y + cell * 0.62:.0f}" text-anchor="middle" fill="#fff" '
                           f'style="font:600 12px -apple-system,sans-serif">{v}</text>')
    for j, b in enumerate(types):
        x = 140 + j * cell + cell / 2
        out.append(f'<text transform="translate({x:.1f},88) rotate(-52)" fill="var(--ink)" '
                   f'style="font:600 13px -apple-system,sans-serif">{E(labels.get(b, b))}</text>')
    out.append(f'<text x="140" y="{h - 16}" fill="var(--mute)" style="font:400 12.5px -apple-system,sans-serif">'
               f'row points at column · darkest cell = {top} links</text>')
    out.append("</svg>")
    return "".join(out)


def ramp_legend(cuts: list, ramp: list, unit: str) -> str:
    """A numbered key. The ramp's pale end recedes into the page, so the numbers do the work."""
    n = len(ramp)
    cells = []
    for i, c in enumerate(ramp):
        lab = ("under " + str(cuts[0])) if i == 0 else (f"{cuts[i-1]}–{cuts[i]}" if i < len(cuts) else f"over {cuts[-1]}")
        cells.append(f'<span style="display:inline-flex;flex-direction:column;align-items:center;gap:.2rem">'
                     f'<i style="width:3.1rem;height:.85rem;background:{c};border-radius:2px;display:block"></i>'
                     f'<small style="font-size:.72rem;color:var(--mute)">{E(lab)}</small></span>')
    return (f'<div style="display:flex;gap:.35rem;flex-wrap:wrap;align-items:flex-end;margin:.6rem 0 .2rem">'
            + "".join(cells) + f'<span style="font-size:.8rem;color:var(--mute);margin-left:.5rem">{E(unit)}</span></div>')


# ------------------------------------------------------------------ the week

DAY_ORDER = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")
DAY_ONE = {"Mo": "M", "Tu": "T", "We": "W", "Th": "T", "Fr": "F", "Sa": "S", "Su": "S"}


def day_strip(days: dict, w=176, h=26, title=True) -> str:
    """Seven boxes, Monday to Sunday. Filled means open, hollow means closed, and a dashed
    outline means nobody has told us — which is not the same thing and never drawn as if
    it were. Sunday is drawn apart because Sunday is the question people ask."""
    if not days:
        return ""
    cell = (w - 10) / 7
    out = [f'<svg class="daystrip" viewBox="0 0 {w} {h}" role="img" aria-label="'
           + E(", ".join(f"{DAY_NAME[d]} {days.get(d, 'unknown')}" for d in DAY_ORDER)) + '">']
    for i, d in enumerate(DAY_ORDER):
        st = days.get(d, "unknown")
        x = i * cell + (10 if d == "Su" else 0)
        fill = {"open": "var(--sauce)", "closed": "none", "unknown": "none"}[st]
        stroke = {"open": "var(--sauce)", "closed": "var(--mute)", "unknown": "var(--line)"}[st]
        dash = ' stroke-dasharray="2.5 2.5"' if st == "unknown" else ""
        col = {"open": "#fff", "closed": "var(--mute)", "unknown": "var(--line)"}[st]
        out.append(f'<rect x="{x + 1.5:.1f}" y="3" width="{cell - 3:.1f}" height="{h - 8}" rx="4" fill="{fill}" '
                   f'stroke="{stroke}" stroke-width="1.6"{dash}/>'
                   f'<text x="{x + cell / 2:.1f}" y="{h / 2 + 4.5:.0f}" text-anchor="middle" fill="{col}" '
                   f'style="font:700 11px -apple-system,sans-serif">{DAY_ONE[d]}</text>')
        if title:
            out.append(f'<title>{E(DAY_NAME[d])}: {E(st)}</title>')
    out.append("</svg>")
    return "".join(out)


def day_key() -> str:
    return ('<span class="daykey"><i class="on"></i> open <i class="off"></i> closed '
            '<i class="unk"></i> not published</span>')


DAY_CSS = """
.daystrip{height:26px;width:176px;display:block}
.daykey{font-size:.76rem;color:var(--mute);display:inline-flex;align-items:center;gap:.3rem;font-family:var(--ui,sans-serif)}
.daykey i{width:.7rem;height:.9rem;border-radius:3px;display:inline-block;margin-left:.5rem}
.daykey i.on{background:var(--sauce);border:1.6px solid var(--sauce)}
.daykey i.off{border:1.6px solid var(--mute)}
.daykey i.unk{border:1.6px dashed var(--line)}
.sunday-yes{color:var(--sauce);font-weight:700}
.sunday-no{color:var(--mute)}
"""
