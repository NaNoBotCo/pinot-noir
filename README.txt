PINOT COUNTRY — THE WORKING GUIDE
=================================

A directory of pinot noir, built the same way as the other record sites in this
fleet: one JSON file per node, per-field provenance, kin written by hand in both
directions, and a static site that people and machines read from the same data.

Live at https://nanobotco.github.io/pinot-noir/ — published from docs/ by GitHub Pages.

READ NEXT
  AUTHORING.txt      how to write a record, field by field, with the cast list
  schema/node.schema.json   what the validator enforces
  LICENSE            what is CC BY, what is ODbL, what is public domain

THE CHAIN
  python3 tools/validate.py     every record, or nothing is built
  python3 tools/build.py        records + harvests -> build/api, searchdocs, thesaurus
  python3 tools/cards.py        1200x630 share cards, only the missing ones
  python3 tools/site.py         build/api -> build/site
  python3 tools/serve.py 8803   http://127.0.0.1:8803/
  ./publish.sh                  the whole chain into docs/, with the host-path gate

  BUILD_DRAFT=1 turns an unwritten kin target into a warning. Never for a publish.

THE HARVESTS, AND WHAT EACH ONE IS FOR
  tools/harvest_ecfr.py       27 CFR part 9 -> data/harvest/ava.json. 289 American
                              Viticultural Areas with the Federal Register citation
                              that established each one. Public domain, and the only
                              place an AVA date is a fact rather than a repetition.
                              A test fails if a record's AVA year disagrees with it.
  tools/harvest_osm.py        craft=winery, tourism=wine_cellar, shop=wine inside 28
                              named boxes -> data/harvest/osm-places.json (ODbL).
                              Run it in chunks: --boxes burgundy,champagne
                              !! Mirrors are unreliable. The sanity check counts
                              wineries in the Cote d'Or and refuses to run against a
                              mirror serving a regional extract - overpass.osm.ch
                              looked healthy and serves SWITZERLAND ONLY, which
                              silently emptied 27 of 28 boxes on the first attempt.
  tools/harvest_wikipedia.py  a plain-text corpus in data/harvest/wp/, registered as
                              sources by REVISION id, so a citation points at the text
                              this project read.
  tools/harvest_commons.py    pictures, licence read per file. CC0 / PD / CC BY /
                              CC BY-SA / FAL only.
  tools/fetch_geo.py          Natural Earth outlines: world.json (countries, 110m),
                              subdiv.json (admin-1 for a few countries), coast.json
                              (10m coastline clipped to the wine regions).

THE PAGES THAT ARE NOT A RECORD
  /map/       every cellar on an Equal Earth world map
  /visit/     the finder: your position or a town, distance-sorted, tag filters
  /numbers/   latitude band, AVA decades, the kin matrix, every published number
  /clones/    the family diagram and the numbered selections
  /search/    the fleet search core, running in the reader's browser
  /coverage/  the scope as an object, including what is missing

WHAT THE VALIDATOR REFUSES
  a source id that is not in the registry · a kin target that does not exist · an
  image licence outside the free-to-use list · a tag at tier tradition or inference ·
  a day listed as both open and closed · a recipe with text under an ingredients-only
  licence · and the banned words: the fluff words this fleet never prints, plus the
  adjudicating vocabulary this subject attracts (authentic, purist, world-class,
  iconic, must-visit, overrated). Report the argument; never join it.

GEOGRAPHY OF THE REPO
  data/nodes/<type>/<id>.json   variety region vineyard producer clone practice
                                pairing person org event term art story
  data/vocab/                   types, facets, regions, tags, recognizers
  data/sources/sources.json     the registry; new-*.json is merged and deleted by build
  cards/                        card masters (gitignored; docs/cards/ is published)
  build/                        generated, gitignored
  docs/                         the published build, committed on purpose


LICENCE
Records, prose and pages: CC BY-SA 4.0. Other layers — upstream data,
pictures, tools — keep their own terms, set out in LICENSE.

COMMERCIAL LICENCE
If share-alike doesn't fit your use — a corpus, a product, a model — a
commercial licence is available. Open an issue and say what you need:
https://github.com/NaNoBotCo/pinot-noir/issues

---

Contact: Nan · nan@motdang.net · Sponsor: ko-fi.com/defiantchiangmai · patreon.com/nanobotco
