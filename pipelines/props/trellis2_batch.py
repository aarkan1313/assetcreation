"""Trellis2 batch runner — load model ONCE, run N concept images.

Trellis2 has high startup cost (model load: ~50s warm, ~5min cold) and
high per-prop cost broken into 2 stages:
  - mesh generation: ~20-25s on RTX 5090 (the 4B DiT)
  - postprocess (UV + texture bake + GLB pack): 4-20s per config

For batch authoring (e.g. "make 10 props for the lava biome"), loading the
pipeline once and reusing it across all concepts saves ~50s × N. This module
provides a clean BatchRunner that does that.

Usage from python (recommended for orchestrators):

    from pipelines.props.trellis2_batch import BatchRunner, BatchSpec
    runner = BatchRunner()              # loads pipeline (one-time)
    runner.run_one(BatchSpec(
        concept_path=Path("..."),
        out_dir=Path("..."),
        preset="balanced",              # or "scatter" / "hero" / "hi_tex"
    ))

Usage from CLI (one-off ad-hoc):

    python trellis2_batch.py \
        --concepts D:/assets/world/props/concepts/ruined_obelisk_a/source.png \
                   D:/assets/world/props/concepts/mushroom_cap/source.png \
        --preset balanced \
        --out-root D:/assets/world/props/ai_routes/trellis2

Outputs land at <out-root>/<concept_id>/{model_lod0.glb, prop.json}.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# Trellis2 expects to be run from its own venv. This module is meant to be
# invoked via `D:\assets\animators\Trellis2\venv\Scripts\python.exe`. We
# reach into Trellis2's source dir (which has trellis2/ as a python package
# at root rather than a pip-installed package).
TRELLIS2_ROOT = Path(r"D:\assets\animators\Trellis2")
sys.path.insert(0, str(TRELLIS2_ROOT))

# Defer Trellis2 imports until BatchRunner is instantiated, so this module
# can be imported by orchestrators without Trellis2's heavy deps.
_LAZY_IMPORTED = False


PRESETS = {
    # id -> (decimation_target, texture_size). Mirrors ai_route_dispatch presets.
    "scatter":  dict(decimation_target=50_000,  texture_size=1024),
    "balanced": dict(decimation_target=200_000, texture_size=2048),
    "hero":     dict(decimation_target=500_000, texture_size=2048),
    "hi_tex":   dict(decimation_target=200_000, texture_size=4096),
}


@dataclass
class BatchSpec:
    concept_path: Path
    out_dir: Path
    preset: str = "balanced"
    seed: int | None = None  # reserved for future use (Trellis2 doesn't currently expose seed cleanly)
    extra: dict = field(default_factory=dict)


@dataclass
class BatchResult:
    concept_path: Path
    out_dir: Path
    preset: str
    glb_path: Path
    wall_clock_s: float
    mesh_gen_s: float
    postprocess_s: float
    verts: int
    faces: int
    texture_px: int
    glb_mb: float
    ok: bool
    error: str | None = None


class BatchRunner:
    """Loads the Trellis2 pipeline + envmap ONCE; reuses across run_one() calls.

    Each call to run_one() generates a fresh mesh (Trellis2 doesn't reuse mesh
    generations across different concepts) but skips the heavy pipeline reload.

    Patches required for this batch runner to work:
      - flex_gemm/kernels/__init__.py — DLL search dirs
      - flex_gemm/kernels/triton/__init__.py — pure-torch fallback (sentinel + dtype safe)
    See pipelines/props/TRELLIS2_PATCHES.md.
    """

    def __init__(
        self,
        *,
        hdri_path: Path | None = None,
        device: str = "cuda",
        verbose: bool = True,
    ):
        os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        self.hdri_path = hdri_path or TRELLIS2_ROOT / "assets" / "hdri" / "forest.exr"
        self.device = device
        self.verbose = verbose
        self.pipeline = None
        self.envmap = None
        self._load_t = 0.0
        self._lazy_load()

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"[trellis2_batch] {msg}")

    def _lazy_load(self) -> None:
        global _LAZY_IMPORTED
        import cv2  # noqa: F401
        import torch
        from PIL import Image  # noqa: F401
        from trellis2.pipelines import Trellis2ImageTo3DPipeline
        from trellis2.renderers import EnvMap
        import o_voxel  # noqa: F401
        import trimesh as _tm  # noqa: F401
        _LAZY_IMPORTED = True

        self._log(f"loading envmap from {self.hdri_path}")
        exr_bgr = cv2.imread(str(self.hdri_path), cv2.IMREAD_UNCHANGED)
        exr_rgb = cv2.cvtColor(exr_bgr, cv2.COLOR_BGR2RGB)
        self.envmap = EnvMap(torch.tensor(exr_rgb, dtype=torch.float32, device=self.device))

        self._log("loading microsoft/TRELLIS.2-4B (cached if previously downloaded)")
        t0 = time.time()
        self.pipeline = Trellis2ImageTo3DPipeline.from_pretrained("microsoft/TRELLIS.2-4B")
        self.pipeline.cuda()
        self._load_t = time.time() - t0
        self._log(f"pipeline ready in {self._load_t:.1f}s; free GPU mem: {torch.cuda.mem_get_info()[0]/1e9:.1f} GB")

    def run_one(self, spec: BatchSpec) -> BatchResult:
        from PIL import Image
        import o_voxel
        import trimesh

        if spec.preset not in PRESETS:
            raise ValueError(f"unknown preset {spec.preset!r}; pick one of {list(PRESETS)}")
        preset_cfg = PRESETS[spec.preset]

        spec.out_dir.mkdir(parents=True, exist_ok=True)
        out_glb = spec.out_dir / "model_lod0.glb"
        wall_t0 = time.time()

        try:
            self._log(f"running on {spec.concept_path}")
            image = Image.open(spec.concept_path)

            t_mesh = time.time()
            mesh = self.pipeline.run(image)[0]
            mesh.simplify(16777216)
            mesh_gen_s = time.time() - t_mesh

            self._log(f"  mesh gen: {mesh_gen_s:.1f}s -> {len(mesh.vertices)} verts")

            t_post = time.time()
            glb_obj = o_voxel.postprocess.to_glb(
                vertices=mesh.vertices, faces=mesh.faces,
                attr_volume=mesh.attrs, coords=mesh.coords,
                attr_layout=mesh.layout, voxel_size=mesh.voxel_size,
                aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
                decimation_target=preset_cfg["decimation_target"],
                texture_size=preset_cfg["texture_size"],
                remesh=True, remesh_band=1, remesh_project=0,
                verbose=False,
            )
            if hasattr(glb_obj, "export"):
                glb_obj.export(str(out_glb), file_type="glb")
            else:
                # Defensive: o_voxel API may evolve.
                raise RuntimeError(f"unexpected to_glb return type {type(glb_obj)}")
            postprocess_s = time.time() - t_post
            wall_clock_s = time.time() - wall_t0

            # Inspect output mesh
            m = trimesh.load(out_glb, force="mesh")
            mat = m.visual.material if hasattr(m.visual, "material") else None
            tex_px = mat.baseColorTexture.size[0] if mat and getattr(mat, "baseColorTexture", None) else None
            glb_mb = out_glb.stat().st_size / (1024 * 1024)

            # Write a prop.json manifest snapshot so we can audit later.
            manifest = {
                "schema": "prop_asset.v1",
                "id": spec.out_dir.name,
                "kit": "ai_hero_props",
                "source_method": "trellis2_image_to_3d",
                "source_image": str(spec.concept_path),
                "license": "MIT",
                "render_class": "hero_prop",
                "lods": [{"file": "model_lod0.glb", "max_distance_m": 25, "triangles": len(m.faces)}],
                "stats": {
                    "vertices": len(m.vertices),
                    "faces": len(m.faces),
                    "texture_px": tex_px,
                    "glb_mb": round(glb_mb, 2),
                },
                "route": {
                    "adapter": "pipelines/props/trellis2_batch.py",
                    "preset": spec.preset,
                    "decimation_target": preset_cfg["decimation_target"],
                    "texture_size": preset_cfg["texture_size"],
                    "wall_clock_s": round(wall_clock_s, 1),
                    "mesh_gen_s": round(mesh_gen_s, 1),
                    "postprocess_s": round(postprocess_s, 1),
                    "torch_version": __import__("torch").__version__,
                },
            }
            (spec.out_dir / "prop.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            self._log(f"  DONE in {wall_clock_s:.1f}s -> {len(m.faces)} faces / {tex_px}² / {glb_mb:.2f} MB")
            return BatchResult(
                concept_path=spec.concept_path, out_dir=spec.out_dir, preset=spec.preset,
                glb_path=out_glb, wall_clock_s=round(wall_clock_s, 1),
                mesh_gen_s=round(mesh_gen_s, 1), postprocess_s=round(postprocess_s, 1),
                verts=len(m.vertices), faces=len(m.faces),
                texture_px=tex_px or 0, glb_mb=round(glb_mb, 2), ok=True,
            )
        except Exception as e:
            self._log(f"  FAIL: {type(e).__name__}: {e}")
            return BatchResult(
                concept_path=spec.concept_path, out_dir=spec.out_dir, preset=spec.preset,
                glb_path=out_glb, wall_clock_s=round(time.time() - wall_t0, 1),
                mesh_gen_s=0.0, postprocess_s=0.0,
                verts=0, faces=0, texture_px=0, glb_mb=0.0,
                ok=False, error=f"{type(e).__name__}: {e}",
            )

    def run_batch(self, specs: Iterable[BatchSpec]) -> list[BatchResult]:
        results = []
        for s in specs:
            results.append(self.run_one(s))
        return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--concepts", nargs="+", type=Path, required=True,
                    help="One or more concept image paths.")
    ap.add_argument("--out-root", type=Path,
                    default=Path(r"D:\assets\world\props\ai_routes\trellis2"))
    ap.add_argument("--preset", default="balanced", choices=list(PRESETS.keys()))
    ap.add_argument("--id-prefix", default="",
                    help="Prefix prepended to each prop_id (the concept folder name).")
    args = ap.parse_args()

    runner = BatchRunner()
    specs = []
    for p in args.concepts:
        if not p.exists():
            print(f"[trellis2_batch] missing concept: {p}", file=sys.stderr)
            return 1
        # Use the parent folder name as the prop_id, OR the file stem if it's a loose file.
        prop_id = p.parent.name if p.parent.name not in ("concepts", "props") else p.stem
        out_dir = args.out_root / f"{args.id_prefix}{prop_id}"
        specs.append(BatchSpec(concept_path=p, out_dir=out_dir, preset=args.preset))

    results = runner.run_batch(specs)

    print("\n=== BATCH SUMMARY ===")
    print(f"{'prop_id':<28} {'preset':<10} {'time_s':>7} {'verts':>8} {'faces':>8} {'tex':>5} {'GLB MB':>7} {'OK':>4}")
    for r in results:
        print(f"{r.out_dir.name:<28} {r.preset:<10} {r.wall_clock_s:>7.1f} "
              f"{r.verts:>8} {r.faces:>8} {str(r.texture_px):>5} {r.glb_mb:>7.2f} {str(r.ok):>4}")
    fails = [r for r in results if not r.ok]
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
