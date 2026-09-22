# Pinot Country

A structured directory of pinot noir: the vine and its mutations, the regions and
appellations, named vineyards, cellars, clones, vineyard and cellar practice, the
people, the words — and what gets eaten beside it.

**Live: https://nanobotco.github.io/pinot-noir/**

One JSON record per node, one folder per type, no database and no framework. Every
field carries a provenance tier, and every record says what its neighbours are to it
in its own words — the neighbour answers back on the same card.

```
data/nodes/<type>/<id>.json     the records
data/sources/sources.json       every source a record may cite, by id
data/harvest/                   OpenStreetMap cellars, 27 CFR part 9, a Wikipedia corpus
tools/                          validate → build → cards → site (stdlib Python + Pillow)
docs/                           the published site, served by GitHub Pages
```

## What is in it

| | |
|---|---|
| records | 143 across 13 types |
| regions | 34, from the Côte de Nuits to Central Otago |
| cellars on the map | ~3,000, curated plus OpenStreetMap |
| sources | 182, each cited by id — Wikipedia by revision |
| kin links | 386, every one written by hand in both directions |

## Provenance, in five tiers

`cited` a named source, linked · `harvested` pulled from an open dataset with its
licence · `tradition` general knowledge of the trade, hedged in the text · `inference`
this project's own reasoning · `field` somebody stood there.

The rules that follow from that: a tag on a cellar names its evidence and is never
inferred from a name or a photograph; a day nobody published is drawn dashed and never
counted as closed; every American appellation date comes from the Federal Register
notice in 27 CFR part 9, and a test fails the build if a record disagrees with it.

## The long read

[Tri-tip over red oak](https://nanobotco.github.io/pinot-noir/story/tri-tip-over-red-oak/) —
one California valley cooks beef over local oak and grows pinot noir on the hills that
oak comes off. The ranch barbecue, the butcher's cut five different people claim, the
wood that cannot ship, and what happens when a thin-skinned grape meets a salted,
charred, medium-rare piece of bottom sirloin.

## Running it

```sh
python3 tools/validate.py          # every record, against schema/node.schema.json
python3 tools/build.py             # records + harvests → build/api
python3 tools/cards.py             # 1200×630 share cards
python3 tools/site.py              # build/api → build/site
python3 tools/serve.py 8803        # look at it
python3 -m unittest discover -s tests
./publish.sh                       # the whole chain, into docs/
```

`BUILD_DRAFT=1` lets the build run while kin targets are still unwritten. Never for a
publish.

## Licences

Records CC BY 4.0. Cellar points OpenStreetMap, ODbL 1.0. Appellation data public
domain. Pictures carry their own licence, per file. Code MIT. See `LICENSE`.

**Using it.** Attribution is the whole of the condition — copy it, adapt it,
sell it, index it, train on it, and say where it came from.
[Open an issue](https://github.com/NaNoBotCo/pinot-noir/issues) if something is missing.

---

Contact: Nan · nan@motdang.net · Sponsor: [Ko-fi](https://ko-fi.com/defiantchiangmai) · [Patreon](https://www.patreon.com/nanobotco)

<!-- fleet-roster -->

## Elsewhere from the same publisher

- [Mot Dang](https://motdang.net/) — city directory for Chiang Mai and Chiang Rai
- [The Mae Hong Son Loop](https://nanobotco.github.io/mae-hong-son-loop/) — motorcycling the 600 km loop out of Chiang Mai — curves counted, air measured
- [Muay Thai](https://motdang.net/muay-thai/) — the eight limbs, the thirty named techniques, the ceremony, and every gym on the map
- [Roads of Chiang Mai](https://motdang.net/roads/) — the square of 1296, four rings, and what each one did to the city — counted from the map
- [wichaa](https://wichaa.net/) — Lanna manuscripts, the amulet market, and the traditions around them
- [Hand Poke](https://nanobotco.github.io/hand-poke/) — 28 traditions of marking skin by hand — the leg-tattoo zone of Burma, the Shan States and Lanna, counted
- [Black Holes, Drawn](https://nanobotco.github.io/black-holes/) — black holes modelled and drawn from the equations — generators, the past, present and future, the legends
- [Quantum Computing, plainly](https://nanobotco.github.io/quantum-computing/) — the history and theory of quantum computing in plain words, with demos; refreshed weekly
- [Goin' Fast](https://nanobotco.github.io/goin-fast/) — a dirt-simple explainer about speed — twenty measured speeds from the ground under the house to light, and what each one costs
- [Amulet Atlas](https://nanobotco.github.io/amulet-atlas/) — amulets, charms and talismans worldwide
- [Carolina Barbecue](https://nanobotco.github.io/carolina-barbecue/) — barbecue in North and South Carolina
- [Wing Country](https://nanobotco.github.io/buffalo-wings/) — the American chicken wing
- [Pink Box](https://nanobotco.github.io/pink-box/) — the American mom-and-pop donut shop
- [Basque Tables](https://nanobotco.github.io/basque-tables/) — Basque dining rooms of California, Nevada and Idaho
- [Care Abroad](https://nanobotco.github.io/care-abroad/) — treatment across borders, with published prices and their dates
- [Thai Roots](https://nanobotco.github.io/thairoots/) — a root dictionary of Thai, with a word decomposer
- [The index](https://nanobotco.github.io/index/) — every corpus, site and repository, counted
- [Uptake](https://nanobotco.github.io/uptake/) — a field manual on publishing for machines that copy
- [NaNoBotCo](https://nanobotco.github.io/) — the portal
- [ฮักฝรั่ง](https://hakfarang.net/) — เรื่องเงิน วีซ่า และชีวิตกับแฟนฝรั่ง
- [Offrampt](https://offrampt.net/) — turning crypto into spendable local money, Thailand first

All of it, counted: https://nanobotco.github.io/index/ · roster as JSON: https://nanobotco.github.io/index/fleet.json
