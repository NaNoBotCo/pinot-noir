"""worldmap.py — one projection for the world map, one for a close-up of a wine region.

Pinot noir grows between about 34°N and 46°S, which rules out any map centred on one
country. The world map here is drawn in **Equal Earth** (Šavrič, Patterson and Jenny,
2018): an equal-area pseudocylindrical projection, so a hectare in Otago is drawn the
same size as a hectare in Baden, and the continents still look like themselves.

A regional map is a different job — a few tens of kilometres, where the curve of the
earth does not matter but the aspect ratio does. Those use a plate carrée box with the
longitude scaled by cos(latitude), so the Sta. Rita Hills are not stretched sideways.

    fit = fit_world(width=900)
    x, y = project(lon, lat, fit)
"""
from __future__ import annotations

import math
from pathlib import Path

from common import GEO, jload

# Equal Earth coefficients, from the paper
A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796
SQRT3_2 = math.sqrt(3) / 2


def _equal_earth(lon: float, lat: float, lon0: float = 0.0) -> tuple[float, float]:
    lam = math.radians(_wrap(lon - lon0))
    phi = math.radians(lat)
    theta = math.asin(SQRT3_2 * math.sin(phi))
    t2 = theta * theta
    t6 = t2 * t2 * t2
    x = lam * math.cos(theta) / (SQRT3_2 * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2)))
    y = theta * (A1 + A2 * t2 + t6 * (A3 + A4 * t2))
    return x, -y                      # SVG counts down


def _wrap(lon: float) -> float:
    while lon > 180:
        lon -= 360
    while lon < -180:
        lon += 360
    return lon


def load_world() -> dict:
    return jload(GEO / "world.json")


def load_subdiv() -> dict:
    p = GEO / "subdiv.json"
    return jload(p) if p.exists() else {"states": []}


def load_coast() -> dict:
    p = GEO / "coast.json"
    return jload(p) if p.exists() else {"lines": []}


def fit_world(width: float = 900.0, pad: float = 6.0, lon0: float = 0.0, lat_max: float = 78.0) -> dict:
    """Scale and offset for a whole-world map, cut off above lat_max — nothing in this
    subject grows in the Arctic and the empty ice wastes a third of the page."""
    xs, ys = [], []
    for lat in (-lat_max, 0, lat_max):
        for lon in (-180, 0, 180):
            x, y = _equal_earth(lon, lat, lon0)
            xs.append(x)
            ys.append(y)
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    k = (width - 2 * pad) / (x1 - x0)
    return {"k": k, "x0": x0, "y0": y0, "pad": pad, "w": width,
            "h": (y1 - y0) * k + 2 * pad, "lon0": lon0, "lat_max": lat_max}


def project(lon: float, lat: float, fit: dict) -> tuple[float, float]:
    x, y = _equal_earth(lon, lat, fit["lon0"])
    return fit["pad"] + (x - fit["x0"]) * fit["k"], fit["pad"] + (y - fit["y0"]) * fit["k"]


def ring_path(ring: list, fit: dict) -> str:
    pts = [project(lon, lat, fit) for lon, lat in ring]
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"


def country_paths(world: dict, fit: dict):
    """(name, svg path) for every country, clipped crudely to the latitude cut."""
    for c in world["countries"]:
        ds = []
        for ring in c["rings"]:
            if max(lat for _, lat in ring) < -fit["lat_max"] or min(lat for _, lat in ring) > fit["lat_max"]:
                continue
            ds.append(ring_path([(lon, max(-fit["lat_max"], min(fit["lat_max"], lat))) for lon, lat in ring], fit))
        if ds:
            yield c.get("name", ""), " ".join(ds)


def graticule(fit: dict, step: int = 30):
    """Meridians and parallels, and the two latitudes this subject actually lives between."""
    out = []
    for lon in range(-180, 181, step):
        pts = [project(lon, lat, fit) for lat in range(-int(fit["lat_max"]), int(fit["lat_max"]) + 1, 5)]
        out.append("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts))
    for lat in range(-60, 61, step):
        pts = [project(lon, lat, fit) for lon in range(-180, 181, 5)]
        out.append("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts))
    return out


def band_path(fit: dict, lat: float) -> str:
    pts = [project(lon, lat, fit) for lon in range(-180, 181, 5)]
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)


# ------------------------------------------------------------------ close up

def fit_box(lat: float, lon: float, span_km: float = 90.0, width: float = 520.0, aspect: float = 1.6) -> dict:
    """A plate carrée window around a point, `span_km` wide, corrected for the latitude so
    the picture is not stretched sideways. `aspect` is width over height; a map that fills
    a page reads better as a letterbox than as a square."""
    half_w_km = span_km / 2
    half_h_km = half_w_km / aspect
    dlat = half_h_km / 111.0
    dlon = half_w_km / (111.0 * max(0.2, math.cos(math.radians(lat))))
    box = (lon - dlon, lat - dlat, lon + dlon, lat + dlat)
    return {"box": box, "w": width, "h": width / aspect, "span_km": span_km}


def project_box(lon: float, lat: float, fit: dict) -> tuple[float, float]:
    b = fit["box"]
    return ((lon - b[0]) / (b[2] - b[0]) * fit["w"], (b[3] - lat) / (b[3] - b[1]) * fit["h"])


def clip_lines(lines: list, fit: dict) -> list:
    """Polylines that touch the window, as SVG paths in its pixels."""
    b = fit["box"]
    out = []
    for line in lines:
        run = []
        for lon, lat in line:
            if b[0] - 0.4 <= lon <= b[2] + 0.4 and b[1] - 0.4 <= lat <= b[3] + 0.4:
                run.append(project_box(lon, lat, fit))
            else:
                # a coastline that leaves the window and comes back is two strokes, not one
                if len(run) > 1:
                    out.append("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in run))
                run = []
        if len(run) > 1:
            out.append("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in run))
    return out
