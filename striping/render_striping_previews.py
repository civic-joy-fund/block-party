#!/usr/bin/env python3
"""
Render a small preview image of each striping diagram for the striping map.

For every current diagram in data/striping.json that has no preview yet, or whose PDF changed since
its preview was made, download the PDF, render page 1, and save striping/previews/<preview>.webp.
striping/previews/manifest.json remembers which PDF version each preview came from.

Usage (from the repo root):
  python3 scripts/render_striping_previews.py            # only new or changed diagrams
  python3 scripts/render_striping_previews.py --all      # redo everything
  python3 scripts/render_striping_previews.py --limit 20 # try a few first

Needs: poppler (pdftoppm) and Pillow.
  macOS:  brew install poppler && pip3 install pillow
  Ubuntu: sudo apt install poppler-utils && pip3 install pillow
"""
import argparse, json, os, subprocess, sys, tempfile, urllib.request
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "striping", "previews")
WIDTH = 1000          # preview width in pixels; diagrams are landscape
QUALITY = 55          # WebP quality: about 40-80 KB per preview


def render(url, dest):
    with tempfile.TemporaryDirectory() as tmp:
        pdf = os.path.join(tmp, "d.pdf")
        req = urllib.request.Request(url, headers={"User-Agent": "block-party-striping-map"})
        with urllib.request.urlopen(req, timeout=120) as r, open(pdf, "wb") as f:
            f.write(r.read())
        subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-r", "110", "-png", pdf, os.path.join(tmp, "p")],
                       check=True, capture_output=True)
        png = next(os.path.join(tmp, n) for n in os.listdir(tmp) if n.endswith(".png"))
        im = Image.open(png).convert("RGB")
        if im.width > WIDTH:
            im = im.resize((WIDTH, round(im.height * WIDTH / im.width)), Image.LANCZOS)
        im.save(dest, "WEBP", quality=QUALITY, method=6)
        return im.size


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    data = json.load(open(os.path.join(ROOT, "data", "striping.json"), encoding="utf-8"))
    man_path = os.path.join(OUT, "manifest.json")
    manifest = json.load(open(man_path)) if os.path.exists(man_path) else {}
    todo = [d for d in data["diagrams"] if d["current"] and d["kind"] == "street" and
            (a.all or manifest.get(d["preview"], {}).get("modified") != d["modified"]
             or not os.path.exists(os.path.join(OUT, d["preview"] + ".webp")))]
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(todo)} previews to render")
    done = failed = 0
    for i, d in enumerate(todo, 1):
        dest = os.path.join(OUT, d["preview"] + ".webp")
        try:
            w, h = render(d["url"], dest)
            manifest[d["preview"]] = {"path": d["path"], "modified": d["modified"], "w": w, "h": h}
            done += 1
        except Exception as e:
            failed += 1
            print(f"  failed {d['file']}: {e}", file=sys.stderr)
        if i % 25 == 0:
            json.dump(manifest, open(man_path, "w"), indent=0)
            print(f"  {i}/{len(todo)}")
    # forget previews for files that are gone
    keep = {d["preview"] for d in data["diagrams"] if d["current"]}
    for k in [k for k in manifest if k not in keep]:
        manifest.pop(k)
        try: os.remove(os.path.join(OUT, k + ".webp"))
        except FileNotFoundError: pass
    json.dump(manifest, open(man_path, "w"), indent=0)
    print(f"rendered {done}, failed {failed}, total previews {len(manifest)}")


if __name__ == "__main__":
    main()
