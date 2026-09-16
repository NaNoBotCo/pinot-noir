#!/usr/bin/env python3
"""pages.py — the pages that are not a record: the world map, the cellar finder, the
arithmetic, and the vine's family tree.

site.py imports this and hands each function its own `page()` renderer, so every page
here gets the same shell, the same head and the same share row.

  map_page      every cellar this project knows, drawn in Equal Earth
  visit_page    a door you can actually knock on: your position or a town, sorted by distance
  numbers_page  what the corpus adds up to — latitude, AVA years, tagging, the week
  clones_page   the pinot family, and the numbered selections growers order by catalogue
"""
from __future__ import annotations

import html
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import viz          # noqa: E402
import worldmap     # noqa: E402

E = html.escape

CHART_CSS = """
.chart{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:.9rem 1rem;margin:.9rem 0}
.chart svg{width:100%;height:auto;display:block}
.chart h3{margin:.1rem 0 .5rem}
.chart .cap{font-size:.86rem;color:var(--mute);margin:.5rem 0 0}
.tbl-twin{font-size:.88rem}
.tbl-twin th{width:auto}
"""

FIND_CSS = """
.chips{display:flex;flex-wrap:wrap;gap:.4rem;margin:.7rem 0 .3rem}
.chips button{font:inherit;font-size:.85rem;font-family:var(--ui);padding:.3rem .75rem;border-radius:999px;
  border:1.5px solid var(--line);background:var(--panel);color:var(--ink);cursor:pointer}
.chips button[aria-pressed=true]{background:var(--wine);border-color:var(--wine);color:#fff}
.finder{display:flex;gap:.5rem;flex-wrap:wrap;margin:.8rem 0}
.finder input,.finder select{font:inherit;padding:.5rem .7rem;border:2px solid var(--line);border-radius:10px;background:var(--panel);color:var(--ink)}
.finder input{flex:1;min-width:14rem}
.hits{list-style:none;margin:.8rem 0;padding:0}
.hits li{border-bottom:1px solid var(--line);padding:.6rem .1rem;display:flex;gap:.8rem;align-items:baseline;flex-wrap:wrap}
.hits .km{font-family:var(--display);font-weight:700;min-width:5.2rem;color:var(--wine)}
.hits .nm{font-weight:600}
.hits .meta{color:var(--mute);font-size:.88rem}
.hits .tg{font-size:.78rem;border:1px solid var(--line);border-radius:999px;padding:.05rem .5rem;color:var(--mute)}
"""


def esc_js(obj) -> str:
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


# ------------------------------------------------------------------ the world map

def world_map_svg(rows: list, width=940, depth: int = 1) -> str:
    """Every cellar row as a dot on an Equal Earth world map. Curated rows are wine-dark
    and link to their page; harvested OpenStreetMap rows are small and grey."""
    fit = worldmap.fit_world(width)
    world = worldmap.load_world()
    paths = "".join(f'<path class="c" d="{d}"><title>{E(name)}</title></path>' for name, d in worldmap.country_paths(world, fit))
    grat = "".join(f'<path class="g" d="{d}"/>' for d in worldmap.graticule(fit))
    bands = (f'<path class="band" d="{worldmap.band_path(fit, 50)}"/><path class="band" d="{worldmap.band_path(fit, 30)}"/>'
             f'<path class="band" d="{worldmap.band_path(fit, -30)}"/><path class="band" d="{worldmap.band_path(fit, -50)}"/>')
    dots = []
    for p in rows:
        if p.get("lat") is None:
            continue
        x, y = worldmap.project(p["lon"], p["lat"], fit)
        label = E(p["name"]) + (f' · {E(p["city"])}' if p.get("city") else "")
        if p.get("curated"):
            dots.append(f'<a href="{"../" * depth}{p["url"]}index.html"><circle class="p c" cx="{x:.1f}" cy="{y:.1f}" r="4.4">'
                        f'<title>{label}</title></circle></a>')
        else:
            dots.append(f'<circle class="p o" cx="{x:.1f}" cy="{y:.1f}" r="1.9"><title>{label}</title></circle>')
    style = ("<style>.c{fill:var(--land);stroke:var(--landline);stroke-width:.7}"
             ".g{fill:none;stroke:var(--line);stroke-width:.5;opacity:.7}"
             ".band{fill:none;stroke:var(--gold);stroke-width:1;stroke-dasharray:5 5;opacity:.65}"
             ".p.c{fill:var(--wine);stroke:var(--panel);stroke-width:1}.p.o{fill:var(--mute);opacity:.62}</style>")
    return (f'<svg viewBox="0 0 {width} {fit["h"]:.0f}" xmlns="http://www.w3.org/2000/svg" role="img" '
            f'aria-label="World map in Equal Earth projection with every cellar in this directory as a dot">'
            f'{style}{grat}{paths}{bands}{"".join(dots)}</svg>')


def map_page(page, cellars: dict, recs: list, site_url: str) -> str:
    rows = cellars["places"]
    by_country: dict = {}
    for p in rows:
        by_country.setdefault(p.get("country") or "??", []).append(p)
    harvest = cellars.get("harvest") or {}
    body = (f'<h1><span class="kind">the whole map</span>Where the doors are</h1>'
            f'<p class="lede">{cellars["curated"]} cellars and vineyards written up here, plus {cellars["harvested"]} more that '
            f'OpenStreetMap knows about inside the regions this project covers, fetched {E((harvest.get("fetched_at") or "")[:10])}. '
            f'The dashed lines mark 30° and 50° in both hemispheres — pinot noir lives between them, and the exceptions are the interesting part.</p>'
            f'<div class="mapwrap">{world_map_svg(rows)}</div>'
            f'<p class="mute">Dark dots have a page here. Grey dots have a name and a position and nothing else yet. '
            f'<a href="../visit/index.html">Find one near you →</a></p>')
    body += '<h2>By country</h2><div class="pl-list">'
    names = {"FR": "France", "US": "United States", "DE": "Germany", "NZ": "New Zealand", "AU": "Australia",
             "IT": "Italy", "CL": "Chile", "AR": "Argentina", "ZA": "South Africa", "CA": "Canada", "??": "Not tagged"}
    for cc, ps in sorted(by_country.items(), key=lambda kv: -len(kv[1])):
        cur = [p for p in ps if p.get("curated")]
        body += (f'<h3>{E(names.get(cc, cc))} <span class="count">({len(ps)})</span></h3><ul>'
                 + "".join(f'<li><a href="../{p["url"]}index.html"><b>{E(p["name"])}</b></a>'
                           + (f' <span class="mute">{E(p.get("city") or "")}</span>' if p.get("city") else "") + "</li>" for p in sorted(cur, key=lambda p: p["name"].lower()))
                 + (f'<li class="mute">and {len(ps) - len(cur)} more from OpenStreetMap</li>' if len(ps) > len(cur) else "")
                 + "</ul>")
    body += "</div>"
    boxes = harvest.get("boxes") or []
    if boxes:
        empty = [b for b in boxes if not b.get("rows")]
        body += ('<h2>What the harvest found, box by box</h2>'
                 '<table class="tbl-twin"><tr><th>region</th><th>rows</th></tr>'
                 + "".join(f'<tr><th>{E(b["key"])}</th><td>{b.get("rows", 0)}</td></tr>' for b in boxes) + "</table>")
        if empty:
            body += (f'<p class="mute">{len(empty)} of {len(boxes)} boxes came back empty: '
                     + E(", ".join(b["key"] for b in empty))
                     + '. That is a fact about OpenStreetMap tagging on the fetch date, not about the wineries, which are certainly there.</p>')
    body += ('<p class="legend">Cellar points © OpenStreetMap contributors, '
             '<a href="https://opendatacommons.org/licenses/odbl/1-0/">ODbL 1.0</a> — and the table built from them, '
             '<a href="../api/cellars.json">api/cellars.json</a>, goes out under the same licence. '
             'Country outlines: Natural Earth, public domain. Projection: Equal Earth.</p>')
    jl = [{"@context": "https://schema.org", "@type": "Dataset", "name": "Cellars and vineyards — Pinot Country",
           "url": f"{site_url}/map/", "license": "https://opendatacommons.org/licenses/odbl/1-0/",
           "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{site_url}/api/cellars.json"}]}]
    return page("The map — Pinot Country", body, 1,
                "Every cellar and vineyard in this directory on one Equal Earth world map, plus every winery OpenStreetMap knows inside the regions covered.",
                jl, f"{site_url}/map/", card="map")


# ------------------------------------------------------------------ the finder

def visit_page(page, cellars: dict, recs: list, tagvocab: dict, site_url: str) -> str:
    """Somewhere to actually go. The browser does the distance sum; nothing leaves it."""
    tags = {e["key"]: e for e in tagvocab.get("entries", [])}
    rows = []
    for p in cellars["places"]:
        if p.get("lat") is None:
            continue
        rows.append({"id": p["id"], "n": p["name"], "c": p.get("city") or "", "cc": p.get("country") or "",
                     "lat": p["lat"], "lon": p["lon"], "u": p.get("url"), "t": p.get("tags") or [],
                     "d": p.get("days") or {}, "w": p.get("website") or "", "b": (p.get("blurb") or "")[:110],
                     "k": p.get("kind") or "osm", "r": p.get("regions") or []})
    towns: dict = {}
    for r in rows:
        key = (r["c"] or r["cc"]).strip()
        if key:
            towns.setdefault(key, []).append((r["lat"], r["lon"]))
    town_list = sorted([{"n": k, "lat": sum(x for x, _ in v) / len(v), "lon": sum(y for _, y in v) / len(v), "c": len(v)}
                        for k, v in towns.items() if len(v) >= 2], key=lambda t: -t["c"])[:400]
    used = [k for k in tags if any(k in r["t"] for r in rows)]
    known_days = sum(1 for r in rows if any(v != "unknown" for v in r["d"].values()))
    body = (f'<h1><span class="kind">find a door</span>Somewhere to taste it</h1>'
            f'<p class="lede">{len(rows):,} cellars with a position on them. Give the page your position, or type a town, and it sorts '
            f'the lot by how far away they are. The arithmetic happens in your browser and goes nowhere.</p>'
            '<div class="finder">'
            '<button class="btn" type="button" id="here">📍 Use my position</button>'
            '<input id="town" list="towns" placeholder="or type a town — Beaune, Dundee, Santa Maria…" aria-label="Town">'
            '<datalist id="towns">' + "".join(f'<option value="{E(t["n"])}">' for t in town_list) + '</datalist>'
            '<select id="cc" aria-label="Country"><option value="">every country</option>'
            + "".join(f'<option value="{E(c)}">{E(c)}</option>' for c in sorted({r["cc"] for r in rows if r["cc"]})) + '</select>'
            '</div>'
            '<div class="chips" id="chips" role="group" aria-label="Filter">'
            + "".join(f'<button type="button" data-tag="{E(k)}" aria-pressed="false">{E(tags[k].get("icon",""))} {E(tags[k]["label"])}</button>' for k in used)
            + '<button type="button" data-tag="__page" aria-pressed="false">📄 Written up here</button>'
            '<button type="button" data-tag="__open" aria-pressed="false">🗓 Open today</button></div>'
            '<p class="mute" id="say" aria-live="polite"></p><ul class="hits" id="out"></ul>'
            f'<h2>Reading the tags</h2><p class="mute">Every tag names its evidence, and a tag is never inferred from a name or a photograph. '
            f'A cellar with no tags has not been read yet — that is a fact about this project, not about the cellar.</p>'
            '<table class="tbl-twin"><tr><th>tag</th><th>what earns it</th></tr>'
            + "".join(f'<tr><th>{E(tags[k].get("icon",""))} {E(tags[k]["label"])}</th><td>{E(tags[k].get("evidence",""))}</td></tr>' for k in sorted(tags))
            + '</table>'
            f'<h2>The week</h2><p>{known_days} of {len(rows):,} rows name a day either way. {viz.day_key()} '
            'A day nobody published is drawn dashed and never counted as closed — a reader drives on this.</p>')
    body += """
<script>
(function(){
  var ROWS=__ROWS__, TAGS=__TAGS__, TOWNS=__TOWNS__;
  var out=document.getElementById('out'), say=document.getElementById('say'), chips=document.getElementById('chips');
  var on={}, origin=null, DAYS=['Mo','Tu','We','Th','Fr','Sa','Su'];
  var today=DAYS[(new Date().getDay()+6)%7];
  function km(a,b,c,d){var R=6371,p=Math.PI/180,x=(c-a)*p,y=(d-b)*p;
    var s=Math.sin(x/2)*Math.sin(x/2)+Math.cos(a*p)*Math.cos(c*p)*Math.sin(y/2)*Math.sin(y/2);
    return 2*R*Math.asin(Math.sqrt(s));}
  function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
  function strip(d){var o='';DAYS.forEach(function(k){var v=d[k]||'unknown';
    o+='<i class="dd '+v+'" title="'+k+': '+v+'"></i>'});return '<span class="wk">'+o+'</span>'}
  function render(){
    var cc=document.getElementById('cc').value;
    var keys=Object.keys(on).filter(function(k){return on[k]});
    var rows=ROWS.filter(function(r){
      if(cc && r.cc!==cc) return false;
      return keys.every(function(k){
        if(k==='__page') return !!r.u;
        if(k==='__open') return r.d[today]==='open';
        return r.t.indexOf(k)>=0;
      });
    });
    if(origin){rows.forEach(function(r){r._k=km(origin[0],origin[1],r.lat,r.lon)});
      rows.sort(function(a,b){return a._k-b._k})}
    else rows.sort(function(a,b){return a.n.localeCompare(b.n)});
    say.textContent=rows.length+' of '+ROWS.length+' match'+(origin?', nearest first':', alphabetical — give the page a position to sort by distance')+'.';
    out.innerHTML=rows.slice(0,120).map(function(r){
      var nm=r.u?'<a href="../'+r.u+'index.html">'+esc(r.n)+'</a>':esc(r.n);
      var tg=r.t.map(function(k){return '<span class="tg">'+esc((TAGS[k]||{}).label||k)+'</span>'}).join(' ');
      var web=r.w?' <a href="'+esc(r.w)+'" rel="noopener nofollow">site</a>':'';
      var any=DAYS.some(function(k){return r.d[k]&&r.d[k]!=='unknown'});
      return '<li><span class="km">'+(r._k!=null?(r._k<10?r._k.toFixed(1):Math.round(r._k))+' km':'')+'</span>'+
        '<span class="nm">'+nm+'</span><span class="meta">'+esc(r.c)+(r.cc?', '+esc(r.cc):'')+
        (r.b?' — '+esc(r.b):'')+web+'</span>'+(any?strip(r.d):'')+tg+'</li>';
    }).join('');
  }
  document.getElementById('here').addEventListener('click',function(){
    if(!navigator.geolocation){say.textContent='This browser will not give a position.';return}
    say.textContent='asking the browser…';
    navigator.geolocation.getCurrentPosition(function(p){origin=[p.coords.latitude,p.coords.longitude];render()},
      function(){say.textContent='No position given. Type a town instead.'});
  });
  document.getElementById('town').addEventListener('change',function(e){
    var v=e.target.value.trim().toLowerCase();
    var t=TOWNS.filter(function(t){return t.n.toLowerCase()===v})[0]||
          TOWNS.filter(function(t){return t.n.toLowerCase().indexOf(v)===0})[0];
    if(t){origin=[t.lat,t.lon];render()} else {say.textContent='No cellar in this directory sits in a town by that name.'}
  });
  document.getElementById('cc').addEventListener('change',render);
  chips.addEventListener('click',function(e){var b=e.target.closest('button[data-tag]');if(!b)return;
    var k=b.getAttribute('data-tag');on[k]=!on[k];b.setAttribute('aria-pressed',on[k]?'true':'false');render()});
  render();
})();
</script>
<style>
.wk{display:inline-flex;gap:2px}
.wk .dd{width:9px;height:14px;border-radius:2px;display:inline-block;border:1.4px solid var(--line)}
.wk .dd.open{background:var(--wine);border-color:var(--wine)}
.wk .dd.closed{border-color:var(--mute)}
.wk .dd.unknown{border-style:dashed}
</style>
"""
    body = body.replace("__ROWS__", esc_js(rows)).replace("__TAGS__", esc_js(tags)).replace("__TOWNS__", esc_js(town_list))
    return page("Somewhere to taste it — Pinot Country", body, 1,
                "Every cellar in this directory sorted by how far it is from you, filtered by what its tags can prove.",
                None, f"{site_url}/visit/", card="visit")


# ------------------------------------------------------------------ the arithmetic

def lat_band_svg(points: list, w=860) -> str:
    """Every region this project covers, plotted by latitude. One axis, both hemispheres,
    and the outliers named — which is the whole argument about where pinot noir will grow."""
    h = 330
    top, bot = 40, h - 46
    lo, hi = -48, 52
    py = lambda lat: bot - (lat - lo) / (hi - lo) * (bot - top)
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Latitude of every pinot noir region in this directory">']
    for lat in range(-45, 51, 15):
        out.append(f'<line x1="120" y1="{py(lat):.1f}" x2="{w-20}" y2="{py(lat):.1f}" stroke="var(--line)" stroke-width="1"/>'
                   f'<text x="112" y="{py(lat)+4:.1f}" text-anchor="end" fill="var(--mute)" style="font:600 12px var(--ui,sans-serif)">{abs(lat)}°{"N" if lat>=0 else "S"}</text>')
    for lat, lab in ((0, "equator"),):
        out.append(f'<line x1="120" y1="{py(lat):.1f}" x2="{w-20}" y2="{py(lat):.1f}" stroke="var(--mute)" stroke-width="1.4" stroke-dasharray="4 4"/>'
                   f'<text x="{w-22}" y="{py(lat)-6:.1f}" text-anchor="end" fill="var(--mute)" style="font:600 11px var(--ui,sans-serif)">{lab}</text>')
    n = len(points)
    labelled: list = []
    for i, p in enumerate(sorted(points, key=lambda p: p["lon"])):
        x = 140 + (i + 0.5) * (w - 175) / max(1, n)
        y = py(p["lat"])
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="var(--wine)" opacity=".85">'
                   f'<title>{E(p["name"])} — {abs(p["lat"]):.1f}°{"N" if p["lat"]>=0 else "S"}</title></circle>')
        if p.get("label"):
            up = -12 if (len(labelled) % 2 == 0) else 20
            labelled.append(p["name"])
            out.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y + up * 0.55:.1f}" stroke="var(--line)" stroke-width="1"/>'
                       f'<text x="{x:.1f}" y="{y + up:.1f}" text-anchor="middle" fill="var(--ink)" '
                       f'style="font:700 11.5px var(--display,serif);paint-order:stroke;stroke:var(--panel);stroke-width:3px">{E(p["name"])}</text>')
    out.append(f'<text x="120" y="{h-14}" fill="var(--mute)" style="font:400 12px var(--ui,sans-serif)">'
               f'{n} regions, ordered west to east · each dot is one appellation in this directory</text>')
    out.append("</svg>")
    return "".join(out)


def decade_bars_svg(counts: dict, w=860, highlight=None) -> str:
    """American Viticultural Areas by the decade the Federal Register established them."""
    if not counts:
        return ""
    ks = sorted(counts)
    top = max(counts.values())
    h, base, left = 300, 240, 48
    bw = (w - left - 24) / len(ks)
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="American Viticultural Areas established, by decade">']
    for i, k in enumerate(ks):
        v = counts[k]
        bh = (v / top) * (base - 40)
        x = left + i * bw
        hl = highlight and k in highlight
        out.append(f'<rect x="{x+4:.1f}" y="{base-bh:.1f}" width="{bw-8:.1f}" height="{bh:.1f}" rx="3" '
                   f'fill="{"var(--wine)" if not hl else "var(--gold)"}"><title>{k}s: {v}</title></rect>'
                   f'<text x="{x+bw/2:.1f}" y="{base-bh-6:.1f}" text-anchor="middle" fill="var(--ink)" style="font:700 12px var(--ui,sans-serif)">{v}</text>'
                   f'<text x="{x+bw/2:.1f}" y="{base+20:.1f}" text-anchor="middle" fill="var(--mute)" style="font:600 12px var(--ui,sans-serif)">{k}s</text>')
    out.append(f'<line x1="{left}" y1="{base}" x2="{w-20}" y2="{base}" stroke="var(--ink)" stroke-width="2"/>')
    out.append("</svg>")
    return "".join(out)


def numbers_page(page, recs: list, cellars: dict, ava: dict, site_url: str) -> str:
    by_type: dict = {}
    for r in recs:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1
    regions = [r for r in recs if r["type"] == "region" and r.get("geo")]
    named = {"santa-maria-valley", "central-otago", "ahr", "sta-rita-hills", "willamette-valley", "burgundy"}
    pts = [{"name": r["names"]["name"], "lat": r["geo"]["lat"], "lon": r["geo"]["lon"], "label": r["id"] in named} for r in regions]
    north = max(regions, key=lambda r: r["geo"]["lat"])
    south = min(regions, key=lambda r: r["geo"]["lat"])
    warm = min([r for r in regions if r["geo"]["lat"] > 0], key=lambda r: r["geo"]["lat"])
    decades: dict = {}
    for a in (ava.get("avas") or []):
        y = a.get("established_year")
        if y:
            decades[(y // 10) * 10] = decades.get((y // 10) * 10, 0) + 1
    ours = {a["name"] for a in (ava.get("avas") or [])}
    rows = cellars["places"]
    days_known = sum(1 for p in rows if any(v != "unknown" for v in (p.get("days") or {}).values()))
    open_sun = sum(1 for p in rows if (p.get("days") or {}).get("Su") == "open")
    closed_sun = sum(1 for p in rows if (p.get("days") or {}).get("Su") == "closed")
    edges: list = []
    for r in recs:
        for k in r.get("kin_out", []):
            edges.append({"from_type": r["type"], "to_type": k["type"]})
    types = ["variety", "region", "vineyard", "producer", "clone", "practice", "pairing", "person", "org", "event", "term", "story"]
    labels = {"variety": "vine", "region": "region", "vineyard": "vineyard", "producer": "cellar", "clone": "clone",
              "practice": "practice", "pairing": "table", "person": "person", "org": "org", "event": "event",
              "term": "word", "art": "art", "story": "story"}
    measures = [(m, r) for r in recs for m in r.get("measures", [])]
    body = (f'<h1><span class="kind">count it up</span>What this adds up to</h1>'
            f'<p class="lede">Every number on this page comes out of the corpus at build time. Nothing is decorative and nothing is rounded to flatter.</p>'
            '<div class="facts">'
            + "".join(f'<div class="fact"><div class="n">{n:,}</div><div class="l">{E(l)}</div></div>' for n, l in
                      [(len(recs), "records"), (len(regions), "regions mapped"), (cellars["count"], "cellars on the map"),
                       (sum(len(r.get("kin_out", [])) for r in recs), "kin links"), (len(measures), "measured numbers")])
            + "</div>"
            f'<div class="chart"><h3>Pinot noir lives in a band, and then breaks it</h3>{lat_band_svg(pts)}'
            f'<p class="cap">Furthest from the equator: {E(north["names"]["name"])} at {north["geo"]["lat"]:.1f}°N and '
            f'{E(south["names"]["name"])} at {abs(south["geo"]["lat"]):.1f}°S. Closest to it: {E(warm["names"]["name"])} at '
            f'{warm["geo"]["lat"]:.1f}°N — the latitude of Beirut, growing a grape that wants Dijon, because the valley runs '
            f'east–west and the Pacific walks in every morning.</p></div>'
            f'<div class="chart"><h3>America drew {sum(decades.values())} lines on the ground</h3>{decade_bars_svg(decades)}'
            f'<p class="cap">American Viticultural Areas by the decade of the Federal Register notice that made them, from 27 CFR part 9. '
            f'The 1980s rush is the first generation of petitions; the ones since are mostly smaller areas carved out of larger ones.</p></div>'
            f'<div class="chart"><h3>Who is kin to who</h3>{viz.kin_matrix_svg(edges, types, labels)}'
            f'<p class="cap">Every link a record makes, by the kind of page at each end. Regions point at everything; '
            f'the table points back at the ground it came off.</p></div>'
            f'<h2>The week, honestly</h2>'
            f'<p>{days_known:,} of {len(rows):,} cellars name a single day either way. {open_sun} say they open on Sunday, '
            f'{closed_sun} say they close, and {len(rows)-open_sun-closed_sun:,} have told nobody this project can read. '
            f'Unknown is drawn dashed and counted as unknown. {viz.day_key()}</p>'
            '<h2>Records by kind</h2><table class="tbl-twin"><tr><th>kind</th><th>records</th></tr>'
            + "".join(f'<tr><th>{E(labels.get(k, k))}</th><td>{v}</td></tr>' for k, v in sorted(by_type.items(), key=lambda kv: -kv[1]))
            + '</table>'
            '<h2>Everything somebody measured</h2><p class="mute">Each row names the source that published it. Nothing here is estimated.</p>'
            '<table class="tbl-twin"><tr><th>what</th><th>value</th></tr>'
            + "".join(f'<tr><th>{E(r["names"]["name"])} — {E(m.get("label") or m["key"])}</th>'
                      f'<td>{E(str(m.get("value")))} {E(m.get("unit") or "")}'
                      f'{" (" + E(str(m["year"])) + ")" if m.get("year") else ""}</td></tr>'
                      for m, r in sorted(measures, key=lambda x: x[1]["names"]["name"])[:80])
            + '</table>')
    return page("Count it up — Pinot Country", body, 1,
                "What the corpus adds up to: the latitude band, the AVA decades, the kin matrix, and every number somebody published.",
                None, f"{site_url}/numbers/", card="numbers")


# ------------------------------------------------------------------ the family

def family_svg(w=760) -> str:
    """Pinot's mutations and its children, drawn once rather than described twice."""
    h = 340
    def box(x, y, label, sub, cls):
        hl = "hl" in cls
        return (f'<g><rect x="{x}" y="{y}" width="148" height="52" rx="10" class="{cls}"/>'
                f'<text x="{x+74}" y="{y+22}" text-anchor="middle" class="t1{" on" if hl else ""}">{E(label)}</text>'
                f'<text x="{x+74}" y="{y+39}" text-anchor="middle" class="t2{" on" if hl else ""}">{E(sub)}</text></g>')
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Pinot noir, its colour mutations and its children by Gouais blanc">',
           '<style>.n{fill:var(--panel);stroke:var(--line);stroke-width:1.5}.hl{fill:var(--wine);stroke:var(--wine)}'
           '.t1{font:700 14px var(--display,serif);fill:var(--ink)}.t1.on{fill:#fff}'
           '.t2{font:400 11px var(--ui,sans-serif);fill:var(--mute)}.t2.on{fill:#f7dbe2}'
           '.ln{stroke:var(--mute);stroke-width:1.6;fill:none}.lb{font:600 11px var(--ui,sans-serif);fill:var(--mute)}</style>']
    out.append('<path class="ln" d="M306 100 C306 130 220 130 220 160"/>')
    out.append('<path class="ln" d="M380 100 C380 130 470 130 470 160"/>')
    out.append('<path class="ln" d="M343 100 L343 160"/>')
    out.append('<path class="ln" d="M343 212 L343 258"/>')
    out.append('<path class="ln" d="M120 100 C120 200 200 240 300 262"/>')
    out.append(box(269, 48, "Pinot noir", "the black one", "n hl"))
    out.append(box(46, 48, "Gouais blanc", "the peasants' vine", "n"))
    out.append(box(146, 160, "Pinot gris", "colour switched off", "n"))
    out.append(box(269, 160, "Pinot Meunier", "a chimera, floury leaves", "n"))
    out.append(box(396, 160, "Pinot blanc", "further along, reversible", "n"))
    out.append(box(269, 262, "Frühburgunder", "two weeks early", "n"))
    out.append(box(560, 160, "Chardonnay · Gamay", "and fourteen more", "n"))
    out.append('<path class="ln" d="M196 92 C300 120 480 140 560 170"/>')
    out.append('<text x="360" y="136" class="lb" text-anchor="middle">mutation</text>')
    out.append('<text x="430" y="118" class="lb">crossed with Gouais blanc</text>')
    out.append("</svg>")
    return "".join(out)


def clones_page(page, recs: list, site_url: str) -> str:
    clones = [r for r in recs if r["type"] == "clone"]
    varieties = [r for r in recs if r["type"] == "variety"]
    body = (f'<h1><span class="kind">one vine, copied</span>The family and the catalogue</h1>'
            f'<p class="lede">Pinot noir mutates readily and gets propagated by cuttings, so every vine in every vineyard is a copy of '
            f'a copy. Two things follow: a family of colour mutations that are the same vine under other names, and a catalogue of '
            f'numbered selections a grower can order by post.</p>'
            f'<div class="chart"><h3>The family</h3>{family_svg()}'
            f'<p class="cap">Solid lines are mutations of one vine. The line to chardonnay and gamay is a cross: pinot × Gouais blanc, '
            f'which produced sixteen varieties that between them plant half of France.</p></div>'
            '<div class="cards">' + "".join(
                f'<div class="card"><a class="t" href="../variety/{E(r["id"])}/index.html">{E(r["names"]["name"])}</a>'
                f'<p>{E(r["blurb"])}</p></div>' for r in sorted(varieties, key=lambda r: r["names"]["name"]))
            + "</div>"
            f'<h2>The numbered ones</h2><p class="mute">Each row is a single mother vine, tested clean and copied. '
            f'The number is the nursery\'s; the behaviour is the grower\'s problem.</p>'
            '<table><tr><th>clone</th><th>where it comes from</th><th>what it does</th></tr>'
            + "".join(f'<tr><th><a href="../clone/{E(r["id"])}/index.html">{E(r["names"]["name"])}</a></th>'
                      f'<td>{E((r.get("facets") or {}).get("origin", ""))}</td><td>{E(r["blurb"])}</td></tr>'
                      for r in sorted(clones, key=lambda r: ((r.get("facets") or {}).get("origin", ""), r["names"]["name"])))
            + "</table>"
            f'<p class="mute">Where a selection\'s origin is trade folklore rather than a document — and several of the famous ones are — '
            f'the record says so on its own page. <a href="../story/the-dijon-numbers/index.html">The whole story →</a></p>')
    return page("The family and the catalogue — Pinot Country", body, 1,
                "Pinot noir's colour mutations, its children by Gouais blanc, and the numbered clones growers plant.",
                None, f"{site_url}/clones/", card="clones")
