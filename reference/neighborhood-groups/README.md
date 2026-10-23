# Neighborhood group notification list

SF Planning's list of neighborhood groups and the Planning Neighborhoods each wants to be notified about.

- **Source:** https://sfplanning.org/resource/neighborhood-group-organizations (published as an Excel file)
- **Files here:**
  - `NeighborhoodGroupList_20260925.xlsx`: as published, with a sheet per neighborhood that refers back to the "Complete List" sheet
  - `SF_Planning_Complete_notification_list_20260925.csv`: the "Complete List" sheet saved as CSV
- **Date:** the list's sheet is named `Complete List_09252026`, so September 25, 2026.

## Updating

1. Download the new Excel file from the page above and save it here with its date in the name (`NeighborhoodGroupList_YYYYMMDD.xlsx`).
2. Save its "Complete List" sheet as CSV next to it, again with the date in the name.
3. Run `python3 scripts/build_neighborhood_groups.py`. It reads the newest CSV and writes `data/neighborhood_groups.json`.

The script prints how many groups each neighborhood gets, and any neighborhood names it couldn't match.

## How it's matched

- **Neighborhoods:** "NEIGHBORHOOD OF INTEREST" is a comma-separated list of the 37 Planning Neighborhoods from DataSF's [Planning Neighborhood Groups Map](https://data.sf.gov/-/Planning-Neighborhood-Groups-Map/iacs-ws63) (`mw29-m2za`). Those boundaries are in `data/boundaries/planning_neighborhoods.geojson`, copied from civic-joy-fund/joiner.
- **Spelling:** names are matched ignoring case, spaces and punctuation, and allowing a typo or two in longer names ("Downton/Civic Center", "Outer Susnet").
- **Aliases:** "South Bayshore" counts as Bayview, "Upper Market" as Castro/Upper Market, and "Treasure Island" as Treasure Island/YBI.
- **Citywide:** "Citywide" groups are listed separately on every card.

## What the site shows

- **Fields:** `data/neighborhood_groups.json` keeps organization, contact name, email and notification preference. Street addresses and phone numbers stay only in the files here.
- **Cards:** a block card lists the groups for the block's Planning Neighborhood. The card tests three points along the block, so a block on a boundary lists both neighborhoods; an intersection is tested at the corner and 15 m each way. There's a "Copy list" button.
