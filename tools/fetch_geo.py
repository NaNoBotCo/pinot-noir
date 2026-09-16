"""fetch_geo.py — the outlines every map on this site is drawn from.

Natural Earth, public domain. Three files, fetched once into data/geo/ and refreshed
only when they need refreshing:

  world.json   ne_110m_admin_0_countries — the world map on /map/
  subdiv.json  ne_50m_admin_1_states_provinces — states, départements, regions, for the
               countries pinot noir is grown in; also what state_by_geo() reads
  coast.json   ne_10m_coastline, clipped to the wine regions in REGION_BOXES — a
               locator map of the Sta. Rita Hills wants a coastline drawn at 10m, not
               at 110m, and the whole world at 10m is 10 MB nobody needs

    python3 tools/fetch_geo.py            # all three
    python3 tools/fetch_geo.py world      # one
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import GEO, jdump  # noqa: E402

BASE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
CREDIT = "Natural Earth (public domain)"
SITE = "https://www.naturalearthdata.com/"

# the countries whose subdivisions this project draws
SUBDIV_COUNTRIES = {"US", "FR", "DE", "NZ", "AU", "CL", "AR", "ZA", "CA", "IT", "CH", "AT", "ES", "GB", "PT", "RO", "MD", "HU", "CZ", "SI", "HR"}

# lon0, lat0, lon1, lat1 — every box a locator map may be drawn inside, padded
REGION_BOXES = [
    (-124.5, 44.0, -122.0, 46.2),    # Willamette Valley
    (-124.5, 38.0, -121.6, 39.6),    # Sonoma, Mendocino, Anderson Valley
    (-123.2, 36.2, -120.4, 37.6),    # Santa Cruz Mountains, Santa Lucia Highlands
    (-121.2, 34.2, -119.2, 35.3),    # Santa Barbara County
    (-123.3, 37.8, -121.9, 38.6),    # Carneros, Napa, San Pablo Bay
    (-78.0, 42.3, -76.0, 43.1),      # Finger Lakes
    (3.6, 46.3, 5.6, 48.0),          # Burgundy, Côte d'Or to the Mâconnais
    (3.3, 48.6, 4.9, 49.6),          # Champagne
    (6.9, 47.8, 8.4, 49.2),          # Alsace
    (6.6, 48.9, 8.3, 50.0),          # Ahr, Pfalz, Baden north
    (7.3, 47.5, 9.0, 49.3),          # Baden
    (168.0, -45.6, 170.0, -44.4),    # Central Otago
    (174.6, -41.6, 176.0, -40.7),    # Wairarapa, Martinborough
    (173.0, -41.8, 174.3, -41.2),    # Marlborough
    (144.5, -38.6, 145.7, -37.8),    # Mornington Peninsula
    (145.0, -38.0, 145.9, -37.3),    # Yarra Valley
    (146.4, -43.5, 148.4, -40.6),    # Tasmania
    (-72.0, -34.0, -70.8, -32.7),    # Casablanca, San Antonio
    (-71.9, -41.5, -66.8, -37.5),    # Patagonia, Río Negro, Neuquén
    (18.9, -34.7, 20.0, -34.0),      # Hemel-en-Aarde, Walker Bay
    (-120.2, 49.0, -119.2, 50.4),    # Okanagan
    (-80.5, 42.7, -78.8, 44.3),      # Niagara, Prince Edward County
    (11.0, 46.2, 11.8, 46.9),        # Alto Adige
]

TOL_WORLD = 0.08
TOL_SUB = 0.02
TOL_COAST = 0.004
MIN_RING = 0.03


def _perp(p, a, b) -> float:
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return ((x - (x1 + t * dx)) ** 2 + (y - (y1 + t * dy)) ** 2) ** 0.5


def simplify(pts: list, tol: float) -> list:
    """Douglas-Peucker, iterative so a long coastline does not blow the stack."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        far, d = -1, tol
        for k in range(i + 1, j):
            dk = _perp(pts[k], pts[i], pts[j])
            if dk > d:
                far, d = k, dk
        if far > 0:
            keep[far] = True
            stack.append((i, far))
            stack.append((far, j))
    return [p for p, k in zip(pts, keep) if k]


def rings_of(geom: dict) -> list:
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    if geom["type"] == "MultiPolygon":
        return [poly[0] for poly in geom["coordinates"]]
    if geom["type"] == "LineString":
        return [geom["coordinates"]]
    if geom["type"] == "MultiLineString":
        return list(geom["coordinates"])
    return []


def fetch(name: str) -> dict:
    url = BASE + name
    print(f"fetching {url}")
    with urllib.request.urlopen(url, timeout=300) as r:
        return json.loads(r.read().decode("utf-8"))


def thin(ring, tol, dp=3):
    s = simplify([(round(c[0], dp), round(c[1], dp)) for c in ring], tol)
    return [[x, y] for x, y in s]


def in_boxes(ring) -> bool:
    xs = [c[0] for c in ring]
    ys = [c[1] for c in ring]
    for x0, y0, x1, y1 in REGION_BOXES:
        if not (max(xs) < x0 or min(xs) > x1 or max(ys) < y0 or min(ys) > y1):
            return True
    return False


def do_world() -> None:
    gj = fetch("ne_110m_admin_0_countries.geojson")
    out = []
    for f in gj["features"]:
        p = f["properties"]
        rings = []
        for ring in rings_of(f["geometry"]):
            xs = [c[0] for c in ring]
            ys = [c[1] for c in ring]
            if max(xs) - min(xs) < 0.5 and max(ys) - min(ys) < 0.5:
                continue
            s = thin(ring, TOL_WORLD, 2)
            if len(s) > 3:
                rings.append(s)
        if not rings:
            continue
        out.append({"iso": p.get("ISO_A2_EH") or p.get("ISO_A2") or "", "name": p.get("NAME") or "", "rings": rings})
    out.sort(key=lambda s: s["name"])
    jdump({"source": CREDIT + ", Admin 0 countries, 1:110m", "url": SITE,
           "coords": "[lon, lat], 2 dp, Douglas-Peucker at 0.08°", "countries": out},
          GEO / "world.json", indent=None)
    say("world.json", out, "rings")


def do_subdiv() -> None:
    gj = fetch("ne_50m_admin_1_states_provinces.geojson")
    out = []
    for f in gj["features"]:
        p = f["properties"]
        cc = p.get("iso_a2") or ""
        if cc not in SUBDIV_COUNTRIES:
            continue
        rings = []
        for ring in rings_of(f["geometry"]):
            xs = [c[0] for c in ring]
            ys = [c[1] for c in ring]
            if max(xs) - min(xs) < MIN_RING and max(ys) - min(ys) < MIN_RING:
                continue
            s = thin(ring, TOL_SUB)
            if len(s) > 3:
                rings.append(s)
        if not rings:
            continue
        out.append({"iso": p.get("iso_3166_2") or cc, "cc": cc, "name": p.get("name") or "", "rings": rings})
    out.sort(key=lambda s: (s["cc"], s["iso"]))
    jdump({"source": CREDIT + ", Admin 1 states and provinces, 1:50m", "url": SITE,
           "coords": "[lon, lat], 3 dp, Douglas-Peucker at 0.02°", "states": out},
          GEO / "subdiv.json", indent=None)
    say("subdiv.json", out, "rings")


def do_coast() -> None:
    gj = fetch("ne_10m_coastline.geojson")
    out = []
    for f in gj["features"]:
        for line in rings_of(f["geometry"]):
            if not in_boxes(line):
                continue
            s = thin(line, TOL_COAST, 4)
            if len(s) > 2:
                out.append(s)
    jdump({"source": CREDIT + ", coastline, 1:10m, clipped to this project's wine regions",
           "url": SITE, "coords": "[lon, lat], 4 dp, Douglas-Peucker at 0.004°",
           "boxes": REGION_BOXES, "lines": out}, GEO / "coast.json", indent=None)
    print(f"wrote coast.json — {len(out)} lines, {sum(len(l) for l in out)} points, "
          f"{(GEO / 'coast.json').stat().st_size / 1024:.0f} KB")


def say(fn, out, _k):
    kb = (GEO / fn).stat().st_size / 1024
    print(f"wrote {fn} — {len(out)} shapes, {sum(len(r) for s in out for r in s['rings'])} points, {kb:.0f} KB")


def main(argv) -> int:
    want = set(argv) or {"world", "subdiv", "coast"}
    if "world" in want:
        do_world()
    if "subdiv" in want:
        do_subdiv()
    if "coast" in want:
        do_coast()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
