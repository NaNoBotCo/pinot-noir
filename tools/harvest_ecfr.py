#!/usr/bin/env python3
"""harvest_ecfr.py — every American Viticultural Area, from the regulation that made it.

27 CFR part 9 is the list: one section per AVA, its name, its boundary, and the Federal
Register citation that established it. The eCFR publishes it as XML and it is a work of
the United States government — public domain, and the only place an AVA's establishment
is a fact rather than a repetition.

    python3 tools/harvest_ecfr.py

Writes data/harvest/ava.json: section number, name, the FR citations in the source note,
the earliest year among them, and the first 400 characters of the boundary text.
"""
from __future__ import annotations

import datetime as dt
import gzip
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HARVEST, jdump  # noqa: E402

UA = "pinot-noir-build/0.1 (https://wichaa.net) python-urllib"
# the versioner serves dated issues; today is not always one of them, so ask for the
# first of the current month and record which issue this is
DATE = os.environ.get("ECFR_DATE") or dt.date.today().replace(day=1).isoformat()
URL = f"https://www.ecfr.gov/api/versioner/v1/full/{DATE}/title-27.xml?part=9"


def text_of(el) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def main() -> int:
    print(f"fetching {URL}")
    # the endpoint refuses an uncompressed reply: "This endpoint requires response compression."
    req = urllib.request.Request(URL, headers={"User-Agent": UA, "Accept": "application/xml", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        data = gzip.decompress(data)
    raw = data.decode("utf-8", "replace")
    root = ET.fromstring(raw)
    out = []
    for sec in root.iter("DIV8"):
        num = (sec.get("N") or "").strip()
        head = text_of(sec.find("HEAD")) if sec.find("HEAD") is not None else ""
        m = re.match(r"§\s*([\d.]+)\s+(.*?)\.?$", head)
        if not m:
            continue
        name = m.group(2).strip()
        body = text_of(sec)
        cites = re.findall(r"(\d+)\s+FR\s+(\d+),\s+([A-Z][a-z]+\.?\s+\d+,\s+(\d{4}))", body)
        years = sorted({int(c[3]) for c in cites})
        # the boundary description sits under a paragraph headed (c) Boundary or similar
        bnd = ""
        for p in sec.iter("P"):
            t = text_of(p)
            if re.match(r"^\(c\)|^\(b\)", t) and ("boundar" in t.lower() or "is located" in t.lower()):
                bnd = t[:400]
                break
        out.append({"section": num or m.group(1), "name": name, "fr_citations": [f"{a} FR {b}, {c}" for a, b, c, _ in cites],
                    "established_year": years[0] if years else None, "years_touched": years, "boundary_excerpt": bnd})
    jdump({"source": "Electronic Code of Federal Regulations, title 27, part 9 — American Viticultural Areas",
           "publisher": "US National Archives and Records Administration / Government Publishing Office",
           "url": "https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-9",
           "licence": "public domain (a work of the United States government)",
           "issue": DATE, "fetched_at": dt.date.today().isoformat(), "count": len(out), "avas": out}, HARVEST / "ava.json")
    print(f"wrote {len(out)} AVA sections; {sum(1 for a in out if a['established_year'])} carry a Federal Register year")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
