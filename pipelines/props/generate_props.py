"""Generate environment props (trees, rocks, barrels, doors) via Meshy or local Trellis2.

Workflow:
  1. You author a prop manifest (JSON list of {name, prompt or image_path})
  2. This script generates each prop, preprocesses it, and saves to world/props/output/<name>/
  3. Output is game-ready GLB (decimated, transformed, single mesh)

Usage:
    python generate_props.py <manifest.json> [options]

Manifest format:
[
  {"name": "oak_tree", "image": "D:\\\\path\\\\to\\\\oak_tree.png", "target_tris": 5000},
  {"name": "barrel",   "image": "D:\\\\path\\\\to\\\\barrel.png"},
  {"name": "boulder",  "image": "D:\\\\path\\\\to\\\\boulder.png", "target_tris": 8000}
]

Options:
    --skip-meshy        skip the Meshy generation step (use existing meshes in props/output/)
    --target-tris N     default target triangle count (default 5000 — props are typically simpler than chars)
    --dry-run           show plan only

Each prop:
  - Must have an `image` field pointing to a PNG/JPG reference
  - Optional `target_tris` overrides default
  - Optional `note` for documentation
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
PROPS_DIR = ROOT.parent.parent / "world" / "props" / "output"
MESHY_GENERATE = ROOT.parent.parent / "meshy" / "generate.py"
PREPROCESS = ROOT.parent.parent / "meshy" / "preprocess.py"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", type=Path)
    ap.add_argument("--skip-meshy", action="store_true")
    ap.add_argument("--target-tris", type=int, default=5000)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.manifest.exists():
        raise SystemExit(f"manifest not found: {args.manifest}")

    props = json.loads(args.manifest.read_text())
    if not isinstance(props, list):
        raise SystemExit("manifest must be a JSON array of prop objects")

    PROPS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"=== {len(props)} props in plan ===")
    for p in props:
        target = p.get("target_tris", args.target_tris)
        print(f"  {p['name']:25s}  -> {target} tris  (img: {Path(p['image']).name})")
    print()

    if args.dry_run:
        return

    succeeded = []
    failed = []
    for prop in props:
        name = prop["name"]
        image = Path(prop["image"])
        target = prop.get("target_tris", args.target_tris)
        prop_out_dir = PROPS_DIR / name
        prop_out_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n--- [{name}] ---")

        # Step 1: Meshy generate (writes to D:\assets\meshy\output\<name>\model.glb)
        meshy_glb = ROOT.parent.parent / "meshy" / "output" / name / "model.glb"
        if args.skip_meshy or meshy_glb.exists():
            print(f"  [skip meshy] reusing {meshy_glb}")
        else:
            if not image.exists():
                print(f"  ERROR image missing: {image}")
                failed.append({"name": name, "stage": "image-missing"})
                continue
            cmd = [sys.executable, str(MESHY_GENERATE), str(image), "--name", name, "--skip-render"]
            print(f"  $ generate.py {image.name}")
            r = subprocess.run(cmd)
            if r.returncode != 0 or not meshy_glb.exists():
                print(f"  FAILED meshy generate ({r.returncode})")
                failed.append({"name": name, "stage": "meshy"})
                continue

        # Step 2: preprocess into props/output/<name>/<name>.glb
        final_glb = prop_out_dir / f"{name}.glb"
        cmd = [sys.executable, str(PREPROCESS), str(meshy_glb), str(final_glb),
               "--target-tris", str(target)]
        print(f"  $ preprocess.py --target-tris {target}")
        r = subprocess.run(cmd)
        if r.returncode != 0:
            print(f"  FAILED preprocess ({r.returncode})")
            failed.append({"name": name, "stage": "preprocess"})
            continue

        # Save the manifest entry alongside the prop
        meta_path = prop_out_dir / "meta.json"
        meta_path.write_text(json.dumps({
            "name": name,
            "source_image": str(image),
            "target_tris": target,
            "note": prop.get("note", ""),
        }, indent=2))
        succeeded.append(name)
        print(f"  OK -> {final_glb}")

    summary = {
        "total": len(props),
        "succeeded": len(succeeded),
        "failed": len(failed),
        "successes": succeeded,
        "failures": failed,
    }
    summary_path = PROPS_DIR / "_batch_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"\n=== {len(succeeded)}/{len(props)} succeeded ===")
    print(f"summary: {summary_path}")


if __name__ == "__main__":
    main()
