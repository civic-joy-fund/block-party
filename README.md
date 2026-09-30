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

The GeoJSON export isn't used; the CSV has the same geometry as WKT.

## Updating the data

Drop fresh exports into `data/` with the same names, then:

```
python3 scripts/build_data.py
```

Standard library only. Commit the new `data/streets.json`.

## Matching free-text locations to CNNs

`scripts/match_blocks.py` reads a CSV with a free-text location column (default: "Block you want to party on") and writes a copy with CNN, street, cross streets, address range, supervisor district, neighborhood, WKT geometry, a confidence level, the matching method, and notes. A description naming several blocks becomes several rows (`part` / `parts`).

```
python3 scripts/match_blocks.py applications.csv                       # writes applications_matched.csv
python3 scripts/match_blocks.py applications.csv --column "Location"   # a different column
```

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
| `#street=dolores,27th` | Blocks around that intersection (preview of intersection mode) |
| `&all=1` | Include retired, freeway, and paper streets |
| `&minor=0` | Hide pedestrian paths and streets the city doesn't maintain |
| `&lang=es` | Interface language, once a translation exists |

Street names in the hash are matched the same way as the search box (case-insensitive, "27th" or "twenty seventh").

## Settings (top of the script in `index.html`)

- `CONFIG.PROTOMAPS_KEY`: swap for the production key.
- `CONFIG.PUBLIC_LAYERS`: street layers shown by default. Anything not listed (freeways, paper streets, pseudo streets, private parking) and anything with `active=false` only appears with the "Include retired…" box checked. Links by CNN always load, whatever the layer.

## Terrain and slope

- Hillshade and 3D terrain use AWS Terrarium elevation tiles (`CONFIG.DEM_TILES`, free, no key). The **3D** button tilts the map; `CONFIG.TERRAIN_EXAGGERATION` (default 1.5) makes SF's hills read better.
- Each block card samples elevation at five points (start, ¼, ½, ¾, end) from the same tiles at zoom 15, giving a four-part profile, average slope, and steepest part. This runs in the browser when a card appears. CSV/JSON exports wait for it and include `length_ft`, `elev_from_ft`, `elev_to_ft`, `slope_pct` (signed, from → to), `steepest_pct`, and `profile_ft`.
- Terrarium in SF is about 10 m resolution, so very short blocks (under ~30 m) can show noisy slopes.

## Adding a language

Copy the `en` block in `I18N`, translate the values, and add it as `es`, `zh`, etc. The page picks it from `#lang=` or the browser language. Street names come from the city data and stay in English.
