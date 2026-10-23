#!/usr/bin/env python3
"""Build data/neighborhood_groups.json from SF Planning's neighborhood group notification list.

    python3 scripts/build_neighborhood_groups.py

Reads the newest CSV in reference/neighborhood-groups/ (SF Planning publishes the list as an Excel
file; save its "Complete List" sheet as CSV next to it, keeping the date in the name). Standard library
only.

Source: https://sfplanning.org/resource/neighborhood-group-organizations
Each group lists the Planning Neighborhoods it wants to hear about ("NEIGHBORHOOD OF INTEREST", comma
separated, sometimes misspelled). Those are the 37 neighborhoods of DataSF's Planning Neighborhood Groups
Map (mw29-m2za), in data/boundaries/planning_neighborhoods.geojson; Block Party works out which of them a
block is in.

The page only needs who the groups are, so the JSON keeps organization, contact name, email, and
notification preference. Street addresses and phone numbers stay in the reference copy.
"""
import csv, json, re, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'reference' / 'neighborhood-groups'
HOODS_FILE = ROOT / 'data' / 'boundaries' / 'planning_neighborhoods.geojson'
OUT = ROOT / 'data' / 'neighborhood_groups.json'
PAGE = 'https://sfplanning.org/resource/neighborhood-group-organizations'

# names on the list that aren't spelled like the boundaries (after the forgiving match below)
ALIASES = {
    'south bayshore': 'Bayview',          # the Bayview Hunters Point area plan's name
    'upper market': 'Castro/Upper Market',
    'treasure island': 'Treasure Island/YBI',
}


def key(s):
    return re.sub(r'[^a-z]', '', s.lower())


def near(a, b):
    """at most 2 edits apart (for typos like "Outer Susnet")"""
    if abs(len(a) - len(b)) > 2:
        return False
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] <= 2


def main():
    hoods = sorted(f['properties']['neighborho'] for f in json.loads(HOODS_FILE.read_text())['features'])
    by_key = {key(h): h for h in hoods}

    def place(name):
        k = key(name)
        if not k:
            return None
        if k == 'citywide':
            return 'Citywide'
        if name.strip().lower() in ALIASES:
            return ALIASES[name.strip().lower()]
        if k in by_key:
            return by_key[k]
        hits = [h for kk, h in by_key.items() if len(k) >= 8 and near(k, kk)]
        return hits[0] if len(hits) == 1 else None

    files = sorted(SRC.glob('*.csv'), key=lambda p: (re.findall(r'20\d{6}', p.stem) or ['0'])[-1])
    if not files:
        sys.exit(f'No CSV in {SRC}')
    src = files[-1]
    stamp = (re.findall(r'(20\d{2})(\d{2})(\d{2})', src.stem) or [None])[-1]
    with open(src, newline='', encoding='utf-8-sig', errors='replace') as fh:
        rows = [{(k or '').strip().upper(): (v or '').strip() for k, v in r.items()} for r in csv.DictReader(fh)]

    groups, unplaced = [], {}
    for r in rows:
        org = '' if r.get('ORGANIZATION') in ('-', '') else r['ORGANIZATION']
        name = r.get('NAME') or ' '.join(x for x in (r.get('FIRST'), r.get('LAST')) if x)
        if not (org or name.strip()):
            continue
        places = []
        for part in re.split(r',', r.get('NEIGHBORHOOD OF INTEREST', '')):
            if not part.strip():
                continue
            p = place(part)
            if p and p not in places:
                places.append(p)
            elif not p:
                unplaced[part.strip()] = unplaced.get(part.strip(), 0) + 1
        emails = '; '.join(re.findall(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+', r.get('EMAIL', '')))
        groups.append({'org': org, 'name': name.strip(), 'email': emails,
                       'pref': r.get('NOTIFICATION PREFERENCES', ''), 'hoods': places})
    groups.sort(key=lambda g: ((g['org'] or g['name']).lower()))
    index = {h: [] for h in hoods + ['Citywide']}
    for i, g in enumerate(groups):
        for h in g['hoods']:
            index[h].append(i)
    out = {'source': {'page': PAGE, 'file': src.name, 'list_date': '-'.join(stamp) if stamp else None,
                      'built': date.today().isoformat(),
                      'neighborhoods': 'DataSF Planning Neighborhood Groups Map (mw29-m2za)'},
           'neighborhoods': index, 'groups': groups}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')))
    print(f'{OUT.relative_to(ROOT)}: {len(groups)} groups, {sum(1 for g in groups if g["hoods"])} placed, '
          f'{len(index["Citywide"])} citywide, {OUT.stat().st_size / 1024:.0f} KB (from {src.name})')
    for h in hoods:
        print(f'  {h:24} {len(index[h]):3}')
    if unplaced:
        print('not matched to a neighborhood:', unplaced)


if __name__ == '__main__':
    main()
