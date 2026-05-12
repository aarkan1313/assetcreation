"""REVERTED — sets W4 anchor_v2 texture .import files back to defaults.

The "fix" to compress/mode=2 + compress/normal_map=1 was wrong:
- The albedo turned olive-yellow because VRAM-compressed RGB got channel-
  shuffled
- The black artifacts persisted, proving import settings weren't the cause

This script reverts the patch so we can diagnose the real issue with a
known-good texture state.
"""
from __future__ import annotations

from pathlib import Path

W4_MAT_DIR = Path("D:/assets/world 4/the world 4/materials/anchor_v2")

MATERIALS = ["scrub_dense", "tundra_lichen", "rocky_slope"]
MAPS = ["albedo", "normal", "roughness", "ao"]

# Original Godot defaults — same for all map kinds since they were the
# defaults from initial copy.
DEFAULTS = {
    "compress/mode": "0",
    "compress/normal_map": "0",
    "detect_3d/compress_to": "1",
}


def patch_import(import_path: Path, overrides: dict[str, str]) -> bool:
    if not import_path.exists():
        return False
    text = import_path.read_text(encoding="utf-8")
    out_lines: list[str] = []
    for line in text.splitlines():
        replaced = False
        for key, value in overrides.items():
            if line.startswith(key + "="):
                out_lines.append(f"{key}={value}")
                replaced = True
                break
        if not replaced:
            out_lines.append(line)
    import_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return True


def main() -> int:
    for mat in MATERIALS:
        mat_dir = W4_MAT_DIR / mat
        if not mat_dir.exists():
            continue
        for kind in MAPS:
            imp = mat_dir / f"{kind}.png.import"
            if patch_import(imp, DEFAULTS):
                print(f"reverted: {mat}/{kind}.png.import")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
