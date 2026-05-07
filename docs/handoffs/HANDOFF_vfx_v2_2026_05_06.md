# Handoff — VFX pipeline v2 (2026-05-06)

Built per `../../research/C2_vfx_3d_volumetric.md` (the SOTA brief that builds on
`../../research/C_vfx.md` and `../../research/I_vfx_lab_local_audit_and_migration_plan.md`).
Takes the v1 pipeline (Pydantic Effect schema, 3 CPU bakers,
SpriteFrames+.tscn export, spell-lab importer, 14-effect gallery — see
`HANDOFF_vfx_2026_05_06.md`) to research-C2-aligned SOTA: 3D / volumetric /
mesh-trail export targets, biome-wired volumetric fog, runtime helpers,
57-effect gallery v2, no-copy exporters.

## Built

### Schema (extends without breaking v1)

- `../../pipelines/vfx/schemas.py` — adds `Effect.export_target` (`2d` | `3d_billboard` | `decal` | `fog_volume` | `mesh_trail`), `Effect.element` / `archetype` / `tags` taxonomy fields, and `EffectVisual3D` (billboard_mode / cast_shadow / depth_test / world_size_m). New `Backend` literals: `volumetric_fog`, `runtime_trail`, `decal_flipbook`, `vat`, plus deferred GPU bakers (`taichi_*`, `warp`, `phiflow`, `liquidfun`). All 14 v1 effects re-validate cleanly.

### Three new export targets (one bake → many Godot scene shapes)

- `../../pipelines/vfx/export_godot_3d.py` — emits `.tscn` + `.tres` + `.gdshader` for the four 3D variants. **No file copies**: every output references baked artifacts at their existing catalog paths via `res://vfx/<kind>/<id>/...`. Outputs land in `../../vfx/catalog/<kind>/<id>/godot/` next to the authored content.
  - `3d_billboard` → `MeshInstance3D` + `QuadMesh` + `ShaderMaterial`. Billboard math is in `billboard.gdshader` because Godot 4.5's `PARTICLES_ANIM_*` material flags only auto-advance inside `GPUParticles3D` (per C2 §6 risk note); `MeshInstance3D` needs explicit `TIME * fps` UV math. Three modes: `enabled` (full face-camera), `y_axis` (upright, rotate around world Y — best for 2.5D iso projectiles), `off` (use the model's own transform).
  - `decal` → `Decal` node + `decal_flipbook.gdshader`. Decal node alone gives a static-frame projection; the companion `<id>_decal.gd` script attaches an animated overlay quad for UV-anim playback (Godot 4.5 Decals don't accept arbitrary `ShaderMaterial` in their texture slots).
  - `mesh_trail` → `MeshInstance3D` + `RibbonTrailMesh` or `TubeTrailMesh` + the `MeshTrail3D.gd` script. Selects ribbon vs. tube via `backend_params.trail_type`.
  - `fog_volume` → `FogVolume` + `FogMaterial` (the `.tres` and `density.png` and `fog.gdshader` come from `baker_volumetric_fog.py`).

### Volumetric fog baker + biome preset wiring

- `../../pipelines/vfx/baker_volumetric_fog.py` — bakes a 3D density volume (default 64×64×32) via numpy Worley or value noise + vertical falloff curve, packs the depth slices side-by-side into a wide `density.png`, and emits `fog.gdshader` (with `shader_type fog;` doing slice interpolation along UVW.z) plus `fog_material.tres` referencing both. CPU-only, deterministic, no GPU. The `--emit-biome-presets` mode writes 7 biome stub `effect.json` files (`lava_field_haze`, `ice_cavern_haze`, `mana_crystal_haze`, `grassland_haze`, `ruins_haze`, `swamp_haze`, `ash_waste_haze`) under `../../vfx/catalog/ambient/`. Per-biome palette + density tuning matches `../../art_lab/biomes/biome_scatter_rules.json`.

### Runtime helpers (Godot 4.5 GDScript, drop into `res://vfx/runtime/`)

- `../../vfx/runtime/MeshTrail3D.gd` — `class_name MeshTrail3D extends MeshInstance3D`. Wraps `RibbonTrailMesh` / `TubeTrailMesh`. Self-driven by default (samples its own `global_position`); call `set_emitter(Node3D)` for emitter-driven mode. Velocity smoothing (EMA) prevents direction-reversal popping. `auto_free` for one-shot projectiles. Static `spawn_burst(...)` convenience for sparks/streaks.
- `../../vfx/runtime/AudioCueBus.gd` — autoload that listens to `AnimatedSprite2D`/`3D` `frame_changed`, fires `cue_hit(name, effect_id)` when a frame index crosses a threshold derived from `manifest.extras.audio_cues[i].t * fps`. Cues are hoisted from `effect.backend_params._audio_cues` into the manifest by `bake.py` post-bake. Per C2 §4 / risk note: bake-time FFT was rejected because it doesn't survive variable playback (time scaling, hit-stop, replay).
- `../../vfx/runtime/README.md` — install + usage examples.

### Content authoring (highest-visible-payoff item)

- `../../pipelines/vfx/author_grid.py` — generator for the 24-cell element × archetype grid (fire/ice/lightning/earth/arcane/shadow × projectile/burst/aura/impact). Each cell ships per-element 4-stop palette (bright → medium → dark → ash), tuned size/speed multipliers, `_audio_cues` for AudioCueBus, and an `export_target` (projectiles/bursts → `3d_billboard`, auras/impacts → `decal`).
- `../../pipelines/vfx/author_damage.py` — 12-effect damage/impact catalogue: 3 blood (small/large spray + drip), 3 sparks (metal/stone/arcane), 3 dust (small puff/large puff/drift), 3 debris (wood/stone/chitin via `fracture2d`).

### Gallery v2 polish

- `../../pipelines/vfx/gallery.py` — rewritten. Element + archetype + backend + export-target filter buttons, live tag/id search, color-coded element pills, autoplay flipbook previews via CSS `@keyframes` `steps()` over the baked sprite atlas, fog-volume tiles render as palette gradients. JS-driven filtering + counter; sticky controls bar.

### Plumbing

- `../../pipelines/vfx/bake.py` — adds routing for `volumetric_fog`, `decal_flipbook` (which wraps an underlying phenomenon baker — default `particle_cpu` — and re-tags the manifest), `runtime_trail` and `external` and `vat` (no-bake stubs that emit a manifest so the gallery and link_validator can find them), `taichi_*` / `warp` / `phiflow` / `liquidfun` (recognized but deferred per `GPU_BACKENDS_PLAN.md`). Adds `_hoist_audio_cues()` post-bake step so the `_audio_cues` declared in `backend_params` lands in `manifest.extras.audio_cues` for `AudioCueBus.gd` to read at runtime.

## Tested

```
[bake] 46 catalog effects baked clean (24 element×archetype + 12 damage/impact + 7 biome haze + 3 v1)
[bake] 11 spell-lab migrated effects re-validate against extended schema
[export_godot] 39 2D scenes exported (7 skipped: no-frame backends like volumetric_fog)
[export_3d]    43 3D scenes exported (3 v1 effects stay 2D since their export_target=2d default)
[gallery]      57 effects, 55 with previews
[link_validator] MISSING references: none ✓
[disk]         catalog dir: ~134 KB per effect; godot/ subdirs: 5-12 KB of pure text per effect
[disk]         bulk export wrote ZERO new bytes outside the catalog dirs (no copies)
```

Sample 3D-billboard `.tscn` (referenced from `../../vfx/catalog/projectiles/fire_projectile/godot/`):

```
[gd_scene load_steps=4 format=3]

[ext_resource type="ShaderMaterial" path="res://vfx/projectiles/fire_projectile/godot/billboard_material.tres" id="1_mat"]

[sub_resource type="QuadMesh" id="QuadMesh_1"]
size = Vector2(1.5, 1.5)

[node name="fire_projectile_billboard" type="MeshInstance3D"]
mesh = SubResource("QuadMesh_1")
cast_shadow = 0
material_override = ExtResource("1_mat")
```

Sample biome `FogVolume.tscn`:

```
[gd_scene load_steps=2 format=3]
[ext_resource type="FogMaterial" path="res://vfx/ambient/lava_field_haze/fog_material.tres" id="1_fog"]
[node name="lava_field_haze_fog" type="FogVolume"]
size = Vector3(24.0, 6.0, 24.0)
shape = 1
material = ExtResource("1_fog")
```

## Bug found and fixed (character-pipeline-quality post-mortem)

**Bug:** v1's `export_godot.py` did `shutil.copytree(frames_dir, dst)` per
exported effect, copying every per-frame PNG into a parallel
`../../vfx/godot/<kind>/<id>/frames/` tree. The first cut of v2's
`export_godot_3d.py` repeated the pattern (per export target, so 4×
amplification). With 46 baked effects × ~20 frames × ~4 export targets,
the tree blew up to **586,545 files** under `../../vfx/godot/` and overflowed
D: drive (954G fully consumed).

There was also pre-existing weirdness: at least one effect's
`../../vfx/godot/ambient/mana_crystal_haze/frames/` had picked up a 6.1 GB mirror
of an unrelated `../../animators/AnimateAnyMesh/.git` tree at some prior point,
contributing to the bloat. (Fix: that whole subtree was moved out and is
now in `D:/tmp/vfx_godot_to_delete_2026_05_06/`.)

**Fix:** rewrote both exporters (`export_godot.py` + `export_godot_3d.py`)
to emit into `../../vfx/catalog/<kind>/<id>/godot/` (one subdir per effect, clean
source-vs-derived separation) with `.tscn`/`.tres`/`.gdshader` referencing
frames at their existing catalog paths via `res://vfx/<kind>/<id>/...`.
Zero copies. Bulk re-export wrote zero new bytes outside the small text
output. Verified with disk-space-before/after on full catalog.

**Recovery action:** `D:\assets\vfx\godot\` was moved to
`D:\tmp\vfx_godot_to_delete_2026_05_06\` (instant same-drive metadata
move, ~580k files), then deleted by the user once cross-checks confirmed
nothing original lived in it. Cross-checks performed before delete:
(1) all-derivable file-type filter — only `.tscn .tres .gd .uid .import
.png .json .txt .md .gdshader` extensions found, zero unknowns;
(2) active-project ref scan — `Select-String` against
`C:\Users\josep\test\new-game-project\**\*.tscn,*.tres` for absolute
`vfx\godot|vfx/godot` paths returned empty; (3) catalog cross-check —
all 50 staged dirs mapped to current `../../vfx/catalog/` effect IDs after
stripping the `_<export_target>` suffix, zero orphans.

**User-facing verification command:**

```powershell
# Should report negligible godot/ output size and no FAILED lines.
python D:\assets\pipelines\vfx\export_godot.py --all
python D:\assets\pipelines\vfx\export_godot_3d.py --all
$d = Get-PSDrive D
Write-Output "free: $([math]::Round($d.Free / 1GB, 1)) GB"
# Confirm: free space stays unchanged (within rounding) before vs after.
```

## How to consume in Godot 4.5

1. Copy the *contents* of `D:\assets\vfx\catalog\` and `D:\assets\vfx\runtime\` into your project's `res://vfx/`. (Skip `../../vfx/migrated_from_spell_lab/` unless you want the legacy artifacts; skip `../../vfx/index.html` and the `../../vfx/godot/` staging dir — the latter is the deleted-but-staged old output, gone after rm.)
2. Project Settings → Autoload → add `res://vfx/runtime/AudioCueBus.gd` as singleton `AudioCueBus`.
3. Instance any effect:
   ```gdscript
   var fb := preload("res://vfx/projectiles/fire_projectile/godot/fire_projectile_billboard.tscn").instantiate()
   add_child(fb)
   fb.global_position = projectile.global_position
   ```
4. Wire audio cues:
   ```gdscript
   var sprite = preload("res://vfx/spell/fire_burst/godot/fire_burst.tscn").instantiate()
   add_child(sprite)
   AudioCueBus.register(sprite, "fire_burst",
       "res://vfx/spell/fire_burst/manifest.json")
   AudioCueBus.cue_hit.connect(_on_cue_hit)
   ```
5. Place biome fog volumes:
   ```gdscript
   var fog = preload("res://vfx/ambient/lava_field_haze/godot/lava_field_haze_fog.tscn").instantiate()
   fog.global_position = biome_zone_center
   add_child(fog)
   # Make sure WorldEnvironment.environment.volumetric_fog_enabled = true.
   ```

## Stubbed (deferred per scope)

- **Taichi** GPU baker (`baker_taichi_particle.py`, `baker_taichi_smoke.py`) — schema slot reserved, install plan in `GPU_BACKENDS_PLAN.md`. ~50-200× speedup over CPU.
- **NVIDIA Warp** baker — vortex / black-hole / attractor effects.
- **PhiFlow** baker — flowmap-quality smoke fields.
- **LiquidFun** adapter — D:\spell lab\ already has a working build; not yet wrapped to Effect schema.
- **VAT** (Vertex Animation Textures) — deferred per C2 §5; no Godot 4.5 first-class support, custom-shader path not justified at current scope. Re-trigger when 100+ animated NPCs or stadium-scale destruction enters scope.
- **Procedural shader generation** feeding `Effect.visual` — research H covered shader gen; could auto-author Effect.visual params for new spells. Out of scope for v2.
- **EmberGen `.vdb` ingestion** — `pyopenvdb` on Windows is fragile; convert in WSL2 if ever needed.

## Cloud-key contract

None. VFX is fully local.

## Files added / changed

```
pipelines/vfx/
  schemas.py                  +export_target +EffectVisual3D +element/archetype/tags +new Backend literals
  bake.py                     +routing for volumetric_fog/decal_flipbook/runtime_trail/external/vat
                              +deferred GPU backends + _hoist_audio_cues()
  export_godot.py             rewrite: emit into <effect>/godot/, no frame copies
  export_godot_3d.py          NEW: 4 export targets (3d_billboard/decal/mesh_trail/fog_volume)
  baker_volumetric_fog.py     NEW: numpy noise → Texture3D-via-slice-atlas + biome presets
  author_grid.py              NEW: 24-cell element x archetype generator
  author_damage.py            NEW: 12-effect damage/impact catalogue (blood/sparks/dust/debris)
  gallery.py                  rewrite: filters + search + autoplay sprite-atlas previews

vfx/runtime/                  NEW directory
  MeshTrail3D.gd              runtime helper for mesh-trail VFX (RibbonTrail/TubeTrail wrappers)
  AudioCueBus.gd              autoload for runtime VFX-audio sync (frame_changed -> cue_hit signal)
  README.md                   install + usage docs

vfx/catalog/
  spells/                     +24 element-archetype effects
                              +9 damage/impact effects (blood, sparks, dust)
  projectiles/                +6 element-projectiles
  destruction/                +3 debris (wood/stone/chitin)
  environment/                +1 dust_drift ambient
  ambient/                    +7 biome volumetric fog presets
                              (each with effect.json, manifest.json, density.png,
                               fog.gdshader, fog_material.tres, godot/<id>_fog.tscn)
  README_GODOT_DROPIN.txt     NEW: copy-into-project instructions
  <kind>/<id>/godot/          NEW per-effect subdir for derived .tscn/.tres/.gdshader

HANDOFF_vfx_v2_2026_05_06.md  this file
```

## Effort

~6 hours of build + content authoring (matches the C2 punch-list estimate
of 12-18h once you exclude content authoring, which dominates the wall
clock — but `author_grid.py` and `author_damage.py` are deterministic
generators, not 36 hand-typed JSON files).

## Outstanding nits (low priority)

- `gallery.py` autoplay only animates row 0 of multi-row sprite atlases (CSS `steps()` is 1D). Effects with all frames in one row (n_frames ≤ ~8 at typical bounds_px) play perfectly; larger atlases play just the first row. Real fix would be a `<canvas>` per tile or a JS-stepped `<img>` with `object-position`. Cosmetic only.
- `link_validator.py` reports 55 unused VFX assets (informational). Wiring them into game_data abilities is a Phase 2 (game_data v2) concern, not VFX.
- The `D:/tmp/vfx_godot_to_delete_2026_05_06/` staging dir was deleted by the user after the cross-checks above passed. Recovered ~370 GB of disk total (from 24 GB free at the worst point back up to 394 GB free).
- **Outstanding bug to investigate next session:** at least two fog-volume effects (`mana_crystal_haze` and `lava_field_haze`) had `frames/animators/<tool>/{...}` subtrees mirroring chunks of `D:\assets\animators\` (in `lava_field_haze`'s case, a complete `mesa-env/venv/Lib/site-packages/torch/` install — multiple GB). Both were inside the deleted staging tree; current `../../vfx/catalog/ambient/<biome>_haze/` dirs are confirmed clean (no `frames/` subdir). Source of the corruption: unknown. Theories: (a) some earlier v2 first-cut export run hit a path-resolution bug where `frames_dir` from a non-frame backend resolved to a parent dir containing animators; (b) a `shutil.copytree` of an empty `frames_dir` defaulted somewhere, the way `shutil.copytree(src=., dst=...)` would when `src` was unset. Neither current `bake.py` nor either current exporter can repro this; verified by re-baking + re-exporting all 7 fog volumes — no `frames/` dirs created. **Action: if the issue recurs, snapshot the offending dir BEFORE deleting and trace via git history of pipelines/vfx/.**
