# VFX (3D bake) — Manual Review (2026-05-07)

`pipelines/vfx/` lane (the content baker, not `art_lab/shaders/`). See [docs/VFX_LANES.md](../VFX_LANES.md) for lane disambiguation.

## Inventory (truth from disk)

| Category | Effects | Backend usage |
|---|---|---|
| `spells/` | **28 effects** | mostly particle_cpu; auras use smoke_field |
| `projectiles/` | 6 effects | particle_cpu |
| `destruction/` | 4 effects | fracture2d (Voronoi shards) |
| `ambient/` | 7 biome haze effects | volumetric_fog (3D, not flipbook) |
| `environment/` | 1 effect (`dust_drift`) | particle_cpu |
| **Total** | **46 effects** | 4 backends used |

**Migrated from spell lab:** `vfx/migrated_from_spell_lab/` has 11 historical effects (4 spell + 5 environment + 2 destruction). These are `backend=external` — referenced, not re-baked.

**Output shape per effect:**
- `effect.json` (canonical authoring artifact, Pydantic-schema'd)
- `manifest.json` (bake provenance, audio cues, metrics)
- `frames/frame_NNNN.png` (raster frames, typically 256² or 320² RGBA)
- `flipbook.png` (atlas grid for Godot import)
- backend-specific extras: `particles.json` / `field.json` / `fragments.json + bodies.json`
- `godot/` — `<id>.tscn` + `sprite_frames.tres` + `<id>_billboard.tscn` + shader/material companions

**Audio sync:** 36/46 effects have `audio_cues` in their manifest (frame-synced trigger points for `vfx/runtime/AudioCueBus.gd` to fire on `frame_changed`).

## The honest finding: the 6-element grid is mostly recolors

I diffed effect.json across the element × archetype catalogue. Here's what came back:

### Spell bursts (6 elements, same archetype)
| Effect | count | speed | palette change? | other physics? |
|---|---|---|---|---|
| fire_burst | 180 | 80.0 | ✓ | — |
| arcane_burst | 180 | 80.0 | ✓ | — |
| ice_burst | 180 | 88.0 | ✓ | — |
| earth_burst | 180 | 56.0 | ✓ | — |
| lightning_burst | 180 | 128.0 | ✓ | — |
| shadow_burst | 180 | 68.0 | ✓ | — |

Same backend, same particle count, ±60% speed delta, **only palette differs.**

### Spell projectiles (6 elements)
Same pattern. count=110, speed=25 ±60%, palette swap.

### Spell impacts (6 elements)
Same pattern. count=95, speed=70 ±60%, palette swap.

### Auras (6 elements)
All use `smoke_field` backend. Backend params not visible in effect.json — they may differ in field config or palette. Likely also recolors.

### Ambient haze (7 biomes)
Same `noise_frequency=3`, palette change per biome. Recolors.

### Where there *is* genuine variety
The blood/dust/spark cluster shows distinct physics:

| Effect | count | speed | drag | gravity | what makes it different |
|---|---|---|---|---|---|
| blood_drip | 20 | 10 | 0.4 | (0, +180) | tiny, slow, falls |
| blood_spray_large | 140 | 160 | 0.7 | (0, +240) | big, fast, falls |
| dust_puff_large | 85 | 80 | 2.0 | (0, **-25**) | medium, hi-drag, **rises** |
| spark_arcane | 50 | 160 | 1.0 | (0, -30) | mid, fast, **rises** |
| spark_metal | 40 | 180 | 1.2 | (0, +80) | small, fast, falls |
| spark_stone | 30 | 140 | 1.4 | (0, +120) | small, fast-ish, falls |

These are real physics variations — different masses, drags, gravity directions. The author actually tuned these.

## What works

- ✅ **Pipeline shape is clean.** effect.json is a real schema, manifest.json carries provenance, frames + flipbook + extras + godot/ are all per-effect deterministic outputs.
- ✅ **3D billboard / decal / mesh_trail / fog_volume export targets all work** — not just 2D flipbook. `godot/` per effect has both 2D `.tscn` and `_billboard.tscn`.
- ✅ **Audio cue infrastructure is real.** `manifest.extras.audio_cues` carries `[{"t": 0.0, "name": "burst"}, {"t": 0.3, "name": "settle"}]`, and `vfx/runtime/AudioCueBus.gd` autoload reads them. **36 of 46 effects have cues authored.**
- ✅ **Volumetric fog is its own thing.** 7 biome hazes use `baker_volumetric_fog.py` — emits a `density.png` slice atlas + a per-effect `fog.gdshader` + `fog_material.tres`. That's a real pipeline branch, not just a 2D effect copy.
- ✅ **Blood/dust/spark cluster is well-tuned.** Real physics variation, not template instantiation.
- ✅ **Migration path** (`import_spell_lab.py`) preserves legacy artifacts as `backend=external` without re-baking. Sound design.

## What's open / weak

1. **The headline 24-cell element × archetype grid is mostly palette-swapped.** 18 of the 24 cells (6 elements × 3 archetypes: burst/projectile/impact) are identical particle counts and gravity, with only palette + speed varying. **They are not 24 distinct effects** — they are 6 archetypes shown in 6 colors.
2. **`environment/` has 1 effect.** The other 5 environment effects are in `migrated_from_spell_lab/environment/` (legacy). The new authoring loop produced exactly one (`dust_drift`).
3. **`destruction/` has 4 effects.** `fracture2d` was a real proof of concept; never expanded beyond 4 demos (debris_chitin/stone/wood + shield_break).
4. **GPU bakers deferred.** `pipelines/vfx/GPU_BACKENDS_PLAN.md` plans Taichi/Warp/PhiFlow/LiquidFun. Not started — current 46 effects are all CPU bakes.
5. **The flipbook detail is thin.** 2-3 KB per RGBA frame at 256×256 = mostly transparent with a small particle pattern. Reads as "particle cluster," not "AAA spell impact." This is the same prototype-tier read as the UI icons.
6. **No author documentation per effect** — there's no "this is *why* fire_impact looks the way it does" rationale beyond effect.json. Hard to iterate without a designer's intent.

## User verdict (2026-05-07)

After scrolling the gallery:

1. **fire_burst vs arcane_burst:** "**mostly recolor, it's ok.**" Confirms the data finding — same animation, different palette.
2. (Auras — not separately checked, but consistent with the recolor pattern.)
3. **blood_drip / dust_puff / spark_metal:** "**I think they are different.**" Confirms — these have real physics tuning, and it shows.

**Overall:** "most of them I saw aren't great, but they weren't handcrafted or focused on super hard."

**Net read:** the user is correctly calibrated — the catalog is **proof-of-pipeline, not proof-of-content**. Nothing was hand-tuned for visual quality; the 24-cell grid was author_grid.py's procedural output. The pipeline can produce real effects (blood/dust/spark cluster shows it); it just hasn't been pointed at hand-tuning the spell archetypes.

## Pipeline-level read

- **State:** **infrastructure is real, content is thin and largely templated.** Same pattern as UI: the plumbing works, the catalog is mostly placeholder.
- **Strongest part:** the bake → manifest → frames + extras → Godot export contract. Volumetric fog is a real second backend. Audio cue plumbing is genuinely useful. fracture2d works.
- **Weakest part:** the headline "24 element × archetype effects" claim doesn't survive scrutiny. **18 of those 24 are palette swaps with minor speed tweaks.** The actual unique effects on disk are roughly: 4 fracture, 1 environment dust, 7 biome hazes, the blood/dust/spark cluster (~6 effects with real physics), the auras (6 smoke_field but probably also recolors), 11 migrated legacy. Net unique-by-physics-and-feel: ~15 effects, not 46.
- **What "shipping quality" would require:**
  1. Author each spell archetype's *physics* per element, not just palette. Fire impact should feel different from ice impact at the simulation level (faster falloff, different trail, different particle shape distribution).
  2. Replace flat-color palettes with per-effect texture maps for richness.
  3. GPU bakers (Taichi/Warp) for fluid-quality smoke and fog (currently 64×64 grid is "adequate" per the README).
  4. More fracture variations.

## Concrete next moves (if you want to push VFX further)

1. **Honest catalogue audit.** Mark the 18 recolor-spells as "palette variants of 3 base archetypes" in their manifests. Stop counting them as separate effects.
2. **Author one *real* per-element burst.** Pick fire vs. ice. Make fire_burst use upward gravity + fast falloff + flickering palette. Make ice_burst use slow drift + crystallizing pattern + slower lifetime. Confirm the bakers can express physics-level differentiation.
3. **Phase 13 GPU bakers** — Taichi/Warp/PhiFlow per `pipelines/vfx/GPU_BACKENDS_PLAN.md`. Half day. Big quality bump for fluid effects.
4. **Add more destruction variants** — fracture2d is solid; expand from 4 → ~10-12 (different material types, sizes, shatter patterns).
5. **A real environment effect set** — wind, leaves, rain, snow, embers. Currently just `dust_drift`.

---

## Research-calibrated update (2026-05-07)

Brief #04 ([response](../research_briefs/2026_05_07_sota_survey/04_vfx_3d_bake.response.md)) returned. **The deferred GPU plan needs revising; the real bottleneck is content authoring, not sim throughput.**

### Headline: GPU backends plan is half-stale

Of the 4 backends in [GPU_BACKENDS_PLAN.md](../../pipelines/vfx/GPU_BACKENDS_PLAN.md):

| Backend | Status | Verdict |
|---|---|---|
| **NVIDIA Warp** | ✅ Alive, validated on RTX 5090 sm_120 (CUDA 12.9, native Windows wheels) | **Promote to primary GPU backend.** |
| **PhiFlow** | ✅ Alive (PyPI 3.4.0 Aug 2025), Apache-2.0, JAX/PyTorch backends, healthy small team | **Keep optional / watch.** Strength is differentiable PDE for ML training (gradients through PDE solves) — overkill for baked flipbooks. Adopt only if a future use case actually needs differentiable physics. |
| **Taichi** | 🟡 Maintenance mode mid-2024 (per [taichi-dev/taichi#8506](https://github.com/taichi-dev/taichi/discussions/8506)) | **Drop from plan.** |
| **LiquidFun** | ❌ Dead | **Drop from plan.** |

GPU plan reduces from 4 backends to **Warp-primary, PhiFlow-optional**.

### Skip diffusion VFX

Sora 2 was discontinued April 2026; AnimateDiff produces RGB video, not alpha-matted tileable flipbooks. Diffusion is the wrong tool for our bake-to-flipbook use case. **Don't pursue.**

### Reordered priorities

The brief's recommendation, in order:

1. **Build LLM-driven `effect_from_description.py` first** — turns plain-language design intent into seeded effect.json. **This addresses the "18 of 24 palette-swap recolors" issue at the right layer (content authoring), not the sim layer.** Sub-day scaffold owned by us.
2. **Then Warp-port the particle baker** — replaces `particle_cpu` for "magic black hole" vortex / swirl / attraction effects where CPU bakers strain.
3. **Mesh fracture: use Blender Cell Fracture headless** — no exotic GPU lib needed. Already mostly free if we have Blender.
4. **Volumetric fog: add Schneider-Vos cloud noise** to the existing numpy `baker_volumetric_fog.py`. Small in-place upgrade, keeps the baker we already have.
5. **Audio cues: extend `manifest.json` with `audio_clip` field** — **don't adopt USD.** USD is overkill for flipbooks; JSON field works.

### What this changes

**Strategic:** simplifies a deferred plan and reorders Phase 13 priorities. The "GPU bakers next" instinct was correct in shape but wrong in priority — LLM authoring tool comes first because it fixes the actual quality gap (palette swaps).

**Tactical:**
- `GPU_BACKENDS_PLAN.md` will be flagged as superseded.
- `effect_from_description.py` queued as the next-actual-thing to build.
- Warp install gets done once we're ready to port (not before).
- PhiFlow install **NOT queued** — watch list only until a differentiable-physics use case appears.

### Texture worker impact

**None.** Brief #04 is entirely VFX-3D-bake internal.
