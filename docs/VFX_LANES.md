# VFX Lanes — Which Pipeline Do I Use?

There are two VFX pipelines on disk. They look similar but solve different problems. **Don't merge them.** Pick the right one per task.

> **Reframe (per project framing 2026-05-06):** content here is throwaway. The point is to build pipelines that work, find their failure modes, and document the tradeoffs. This doc is about pipeline selection, not which fireball to ship.

## TL;DR

| If your task is… | Use |
|---|---|
| "Bake a fireball / explosion / spray with frames Godot can play as an AnimatedSprite2D" | **`pipelines/vfx/`** |
| "Iterate on a `.gdshader` file until it looks like a reference" | **`art_lab/shaders/`** |
| "Make a 3D billboard / decal / mesh trail / fog volume" | **`pipelines/vfx/`** (export_godot_3d targets this) |
| "Tune a shield-ripple visual; tweak hex_scale and fresnel_power" | **`art_lab/shaders/`** |
| "Author a damage-on-hit fire AOE with audio cues" | **`pipelines/vfx/`** (effect.json has `audio_cues`) |
| "Generate 80 portal-swirl variants and let scoring pick the best 24" | **`art_lab/shaders/`** (shader_evolve + shader_promote) |

## What each lane actually does

### `pipelines/vfx/` — content baker

**Authoring artifact:** `effect.json` (Pydantic-schema'd; `pipelines/vfx/schemas.py`)

**What it produces:**
- `manifest.json` (bake provenance + audio_cues + metrics)
- `frames/frame_NNNN.png` (per-frame raster output)
- `flipbook.png` (grid atlas of frames)
- backend-specific extras: `particles.json` / `fragments.json + bodies.json` / `field.json`
- For 3D effects: `fog.gdshader` (volumetric_fog only), or 3D billboard / decal / mesh_trail tscn

**Backends (4 CPU bakers + external):**
- `particle_cpu` — numpy SoA particles, emitter, gravity, drag (most spell effects)
- `fracture2d` — Voronoi shards + analytical motion (destruction)
- `smoke_field` — semi-Lagrangian 2D fluid (smoke, dust, fog haze)
- `volumetric_fog` — numpy 3D noise → Texture3D-via-slice-atlas (writes a fog.gdshader; this is the one place the bake lane writes shaders)
- `external` — already-baked artifacts migrated from `D:\spell lab\` (no rebake)

**Godot integration:**
- 2D: `SpriteFrames.tres` + `AnimatedSprite2D` scene → drop-in at `res://vfx/<kind>/<id>/`
- 3D: 4 export targets via `export_godot_3d.py` — `3d_billboard`, `decal`, `mesh_trail`, `fog_volume`
- Runtime helpers: `vfx/runtime/MeshTrail3D.gd` (RibbonTrail wrapper), `vfx/runtime/AudioCueBus.gd` (frame-synced cue autoload reading `manifest.extras.audio_cues`)

**Output catalog state (today):**
- 46 effect.json entries across 6 categories (28 spells, plus ambient/destruction/environment/projectiles/blood/dust)
- 39 2D + 43 3D Godot scenes

**One-line entry:** `python pipelines/vfx/bake.py --all` (all catalog) or `--effect <path>/effect.json` (one).

---

### `art_lab/shaders/` — shader iteration

**Authoring artifact:** `<request>.json` + a chosen `.gdshader` template

**What it produces:**
- `<candidate_id>.gdshader` (the actual Godot shader file, parameterized from a template)
- `<candidate_id>.tscn` (a one-quad scene that uses the shader)
- `request.json` (params + score)
- `preview.png` + `flipbook.png` + `frames/` (CPU proxy renders)
- batch-level: `gallery.html`, `batch_summary.json`, `evolution_summary.json`, `llm_review_packet.json`, `llm_review.md`

**Templates (6 first-party, all `canvas_item` 2D except one):**
- `ring_field_2d.gdshader` — magic circles, runes, portal rings
- `beam_lightning_2d.gdshader` — bolts, beams, energy slashes
- `dissolve_fire_2d.gdshader` — burn-edge / fire dissolve mask
- `shield_ripple_2d.gdshader` — hex shield + hit ripple
- `portal_swirl_2d.gdshader` — spiraling portal vortex
- `macro_detail_v1.gdshader` — terrain macro+detail PBR (3D, **not VFX** — see "edge cases" below)

**Workflow loop (LLM-driven):**
1. `shader_evolve.py` — generate N candidates from a template + reference-set, mutating params
2. `shader_compile_preview.py` / `shader_godot_render.py` — render previews (CPU proxy or Godot CLI)
3. `shader_reference_score.py` — score against curated reference images (color/silhouette/edge metrics, not OCR)
4. `shader_promote.py` — diversity-filtered shortlist into a `review_queues/<id>/`
5. `shader_batch_review.py` — build `llm_review_packet.json` for the next LLM iteration
6. `shader_lab_index.py` — static dashboard at `art_lab/shaders/index.html`

**Output catalog state (today):** 5 evolution batches (`shader_evolve_smoke_001`, `shader_review_smoke_001/002`, `shader_review_mutate_001`, `shader_review_upgrade_smoke_001`).

**One-line entry:** `python art_lab/tools/shader_evolve.py --template <name> --batch <id> --population 36 --generations 5 --reference <ref-set>`.

---

## Why both exist

The two lanes solve different problems with different physics:

| Aspect | `pipelines/vfx/` | `art_lab/shaders/` |
|---|---|---|
| **Output** | Raster frames you blit | Shader code that runs on GPU per-frame |
| **Authoring** | Imperative — particles/grid/Voronoi sim → frames | Declarative — params on a template, GPU-rasterized live |
| **Cost** | CPU bake once; runtime is cheap (sprite playback) | No bake; runtime cost is GPU shader per frame |
| **Iteration** | Slow (re-bake per change) | Fast (shader hot-reload + param sliders) |
| **Best fit** | Anything driven by physics: explosions, debris, smoke | Anything driven by formulas: rings, beams, ripples, portals |
| **Animation** | Pre-baked frame timeline | Driven by `TIME` uniform live |
| **Determinism** | Seeded → deterministic | Param-locked → deterministic |
| **Godot import** | `SpriteFrames` + `AnimatedSprite2D`/3D | `ShaderMaterial` on a quad/mesh |

If you tried to do a Voronoi fracture in a shader, you'd hate yourself. If you tried to bake a portal_swirl in particles, you'd waste 100× the runtime cost for worse-looking output.

## Edge cases

- **`macro_detail_v1.gdshader` lives in `art_lab/shaders/templates/` but it's a terrain shader, not VFX.** Worldgen historically owned it; post-nuke it's homeless. Keep it where it is for now — it's still a shader and `art_lab/` is the shader lane. If a new worldgen pipeline takes it, fine.

- **`pipelines/vfx/baker_volumetric_fog.py` writes a `fog.gdshader` per ambient effect.** This is the one case where the bake lane writes shader code, but it's narrow: the shader is the standard `shader_type fog;` boilerplate that samples the baked Texture3D atlas. The shader isn't the point; the baked density volume is.

- **Both lanes have galleries.** `pipelines/vfx/gallery.py` builds a static `vfx/index.html` over the catalog. `art_lab/tools/shader_lab_index.py` builds `art_lab/shaders/index.html` over batches. They're separate views; don't try to merge.

- **Both ship to Godot, but to different `res://` roots.** `pipelines/vfx/` lands at `res://vfx/<kind>/<id>/`. `art_lab/shaders/` lands at `res://shaders/<batch>/<candidate>/` (when a candidate is promoted into a Godot project). No overlap.

## When you might be tempted to merge them — don't

- "Both produce VFX, both have galleries, both ship to Godot." Yes — but the **artifact types are different objects in Godot**. `SpriteFrames` and `ShaderMaterial` aren't substitutable.
- "Couldn't `effect.json` reference a shader template?" It already can if you wire it (e.g., a future `backend: "shader"` could point at an `art_lab/shaders/templates/<name>.gdshader`). But: that's a feature decision, not a "merge the lanes" decision. If you do it, it's `pipelines/vfx/` *consuming* an `art_lab/` template, not the lanes becoming one.
- "The naming is confusing." Yes. But renaming either one breaks every doc that references it. Live with it; this doc is the disambiguator.

## Decision tree

```
Need a VFX. Ask:

  Is it animated by a formula (TIME-driven; rings, beams, ripples, portals,
  dissolves, shields, force fields, ground glyphs)?
    └── YES → art_lab/shaders/
              shader_evolve.py  → shader_promote.py  → drop into Godot

  Is it animated by simulation (particles, fracture, smoke, fluid, fog)?
    └── YES → pipelines/vfx/
              author effect.json → bake.py → export_godot[_3d].py

  Is it 3D-volumetric (fog volume, ambient haze)?
    └── YES → pipelines/vfx/  (volumetric_fog backend)

  Do you need it to drive sprite-sheet frames Godot can blit on a 2D layer?
    └── YES → pipelines/vfx/  (any 2D backend)

  Do you need a `ShaderMaterial.tres` you can drop on a Sprite2D / MeshInstance3D?
    └── YES → art_lab/shaders/

  Are you adding a new authoring artifact (e.g. `audio_cues`, palette, role) to a spell?
    └── YES → pipelines/vfx/  (effect.json schema is the place)

  Are you tuning a single visual until it looks right?
    ├── If it's a shader template → art_lab/shaders/
    └── If it's a particle/sim setup → pipelines/vfx/  (re-bake per change)
```

## Tools at a glance

### `pipelines/vfx/` (12 .py files)

| Tool | Role |
|---|---|
| `schemas.py` | Pydantic schemas — single source of truth for `effect.json` shape |
| `bake.py` | Orchestrator. Routes effect.json to one of 4 bakers. `--all` walks `vfx/catalog/` |
| `baker_particle_cpu.py` | numpy SoA particles + emitter + gravity + drag + Gaussian splats |
| `baker_fracture2d.py` | Voronoi shards + Sutherland-Hodgman clip + radial burst velocity + spin |
| `baker_smoke_field.py` | semi-Lagrangian 2D fluid solver (density + velocity grid; 64×64) |
| `baker_volumetric_fog.py` | numpy 3D noise → Texture3D-via-slice-atlas + writes `fog.gdshader` |
| `author_grid.py` | 24-cell element × archetype generator (fire/ice/lightning/earth/arcane/shadow × projectile/burst/aura/impact) |
| `author_damage.py` | 12-effect damage / impact catalogue (3 blood + 3 sparks + 3 dust + 3 debris) |
| `import_spell_lab.py` | Migrate `D:\spell lab\` artifacts into the new catalog with `backend: external` |
| `export_godot.py` | 2D: `SpriteFrames.tres` + `AnimatedSprite2D` `.tscn` |
| `export_godot_3d.py` | 3D: 4 targets (3d_billboard / decal / mesh_trail / fog_volume) |
| `gallery.py` | Static `vfx/index.html` over the full catalog |

### `art_lab/tools/` (7 .py files)

| Tool | Role |
|---|---|
| `shader_compile_preview.py` | Single shader: template + request.json → `.gdshader` + `.tscn` + preview render |
| `shader_evolve.py` | Evolutionary search: generate population, mutate around elites, score against reference set |
| `shader_godot_render.py` | Wrapper for Godot CLI render (when a 4.5 binary is available) |
| `shader_reference_score.py` | Score a batch against curated images in `art_lab/shaders/reference_sets/<name>/` |
| `shader_promote.py` | Diversity-filtered shortlist of high-scoring candidates into a review queue |
| `shader_batch_review.py` | Build LLM review packet (compact top-candidate JSON) + readable handoff |
| `shader_lab_index.py` | Static `art_lab/shaders/index.html` linking batches + queues + templates + references |

## Status snapshot (2026-05-07)

- **`pipelines/vfx/`** — content-first contract per `research/I_vfx_lab_local_audit_and_migration_plan.md` shipped. CPU bakers cover most cases. GPU plan (Taichi/Warp/PhiFlow) deferred to Phase 13 — see `pipelines/vfx/GPU_BACKENDS_PLAN.md`.
- **`art_lab/shaders/`** — 6 templates compiled, 5 evolution batches done (smoke tests). Pending validated Godot-rendered flipbook bake on this machine. Pending: spatial shader templates (force fields, water, energy weapons, terrain overlays); particle process shaders (orbitals, sparks, embers, swarms).

If you only remember one thing: **simulation-driven → `pipelines/vfx/`. Formula-driven → `art_lab/shaders/`.**
