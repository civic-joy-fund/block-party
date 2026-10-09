# Block Party

Find a San Francisco street block and its city ID (CNN) for a block party application.
Live site: https://civic-joy-fund.github.io/block-party/

Single page, hosted on GitHub Pages: `index.html` + `data/streets.json`.

## Files

| Path | What it is |
|---|---|
| `index.html` | The whole app (HTML, CSS, JS) |
| `img/civic-joy.png` | Civic Joy Fund logo shown next to the title |
| `data/streets.json` | Compact lookup data built from the DataSF exports (~2.5 MB, ~650 KB gzipped) |
| `data/sf_streets.csv` | DataSF "Streets – Active and Retired" export (source) |
| `data/sf_intersections.csv` | DataSF "Street Intersections" export (source, used for intersection lookups) |
| `scripts/build_data.py` | Rebuilds `data/streets.json` from the CSVs |
| `scripts/match_blocks.py` | Matches free-text block descriptions in a CSV to CNNs |

`data/streets.json`, `scripts/build_data.py`, and `scripts/match_blocks.py` are copies from [burritojustice/sf-blocks](https://github.com/burritojustice/sf-blocks), which keeps the master copy of the street data and matching logic (it's shared with other projects). Block Party doesn't depend on that repo to run or build; the copies are complete. Each script's first lines say which version it came from.

## Data sources

From DataSF:

- **Streets – Active and Retired** → `data/sf_streets.csv`
  https://data.sf.gov/Geographic-Locations-and-Boundaries/Streets-Active-and-Retired/3psu-pn9h/about_data
- **List of Intersections only** → `data/sf_intersections.csv`
  https://data.sf.gov/Geographic-Locations-and-Boundaries/List-of-Intersections-only/sw2d-qfup/about_data

The GeoJSON version of the streets dataset isn't needed; the CSV has the same geometry as WKT.

### How the intersections file is used

The site never loads `sf_intersections.csv` directly. `scripts/build_data.py` reads it and stores, for each intersection CNN, the list of streets that meet there; that list goes into `data/streets.json` next to the intersection's coordinates (which come from the street segments, since the CSV has none). An intersection's CNN is the same number the streets file uses for segment ends (`f_node_cnn` / `t_node_cnn`), and no CNN is both a segment and an intersection.

What it adds beyond the streets file: for about 615 of the ~9,800 intersections, it names a street that no segment in the streets file touches at that corner. Those names appear in the intersection card's "Streets here" line, the intersection's name, the `from_street` column in exports, and the CSV matcher's cross street checks. The site's cross street dropdowns are built from segments, so those names don't appear there.

If the CSV is missing when you rebuild, `build_data.py` prints a warning and falls back to street names taken from the segments; everything still works without those extra names.

Not used yet: the `theOrder` column (the city's order of cross streets along each street), which could replace the distance calculation used to sort the cross street dropdowns.

See also the [striping diagram map](https://burritojustice.github.io/sf-striping/), which uses the same street data.

## Updating the data

The usual way: update sf-blocks (new DataSF exports, rebuild there), then copy its new `data/streets.json` and scripts here.

Or directly here: drop fresh exports into `data/` with the same names, then:

```
python3 scripts/build_data.py
```

To also enable the "flat to moderate" quiet-streets filter, build with slopes (downloads about 250 elevation tiles once, into `.tile-cache/`):

```
python3 scripts/build_data.py --slopes
```

Standard library only. Commit the new `data/streets.json`. If you change `match_blocks.py` or `build_data.py` here, make the same change in sf-blocks so the projects stay in step.

## Matching free-text locations to CNNs

`scripts/match_blocks.py` reads a CSV with a free-text location column (default: "Block you want to party on") and writes a copy with CNN, street, cross streets, address range, supervisor district, neighborhood, WKT geometry, a confidence level, the matching method, and notes. A description naming several blocks becomes several rows (`part` / `parts`).

```
python3 scripts/match_blocks.py applications.csv                       # writes applications_matched.csv
python3 scripts/match_blocks.py applications.csv --column "Location"   # a different column
```

Intersections come back as the intersection's own CNN with a POINT in `wkt` (`type` = intersection), with the touching blocks in `nearby_cnns`.

It understands "X between A and B", "NNN block of X", street addresses, intersections ("Haight and Masonic"), short streets named on their own, and several blocks in one description. Cross streets are checked against the streets that actually meet the named street, so misspellings and missing suffixes usually resolve. Confidence is `high` (street and both cross streets found), `medium` (block number, address, short street, or a spelling fix), `low` (intersection only, one cross street, conflicting details), or `none` (with a reason in `notes`). Review everything below `high`.

## Running locally

`fetch()` doesn't work from `file://`, so serve the folder:

```
python3 -m http.server 8000   # then open http://localhost:8000
```

## Link format (URL hash)

| Hash | Result |
|---|---|
| `#cnn=13060000` (e.g. https://civic-joy-fund.github.io/block-party/#cnn=13060000) | One block, checked, map zoomed to it |
| `#cnn=4883101,4883201` | Several blocks (both sides of a divided street, or a run of blocks) |
| `#street=dolores` | Street filled in, whole street shown |
| `#street=dolores,27th` | That intersection, in intersection mode |
| `#cnn=21900000` | An intersection by its CNN (intersection and block CNNs never overlap) |
| `&all=1` | Include retired, freeway, and paper streets |
| `&minor=0` | Hide pedestrian paths and streets the city doesn't maintain |
| `&quiet=dead,ped,unmaint,res,flat` | Find quiet streets: any of dead ends, pedestrian, not city-maintained; narrowed to residential and flat to moderate |
| `&lang=es` | Interface language, once a translation exists |

Street names in the hash are matched the same way as the search box (case-insensitive, "27th" or "twenty seventh").

## Settings (top of the script in `index.html`)

- `CONFIG.PROTOMAPS_KEY`: swap for the production key.
- `CONFIG.PUBLIC_LAYERS`: street layers shown by default. Anything not listed (freeways, paper streets, pseudo streets, private parking) and anything with `active=false` only appears with the "Include retired…" box checked. Links by CNN always load, whatever the layer.

## Quiet streets, dead ends, one-way

- **Dead end:** a block end where no other drivable street meets it; paper streets (often stairs or unbuilt sections) and pedestrian paths don't count as a way through. About 1,040 blocks.
- **One-way:** `oneway` F = traffic from the `from` street to the `to` street, T = the reverse, B = both ways. The compass direction comes from the line's geometry.
- **Find quiet streets:** the first group adds (any of dead ends, pedestrian streets, not city-maintained); the second group narrows (residential only = road class 5 or 0; flat to moderate = larger of average grade and 80% of the steepest quarter under 10%, needs `--slopes`). Rules live in `QUIET_SHOW` and `QUIET_NARROW` in `index.html`; future conditions (meets a busy street, bus route, protected bike lane) go in `QUIET_NARROW`.

## Terrain and slope

- Hillshade and 3D terrain use AWS Terrarium elevation tiles (`CONFIG.DEM_TILES`, free, no key). The **3D** button tilts the map; `CONFIG.TERRAIN_EXAGGERATION` (default 1.5) makes SF's hills read better.
- Each block card samples elevation at five points (start, ¼, ½, ¾, end) from the same tiles at zoom 15, giving a four-part profile, average slope, and steepest part. This runs in the browser when a card appears. CSV/JSON exports wait for it and include `length_ft`, `elev_from_ft`, `elev_to_ft`, `slope_pct` (signed, from → to), `steepest_pct`, and `profile_ft`.
- Terrarium in SF is about 10 m resolution, so very short blocks (under ~30 m) can show noisy slopes.

## Adding a language

Copy the `en` block in `I18N`, translate the values, and add it as `es`, `zh`, etc. The page picks it from `#lang=` or the browser language. Street names come from the city data and stay in English.
