#!/usr/bin/env python3
"""cards.py — the picture that shows when a page is shared.

One 1200x630 card per record and per standing page, drawn with Pillow. Masters are
committed to `cards/` and copied into the site by site.py, which points og:image at a
card ONLY when its file exists — an og:image that 404s unfurls worse than none at all.

Each card says what kind of thing the page is, names it, and then shows the one fact
that makes it worth a click:

    place   the town, the tags it has earned, and a dot on a map of the two states
    style   the hog with this style's cuts lit
    sauce   where its sugar sits on the 0-13 g scale, against the other bases
    dish    the course, and the count of free recipes on the page
    person  the role and the place they are known for
    term    the root of the word
    art     the picture itself, bled to the edge
    story   the lede

A record with a photograph gets that photograph as a bleed on the right, which is the
strongest card this site can make, and the drawn panel otherwise.

    python3 tools/cards.py              # every card that is missing or out of date
    python3 tools/cards.py --all        # redraw everything
    python3 tools/cards.py place/skylight-inn index near
"""
from __future__ import annotations

import json
import math
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BUILD, DATA, GEO, IMAGES, ROOT, jload  # noqa: E402

CARDS = ROOT / "cards"
W, H = 1200, 630
PAD = 64

# The site's own ink-mode palette: a card is read at thumbnail size in a feed, so it is
# built on the dark ground where the ember reads hottest.
INK = (23, 20, 18)
INK_2 = (31, 27, 24)
CREAM = (241, 235, 224)
MUTE = (168, 158, 143)
EMBER = (176, 58, 84)          # wine, at card contrast
EMBER_HI = (214, 102, 128)
GOLD = (216, 176, 96)
LINE = (58, 50, 43)
CHIP_BG = (42, 36, 31)

SERIF = "/System/Library/Fonts/Supplemental/Iowan Old Style.ttc"
SERIF_FALLBACK = "/System/Library/Fonts/Supplemental/Georgia.ttf"
SANS = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
SANS_R = "/System/Library/Fonts/Supplemental/Arial.ttf"

TYPE_LABEL = {"variety": "THE VINE", "region": "A REGION", "vineyard": "A VINEYARD", "producer": "A CELLAR",
              "clone": "A CLONE", "practice": "VINEYARD AND CELLAR", "pairing": "AT THE TABLE", "person": "A PERSON",
              "org": "AN ORGANIZATION", "event": "AN EVENT", "term": "A WORD", "art": "A PICTURE", "story": "A STORY"}
SITE_MARK = "PINOT COUNTRY"


def font(path: str, size: int, index: int = 0):
    try:
        return ImageFont.truetype(path, size, index=index)
    except OSError:
        return ImageFont.truetype(SERIF_FALLBACK, size)


def F_TITLE(sz):
    return font(SERIF, sz, index=1)      # Iowan Old Style Bold


def F_BODY(sz):
    return font(SERIF, sz, index=0)


def F_SANS(sz):
    return font(SANS, sz)


def F_SANS_R(sz):
    return font(SANS_R, sz)


# ------------------------------------------------------------------ helpers

def fit_text(d: ImageDraw.ImageDraw, text: str, fnt_for, max_w: int, max_lines: int, start: int, floor: int):
    """Largest size at which `text` wraps into max_lines of max_w. Returns (font, lines)."""
    size = start
    while size >= floor:
        f = fnt_for(size)
        avg = d.textlength("n", font=f) or 1
        cols = max(8, int(max_w / avg * 1.05))
        lines = textwrap.wrap(text, width=cols) or [text]
        if len(lines) <= max_lines and all(d.textlength(l, font=f) <= max_w for l in lines):
            return f, lines
        size -= 3
    # nothing fits: take what does and end it honestly
    f = fnt_for(floor)
    avg = d.textlength("n", font=f) or 1
    cols = max(8, int(max_w / avg * 1.05))
    lines = textwrap.wrap(text, width=cols) or [text]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and d.textlength(last + "\u2026", font=f) > max_w:
            last = last[:-1]
        lines[-1] = last.rstrip(" ,;:\u2014-") + "\u2026"
    return f, lines


def draw_lines(d, x, y, lines, fnt, fill, leading=1.16):
    lh = int(fnt.size * leading)
    for i, line in enumerate(lines):
        d.text((x, y + i * lh), line, font=fnt, fill=fill)
    return y + len(lines) * lh


def chip(d, x, y, text, fnt, fg=CREAM, bg=CHIP_BG, border=LINE):
    tw = d.textlength(text, font=fnt)
    h = int(fnt.size * 1.95)
    d.rounded_rectangle([x, y, x + tw + 30, y + h], radius=h // 2, fill=bg, outline=border, width=2)
    d.text((x + 15, y + (h - fnt.size) / 2 - fnt.size * 0.08), text, font=fnt, fill=fg)
    return x + tw + 30 + 10


def base_card(photo: Image.Image | None = None):
    """The ground: ink, a warm glow behind the text column, an ember rule down the left,
    and the photograph bled into the right third under a gradient so type stays legible."""
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)
    glow = Image.new("RGB", (W, H), INK)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-260, 240, 520, 1040], fill=(46, 32, 25))
    img = Image.blend(img, glow.filter(ImageFilter.GaussianBlur(120)), 0.9)
    d = ImageDraw.Draw(img)
    if photo is not None:
        pw = 520
        ph = photo.copy()
        ratio = max(pw / ph.width, H / ph.height)
        ph = ph.resize((max(1, int(ph.width * ratio)), max(1, int(ph.height * ratio))), Image.LANCZOS)
        left = max(0, (ph.width - pw) // 2)
        top = max(0, (ph.height - H) // 2)
        ph = ph.crop((left, top, left + pw, top + H))
        img.paste(ph, (W - pw, 0))
        # a horizontal fade so the photograph dissolves into the ground rather than butting it
        fade = Image.new("L", (240, 1), 0)
        for x in range(240):
            fade.putpixel((x, 0), int(255 * (1 - x / 240) ** 1.2))
        mask = fade.resize((240, H))
        img.paste(Image.new("RGB", (240, H), INK), (W - pw, 0), mask)
        d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 10, H], fill=EMBER)
    return img, d


def footer(d, right_note: str = ""):
    f = F_SANS(21)
    d.text((PAD, H - 62), SITE_MARK, font=f, fill=GOLD)
    if right_note:
        fr = F_SANS_R(21)
        tw = d.textlength(right_note, font=fr)
        d.text((W - PAD - tw, H - 62), right_note, font=fr, fill=MUTE)


def eyebrow(d, text: str, y=PAD):
    f = F_SANS(23)
    t = " ".join(text.upper())
    d.text((PAD, y), t, font=f, fill=EMBER_HI)
    return y + 44


def _open(im: dict):
    p = IMAGES / im["file"]
    if not p.exists():
        return None
    try:
        return Image.open(p).convert("RGB")
    except Exception:  # noqa: BLE001
        return None


def vivid(ph: Image.Image) -> Image.Image:
    """Warm the picture toward the site's ember and lift it, so a card glows in a feed
    instead of sitting grey next to it. Never so far that a red sauce reads orange."""
    from PIL import ImageEnhance
    ph = ImageEnhance.Color(ph).enhance(1.22)
    ph = ImageEnhance.Contrast(ph).enhance(1.10)
    ph = ImageEnhance.Brightness(ph).enhance(1.04)
    warm = Image.new("RGB", ph.size, (214, 92, 40))
    return Image.blend(ph, warm, 0.06)


def load_photo(rec: dict, ctx: dict | None = None):
    """The record's own picture if it has one; otherwise the best picture among the pages
    it points at, then its style's, then its type's. Returns (image, credit, borrowed_from)."""
    own = rec.get("primary_image") or (rec.get("images") or [None])[0]
    if own:
        ph = _open(own)
        if ph:
            return ph, f'{own.get("author", "")} · {own.get("license", "")}'.strip(" ·"), None
    if not ctx:
        return None, "", None
    by_id = ctx.get("by_id") or {}
    order = [k["to"] for k in (rec.get("kin_out") or [])] + [k["from"] for k in (rec.get("kin_in") or [])]
    # a style or a place makes a better stand-in than a word does
    rank = {"art": 0, "place": 1, "style": 2, "pit": 3, "dish": 4, "event": 5, "sauce": 6, "person": 7}
    cands = [by_id[i] for i in order if i in by_id and by_id[i].get("images")]
    cands.sort(key=lambda r: rank.get(r["type"], 9))
    seed = sum(ord(ch) for ch in rec["id"])
    for c in cands:
        imgs = c.get("images") or []
        if not imgs:
            continue
        im = imgs[seed % len(imgs)]
        ph = _open(im)
        if ph:
            return ph, f'{im.get("author", "")} · {im.get("license", "")}'.strip(" ·"), c["names"]["name"]
    for sid in ((rec.get("facets") or {}).get("styles") or []):
        st = by_id.get(sid)
        if st and st.get("images"):
            im = st["images"][seed % len(st["images"])]
            ph = _open(im)
            if ph:
                return ph, f'{im.get("author", "")} · {im.get("license", "")}'.strip(" ·"), st["names"]["name"]
    fb = ctx.get("fallback_by_type", {}).get(rec["type"]) or ctx.get("fallback")
    if fb:
        ph = _open(fb[0])
        if ph:
            return ph, f'{fb[0].get("author", "")} · {fb[0].get("license", "")}'.strip(" ·"), fb[1]
    return None, "", None


# ------------------------------------------------------------------ the little map

_WORLD = None


def world():
    global _WORLD
    if _WORLD is None:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import worldmap
        _WORLD = (worldmap, worldmap.load_world())
    return _WORLD


def mini_map(size=(470, 300), dot=None, dots=None, dot_r=9):
    """The whole world in Equal Earth, with one cellar lit or many. Drawn at 3x and
    downsampled, because a 1px coastline at card size reads as a scan artefact."""
    wm, gj = world()
    S = 3
    w, h = size[0] * S, size[1] * S
    fit = wm.fit_world(w, pad=4 * S, lat_max=62)
    img = Image.new("RGB", (w, int(fit["h"])), INK)
    d = ImageDraw.Draw(img)
    for c in gj["countries"]:
        for ring in c["rings"]:
            pts = [wm.project(lon, max(-62, min(62, lat)), fit) for lon, lat in ring]
            if len(pts) > 2:
                d.polygon(pts, fill=(52, 44, 44), outline=(104, 88, 88))
    for p in (dots or []):
        x, y = wm.project(p[1], p[0], fit)
        d.ellipse([x - 2.2 * S, y - 2.2 * S, x + 2.2 * S, y + 2.2 * S], fill=(150, 78, 96))
    if dot:
        x, y = wm.project(dot[1], dot[0], fit)
        r = dot_r * S
        d.ellipse([x - r * 2.4, y - r * 2.4, x + r * 2.4, y + r * 2.4], fill=(84, 34, 48))
        d.ellipse([x - r, y - r, x + r, y + r], fill=EMBER_HI, outline=CREAM, width=2 * S)
    out = img.crop((0, 0, w, int(fit["h"])))
    return out.resize((size[0], int(size[0] * fit["h"] / w)), Image.LANCZOS)


def photo_ground(ph: Image.Image, strength=1.0):
    """The picture, warmed and bled edge to edge, with a scrim that is opaque under the
    text column and clear on the right. This is the card; the type sits on top of it."""
    img = Image.new("RGB", (W, H), INK)
    ph = vivid(ph)
    ratio = max(W / ph.width, H / ph.height)
    ph = ph.resize((max(1, int(ph.width * ratio)), max(1, int(ph.height * ratio))), Image.LANCZOS)
    img.paste(ph, ((W - ph.width) // 2, (H - ph.height) // 2))
    # horizontal scrim: solid ink at the left edge, gone by 70% across
    grad = Image.new("L", (W, 1), 0)
    for x in range(W):
        t = x / W
        v = 252 if t < 0.26 else int(252 * max(0.0, (0.76 - t) / 0.5) ** 0.85)
        grad.putpixel((x, 0), int(v * strength))
    img.paste(Image.new("RGB", (W, H), INK), (0, 0), grad.resize((W, H)))
    # a bottom band so the footer line always has ground under it
    bot = Image.new("L", (1, H), 0)
    for y in range(H):
        bot.putpixel((0, y), int(210 * max(0.0, (y - H * 0.80) / (H * 0.20)) ** 1.1))
    img.paste(Image.new("RGB", (W, H), INK), (0, 0), bot.resize((W, H)))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 10, H], fill=EMBER)
    return img, d


FOOT_Y = H - 62          # the footer baseline
FACT_Y = H - 168         # chips, dots and panels hang from here, never from the flow


def record_card(rec: dict, ctx: dict) -> Image.Image:
    t = rec["type"]
    photo, credit, borrowed = load_photo(rec, ctx)
    art = t == "art" and photo is not None and not borrowed

    if art:
        img = Image.new("RGB", (W, H), INK)
        ph = vivid(photo)
        ratio = max(W / ph.width, H / ph.height)
        ph = ph.resize((int(ph.width * ratio), int(ph.height * ratio)), Image.LANCZOS)
        img.paste(ph, ((W - ph.width) // 2, (H - ph.height) // 2))
        scrim = Image.new("L", (1, H), 0)
        for yy in range(H):
            scrim.putpixel((0, yy), int(248 * max(0.0, (yy - H * 0.32) / (H * 0.68)) ** 1.05))
        img.paste(Image.new("RGB", (W, H), INK), (0, 0), scrim.resize((W, H)))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, 10, H], fill=EMBER)
        col_w, y, title_lines = W - PAD * 2, eyebrow(d, TYPE_LABEL.get(t, t), y=int(H * 0.50)), 2
    elif photo is not None:
        img, d = photo_ground(photo)
        col_w, y, title_lines = int(W * 0.55), eyebrow(d, TYPE_LABEL.get(t, t)), 2
    else:
        img, d = base_card(None)
        col_w, y, title_lines = W - PAD * 2 - 470, eyebrow(d, TYPE_LABEL.get(t, t)), 3

    f, lines = fit_text(d, rec["names"]["name"], F_TITLE, col_w, title_lines, 78, 32)
    y = draw_lines(d, PAD, y + 4, lines, f, CREAM, 1.07) + 10

    a = rec.get("address") or {}
    fc = rec.get("facets") or {}
    sub = ""
    if t in ("producer", "vineyard"):
        sub = ", ".join(x for x in (a.get("city"), a.get("state")) if x) or (rec.get("region_terms") or [{}])[0].get("name", "")
    elif t == "person":
        sub = str(fc.get("role") or "").replace("-", " ")
    elif t == "region":
        sub = (fc.get("country") or "") + (f' · {fc["level"]}' if fc.get("level") else "")
    elif t == "clone":
        sub = str(fc.get("origin") or "")
    elif t == "term":
        sub = "a word, with its root"
    elif t == "pairing":
        sub = {"main": "on the plate", "side": "a side", "cheese": "cheese", "condiment": "on the plate and in the fire",
               "fish": "out of the water", "bird": "a bird", "fungus": "out of the ground"}.get(fc.get("course", ""), "")
    elif t == "practice":
        sub = {"vineyard": "in the vineyard", "cellar": "in the cellar", "ferment": "in the fermenter",
               "press": "at the press", "ageing": "in barrel", "planting": "in the ground"}.get(fc.get("kind", ""), "")
    elif t == "variety":
        sub = "one vine, and its mutations"
    if sub:
        d.text((PAD, y), sub[:60], font=F_SANS(25), fill=GOLD)
        y += 44

    # the blurb takes whatever room is left above the fact line, and no more
    room = FACT_Y - 16 - y
    if room > 40:
        maxl = max(1, min(3, room // 39))
        fb, bl = fit_text(d, rec.get("blurb") or rec["text"]["what"], F_BODY, col_w, maxl, 29, 20)
        draw_lines(d, PAD, y, bl, fb, (208, 199, 185), 1.3)

    # the one fact, anchored
    fy = FACT_Y
    if t in ("producer", "vineyard"):
        x = PAD
        fchip = F_SANS(20)
        for tg in (rec.get("tag_facts") or [])[:4]:
            lab = tg.get("label", "")
            if x + d.textlength(lab, font=fchip) + 42 > PAD + col_w:
                break
            x = chip(d, x, fy, lab, fchip, fg=CREAM, border=GOLD if tg.get("group") == "ownership" else LINE)
        est = fc.get("established")
        if est:
            d.text((PAD, fy + 54), f"planted or founded {est}", font=F_SANS(20), fill=GOLD)
        if rec.get("geo") and photo is None:
            img.paste(mini_map(dot=(rec["geo"]["lat"], rec["geo"]["lon"]), dots=ctx.get("dots")), (W - PAD - 470, 190))
    elif t == "region":
        mm = next((m for m in rec.get("measures", []) if m["key"].startswith(("hectares", "acres"))), None)
        bits = []
        if fc.get("established"):
            bits.append(f'appellation {fc["established"]}')
        if mm and mm.get("value"):
            bits.append(f'{mm["value"]:,g} {mm.get("unit","")}' if isinstance(mm["value"], (int, float)) else str(mm["value"]))
        if rec.get("geo"):
            g = rec["geo"]
            bits.append(f'{abs(g["lat"]):.1f}°{"N" if g["lat"] >= 0 else "S"}')
        if bits:
            chip(d, PAD, fy + 18, " · ".join(bits)[:58], F_SANS(21), fg=CREAM, border=GOLD)
        if rec.get("geo") and photo is None:
            img.paste(mini_map(dot=(rec["geo"]["lat"], rec["geo"]["lon"]), dots=ctx.get("dots")), (W - PAD - 470, 190))
    elif t == "term":
        root = (rec.get("etymology") or {}).get("root", "")
        if root:
            fr, rl = fit_text(d, root, F_BODY, col_w, 2, 25, 18)
            draw_lines(d, PAD, fy, rl, fr, CREAM, 1.24)
    elif t == "pairing" and rec.get("recipes"):
        n = sum(len(rc.get("ingredients") or []) for rc in rec["recipes"])
        chip(d, PAD, fy + 18, f"{n} ingredients, every one a fact somebody printed", F_SANS(21), fg=CREAM, border=GOLD)
    elif t == "story":
        n = len(rec.get("sections") or [])
        if n:
            chip(d, PAD, fy + 18, f"{n} sections, and a list of what it could not settle", F_SANS(21), fg=CREAM, border=GOLD)
    elif t == "clone":
        chip(d, PAD, fy + 18, (fc.get("origin") or "a selection") + " · one mother vine, copied", F_SANS(21), fg=CREAM, border=GOLD)
    elif t == "person":
        pl = [k["name"] for k in (rec.get("kin_out") or []) if k.get("type") in ("producer", "vineyard", "region")][:2]
        if pl:
            chip(d, PAD, fy + 18, " \u00b7 ".join(pl)[:46], F_SANS(21), fg=CREAM, border=LINE)

    note = credit if (photo is not None and not borrowed) else (f"picture: {borrowed}" if borrowed else ctx.get("host", ""))
    footer(d, note[:74])
    return img


# ------------------------------------------------------------------ page cards

def page_card(title: str, lede: str, eyebrow_text: str, ctx: dict, panel=None, stats=None, photo_id=None) -> Image.Image:
    ph = None
    if photo_id:
        rec = (ctx.get("by_id") or {}).get(photo_id)
        if rec and rec.get("images"):
            ph = _open(rec["images"][0])
    if ph is not None:
        img, d = photo_ground(ph)
        panel = None
    else:
        img, d = base_card()
    y = eyebrow(d, eyebrow_text)
    f, lines = fit_text(d, title, F_TITLE, W - PAD * 2 - (470 if panel is not None else 0), 2, 86, 40)
    y = draw_lines(d, PAD, y + 4, lines, f, CREAM, 1.06) + 16
    fb, bl = fit_text(d, lede, F_BODY, W - PAD * 2 - (470 if panel is not None else 0), 3, 31, 22)
    y = draw_lines(d, PAD, y, bl, fb, MUTE, 1.3) + 18
    if stats:
        x, y = PAD, max(y, FACT_Y - 30)
        for n, lab in stats:
            fn, fl = F_TITLE(44), F_SANS(19)
            d.text((x, y), str(n), font=fn, fill=EMBER_HI)
            d.text((x, y + 52), lab.upper(), font=fl, fill=MUTE)
            x += max(d.textlength(str(n), font=fn), d.textlength(lab.upper(), font=fl)) + 52
    if panel is not None:
        img.paste(panel, (W - PAD - panel.width, (H - panel.height) // 2))
    footer(d, ctx.get("host", ""))
    return img


# ------------------------------------------------------------------ main

def main(argv: list[str]) -> int:
    api = BUILD / "api"
    if not (api / "nodes.json").exists():
        print("run tools/build.py first")
        return 1
    recs = jload(api / "nodes.json")["nodes"]
    cellars = jload(api / "cellars.json")
    cov = jload(api / "coverage.json")
    CARDS.mkdir(exist_ok=True)

    ctx = {"by_id": {r["id"]: r for r in recs},
           "dots": [(p["lat"], p["lon"]) for p in cellars["places"] if p.get("lat") is not None][:1200],
           "host": "nanobotco.github.io/pinot-noir"}

    want = set(argv)
    redraw_all = "--all" in want
    want.discard("--all")
    made = 0

    def save(img: Image.Image, name: str):
        """JPEG, because these are photographs: the same cards as PNG came to 164 MB.
        Every unfurler takes JPEG, and 1200x630 at q86 is about 120 KB."""
        nonlocal made
        p = CARDS / (name + ".jpg")
        p.parent.mkdir(parents=True, exist_ok=True)
        img.save(p, "JPEG", quality=86, optimize=True, progressive=True, subsampling=1)
        made += 1

    # standing pages
    allmap = mini_map(size=(470, 330), dots=ctx["dots"])
    n_reg = cov["records"].get("region", 0)
    pages = {
        "index": ("Pinot Country", "One thin-skinned grape, the ground it answers to, and what gets eaten beside it: Burgundy, the Ahr, the Willamette, a fog corridor in Sonoma and a valley in Santa Barbara County that runs the wrong way.",
                  "a directory of one grape", allmap,
                  [(sum(cov["records"].values()), "records"), (n_reg, "regions"), (cellars["count"], "cellars"), (cov["sources"], "sources")], None),
        "visit": ("Somewhere to taste it", "Every cellar on the map sorted by how far it is from you, filtered by what its tags can actually prove. The arithmetic happens in your browser.",
                  "find a door", allmap, None, None),
        "map": ("Where the doors are", "Every cellar and vineyard here, plus every winery OpenStreetMap knows inside the regions covered, drawn in Equal Earth.",
                "the whole map", allmap, None, None),
        "numbers": ("What this adds up to", "The latitude band and the places that break it, the decades America spent drawing appellation lines, and every number somebody published.",
                    "count it up", None, [(n_reg, "regions"), (cellars["count"], "cellars"), (cov["sources"], "sources")], None),
        "clones": ("The family and the catalogue", "Pinot noir mutates readily and travels as cuttings, so every vine is a copy of a copy — colour mutations under other names, and numbered selections ordered by post.",
                   "one vine, copied", None, None, None),
        "regions": ("The regions", "Appellations, AVAs, valleys and communes, from the Côte de Nuits to a schist basin at 45 degrees south.", "the ground", allmap, None, None),
        "cellars": ("The cellars", "Domaines, wineries and tasting rooms — who presses the fruit, and who lets you in.", "who makes it", allmap, None, None),
        "table": ("At the table", "Tri-tip over red oak, duck, salmon, mushrooms, a washed-rind cheese and a cold cellar.", "what goes beside it", None, None, None),
        "words": ("The words, with their roots", "Climat from the Greek for a slope. Saignée from the verb to bleed. Spätburgunder, the late Burgundian, against the früh one.", "vocabulary", None, None, None),
        "stories": ("The long reads", "How the grape left the hill, what thin skin costs, the numbers on the vine, and one California valley that cooks beef over the same oak it grows pinot beside.", "long reads", None, None, None),
        "coverage": ("Coverage", "The scope as an object: where every row comes from, what each tag needs before it is granted, and what has not been read yet.", "coverage", None, None, None),
        "search": ("Search the directory", "Spätburgunder, blauburgunder, pinot nero — same vine, three spellings, and near spellings are found and said to be near.", "search", None, None, None),
        "sources": ("Sources", "Every book, regulation, dataset and page the records cite, by id — including the revision of each Wikipedia article this project actually read.", "sources", None, None, None),
        "vineyards": ("The vineyards", "Named sites: grands crus, climats, benchland blocks, a hillside somebody fenced and argued over for six hundred years.", "named ground", allmap, None, None),
        "practices": ("In the vineyard and cellar", "Whole cluster, cold soak, punch-down, neutral oak — the decisions that show up in the glass.", "decisions", None, None, None),
        "people": ("The people", "Growers, winemakers, nurserymen, a Dijon agronomist, and a Santa Maria butcher.", "who did it", None, None, None),
        "vine": ("The vine", "Pinot noir and the family it mutates into: meunier, gris, blanc, and the früh one that ripens two weeks early.", "the grape", None, None, None),
    }
    for name, (title, lede, eb, panel, stats, photo_id) in pages.items():
        if want and name not in want:
            continue
        p = CARDS / (name + ".jpg")
        if not redraw_all and not want and p.exists():
            continue
        save(page_card(title, lede, eb, ctx, panel, stats, photo_id), name)

    # records
    for r in recs:
        key = f'{r["type"]}__{r["id"]}'
        sel = f'{r["type"]}/{r["id"]}'
        if want and sel not in want and key not in want:
            continue
        p = CARDS / (key + ".jpg")
        if not redraw_all and not want and p.exists():
            continue
        try:
            save(record_card(r, ctx), key)
        except Exception as e:  # noqa: BLE001
            print(f"  {key}: {e}")
    total = len(list(CARDS.glob("*.jpg")))
    size = sum(f.stat().st_size for f in CARDS.glob("*.jpg"))
    print(f"cards: {made} drawn, {total} on file, {size/1e6:.1f} MB in {CARDS}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
