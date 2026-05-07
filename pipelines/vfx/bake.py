"""VFX bake orchestrator. Routes effect.json to the right backend.

Per `research/I_vfx_lab_local_audit_and_migration_plan.md`:

  effect.json  ->  bake.py  ->  backends/<backend>_baker.py  ->
                                normalize  ->  pack flipbook  ->  manifest.json

v2 (2026-05-06): adds `volumetric_fog`, `decal_flipbook`, `runtime_trail`,
plus stubs for deferred GPU bakers. `decal_flipbook` reuses an underlying
phenomenon baker (default `particle_cpu`) - the export wrapper handles the
Decal scene shape, not a new sim. `runtime_trail` is no-bake; the export
target writes a RibbonTrailMesh scene.

CLI:
  python bake.py vfx/catalog/spells/fireball_projectile/effect.json
  python bake.py --all   # bake every effect.json under vfx/catalog/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from schemas import Effect  # noqa: E402

BACKENDS = {
    "particle_cpu":    ("baker_particle_cpu",    "bake"),
    "fracture2d":      ("baker_fracture2d",      "bake"),
    "smoke_field":     ("baker_smoke_field",     "bake"),
    "volumetric_fog":  ("baker_volumetric_fog",  "bake"),
    # external: skip - assumed baked elsewhere (e.g. spell-lab migration)
    # decal_flipbook: routes through underlying_backend, see _bake_decal()
    # runtime_trail: no bake
    # vat: deferred stub
    # taichi_*, warp, phiflow, liquidfun: GPU-bound, deferred
}

# Backends that produce no frames/flipbook (fog volumes etc.)
NO_FRAME_BACKENDS = {"volumetric_fog"}

# Backends that don't bake at all (runtime-only or external)
NO_BAKE_BACKENDS = {"external", "runtime_trail", "vat"}

# GPU bakers we know about but defer to GPU_BACKENDS_PLAN.md
GPU_DEFERRED = {"taichi_particle", "taichi_smoke", "warp", "phiflow", "liquidfun"}


def _bake_decal(effect: Effect, out_root: Path):
    """decal_flipbook is a wrapper: bake via the underlying phenomenon baker
    (particle_cpu by default) and tag the manifest as decal_flipbook."""
    underlying = effect.backend_params.get("underlying_backend", "particle_cpu")
    if underlying not in BACKENDS:
        raise ValueError(f"decal_flipbook underlying_backend={underlying!r} "
                         f"unknown (known: {list(BACKENDS)})")
    mod_name, fn_name = BACKENDS[underlying]
    mod = __import__(mod_name)
    fn = getattr(mod, fn_name)
    # Build a synthetic Effect with the underlying backend so the baker accepts it.
    eff_dict = effect.model_dump()
    eff_dict["backend"] = underlying
    sub_effect = Effect(**eff_dict)
    manifest = fn(sub_effect, out_root)
    # Re-tag the manifest backend to decal_flipbook so the exporter routes correctly.
    manifest.backend = "decal_flipbook"
    manifest.extras["underlying_backend"] = underlying
    return manifest


def bake_one(effect_path: Path) -> Path | None:
    effect = Effect.model_validate_json(effect_path.read_text(encoding="utf-8"))
    out_root = effect_path.parent

    if effect.backend in NO_BAKE_BACKENDS:
        # Runtime-only or external. Still emit a stub manifest so downstream
        # tools (gallery, link_validator) can find the effect.
        from datetime import datetime, timezone
        from schemas import BakeManifest
        manifest = BakeManifest(
            effect_id=effect.id,
            backend=effect.backend,
            n_frames=0,
            fps=effect.fps,
            bounds_px=effect.bounds_px,
            flipbook="",
            frames_dir="",
            extras={"runtime_only": effect.backend != "external"},
            metrics={},
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        (out_root / "manifest.json").write_text(manifest.model_dump_json(indent=2))
        print(f"[bake] {effect.id} ({effect.backend}): no-bake, stub manifest -> {out_root}")
        return out_root

    if effect.backend in GPU_DEFERRED:
        print(f"[bake] {effect.id}: backend {effect.backend!r} is GPU-deferred "
              f"(see GPU_BACKENDS_PLAN.md); skipping")
        return None

    if effect.backend == "decal_flipbook":
        manifest = _bake_decal(effect, out_root)
        _hoist_audio_cues(effect, manifest)
        (out_root / "manifest.json").write_text(manifest.model_dump_json(indent=2))
        print(f"[bake] {effect.id} (decal_flipbook via "
              f"{manifest.extras.get('underlying_backend')}): "
              f"{manifest.n_frames} frames -> {out_root}")
        return out_root

    if effect.backend not in BACKENDS:
        print(f"[bake] {effect.id}: backend {effect.backend!r} not implemented "
              f"(known: {list(BACKENDS)}); skipping")
        return None

    mod_name, fn_name = BACKENDS[effect.backend]
    mod = __import__(mod_name)
    fn = getattr(mod, fn_name)
    manifest = fn(effect, out_root)
    _hoist_audio_cues(effect, manifest)
    (out_root / "manifest.json").write_text(manifest.model_dump_json(indent=2))
    if effect.backend in NO_FRAME_BACKENDS:
        print(f"[bake] {effect.id} ({effect.backend}): no frames "
              f"(volumetric/runtime backend) -> {out_root}")
    else:
        print(f"[bake] {effect.id} ({effect.backend}): {manifest.n_frames} frames -> {out_root}")
    return out_root


def _hoist_audio_cues(effect: Effect, manifest) -> None:
    """If the authoring effect.json declared `_audio_cues` under
    `backend_params`, hoist it into `manifest.extras.audio_cues` so the
    runtime `AudioCueBus` autoload can consume it without re-reading
    effect.json. Cleared from the persisted manifest if no cues exist."""
    cues = effect.backend_params.get("_audio_cues")
    if cues:
        manifest.extras["audio_cues"] = cues


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("effect", type=Path, nargs="?")
    ap.add_argument("--all", action="store_true",
                    help="Bake every effect.json under vfx/catalog/")
    ap.add_argument("--catalog", type=Path,
                    default=Path(r"D:\assets\vfx\catalog"))
    args = ap.parse_args()

    if args.all:
        any_failed = False
        for ej in sorted(args.catalog.rglob("effect.json")):
            try:
                bake_one(ej)
            except Exception as e:
                any_failed = True
                print(f"[bake] FAILED {ej}: {e}")
        return 1 if any_failed else 0

    if not args.effect:
        ap.error("provide an effect.json path or --all")
    bake_one(args.effect)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
