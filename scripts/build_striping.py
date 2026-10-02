#!/usr/bin/env python3
"""
Link SFMTA striping diagram PDFs to San Francisco street segments (CNNs).

Reads SFMTA's file index (webappsindex.json), parses each striping PDF's file name
("2-Fulton St_str-7970.1 (42nd Ave to 34th Ave).pdf"), finds the blocks and intersections it covers
using data/streets.json, and writes data/striping.json for the striping map (striping/index.html).

Usage (from the repo root):
  python3 scripts/build_striping.py                         # downloads the index
  python3 scripts/build_striping.py --index webappsindex.json   # or use a saved copy

Each run also compares against the previous data/striping.json and appends what changed
(new, removed, renamed/revised, re-uploaded files) to data/striping_changes.json, so we can see
over time whether SFMTA revises files in place, renames them (r1, rev2...), or both.

Standard library only. Reuses the street matcher in scripts/match_blocks.py.
"""
import argparse, hashlib, json, os, re, sys, urllib.parse, urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import match_blocks as mb   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_URL = "https://safitwebapps.blob.core.windows.net/$web/webappsindex.json"
BASE_URL = "https://safitwebapps.blob.core.windows.net/$web/"
PREFIX = "Striping Drawings/"

# spellings in file names that differ from the city's street names
ALIASES = [
    (r"\bgreat\s*high\s*way\b|\bgreathigh\s*way\b|\bgreat hwy\b", "great highway"),
    (r"\blincolnway\b", "lincoln way"),
    (r"\bvan\s*ness\b", "van ness"),
    (r"\bsouth\s*van\s*ness\b", "south van ness"),
    (r"\bembarcadero\b", "the embarcadero"),
    (r"\barmy\b", "cesar chavez"),
    (r"\bmlk\b", "martin luther king jr"),
    (r"\bjfk( dr(ive)?)?\b", "john f kennedy dr"),
    (r"\bterminus\b|\bend of street\b", "dead end"),
    (r"\bcity and county (limit|line)\b|\bcounty limit\b", "county line"),
    (r"\bbernal heights boulevard\b", "bernal heights blvd"),
]


def fix(text):
    t = text.lower().replace("_", " ").replace("&amp;", "&")
    for pat, rep in ALIASES:
        t = re.sub(pat, rep, t)
    t = re.sub(r"\bthe the\b", "the", t)
    return re.sub(r"\s+", " ", t).strip(" -,.")


ID_RE = re.compile(r"(?<![a-z])str\s*[-_ ]?\s*(\d+(?:\.\d+)?)\.?", re.I)   # "_Str-7970.1", "STR 8093", "Str4896"
REV_RE = re.compile(r"\s*(?:_?see\b.*|\b(?:rev|r)\s*\d+\b.*|\brev\b.*|\bR\d*\b.*)$", re.I)


def parse_name(path):
    """file name -> dict of parts (no street matching yet)"""
    parts = path[len(PREFIX):].split("/")
    folder_street = parts[-2] if len(parts) >= 3 else ""
    name = re.sub(r"\.pdf$", "", parts[-1], flags=re.I)
    out = {"path": path, "file": parts[-1], "group": parts[0], "folder_street": folder_street,
           "series": None, "id": None, "street_text": "", "inside": "", "revision": "", "kind": "street"}
    m = re.match(r"^\s*(\d+)\s*-\s*(?=\D)", name)
    if m and not re.match(r"^\s*\d+(st|nd|rd|th)\b", name, re.I):
        out["series"] = int(m.group(1))
        name = name[m.end():]
    if parts[0].startswith("03_Detail"):
        out["kind"] = "detail"
    if re.match(r"\s*caltrans", name, re.I):
        out["kind"] = "caltrans"
    idm = ID_RE.search(name)
    if idm:
        out["id"] = idm.group(1).rstrip(".")
        before, after = name[:idm.start()], name[idm.end():]
    else:
        before, after = name, ""
    # what's in the first (...) after the ID; tolerate a missing "("
    pm = re.search(r"\(([^)]*)\)?(.*)$", after) or re.search(r"\(([^)]*)\)?(.*)$", before)
    if pm:
        out["inside"] = re.sub(r"\s(to)(?=[A-Z0-9])", " to ", pm.group(1).strip())   # "Market St to19th St"
        out["revision"] = pm.group(2).strip(" _")
        lead = after[:pm.start()] if pm.string is after else ""   # "STR-8420 New Montgomery St (...)"
    else:
        out["inside"] = after.strip(" _")
        lead = ""
    street = before.strip(" _-") or lead.strip(" _-")
    street = re.sub(r"^(detail)\s*", "", street, flags=re.I)
    if not street or re.fullmatch(r"\W*", street):
        street = after.split("(")[0].strip(" _-")
    out["street_text"] = street or folder_street
    return out


def nodes_of(segs):
    return sorted({n for s in segs for n in (s["fn"], s["tn"])})


def match(st, d):
    """add street, cross streets, CNNs, intersections, confidence, notes"""
    d.update(street="", from_street="", to_street="", cnns=[], intersections=[], confidence="none", method="", notes=[])
    if d["kind"] in ("detail",):
        d["notes"].append("standard detail drawing, not a location")
        return d
    street_text = fix(d["street_text"])
    inside = fix(d["inside"])
    folder = fix(d["folder_street"])
    # "Baker St to Scott St, Fillmore St to Laguna St": several ranges in one drawing
    ranges = [r.strip() for r in inside.split(",") if re.search(r"\bto\b", r)]
    if len(ranges) > 1:
        parts = [match(st, {**d, "inside": r, "kind": d["kind"]}) for r in ranges]
        got = [p for p in parts if p["cnns"]]
        if got:
            d.update(street=got[0]["street"], from_street=got[0]["from_street"], to_street=got[-1]["to_street"],
                     cnns=sorted({c for p in got for c in p["cnns"]}), intersections=sorted({n for p in got for n in p["intersections"]}),
                     method="between", confidence=min((p["confidence"] for p in got), key=["none", "low", "medium", "high"].index),
                     notes=[f"{len(ranges)} separate ranges"])
            return d
    # "(West to East)": no cross streets, the whole (short) street
    if re.fullmatch(r".*\b(north|south|east|west)\b\s+to\s+(north|south|east|west)\b.*", inside):
        inside = ""
    # "A to B", "A - B", "A thru B"
    m = re.match(r"^(?P<a>.+?)\s+(?:to|thru|through)\s+(?P<b>.+)$", inside) or \
        re.match(r"^(?P<a>[^-]+?)\s+-\s+(?P<b>.+)$", inside)
    if m:
        a, b = m.group("a"), m.group("b")
        # "mccoppin otis sts" style: two names for one end; try each word pair
        r = None
        for main in dict.fromkeys([street_text, folder]):
            if not main:
                continue
            r = mb.try_between(st, main, a, b, d["file"], tail=f"{a}, {b}")
            if r and r["segs"]:
                break
            for alt_a in re.split(r"\s+(?=\S+\s+sts?\b)|/", a):
                for alt_b in re.split(r"/", b):
                    r2 = mb.try_between(st, main, alt_a, alt_b, d["file"])
                    if r2 and r2["segs"]:
                        r = r2; break
                if r and r["segs"]:
                    break
            if r and r["segs"]:
                break
        if r and r["segs"]:
            segs = r["segs"]
            notes = [n for n in r["notes"] if n and not n.startswith("long stretch")]
            conf = r["confidence"]
            if conf == "low" and r["to_street"]:
                # "low" only because it's long (normal for a striping diagram) or a spelling fix
                conf = "high" if not notes else "medium" if all(n.startswith("read ") for n in notes) else conf
            d.update(street=r["street"], from_street=r["from_street"], to_street=r["to_street"],
                     cnns=sorted(s["cnn"] for s in segs), intersections=nodes_of(segs),
                     confidence=conf, method=r["method"], notes=notes)
            return d
        if r:
            d.update(street=r["street"], notes=[n for n in r["notes"] if n])
        else:
            d["notes"].append(f'street "{d["street_text"]}" not found')
        return d
    # intersection: "(11th_ave Clement)", "(And Lawton St)", "(18th and Danvers)"
    streets, note, _ = mb.street_phrase(st, street_text) if street_text else (set(), None, None)
    if not streets and folder:
        streets, note, _ = mb.street_phrase(st, folder)
    if streets and inside:
        cross_text = re.sub(r"^(and|at|&)\s+", "", inside)
        # "(Market St & Broadway St)": two cross streets that both meet the street = the stretch between them
        two = [p for p in re.split(r"\s+(?:and|&)\s+", cross_text) if p.strip()]
        if len(two) == 2:
            for street in sorted(streets):
                r = mb.try_between(st, street.lower(), two[0], two[1], d["file"])
                if r and r["segs"] and r["to_street"]:
                    d.update(street=r["street"], from_street=r["from_street"], to_street=r["to_street"],
                             cnns=sorted(s["cnn"] for s in r["segs"]), intersections=nodes_of(r["segs"]),
                             method="between", confidence="medium", notes=['read "A & B" as the stretch between them'])
                    return d
        for street in sorted(streets):
            for piece in reversed(re.split(r"\s+(?:and|&|at)\s+|,", cross_text)):
                c, nc = st.match_cross(street, piece)
                if c and not c.startswith("END") and c != street:
                    nodes = sorted(st.intersection(street, c))
                    if nodes:
                        touching = [s for s in st.by_street[street] + st.by_street[c] if s["fn"] in nodes or s["tn"] in nodes]
                        d.update(street=street, from_street=c, intersections=nodes,
                                 cnns=sorted({s["cnn"] for s in touching}), method="intersection",
                                 confidence="medium" if nc or note else "high", notes=[n for n in (note, nc) if n])
                        return d
    if streets:
        street = sorted(streets, key=lambda n: -len(st.by_street[n]))[0]
        segs = st.by_street[street]
        if len(segs) <= 25:
            d.update(street=street, cnns=sorted(s["cnn"] for s in segs), intersections=nodes_of(segs),
                     method="whole_street", confidence="low",
                     notes=[n for n in (note, f'no cross streets in the name; used all of {street}') if n])
            return d
        d.update(street=street, notes=[f'no cross streets in the name and {street} is long; not mapped'])
        return d
    d["notes"].append("couldn't read a street from the file name")
    return d


def ends(st, d):
    """[lon, lat] of the from and to intersections, so the map can turn the preview to match the street"""
    if not d["street"] or not d["intersections"]:
        return []
    names = st.cross_names(d["street"])
    on = set(d["intersections"])
    out = []
    for cross in (d["from_street"], d["to_street"]):
        nodes = [n for n in names.get(cross, ()) if n in on and n in st.node_xy]
        if nodes:
            x, y = st.node_xy[nodes[0]]
            out.append([round(x, 5), round(y, 5)])
    return out if len(out) == 2 else []


def load_index(path_or_url):
    if re.match(r"https?://", path_or_url):
        with urllib.request.urlopen(path_or_url, timeout=60) as r:
            return json.load(r)
    return json.load(open(path_or_url, encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", default=INDEX_URL, help="URL or saved copy of webappsindex.json")
    ap.add_argument("--data", default=os.path.join(ROOT, "data", "streets.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "striping.json"))
    ap.add_argument("--changes", default=os.path.join(ROOT, "data", "striping_changes.json"))
    a = ap.parse_args()

    index = load_index(a.index)
    files = [f for f in index if f["Path"].startswith(PREFIX) and f["Path"].lower().endswith(".pdf")]
    st = mb.Streets(*mb.load(a.data))
    diagrams = []
    for f in sorted(files, key=lambda f: f["Path"].lower()):
        d = match(st, parse_name(f["Path"]))
        d["modified"] = f["LastModified"]
        d["size_kb"] = f["SizeKB"]
        d["url"] = BASE_URL + urllib.parse.quote(f["Path"])
        d["preview"] = hashlib.sha1(f["Path"].encode()).hexdigest()[:12]   # striping/previews/<preview>.webp
        d["ends"] = ends(st, d)
        diagrams.append(d)

    # newest file per ID is "current"; older uploads of the same ID are kept but marked
    newest = {}
    for d in diagrams:
        if d["id"] and (d["id"] not in newest or d["modified"] > newest[d["id"]]["modified"]):
            newest[d["id"]] = d
    for d in diagrams:
        d["current"] = (not d["id"]) or newest[d["id"]] is d

    # change log against the previous build
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if os.path.exists(a.out):
        prev = {d["path"]: d for d in json.load(open(a.out, encoding="utf-8"))["diagrams"]}
        cur = {d["path"]: d for d in diagrams}
        prev_by_id = {}
        for d in prev.values():
            if d.get("id"):
                prev_by_id.setdefault(d["id"], []).append(d["path"])
        entry = {"run": now, "added": [], "removed": [], "renamed": [], "updated": []}
        for p, d in cur.items():
            if p not in prev:
                old = [q for q in prev_by_id.get(d["id"], []) if q not in cur]
                (entry["renamed"].append({"id": d["id"], "from": old, "to": p}) if old else entry["added"].append(p))
            elif prev[p]["modified"] != d["modified"]:
                entry["updated"].append({"path": p, "was": prev[p]["modified"], "now": d["modified"]})
        renamed_from = {q for r in entry["renamed"] for q in r["from"]}
        entry["removed"] = [p for p in prev if p not in cur and p not in renamed_from]
        if any(entry[k] for k in ("added", "removed", "renamed", "updated")):
            log = json.load(open(a.changes, encoding="utf-8")) if os.path.exists(a.changes) else []
            log.append(entry)
            json.dump(log, open(a.changes, "w", encoding="utf-8"), indent=1)
        print("changes:", {k: len(v) for k, v in entry.items() if k != "run"})

    keep = ["path", "file", "id", "series", "revision", "kind", "street", "from_street", "to_street", "cnns",
            "intersections", "ends", "confidence", "method", "notes", "modified", "size_kb", "url", "preview", "current"]
    out = {"v": 1, "built": now, "source": a.index if a.index.startswith("http") else INDEX_URL,
           "diagrams": [{k: d[k] for k in keep} for d in diagrams]}
    json.dump(out, open(a.out, "w", encoding="utf-8"), separators=(",", ":"))
    from collections import Counter
    c = Counter(d["confidence"] for d in diagrams if d["kind"] == "street")
    print(f"wrote {a.out}: {len(diagrams)} PDFs ({sum(1 for d in diagrams if d['kind']=='street')} street drawings), "
          f"mapped {sum(1 for d in diagrams if d['cnns'])}; confidence {dict(c)}")


if __name__ == "__main__":
    main()
