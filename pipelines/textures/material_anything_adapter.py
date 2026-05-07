"""Material Anything adapter — generate PBR textures for an existing 3D mesh.

Per the SOTA report, Material Anything is the strongest open research model
for material *generation on a mesh* (not just image-to-PBR). It takes an
untextured 3D mesh + a text prompt and produces a fully PBR-textured mesh.

Workflow target:
  characters/preprocessed/<asset>.glb (or any OBJ) + prompt
    → Material Anything (WSL conda 'materialanything' env)
    → PBR-textured OBJ + albedo/normal/roughness/metalness/height maps
    → wrap in our manifest contract
    → optional Godot exporter pass

STATUS (2026-05): kaolin source build in progress in WSL. Once that lands,
this script wires through to the upstream `bash/test.sh` flow.

License: research code, check repo. Weights from xanderhuang/material_estimator
+ material_refiner (HF, ~8.6 GB total).

Usage (when working):
  python material_anything_adapter.py \
      --mesh D:/assets/meshy/preprocessed/goblin_p.glb \
      --prompt "ancient bronze armor, weathered, mossy" \
      --id goblin_bronze
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WSL_REPO = "/mnt/d/assets/animators/MaterialAnything"
WSL_OUTPUT_BASE = "/mnt/d/assets/world/textures/library"
WSL_DEMO_DIR = f"{WSL_REPO}/demo"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh", type=Path, required=True, help="Input mesh (GLB/OBJ)")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--steps", type=int, default=50)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--num-viewpoints", type=int, default=36)
    args = ap.parse_args()

    if not args.mesh.exists():
        raise SystemExit(f"mesh not found: {args.mesh}")

    # Material Anything wants OBJ in a directory. Convert from GLB if needed.
    work_dir = Path(r"D:\assets\world\textures\library") / args.id
    work_dir.mkdir(parents=True, exist_ok=True)
    mesh_in_dir = work_dir / "input"
    mesh_in_dir.mkdir(exist_ok=True)
    obj_path = mesh_in_dir / "mesh.obj"

    if args.mesh.suffix.lower() == ".obj":
        shutil.copy2(args.mesh, obj_path)
    else:
        # Convert GLB → OBJ via trimesh in current Python (simpler than spawning blender)
        try:
            import trimesh
        except ImportError:
            raise SystemExit("trimesh needed for non-OBJ inputs; pip install trimesh")
        scene = trimesh.load(args.mesh)
        if isinstance(scene, trimesh.Scene):
            mesh = trimesh.util.concatenate([m for m in scene.geometry.values() if isinstance(m, trimesh.Trimesh)])
        else:
            mesh = scene
        mesh.export(str(obj_path))
    print(f"[ma] mesh -> {obj_path}")

    # MA's pipeline expects an init texture (texture_kd.png) — use a white seed
    # if the user didn't supply one. This is what the official demo does.
    init_tex_path = mesh_in_dir / "texture_kd.png"
    if not init_tex_path.exists():
        seed_white = Path(r"D:\assets\animators\MaterialAnything\samples\textures\white.png")
        if seed_white.exists():
            shutil.copy2(seed_white, init_tex_path)
            print(f"[ma] init texture seeded from {seed_white.name}")
        else:
            # Fallback: write a 1024x1024 white PNG
            from PIL import Image as _Image
            _Image.new("RGB", (1024, 1024), (255, 255, 255)).save(init_tex_path)
            print(f"[ma] init texture written: 1024x1024 white")

    # Convert to WSL path
    wsl_input = "/mnt/" + str(mesh_in_dir).replace("D:\\", "d/").replace("\\", "/").lower()
    wsl_output = "/mnt/" + str(work_dir).replace("D:\\", "d/").replace("\\", "/").lower()

    cmd = [
        "wsl", "-d", "Ubuntu-24.04", "--",
        "bash", "-c",
        f"source /opt/miniconda3/etc/profile.d/conda.sh && conda activate materialanything && cd {WSL_REPO} && "
        f"python scripts/generate_texture_pbr_3d.py "
        f"--image2materials_model ./pretrained_models/material_estimator "
        f"--uvrefine_model ./pretrained_models/material_refiner "
        f"--input_dir {wsl_input} "
        f"--output_dir {wsl_output}/generate "
        f"--obj_name mesh "
        f"--obj_file mesh.obj "
        f"--prompt {args.prompt!r} "
        f"--add_view_to_prompt "
        f"--ddim_steps {args.steps} "
        f"--new_strength 1 --update_strength 0.5 --view_threshold 0.1 --blend 0 --dist 1.2 "
        f"--num_viewpoints {args.num_viewpoints} "
        f"--viewpoint_mode predefined --use_principle --update_steps 0 --update_mode heuristic "
        f"--seed {args.seed} --post_process --device 2080 --use_objaverse"
    ]
    print(f"[ma] running Material Anything in WSL...")
    print(f"     prompt: {args.prompt!r}")
    print(f"     output: {work_dir/'generate'}")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        raise SystemExit(f"Material Anything failed (rc={result.returncode})")

    # The pipeline emits {output_dir}/generate/material/ with the PBR maps
    material_dir = work_dir / "generate" / "material"
    if not material_dir.exists():
        print(f"  warning: expected {material_dir} not found — pipeline may have failed silently")
        return

    # Append to our catalog
    record = {
        "id": args.id,
        "source": "material_anything",
        "source_mesh": str(args.mesh),
        "prompt": args.prompt,
        "license": "research; check 3DTopia/MaterialAnything LICENSE",
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "library_path": str(work_dir.relative_to(Path("D:/assets"))),
        "ddim_steps": args.steps,
        "num_viewpoints": args.num_viewpoints,
        "seed": args.seed,
        "notes": "PBR textures generated from mesh + prompt via diffusion-on-views.",
    }
    catalog = Path("D:/assets/world/textures/catalog/materials.jsonl")
    catalog.parent.mkdir(parents=True, exist_ok=True)
    with catalog.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    print(f"[ma] done. catalog appended for {args.id}")


if __name__ == "__main__":
    main()
