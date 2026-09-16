#!/usr/bin/env python3
"""harvest_wikipedia.py — the plain-text corpus the records are written against.

Wikipedia is not the authority for anything here, but it is a fast index to the
literature and it carries dates, spellings and the shape of a story. Each article is
fetched as plain text, stored under data/harvest/wp/<slug>.txt, and registered as a
source with ITS REVISION ID — so a citation points at the text this project actually
read, not at whatever the page says next year.

    python3 tools/harvest_wikipedia.py            # fetch every title in TITLES
    python3 tools/harvest_wikipedia.py --list     # print what is already on disk
    python3 tools/harvest_wikipedia.py "Tri-tip" "Santa Maria-style barbecue"

Writes data/sources/new-wp.json, which build.py merges into the registry.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, HARVEST, jdump, slugify  # noqa: E402

API = "https://en.wikipedia.org/w/api.php"
UA = "pinot-noir-build/0.1 (https://wichaa.net) python-urllib"
OUT = HARVEST / "wp"

TITLES = [
    # the grape and its family
    "Pinot noir", "Pinot Meunier", "Pinot gris", "Pinot blanc", "Pinot noir précoce",
    "Clone (viticulture)", "Foundation Plant Services", "Grafting", "Rootstock", "Phylloxera",
    "Chardonnay", "Gamay", "Vitis vinifera", "Ampelography",
    # Burgundy
    "Burgundy wine", "Côte de Nuits", "Côte de Beaune", "Côte Chalonnaise", "Climat (Burgundy)",
    "Gevrey-Chambertin", "Vosne-Romanée", "Chambolle-Musigny", "Nuits-Saint-Georges", "Pommard",
    "Volnay", "Beaune", "Romanée-Conti", "La Tâche", "Clos de Vougeot", "Musigny", "Richebourg",
    "Corton", "Domaine de la Romanée-Conti", "Grand cru", "Premier cru", "Appellation d'origine contrôlée",
    "Hospices de Beaune", "Négociant", "Monopole (wine)",
    # the rest of France
    "Champagne (wine region)", "Champagne", "Blanc de noirs", "Alsace wine", "Sancerre AOC",
    "Jura wine", "Crémant",
    # Germany and central Europe
    "German wine", "Ahr (wine region)", "Baden (wine region)", "Pfalz (wine region)",
    "Switzerland wine", "Austrian wine", "Alto Adige wine",
    # Oregon
    "Oregon wine", "Willamette Valley AVA", "Dundee Hills AVA", "Eola-Amity Hills AVA",
    "Ribbon Ridge AVA", "Yamhill-Carlton AVA", "Chehalem Mountains AVA", "McMinnville AVA",
    "The Eyrie Vineyards", "David Lett", "Domaine Drouhin Oregon", "International Pinot Noir Celebration",
    # California
    "California wine", "Russian River Valley AVA", "Sonoma Coast AVA", "Anderson Valley AVA",
    "Los Carneros AVA", "Santa Lucia Highlands AVA", "Santa Cruz Mountains AVA",
    "Sta. Rita Hills AVA", "Santa Maria Valley AVA", "Santa Barbara County wine", "Chalone AVA",
    "Calera Wine Company", "Williams Selyem Winery", "Au Bon Climat", "Jim Clendenen",
    "Josh Jensen", "Martin Ray (winemaker)", "André Tchelistcheff", "Paul Masson",
    "American Viticultural Area", "Judgment of Paris (wine)", "Sideways",
    # the southern hemisphere and the north
    "New Zealand wine", "Central Otago wine region", "Martinborough", "Marlborough wine region",
    "Australian wine", "Mornington Peninsula", "Yarra Valley", "Tasmanian wine",
    "Chilean wine", "Casablanca Valley", "San Antonio Valley (wine)", "Argentine wine",
    "Okanagan Valley (wine region)", "Prince Edward County (wine region)", "South African wine",
    "Walker Bay, Western Cape", "English wine",
    # in the cellar
    "Winemaking", "Maceration (wine)", "Malolactic fermentation", "Oak (wine)", "Barrel",
    "Yeast in winemaking", "Fermentation in winemaking", "Terroir", "Vintage", "Wine tasting",
    "Wine fault", "Brettanomyces", "Tannin", "Anthocyanin", "Rosé", "Sparkling wine",
    "Sulfur dioxide", "Biodynamic wine", "Organic wine", "Natural wine",
    "Wine and food matching", "Glass of wine", "Decanter (wine)", "Wine cellar",
    # the plate
    "Tri-tip", "Santa Maria-style barbecue", "Santa Maria, California", "Quercus agrifolia",
    "Rancheros Visitadores", "Barbecue", "Salsa (sauce)", "Bean", "Coq au vin",
    "Duck as food", "Salmon as food", "Edible mushroom", "Truffle", "Umami", "Beef aging",
    "Cut of beef", "Grilling", "Santa Maria Valley", "Chumash", "Rancho Tepusquet",
]


def get(params: dict) -> dict:
    q = urllib.parse.urlencode({**params, "format": "json", "formatversion": "2"})
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_one(title: str) -> dict | None:
    d = get({"action": "query", "prop": "extracts|info", "explaintext": 1,
             "exsectionformat": "plain", "redirects": 1, "titles": title})
    pages = d.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return None
    p = pages[0]
    text = p.get("extract") or ""
    if len(text) < 400:
        return None
    return {"title": p["title"], "pageid": p["pageid"], "revid": p.get("lastrevid"),
            "touched": p.get("touched"), "chars": len(text), "text": text}


def main(argv) -> int:
    if "--list" in argv:
        for p in sorted(OUT.glob("*.txt")):
            print(f"{p.stem:42s} {p.stat().st_size / 1024:6.1f} KB")
        return 0
    titles = [a for a in argv if not a.startswith("--")] or TITLES
    OUT.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    manifest = {}
    mpath = HARVEST / "wp.json"
    if mpath.exists():
        manifest = {r["slug"]: r for r in json.loads(mpath.read_text())["articles"]}
    missing = []
    for i, t in enumerate(titles, 1):
        slug = slugify(t)
        if (OUT / f"{slug}.txt").exists() and slug in manifest and "--force" not in argv:
            continue
        try:
            rec = fetch_one(t)
        except Exception as e:                      # noqa: BLE001 — a network blip is not a crash
            print(f"  !! {t}: {e}")
            time.sleep(2)
            continue
        if not rec:
            missing.append(t)
            print(f"  -- {t}: no article")
            continue
        (OUT / f"{slug}.txt").write_text(rec.pop("text"), encoding="utf-8")
        rec.update({"slug": slug, "asked": t, "accessed": today})
        manifest[slug] = rec
        print(f"  {i:3d}/{len(titles)}  {rec['title']:45s} {rec['chars'] / 1000:5.1f}k  rev {rec['revid']}")
        time.sleep(0.4)
    arts = sorted(manifest.values(), key=lambda r: r["slug"])
    jdump({"source": "English Wikipedia, via the MediaWiki action API",
           "licence": "CC BY-SA 4.0", "note": "corpus only — each record cites the revision it read",
           "missing": missing, "articles": arts}, mpath)
    jdump({"sources": [{
        "id": f"s:wp-{a['slug']}", "kind": "encyclopaedia", "title": a["title"],
        "publisher": "Wikipedia", "url": f"https://en.wikipedia.org/wiki/?curid={a['pageid']}",
        "permalink": f"https://en.wikipedia.org/w/index.php?oldid={a['revid']}",
        "accessed": a["accessed"], "licence": "CC BY-SA 4.0",
    } for a in arts]}, DATA / "sources" / "new-wp.json")
    print(f"\n{len(arts)} articles on disk, {sum(a['chars'] for a in arts) / 1e6:.2f} M characters"
          f"{', ' + str(len(missing)) + ' asked for and not found' if missing else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
