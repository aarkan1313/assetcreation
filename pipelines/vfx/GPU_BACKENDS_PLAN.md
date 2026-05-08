# GPU backends - install plan (do not run yet)

> **⚠ 2026-05-07 — superseded by research brief #04.** This four-backend plan is half-stale. The current state of each:
>
> - **NVIDIA Warp** ✅ — keep, **promote to primary GPU backend.** Validated on RTX 5090 sm_120 (CUDA 12.9, native Windows wheels).
> - **Taichi** 🟡 — drop. In maintenance mode since mid-2024 (per [taichi-dev/taichi#8506](https://github.com/taichi-dev/taichi/discussions/8506)).
> - **PhiFlow** 🟡 — keep on watch list only. Alive (PyPI 3.4.0 Aug 2025), Apache-2.0, healthy small team. Strength is differentiable PDE for ML training (gradients through PDE solves) — overkill for baked flipbooks. Adopt only if a future use case actually needs differentiable physics.
> - **LiquidFun** ❌ — drop. Dead.
>
> Per the brief, **the priority order also changes:** build LLM-driven `effect_from_description.py` *first* (addresses the "18 palette-swap recolors" content-authoring problem at the right layer), *then* Warp-port the particle baker. The GPU port is no longer #1 priority — content authoring is.
>
> Full reasoning: [`docs/research_briefs/2026_05_07_sota_survey/04_vfx_3d_bake.response.md`](../../docs/research_briefs/2026_05_07_sota_survey/04_vfx_3d_bake.response.md).
>
> Sections below kept for historical reference; **only the Warp section is still active**, with priority deferred behind the LLM authoring tool.

---

The 5090 is busy with other pipelines, so we keep these as **install/setup
documentation** for now. The current CPU bakers (`particle_cpu`,
`fracture2d`, `smoke_field`) cover the demo phenomenon classes; GPU bakers
become primary once they're worth the GPU time.

## Order of adoption (highest leverage first)

1. **Taichi** - drop-in replacement for both `particle_cpu` and `smoke_field`
   at 50-200x speed; permits real MPM/falling-sand effects we can't do in
   pure numpy. Same effect.json schema.

   ```powershell
   python -m pip install --upgrade taichi   # latest stable; ~50 MB
   ```
   Validate: `python -c "import taichi as ti; ti.init(arch=ti.gpu); print(ti.lang.impl.current_cfg().arch)"`

2. **NVIDIA Warp** - differentiable particles, custom CUDA kernels in Python.
   Best fit for "magic black hole" vortex / swirl / attraction effects.

   ```powershell
   python -m pip install warp-lang
   ```
   Validate: `python -c "import warp as wp; wp.init()"`

3. **PhiFlow** - 2D smoke / vector fields, differentiable. Better quality
   than the in-house numpy smoke baker, plus exports flow-maps directly.

   ```powershell
   python -m pip install phiflow phi-tf phi-torch  # pick one backend
   ```

4. **LiquidFun** - 2D Box2D fluid timing, runs on CPU but the existing
   spell-lab build is already configured. Keep as a **secondary** baker
   (most projectile work is fine on `particle_cpu`).

5. **SPlisHSPlasH** - high-quality SPH water; offline reference only.

## Adapter shape (proposed)

Each new GPU backend should mirror `baker_particle_cpu.py`:
- Accept an `Effect` (Pydantic) and an `out_root: Path`.
- Honor `effect.fps`, `effect.bounds_px`, `effect.duration_s`.
- Write `frames/frame_NNNN.png` + `flipbook.png` + a backend-specific extras file (`particles.json`, `field.json`, `fragments.json`).
- Return a `BakeManifest`.
- Register in `bake.py`'s `BACKENDS` dict.

If we add an enum value to `Backend` in `schemas.py`, every existing effect.json keeps working (extra=forbid only blocks unknown fields, not unknown literal values - new literal values are additive).

## Models we already cataloged

- Newton 1.0 (2026 GA, NVIDIA + Disney + DeepMind via Warp) - granular materials, deformables, USD export. Worth a single demo when 5090 is free.
- Genesis - Apache-2.0 unified physics. Watch, don't depend on.
- Mantaflow / Blender headless - smoke/fire reference baker. Already routed via Blender 5.1 which we have installed locally.

## Migration tool already built

`pipelines/vfx/import_spell_lab.py` already pulls 11 existing artifacts from
`D:\spell lab\spell-sandbox\artifacts\` into the new catalog shape, marked
`backend: external` so re-baking is a no-op. When the GPU bakers come
online, we can re-run the original spell-lab demos with our new schema by
flipping `backend: external` → `backend: taichi` (or whichever) and
filling in `backend_params`.

## What a GPU-active session should validate

When you do return to a GPU-free moment:

1. `pip install taichi`
2. Build `baker_taichi_particle.py` with the same shape as `baker_particle_cpu.py` but using `@ti.kernel` for the integrator.
3. Bake `vfx/catalog/spells/fireball_projectile/effect.json` with `--backend taichi` and confirm visual parity within ~1% pixel diff.
4. Wire it into `bake.py`.
5. Build `baker_taichi_smoke.py` similarly (taichi MPM or grid smoke). Replace `baker_smoke_field.py` for higher resolutions.

Until then, all three CPU bakers ship demo-quality output.
