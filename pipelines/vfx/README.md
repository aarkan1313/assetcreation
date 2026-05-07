# VFX Pipeline

**Status:** ✅ Working end-to-end (CPU-only, 3 backends, 3 demo spells, 11 spell-lab artifacts migrated). GPU backends planned in [GPU_BACKENDS_PLAN.md](GPU_BACKENDS_PLAN.md).

Per `research/I_vfx_lab_local_audit_and_migration_plan.md`'s **content-first**
contract:

```
effect.json  (canonical authoring artifact)
   ↓
bake.py routes to backend baker:
   • particle_cpu    numpy SoA particles + emitter + gravity + drag
   • fracture2d      Voronoi shards + analytical motion
   • smoke_field     semi-Lagrangian advection 2D smoke field
   • external        already-baked artifacts (e.g. migrated from spell lab)
   ↓
manifest.json + frames/ + flipbook.png + extras (particles.json | field.json | fragments.json)
   ↓
export_godot.py
   ↓
res://vfx/<kind>/<id>/sprite_frames.tres   +   <id>.tscn   +   frames/   +   flipbook.png
```

## Files

| File | Role |
|---|---|
| [schemas.py](schemas.py) | Pydantic v2 `Effect` + `BakeManifest`. Single source of truth for effect.json. |
| [baker_particle_cpu.py](baker_particle_cpu.py) | numpy particle baker: emitter, gravity, drag, palette-coded color over life, alpha + additive blend, Gaussian splats. |
| [baker_fracture2d.py](baker_fracture2d.py) | First-party 2D fracture: source polygon → Voronoi seeds → Sutherland-Hodgman half-plane clip → shards → radial burst velocity + spin. Outputs `fragments.json` + `bodies.json` (transform timeline). |
| [baker_smoke_field.py](baker_smoke_field.py) | numpy semi-Lagrangian fluid solver: density + velocity grid, buoyancy-driven plume, viscosity, dissipation. Adequate at 64×64 grid. |
| [bake.py](bake.py) | Orchestrator. `--all` walks `vfx/catalog/` and bakes everything. |
| [export_godot.py](export_godot.py) | Emits `SpriteFrames.tres` (1 anim @ effect's fps, frame textures via ext_resource) + `<id>.tscn` (AnimatedSprite2D, autoplay). Copies frames/ + flipbook.png into the Godot drop-in. |
| [import_spell_lab.py](import_spell_lab.py) | Migrates 11 named artifacts from `D:\spell lab\spell-sandbox\artifacts\` into the new catalog shape with `backend: external`. |
| [gallery.py](gallery.py) | Static HTML gallery for the catalog + migrated artifacts. |
| [GPU_BACKENDS_PLAN.md](GPU_BACKENDS_PLAN.md) | Adoption plan for Taichi / Warp / PhiFlow when GPU is free. |

## Quickstart

```powershell
# Bake the 3 demo spells:
python pipelines\vfx\bake.py --all

# Export to Godot:
python pipelines\vfx\export_godot.py --all

# Migrate the legacy spell-lab artifacts:
python pipelines\vfx\import_spell_lab.py

# Build the gallery:
python pipelines\vfx\gallery.py
# Open D:\assets\vfx\index.html in a browser.
```

Drop `vfx/godot/` into a Godot 4.5 project at `res://vfx/`:

```gdscript
var sf := load("res://vfx/spell/fireball_projectile/sprite_frames.tres")
$AnimatedSprite2D.sprite_frames = sf
$AnimatedSprite2D.play("fireball_projectile")
```

Or instance the scene directly:

```gdscript
var ps := preload("res://vfx/spell/fireball_projectile/fireball_projectile.tscn")
add_child(ps.instantiate())
```

## Output contract

```
vfx/catalog/<kind>/<id>/
  effect.json            authored
  manifest.json          baker output
  frames/frame_NNNN.png  per-frame
  flipbook.png           grid atlas of frames
  particles.json | fragments.json + bodies.json | field.json   (backend-specific)

vfx/migrated_from_spell_lab/<kind>/<id>/    same shape, `backend: external`

vfx/godot/<kind>/<id>/
  effect.json
  manifest.json
  frames/frame_NNNN.png
  flipbook.png
  sprite_frames.tres
  <id>.tscn
  particles.json | fragments.json | ...

vfx/index.html                                static gallery
```

## Demo set

| effect_id | backend | phenomenon | frames | extras |
|---|---|---|---|---|
| `fireball_projectile` | particle_cpu | fire | 19 | particles.json |
| `shield_break` | fracture2d | shatter | 29 | fragments.json + bodies.json |
| `smoke_pulse` | smoke_field | smoke | 36 | field.json |

Plus 11 migrated legacy artifacts (fireball_projectile_legacy, arcane_shock_ring_legacy, blood_orbit_legacy, gravity_lens_field_legacy, rune_shatter_legacy, smoke_rift_legacy, liquidfun_particle_splash, fracture2d_shard_baker, phiflow_smoke_field, warp_blackhole_particles, taichi_sand_spell). All show up in the gallery.

## What we did NOT add (and why)

- **GPU bakers (Taichi / Warp / PhiFlow)** — the 5090 is in use by other pipelines. Their effect.json schema is identical, so adding `baker_taichi_*.py` and registering in `bake.py:BACKENDS` is the only delta. See [GPU_BACKENDS_PLAN.md](GPU_BACKENDS_PLAN.md).
- **Real Liquid/SPH water** — SPlisHSPlasH is C++/build-heavy. The `smoke_field` baker covers most "rising plume" use cases; particle splashes can be `particle_cpu` with downward gravity.
- **Live runtime fluids in Godot (compute shaders)** — out of scope for v1. The bake-once flipbook approach was the chosen design per C_vfx.
- **Newton / Genesis** — Watch list per C_vfx; not built.
- **JangaFX EmberGen / IlluGen** — GUI/subscription, not LLM-friendly. Reference quality bar only.

## Phenomenon routing (from C_vfx)

| Phenomenon | Pick | Notes |
|---|---|---|
| Projectile (fireball, ice shard) | `particle_cpu` | Burst + drag + palette-fade |
| Burst / explosion / spark | `particle_cpu` | High count + outward spread |
| Shatter (shield, glass, ice) | `fracture2d` | Voronoi shards + bodies.json timeline |
| Rubble / debris | `fracture2d` | Higher gravity, more shards |
| Smoke / fog / steam | `smoke_field` | Bottom emitter + buoyancy |
| Aura / portal / shield idle | (use Art Lab shaders) | These are not bake-and-play; they're live shaders |
| Lightning / beam | (Art Lab shaders) | Same |
| Sand / lava | future Taichi | Falling-sand CA / MPM |
