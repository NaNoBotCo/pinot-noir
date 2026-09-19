#!/usr/bin/env python3
"""site.py — build/api → build/site: a static site people and bots can both read.

People: a 1997-directory front (Term (count) links, hierarchy on the page), one page per
node with its kin said in both directions, an inline SVG map of every place, a glossary
with roots, large type, high contrast, theme-aware, motion gated behind
prefers-reduced-motion, no external requests.

Bots: JSON-LD on every page, robots.txt that ALLOWS everything and says so with
Content-Signal, sitemap.xml with lastmod, llms.txt and llms-full.txt, Atom feed,
OpenSearch description, CSV + JSONL dumps, the whole /api tree.

    python3 tools/site.py                          # SITE_URL defaults to the Pages address
    SITE_URL=https://example.org python3 tools/site.py
"""
from __future__ import annotations

import csv
import html
import json
import math
import os

import fleet
import random
import re
import shutil
import sys
import urllib.parse
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BUILD, DATA, GEO, IMAGES, ROOT, SEARCH_CORE, TIER_LABEL, TYPES, VENDOR, jload  # noqa: E402
import pages  # noqa: E402
import viz  # noqa: E402
import worldmap  # noqa: E402

SITE = BUILD / "site"
API = BUILD / "api"
SITE_URL = os.environ.get("SITE_URL", "https://nanobotco.github.io/pinot-noir").rstrip("/")
SITE_NAME = "Pinot Country"
TAGLINE = "one thin-skinned grape, the ground it answers to, and what gets eaten beside it"
DATA_LICENSE = "https://creativecommons.org/licenses/by/4.0/"   # the records' own licence — Nan's call; default CC BY 4.0
AUTHOR = {"@type": "Person", "name": "NaN", "url": "https://wichaa.net"}
E = html.escape
PATH_OF = {"variety": "variety", "region": "region", "vineyard": "vineyard", "producer": "producer", "clone": "clone",
           "practice": "practice", "pairing": "pairing", "person": "person", "org": "org", "event": "event",
           "term": "word", "art": "art", "story": "story"}
DIR_OF = {"variety": "vine", "region": "regions", "vineyard": "vineyards", "producer": "cellars", "clone": "clones",
          "practice": "practices", "pairing": "table", "person": "people", "org": "organizations", "event": "events",
          "term": "words", "art": "art", "story": "stories"}
COUNTRY_NAME = {"FR": "France", "US": "United States", "DE": "Germany", "NZ": "New Zealand", "AU": "Australia",
                "IT": "Italy", "CL": "Chile", "AR": "Argentina", "ZA": "South Africa", "CA": "Canada",
                "CH": "Switzerland", "AT": "Austria", "GB": "United Kingdom"}


def clip(text: str, n: int) -> str:
    """Cut at a word, and say that it was cut."""
    t = (text or "").strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"


def rel(depth: int) -> str:
    return "../" * depth


def url_of(r: dict) -> str:
    return f"{PATH_OF[r['type']]}/{r['id']}/"


def img_src(im: dict, depth: int) -> str:
    return f"{rel(depth)}images/{im['file']}"


CSS = """
:root{--bg:#faf7f1;--panel:#fffdf8;--ink:#1f1a1c;--mute:#6d6360;--line:#e6ddd0;--wine:#7b2038;--bright:#a3324f;
  --gold:#957324;--leaf:#4f6b3a;--stone:#6b6257;--focus:#1f5fa8;--chip:#f0e8dc;--land:#ece3d3;--landline:#b6aa94;
  /* A wine label is set in a serif and a cellar door is painted by hand. Headings take a
     broad old-style serif, small labels take a humanist face with wide caps, and the
     reading text stays a serif that holds up at 19px. Everything is already on the
     reader's machine: no webfont, no request off the page. */
  --display:"Palatino Linotype",Palatino,"Iowan Old Style","Book Antiqua",Georgia,serif;
  --sign:Optima,"Gill Sans","Gill Sans MT",Candara,"Trebuchet MS",sans-serif;
  --body:"Iowan Old Style",Georgia,"Times New Roman",serif;
  --ui:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#171314;--panel:#201a1c;--ink:#f3eae5;--mute:#b3a69f;--line:#352b2d;--wine:#e5809a;--bright:#f09db3;--gold:#d9b25e;--leaf:#9bc37b;--stone:#c9bcb4;--focus:#8ab4f8;--chip:#2a2123;--land:#39302f;--landline:#7a6a66}}
:root[data-theme="dark"]{--bg:#171314;--panel:#201a1c;--ink:#f3eae5;--mute:#b3a69f;--line:#352b2d;--wine:#e5809a;--bright:#f09db3;--gold:#d9b25e;--leaf:#9bc37b;--stone:#c9bcb4;--focus:#8ab4f8;--chip:#2a2123;--land:#39302f;--landline:#7a6a66}
*{box-sizing:border-box}html{font-size:19px;scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--body);line-height:1.62;font-size:1.02rem}
a{color:var(--wine);text-decoration-thickness:.07em;text-underline-offset:.16em}a:hover{color:var(--bright)}
a:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid var(--focus);outline-offset:2px;border-radius:4px}
header.top{border-bottom:1px solid var(--line);padding:.7rem 1rem;max-width:66rem;margin:0 auto;display:flex;gap:.6rem 1.2rem;flex-wrap:wrap;align-items:baseline}
header.top .brand{font-weight:700;text-decoration:none;color:var(--ink);letter-spacing:.01em;font-family:var(--display);font-size:1.1rem}header.top .brand b{color:var(--wine)}
nav.crumbs{font-size:.84rem;color:var(--mute);font-family:var(--ui)}nav.crumbs a{text-decoration:none}nav.crumbs a:hover{text-decoration:underline}
main{max-width:66rem;margin:0 auto;padding:1.2rem 1rem 4rem}
h1{font-family:var(--display);font-size:clamp(2rem,4.4vw,2.9rem);line-height:1.1;margin:.5rem 0 .3rem;font-weight:700;letter-spacing:-.005em}
h1 .kind{display:block;font-size:.74rem;color:var(--gold);text-transform:uppercase;letter-spacing:.24em;font-family:var(--sign);margin-bottom:.5rem}
h2{font-family:var(--display);font-size:1.34rem;margin:1.8rem 0 .5rem;border-bottom:2px solid var(--line);padding-bottom:.25rem;font-weight:700}
h3{font-family:var(--display);font-size:1.08rem;margin:1rem 0 .3rem;font-weight:700}
.said{font-style:italic;color:var(--mute);margin:.2rem 0 .8rem}.lede{font-size:1.12rem;margin:.2rem 0 1rem}.mute{color:var(--mute)}
p{margin:.55rem 0}.prose p{margin:.75rem 0}.prose{max-width:38rem}
.dir{display:grid;grid-template-columns:repeat(auto-fill,minmax(19rem,1fr));gap:1.3rem 2.4rem;align-items:start;margin-top:.8rem}
.dir section{margin:0}.dir h2{margin:.2rem 0 .3rem;border:0;font-size:1.14rem}.dir h2 a{text-decoration:none;color:var(--ink)}.dir h2 a:hover{color:var(--wine)}
.dir ul{list-style:none;margin:0;padding:0 0 0 .7rem;border-left:2px solid var(--line)}.dir li{margin:.14rem 0}.dir li.sub{padding-left:.9rem;font-size:.95rem}
.count{color:var(--mute);font-size:.85em;font-family:var(--ui)}
.chip{display:inline-block;background:var(--chip);border:1px solid var(--line);border-radius:999px;padding:.05rem .6rem;font-size:.78rem;margin:.1rem .25rem .1rem 0;color:var(--ink);font-family:var(--ui)}
.tier-cited{border-color:var(--focus)}.tier-harvested{border-color:var(--stone)}.tier-tradition{border-color:var(--gold)}.tier-inference{border-style:dashed}.tier-field{border-color:var(--wine)}
table{border-collapse:collapse;width:100%;margin:.4rem 0 1rem;font-size:.95rem}th,td{text-align:left;vertical-align:top;padding:.45rem .5rem;border-bottom:1px solid var(--line)}th{width:28%;color:var(--mute);font-weight:600}
.kin{display:grid;grid-template-columns:repeat(auto-fill,minmax(17rem,1fr));gap:.9rem}
.kin a.card{display:block;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:.8rem .95rem;text-decoration:none;color:var(--ink)}
.kin a.card b{display:block;font-size:1.03rem;color:var(--wine);font-family:var(--display);font-weight:700}
.kin a.card small{display:block;font-size:.68rem;color:var(--gold);text-transform:uppercase;letter-spacing:.18em;font-family:var(--sign)}
.kin a.card span{display:block;margin-top:.3rem;font-size:.92rem;color:var(--ink)}
.kin a.card:hover b{color:var(--bright)}
figure{margin:0 0 1rem;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:.6rem}
figure img{width:100%;height:auto;max-height:32rem;object-fit:contain;border-radius:8px;display:block}
figcaption{font-size:.8rem;color:var(--mute);margin-top:.4rem;font-family:var(--ui)}
.gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(12rem,1fr));gap:.7rem}.gallery figure{margin:0}
.hero{display:grid;grid-template-columns:1.05fr .95fr;gap:1.6rem;align-items:center;margin:.6rem 0 1.4rem}
.hero h1{font-size:clamp(2.3rem,6vw,3.6rem);letter-spacing:-.012em}.hero .sub{font-size:1.15rem;color:var(--mute);font-style:italic;max-width:32rem}
@media(max-width:760px){.hero{grid-template-columns:1fr}html{font-size:18px}}
.mapwrap{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:.5rem}.mapwrap svg{width:100%;height:auto;display:block}
.facts{display:flex;flex-wrap:wrap;gap:.8rem;margin:.6rem 0 1.2rem}
.fact{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:.7rem 1rem;min-width:8rem;text-align:center}
.fact .n{font-family:var(--display);font-size:2rem;font-weight:700;line-height:1}
.fact .l{font-size:.72rem;color:var(--mute);margin-top:.28rem;font-family:var(--sign);text-transform:uppercase;letter-spacing:.12em}
.search{display:flex;gap:.5rem;margin:.6rem 0 1rem}
.search input{flex:1;font:inherit;font-size:1.1rem;padding:.6rem .8rem;border:2px solid var(--line);border-radius:10px;background:var(--panel);color:var(--ink)}
.search button{font:inherit;padding:.6rem 1rem;border-radius:10px;border:2px solid var(--wine);background:var(--wine);color:#fff;cursor:pointer}
.tierline{font-size:.9rem;color:var(--mute);margin:.2rem 0 .8rem}.legend{font-size:.85rem;color:var(--mute);border-top:1px solid var(--line);margin-top:2rem;padding-top:.6rem}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(15rem,1fr));gap:1rem;align-items:start}
.card .thumb{width:100%;aspect-ratio:16/9;object-fit:cover;object-position:80% center;border-radius:9px;margin-bottom:.55rem;display:block;background:var(--chip)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:.9rem}
.card a.t{font-family:var(--display);font-weight:700;text-decoration:none;font-size:1.06rem}.card p{margin:.3rem 0 0;font-size:.9rem;color:var(--mute)}
footer{max-width:66rem;margin:0 auto;padding:1rem;color:var(--mute);font-size:.85rem;border-top:1px solid var(--line);font-family:var(--ui)}.bots a{margin-right:.7rem}.support{margin:.45rem 0 0}.support a{margin-right:.5rem}.fleet{margin:.6rem 0 0;line-height:1.9}.fleet a{margin-right:.55rem;white-space:nowrap}
.btn{display:inline-block;padding:.55rem 1.05rem;border-radius:999px;background:var(--wine);color:#fff;text-decoration:none;font-weight:700;border:2px solid var(--wine);font-family:var(--sign);font-size:.92rem;letter-spacing:.04em}
.btn.ghost{background:transparent;color:var(--ink);border-color:var(--line)}.btn:hover{color:#fff;filter:brightness(1.1)}.btn.ghost:hover{color:var(--ink);border-color:var(--wine)}
.cta{display:flex;gap:.6rem;flex-wrap:wrap;margin:.8rem 0}
.etym{background:var(--panel);border-left:4px solid var(--gold);border-radius:0 12px 12px 0;padding:.7rem 1rem;margin:.8rem 0}
.wander{font-size:.85rem;color:var(--mute)}
.pl-list{columns:2;column-gap:2.4rem;font-size:.95rem}.pl-list h3{break-after:avoid;margin:.6rem 0 .2rem}.pl-list ul{margin:0 0 .5rem;padding-left:1rem}@media(max-width:700px){.pl-list{columns:1}}
mark.tier{background:transparent;color:var(--mute);font-style:italic}
.whenbox{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:.9rem 1rem;margin:.4rem 0 1rem}
.whenbox .hrs{margin:.55rem 0 0;font-size:.95rem}
.two-up{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin:1.4rem 0}@media(max-width:700px){.two-up{grid-template-columns:1fr}}
.pitch{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:1rem 1.2rem}
.tagrow{display:flex;flex-wrap:wrap;gap:.35rem;margin:.5rem 0 .3rem}
.tagrow a.tg,.tagrow span.tg{display:inline-flex;align-items:center;gap:.3rem;background:var(--chip);border:1px solid var(--line);border-radius:999px;padding:.15rem .7rem;font-size:.84rem;font-family:var(--ui);text-decoration:none;color:var(--ink)}
.tagrow a.tg:hover{border-color:var(--wine)}
.tagrow .tg.ownership{border-color:var(--gold)}.tagrow .tg.welcome{border-color:#9b59b6}.tagrow .tg.certification{border-color:var(--leaf)}.tagrow .tg.visit{border-color:var(--wine)}
.acc{display:flex;flex-wrap:wrap;gap:.4rem;margin:.3rem 0 .6rem;font-size:.86rem;font-family:var(--ui)}
.acc b{color:var(--gold)}
.recipe{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--gold);border-radius:0 12px 12px 0;padding:.8rem 1rem;margin:.8rem 0}
.recipe h3{margin:.1rem 0 .2rem;font-size:1.02rem}
.recipe .src{font-size:.82rem;color:var(--mute);font-family:var(--ui)}
.recipe .txt{white-space:pre-wrap;margin:.5rem 0 0;font-size:.97rem}
.recipe ul{margin:.4rem 0 0;padding-left:1.1rem}
.sect{margin:1.2rem 0}
.gal2{display:grid;grid-template-columns:repeat(auto-fill,minmax(14rem,1fr));gap:.8rem;margin:.6rem 0}
.gal2 figure{margin:0}
.hero-word{display:flex;flex-direction:column;gap:.4rem;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:1.2rem}
.hero-word b{font-family:var(--display);font-size:clamp(1.8rem,5vw,3rem);color:var(--wine);line-height:1}
.hero-word span{font-size:.95rem;color:var(--mute)}
.toc{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:.9rem 1.1rem;margin:1rem 0}
.toc ol{margin:.3rem 0 0;padding-left:1.2rem}.toc li{margin:.16rem 0}
@media (prefers-reduced-motion: no-preference){.kin a.card,.card,.fact{transition:transform .18s ease,box-shadow .18s ease}
.kin a.card:hover,.card:hover{transform:translateY(-3px);box-shadow:0 10px 24px rgba(0,0,0,.09)}
.btn{transition:transform .15s ease}.btn:hover{transform:scale(1.04)}
.search input{transition:box-shadow .2s}.search input:focus{box-shadow:0 0 0 4px color-mix(in srgb,var(--wine) 22%,transparent)}
.mapwrap circle.p{transition:r .15s ease}.mapwrap circle.p:hover{r:6}}
"""


def page(title: str, body: str, depth: int, desc: str = "", jsonld: list | None = None, canonical: str = "", extra_head: str = "",
         og_image: str = "", alt_json: str = "", og_alt: str = "", og_type: str = "website", card: str = "", share_title: str = "") -> str:
    r = rel(depth)
    if card and (CARDS_DIR / f"{card}.jpg").exists():
        og_image = f"{SITE_URL}/cards/{card}.jpg"
    ld = "".join(f'<script type="application/ld+json">{json.dumps(o, ensure_ascii=False)}</script>' for o in (jsonld or []))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc[:300])}">
<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1">
<meta name="color-scheme" content="light dark">
<meta property="og:site_name" content="{E(SITE_NAME)}"><meta property="og:locale" content="en_US">
<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc[:200])}"><meta property="og:type" content="{E(og_type)}">
{f'<meta property="og:image" content="{E(og_image)}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:type" content="image/jpeg"><meta property="og:image:alt" content="{E(og_alt or title)}"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{E(og_image)}"><meta name="twitter:image:alt" content="{E(og_alt or title)}"><meta name="twitter:title" content="{E(title)}"><meta name="twitter:description" content="{E(desc[:200])}">' if og_image else ''}
{f'<link rel="canonical" href="{E(canonical)}">' if canonical else ''}
{f'<link rel="alternate" type="application/json" href="{E(alt_json)}">' if alt_json else ''}
<link rel="manifest" href="{r}manifest.webmanifest">
<meta name="theme-color" content="#7b2038">
<link rel="icon" href="{r}icon.svg" type="image/svg+xml">
<link rel="search" type="application/opensearchdescription+xml" title="{E(SITE_NAME)}" href="{r}opensearch.xml">
<link rel="alternate" type="application/atom+xml" title="{E(SITE_NAME)} updates" href="{r}feed.xml">
{extra_head}
<style>{CSS}{SHARE_CSS}{viz.DAY_CSS}{pages.CHART_CSS}{pages.FIND_CSS}</style>
{ld}
</head>
<body>
<header class="top"><a class="brand" href="{r}index.html">Pinot <b>Country</b></a>
<nav class="crumbs"><a href="{r}index.html">Directory</a> · <a href="{r}visit/index.html">Visit</a> · <a href="{r}map/index.html">Map</a> · <a href="{r}regions/index.html">Regions</a> · <a href="{r}clones/index.html">Clones</a> · <a href="{r}table/index.html">At the table</a> · <a href="{r}numbers/index.html">Numbers</a> · <a href="{r}stories/index.html">Stories</a> · <a href="{r}search/index.html">Search</a> · <a href="{r}words/index.html">Words</a> · <a href="{r}sources/index.html">Sources</a> · <a href="{r}coverage/index.html">Coverage</a> · <a href="{r}api/index.json">API</a> · <a href="{r}llms.txt">llms.txt</a> · <a class="wander" href="{r}wander.html" title="a page at random">🎲 Wander</a></nav></header>
<main>
{body}
{share_row(canonical, share_title or title) if canonical else ""}
</main>
<script>document.addEventListener("keydown",function(e){{if(e.key==="r"&&!e.metaKey&&!e.ctrlKey&&!e.altKey&&!/input|textarea/i.test(e.target.tagName))location.href="{r}wander.html"}});</script>
<footer>
<div class="bots">For the machines: <a href="{r}api/nodes.json">nodes.json</a> <a href="{r}api/cellars.json">cellars.json</a> <a href="{r}api/kin.json">kin.json</a> <a href="{r}nodes.jsonl">nodes.jsonl</a> <a href="{r}nodes.csv">nodes.csv</a> <a href="{r}llms-full.txt">llms-full.txt</a> <a href="{r}sitemap.xml">sitemap.xml</a> <a href="{r}feed.xml">feed.xml</a> <a href="{r}api/coverage.json">coverage</a> <a href="{r}api/sources.json">sources</a></div>
<p>Records licensed <a href="{DATA_LICENSE}">CC BY 4.0</a>. Cellar points from <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>, ODbL. Appellation dates from 27 CFR part 9, public domain. Outlines from Natural Earth. Every field says where it came from.</p>
{fleet.row_html("pinot-noir")}
{fleet.support_html()}
{fleet.maker_html()}
</footer>
</body>
</html>
"""


# ------------------------------------------------------------------ helpers

KIND_ONE = {"variety": "the vine", "region": "region", "vineyard": "vineyard", "producer": "cellar", "clone": "clone",
            "practice": "practice", "pairing": "at the table", "person": "person", "org": "organization",
            "event": "event", "term": "word", "art": "picture", "story": "story"}
KIND_ARTICLE = {"variety": "the vine", "region": "a region", "vineyard": "a vineyard", "producer": "a cellar",
                "clone": "a clone", "practice": "in the vineyard and cellar", "pairing": "at the table",
                "person": "a person", "org": "an organization", "event": "an event", "term": "a word",
                "art": "a picture", "story": "a story"}


def tier_chip(t: dict) -> str:
    tier = (t or {}).get("tier", "")
    if not tier:
        return ""
    lab = {"cited": "Cited", "harvested": "Harvested", "tradition": "Tradition", "inference": "Inference", "field": "Field"}.get(tier, tier)
    src = (t or {}).get("source", "")
    note = (t or {}).get("note", "")
    return f'<span class="chip tier-{E(tier)}" title="{E((src + " — " if src else "") + note)}">{E(lab)}{(" · " + E(src[2:])) if src else ""}</span>'


def marks(text: str) -> str:
    """Escape, then render *Tradition holds —* / *Inference —* as quiet italics (one line, no paragraphs)."""
    return re.sub(r"\*([^*]+)\*", r'<mark class="tier">\1</mark>', E(text or ""))


def prose(text: str) -> str:
    """Paragraphs. **bold** is bold; a single *phrase* is a provenance mark — *Tradition
    holds —* and *Inference —* — and renders as quiet italics."""
    out = []
    for para in re.split(r"\n\s*\n", (text or "").strip()):
        p = E(para.strip())
        p = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", p)
        p = re.sub(r"\*([^*]+)\*", r'<mark class="tier">\1</mark>', p)
        out.append(f"<p>{p}</p>")
    return "".join(out)


def name_link(r: dict, depth: int) -> str:
    return f'<a href="{rel(depth)}{url_of(r)}index.html">{E(r["names"]["name"])}</a>'


def group_key(r: dict, key: str):
    node = r
    for part in key.split("."):
        node = (node or {}).get(part) if isinstance(node, dict) else None
    if key == "facets.letter":
        return (r["names"]["name"][:1] or "?").upper()
    if isinstance(node, list):
        return node[0] if node else None
    return node


GROUP_LABEL = dict(COUNTRY_NAME)
GROUP_LABEL.update({
    "—": "Elsewhere", "unknown": "Not tagged", "world": "Everywhere it grows",
    "black": "Black-skinned", "grey": "Grey", "white": "White", "red-fleshed": "Red-fleshed",
    "Dijon": "Dijon, by number", "Swiss": "Swiss stations", "California": "California field selections",
    "Oregon": "Oregon", "Burgundy field selection": "Burgundy, by cutting", "Champagne": "Champagne", "unknown": "Origin unclear",
    "vineyard": "In the vineyard", "cellar": "In the cellar", "press": "At the press", "ferment": "In the fermenter",
    "ageing": "In barrel", "bottling": "At bottling", "farming": "Farming", "planting": "Planting",
    "essay": "Essays", "map": "Maps explained", "chart": "Charts", "resources": "Where it came from",
    "label": "Labels", "poster": "Posters", "photograph": "Photographs", "painting": "Paintings", "print": "Prints",
    "sign": "Signs", "nursery": "Nurseries", "association": "Associations", "appellation": "Appellation bodies",
    "archive": "Archives", "school": "Schools",
    "main": "Mains", "side": "Sides", "cheese": "Cheese", "sweet": "Sweet", "snack": "Snacks",
    "condiment": "Condiments and fuel", "fish": "Fish", "bird": "Birds", "fungus": "Fungi",
    "grower": "Growers", "winemaker": "Winemakers", "owner": "Owners", "nurseryman": "Nurserymen",
    "scientist": "Scientists", "writer": "Writers", "critic": "Critics", "importer": "Importers",
    "sommelier": "Sommeliers", "cooper": "Coopers", "butcher": "Butchers", "pitmaster": "Pitmasters"})


def directory_sections(recs: list[dict], types: dict, depth: int, limit: int | None = None) -> str:
    out = []
    for t in types["entries"]:
        rs = [r for r in recs if r["type"] == t["key"]]
        if not rs:
            continue
        groups: dict = {}
        for r in rs:
            g = group_key(r, t["group_by"]) or "—"
            groups.setdefault(g, []).append(r)
        lis = []
        for g, members in sorted(groups.items(), key=lambda kv: (kv[0] == "—", str(kv[0]))):
            members.sort(key=lambda r: (r["names"].get("sort") or r["names"]["name"]).lower())
            if len(groups) > 1:
                lis.append(f'<li><b>{E(GROUP_LABEL.get(g, str(g)))}</b> <span class="count">({len(members)})</span></li>')
            for r in (members if limit is None else members[:limit]):
                lis.append(f'<li class="{"sub" if len(groups) > 1 else ""}">{name_link(r, depth)}</li>')
            if limit is not None and len(members) > limit:
                lis.append(f'<li class="sub"><a href="{rel(depth)}{DIR_OF[t["key"]]}/index.html">… all {len(members)}</a></li>')
        out.append(f'<section><h2><a href="{rel(depth)}{DIR_OF[t["key"]]}/index.html">{E(t["name"])}</a> <span class="count">({len(rs)})</span></h2><p class="mute" style="margin:.1rem 0 .4rem;font-size:.9rem">{E(t["blurb"])}</p><ul>{"".join(lis)}</ul></section>')
    return f'<div class="dir">{"".join(out)}</div>'


# ------------------------------------------------------------------ the map

def map_svg(places: list[dict], recs_by_id: dict, depth: int, width=760) -> str:
    """The world in Equal Earth with every cellar on it — drawn by pages.world_map_svg,
    which the map page uses too, so both are the same picture at two sizes."""
    return pages.world_map_svg(places, width, depth)


# ------------------------------------------------------------------ pages

def node_jsonld(r: dict) -> list:
    url = f"{SITE_URL}/{url_of(r)}"
    base = {"@context": "https://schema.org", "url": url, "name": r["names"]["name"], "description": r["blurb"], "inLanguage": "en",
            "isPartOf": {"@type": "Dataset", "name": SITE_NAME, "url": SITE_URL + "/"}, "license": DATA_LICENSE, "dateModified": r["updated"]}
    if r.get("names", {}).get("aliases"):
        base["alternateName"] = r["names"]["aliases"]
    if r["type"] in ("producer", "vineyard"):
        a = r.get("address") or {}
        g = r.get("geo") or {}
        base.update({"@type": "Winery" if r["type"] == "producer" else "LandmarksOrHistoricalBuildings"})
        if a:
            base["address"] = {"@type": "PostalAddress", "streetAddress": a.get("street", ""), "addressLocality": a.get("city", ""), "addressRegion": a.get("state", ""), "postalCode": a.get("postcode", ""), "addressCountry": a.get("country", "")}
        if g:
            base["geo"] = {"@type": "GeoCoordinates", "latitude": g["lat"], "longitude": g["lon"]}
        if r.get("links"):
            base["sameAs"] = [l["url"] for l in r["links"]]
    elif r["type"] == "person":
        base.update({"@type": "Person"})
        if r.get("links"):
            base["sameAs"] = [l["url"] for l in r["links"]]
    elif r["type"] == "org":
        base.update({"@type": "Organization"})
        if r.get("links"):
            base["sameAs"] = [l["url"] for l in r["links"]]
    elif r["type"] == "event":
        base.update({"@type": "Event", "eventSchedule": (r.get("facets") or {}).get("when", "")})
        g = r.get("geo") or {}
        if g:
            base["location"] = {"@type": "Place", "geo": {"@type": "GeoCoordinates", "latitude": g["lat"], "longitude": g["lon"]}}
    elif r["type"] == "region":
        base.update({"@type": "AdministrativeArea"})
        g = r.get("geo") or {}
        if g:
            base["geo"] = {"@type": "GeoCoordinates", "latitude": g["lat"], "longitude": g["lon"]}
    elif r["type"] == "term":
        base.update({"@type": "DefinedTerm", "inDefinedTermSet": f"{SITE_URL}/words/"})
    else:
        base.update({"@type": "DefinedTerm", "inDefinedTermSet": f"{SITE_URL}/{DIR_OF[r['type']]}/"})
    out = [base, {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": SITE_NAME, "item": SITE_URL + "/"},
        {"@type": "ListItem", "position": 2, "name": DIR_OF[r["type"]].replace("-", " ").title(), "item": f"{SITE_URL}/{DIR_OF[r['type']]}/"},
        {"@type": "ListItem", "position": 3, "name": r["names"]["name"], "item": url}]}]
    # a recipe a reader may actually cook is worth saying so in the machine layer
    for i, rc in enumerate(r.get("recipes", []), 1):
        lic = (rc.get("license") or "").strip()
        rec_ld = {"@context": "https://schema.org", "@type": "Recipe", "name": rc.get("title", r["names"]["name"]),
                  "url": f"{url}#recipe-{i}", "isPartOf": {"@type": "WebPage", "@id": url},
                  "recipeCuisine": "California, Central Coast", "inLanguage": "en"}
        if rc.get("ingredients"):
            rec_ld["recipeIngredient"] = rc["ingredients"]
        if rc.get("text"):
            steps = [x.strip() for x in re.split(r"(?<=[.;])\s{1,}(?=[A-Z])", rc["text"]) if len(x.strip()) > 12]
            rec_ld["recipeInstructions"] = ([{"@type": "HowToStep", "text": x} for x in steps] if len(steps) > 1
                                            else rc["text"])
        if rc.get("author") or rc.get("book"):
            rec_ld["author"] = {"@type": "Person" if rc.get("author") else "Organization", "name": rc.get("author") or rc.get("book")}
        if rc.get("book"):
            rec_ld["isBasedOn"] = {"@type": "Book", "name": rc["book"], **({"datePublished": str(rc["year"])} if rc.get("year") else {})}
        if rc.get("year"):
            rec_ld["datePublished"] = str(rc["year"])
        if rc.get("url"):
            rec_ld["sameAs"] = rc["url"]
        if lic:
            rec_ld["license"] = ("https://creativecommons.org/licenses/by-sa/4.0/" if "by-sa" in lic.lower()
                                 else "https://creativecommons.org/publicdomain/mark/1.0/" if "public domain" in lic.lower() else lic)
        if rc.get("yield"):
            rec_ld["recipeYield"] = rc["yield"]
        if (r.get("facets") or {}).get("course"):
            rec_ld["recipeCategory"] = r["facets"]["course"]
        out.append(rec_ld)
    for im in r.get("images", []):
        out.append({"@context": "https://schema.org", "@type": "ImageObject", "contentUrl": f"{SITE_URL}/images/{im['file']}", "license": im.get("license_url") or im.get("license", ""),
                    "acquireLicensePage": im.get("page_url", ""), "creator": {"@type": "Person", "name": im.get("author", "")}, "creditText": im.get("author", ""), "name": r["names"]["name"], "description": im.get("alt", "")})
    return out


def kin_block(r: dict, by_id: dict, depth: int) -> str:
    cards = []
    # the neighbour's own sentence back, when it has one — both directions of a relation on one card
    back_by = {k["from"]: k["as"] for k in r.get("kin_in", [])}
    for k in r.get("kin_out", []):
        t = by_id.get(k["to"])
        if not t:
            continue
        reply = back_by.get(k["to"])
        cards.append(f'<a class="card" href="{rel(depth)}{url_of(t)}index.html"><small>{E(KIND_ONE.get(t["type"], t["type"]))}</small><b>{E(t["names"]["name"])}</b><span>{E(k["as"])}</span>'
                     + (f'<span class="mute" style="font-size:.82rem;font-style:italic;margin-top:.45rem">and of this page it says: {E(reply)}</span>' if reply else "") + '</a>')
    seen = {k["to"] for k in r.get("kin_out", [])}
    back = []
    for k in r.get("kin_in", []):
        if k["from"] in seen:
            continue
        t = by_id.get(k["from"])
        if not t:
            continue
        back.append(f'<a class="card" href="{rel(depth)}{url_of(t)}index.html"><small>{E(KIND_ONE.get(t["type"], t["type"]))} · says of this page</small><b>{E(t["names"]["name"])}</b><span>{E(k["as"])}</span></a>')
    out = ""
    if cards:
        out += f'<h2>Its kin</h2><div class="kin">{"".join(cards)}</div>'
    if back:
        out += f'<h2>Who points back</h2><div class="kin">{"".join(back)}</div>'
    return out


def node_page(r: dict, by_id: dict, sources: dict) -> str:
    n = r["names"]
    depth = 2
    et = r.get("etymology") or {}
    f = r.get("facets") or {}
    kind = {"style": "a style", "sauce": "a sauce", "dish": "a dish", "pit": "the pit", "place": "a place", "person": "a person", "org": "an organization",
            "event": "an event", "term": "a word", "art": "pig art", "story": "a story"}.get(r["type"], r["type"])
    head = f'<h1><span class="kind">{E(kind)}' + (f' · {E(f["state"])}' if f.get("state") and f["state"] != "both" else "") + f'</span>{E(n["name"])}</h1>'
    if n.get("aliases"):
        head += f'<p class="mute" style="margin:.1rem 0">also: {E(" · ".join(n["aliases"]))}</p>'
    if n.get("said"):
        head += f'<p class="said">{E(n["said"])}</p>'
    hero = ""
    if r.get("primary_image"):
        im = r["primary_image"]
        hero = (f'<figure class="hero-shot"><img src="{img_src(im, depth)}" alt="{E(im.get("alt", n["name"]))}" loading="eager">'
                f'<figcaption>{E(im.get("alt", ""))} — {E(im.get("author", ""))}, '
                f'<a href="{E(im.get("page_url", "#"))}" rel="noopener">{E(im.get("license", ""))}</a></figcaption></figure>')
    elif r["type"] == "variety":
        hero = (f'<figure class="hero-draw">{pages.family_svg(760)}'
                f'<figcaption>One vine, its colour mutations, and the children it had by Gouais blanc.</figcaption></figure>')
    elif r.get("geo") and r["type"] in ("producer", "vineyard", "region", "event", "org", "pairing"):
        g = r["geo"]
        span = {"region": 240.0, "org": 160.0, "pairing": 160.0}.get(r["type"], 90.0)
        others = [{"lat": (o.get("geo") or {}).get("lat"), "lon": (o.get("geo") or {}).get("lon"), "name": o["names"]["name"]}
                  for o in by_id.values() if o["id"] != r["id"] and o.get("geo")]
        hero = (f'<figure class="hero-draw">{viz.locator_svg(g["lat"], g["lon"], others, w=760, span_km=span, label=n["name"])}'
                f'<figcaption>{E(n["name"])}, and what else this directory knows within {span:.0f} km.</figcaption></figure>')
    elif r["type"] == "term" and (r.get("etymology") or {}).get("root"):
        hero = (f'<figure class="hero-word"><b>{E(n["name"])}</b>'
                f'<span>{E((r["etymology"]["root"])[:150])}</span></figure>')
    body = head + hero
    body += f'<div class="prose"><p class="lede">{E(r["text"]["what"])}</p></div>'
    if et.get("root"):
        body += f'<div class="etym"><b>Root.</b> {marks(et["root"])}' + (f'<br><b>First seen.</b> {marks(et["first_attested"])}' if et.get("first_attested") else "") + (f'<br>{marks(et["note"])}' if et.get("note") else "") + f' {tier_chip({"tier": et.get("tier", ""), "source": et.get("source", "")})}</div>'
    if r.get("tag_facts"):
        body += '<div class="tagrow">' + "".join(
            f'<a class="tg {E(t.get("group", ""))}" href="{rel(depth)}near/index.html" title="{E(t.get("evidence", ""))}">{E(t.get("icon", ""))} {E(t.get("label", t["key"]))}</a>' for t in r["tag_facts"]) + "</div>"
    if r.get("recognition_facts"):
        body += '<div class="acc"><b>Written down by</b> ' + " · ".join(
            (f'<a href="{E(x["url"])}" rel="noopener">{E(x.get("label", x["key"]))}</a>' if x.get("url") else E(x.get("label", x["key"])))
            + (f' ({E(str(x["year"]))})' if x.get("year") else "") for x in r["recognition_facts"]) + "</div>"
    if r["type"] in ("producer", "vineyard"):
        row = PLACE_DAYS.get(r["id"])
        hrs = r.get("hours") or {}
        if row and any(v != "unknown" for v in row.values()):
            src = hrs.get("source") or ("s:osm" if not hrs else "")
            body += ('<h2>When the door opens</h2><div class="whenbox">'
                     + viz.day_strip(row)
                     + (f'<p class="hrs">{E(hrs["text"])}</p>' if hrs.get("text") else "")
                     + ('<p class="hrs sold">Closes early once the day&#8217;s pours run out.</p>' if hrs.get("sold_out") else "")
                     + f'<p class="mute" style="font-size:.82rem">{viz.day_key()}'
                     + (f' · {tier_chip({"tier": hrs.get("tier", "cited"), "source": src})}' if src else "")
                     + (f' · checked {E(hrs["checked"])}' if hrs.get("checked") else "")
                     + '</p></div>')
        else:
            body += ('<h2>When the door opens</h2><p class="mute">Nobody has published this one\'s days where this project could read them. '
                     'That is a gap here, not a locked door — write ahead, and see '
                     '<a href="../../visit/index.html">the finder</a> for the cellars that do publish.</p>')
    for key, title in (("story", "The story"), ("how", "How it is done"), ("today", "Today"), ("notes", "Notes")):
        if r["text"].get(key):
            body += f'<h2>{title} {tier_chip(r["tiers"].get(f"text.{key}"))}</h2><div class="prose">{prose(r["text"][key])}</div>'
    for i, sec in enumerate(r.get("sections") or []):
        body += f'<h2 class="sect">{E(sec["h"])}</h2><div class="prose">{prose(sec["text"])}</div>'
        idx = sec.get("images") or []
        if idx:
            body += '<div class="gal2">' + "".join(
                f'<figure><img src="{img_src(r["images"][j], depth)}" alt="{E(r["images"][j].get("alt", ""))}" loading="lazy">'
                f'<figcaption>{E(r["images"][j].get("alt", ""))} — {E(r["images"][j].get("author", ""))}, <a href="{E(r["images"][j].get("page_url", "#"))}">{E(r["images"][j].get("license", ""))}</a></figcaption></figure>'
                for j in idx if j < len(r.get("images", []))) + "</div>"
    # facts table
    rows = []
    if f:
        for k, v in f.items():
            if k in ("letter",):
                continue
            vv = ", ".join(map(str, v)) if isinstance(v, list) else str(v)
            vv = E(vv)
            rows.append(f"<tr><th>{E(k.replace('_', ' '))}</th><td>{vv}</td></tr>")
    rows.append(f"<tr><th>region</th><td>{E(', '.join(t.get('name', t['key']) for t in r['region_terms']))}</td></tr>")
    if r.get("address"):
        a = r["address"]
        rows.append(f"<tr><th>address</th><td>{E(', '.join(x for x in (a.get('street'), a.get('city'), a.get('state'), a.get('postcode')) if x))}{(' · ' + E(a['county']) + ' County') if a.get('county') else ''} {tier_chip(r['tiers'].get('address'))}</td></tr>")
    if r.get("geo"):
        g = r["geo"]
        rows.append(f'<tr><th>where</th><td>{g["lat"]:.4f}, {g["lon"]:.4f} ({E(g.get("precision", ""))}) · <a href="https://www.openstreetmap.org/?mlat={g["lat"]}&mlon={g["lon"]}#map=15/{g["lat"]}/{g["lon"]}">OpenStreetMap</a> · <a href="geo:{g["lat"]},{g["lon"]}">open in maps</a> {tier_chip(r["tiers"].get("geo"))}</td></tr>')
    if r.get("links"):
        rows.append("<tr><th>links</th><td>" + " · ".join(f'<a href="{E(l["url"])}" rel="noopener">{E(l["label"])}</a>' for l in r["links"]) + "</td></tr>")
    rows.append(f"<tr><th>confidence</th><td>{E(r['confidence'])}{' · needs verification' if r.get('needs_verification') else ''} · updated {E(r['updated'])}</td></tr>")
    body += f"<h2>Facts</h2><table>{''.join(rows)}</table>"
    if r.get("measures"):
        mrows = []
        for m in r["measures"]:
            src = sources.get(m["source"], {})
            val = f'{m.get("value")}' + (f' {E(m["unit"])}' if m.get("unit") else "")
            cite = f'<a href="{E(m["url"])}" rel="noopener">{E(src.get("title", m["source"]))}</a>' if m.get("url") else E(src.get("title", m["source"]))
            note = f'<br><span class="mute" style="font-size:.85rem">{E(m["note"])}</span>' if m.get("note") else ""
            year = f' · {E(str(m["year"]))}' if m.get("year") else ""
            mrows.append(f'<tr><th>{E(m.get("label") or m["key"])}{year}</th>'
                         f'<td>{val} <span class="mute">— {cite}</span>{note}</td></tr>')
        body += ('<h2>Numbers somebody published</h2><table>' + "".join(mrows) + "</table>"
                 '<p class="mute" style="font-size:.85rem">Nothing in this table is estimated here. '
                 'Where a figure is missing it is missing, and the row is not written.</p>')
    if r.get("recipes"):
        body += f'<h2>Recipes you may use</h2><p class="mute">Public-domain cookbooks are printed here in full, spelling and all. Where a recipe is still in copyright, the page gives the ingredients — a list of what goes in is a fact — and links to the rest.</p>'
        for rc in r["recipes"]:
            lic = rc.get("license", "")
            head = f'<h3>{E(rc["title"])}</h3><div class="src">' + " · ".join(filter(None, [
                E(rc.get("author", "")), E(rc.get("book", "")), E(str(rc.get("year", ""))), (f'p. {E(str(rc["page"]))}' if rc.get("page") else ""),
                (f'<a href="{E(rc["url"])}" rel="noopener">source</a>' if rc.get("url") else ""), E(lic)])) + "</div>"
            inner = ""
            if rc.get("ingredients"):
                inner += "<ul>" + "".join(f"<li>{E(x)}</li>" for x in rc["ingredients"]) + "</ul>"
            if rc.get("text"):
                inner += f'<div class="txt">{E(rc["text"])}</div>'
            if rc.get("yield"):
                inner += f'<p class="src">Makes {E(rc["yield"])}.</p>'
            if rc.get("note"):
                inner += f'<p class="src">{E(rc["note"])}</p>'
            body += f'<div class="recipe">{head}{inner}</div>'
    if r.get("confusable_with"):
        body += "<h2>Not to be confused with</h2><ul>" + "".join(f'<li><b>{name_link(by_id[c["id"]], depth) if c["id"] in by_id else E(c["id"])}</b> — {E(c["tell"])}</li>' for c in r["confusable_with"]) + "</ul>"
    if r["type"] in ("producer", "vineyard", "region", "org", "event") and r.get("geo"):
        g = r["geo"]
        others = []
        for o in by_id.values():
            if o["id"] == r["id"] or not o.get("geo") or o["type"] not in ("producer", "vineyard", "region"):
                continue
            dx = (o["geo"]["lon"] - g["lon"]) * math.cos(math.radians(g["lat"])) * 111.0
            dy = (o["geo"]["lat"] - g["lat"]) * 111.0
            others.append((round((dx * dx + dy * dy) ** 0.5, 1), o))
        others.sort(key=lambda x: x[0])
        near = [x for x in others if x[0] < 400][:6]
        if near:
            body += ('<h2>Near here</h2><p class="mute">Straight-line kilometres; the road is always longer. '
                     f'<a href="{rel(depth)}visit/index.html">The finder</a> sorts every cellar on the map from wherever you are.</p><ul>'
                     + "".join(f'<li><b>{d:g} km</b> — {name_link(o, depth)}'
                               + (f' <span class="mute">{E(KIND_ONE.get(o["type"], ""))}</span>')
                               + ("".join(f' <span class="chip">{E(t.get("icon", ""))} {E(t.get("label", ""))}</span>' for t in o.get("tag_facts", [])[:3]))
                               + "</li>" for d, o in near) + "</ul>")
    body += kin_block(r, by_id, depth)
    if len(r.get("images", [])) > 1:
        body += '<h2>Pictures</h2><div class="gallery">' + "".join(
            f'<figure><img src="{img_src(im, depth)}" alt="{E(im.get("alt", ""))}" loading="lazy"><figcaption>{E(im.get("author", ""))} · <a href="{E(im.get("page_url", "#"))}">{E(im.get("license", ""))}</a></figcaption></figure>' for im in r["images"]) + "</div>"
    if r.get("source_list"):
        body += "<h2>Sources</h2><ul>" + "".join(
            f'<li>{E(s.get("title", s["id"]))}' + (f' — {E(s["author"])}' if s.get("author") else "") + (f', {E(str(s["year"]))}' if s.get("year") else "") + (f' · <a href="{E(s["url"])}" rel="noopener">link</a>' if s.get("url") else "") + "</li>" for s in r["source_list"]) + "</ul>"
    body += ('<p class="legend">Where it came from: <span class="chip tier-cited">Cited</span> a source we name · <span class="chip tier-harvested">Harvested</span> pulled from an open dataset · '
             '<span class="chip tier-tradition">Tradition</span> what the tradition says, hedged · <span class="chip tier-inference">Inference</span> this project\'s reasoning · <span class="chip tier-field">Field</span> somebody stood there. '
             f'<a href="{rel(depth)}api/{E(r["type"])}/{E(r["id"])}.json">This record as JSON</a>.</p>')
    og = f"{SITE_URL}/images/{r['primary_image']['file']}" if r.get("primary_image") else ""
    return page(f"{n['name']} — {SITE_NAME}", body, depth, r["blurb"], node_jsonld(r), f"{SITE_URL}/{url_of(r)}", og_image=og,
                alt_json=f"{SITE_URL}/api/{r['type']}/{r['id']}.json", og_alt=f'{n["name"]} — {r["blurb"][:110]}',
                og_type="article" if r["type"] in ("story", "art") else "website",
                card=f'{r["type"]}__{r["id"]}', share_title=n["name"])


def art_index(t: dict, recs: list[dict]) -> str:
    """The art index is a wall of pictures, not a list of names — the pictures are the point."""
    rs = [r for r in recs if r["type"] == "art"]
    depth = 1
    body = (f'<h1><span class="kind">{E(SITE_NAME)}</span>{E(t["name"])} <span class="count">({len(rs)})</span></h1>'
            f'<p class="lede">{E(t["blurb"])} Every picture here is free to use; the licence and the photographer are under each one, '
            'and the page it came from is a click away.</p>')
    shots = sum(len(r.get("images", [])) for r in rs)
    if shots:
        body += f'<p class="mute">{shots} pictures across {len(rs)} genres.</p>'
    for r in sorted(rs, key=lambda r: r["names"]["name"].lower()):
        body += (f'<h2><a href="{rel(depth)}{url_of(r)}index.html" style="text-decoration:none">{E(r["names"]["name"])}</a></h2>'
                 f'<p>{E(r["blurb"])} <a href="{rel(depth)}{url_of(r)}index.html">the whole piece →</a></p>')
        ims = r.get("images", [])[:6]
        if ims:
            body += '<div class="gal2">' + "".join(
                f'<figure><a href="{rel(depth)}{url_of(r)}index.html"><img src="{img_src(im, depth)}" alt="{E(im.get("alt", ""))}" loading="lazy"></a>'
                f'<figcaption>{E((im.get("alt") or "")[:90])} — {E(im.get("author", ""))}, <a href="{E(im.get("page_url", "#"))}" rel="noopener">{E(im.get("license", ""))}</a></figcaption></figure>'
                for im in ims) + "</div>"
        else:
            body += '<p class="mute">No picture on file yet for this one.</p>'
    jl = [{"@context": "https://schema.org", "@type": "ImageGallery", "name": f"{t['name']} — {SITE_NAME}", "url": f"{SITE_URL}/art/"}]
    return page(f"{t['name']} — {SITE_NAME}", body, depth, t["blurb"], jl, f"{SITE_URL}/art/", card="art")


def type_index(t: dict, recs: list[dict], by_id: dict) -> str:
    rs = [r for r in recs if r["type"] == t["key"]]
    depth = 1
    groups: dict = {}
    for r in rs:
        groups.setdefault(group_key(r, t["group_by"]) or "—", []).append(r)
    body = f'<h1><span class="kind">{E(SITE_NAME)}</span>{E(t["name"])} <span class="count">({len(rs)})</span></h1><p class="lede">{E(t["blurb"])}</p>'
    for g, members in sorted(groups.items(), key=lambda kv: (kv[0] == "—", str(kv[0]))):
        members.sort(key=lambda r: (r["names"].get("sort") or r["names"]["name"]).lower())
        if len(groups) > 1:
            body += f'<h2>{E(GROUP_LABEL.get(g, str(g)))} <span class="count">({len(members)})</span></h2>'
        body += '<div class="cards">' + "".join(
            f'<div class="card">' + (f'<a href="{rel(depth)}{url_of(r)}index.html"><img class="thumb" src="{rel(depth)}cards/{E(r["type"])}__{E(r["id"])}.jpg" alt="" loading="lazy"></a>'
                                      if (CARDS_DIR / f'{r["type"]}__{r["id"]}.jpg').exists() else "") +
            f'<a class="t" href="{rel(depth)}{url_of(r)}index.html">{E(r["names"]["name"])}</a>' + (f'<p class="mute" style="font-size:.8rem">{E(", ".join(r["names"]["aliases"][:3]))}</p>' if r["names"].get("aliases") else "") +
            f'<p>{E(r["blurb"])}</p></div>' for r in members) + "</div>"
    if t["key"] == "term":
        others = [r for r in recs if r["type"] != "term" and (r.get("etymology") or {}).get("root")]
        if others:
            body += '<h2>Other pages with a root</h2><ul>' + "".join(f'<li>{name_link(r, depth)} <span class="mute">— {E((r["etymology"]["root"])[:120])}</span></li>' for r in sorted(others, key=lambda r: r["names"]["name"].lower())) + "</ul>"
    jl = [{"@context": "https://schema.org", "@type": "DefinedTermSet" if t["key"] != "place" else "ItemList", "name": f"{t['name']} — {SITE_NAME}", "url": f"{SITE_URL}/{DIR_OF[t['key']]}/",
           ("hasDefinedTerm" if t["key"] != "place" else "itemListElement"): [{"@type": "DefinedTerm" if t["key"] != "place" else "ListItem", "name": r["names"]["name"], "url": f"{SITE_URL}/{url_of(r)}"} for r in rs]}]
    return page(f"{t['name']} — {SITE_NAME}", body, depth, t["blurb"], jl, f"{SITE_URL}/{DIR_OF[t['key']]}/", card=DIR_OF[t["key"]])


CARDS_DIR = ROOT / "cards"

SHARE_CSS = """
.shareme{margin:2.6rem 0 .4rem;padding:1rem 1.1rem;background:var(--panel);border:1px solid var(--line);border-radius:14px}
.shareme b{display:block;font-size:.95rem;margin-bottom:.55rem}
.shareme .row{display:flex;flex-wrap:wrap;gap:.45rem}
.shareme a,.shareme button{font:inherit;font-size:.87rem;font-family:-apple-system,"Segoe UI",Roboto,sans-serif;padding:.4rem .85rem;border-radius:999px;
  border:1.5px solid var(--line);background:var(--bg);color:var(--ink);cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;gap:.35rem}
.shareme a:hover,.shareme button:hover{border-color:var(--sauce);color:var(--sauce)}
.shareme .said{font-size:.85rem;color:var(--mute);margin-left:.4rem}
.shareme .copy{border-color:var(--sauce);color:#fff;background:var(--sauce)}
.shareme .copy:hover{color:#fff;filter:brightness(1.08)}
"""


def share_row(url: str, title: str) -> str:
    u, t = urllib.parse.quote(url, safe=""), urllib.parse.quote(title)
    links = [
        ("Bluesky", f"https://bsky.app/intent/compose?text={t}%20{u}"),
        ("Mastodon", f"https://mastodonshare.com/?text={t}&url={u}"),
        ("X", f"https://twitter.com/intent/tweet?text={t}&url={u}"),
        ("Facebook", f"https://www.facebook.com/sharer/sharer.php?u={u}"),
        ("Reddit", f"https://www.reddit.com/submit?url={u}&title={t}"),
        ("WhatsApp", f"https://api.whatsapp.com/send?text={t}%20{u}"),
        ("Email", f"mailto:?subject={t}&body={u}"),
    ]
    btns = "".join(f'<a href="{E(href)}" target="_blank" rel="noopener">{E(name)}</a>' for name, href in links)
    return (f'<section class="shareme" data-url="{E(url)}" data-title="{E(title)}">'
            f'<b>Pass it on</b><div class="row">'
            f'<button type="button" class="copy" data-sh="copy">Copy link</button>'
            f'<button type="button" data-sh="native" hidden>Share…</button>{btns}'
            f'<span class="said" aria-live="polite"></span></div></section>'
            '<script>(function(){var s=document.currentScript.previousElementSibling;'
            'var n=s.querySelector(\'[data-sh="native"]\');if(navigator.share)n.hidden=false;'
            's.addEventListener("click",function(e){var b=e.target.closest("[data-sh]");if(!b)return;'
            'var url=s.dataset.url,title=s.dataset.title,said=s.querySelector(".said");'
            'if(b.dataset.sh==="copy"){(navigator.clipboard?navigator.clipboard.writeText(url):Promise.reject())'
            '.then(function(){said.textContent="copied"},function(){said.textContent=url});}'
            'else if(b.dataset.sh==="native"){navigator.share({title:title,url:url}).catch(function(){})}});})();</script>')


PLACE_DAYS: dict = {}
TAGV: dict = {}


def front_page(recs: list[dict], by_id: dict, cellars: dict, types: dict, coverage: dict) -> str:
    depth = 0
    counts = coverage["records"]
    svg = map_svg(cellars["places"], by_id, depth, 640)
    facts = [(len(recs), "records"),
             (counts.get("region", 0), "regions"),
             (cellars["harvested"], "cellars off OpenStreetMap"),
             (sum(len(r.get("kin_out", [])) for r in recs), "kin links"),
             (counts.get("term", 0), "words with roots")]
    body = (f'<div class="hero"><div><h1><span class="kind">a directory of one grape</span>Pinot Country</h1>'
            f'<p class="sub">{E(TAGLINE)}.</p>'
            f'<p>Thin skin, tight bunches, early ripening. It rots in the rain, burns in the heat, mutates '
            f'when nobody is looking, and people keep planting it colder and further out anyway — Burgundy, '
            f'the Ahr, the Willamette, a fog corridor in Sonoma, a valley in Santa Barbara County that runs '
            f'the wrong way, and a schist basin in Otago at 45° south.</p>'
            f'<div class="cta"><a class="btn" href="visit/index.html">📍 Find a cellar near me</a>'
            f'<a class="btn ghost" href="map/index.html">The map</a>'
            f'<a class="btn ghost" href="clones/index.html">The family</a>'
            f'<a class="btn ghost" href="story/tri-tip-over-red-oak/index.html">Tri-tip over red oak</a>'
            f'<a class="btn ghost" href="numbers/index.html">Count it up</a>'
            f'<a class="btn ghost" href="wander.html">🎲 A page at random</a></div></div>'
            f'<div class="mapwrap">{svg}</div></div>'
            '<div class="facts">' + "".join(f'<div class="fact"><div class="n">{n:,}</div><div class="l">{E(l)}</div></div>' for n, l in facts) + "</div>")
    # the long read gets the space it earns
    deep = by_id.get("tri-tip-over-red-oak")
    trav = by_id.get("how-pinot-travelled")
    if deep:
        body += ('<div class="two-up">'
                 f'<div class="pitch"><h2 style="border:0;margin-top:0">{E(deep["names"]["name"])}</h2>'
                 f'<p>{E(deep["blurb"])}</p>'
                 f'<p><a class="btn" href="{url_of(deep)}index.html">Read it →</a></p></div>'
                 + (f'<div class="pitch"><h2 style="border:0;margin-top:0">{E(trav["names"]["name"])}</h2>'
                    f'<p>{E(trav["blurb"])}</p><p><a class="btn ghost" href="{url_of(trav)}index.html">Follow the cuttings →</a></p></div>' if trav else "")
                 + "</div>")
    # regions with the most attention paid to them, by somebody else's count
    drive = sorted([r for r in recs if r["type"] in ("region", "vineyard", "producer") and r.get("acclaim")],
                   key=lambda r: (-r["acclaim"], r["names"]["name"]))[:6]
    if drive:
        body += ('<h2>Written down by somebody else</h2><p class="mute">Ground a named body has already ruled on: an appellation '
                 'established, a boundary drawn in the Federal Register, a World Heritage listing. The count is how many '
                 'different bodies, not our opinion.</p><div class="cards">'
                 + "".join(f'<div class="card">'
                           + (f'<a href="{url_of(r)}index.html"><img class="thumb" src="cards/{E(r["type"])}__{E(r["id"])}.jpg" alt="" loading="lazy"></a>'
                              if (CARDS_DIR / f'{r["type"]}__{r["id"]}.jpg').exists() else "")
                           + f'<a class="t" href="{url_of(r)}index.html">{E(r["names"]["name"])}</a>'
                           f'<p>{E(", ".join(x.get("label", "") for x in r.get("recognition_facts", [])[:3]))}</p></div>' for r in drive)
                 + "</div>")
    body += directory_sections(recs, types, depth, limit=8)
    body += (f'<h2>Reading the marks</h2><p class="mute">Plain prose is cited and the source sits on the page. '
             f'<mark class="tier">Tradition holds —</mark> is what the trade says, hedged. '
             f'<mark class="tier">Inference —</mark> is this project reasoning. It is all JSON as well, under '
             f'<a href="api/index.json">/api/</a>, and what is missing is listed at <a href="coverage/index.html">coverage</a>.</p>')
    jl = [{"@context": "https://schema.org", "@type": "Dataset", "name": SITE_NAME,
           "description": "A structured directory of pinot noir: the vine and its mutations, regions and appellations, named vineyards, cellars, clones, vineyard and cellar practice, people, organizations, events, vocabulary and food — one JSON record per node with per-field provenance.",
           "url": SITE_URL + "/", "license": DATA_LICENSE, "creator": AUTHOR, "publisher": fleet.publisher_ld(), "includedInDataCatalog": fleet.catalog_ld(), "isAccessibleForFree": True,
           "keywords": ["pinot noir", "Burgundy", "Willamette Valley", "Santa Maria Valley", "Central Otago", "clones", "appellation", "AVA", "tri-tip"],
           "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{SITE_URL}/api/nodes.json"},
                            {"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": f"{SITE_URL}/nodes.csv"},
                            {"@type": "DataDownload", "encodingFormat": "application/x-ndjson", "contentUrl": f"{SITE_URL}/nodes.jsonl"}]},
          {"@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME, "url": SITE_URL + "/",
           "potentialAction": {"@type": "SearchAction", "target": f"{SITE_URL}/search/?q={{search_term_string}}", "query-input": "required name=search_term_string"}}]
    return page(f"{SITE_NAME} — {TAGLINE}", body, depth,
                "A directory of pinot noir: the vine, the regions, the vineyards, the cellars, the clones, the practice, the words, and what gets eaten beside it — each with its sources.",
                jl, SITE_URL + "/", card="index", og_alt="Pinot Country: a directory of one grape", share_title=SITE_NAME)


def wander_page(recs: list[dict]) -> str:
    urls = [url_of(r) for r in recs]
    body = ('<h1><span class="kind">🎲</span>Wander</h1><p class="lede">A page at random. If nothing happens, pick from the list.</p>'
            f'<script>(function(){{var u={json.dumps(urls)};location.replace(u[Math.floor(Math.random()*u.length)]+"index.html")}})();</script>'
            '<ul>' + "".join(f'<li><a href="{E(url_of(r))}index.html">{E(r["names"]["name"])}</a></li>' for r in sorted(recs, key=lambda r: r["names"]["name"].lower())) + "</ul>")
    return page(f"Wander — {SITE_NAME}", body, 0, "A page at random.", None, f"{SITE_URL}/wander.html", '<meta name="robots" content="noindex">')


def sources_page(sources: dict) -> str:
    kinds: dict = {}
    for s in sources.values():
        kinds.setdefault(s.get("kind", "other"), []).append(s)
    body = f'<h1><span class="kind">{E(SITE_NAME)}</span>Sources <span class="count">({len(sources)})</span></h1><p class="lede">Every source a record may cite, by id. Cite anything else and the build refuses it.</p>'
    for k in ("book", "wikipedia", "oral-history", "web", "org", "dataset", "article", "film", "other"):
        rows = kinds.get(k)
        if not rows:
            continue
        body += f'<h2>{E(k.replace("-", " ").title())} <span class="count">({len(rows)})</span></h2><ul>' + "".join(
            f'<li><code class="mute" style="font-size:.8rem">{E(s["id"])}</code> {E(s.get("title", ""))}' + (f' — {E(s["author"])}' if s.get("author") else "") + (f', {E(s["publisher"])}' if s.get("publisher") else "") + (f' {E(str(s["year"]))}' if s.get("year") else "") +
            (f' · <a href="{E(s["url"])}" rel="noopener">link</a>' if s.get("url") else "") + (f' <span class="mute">({E(s["license"])})</span>' if s.get("license") else "") + (f'<br><span class="mute" style="font-size:.85rem">{E(s["note"])}</span>' if s.get("note") else "") + "</li>"
            for s in sorted(rows, key=lambda s: s.get("title", ""))) + "</ul>"
    return page(f"Sources — {SITE_NAME}", body, 1, "Every source the records cite.", None, f"{SITE_URL}/sources/", card="sources")


def coverage_page(cov: dict) -> str:
    body = (f'<h1><span class="kind">{E(SITE_NAME)}</span>Coverage</h1><p class="lede">{E(cov["scope"])}</p>'
            '<h2>Records</h2><table>' + "".join(f"<tr><th>{E(DIR_OF[t])}</th><td>{n}</td></tr>" for t, n in cov["records"].items()) + "</table>"
            f'<h2>How records are made</h2><p>{E(cov["how_records_are_made"])}</p>'
            '<h2>Cellars</h2><table>' + "".join(f"<tr><th>{E(k.replace('_', ' '))}</th><td>{E(str(v))}</td></tr>" for k, v in cov["cellars"].items() if k != "osm_query") + "</table>"
            f'<p class="mute" style="font-size:.85rem">Overpass query: <code>{E(cov["cellars"].get("osm_query") or "")}</code></p>'
            f'<h2>Pictures</h2><p>{cov["images"]["count"]} on file. Licences accepted: {E(", ".join(cov["images"]["licences_accepted"]))}.</p>'
            '<h2>The week</h2><table>' + "".join(f"<tr><th>{E(k.replace('_', ' '))}</th><td>{E(str(v))}</td></tr>" for k, v in cov.get("hours", {}).items()) + "</table>"
            '<h2>Gaps</h2><ul>' + "".join(f"<li>{E(x)}</li>" for x in cov["not_yet"]) + "</ul>"
            '<h2>Tiers</h2><table>' + "".join(f"<tr><th>{E(k)}</th><td>{E(v)}</td></tr>" for k, v in cov["tiers"].items()) + "</table>"
            '<p class="mute">The same object as JSON: <a href="../api/coverage.json">api/coverage.json</a>.</p>')
    return page(f"Coverage — {SITE_NAME}", body, 1, "What this directory covers, where its rows come from, and what it does not have yet.", None, f"{SITE_URL}/coverage/", card="coverage")


def search_page(docs: list[dict]) -> str:
    body = f"""
<h1><span class="kind">{E(SITE_NAME)}</span>Search</h1>
<p class="lede">Spätburgunder, blauburgunder, pinot nero — same vine, three spellings. If the search had to stretch to find something, it says so.</p>
<form class="search" role="search" onsubmit="return false"><input id="q" type="search" placeholder="climat · whole cluster · Dundee · saignée · tri-tip…" aria-label="Search" autofocus><button id="go" type="button">Search</button></form>
<p id="tier" class="tierline" aria-live="polite"></p>
<div id="out" class="cards"></div>
<p class="legend" id="how">Runs in your browser over every record: exact → same meaning, other word → near spellings → partial. Nothing leaves the page.</p>
<script src="../vendor/searchcore.js"></script>
<script>
(function(){{
var DOCS={json.dumps(docs, ensure_ascii=False)};
var PATH={json.dumps(PATH_OF)};
var TABLES=null, core=null, index=null, PREP=null;
var byId={{}}; DOCS.forEach(function(d){{byId[d.id]=d}});
var TIER={{exact:"exact match",thesaurus:"same meaning, other word",loose:"near spellings — closest first",partial:"partial matches"}};
function esc(s){{return String(s==null?"":s).replace(/[&<>"]/g,function(c){{return {{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}}[c]}})}}
function build(){{
  core=new SEARCHCORE.SearchCore(TABLES.groups||[],TABLES.words||[]);
  index=new SEARCHCORE.Index(core);
  PREP={{}};
  DOCS.forEach(function(d){{var f={{name:[d.names,3],terms:[d.terms,2],text:[d.text,1]}};index.add(d,f);PREP[d.id]=core.prepareDoc(f)}});
  index.finalize();
}}
function card(d,tier){{
  return '<div class="card"><a class="t" href="../'+PATH[d.type]+'/'+esc(d.id)+'/index.html">'+esc(d.name)+'</a><p class="mute" style="font-size:.78rem;text-transform:uppercase;letter-spacing:.12em">'+esc(d.type)+(d.state?' · '+esc(d.state):'')+'</p><p>'+esc(d.blurb)+'</p><p><span class="chip">'+esc(TIER[tier]||tier)+'</span></p></div>';
}}
function lexical(q){{
  var an=core.analyze(q,index); var rows=[];
  for(var id in PREP){{var r=core.scoreDoc(an,PREP[id]); if(r) rows.push({{id:id,tier:r.tier,score:r.score,coverage:r.coverage}})}}
  var whole=rows.filter(function(r){{return r.coverage>=1}}); var kept=whole.length?whole:rows;
  kept.sort(function(a,b){{return b.score-a.score}}); return kept.slice(0,30);
}}
function render(rows,worst){{
  var out=document.getElementById("out"), t=document.getElementById("tier");
  if(!rows.length){{out.innerHTML="";t.textContent="Nothing here answers to that yet.";return}}
  t.textContent=(TIER[worst]||worst);
  out.innerHTML=rows.map(function(r){{var d=byId[r.id];return d?card(d,r.tier):''}}).join("");
}}
function run(){{
  var q=document.getElementById("q").value.trim(); if(!q){{render([],null);return}}
  var lex=lexical(q); var worst=null;
  lex.forEach(function(r){{if(worst==null||SEARCHCORE.TIER_ORDER.indexOf(r.tier)>SEARCHCORE.TIER_ORDER.indexOf(worst))worst=r.tier}});
  render(lex,worst||"exact");
}}
fetch("tables.json").then(function(r){{return r.json()}}).then(function(t){{TABLES=t;build();
  var u=new URL(location.href); var q0=u.searchParams.get("q"); if(q0){{document.getElementById("q").value=q0;run()}}
}});
document.getElementById("go").addEventListener("click",run);
document.getElementById("q").addEventListener("keydown",function(e){{if(e.key==="Enter"&&!e.isComposing){{e.preventDefault();run()}}}});
document.getElementById("q").addEventListener("input",function(){{if(index)run()}});
}})();
</script>
"""
    return page(f"Search — {SITE_NAME}", body, 1, "Spell it however you spell it; the search will find it.", None, f"{SITE_URL}/search/", card="search")


def manifest() -> str:
    return json.dumps({"name": SITE_NAME, "short_name": "Pinot", "start_url": "./index.html", "display": "standalone", "background_color": "#faf7f1", "theme_color": "#7b2038",
                       "description": TAGLINE, "icons": [{"src": "icon.svg", "sizes": "any", "type": "image/svg+xml"}]}, indent=1)


def icon_svg() -> str:
    """A glass, and the cluster that fills it — drawn, not fetched."""
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            '<rect width="64" height="64" rx="12" fill="#7b2038"/>'
            '<path d="M22 14h20c0 12-4 15-7 17v13h6v4H23v-4h6V31c-3-2-7-5-7-17z" fill="#faf7f1"/>'
            '<circle cx="32" cy="20" r="3.1" fill="#7b2038"/><circle cx="26.5" cy="24" r="3.1" fill="#7b2038"/>'
            '<circle cx="37.5" cy="24" r="3.1" fill="#7b2038"/><circle cx="32" cy="27.5" r="3.1" fill="#7b2038"/></svg>')


def llms_txt(recs: list[dict], cov: dict) -> str:
    lines = [f"# {SITE_NAME}", "",
             f"> A structured directory of pinot noir: the vine and its mutations, regions and appellations, named vineyards, cellars, clones, vineyard and cellar practice, people, organizations, events, vocabulary, and what gets eaten beside it. One JSON record per node; every field carries a provenance tier (cited / harvested / tradition / inference / field); records say what their neighbours are to them in both directions.",
             "", f"Records are CC BY 4.0 ({DATA_LICENSE}). Cellar points are OpenStreetMap, ODbL 1.0 (share-alike). American Viticultural Area dates come from 27 CFR part 9, public domain. Pictures carry their own licences, stated per file. Scope and gaps: {SITE_URL}/api/coverage.json",
             "", "## Data", f"- [All records, JSON]({SITE_URL}/api/nodes.json)", f"- [Directory index, JSON]({SITE_URL}/api/index.json)", f"- [Every cellar, curated + OpenStreetMap]({SITE_URL}/api/cellars.json)",
             f"- [Kin edges]({SITE_URL}/api/kin.json)", f"- [JSONL]({SITE_URL}/nodes.jsonl) · [CSV]({SITE_URL}/nodes.csv)", f"- [Record schema]({SITE_URL}/schema/node.schema.json)",
             f"- [Vocabularies: regions, types, facets]({SITE_URL}/api/vocab/regions.json)", f"- [Sources registry]({SITE_URL}/api/sources.json)", f"- [Full text of every record]({SITE_URL}/llms-full.txt)", ""]
    for t in TYPES:
        rs = sorted([r for r in recs if r["type"] == t], key=lambda r: r["names"]["name"].lower())
        if not rs:
            continue
        lines.append(f"## {DIR_OF[t].title()}")
        for r in rs:
            lines.append(f"- [{r['names']['name']}]({SITE_URL}/{url_of(r)}): {r['blurb']}")
        lines.append("")
    lines += ["## Optional", f"- [Search page]({SITE_URL}/search/)", f"- [World map of every cellar]({SITE_URL}/map/)", f"- [Atom feed]({SITE_URL}/feed.xml)", f"- [Sitemap]({SITE_URL}/sitemap.xml)"]
    return "\n".join(lines) + "\n"


def llms_full(recs: list[dict], sources: dict) -> str:
    out = [f"# {SITE_NAME} — every record, flattened\n"]
    for t in TYPES:
        for r in sorted([r for r in recs if r["type"] == t], key=lambda r: r["names"]["name"].lower()):
            n = r["names"]
            out.append(f"## {n['name']} ({t})\nURL: {SITE_URL}/{url_of(r)}\nJSON: {SITE_URL}/api/{t}/{r['id']}.json\nid: {r['id']}")
            if n.get("aliases"):
                out.append("aliases: " + " · ".join(n["aliases"]))
            if n.get("said"):
                out.append("said: " + n["said"])
            et = r.get("etymology") or {}
            if et.get("root"):
                out.append(f"root: {et['root']}" + (f" · first seen: {et['first_attested']}" if et.get("first_attested") else "") + (f" · {et['note']}" if et.get("note") else ""))
            if r.get("facets"):
                out.append("facets: " + " · ".join(f"{k}={', '.join(map(str, v)) if isinstance(v, list) else v}" for k, v in r["facets"].items()))
            out.append("region: " + ", ".join(t2.get("name", t2["key"]) for t2 in r["region_terms"]))
            for k in ("what", "story", "how", "today", "notes"):
                if r["text"].get(k):
                    out.append(f"{k}: {r['text'][k]}")
            a = r.get("address") or {}
            if a:
                out.append("address: " + ", ".join(x for x in (a.get("street"), a.get("city"), a.get("state"), a.get("postcode")) if x))
            if r.get("geo"):
                out.append(f"geo: {r['geo']['lat']}, {r['geo']['lon']} ({r['geo'].get('precision', '')})")
            for k in r.get("kin_out", []):
                out.append(f"- kin → {k['to']} ({k['type']}): {k['as']}")
            for c in r.get("confusable_with", []):
                out.append(f"- not to be confused with {c['id']}: {c['tell']}")
            for im in r.get("images", []):
                out.append(f"- image: {SITE_URL}/images/{im['file']} · {im.get('license', '')} · {im.get('author', '')} · {im.get('page_url', '')}")
            out.append("sources: " + "; ".join(f"{s} — {sources[s].get('title', '')}" for s in r.get("sources", []) if s in sources))
            out.append(f"provenance default: {r['provenance']['default'].get('tier')} · confidence: {r['confidence']} · needs_verification: {r.get('needs_verification', False)} · updated: {r['updated']}\n")
    return "\n".join(out)


def sitemap(recs: list[dict]) -> str:
    today = time.strftime("%Y-%m-%d")
    urls = [(SITE_URL + "/", max((r["updated"] for r in recs), default=today)), (SITE_URL + "/search/", today),
            (SITE_URL + "/visit/", today), (SITE_URL + "/map/", today), (SITE_URL + "/clones/", today), (SITE_URL + "/numbers/", today),
            (SITE_URL + "/sources/", today), (SITE_URL + "/coverage/", today)] + [(f"{SITE_URL}/{DIR_OF[t]}/", today) for t in TYPES]
    body = []
    for u, d in urls:
        body.append(f"<url><loc>{E(u)}</loc><lastmod>{E(d)}</lastmod></url>")
    for r in recs:
        imgs = "".join(f"<image:image><image:loc>{E(SITE_URL + '/images/' + im['file'])}</image:loc><image:caption>{E(r['names']['name'])}</image:caption>" +
                       (f"<image:license>{E(im['license_url'])}</image:license>" if im.get("license_url") else "") + "</image:image>" for im in r.get("images", []))
        body.append(f"<url><loc>{E(SITE_URL + '/' + url_of(r))}</loc><lastmod>{E(r['updated'])}</lastmod>{imgs}</url>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">' + "".join(body) + "</urlset>\n")


def ai_txt() -> str:
    return (f"# {SITE_NAME} — {SITE_URL}/\n"
            "# Everything here is meant to be read by machines as well as people.\n\n"
            "User-agent: *\nAllow: /\n\n"
            "Content-Signal: search=yes, ai-input=yes, ai-train=yes\n\n"
            f"Corpus: {SITE_URL}/llms.txt\nFull-text: {SITE_URL}/llms-full.txt\n"
            f"Records: {SITE_URL}/api/nodes.json\nCellars: {SITE_URL}/api/cellars.json\n"
            f"Kin edges: {SITE_URL}/api/kin.json\nScope and gaps: {SITE_URL}/api/coverage.json\n"
            f"Schema: {SITE_URL}/schema/node.schema.json\nTabular: {SITE_URL}/nodes.csv · {SITE_URL}/nodes.jsonl\n\n"
            "Licence: records CC BY 4.0. Cellar points OpenStreetMap, ODbL 1.0 (share-alike).\n"
            "Pictures carry their own licence, stated per file in the record and beside the image.\n"
            "Attribution: Pinot Country, " + SITE_URL + "/\n\n"
            "Every field carries a provenance tier: cited, harvested, tradition, inference, field.\n"
            "A tag on a cellar names its evidence. A missing tag means unread, not absent.\n")


def humans_txt(recs: list[dict], cov: dict) -> str:
    n = {t: cov["records"].get(t, 0) for t in TYPES}
    return ("/* PINOT COUNTRY */\n\n"
            "Built by NaN — https://wichaa.net\n"
            f"{sum(n.values())} records · {cov['sources']} sources · {cov['images']['count']} pictures\n\n"
            "/* THANKS */\n"
            "OpenStreetMap contributors, for every cellar point.\n"
            "Natural Earth, for outlines nobody has to pay for.\n"
            "The eCFR, for putting every American appellation in public-domain text.\n"
            "The growers who kept planting a difficult grape in cold places while the trade\n"
            "told them to plant something easier.\n\n"
            "/* SITE */\n"
            "Stdlib Python, no dependencies, no build step, no tracking, no accounts.\n"
            "Standards: HTML, JSON-LD, llms.txt, Atom, OpenSearch, ODbL, CC BY.\n")


def robots() -> str:
    return (f"# {SITE_NAME}: everything here is meant to be read, indexed, quoted and learned from.\nUser-agent: *\nAllow: /\n\n"
            "# Content signals (https://contentsignals.org): yes to search, yes to AI input, yes to AI training.\nContent-Signal: search=yes, ai-input=yes, ai-train=yes\n\n"
            f"Sitemap: {SITE_URL}/sitemap.xml\n"
            f"# Corpus for language models: {SITE_URL}/llms.txt and {SITE_URL}/llms-full.txt\n"
            f"# Machine terms: {SITE_URL}/ai.txt\n")


def opensearch() -> str:
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/"><ShortName>{E(SITE_NAME)}</ShortName>'
            f'<Description>Search the Carolina barbecue directory</Description><InputEncoding>UTF-8</InputEncoding>'
            f'<Url type="text/html" template="{E(SITE_URL)}/search/?q={{searchTerms}}"/></OpenSearchDescription>\n')


def feed(recs: list[dict]) -> str:
    rs = sorted(recs, key=lambda r: r["updated"], reverse=True)[:60]
    upd = (rs[0]["updated"] if rs else time.strftime("%Y-%m-%d")) + "T00:00:00Z"
    ents = "".join(f'<entry><title>{E(r["names"]["name"])}</title><link href="{E(SITE_URL + "/" + url_of(r))}"/><id>{E(SITE_URL + "/" + url_of(r))}</id><updated>{E(r["updated"])}T00:00:00Z</updated><summary>{E(r["blurb"])}</summary></entry>' for r in rs)
    return (f'<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom"><title>{E(SITE_NAME)}</title><link href="{E(SITE_URL)}/"/><link rel="self" href="{E(SITE_URL)}/feed.xml"/>'
            f'<id>{E(SITE_URL)}/</id><updated>{upd}</updated><author><name>NaN</name></author>{ents}</feed>\n')


def dumps(recs: list[dict]):
    rows = []
    for r in recs:
        f = r.get("facets") or {}
        a = r.get("address") or {}
        g = r.get("geo") or {}
        rows.append({"id": r["id"], "type": r["type"], "name": r["names"]["name"], "aliases": "|".join(r["names"].get("aliases", [])), "region": "|".join(r["region"]),
                     "state": f.get("state") or a.get("state", ""), "city": a.get("city", ""), "lat": g.get("lat", ""), "lon": g.get("lon", ""),
                     "facets": json.dumps(f, ensure_ascii=False) if f else "", "what": r["text"]["what"], "root": (r.get("etymology") or {}).get("root", ""),
                     "kin": "|".join(k["to"] for k in r.get("kin_out", [])), "sources": "|".join(r.get("sources", [])), "tier": r["provenance"]["default"].get("tier", ""),
                     "confidence": r["confidence"], "needs_verification": r.get("needs_verification", False), "updated": r["updated"], "url": f"{SITE_URL}/{url_of(r)}"})
    with open(SITE / "nodes.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["id"])
        w.writeheader()
        w.writerows(rows)
    with open(SITE / "nodes.jsonl", "w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps({k: v for k, v in r.items() if k not in ("tiers",)}, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------ main

def main() -> int:
    if not (API / "nodes.json").exists():
        print("run tools/build.py first")
        return 1
    t0 = time.time()
    recs = jload(API / "nodes.json")["nodes"]
    by_id = {r["id"]: r for r in recs}
    sources = {s["id"]: s for s in jload(API / "sources.json")["sources"]}
    cellars = jload(API / "cellars.json")
    global PLACE_DAYS
    PLACE_DAYS = {p["id"]: p.get("days") or {} for p in cellars["places"]}
    types = jload(API / "vocab" / "types.json")
    cov = jload(API / "coverage.json")
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir(parents=True)
    shutil.copytree(API, SITE / "api")
    shutil.copytree(ROOT / "schema", SITE / "schema")
    (SITE / "vendor").mkdir()
    core_js = VENDOR / "searchcore.js"
    if not core_js.exists():
        print("vendor/searchcore.js missing — run search-core/sync.py")
        return 1
    shutil.copy(core_js, SITE / "vendor" / "searchcore.js")
    # Pictures: only the files records name, and never at archive size. A 2 MB scan of a
    # 1944 news photograph is the right thing to keep in data/; it is the wrong thing to
    # send down a phone line. Originals stay put; the published copy is capped at 1600px.
    saved = 0
    for r in recs:
        for im in r.get("images", []):
            src = IMAGES / im["file"]
            if not src.exists():
                continue
            dst = SITE / "images" / im["file"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                from PIL import Image as _Im
                with _Im.open(src) as pic:
                    if max(pic.size) > 1600 or src.stat().st_size > 600_000:
                        pic = pic.convert("RGB")
                        pic.thumbnail((1600, 1600), _Im.LANCZOS)
                        pic.save(dst, "JPEG", quality=84, optimize=True, progressive=True)
                        saved += src.stat().st_size - dst.stat().st_size
                        continue
            except Exception:  # noqa: BLE001
                pass
            shutil.copy(src, dst)
    # pages
    (SITE / "index.html").write_text(front_page(recs, by_id, cellars, types, cov), encoding="utf-8")
    (SITE / "wander.html").write_text(wander_page(recs), encoding="utf-8")
    for t in types["entries"]:
        d = SITE / DIR_OF[t["key"]]
        d.mkdir(exist_ok=True)
        (d / "index.html").write_text(art_index(t, recs) if t["key"] == "art" else type_index(t, recs, by_id), encoding="utf-8")
    for r in recs:
        d = SITE / url_of(r)
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(node_page(r, by_id, sources), encoding="utf-8")
    global TAGV
    TAGV = {e["key"]: e for e in jload(DATA / "vocab" / "tags.json")["entries"]}
    (SITE / "sources").mkdir(exist_ok=True)
    (SITE / "sources" / "index.html").write_text(sources_page(sources), encoding="utf-8")
    (SITE / "coverage").mkdir(exist_ok=True)
    (SITE / "coverage" / "index.html").write_text(coverage_page(cov), encoding="utf-8")
    # the pages that are not a record
    tagvocab = jload(DATA / "vocab" / "tags.json")
    ava = jload(DATA / "harvest" / "ava.json") if (DATA / "harvest" / "ava.json").exists() else {}
    if ava:
        jdump_path = SITE / "api" / "ava.json"
        shutil.copy(DATA / "harvest" / "ava.json", jdump_path)
    for name, html_text in (("map", pages.map_page(page, cellars, recs, SITE_URL)),
                            ("visit", pages.visit_page(page, cellars, recs, tagvocab, SITE_URL)),
                            ("numbers", pages.numbers_page(page, recs, cellars, ava, SITE_URL)),
                            ("clones", pages.clones_page(page, recs, SITE_URL))):
        d = SITE / name
        d.mkdir(exist_ok=True)
        (d / "index.html").write_text(html_text, encoding="utf-8")

    # search: docs + tables (fleet hand thesaurus + this project's mined table), fetched by the search page only
    docs = jload(BUILD / "searchdocs.json")["docs"]
    (SITE / "search").mkdir(exist_ok=True)
    (SITE / "search" / "index.html").write_text(search_page(docs), encoding="utf-8")
    groups = []
    # only this project's mined table: the fleet hand table is Thai/medical and would be noise here
    p = DATA / "search" / "pinot.thesaurus.json"
    if p.exists():
        groups += jload(p).get("groups", [])
    (SITE / "search" / "tables.json").write_text(json.dumps({"groups": groups, "words": []}, ensure_ascii=False), encoding="utf-8")
    # bot layer
    (SITE / "llms.txt").write_text(llms_txt(recs, cov), encoding="utf-8")
    (SITE / "llms-full.txt").write_text(llms_full(recs, sources), encoding="utf-8")
    (SITE / "sitemap.xml").write_text(sitemap(recs), encoding="utf-8")
    (SITE / "robots.txt").write_text(robots(), encoding="utf-8")
    (SITE / "opensearch.xml").write_text(opensearch(), encoding="utf-8")
    (SITE / "feed.xml").write_text(feed(recs), encoding="utf-8")
    (SITE / "manifest.webmanifest").write_text(manifest(), encoding="utf-8")
    if CARDS_DIR.exists():
        shutil.copytree(CARDS_DIR, SITE / "cards")
    (SITE / "humans.txt").write_text(humans_txt(recs, cov), encoding="utf-8")
    fleet.decorate(SITE, "pinot-noir")
    wk = SITE / ".well-known"
    wk.mkdir(exist_ok=True)
    (wk / "ai.txt").write_text(ai_txt(), encoding="utf-8")
    (SITE / "ai.txt").write_text(ai_txt(), encoding="utf-8")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    (SITE / "icon.svg").write_text(icon_svg(), encoding="utf-8")
    dumps(recs)
    n_html = sum(1 for _ in SITE.rglob("*.html"))
    # privacy gate: no host paths in anything published
    leaks = [p for p in SITE.rglob("*") if p.is_file() and p.suffix in (".html", ".json", ".txt", ".xml", ".csv", ".jsonl") and "/Users/" in p.read_text(encoding="utf-8", errors="ignore")]
    if leaks:
        print("REFUSED: host paths in", [str(p.relative_to(SITE)) for p in leaks][:5])
        return 2
    print(f"site: {n_html} pages · {len(recs)} records · {cellars['count']} cellars on the map · "
          f"{saved/1e6:.0f} MB saved on pictures · {SITE} · {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
