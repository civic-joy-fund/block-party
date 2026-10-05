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
  python3 scripts/render_striping_previews.py --samples 8218.2 7970.1 7728   # test images at several sizes

--samples writes striping/samples/<id>/<width>.webp (and full.webp at the PDF's full detail) plus
striping/samples/index.json, for comparing sizes on striping/samples.html before deciding on a
higher-resolution set.

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


def fetch_pdf(url, folder):
    pdf = os.path.join(folder, "d.pdf")
    req = urllib.request.Request(url, headers={"User-Agent": "block-party-striping-map"})
    with urllib.request.urlopen(req, timeout=120) as r, open(pdf, "wb") as f:
        f.write(r.read())
    return pdf


def raster(pdf, dpi, folder):
    """page 1 of the PDF as a PIL image at `dpi`"""
    for n in os.listdir(folder):
        if n.endswith(".png"):
            os.remove(os.path.join(folder, n))
    subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-r", str(dpi), "-png", pdf, os.path.join(folder, "p")],
                   check=True, capture_output=True)
    png = next(os.path.join(folder, n) for n in os.listdir(folder) if n.endswith(".png"))
    Image.MAX_IMAGE_PIXELS = None
    return Image.open(png).convert("RGB")


def shrink(im, width):
    return im if im.width <= width else im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)


def render(url, dest):
    with tempfile.TemporaryDirectory() as tmp:
        im = shrink(raster(fetch_pdf(url, tmp), 110, tmp), WIDTH)
        im.save(dest, "WEBP", quality=QUALITY, method=6)
        return im.size


def samples(data, ids, widths):
    """the same drawings at several sizes, to judge readability against file size"""
    out_root = os.path.join(ROOT, "striping", "samples")
    os.makedirs(out_root, exist_ok=True)
    idx_path = os.path.join(out_root, "index.json")
    index = json.load(open(idx_path)) if os.path.exists(idx_path) else {}
    for sid in ids:
        d = next((d for d in data["diagrams"] if d["id"] == sid and d["current"]), None)
        if not d:
            print(f"  no current diagram with ID {sid}"); continue
        folder = os.path.join(out_root, sid)
        os.makedirs(folder, exist_ok=True)
        entry = {"id": sid, "file": d["file"], "url": d["url"], "pdf_kb": d["size_kb"], "images": []}
        with tempfile.TemporaryDirectory() as tmp:
            pdf = fetch_pdf(d["url"], tmp)
            full = raster(pdf, 300, tmp)          # 300 dpi: about as much detail as the drawings carry
            entry["page_px"] = list(full.size)
            for w in widths:
                im = full if w == "full" else shrink(full, int(w))
                name = f"{w}.webp"
                im.save(os.path.join(folder, name), "WEBP", quality=QUALITY if w != "full" else 70, method=6)
                kb = round(os.path.getsize(os.path.join(folder, name)) / 1024)
                entry["images"].append({"width": w, "px": list(im.size), "kb": kb, "src": f"samples/{sid}/{name}"})
                print(f"  {sid} {w}: {im.size[0]}x{im.size[1]} px, {kb} KB", flush=True)
        index[sid] = entry
    json.dump(index, open(idx_path, "w"), indent=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--samples", nargs="*", help="diagram IDs to render at several sizes")
    ap.add_argument("--widths", default="1000,2000,3000,full")
    a = ap.parse_args()
    data = json.load(open(os.path.join(ROOT, "data", "striping.json"), encoding="utf-8"))
    if a.samples:
        samples(data, a.samples, a.widths.split(","))
        return
    os.makedirs(OUT, exist_ok=True)
    man_path = os.path.join(OUT, "manifest.json")
    manifest = json.load(open(man_path)) if os.path.exists(man_path) else {}
    todo = [d for d in data["diagrams"] if d["current"] and d["kind"] == "street" and
            (a.all or manifest.get(d["preview"], {}).get("modified") != d["modified"]
             or not os.path.exists(os.path.join(OUT, d["preview"] + ".webp")))]
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(todo)} previews to render", flush=True)
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
            print(f"  {i}/{len(todo)}", flush=True)
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
