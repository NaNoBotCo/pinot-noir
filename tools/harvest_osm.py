#!/usr/bin/env python3
"""harvest_osm.py — every winery, cellar door and wine shop OpenStreetMap holds inside
the pinot regions this project covers.

One Overpass query per box (BOXES below, each one a region key from
data/vocab/regions.json and the country it sits in), ways and relations reduced to a
centre point. Output is a harvest file, never a record: data/harvest/osm-places.json,
carrying the ODbL licence, the fetch time and the query itself — so an absence reads as
"not in OpenStreetMap on that date, inside that box" and nothing more.

Four matchers, and every row says which one caught it:
  winery       craft=winery
  cellar       tourism=wine_cellar
  shop         shop=wine — retail, and a weaker signal than the other two
  amenity      amenity=winery, which is not standard but is in use

    python3 tools/harvest_osm.py                 # every box
    python3 tools/harvest_osm.py --dry           # counts only, writes nothing
    python3 tools/harvest_osm.py --boxes burgundy,willamette

Refuses to overwrite a previous harvest with a much smaller one: an empty Overpass reply
is valid and looks exactly like "no wineries in Burgundy".
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HARVEST, jdump, jload, slugify  # noqa: E402

UA = "pinot-noir-build/0.1 (https://wichaa.net) python-urllib"
# Mirrors, tried in order, and the pauses stay long — these are somebody else's servers.
#
# ⚠ 2026-09-16: overpass-api.de, kumi.systems and overpass.osm.jp all refused every
# connection from this machine. overpass.osm.ch answered and looked healthy — and serves
# a SWITZERLAND-ONLY extract, so 27 of 28 boxes came back empty and the 28th returned
# only the Swiss corner of Baden. An empty box from a working mirror is indistinguishable
# from "no wineries there" unless you check: the sanity query at the bottom of this file
# counts craft=winery in the Côte d'Or, where the answer is definitely not zero.
ENDPOINTS = ["https://maps.mail.ru/osm/tools/overpass/api/interpreter",
             "https://overpass-api.de/api/interpreter",
             "https://overpass.kumi.systems/api/interpreter"]

SANITY = ('[out:json][timeout:60];nwr["craft"="winery"](46.9,4.7,47.3,5.05);out count;',
          "craft=winery in the Côte d'Or", 20)
OUT = HARVEST / "osm-places.json"

# key, country, south, west, north, east
BOXES = [
    ("willamette", "US", 44.0, -124.0, 46.2, -122.2),
    ("sonoma", "US", 38.0, -123.9, 39.6, -122.2),
    ("anderson-valley", "US", 38.8, -123.7, 39.3, -123.1),
    ("santa-cruz-mountains", "US", 36.9, -122.6, 37.5, -121.7),
    ("santa-lucia-highlands", "US", 36.2, -121.6, 36.8, -121.0),
    ("santa-barbara", "US", 34.4, -120.7, 35.2, -119.6),
    ("carneros", "US", 38.1, -122.6, 38.4, -122.1),
    ("finger-lakes", "US", 42.3, -77.5, 43.0, -76.4),
    ("burgundy", "FR", 46.6, 4.2, 47.7, 5.2),
    ("champagne", "FR", 48.7, 3.5, 49.5, 4.7),
    ("alsace", "FR", 47.9, 7.0, 49.1, 7.6),
    ("loire", "FR", 47.0, 2.4, 47.6, 3.2),
    ("jura", "FR", 46.6, 5.4, 47.2, 5.9),
    ("ahr", "DE", 50.4, 6.8, 50.7, 7.3),
    ("baden", "DE", 47.6, 7.5, 49.2, 9.0),
    ("pfalz", "DE", 49.0, 7.9, 49.7, 8.4),
    ("central-otago", "NZ", -45.4, 168.6, -44.6, 169.6),
    ("martinborough", "NZ", -41.4, 175.2, -40.9, 175.7),
    ("marlborough", "NZ", -41.7, 173.5, -41.3, 174.2),
    ("mornington", "AU", -38.5, 144.8, -38.1, 145.3),
    ("yarra", "AU", -37.9, 145.2, -37.4, 145.8),
    ("tasmania", "AU", -43.4, 146.6, -40.7, 148.3),
    ("casablanca", "CL", -33.6, -71.7, -32.9, -71.0),
    ("patagonia", "AR", -39.6, -68.5, -38.6, -67.2),
    ("hemel-en-aarde", "ZA", -34.5, 19.1, -34.2, 19.6),
    ("okanagan", "CA", 49.0, -119.8, 50.4, -119.2),
    ("niagara", "CA", 43.0, -79.7, 43.4, -79.0),
    ("alto-adige", "IT", 46.3, 11.1, 46.8, 11.6),
]

QUERY_TMPL = ('[out:json][timeout:180];'
              '('
              'nwr["craft"="winery"]({s},{w},{n},{e});'
              'nwr["tourism"="wine_cellar"]({s},{w},{n},{e});'
              'nwr["shop"="wine"]({s},{w},{n},{e});'
              'nwr["amenity"="winery"]({s},{w},{n},{e});'
              ');'
              'out center tags;')

KEEP = ("name", "name:en", "craft", "tourism", "shop", "amenity", "addr:housenumber", "addr:street", "addr:city",
        "addr:state", "addr:postcode", "addr:country", "phone", "website", "contact:website", "opening_hours",
        "wikidata", "wikipedia", "brand", "start_date", "operator", "description", "wheelchair", "check_date")


def matcher_of(t: dict) -> str:
    if t.get("craft") == "winery":
        return "winery"
    if t.get("tourism") == "wine_cellar":
        return "cellar"
    if t.get("amenity") == "winery":
        return "amenity"
    return "shop"


def overpass(q: str) -> dict:
    data = urllib.parse.urlencode({"data": q}).encode()
    last = None
    for ep in ENDPOINTS:
        try:
            req = urllib.request.Request(ep, data=data, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=240) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as ex:                       # noqa: BLE001
            last = ex
            time.sleep(3)
    raise last


def sanity() -> bool:
    """Refuse to run against a mirror that serves a regional extract: a global mirror
    finds dozens of wineries in the Côte d'Or, a Swiss one finds none."""
    q, what, floor = SANITY
    try:
        d = overpass(q)
        n = int(d["elements"][0]["tags"]["total"])
    except Exception as ex:                           # noqa: BLE001
        print(f"sanity check failed to run: {ex}")
        return False
    print(f"sanity: {n} {what} (need at least {floor})")
    return n >= floor


def main(argv) -> int:
    dry = "--dry" in argv
    if not sanity():
        print("REFUSED: the mirror answering is not serving the whole planet")
        return 3
    want = None
    for i, a in enumerate(argv):
        if a == "--boxes" and i + 1 < len(argv):
            want = set(argv[i + 1].split(","))
    boxes = [b for b in BOXES if not want or b[0] in want]
    rows, seen, per_box = [], set(), {}
    for key, cc, s, w, n, e in boxes:
        q = QUERY_TMPL.format(s=s, w=w, n=n, e=e)
        try:
            d = overpass(q)
        except Exception as ex:                       # noqa: BLE001
            print(f"  !! {key}: {ex}")
            time.sleep(10)
            continue
        got = 0
        for el in d.get("elements", []):
            t = {k: v for k, v in (el.get("tags") or {}).items() if k in KEEP}
            name = t.get("name") or t.get("name:en")
            if not name:
                continue
            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lon = el.get("lon") or (el.get("center") or {}).get("lon")
            if lat is None:
                continue
            oid = f"{el['type'][0]}{el['id']}"
            if oid in seen:
                continue
            seen.add(oid)
            rows.append({"osm_id": oid, "slug": slugify(f"{name}-{key}"), "name": name, "lat": round(lat, 6),
                         "lon": round(lon, 6), "box": key, "country": cc, "state": t.get("addr:state", ""),
                         "matcher": matcher_of(t), "tags": t})
            got += 1
        per_box[key] = got
        print(f"  {key:22s} {got:4d}")
        time.sleep(3)
    print(f"\n{len(rows)} rows across {len(per_box)} boxes")
    if dry:
        return 0
    old = jload(OUT) if OUT.exists() else None
    if old and not want and len(rows) < 0.75 * old.get("count", 0):
        print(f"REFUSED: {len(rows)} rows would replace {old['count']} — run --dry and look before forcing")
        return 2
    if old and want:
        keep = [r for r in old.get("places", []) if r["box"] not in {b[0] for b in boxes}]
        rows = keep + rows
    jdump({"source": "OpenStreetMap via the Overpass API",
           "license": "ODbL 1.0", "license_url": "https://opendatacommons.org/licenses/odbl/1-0/",
           "attribution": "© OpenStreetMap contributors",
           "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "query": QUERY_TMPL, "endpoints": ENDPOINTS,
           # counted from the merged rows, not from this run alone: a partial rerun must not
           # blank out the boxes it did not touch
           "boxes": [{"key": b[0], "country": b[1], "bbox": list(b[2:]),
                      "rows": sum(1 for r in rows if r["box"] == b[0]),
                      "fetched_now": per_box.get(b[0])} for b in BOXES],
           "reading_an_absence": "Rows come from inside the boxes listed, on the fetch date. A cellar outside those boxes, or missing from OpenStreetMap, is simply not here.",
           "count": len(rows), "places": sorted(rows, key=lambda r: (r["box"], r["name"].lower()))}, OUT)
    print(f"wrote {OUT.relative_to(OUT.parent.parent.parent)} — {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
