#!/usr/bin/env python3
# Copied from burritojustice/sf-blocks 2026.10.08. Make changes there, then copy the new version here.
"""
Build the compact lookup file used by Block Party (index.html).

Reads the DataSF exports in data/ and writes data/streets.json:

  data/sf_streets.csv        "Streets - Active and Retired" (required)
  data/sf_intersections.csv  "Street Intersections"         (optional, for intersection lookups)

Usage (from the repo root):
  python3 scripts/build_data.py
  python3 scripts/build_data.py --slopes      # also store each block's slope (downloads ~250 elevation tiles)
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
import argparse, csv, json, math, os, re, struct, sys, urllib.request, zlib
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


# ---------------------------------------------------------------- slopes (optional)
# Same method as Block Party's in-browser profile: AWS Terrarium elevation tiles at zoom 15, sampled
# with bilinear interpolation at five points (start, 1/4, 1/2, 3/4, end) along each segment.
DEM_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/15/{x}/{y}.png"
DEM_Z, TILE = 15, 256


def png_rgb(data):
    """Decode an 8-bit RGB or RGBA PNG (what Terrarium tiles are) into rows of bytes, standard library only."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    pos, idat, w = 8, b"", 0
    while pos < len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", body[:10])
            assert depth == 8 and ctype in (2, 6), f"unsupported PNG type {ctype}/{depth}"
            bpp = 3 if ctype == 2 else 4
        elif kind == b"IDAT":
            idat += body
        pos += 12 + n
    raw, stride, rows, prev = zlib.decompress(idat), w * bpp, [], bytearray(w * bpp)
    for r in range(h):
        f, line = raw[r * (stride + 1)], bytearray(raw[r * (stride + 1) + 1:(r + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b, c = prev[i], (prev[i - bpp] if i >= bpp else 0)
            if f == 1: line[i] = (line[i] + a) & 255
            elif f == 2: line[i] = (line[i] + b) & 255
            elif f == 3: line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                p_ = a + b - c; pa, pb, pc = abs(p_ - a), abs(p_ - b), abs(p_ - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line); prev = line
    return rows, bpp


class Elevation:
    def __init__(self, cache_dir):
        self.cache_dir, self.tiles = cache_dir, {}
        os.makedirs(cache_dir, exist_ok=True)

    def tile(self, x, y):
        k = (x, y)
        if k not in self.tiles:
            path = os.path.join(self.cache_dir, f"{x}_{y}.png")
            if not os.path.exists(path):
                req = urllib.request.Request(DEM_URL.format(x=x, y=y), headers={"User-Agent": "sf-blocks"})
                with urllib.request.urlopen(req, timeout=60) as r, open(path, "wb") as f:
                    f.write(r.read())
            rows, bpp = png_rgb(open(path, "rb").read())
            self.tiles[k] = [[(row[i * bpp] * 256 + row[i * bpp + 1] + row[i * bpp + 2] / 256) - 32768
                              for i in range(TILE)] for row in rows]
        return self.tiles[k]

    def pixel(self, gx, gy):
        return self.tile(gx // TILE, gy // TILE)[gy % TILE][gx % TILE]

    def at(self, lon, lat):
        n = 2 ** DEM_Z
        px = (lon + 180) / 360 * n * TILE - 0.5
        lr = math.radians(lat)
        py = (1 - math.log(math.tan(lr) + 1 / math.cos(lr)) / math.pi) / 2 * n * TILE - 0.5
        x0, y0 = math.floor(px), math.floor(py)
        fx, fy = px - x0, py - y0
        a, b, c, d = self.pixel(x0, y0), self.pixel(x0 + 1, y0), self.pixel(x0, y0 + 1), self.pixel(x0 + 1, y0 + 1)
        return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def seg_slope(elev, pts):
    """(average grade %, steepest quarter %), both unsigned, for a list of (lon, lat) points"""
    m = lambda p, q: math.hypot((q[0] - p[0]) * 111320 * math.cos(math.radians(37.76)), (q[1] - p[1]) * 111320)
    lens = [m(pts[i - 1], pts[i]) for i in range(1, len(pts))]
    total = sum(lens)
    if total < 1:
        return 0.0, 0.0
    def along(frac):
        target, acc = frac * total, 0.0
        for i, L in enumerate(lens):
            if acc + L >= target and L > 0:
                k = (target - acc) / L
                p, q = pts[i], pts[i + 1]
                return p[0] + k * (q[0] - p[0]), p[1] + k * (q[1] - p[1])
            acc += L
        return pts[-1]
    e = [elev.at(*along(f)) for f in (0, .25, .5, .75, 1)]
    part = total / 4
    quarters = [abs(e[i + 1] - e[i]) / part * 100 for i in range(4)]
    return abs(e[4] - e[0]) / total * 100, max(quarters)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--streets", default=os.path.join(ROOT, "data", "sf_streets.csv"))
    ap.add_argument("--intersections", default=os.path.join(ROOT, "data", "sf_intersections.csv"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "streets.json"))
    ap.add_argument("--slopes", action="store_true", help="add slope_avg and slope_max (percent x10) to every segment")
    ap.add_argument("--tile-cache", default=os.path.join(ROOT, ".tile-cache"), help="where elevation tiles are kept")
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

    fields = list(SEG_FIELDS)
    if a.slopes:
        elev = Elevation(a.tile_cache)
        for i, row in enumerate(segs):
            g, pts, x, y = row[-1], [], 0, 0
            for j in range(0, len(g), 2):
                if j == 0: x, y = g[0], g[1]
                else: x, y = x + g[j], y + g[j + 1]
                pts.append((x / SCALE, y / SCALE))
            try:
                avg, mx = seg_slope(elev, pts)
                row += [round(avg * 10), round(mx * 10)]
            except Exception as e:
                print(f"slope failed for cnn {row[0]}: {e}", file=sys.stderr)
                row += [-1, -1]
            if i % 2000 == 0:
                print(f"  slopes {i}/{len(segs)}", flush=True)
        fields += ["slope_avg", "slope_max"]     # percent x10; -1 = unknown
    out = {
        "v": 1,
        "built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_as_of": data_as_of,
        "strings": S.list,
        "seg_fields": fields,
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
