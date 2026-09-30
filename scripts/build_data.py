#!/usr/bin/env python3
"""
Build the compact lookup file used by Block Party (index.html).

Reads the DataSF exports in data/ and writes data/streets.json:

  data/sf_streets.csv        "Streets - Active and Retired" (required)
  data/sf_intersections.csv  "Street Intersections"         (optional, for intersection lookups)

Usage (from the repo root):
  python3 scripts/build_data.py
  python3 scripts/build_data.py --streets path/to/streets.csv --intersections path/to/int.csv --out data/streets.json

Standard library only; no pip installs needed.

Output format (version 1)
-------------------------
{
  "v": 1,
  "built": ISO timestamp,
  "data_as_of": value of data_as_of from the source export,
  "strings": [...],                      shared string table; string fields below are indexes into it
  "seg_fields": [...],                   column names for each row of "segs"
  "segs": [[...], ...],                  one row per street segment (active and retired)
  "node_fields": [...],
  "nodes": [[cnn, x, y, [street idx...]], ...]   intersections: coordinates + the streets that meet there
}
Coordinates are integers of degrees * 1e5 (about 1 m precision).
Segment geometry is delta-encoded: [x0, y0, dx1, dy1, dx2, dy2, ...].
"""
import argparse, csv, json, os, re, sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCALE = 100000

SEG_FIELDS = ["cnn", "streetname", "f_st", "t_st",
              "lf_fadd", "lf_toadd", "rt_fadd", "rt_toadd",
              "f_node_cnn", "t_node_cnn", "layer", "flags",
              "nhood", "analysis_neighborhood", "supervisor_district", "zip_code",
              "oneway", "classcode", "date_dropped", "geom"]
NODE_FIELDS = ["cnn", "x", "y", "streets"]


class Strings:
    def __init__(self):
        self.idx, self.list = {}, []

    def __call__(self, s):
        s = (s or "").strip()
        if s not in self.idx:
            self.idx[s] = len(self.list)
            self.list.append(s)
        return self.idx[s]


def to_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def parse_wkt_line(wkt):
    m = re.match(r"\s*LINESTRING\s*\((.*)\)\s*$", wkt or "", re.I)
    if not m:
        return []
    pts = []
    for pair in m.group(1).split(","):
        x, y = pair.split()
        pts.append((round(float(x) * SCALE), round(float(y) * SCALE)))
    return pts


def delta(pts):
    out, px, py = [], 0, 0
    for i, (x, y) in enumerate(pts):
        if i == 0:
            out += [x, y]
        else:
            out += [x - px, y - py]
        px, py = x, y
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--streets", default=os.path.join(ROOT, "data", "sf_streets.csv"))
    ap.add_argument("--intersections", default=os.path.join(ROOT, "data", "sf_intersections.csv"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "streets.json"))
    a = ap.parse_args()

    S = Strings()
    segs, node_xy, data_as_of = [], {}, ""
    with open(a.streets, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            pts = parse_wkt_line(r.get("line"))
            if not pts:
                print(f"skipping cnn {r.get('cnn')}: no geometry", file=sys.stderr)
                continue
            fn, tn = to_int(r["f_node_cnn"]), to_int(r["t_node_cnn"])
            node_xy.setdefault(fn, pts[0])
            node_xy.setdefault(tn, pts[-1])
            flags = (1 if r["active"].lower() == "true" else 0) | (2 if r["accepted"].lower() == "true" else 0)
            data_as_of = data_as_of or r.get("data_as_of", "")
            segs.append([
                to_int(r["cnn"]), S(r["streetname"]), S(r["f_st"]), S(r["t_st"]),
                to_int(r["lf_fadd"]), to_int(r["lf_toadd"]), to_int(r["rt_fadd"]), to_int(r["rt_toadd"]),
                fn, tn, S(r["layer"]), flags,
                S(r["nhood"]), S(r["analysis_neighborhood"]), to_int(r["supervisor_district"]), S(r["zip_code"]),
                S(r["oneway"]), to_int(r["classcode"]), S(r["date_dropped"]), delta(pts),
            ])

    # Intersections: which streets meet at each node. Falls back to segment endpoints if the CSV is missing.
    node_streets = {}
    if os.path.exists(a.intersections):
        with open(a.intersections, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                cnn = to_int(r.get("CNN") or r.get("cnn"))
                names = node_streets.setdefault(cnn, set())
                names.add(r["streetname"].strip())
                for part in (r.get("from_st") or "").split("\\"):
                    part = part.strip()
                    if part and not part.upper().startswith("END"):
                        names.add(part)
    else:
        print("no intersections CSV found; deriving nodes from segments", file=sys.stderr)
    strings = S.list
    for s in segs:
        for n in (s[8], s[9]):
            node_streets.setdefault(n, set()).add(strings[s[1]])

    nodes = []
    for cnn, names in sorted(node_streets.items()):
        if cnn in node_xy:
            x, y = node_xy[cnn]
            nodes.append([cnn, x, y, sorted(S(n) for n in names if n)])

    out = {
        "v": 1,
        "built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_as_of": data_as_of,
        "strings": S.list,
        "seg_fields": SEG_FIELDS,
        "segs": segs,
        "node_fields": NODE_FIELDS,
        "nodes": nodes,
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"), ensure_ascii=False)
    print(f"wrote {a.out}: {len(segs)} segments, {len(nodes)} intersections, "
          f"{len(S.list)} strings, {os.path.getsize(a.out)/1e6:.2f} MB")


if __name__ == "__main__":
    main()
