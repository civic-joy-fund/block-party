# Changelog

All changes are in `index.html` unless noted. `data/streets.json` and `scripts/build_data.py` are unchanged since v1.

## v35
- **Neighborhoods on cards:** one Neighborhood row shows the Analysis neighborhood; click it for every set the block falls in: Analysis, SF Find, Planning, Realtor, Who's on First, and the streets file's own (DPW) neighborhood. A block on a boundary lists both sides. Replaces the separate Neighborhood (which was the streets file's DPW/realtor-style name) and Analysis neighborhood rows. Exports add `hood_analysis`, `hood_sffind`, `hood_planning`, `hood_realtor`, `hood_wof`.
- `data/streets.json` gains those `hood_*` fields (`build_data.py --areas`, from sf-blocks 2026.10.23), from boundary files in the new `data/boundaries/` (copied from civic-joy-fund/joiner). `planning_neighborhoods.geojson` moved there from `data/layers/`. Neighborhood groups use the block's `hood_planning`.
- Lot outlines on checked blocks only show while the Parcels layer is on (Land use or Zoning).

## v34
- **Neighborhood groups** on block and intersection cards: the groups on SF Planning's notification list for the block's Planning Neighborhood, behind a link that expands (organization, contacts, emails), with citywide groups in their own expandable list and a "Copy list" button. A block on a boundary lists both neighborhoods. Data: `data/neighborhood_groups.json`, built by `scripts/build_neighborhood_groups.py` from the copy in the new `reference/neighborhood-groups/` folder (list of September 25, 2026); boundaries `data/boundaries/planning_neighborhoods.geojson` (DataSF `mw29-m2za`, copied from civic-joy-fund/joiner). Exports add `planning_neighborhood` and `neighborhood_groups` (count).
- **Zoning colors are now SF Planning's own**, from the Zoning Map's Zoning Districts layer (`PlanningData/MapServer/3`), matched by zoning code; the map key lists the families with one of their colors each.

## v33
- **Parcels** layer (was "Land use and zoning") is now **Off / Land use / Zoning**. Zoning colors parcels by zoning code family: houses (RH) yellow, apartments (RM, RTO, RC) orange, neighborhood commercial (NC, NCT, NCD) pink, downtown and community business (C-2, C-3, Chinatown) red, industrial (PDR, M) purple, mixed use (UMU, MUG, MUO, MUR, SoMa) orchid, public (P) blue, special plan areas grey. Provisional palette until we have SF Planning's. Links from v32 with `landuse:on` open in Land use.
- Parcel labels from zoom 16: one label per run of same-kind lots on an assessor block (land use name, or zoning code), placed in the middle of the run, so a block of 30 RH-2 houses gets one "RH-2" instead of 30.
- Map key: the land use / zoning row expands (click) into a color table for the current mode.
- Checking a block outlines the lots counted on its card in white (from zoom 15, whether or not the Parcels layer is on). Zoning on the card gets a color swatch.
- Hovering the "Block Party" title shows the build number.

## v32
- **Land use and zoning** layer from `data/Land_Use_with_Active_Parcel_Information.pmtiles` (SF Planning land use 2023 joined to active parcels, DataSF `h5vv-2u24`): parcels tinted by land use with faint outlines, off by default (Off / On in the Layers menu, with a color key), drawn from zoom 15. Hovering a parcel shows its lot, land use, homes, and zoning. Loaded with the PMTiles library (4.5.0), which needs a server with range requests (GitHub Pages; `npx http-server` locally, not `python3 -m http.server`).
- Block cards add **Zoning** (districts with lot counts), **Parcels** (lots and homes), and a **Land use** table, read from the same file for the lots beside the block, whether or not the layer is on. Lots count when they're within 14 m of the middle 70% of the block's centerline, or 25 m when their address is on the block's street; lots are counted once per map block-lot, since condos repeat. Copy-card text and exports add `lots`, `homes`, `land_use_2023`, and `zoning`.

## v31
- Basemap: hides Mission Creek and other creeks OSM tags as rivers (some run underground), ported from Selecter. Streams are hidden, and river lines and waterway labels named "Creek" or "Arroyo" are filtered out. The style's own river/stream filter is kept and added to rather than replaced.

## v30
- **Next to** on block cards: the city-owned land the block runs alongside (Mission Dolores Park, Parks), plus schools, fire and police stations, and health facilities from the point layers within 35 m, which adds private schools and clinics City Lands leaves out. A parcel counts when at least 2 points sampled every ~10 m along the block (ignoring the last 10% at each end) are inside it or within 20 m of its edge, so parcels across a cross street don't count. Intersection cards list what's within 20 m of the corner. Lists every category, whatever the map's checkboxes say. Copy-card text and exports add `next_to`.

## v29
- **City-owned land** layer (DataSF City Lands, `gtnh-hgvs`): parcel polygons with a faint tint and thin outline, under the basemap labels, with Off / Close up / Always. Category checkboxes under it in the Layers menu; Schools, Parks, Fire, Police, Health, and Open space are on by default, and Port, Library, MTA, Public Works, Water and sewer, Housing Authority, Real Estate, Former Redevelopment, and Other can be turned on. Parks get a dashed outline only. Hovering a parcel (away from streets and icons) shows its name, category, department, and address. Links keep non-default categories as `&lands=…`.
- `build_layers.py` builds `data/layers/lands.geojson` (downloaded automatically when missing), keeping name, category, department, and address, and simplifying outlines by 0.5 m.

## v28
- `build_layers.py` downloads any missing dataset from DataSF's API before building (like `build_data.py` does for the street CSVs); `--download` refreshes all of them except schools. CSV columns are read case-insensitively, so API downloads and site Exports both work.
- **Slow Streets** layer (DataSF `hkz3-itiu`): dotted blue line, planned blocks fainter, in the Layers menu with Off / Close up / Always like the others. Blocks on a Slow Street get a "Slow Street" card row and popup line with the corridor; exports add `slow_street`. Intersection cards list it when any block meeting there is on one.
- `build_layers.py` builds `data/layers/slow.geojson` from a "Slow Streets" download in `layers/`, leaving out blocks marked as removed (`slw_st = 0`). Until that file exists, the layer and rows just stay empty.

## v27
- **Dead ends:** an end that touches another street's line (within 1.5 m) counts as open even when the city data has no intersection there. Comerford St now reads "Church St to Sanchez St" and isn't a dead end; Gaiser Ct reads "Guerrero St to dead end". 36 block ends in all, mostly private streets around Stonestown, Sunnyside, and Mission Terrace. Freeways and ramps don't count, since they pass over or under streets. The quiet-streets dead-end count drops from about 1,040 to 1,020.
- Where the city names such an end "START: 1-99 BLOCK" or "END: …", the card, popup, and exports use the street it touches instead.
- Hover popup shows the block's slope and tier ("Slope 22.7% average, steepest 25.9% · Extremely steep"), from the slopes in `streets.json`.
- Bike info on cards and the popup labels the barrier: "Separated bikeway · barrier: curb, posts".
- School, station, and health care icons are about 25% larger; Muni shield numbers one size up.

## v26
- **Muni and bike on cards:** block cards list the Muni routes running along the block, grouped by service type (14, 49 Frequent Local · 14R Rapid Bus …), and the block's bike facility. Intersection cards list the routes through the corner and the bike facilities on the streets meeting there. Shown whether or not the map layers are on; "Checking…" until the files load.
- Hover popup shows each route's service type: "Muni 14, 49 (Frequent Local) · 14R (Rapid Bus) · 714 (Specialized)".
- **Route shields list every route on a block** ("14 · 14R · 49 · 714") instead of one per route line, where overlapping shields hid all but one. Busier blocks win when shields collide.
- Muni routes are matched to blocks in the browser: a route counts when it's within 15 m of the block at 25%, 50%, and 75% along and heading the same way, so routes crossing at a corner don't count. Bike facilities use the CNN already in the bike data.
- The copy-card text and CSV/JSON exports add `muni_routes` and `bike_facility`.
- `data/streets.json` rebuilt from DataSF on 2026-10-11 with slopes (6 new blocks).

## v25
- **Map layers:** Muni routes, bike network, schools, fire and police stations, hospitals and clinics. New **Layers** menu on the map: Off / Close up (zoom 16 and in, the default) / Always for each. Contours moved into the same menu (Off / On). Links keep non-default settings as `&layers=muni:always,contours:on`.
- Muni is a pale orange band with route-number shields; bike lanes dark green (solid for separated bikeways, lanes, and paths; dashed for shared routes); schools, stations, and health care as small icons with names close up. Map key rows appear while a layer shows.
- Hovering a street also lists the Muni routes there and the block's bike facility ("Separated bikeway · parking, posts"). Hovering a school, station, or clinic shows its name and type.
- **Quiet streets** moved from the header onto the map toolbar as a yellow "✦ Quiet streets ▾" button with a match count; its panel drops down over the map. Matches are now magenta (#B5179E) instead of green, which was hard to tell from parks and now the bike lanes.
- New `scripts/build_layers.py` builds `data/layers/*.geojson` from the raw downloads in `layers/`.
- `scripts/build_data.py` updated from sf-blocks 2026.10.11: downloads `data/sf_streets.csv` and `data/sf_intersections.csv` from DataSF when missing (`--download` to refresh), with the dataset pages listed in the script. Dates are stored as YYYY-MM-DD, so a retired block reads "Retired 2013-11-07" whichever way the CSV was downloaded.
- `.gitignore` also covers `.DS_Store`, `__pycache__/`, `*.pyc`, and partial downloads.
- `build_layers.py` lists each layer's DataSF dataset (title, id, URL) and finds downloads by dataset title with DataSF's date stamp, so new downloads don't need renaming. Built files record their source dataset, file, and "as of" date. Map credits DataSF for the layers.

## v24
- Fixed: the map hover popup and the "Blocks leading into it" rows under intersection cards now say "Myra Way to dead end" like the cards do, instead of naming the street itself as the cross street.

## v23
- **One-way streets:** cards show "One-way ↑ northbound, 18th St → 17th St" (from the `oneway` field: F = from street to to street, T = the reverse). Arrows along one-way streets on the map from zoom 15; new "One-way" row in the map key.
- **Dead ends:** a block end with no other drivable street (paper streets and stairs don't count) reads "Church St to dead end", with a green "Dead end" pill.
- **Road class** pill: Residential, Collector, Arterial, Major street, Freeway, Freeway ramp (none for class 0, which already has a private / paper / pedestrian pill).
- **Copying text:** dragging to select text no longer checks or unchecks a card, and clicks in the details, chart, or pills don't toggle it. New ⧉ button copies the whole card as plain text.
- **Find quiet streets** (under the intro): show any of dead ends, pedestrian streets, streets the city doesn't maintain; narrow to residential only (leaves out collectors, arterials, and bigger) and flat to moderate (under 10%). Matches light up green on the map with a count; tap one to add it. Links keep it as `&quiet=dead,res`. Matches stay clickable even when the Options hide minor streets.
- The "flat to moderate" filter only appears when `streets.json` has slopes (`build_data.py --slopes`).
- Exports add `road_class`, `oneway`, `oneway_direction`, and `dead_end` (the cross street at the dead end, or "both ends").
- `scripts/build_data.py` updated from sf-blocks 2026.10.08 (optional `--slopes`).

## v22 (housekeeping)
- The striping diagram map moved to its own repo, [burritojustice/sf-striping](https://github.com/burritojustice/sf-striping) (https://burritojustice.github.io/sf-striping/). Removed `striping/`, its data files, scripts, and workflows from this repo.
- The street data and matching scripts now have a master copy in [burritojustice/sf-blocks](https://github.com/burritojustice/sf-blocks). This repo keeps its own copies (`data/streets.json`, `scripts/build_data.py`, `scripts/match_blocks.py`), marked with the version they came from, so Block Party still stands alone.
- Removed `.github/workflows/` (only the striping jobs used it).

## v21
- **Intersection mode.** The mode switch is now Cross streets / Intersection / Address. Pick a street and a cross street to select the intersection itself (its CNN is the city's intersection CNN). Streets that meet more than once get one card per intersection, tagged by side.
- Intersection cards show the streets that meet there, supervisor district, ZIP, neighborhoods (both values when the corner sits on a boundary), and elevation.
- Blocks leading into a selected intersection appear as compact rows under "Blocks leading into it," with a direction tag; checking one turns it into a full block card.
- Map: selected intersections are pink with a yellow ring and a name/CNN label; unchecked ones are a dashed purple ring; hovering a cross street in the list previews the corner in purple. Every corner is a clickable dot from zoom 16.
- Cross street lists now include every street that meets at an intersection, not just the one named on each block (for example Mullen Ave at Montcalm St).
- `#cnn=` accepts intersection CNNs; `#street=dolores,27th` opens that intersection, picking 27th St or 27th Ave by which one actually meets Dolores.
- CSV/JSON exports add `type` (block or intersection) and `wkt` (LINESTRING or POINT).
- Map key uses the combined layout: Your blocks / intersections, Matches, Preview, Cross streets, Your whole street, Corners, Other streets, and "20 ft contours."
- Only checked blocks get the large stacked map label once anything is checked.

## Matcher
- `scripts/match_blocks.py` (new): matches free-text block descriptions in a CSV to CNNs, with street, cross streets, address ranges, WKT, confidence, method, and notes.
- Intersections ("Haight and Masonic") return the intersection CNN and a POINT, marked high when the streets meet once; the touching blocks go in `nearby_cnns`. New `type` column.
- Streets with gaps in the city data (15th St between Florida and Alabama) match by position along the street; directional names ("South Van Ness", "West Portal") and exact names like "Front St" resolve; intersection points a few meters apart are treated as one.


## v20
- Fixed: the Options panel ignored its toggle and was always open. Elements with display rules (Options panel, legend contours row, bottom Clear selections) now respect `hidden`.

## v19
- Civic Joy Fund logo next to the "Block Party" title (`img/civic-joy.png`, new file).
- Start over and Clear selections are small buttons, on one line with an **Options** toggle on the right. Options opens two checkboxes:
  - "Include pedestrian paths and streets the city doesn't maintain" (new, checked by default). Unchecked, it hides pedestrian paths, private streets, and segments the city data marks as not accepted. Presidio and Fort Mason roads always stay visible. URL: `&minor=0`.
  - "Include retired, freeway, and paper streets" (moved here).
- Results: a full-width "Apply for a Block Party" button (placeholder; shows a "coming soon" note), with small CSV / JSON / Link copy buttons under it. The bottom Clear selections is a small button too.
- Map key shows a contours row ("Contours, every 20 ft") while contours are on and visible, with the interval for the current zoom and a swatch that matches map or satellite mode.

## v18
- "The other cross street" list shows the direct matches (the other end of each block touching the first cross street) first, then a "Further along" separator, then the remaining cross streets in italics.

## v17
- Contours at 80% opacity.
- In satellite mode, the basemap's labels (street names, neighborhoods, places) move above the imagery so people don't get disoriented, and drop back under it on the map view.
- Contours also draw above the satellite imagery, just under the labels. They turn pale yellow on satellite so they stay distinct from the white clickable streets, and are white on the map view.

## v16
- Contour lines back to their original width (0.6–0.9 px), at 70% opacity.
- Contours now sit under the basemap's labels.

## v15
- Contours changed to white so they stand apart from the blue-gray clickable streets; elevation labels warm gray with a white halo.

## v14
- Clearing "Your street" with the × keeps the current map view. Only "Start over" zooms back to the whole city.

## v13
- **Memory:** the elevation tile cache is capped at the 48 most recent tiles, stores elevation at half the size (Int16 decimeters instead of RGBA), and reuses one canvas. MapLibre's tile cache is capped at 150 tiles per source.
- "Clear selections" also appears at the bottom of the card list, shown only when there are cards.
- Cross streets on the map show one block on each side of the selection instead of two.

## v12
- Contour spacing restored to 40 / 20 / 10 ft at zoom 13 / 14 / 15, labeled every 200 / 100 / 50 ft.
- Contours only appear from zoom 13 in (`CONTOUR_MINZOOM`).

## v11
- Selected-block map labels read "2–79 Duncan St" on the first line (lowest and highest address on the block) with the CNN below. Separate even/odd ranges stay in the hover popup.
- Contours: all lines drawn the same (no major lines), denser spacing, elevation labels on every fifth line.
- Hillshading turns off while contours are on.

## v10
- Hovering a card highlights its block on the map and pans to it if it's out of view.
- Hovering a block on the map outlines its card and scrolls the list to it after a short pause if it's off screen.
- Selected-block labels are stacked (street, CNN, address ranges) at the block's midpoint and rotated to run along the street.
- Hover popup shows address ranges, even range first ("900–988, 901–989").

## v9
- 3D terrain stays on at every tilt, so tilting no longer jumps.
- Street-following labels (basemap, ours, contours) are printed on the ground instead of standing up, which keeps them from twisting on terrain.
- Past 30° of tilt, labels switch to flat-on-screen labels at each block's midpoint.
- Test switches in the query string: `?labelalign=viewport` and `?label3d=45`.
- Legend reordered and shortened: Your blocks, Cross streets, Block matches, Block preview, Your whole street, Block ends, Other streets, plus a "Tap any street to add it" hint.

## v8
- Terrain only while tilted, with midpoint labels at any tilt (replaced in v9).
- Dashed "block matches" line has visible gaps on the map and in the legend.
- Legend splits "Your whole street" and "Block preview" into separate entries.
- **Contours toggle**, ported from Selecter: maplibre-contour v0.1.0 on the Terrarium tiles, feet, including Selecter's Safari ArrayBuffer workaround.

## v7
- When the map is tilted past 15°, street-following labels are hidden and replaced with flat-on-screen labels at each block's midpoint (threshold changed in v8 and v9).
- × on each card removes it from the list and the map.
- Map legend ("Map key") replaces the "tap a street" tip; collapsed by default on phones.

## v6
- Elevation chart width depends on block length: under 400 ft = 62% of the card, 400–600 ft = 81%, 600 ft and up = full width (`PROFILE_BUCKETS`).
- The same grade draws at the same angle in every bucket, so short charts have headroom for steeper grades before squeezing.
- Quarter labels drop the decimal at 10% and up.

## v5
- "Clear selections" below "Start over": empties the list and the cross street / number fields, keeps the street and the map view.
- Hovering a cross street in either dropdown previews the matching blocks on the map (purple) and the cross street (teal).
- Clicking a block on the map scrolls to its card and flashes it.

## v4
- Elevation chart uses one scale for every block: a 30% climb fills the chart height (`PROFILE_MAX_GRADE`).
- Dashed reference lines at 5%, 10%, 20%, and 30%, fanning out from the block's low end.
- Blocks too steep to fit are squeezed and get a zigzag break mark on the left edge plus a "Not to scale" caption.
- Eight slope tiers: Flat (<2%), Gentle (2–5%), Moderate (5–10%), Steep (10–15%), Very steep (15–20%), Extremely steep (20–25%), Ridiculously steep (25–30%), Ludicrously steep (30%+).

## v3
- Street labels stay upright facing the screen when the map is tilted, using Selecter's approach (replaced in v9 because they twisted on terrain).

## v2
- Hillshade and 3D terrain from AWS Terrarium tiles, with a 3D button to tilt the map.
- Cards show block length, average and steepest slope with uphill direction, and a five-point (four-part) elevation profile chart.
- CSV/JSON exports add `length_ft`, `elev_from_ft`, `elev_to_ft`, `slope_pct`, `steepest_pct`, and `profile_ft`.

## v1
- Initial build: street autocomplete, cross street and street address lookups, result cards with CNN, address ranges, supervisor district, ZIP, and neighborhoods.
- Handles alley-split blocks and both sides of divided streets.
- MapLibre + Protomaps light basemap with Esri satellite toggle; click streets on the map to add them.
- Copy as CSV / JSON / link; `#cnn=`, `#street=`, `&all=1`, and `&lang=` URL hashes.
- `scripts/build_data.py` builds the compact `data/streets.json` from the DataSF CSVs.
