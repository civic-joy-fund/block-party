# Changelog

All changes are in `index.html` unless noted. `data/streets.json` and `scripts/build_data.py` are unchanged since v1.

## Striping map s1
- New `striping/` page: streets with an SFMTA striping diagram in teal; hover shows the diagram's blocks and a preview turned to match the street; click picks it, with Open PDF, file details, other sheets in the set, and other diagrams covering that block. Search by street or ID; `#id=` links.
- `scripts/build_striping.py`, `scripts/render_striping_previews.py`, weekly `.github/workflows/striping.yml`.
- Matcher: streets with gaps (15th St between Florida and Alabama) now match by position along the street; directional names like "South Van Ness" and "West Portal" resolve; nearby duplicate intersection points are treated as one.

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
- Intersections ("Haight and Masonic") now return the intersection CNN and a POINT, marked high when the streets meet once; the touching blocks go in `nearby_cnns`. New `type` column.


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
