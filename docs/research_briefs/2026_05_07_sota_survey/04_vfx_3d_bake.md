# Research Brief — VFX 3D Bake Pipeline (2026 SOTA)

## Goal

Identify 2026-current SOTA tools for **CPU/GPU baking of game-engine VFX** — particle simulations, fluid simulations, fracture, smoke, fog. Current pipeline is CPU-only. We have a deferred GPU plan that might be stale.

## Hardware target

- RTX 5090 Laptop (24 GB VRAM, Blackwell sm_120, CUDA 12.8+ / torch >=2.7)
- Windows 11; Python 3.11/3.12 venvs preferred

## Context

We have a "content baker" VFX pipeline distinct from a separate shader-iteration pipeline (different brief). This one **simulates** physics → renders frames → flipbook + manifest + Godot SpriteFrames/decal/billboard/mesh-trail/fog-volume export.

**Current backends (all CPU):**
- `baker_particle_cpu.py` — numpy SoA particles + emitter + gravity + drag + Gaussian splats
- `baker_fracture2d.py` — Voronoi shards + Sutherland-Hodgman clip + radial burst velocity + spin
- `baker_smoke_field.py` — semi-Lagrangian advection 2D smoke field (64×64 grid; "adequate")
- `baker_volumetric_fog.py` — numpy 3D noise → Texture3D-via-slice-atlas + per-effect `fog.gdshader`
- `external` — already-baked artifacts migrated from spell lab

**Output catalog state (today):** 46 effect.json entries. Manual review found **18 of 24 spell-grid effects are palette-swap recolors** (same backend, same particle count, ±60% speed). 4 fracture effects, 7 volumetric fog hazes, blood/dust/spark cluster has real physics tuning. **Pipeline plumbing real, content thin.**

**Deferred GPU plan** at `pipelines/vfx/GPU_BACKENDS_PLAN.md` lists Taichi / Warp / PhiFlow / LiquidFun. **Not yet started.**

## Specific questions

1. **Is the Taichi/Warp/PhiFlow/LiquidFun plan still 2026-current?** Or have those been superseded?
   - **Taichi** — domain-specific Python language for differentiable parallel computing
   - **Warp** (NVIDIA) — Python-to-CUDA particle/cloth/fluid sim
   - **PhiFlow** — JAX/PyTorch fluid sim
   - **LiquidFun** — Box2D fluid extension
   What are the 2026-current options? Is there a clear winner for "Python-native GPU particle/fluid sim that exports to game-engine flipbooks"?

2. **What's 2026 SOTA for game-engine fluid/smoke baking specifically?** The use case is "simulate a smoke plume / fire vortex / explosion / liquid splash, output 16-32 frame flipbook PNG sequence." Is anything beating semi-Lagrangian for this scale? Real-time fluid sim that runs entirely on a 5090?

3. **What about ML-driven VFX?** E.g., diffusion models for VFX flipbook generation? Text-to-VFX? Are there 2026 tools that do "describe a fireball, get back a baked 16-frame flipbook with PBR" without writing a sim?

4. **Voronoi fracture in 2026.** Our 2D fracture works. Is there a 2026 SOTA for 3D mesh fracture for destruction VFX? Specifically: "given a prop GLB, produce N fracture variants for destruction" suitable for runtime instantiation.

5. **Volumetric fog tooling.** We hand-roll 3D noise volumes via numpy. Is there a 2026 standard for atmosphere/weather VFX baking — clouds, fog banks, weather systems — that exports to Godot's `shader_type fog` format?

6. **VFX authoring beyond effect.json.** Our authoring is hand-written effect.json + procedural gen via author_grid.py. Are there 2026 tools for "describe an effect in plain English → produce all the params + bake it"? Better than just an LLM filling out effect.json by hand.

7. **Audio-VFX sync.** We have `audio_cues` in manifest.json (frame-synced trigger points for runtime). Is there a 2026 standard for "VFX with embedded audio that ships as one asset" that we should adopt instead?

## Format of response

Per question:
1. Top 2-3 tool/approach recommendations with one-paragraph why
2. Hardware/install fit (RTX 5090 Blackwell sm_120 / Windows native; CUDA 12.8+ required)
3. License + cost notes (open-source preferred for game-engine baking)
4. Maturity check: actively maintained 2025/2026?
5. **Honest comparison** — does the new tool produce visibly better game-engine flipbooks than our current CPU bakers?

## Out of scope

- Houdini/Embergen (we don't have those licenses; programmatic batch only)
- Real-time game-engine particle systems (we want pre-baked flipbooks)
- Shader-driven VFX (different pipeline — see `05_vfx_shaders.md`)

## After response returns

Update `pipelines/vfx/GPU_BACKENDS_PLAN.md` with 2026 reality, and decide whether to start Phase 13 GPU implementation or something newer/different.
