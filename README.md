# Block Party

Find a San Francisco street block and its city ID (CNN) for a block party application.
Single page, hosted on GitHub Pages: `index.html` + `data/streets.json`.

https://civic-joy-fund.github.io/block-party/

## Files

| Path | What it is |
|---|---|
| `index.html` | The whole app (HTML, CSS, JS) |
| `data/streets.json` | Compact lookup data built from the DataSF exports (~2.5 MB, ~650 KB gzipped) |
| `data/sf_streets.csv` | DataSF "Streets – Active and Retired" export (source) |
| `data/sf_intersections.csv` | DataSF "Street Intersections" export (source, used for intersection lookups) |
| `scripts/build_data.py` | Rebuilds `data/streets.json` from the CSVs |

The GeoJSON export isn't used; the CSV has the same geometry as WKT.

## Updating the data

Drop fresh exports into `data/` with the same names, then:

```
python3 scripts/build_data.py
```

Standard library only. Commit the new `data/streets.json`.

## Running locally

`fetch()` doesn't work from `file://`, so serve the folder:

```
python3 -m http.server 8000   # then open http://localhost:8000
```

## Link format (URL hash)

| Hash | Result |
|---|---|
| `#cnn=13060000` | One block, checked, map zoomed to it |
| `#cnn=4883101,4883201` | Several blocks (both sides of a divided street, or a run of blocks) |
| `#street=dolores` | Street filled in, whole street shown |
| `#street=dolores,27th` | Blocks around that intersection (preview of intersection mode) |
| `&all=1` | Include retired, freeway, and paper streets |
| `&lang=es` | Interface language, once a translation exists |

Street names in the hash are matched the same way as the search box (case-insensitive, "27th" or "twenty seventh").

## Settings (top of the script in `index.html`)

- `CONFIG.PROTOMAPS_KEY`: swap for the production key.
- `CONFIG.PUBLIC_LAYERS`: street layers shown by default. Anything not listed (freeways, paper streets, pseudo streets, private parking) and anything with `active=false` only appears with the "Include retired…" box checked. Links by CNN always load, whatever the layer.

## Adding a language

Copy the `en` block in `I18N`, translate the values, and add it as `es`, `zh`, etc. The page picks it from `#lang=` or the browser language. Street names come from the city data and stay in English.
