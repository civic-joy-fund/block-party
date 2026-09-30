#!/usr/bin/env python3
"""
Match free-text block descriptions ("Sanchez between 27th St and Duncan", "100 block of Winfield",
"300 Otsego Ave", "Haight and Masonic") to San Francisco street segments (CNNs).

Usage (from the repo root):
  python3 scripts/match_blocks.py applications.csv
  python3 scripts/match_blocks.py applications.csv --column "Block you want to party on" --out matched.csv

Reads data/streets.json (built by scripts/build_data.py). Standard library only.

Output: every input column, plus one row per location found in the description (a row that names
two blocks becomes two rows). Rows where nothing could be matched are kept, with an explanation.

  source_row      1-based row number in the input file
  part / parts    which location in that row (1 of 2, ...)
  matched_text    the piece of the description this row came from
  cnn             CNN(s) of the matched segment(s), separated by ";"
  street          street name (city spelling)
  from_street     first cross street
  to_street       second cross street
  address_low / address_high   lowest and highest address on the matched segment(s)
  address_ranges  per-segment ranges, even range first ("900-988, 901-989"), separated by ";"
  supervisor_district, nhood
  wkt             LINESTRING / MULTILINESTRING (WGS84 lon/lat), ready for mapping tools
  confidence      high / medium / low / none
  method          how it was matched: between, block, address, intersection, street_only, none
  notes           warnings, fuzzy spelling fixes, or why it couldn't be matched
"""
import argparse, csv, difflib, heapq, json, math, os, re, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCLUDED_LAYERS = {"FREEWAYS", "PAPER", "PAPER_FWYS", "PAPER_WATER", "PSEUDO", "PRIVATE_PARKING"}

SUFFIXES = {
    "street": "st", "streets": "st", "st": "st", "str": "st",
    "avenue": "ave", "avenues": "ave", "ave": "ave", "av": "ave",
    "boulevard": "blvd", "blvd": "blvd", "terrace": "ter", "ter": "ter",
    "court": "ct", "ct": "ct", "way": "way", "wy": "way", "place": "pl", "pl": "pl",
    "drive": "dr", "dr": "dr", "alley": "aly", "aly": "aly", "lane": "ln", "ln": "ln",
    "road": "rd", "rd": "rd", "circle": "cir", "cir": "cir", "plaza": "plz", "plz": "plz",
    "highway": "hwy", "hwy": "hwy", "row": "row", "walk": "walk", "loop": "loop",
}
ONES = ["", "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth"]
TEENS = ["tenth", "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth", "sixteenth",
         "seventeenth", "eighteenth", "nineteenth"]
TENS_ORD = {2: "twentieth", 3: "thirtieth", 4: "fortieth"}
TENS = {2: "twenty", 3: "thirty", 4: "forty"}


def ordinal(n):
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


ORD_WORDS = {}
for n in range(1, 50):
    if n < 10: w = ONES[n]
    elif n < 20: w = TEENS[n - 10]
    elif n % 10 == 0: w = TENS_ORD[n // 10]
    else: w = TENS[n // 10] + ONES[n % 10]
    ORD_WORDS[w] = ordinal(n)


# ---------------------------------------------------------------- data
def load(path):
    raw = json.load(open(path, encoding="utf-8"))
    S, F = raw["strings"], {f: i for i, f in enumerate(raw["seg_fields"])}
    NF = {f: i for i, f in enumerate(raw["node_fields"])}
    node_streets = {n[NF["cnn"]]: {S[i] for i in n[NF["streets"]]} for n in raw["nodes"]}
    segs = []
    for r in raw["segs"]:
        g, pts, x, y = r[F["geom"]], [], 0, 0
        for i in range(0, len(g), 2):
            if i == 0: x, y = g[0], g[1]
            else: x, y = x + g[i], y + g[i + 1]
            pts.append((x / 1e5, y / 1e5))
        layer, flags = S[r[F["layer"]]], r[F["flags"]]
        if not flags & 1 or layer in EXCLUDED_LAYERS:
            continue
        length = sum(math.hypot((b[0] - a[0]) * 88000, (b[1] - a[1]) * 111320) for a, b in zip(pts, pts[1:]))
        segs.append(dict(
            cnn=r[F["cnn"]], street=S[r[F["streetname"]]], f=S[r[F["f_st"]]], t=S[r[F["t_st"]]],
            lf=(r[F["lf_fadd"]], r[F["lf_toadd"]]), rt=(r[F["rt_fadd"]], r[F["rt_toadd"]]),
            fn=r[F["f_node_cnn"]], tn=r[F["t_node_cnn"]], sup=r[F["supervisor_district"]],
            nhood=S[r[F["nhood"]]], pts=pts, len=length))
    return segs, node_streets


def norm_words(text):
    text = text.lower().replace("’", "'").replace("'", "").replace(".", " ")
    text = re.sub(r"(twenty|thirty|forty)[\s-]+", r"\1", text)
    words = re.findall(r"[a-z0-9]+", text)
    out = []
    for w in words:
        w = ORD_WORDS.get(w, w)
        w = re.sub(r"^0+(?=\d)", "", w)
        out.append(w)
    return out


def split_name(name_words):
    """-> (base words tuple, suffix or None)"""
    if name_words and name_words[-1] in SUFFIXES:
        return tuple(name_words[:-1]), SUFFIXES[name_words[-1]]
    return tuple(name_words), None


def base_key(words):
    """numbers become ordinals so "18" matches "18th"; "st" at the start means Saint"""
    out = []
    for i, w in enumerate(words):
        if re.fullmatch(r"\d+", w):
            w = ordinal(int(w))
        if i == 0 and w == "st" and len(words) > 1:
            w = "saint"
        out.append(w)
    return " ".join(out)


class Streets:
    def __init__(self, segs, node_streets):
        self.segs = segs
        self.node_streets = node_streets
        self.by_street = defaultdict(list)
        for s in segs:
            self.by_street[s["street"]].append(s)
        self.by_base = defaultdict(set)      # "sanchez" -> {"SANCHEZ ST"}
        self.suffix_of = {}
        for name in self.by_street:
            base, suf = split_name(norm_words(name))
            key = base_key(base)
            self.by_base[key].add(name)
            self.by_base[key.replace(" ", "")].add(name)    # "ofarrell", "mission bay"
            self.suffix_of[name] = suf
        self.bases = list(self.by_base)

    # -- names
    def candidates(self, words, cutoff=0.86):
        """street names a phrase could mean -> (set, fuzzy_note)"""
        base, suf = split_name(words)
        if not base:
            return set(), None
        key = base_key(base)
        hits = set(self.by_base.get(key, ())) | set(self.by_base.get(key.replace(" ", ""), ()))
        note = None
        if not hits and len(key) >= 4 and not re.fullmatch(r"\d+(st|nd|rd|th)", key):
            close = difflib.get_close_matches(key, self.bases, n=1, cutoff=cutoff)
            if close:
                hits = set(self.by_base[close[0]])
                note = f'read "{" ".join(base)}" as "{close[0]}"'
        if suf and len(hits) > 1:
            same = {h for h in hits if self.suffix_of[h] == suf}
            hits = same or hits
        return hits, note

    def cross_names(self, street):
        """every street that meets `street`, with the intersection nodes where it does. Uses the city's
        intersection list, because a segment's f_st/t_st names only one of the streets at a node."""
        out = defaultdict(set)
        for s in self.by_street[street]:
            out[s["f"]].add(s["fn"]); out[s["t"]].add(s["tn"])
            for n in (s["fn"], s["tn"]):
                for other in self.node_streets.get(n, ()):
                    if other != street:
                        out[other].add(n)
        return out

    def match_cross(self, street, text):
        """resolve a cross-street phrase against the streets that actually cross `street`"""
        names = self.cross_names(street)
        if re.search(r"dead ?end|\bend\b|cul.de.sac", text):
            ends = [n for n in names if n.startswith("END")]
            if ends:
                return ends[0], None
        words = [w for w in norm_words(text) if w not in ("the", "of", "and", "on", "street", "streets")] or norm_words(text)
        base, suf = split_name(words)
        key = base_key(base)
        if not key:
            return None, None
        table = {}
        for n in names:
            b, sf = split_name(norm_words(n))
            table.setdefault(base_key(b), []).append(n)
            table.setdefault(base_key(b).replace(" ", ""), []).append(n)
        if key in table:
            opts = table[key]
            if suf and len(opts) > 1:
                opts = [o for o in opts if self.suffix_of.get(o) == suf] or opts
            return opts[0], None
        close = difflib.get_close_matches(key, list(table), n=1, cutoff=0.8)
        if close:
            return table[close[0]][0], f'read cross street "{text.strip()}" as "{close[0]}"'
        # "18th Ave" style phrase that includes extra words: try each word window
        for n in range(len(base), 0, -1):
            for i in range(len(base) - n + 1):
                k = base_key(base[i:i + n])
                if k in table:
                    return table[k][0], None
        return None, None

    # -- graph
    def dijkstra(self, segs, sources):
        adj = defaultdict(list)
        for s in segs:
            adj[s["fn"]].append((s["tn"], s["len"])); adj[s["tn"]].append((s["fn"], s["len"]))
        dist = {n: 0.0 for n in sources}
        pq = [(0.0, n) for n in sources]
        while pq:
            d, n = heapq.heappop(pq)
            if d > dist.get(n, math.inf): continue
            for m, w in adj[n]:
                if d + w < dist.get(m, math.inf):
                    dist[m] = d + w; heapq.heappush(pq, (d + w, m))
        return dist

    def between(self, street, a, b):
        segs = self.by_street[street]
        names = self.cross_names(street)
        A, B = names.get(a, set()), names.get(b, set())
        dA, dB = self.dijkstra(segs, A), self.dijkstra(segs, B)
        D = min((dA[n] for n in B if n in dA), default=math.inf)
        if D == math.inf:
            return [], math.inf
        tol = D * 1.3 + 25
        out = [s for s in segs if min(dA.get(s["fn"], math.inf) + s["len"] + dB.get(s["tn"], math.inf),
                                      dA.get(s["tn"], math.inf) + s["len"] + dB.get(s["fn"], math.inf)) <= tol]
        return out, D

    def in_block(self, street, block):
        lo, hi = block, block + 99
        out = []
        for s in self.by_street[street]:
            for a, b in (s["lf"], s["rt"]):
                if a > 0 and b > 0 and min(a, b) <= hi and max(a, b) >= lo:
                    out.append(s); break
        return out

    def at_address(self, street, num):
        out = []
        for s in self.by_street[street]:
            for a, b in (s["lf"], s["rt"]):
                if a > 0 and b > 0 and min(a, b) <= num <= max(a, b) and (a % 2 == num % 2 or b % 2 == num % 2):
                    out.append(s); break
        return out

    def intersection(self, a, b):
        return set(self.cross_names(a).get(b, set()))


# ---------------------------------------------------------------- parsing
CONNECT = r"(?:and|&|to|through|thru|-|/)"
CONNECT_TIGHT = r"\s*(?:&|/|-)\s*|\s+(?:and|to|through|thru)\s+"      # "17th/18th", "Clipper & 26th", "Noe and Castro"
NAME = r"[a-z0-9' .\-]+?"


def clean(text):
    t = (text or "").replace("\\n", "\n").replace("’", "'")
    # drop asides that aren't locations: "(main event)", "(it's a one block long street)", "(to the South)"
    t = re.sub(r"\((?:\s*(?:there is|it'?s|aka|main event|to the|in the)\b)[^)]*\)?", " ", t, flags=re.I)
    t = re.sub(r",?\s*san francisco(?:,?\s*(?:ca|california))?(?:\s*\d{5})?|,?\s*\bsf\b,?\s*(?:ca)?\s*\d{5}", " ", t, flags=re.I)
    t = re.sub(r"cross streets? (?:are|is|of)?:?", " between ", t, flags=re.I)
    t = t.replace("(", ", ").replace(")", ", ")
    t = re.sub(r"\bbtwn\b|\bb/w\b|\bin between\b", "between", t, flags=re.I)
    t = re.sub(r"\bblk\b", "block", t, flags=re.I)
    return t


def street_phrase(st, text):
    """find a street name inside a phrase: longest word window that names a real street, nearest the end"""
    words = [w for w in norm_words(text)]
    stop = {"on", "the", "of", "block", "blocks", "in", "front", "at", "also", "and", "a", "we", "are",
            "repeating", "both", "north", "south", "east", "west", "side", "sf"}
    places = {"park", "plaza", "center", "playground", "garden", "square", "commons"}
    best = None
    for n in range(min(5, len(words)), 0, -1):
        for i in range(len(words) - n, -1, -1):
            win = words[i:i + n]
            if win[0] in stop or (len(win) == 1 and (win[0] in stop or win[0] in SUFFIXES or win[0] in places)):
                continue
            hits, note = st.candidates(win)
            if hits:
                score = (0 if note else 1, n, i)
                if best is None or score > best[0]:
                    best = (score, hits, note, " ".join(win))
        if best and best[0][0] == 1:
            break
    return (best[1], best[2], best[3]) if best else (set(), None, None)


def result(method, segs, confidence, street, text, a="", b="", notes=()):
    return dict(method=method, segs=segs, confidence=confidence, street=street, text=text.strip(" ,.;"),
                from_street=a, to_street=b, notes=[n for n in notes if n])


def try_between(st, main_txt, a_txt, b_txt, text, block=None, tail=""):
    streets, note, _ = street_phrase(st, main_txt)
    if not streets:
        return None

    def best_pair(pairs):
        best = None
        for street in streets:
            for at, bt in pairs:
                a, na = st.match_cross(street, at)
                b, nb = st.match_cross(street, bt)
                if not a or not b or a == b:
                    continue
                if b.startswith("END"):     # "to the dead end": use whichever end is reachable
                    b_opts = [n for n in st.cross_names(street) if n.startswith("END")] or [b]
                else:
                    b_opts = [b]
                for b2 in b_opts:
                    segs, D = st.between(street, a, b2)
                    if segs and (best is None or D < best[0]):
                        best = (D, street, a, b2, segs, [note, na, nb])
        return best

    best = best_pair([(a_txt, b_txt)])
    if not best and tail:
        # "Ford St between 17th/18th, Sanchez and Noe": try every pair of names that follow "between"
        pieces = [p.strip() for p in re.split(r"[,/&;]|\band\b|\bto\b", tail) if p.strip()][:6]
        pairs = [(pieces[i], pieces[j]) for i in range(len(pieces)) for j in range(i + 1, len(pieces))]
        best = best_pair(pairs)
        if best:
            best[5].append("picked the cross streets out of several names")
    if not best and block is not None:
        for street in streets:
            segs = st.in_block(street, block)
            if segs:
                return result("block", segs, "medium", street, text, notes=[note, "cross streets didn't match; used block number"])
    if not best:
        # only one cross street found: list the blocks touching it
        for street in streets:
            for t_ in (a_txt, b_txt):
                c, nc = st.match_cross(street, t_)
                if c and not c.startswith("END"):
                    other = b_txt if t_ is a_txt else a_txt
                    segs = [s for s in st.by_street[street] if s["fn"] in st.cross_names(street)[c] or s["tn"] in st.cross_names(street)[c]]
                    if segs:
                        return result("between", segs, "low", street, text, c, "",
                                      [note, nc, f'couldn\'t find "{other.strip()}" at {street}; listed the blocks touching {c}'])
        # couldn't find both cross streets; fall back to a block number or say why
        street = sorted(streets)[0]
        if block is not None:
            segs = st.in_block(street, block)
            if segs:
                return result("block", segs, "medium", street, text, notes=[note, "cross streets didn't match; used block number"])
        return result("between", [], "none", street, text,
                      notes=[note, f'couldn\'t find "{a_txt.strip()}" and "{b_txt.strip()}" as cross streets of {street}'])
    D, street, a, b, segs, notes = best
    conf = "high" if not any(notes) else "medium"
    if block is not None:
        blk = st.in_block(street, block)
        if blk and not ({s["cnn"] for s in blk} & {s["cnn"] for s in segs}):
            conf = "low"; notes.append(f"block {block} doesn't match the cross streets; used cross streets")
    if len(segs) > 12:
        conf = "low"; notes.append(f"long stretch: {len(segs)} segments")
    return result("between", segs, conf, street, text, a, b, notes)


def parse(st, raw):
    text = clean(raw)
    low = text.lower()
    found = []

    # 1. "<street> between A and B" (also "from A to B", "A to B" after a comma), any number of times
    pat = re.compile(
        r"(?:(\d+)\s*(?:-\s*\d+\s*)?block\s+(?:of\s+)?)?(?P<main>[a-z0-9' .,\-]{2,60}?)\s*,?\s*(?:\(\s*)?"
        r"(?:between|from)\s+(?P<a>[a-z0-9' .\-]{2,40}?)(?:" + CONNECT_TIGHT + r")(?P<b>[a-z0-9' .\-]{2,40}?)"
        r"(?=\s*(?:[,.;()\n]|$|\s(?:and|also|in|on|with|for|streets?|avenues?)\b))", re.I)
    used = []
    for m in pat.finditer(low):
        block = int(m.group(1)) // 100 * 100 if m.group(1) else None
        main = m.group("main")
        mb = re.search(r"(\d+)\s*(?:-\s*\d+\s*)?block\s+(?:of\s+)?(.*)$", main)   # "2600 block of filbert"
        if mb:
            block, main = int(mb.group(1)) // 100 * 100, mb.group(2)
        parts = [p for p in re.split(r"[,;]", main) if p.strip()]
        if len(parts) > 1 and re.fullmatch(r"\s*\d+\s*block\s*", parts[-1]):   # "taylor street, 2200 block, between ..."
            block = int(re.search(r"\d+", parts[-1]).group()) // 100 * 100
            parts = parts[:-1]
        main = parts[-1] if parts else main
        mb2 = re.search(r"(\d+)\s*block", main)
        if mb2:
            block = int(mb2.group(1)) // 100 * 100
            main = re.sub(r"\d+\s*block", " ", main)
        tail = low[m.start("a"):m.end("b") + 60]
        r = try_between(st, main, m.group("a"), m.group("b"), m.group(0), block, tail=re.split(r"[.;\n(]", tail)[0])
        if r:
            found.append(r); used.append(m.span())
    # "Grant Ave, Broadway to California" / "Java Street (Masonic and Buena Vista Ave West)"
    if not found:
        for m in re.finditer(r"(?P<main>[a-z0-9' .\-]{2,40}?)\s*[,(]\s*(?P<a>[a-z0-9' .\-]{2,40}?)\s+" + CONNECT +
                             r"\s+(?P<b>[a-z0-9' .\-]{2,40}?)(?=\s*(?:[,.;)\n]|$|\s(?:and|also)\b))", low):
            r = try_between(st, m.group("main"), m.group("a"), m.group("b"), m.group(0))
            if r and r["segs"]:
                found.append(r); used.append(m.span())
    # "Between 18 - 24 on Shotwell"
    if not found:
        m = re.search(r"between\s+(?P<a>[a-z0-9 ]+?)\s*" + CONNECT + r"\s*(?P<b>[a-z0-9 ]+?)\s+on\s+(?P<main>[a-z0-9' .\-]+)", low)
        if m:
            r = try_between(st, m.group("main"), m.group("a"), m.group("b"), m.group(0))
            if r: found.append(r)
    if re.search(r"\bsuch as\b|\be\.?g\.?\b", low) and not found:
        return [result("none", [], "none", "", raw[:80], notes=["lists several streets or places; needs a person to read it"])]
    good = [r for r in found if r["segs"]]
    if good:
        return good
    failed_between = found          # reported only if nothing else works

    # 2. block numbers: "100 block of Winfield", "600 - 700 block of Shotwell", "400 and 500 blocks of X"
    m = re.search(r"(\d+)\s*(?:(?:-|&|and|to)\s*(\d+)\s*)?blocks?(?!\s*part)\s*(?:of\s+)?(?P<main>[a-z0-9' .\-]+)", low) \
        or re.search(r"(?P<main>[a-z][a-z0-9' .\-]+?)\s*\(?\s*(\d+)\s+block", low)
    if m:
        nums = [int(g) for g in m.groups()[:2] if g and g.isdigit()] if m.re.pattern.startswith("(\\d") else [int(m.group(2))]
        main = re.split(r"\bbeginning\b|\bwith\b|\bwhich\b|\bbetween\b|\band\b|,|\.\s|\badjacent\b|\bon\b(?! [a-z]+ st)", m.group("main"))[0]
        streets, note, _ = street_phrase(st, main)
        if streets:
            street = sorted(streets, key=lambda n: -len(st.by_street[n]))[0]
            blocks = sorted({n // 100 * 100 for n in nums})
            if len(blocks) == 2 and blocks[1] - blocks[0] > 100:
                blocks = list(range(blocks[0], blocks[1] + 1, 100))
            segs = [s for b in blocks for s in st.in_block(street, b)]
            if segs:
                conf = "medium" if not note else "low"
                extra = [] if len(streets) == 1 else [f"street name could also be {', '.join(sorted(streets - {street}))}"]
                return [result("block", segs, conf, street, m.group(0), notes=[note, *extra])]
            return [result("block", [], "none", street, m.group(0), notes=[note, f"no addresses in block(s) {blocks} on {street}"])]

    # 3. street address: "300 Otsego Ave", "In front of 12 Ord Ct.", "1600-1700 on 43rd Ave"
    m = re.search(r"\b(\d{1,5})(?:\s*-\s*(\d{1,5}))?\s+(?:on\s+)?(?P<main>(?:\d+(?:st|nd|rd|th)\b|[a-z])[a-z0-9' .\-]*)", low)
    if m:
        main_a = re.split(r",|\(|\bsan francisco\b|\bbetween\b", m.group("main"))[0]
        streets, note, win = street_phrase(st, main_a)
        lead = norm_words(main_a)
        if streets and win and " ".join(lead).find(win) > len(lead[0]) + 1 if lead else False:
            streets = set()          # "10 block parties on slow streets such as Lyon": street isn't next to the number
        if streets:
            nums = [int(m.group(1))] + ([int(m.group(2))] if m.group(2) else [])
            for street in sorted(streets, key=lambda n: -len(st.by_street[n])):
                if len(nums) == 2:
                    segs = [s for b in range(nums[0] // 100 * 100, nums[1] // 100 * 100 + 1, 100) for s in st.in_block(street, b)]
                else:
                    segs = st.at_address(street, nums[0])
                if segs:
                    n0 = nums[0]
                    notes = [note]
                    if len(nums) == 1 and n0 % 100 == 0:
                        notes.append(f"{n0} may mean the {n0} block")
                    if re.search(r"\b(?:park|plaza|playground|center|centre)\b", low):
                        notes.append("mentions a park or place; the address is used")
                    return [result("address", segs, "medium" if not note else "low", street, m.group(0), notes=notes)]

    # 4. intersections: "Haight and Masonic", "3rd St. & Thornton", "Ada Alley @ Ofarrell", "Fulton & Lyon & McAllister"
    parts = [p for p in re.split(r"\s*(?:&|@|/|\band\b|\bintersection of\b|,)\s*", low) if p.strip()]
    named = []
    for p in parts:
        streets, note, _ = street_phrase(st, p)
        if streets:
            named.append((streets, note, p))
    if len(named) >= 2:
        # three streets where the middle one runs between the other two = a block
        if len(named) == 3:
            for i in range(3):
                others = [named[j] for j in range(3) if j != i]
                for street in named[i][0]:
                    r = try_between(st, street.lower(), others[0][2], others[1][2], raw)
                    # a real block between the other two (not a fallback), and short, so a neighborhood name
                    # like "Bayview" can't stretch it across half the city
                    if r and r["segs"] and r["to_street"] and len(r["segs"]) <= 3:
                        r["notes"].append("read three street names as a block between two cross streets")
                        return [r]
        pairs = [(named[i], named[j]) for i in range(len(named)) for j in range(i + 1, len(named))]
        for (a_set, na, _), (b_set, nb, _) in pairs:
          for a in sorted(a_set):
            for b in sorted(b_set):
                nodes = st.intersection(a, b)
                if nodes:
                    segs = [s for s in st.by_street[a] + st.by_street[b] if s["fn"] in nodes or s["tn"] in nodes]
                    notes = [na, nb, "intersection only: all blocks touching it are listed; pick the right one"]
                    if len(named) > 2:
                        notes.append("more than two streets named")
                    return [result("intersection", segs, "low", a, raw, b, "", notes)]

    # 5. just a street name: "Coventry Court", "Rossi Avenue!", "LARCH", or a street at the start of a longer note
    place = re.search(r"\b(?:park|plaza|playground|center|centre|wharf|warf|commons|rec)\b", low)
    first = re.split(r"[.;,!(]|\bit is\b|\bwhere\b|\bwhich\b", low)[0]
    words = norm_words(first)
    if 0 < len(words) <= 5:
        streets, note, _ = street_phrase(st, first)
        if streets and place and (note or not any(w in SUFFIXES and w not in ("plaza", "plz") for w in words)):
            streets = set()          # "Martin Luther King Park", "Gambier Plaza": a place, not a street
        if streets:
            street = sorted(streets, key=lambda n: len(st.by_street[n]))[0]
            segs = st.by_street[street]
            notes = [note]
            if len(streets) > 1:
                notes.append(f"could also be {', '.join(sorted(streets - {street}))}")
            if place:
                notes.append("mentions a park or place; check the street")
            if len(segs) <= 2:
                conf = "medium" if not note and not place else "low"
                return [result("street_only", segs, conf, street, raw, notes=notes + ["short street; whole street used"])]
            return [result("street_only", segs if len(segs) <= 6 else [], "low" if len(segs) <= 6 else "none", street, raw,
                           notes=notes + [f"only a street name; {street} has {len(segs)} blocks, which one?"])]

    if failed_between:
        return failed_between
    reason = "no street, block, or address found"
    if place:
        reason = "names a park or place, not a street block"
    elif len(low) > 200:
        reason = "long description; needs a person to read it"
    return [result("none", [], "none", "", raw[:80], notes=[reason])]


# ---------------------------------------------------------------- output
def ranges(s):
    out = []
    for a, b in sorted((s["lf"], s["rt"]), key=lambda r: (min(r) % 2, min(r))):
        if a or b:
            out.append(f"{min(a, b)}-{max(a, b)}")
    return ", ".join(out)


def wkt(segs):
    lines = ["(" + ", ".join(f"{x:.5f} {y:.5f}" for x, y in s["pts"]) + ")" for s in segs]
    if not lines:
        return ""
    return "LINESTRING " + lines[0] if len(lines) == 1 else "MULTILINESTRING (" + ", ".join(lines) + ")"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--column", default="Block you want to party on")
    ap.add_argument("--data", default=os.path.join(ROOT, "data", "streets.json"))
    ap.add_argument("--out")
    a = ap.parse_args()
    st = Streets(*load(a.data))
    rows = list(csv.DictReader(open(a.csv, newline="", encoding="utf-8-sig")))
    if rows and a.column not in rows[0]:
        sys.exit(f'column "{a.column}" not found; columns are: {list(rows[0])}')
    out_path = a.out or re.sub(r"\.csv$", "", a.csv) + "_matched.csv"
    extra = ["source_row", "part", "parts", "matched_text", "cnn", "street", "from_street", "to_street",
             "address_low", "address_high", "address_ranges", "supervisor_district", "nhood", "wkt",
             "confidence", "method", "notes"]
    counts = defaultdict(int)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) + extra if rows else extra)
        w.writeheader()
        for i, row in enumerate(rows, 1):
            try:
                text = row.get(a.column, "") or ""
                results = parse(st, text)
                cap = "low" if len(text) > 400 else "medium" if len(text) > 250 else None
                for r in results:
                    if cap and r["confidence"] in ("high", "medium") and r["confidence"] != cap and (cap == "low" or r["confidence"] == "high"):
                        r["confidence"] = cap
                        r["notes"].append("long description; check this is the main location")
            except Exception as e:     # never lose a row
                results = [result("none", [], "none", "", row.get(a.column, "")[:80], notes=[f"error: {e}"])]
            for p, r in enumerate(results, 1):
                segs = sorted({s["cnn"]: s for s in r["segs"]}.values(), key=lambda s: s["cnn"])
                nums = [n for s in segs for n in (*s["lf"], *s["rt"]) if n > 0]
                if r["from_street"]:
                    f_st, t_st = r["from_street"], r["to_street"]
                else:
                    f_st, t_st = (segs[0]["f"], segs[0]["t"]) if len(segs) == 1 else ("", "")
                w.writerow({**row,
                    "source_row": i, "part": p, "parts": len(results), "matched_text": r["text"],
                    "cnn": ";".join(str(s["cnn"]) for s in segs), "street": r["street"],
                    "from_street": f_st, "to_street": t_st,
                    "address_low": min(nums) if nums else "", "address_high": max(nums) if nums else "",
                    "address_ranges": "; ".join(ranges(s) for s in segs),
                    "supervisor_district": ";".join(sorted({str(s["sup"]) for s in segs if s["sup"]})),
                    "nhood": ";".join(sorted({s["nhood"] for s in segs if s["nhood"]})),
                    "wkt": wkt(segs), "confidence": r["confidence"], "method": r["method"],
                    "notes": "; ".join(r["notes"])})
                counts[r["confidence"]] += 1
    print(f"wrote {out_path}: {len(rows)} input rows -> {sum(counts.values())} locations "
          + ", ".join(f"{k} {counts[k]}" for k in ("high", "medium", "low", "none")))


if __name__ == "__main__":
    main()
