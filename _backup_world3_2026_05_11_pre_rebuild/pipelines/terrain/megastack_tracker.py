"""Build a tracker for stitched mega-stack pulls.

Reads art_lab/biomes/data_wishlist.json's stitched tier and checks
each entry's status in the cache + pipelines/terrain/output/.
"""
import json
from pathlib import Path

REPO = Path(r"d:/assets")
WISH = REPO / "art_lab/biomes/data_wishlist.json"
DEMS = REPO / "dems"
OUTPUT = REPO / "pipelines/terrain/output"

d = json.loads(WISH.read_text(encoding="utf-8"))
stitched = d["tiers"]["stitched"]["regions"]

print(f"{'STATUS':12s} {'ID':35s} {'DATASET':14s} {'TILES':8s} NOTES")
print("-" * 110)

status_counts = {"DONE": 0, "PARTIAL": 0, "NEW": 0, "MISSING": 0}
done_ids = []
new_ids = []

for r in stitched:
    rid = r["id"]
    ds = r.get("dataset", "?")
    rows = r.get("rows", 3)
    cols = r.get("cols", 3)
    expected = rows * cols
    bbox = r["bbox"]

    # Check pipelines/terrain/output/<id>/height_16.png
    out_path = OUTPUT / rid / "height_16.png"
    has_stitched = out_path.exists()

    # Crude tile count: cache TIFs whose bbox-prefix matches the dataset and
    # whose lon falls in our bbox west..east range.
    w, s, e, n = bbox
    tile_count = 0
    for tif in DEMS.glob(f"{ds}_*.tif"):
        # Parse TIF filename bbox
        parts = tif.stem.split("_")
        if len(parts) < 5:
            continue
        try:
            tw = float(parts[-4])
            ts = float(parts[-3])
            te = float(parts[-2])
            tn = float(parts[-1])
        except ValueError:
            continue
        # Intersection check (simple)
        if tw < e and te > w and ts < n and tn > s:
            tile_count += 1

    if has_stitched and tile_count >= expected:
        status = "DONE"
        done_ids.append(rid)
    elif has_stitched and tile_count > 0:
        status = "PARTIAL"
    elif tile_count > 0:
        status = "PARTIAL"
    else:
        status = "NEW"
        new_ids.append(rid)
    status_counts[status] += 1

    notes = f"{tile_count}/{expected}"
    if has_stitched:
        notes += " stitched"
    print(f"{status:12s} {rid:35s} {ds:14s} {notes:8s}")

print()
print(f"DONE   : {status_counts['DONE']}")
print(f"PARTIAL: {status_counts['PARTIAL']}")
print(f"NEW    : {status_counts['NEW']}")
print()
print("---NEW---")
for n in new_ids:
    print(f"  {n}")
