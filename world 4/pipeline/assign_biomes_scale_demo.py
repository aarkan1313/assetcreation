"""Assign biome labels to scale_demo's 16 tile meta.json files.

Hard-coded 4x4 layout matching BIOMES.md's sketch:
  Z=3:  alpine    alpine    rocky    rocky
  Z=2:  alpine    forest    forest   rocky
  Z=1:  forest    forest    desert   desert
  Z=0:  wetland   wetland   desert   desert

(meta.json's tile coords use Godot Z+, so the row at the top of the
sketch above is Z=3 in the on-disk tiles.)

Idempotent: overwrites the `biome` field, leaves everything else alone.
"""
from __future__ import annotations
import json
from pathlib import Path

TILES_DIR = Path(r"D:/assets/world 4/the world 4/worlds/scale_demo/tiles")

# Rows are Z=3 (top of sketch) down to Z=0 (bottom). Columns are X=0..3.
LAYOUT = [
    # X=0       X=1       X=2       X=3
    ["alpine",  "alpine",  "rocky",   "rocky"   ],  # Z=3
    ["alpine",  "forest",  "forest",  "rocky"   ],  # Z=2
    ["forest",  "forest",  "desert",  "desert"  ],  # Z=1
    ["wetland", "wetland", "desert",  "desert"  ],  # Z=0
]
GRID_N = 4
ROW_FOR_Z = {3: 0, 2: 1, 1: 2, 0: 3}  # Z=3 is layout[0]


def biome_at(tile_x: int, tile_z: int) -> str:
    return LAYOUT[ROW_FOR_Z[tile_z]][tile_x]


def main() -> int:
    if not TILES_DIR.is_dir():
        raise SystemExit(f"tiles dir missing: {TILES_DIR}")
    updated = 0
    for tx in range(GRID_N):
        for tz in range(GRID_N):
            meta_path = TILES_DIR / f"tile_{tx}_{tz}" / "meta.json"
            if not meta_path.is_file():
                raise SystemExit(f"missing tile meta: {meta_path}")
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["biome"] = biome_at(tx, tz)
            meta_path.write_text(
                json.dumps(meta, indent=2),
                encoding="utf-8",
                newline="\n",
            )
            updated += 1
            print(f"  tile_{tx}_{tz}: biome={meta['biome']}")
    print(f"\nwrote biome label into {updated} tile meta.json files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
