#!/usr/bin/env python3
"""build.py — records + harvests → build/api (JSON) + build/searchdocs.json + search tables.

Order: validate → enrich → write. Nothing is written if validation fails.

Outputs (all regenerated, never hand-edited):
  build/api/nodes.json               every enriched record
  build/api/<type>/<id>.json         one per record
  build/api/index.json               directory: id, type, name, region, facets, blurb
  build/api/cellars.json             curated cellars and vineyards + the OSM harvest, one row each
  build/api/kin.json                 every directed kin edge, plus auto backlinks
  build/api/vocab/*.json             regions, types, facets
  build/api/sources.json             the source registry (merged)
  build/api/coverage.json            scope as an object: what is in, what is not, where rows come from
  build/searchdocs.json              one document per record
  data/search/pinot.thesaurus.json   mined from the records for search-core (synonymy only)

    python3 tools/build.py
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (BUILD, DATA, SOURCES, TIER_LABEL, TYPES, jdump, jload,  # noqa: E402
                    load_harvest, load_nodes, load_sources, load_vocab, state_by_geo)
from validate import validate_all  # noqa: E402

SEARCH_DIR = DATA / "search"
API = BUILD / "api"
TAGS = {e["key"]: e for e in load_vocab("tags").get("entries", [])}
RECOG = {e["key"]: e for e in load_vocab("recognizers").get("entries", [])}
# A harvested list in data/harvest/tag-lists.json names the tag it grants and the source
# id that stands behind it. Nothing else may put a tag on a harvested row.


def merge_sources() -> dict:
    """sources.json + every data/sources/new-*.json, de-duplicated by id, written back to sources.json."""
    base = jload(SOURCES)
    have = {s["id"] for s in base["sources"]}
    added = 0
    for p in sorted(SOURCES.parent.glob("new-*.json")):
        d = jload(p)
        for s in d.get("sources", []):
            if s.get("id") and s["id"] not in have:
                base["sources"].append(s)
                have.add(s["id"])
                added += 1
        p.unlink()
    if added:
        jdump(base, SOURCES)
        print(f"merged {added} new sources into sources.json")
    return {s["id"]: s for s in base["sources"]}


def blurb(r: dict, n=220) -> str:
    """The first sentence(s) of `what` that fit in n characters; a word boundary and an ellipsis otherwise."""
    w = r["text"]["what"].strip()
    if len(w) <= n:
        return w
    head = w[:n]
    if ". " in head and len(head.rsplit(". ", 1)[0]) > 60:
        return head.rsplit(". ", 1)[0] + "."
    return head.rsplit(" ", 1)[0].rstrip(",;:—-") + "…"


def tier_for(rec: dict, path: str) -> dict:
    prov = rec.get("provenance", {})
    best = None
    for p, v in prov.get("fields", {}).items():
        if path == p or path.startswith(p + "."):
            if best is None or len(p) > len(best[0]):
                best = (p, v)
    return best[1] if best else prov.get("default", {})


def enrich(r: dict, by_id: dict, sources: dict, regions: dict) -> dict:
    out = {k: v for k, v in r.items() if not k.startswith("_")}
    out["blurb"] = blurb(out)
    out["region_terms"] = [dict(regions.get(k) or {"key": k, "name": k}) for k in out["region"]]
    out["kin_out"] = []
    for k in out.get("kin", []):
        t = by_id.get(k["to"])
        if t:
            out["kin_out"].append({"to": k["to"], "type": t["type"], "name": t["names"]["name"], "as": k["as"], "rel": k.get("rel", "kin")})
    out["source_list"] = [dict(sources[s], id=s) for s in out.get("sources", []) if s in sources]
    out["tiers"] = {p: tier_for(out, p) for p in ("text.what", "text.story", "text.how", "text.today", "etymology", "geo", "address")
                    if p.split(".")[0] in out and (len(p.split(".")) == 1 or p.split(".")[1] in out[p.split(".")[0]])}
    out["primary_image"] = next((im for im in out.get("images", []) if im.get("primary")), (out.get("images") or [None])[0])
    out["tag_facts"] = [dict(TAGS.get(t["tag"], {"key": t["tag"], "label": t["tag"], "icon": ""}), **{"source": t["source"], "note": t.get("note", ""), "tier": t.get("tier", "cited"), "url": t.get("url", "")}) for t in out.get("tags", [])]
    out["recognition_facts"] = [dict(RECOG.get(r["by"], {"key": r["by"], "label": r["by"]}), **{"what": r["what"], "year": r.get("year"), "source": r["source"], "url": r.get("url", "")}) for r in out.get("recognitions", [])]
    out["acclaim"] = len({r["by"] for r in out.get("recognitions", [])})
    return out


def backlinks(recs: list[dict]):
    """Every record learns who links to it, with that record's sentence (kin_in). Never invented prose."""
    by_id = {r["id"]: r for r in recs}
    for r in recs:
        r["kin_in"] = []
    for r in recs:
        for k in r["kin_out"]:
            t = by_id.get(k["to"])
            if t:
                t["kin_in"].append({"from": r["id"], "type": r["type"], "name": r["names"]["name"], "as": k["as"], "rel": k["rel"]})


def search_doc(r: dict) -> dict:
    n = r["names"]
    et = r.get("etymology") or {}
    return {
        "id": r["id"], "type": r["type"], "name": n["name"],
        "names": " ".join([n["name"]] + n.get("aliases", []) + [n.get("said", "")]),
        "terms": " ".join([r["type"]] + [t.get("name", "") for t in r["region_terms"]] + [tf["label"] for tf in r.get("tag_facts", [])] + [rf["label"] for rf in r.get("recognition_facts", [])] +
                          [rc.get("title", "") for rc in r.get("recipes", [])] +
                          [str(v) if not isinstance(v, list) else " ".join(map(str, v)) for v in (r.get("facets") or {}).values()] +
                          [k["name"] for k in r["kin_out"]] + [(r.get("address") or {}).get(k, "") for k in ("city", "county", "state")]),
        "text": " ".join([r["text"].get(k, "") for k in ("what", "story", "how", "today", "notes")] + [et.get("root", ""), et.get("note", "")] +
                         [c["tell"] for c in r.get("confusable_with", [])]),
        "blurb": r["blurb"], "state": (r.get("facets") or {}).get("state") or (r.get("address") or {}).get("state") or "",
    }


def mine_thesaurus(recs: list[dict]) -> int:
    """Synonymy groups from each record's own names and aliases — never hand-curated here."""
    groups = []
    for r in recs:
        n = r["names"]
        g = sorted({x.lower().strip() for x in [n["name"]] + n.get("aliases", []) if x and len(x.split()) <= 4})
        if len(g) >= 2:
            groups.append(g)
    # words a wine list, a label and a grower use for the same thing
    groups += [
        ["pinot noir", "pinot", "spatburgunder", "spätburgunder", "blauburgunder", "pinot nero", "blauer burgunder"],
        ["burgundy", "bourgogne"],
        ["vineyard", "vigne", "climat", "lieu-dit", "site"],
        ["cellar", "domaine", "winery", "weingut", "estate"],
        ["clone", "selection", "sélection massale", "massale"],
        ["whole cluster", "whole-cluster", "stem inclusion", "vendange entière"],
        ["malolactic fermentation", "malo", "mlf"],
        ["punch down", "pigeage", "punching down"],
        ["tri-tip", "tri tip", "triangle roast", "santa maria steak"],
        ["barbecue", "barbeque", "bar-b-q", "bbq"],
        ["ava", "american viticultural area", "appellation"],
    ]
    SEARCH_DIR.mkdir(parents=True, exist_ok=True)
    jdump({"note": "mined by build.py from data/nodes names + aliases — synonymy only", "groups": groups}, SEARCH_DIR / "pinot.thesaurus.json", indent=0)
    return len(groups)


def cellars_table(recs: list[dict], osm: dict | None) -> dict:
    """Curated cellars and named vineyards, plus the OpenStreetMap harvest, in one table.
    A curated cellar that also sits in OSM keeps its own row and gains the osm_id; the
    harvested row is dropped so nobody appears twice."""
    rows = []
    curated_names = {}
    for r in recs:
        if r["type"] not in ("producer", "vineyard"):
            continue
        g = r.get("geo") or {}
        a = r.get("address") or {}
        f = r.get("facets") or {}
        hrs = r.get("hours") or {}
        rows.append({"days": day_state(r, None), "hours_text": hrs.get("text", ""), "sold_out": bool(hrs.get("sold_out")),
                     "id": r["id"], "kind": r["type"], "name": r["names"]["name"], "country": a.get("country") or f.get("country"),
                     "state": a.get("state"), "city": a.get("city", ""), "lat": g.get("lat"), "lon": g.get("lon"),
                     "regions": r.get("region", []), "status": f.get("status"), "established": f.get("established"),
                     "curated": True, "url": f"{r['type']}/{r['id']}/", "blurb": r["blurb"],
                     "tier": tier_for(r, "text.what").get("tier"), "osm_id": None,
                     "tags": sorted({t["tag"] for t in r.get("tags", [])}), "recognitions": r.get("acclaim", 0),
                     "recognized_by": [RECOG.get(x["by"], {}).get("label", x["by"]) for x in r.get("recognitions", [])],
                     "image": (r.get("primary_image") or {}).get("file")})
        curated_names[_norm(r["names"]["name"])] = rows[-1]
        for al in r["names"].get("aliases", []):
            curated_names[_norm(al)] = rows[-1]
    n_osm = 0
    by_rec = {r["id"]: r for r in recs if r["type"] in ("producer", "vineyard")}
    listed: dict = {}
    for lst in (load_harvest("tag-lists") or {}).get("lists", []):
        grants = lst.get("grants")
        if grants not in TAGS:
            print(f"warn  tag-lists: {lst.get('list')!r} grants {grants!r}, which is not a tag key — skipped")
            continue
        for row in lst.get("rows", []):
            if row.get("name"):
                listed.setdefault((_norm(row["name"]), (row.get("country") or "").upper()), []).append((lst.get("list"), grants))
    for p in (osm or {}).get("places", []):
        key = _norm(p["name"])
        t = p["tags"]
        hit = curated_names.get(key)
        if hit and hit["lat"] is not None and abs(hit["lat"] - p["lat"]) < 0.05 and abs(hit["lon"] - p["lon"]) < 0.05:
            hit["osm_id"] = p["osm_id"]
            # The curated row keeps its own everything, but it should not throw away days
            # OpenStreetMap already knows just because someone wrote the cellar up. The
            # record's own hours still win, day by day, inside day_state().
            if t.get("opening_hours") and all(v == "unknown" for v in hit["days"].values()):
                hit["days"] = day_state(by_rec.get(hit["id"]), t["opening_hours"])
                hit["osm_hours"] = t["opening_hours"]
            continue
        cc = (p.get("country") or "").upper()
        tags = []
        lists_hit = listed.get((_norm(p["name"]), cc), []) or listed.get((_norm(p["name"]), ""), [])
        for _, grants in lists_hit:
            if grants not in tags:
                tags.append(grants)
        if t.get("opening_hours"):
            tags.append("tasting-room")
        rows.append({"days": day_state(None, t.get("opening_hours")), "hours_text": "", "sold_out": False,
                     "id": "osm-" + p["slug"], "kind": "osm", "name": p["name"], "country": cc, "state": p.get("state") or "",
                     "city": t.get("addr:city", ""), "lat": p["lat"], "lon": p["lon"], "regions": [p.get("box") or ""],
                     "status": None, "established": t.get("start_date"), "curated": False, "url": None, "blurb": "",
                     "tier": "harvested", "osm_id": p["osm_id"], "website": t.get("website"), "phone": t.get("phone"),
                     "hours": t.get("opening_hours"), "matcher": p.get("matcher"),
                     "street": " ".join(x for x in (t.get("addr:housenumber"), t.get("addr:street")) if x),
                     "postcode": t.get("addr:postcode"), "tags": tags, "tag_lists": [l for l, _ in lists_hit],
                     "recognitions": 0, "recognized_by": [], "image": None})
        n_osm += 1
    rows.sort(key=lambda x: ((x["country"] or "zz"), (x["state"] or ""), x["name"].lower()))
    return {"built": time.strftime("%Y-%m-%d"), "count": len(rows), "curated": len(rows) - n_osm, "harvested": n_osm,
            "harvest": {k: (osm or {}).get(k) for k in ("source", "license", "license_url", "attribution", "fetched_at", "osm_base", "boxes")} if osm else None,
            "places": rows}


DAYS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")


def day_state(rec: dict | None, osm_hours: str | None) -> dict:
    """open / closed / unknown for each of the seven days.

    A record's own hours win, because someone read them off the door or a page and named
    the source. OpenStreetMap fills the rest. A day nobody has told us about stays
    UNKNOWN — it is never quietly called closed, which is the difference between a
    directory that is useful and one that sends a reader to a locked door or, worse,
    tells them a pit is shut when it is open.
    """
    out = {d: "unknown" for d in DAYS}
    if osm_hours:
        import sys as _s
        from pathlib import Path as _P
        _s.path.insert(0, str(_P(__file__).resolve().parent))
        import viz
        got = viz.open_days([osm_hours])
        # a published timetable that names some days is taken to close the others
        if any(got.values()):
            for d in DAYS:
                out[d] = "open" if got[d] else "closed"
    h = (rec or {}).get("hours") or {}
    for d in h.get("closed", []):
        out[d] = "closed"
    for d in h.get("open", []):
        out[d] = "open"
    return out


def _norm(s: str) -> str:
    """Two cellars are the same cellar when the words that differ are the trade's
    furniture: domaine, winery, estate, cellars, the plural of vineyard."""
    s = unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()
    s = s.replace("&", "and").replace("'", "").replace("’", "")
    s = re.sub(r"\b(domaine|chateau|clos|weingut|bodega|azienda agricola|tenuta|cave|caves|maison)\b", "", s)
    s = re.sub(r"\b(winery|wineries|vineyard|vineyards|cellars|cellar|estate|wines|wine|company|co|inc|llc|ltd)\b", "", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def coverage(recs: list[dict], osm: dict | None, sources: dict) -> dict:
    by_type = {t: sum(1 for r in recs if r["type"] == t) for t in TYPES}
    return {
        "built": time.strftime("%Y-%m-%d"),
        "scope": "Pinot noir: the ground it grows on, the vines people planted, the cellars that press it, the words the trade uses, and what gets eaten beside it. Burgundy first, because everything else answers to it, then Oregon, California, Germany, New Zealand and the rest.",
        "records": by_type,
        "how_records_are_made": "Hand-written JSON, one per node, each field carrying a provenance tier (cited / harvested / tradition / inference / field). Cited fields name a source in sources.json. Tradition fields are general knowledge of the tradition and are hedged in the text.",
        "cellars": {
            "curated": by_type["producer"] + by_type["vineyard"],
            "harvested_from_osm": (osm or {}).get("count", 0),
            "osm_fetched_at": (osm or {}).get("fetched_at"),
            "reading_an_absence": "A cellar missing here is missing from OpenStreetMap on the fetch date, or sits outside the boxes queried, or has not been written up. None of that is a claim that it does not exist.",
            "osm_query": (osm or {}).get("query"),
        },
        "hours": {
            "cellars_with_any_day_known": 0, "open_sunday": 0, "closed_sunday": 0, "sunday_unknown": 0,
            "reading_an_absence": "A day is 'unknown' unless a source said so. Unknown is never rendered as closed.",
        },
        "images": {"count": sum(len(r.get("images", [])) for r in recs), "licences_accepted": ["CC0", "Public domain", "CC BY", "CC BY-SA", "FAL"]},
        "tags": {k: sum(1 for r in recs for t in r.get("tags", []) if t["tag"] == k) for k in TAGS},
        "tags_note": "A tag names its evidence (the owner's words, a press profile, a public directory or list). No evidence, no tag; absence of a tag says nothing about a place.",
        "recognitions": sum(len(r.get("recognitions", [])) for r in recs),
        "recipes": sum(len(r.get("recipes", [])) for r in recs),
        "sources": len(sources),
        "not_yet": ["field observations — no record carries the field tier yet", "vintage-by-vintage notes",
                    "prices, which move and which this project does not track", "planted area for most single vineyards",
                    "most of Burgundy's 1,247 climats", "photographs for most records"],
        "tiers": TIER_LABEL,
    }


def hours_coverage(rows: list) -> dict:
    su = [r["days"]["Su"] for r in rows]
    return {"cellars_with_any_day_known": sum(1 for r in rows if any(v != "unknown" for v in r["days"].values())),
            "open_sunday": su.count("open"), "closed_sunday": su.count("closed"), "sunday_unknown": su.count("unknown"),
            "reading_an_absence": "A day is 'unknown' unless a source said so. Unknown is never rendered as closed."}


def main() -> int:
    if validate_all(quiet=False) != 0:
        print("build refused: fix the errors above")
        return 1
    t0 = time.time()
    sources = merge_sources()
    regions = {e["key"]: e for e in load_vocab("regions").get("entries", [])}
    raw = load_nodes()
    by_id = {r["id"]: r for r in raw}
    recs = [enrich(r, by_id, sources, regions) for r in raw]
    backlinks(recs)
    osm = load_harvest("osm-places")
    for r in recs:
        jdump(r, API / r["type"] / f"{r['id']}.json")
    jdump({"built": time.strftime("%Y-%m-%d"), "count": len(recs), "nodes": recs}, API / "nodes.json")
    jdump({"built": time.strftime("%Y-%m-%d"), "count": len(recs), "nodes": [{
        "id": r["id"], "type": r["type"], "name": r["names"]["name"], "aliases": r["names"].get("aliases", []), "region": r["region"],
        "facets": r.get("facets", {}), "state": (r.get("facets") or {}).get("state") or (r.get("address") or {}).get("state"),
        "blurb": r["blurb"], "image": (r["primary_image"] or {}).get("file"), "confidence": r["confidence"], "tags": sorted({t["tag"] for t in r.get("tags", [])}), "acclaim": r.get("acclaim", 0),
        "has_recipes": bool(r.get("recipes")), "has_measures": bool(r.get("measures")),
        "needs_verification": r.get("needs_verification", False), "updated": r["updated"], "url": f"{r['type'] if r['type'] != 'term' else 'word'}/{r['id']}/",
    } for r in recs]}, API / "index.json")
    jdump({"built": time.strftime("%Y-%m-%d"), "edges": [dict(k, **{"from": r["id"]}) for r in recs for k in r["kin_out"]]}, API / "kin.json")
    for a in ("regions", "types", "facets"):
        jdump(load_vocab(a), API / "vocab" / f"{a}.json")
    jdump(jload(SOURCES), API / "sources.json")
    ptab = cellars_table(recs, osm)
    jdump(ptab, API / "cellars.json")
    cov = coverage(recs, osm, sources)
    cov["hours"] = hours_coverage(ptab["places"])
    jdump(cov, API / "coverage.json")
    docs = [search_doc(r) for r in recs]
    jdump({"built": time.strftime("%Y-%m-%dT%H:%M:%S"), "docs": docs}, BUILD / "searchdocs.json")
    ng = mine_thesaurus(recs)
    edges = sum(len(r["kin_out"]) for r in recs)
    print(f"built {len(recs)} nodes · {edges} kin edges · {sum(1 for r in recs if r['type'] in ('producer','vineyard'))} curated + {(osm or {}).get('count', 0)} OSM cellars · "
          f"thesaurus {ng} groups · {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
