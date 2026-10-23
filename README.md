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
| `layers/` | Raw downloads for the map layers (Muni, bike network, schools, fire/police, health care) |
| `data/layers/*.geojson` | Trimmed copies the map loads (~1.7 MB total, ~230 KB gzipped) |
| `data/boundaries/` | Neighborhood boundary sets (Analysis, SF Find, Planning, Realtor, Who's on First), copied from civic-joy-fund/joiner; `build_data.py --areas` tags blocks with them |
| `reference/` | Non-map reference lists, kept as published (SF Planning's neighborhood group notification list) |
| `scripts/build_neighborhood_groups.py` | `reference/neighborhood-groups/` → `data/neighborhood_groups.json` |
| `scripts/build_layers.py` | Rebuilds `data/layers/` from `layers/` |

`data/streets.json`, `scripts/build_data.py`, and `scripts/match_blocks.py` are copies from [burritojustice/sf-blocks](https://github.com/burritojustice/sf-blocks), which keeps the master copy of the street data and matching logic (it's shared with other projects). Block Party doesn't depend on that repo to run or build; the copies are complete. Each script's first lines say which version it came from.

## Data sources

From DataSF:

- **Streets – Active and Retired** → `data/sf_streets.csv`
  https://data.sf.gov/Geographic-Locations-and-Boundaries/Streets-Active-and-Retired/3psu-pn9h/about_data
- **List of Intersections only** → `data/sf_intersections.csv`
  https://data.sf.gov/Geographic-Locations-and-Boundaries/List-of-Intersections-only/sw2d-qfup/about_data

Both CSVs are committed so anyone can rebuild `streets.json` right away. If one is missing, `scripts/build_data.py` downloads it from DataSF's API; `python3 scripts/build_data.py --download` refreshes both before building. The dataset ids and pages are also at the top of the script. `build_data.py` reads and writes only inside this repo (`data/` next to `scripts/`), wherever you run it from.

The GeoJSON version of the streets dataset isn't needed; the CSV has the same geometry as WKT, so `data/sf_streets.geojson` (18 MB) can be removed.

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
python3 scripts/build_data.py --slopes --areas
```

`--areas` tags each block with its neighborhoods from `data/boundaries/` (the card's Neighborhood row and the neighborhood groups use them).

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
| `&layers=muni:always,bike:off,contours:on` | Map layer settings that differ from the defaults (each layer `off`, `close`, or `always`; contours `off` or `on`) |
| `&lands=school,park,port` | City-owned land categories shown, when different from the default (`none` for none) |
| `&lang=es` | Interface language, once a translation exists |

Street names in the hash are matched the same way as the search box (case-insensitive, "27th" or "twenty seventh").

## Settings (top of the script in `index.html`)

- `CONFIG.PROTOMAPS_KEY`: swap for the production key.
- `CONFIG.PUBLIC_LAYERS`: street layers shown by default. Anything not listed (freeways, paper streets, pseudo streets, private parking) and anything with `active=false` only appears with the "Include retired…" box checked. Links by CNN always load, whatever the layer.

## Quiet streets, dead ends, one-way

- **Dead end:** a block end where no other drivable street meets it; paper streets (often stairs or unbuilt sections) and pedestrian paths don't count as a way through. An end that touches another drivable street's line within 1.5 m counts as open even without an intersection in the data (Comerford St between Church and Sanchez); freeways and ramps don't count. About 1,020 blocks.
- **One-way:** `oneway` F = traffic from the `from` street to the `to` street, T = the reverse, B = both ways. The compass direction comes from the line's geometry.
- **Find quiet streets:** the first group adds (any of dead ends, pedestrian streets, not city-maintained); the second group narrows (residential only = road class 5 or 0; flat to moderate = larger of average grade and 80% of the steepest quarter under 10%, needs `--slopes`). Rules live in `QUIET_SHOW` and `QUIET_NARROW` in `index.html`; future conditions (meets a busy street, bus route, protected bike lane) go in `QUIET_NARROW`.

## Map layers

The **Layers** menu on the map has Off / Close up / Always for each layer, plus Contours (Off / On). "Close up" (the default) shows a layer from zoom 16 in (`CLOSE_ZOOM`); names and route numbers appear from there too, or from zoom 14 with "Always". Each file loads the first time its layer is about to show.

| Layer | DataSF dataset (download into `layers/`) | Style |
|---|---|---|
| Muni routes | [Muni Simple Routes](https://data.sf.gov/Transportation/Muni-Simple-Routes/9exe-acju/about_data) (`9exe-acju`), GeoJSON | Pale orange band along the street (under basemap labels), orange route-number shields. Solid on the map so overlapping routes don't darken; see-through orange over satellite |
| Bike network | [MTA Bike Network Linear Features](https://data.sf.gov/Transportation/MTA-Bike-Network-Linear-Features/ygmz-vaxd/about_data) (`ygmz-vaxd`), GeoJSON | Dark green #1A7F37 (light green over satellite). Separated bikeway 3 px, bike lane and path 2 px, bike route and Neighborway dashed 1.6 px (at zoom 16). Label like "Separated bikeway · parking, posts" |
| City-owned land | [City Lands](https://data.sf.gov/City-Infrastructure/City-Lands/gtnh-hgvs/about_data) (`gtnh-hgvs`), GeoJSON | Parcels with a faint (9%) tint and thin outline in their category's color, under the basemap labels; parks get a dashed green outline and no tint, since the basemap already shades them. Names close up; hover shows name, category, department, and address. Checkboxes under the layer pick categories: on by default Schools, Parks, Fire, Police, Health, Open space (any non-park parcel named "Open Space"); off by default Port, Library, MTA, Public Works, Water and sewer (PUC), Housing Authority, Real Estate, Former Redevelopment (OCII), Other. Category mapping is `LAND_CATS` in `build_layers.py` and `index.html`. Outlines are simplified by 0.5 m. Doesn't include private schools or hospitals |
| Parcels (land use or zoning) | `data/Land_Use_with_Active_Parcel_Information.pmtiles`, built with tippecanoe from [Land Use with Active Parcel Information](https://data.sf.gov/Geographic-Locations-and-Boundaries/Land-Use-with-Active-Parcel-Information/h5vv-2u24/about_data) (`h5vv-2u24`). **Land use is SF Planning's 2023 survey**, updated every few years. | Parcels tinted by `landuse`, about 32% opacity, from zoom 15; off by default. Residential yellow, mixed residential orange, mixed (no housing) tan, retail and entertainment purple, office blue, cultural/institutional/education dark blue, medical red, hotels red-orange, industrial (PDR) grey-violet, open space green, vacant grey. Off / Land use / Zoning. Zoning in SF Planning's own colors by zoning code (`ZONING` in `index.html`, from the Zoning Map's Zoning Districts layer). Labels from zoom 16, one per run of same-kind lots on an assessor block. Block cards summarize zoning, lots, homes, and land use for the lots beside the block (`Parcels` in `index.html`), and those lots are outlined in white when the block is checked |
| Slow Streets | [Slow Streets](https://data.sf.gov/Transportation/Slow-Streets/hkz3-itiu/about_data) (`hkz3-itiu`), GeoJSON | Dotted blue #2457D6 (light blue over satellite), planned blocks fainter, "Slow Street" label. One record per block with its CNN; blocks marked `slw_st = 0` (planned, then dropped) are left out. Blocks on one get a "Slow Street" row on their card and a line in the hover popup, with the corridor (`extents`) |
| Schools | [Schools](https://data.sf.gov/Economy-and-Community/Schools/7e7j-59qk/about_data) (`7e7j-59qk`), GeoJSON, plus columns added after download: `short_name`, elevation, and (coming) enrollment from the California Department of Education. That join will be documented with its own workflow, possibly a separate repo | Brown #8A5A00 square, `short_name` |
| Fire and police | [City-owned Facilities: Fire and Police](https://data.sf.gov/City-Infrastructure/City-owned-Facilities-Fire-and-Police/wt27-4jim/about_data) (`wt27-4jim`), CSV | Red #C92A2A "F" / navy #1E3A8A "P", `common_name` |
| Hospitals and clinics | [Health Care Facilities](https://data.sf.gov/Health-and-Social-Services/Health-Care-Facilities/jhsu-2pka/about_data) (`jhsu-2pka`), CSV | Dark teal #0B7285: "H" square for hospitals, "+" circle for clinics, facility name |

Block cards also list what the block is **next to** (`Nearby` in `index.html`): city-owned parcels it runs alongside (at least 2 of the points sampled every ~10 m along the block, ignoring the last 10% at each end, within 20 m of the parcel or inside it), plus schools, stations, and health facilities from the point layers within 35 m; exported as `next_to`.

Hovering a street adds the block's Muni routes (with service type) and bike facility to the popup, and block and intersection cards list them too (also in exports as `muni_routes` and `bike_facility`). Hovering a point shows its name and type.

Bike facilities join to blocks by the `cnn` in the bike data. Muni lines have no CNN, so `Transit` in `index.html` matches them when the files load: a route runs along a block when it's within 15 m (`MATCH_M`) at 25%, 50%, and 75% of the way along and heading the same way within 30°, which keeps out routes that only cross at a corner. An intersection lists routes within 15 m of the corner. Route shields come from the same matching, one per block listing every route on it. Later, GTFS can replace the route lines as the input; the block matching stays the same.

To update: run `python3 scripts/build_layers.py`. Any dataset with no file in `layers/` is downloaded from DataSF's API first (named like an Export, `Slow_Streets_20261013.geojson`); `--download` fetches fresh copies of all of them except schools, whose file has hand-added columns. A manual Export from the dataset page works too: save it into `layers/` without renaming it. The script finds each by its title and uses the newest date stamp, so old downloads can stay or go. The dataset list (title, id, URL) is `SOURCES` at the top of the script, and each built file in `data/layers/` records which dataset and download it came from, plus the data's "as of" date where the download has one. The script keeps only the fields the map uses and rounds coordinates to about 1 m. Muni lines are passed through as published, one line per route and direction, except the rail-replacement bus patterns (FBUS, KBUS, NBUS, TBUS), which are dropped.

Later, the script can pull these straight from the Socrata API using the same ids (`https://data.sf.gov/resource/<id>.geojson`), so Muni and bike routes stay current without hand downloads.

Known limits: Muni Metro lines include their subway and tunnel sections (Market St subway, Twin Peaks and Sunset tunnels, Central Subway), so those show on the streets above. The Central Subway also puts the T on Stockton St blocks, and the Market St subway puts J, K, L, M, N on Market's blocks.

The layers are small enough to load as GeoJSON. For offline use or bigger layers, the same files can go into one PMTiles file instead (needs a server with HTTP range requests, which `python3 -m http.server` doesn't do):

```
tippecanoe -o data/layers.pmtiles --force -Z11 -z16 --no-line-simplification \
  --no-feature-limit --no-tile-size-limit -r1 \
  -L muni:data/layers/muni.geojson -L bike:data/layers/bike.geojson \
  -L schools:data/layers/schools.geojson -L stations:data/layers/stations.geojson \
  -L health:data/layers/health.geojson
```

## Terrain and slope

- Hillshade and 3D terrain use AWS Terrarium elevation tiles (`CONFIG.DEM_TILES`, free, no key). The **3D** button tilts the map; `CONFIG.TERRAIN_EXAGGERATION` (default 1.5) makes SF's hills read better.
- Each block card samples elevation at five points (start, ¼, ½, ¾, end) from the same tiles at zoom 15, giving a four-part profile, average slope, and steepest part. This runs in the browser when a card appears. CSV/JSON exports wait for it and include `length_ft`, `elev_from_ft`, `elev_to_ft`, `slope_pct` (signed, from → to), `steepest_pct`, and `profile_ft`.
- Terrarium in SF is about 10 m resolution, so very short blocks (under ~30 m) can show noisy slopes.

## Adding a language

Copy the `en` block in `I18N`, translate the values, and add it as `es`, `zh`, etc. The page picks it from `#lang=` or the browser language. Street names come from the city data and stay in English.
