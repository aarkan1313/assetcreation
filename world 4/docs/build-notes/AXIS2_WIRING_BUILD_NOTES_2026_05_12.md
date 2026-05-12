# Axis 2 Wiring Build Notes — 2026-05-12

> Per-tile biome material assignment in ScaleWorld (hard borders, v1).
> The texture kits shipped earlier today
> (`BIOME_KITS_BUILD_NOTES_2026_05_12.md`) are now actually rendered
> on the scale_demo world.

## What got built

```
16 tiles × meta.json + "biome" field
  ↓ pipeline/assign_biomes_scale_demo.py (one-shot hard-coded 4x4 layout)
each tile knows what biome it belongs to
  ↓ ScaleWorld._resolve_tile_material_path() reads tile meta.json
  ↓ matches biome label against the biome_materials Dictionary export
  ↓ tile gets the matching material_<biome>.tres at spawn
4 biomes visible across the 16-tile world, hard seams at every boundary
```

## Decisions made during build

- **Biome label lives in tile meta.json**, not derived from heightmap.
  Lets us hand-author the 4×4 sketch from `BIOMES.md` and look at
  specific adjacencies (forest↔alpine, desert↔wetland, etc.)
  deliberately. Procedural assignment from height/slope/aspect is a
  follow-up — useful once we know what we want.

- **Hard borders, not soft transitions.** The visible seams are the
  v1 deliverable — they're the concrete failure mode that Axis 6
  (transition workflow) needs to solve. W3 spent sessions designing
  transitions in the abstract; this avoids that trap.

- **biome_materials as a `@export var Dictionary`** in scale_demo.tscn.
  Resolves at spawn time. Empty dict = legacy single-material behavior
  (zero-cost fallback for builds that don't use biomes).

- **View modes interact deliberately.** Walk-mode hotkey leaves
  per-biome materials in place (the `mode_name == "walk" and not
  biome_materials.is_empty()` branch). Iso/topdown still clobber to
  their respective view shaders — per-view × per-biome shading is a
  follow-up that crosses Axis 4 ↔ Axis 2. For the v1 demo, iso/topdown
  capturing per-biome materials happens by temporarily clearing
  `view_material_iso` / `view_material_topdown` in the scene.

- **Layout sketch follows BIOMES.md exactly:**
  ```
  Z=3: alpine  alpine  rocky    rocky
  Z=2: alpine  forest  forest   rocky
  Z=1: forest  forest  desert   desert
  Z=0: wetland wetland desert   desert
  ```

## Files touched

New:
- `pipeline/assign_biomes_scale_demo.py` (~40 lines, idempotent biome
  label writer)

Edited:
- 16× `worlds/scale_demo/tiles/tile_X_Z/meta.json` — added `"biome"`
  field per tile
- `scripts/ScaleWorld.gd` — added `biome_materials: Dictionary` export,
  `_resolve_tile_material_path()` helper, updated `_spawn_tile()` to
  use it, updated `set_view_mode()` to skip the bulk material clobber
  when walk-mode-with-biomes
- `scenes/scale_demo.tscn` — wired `biome_materials`, cleared
  `material_override_path` and `view_material_walk`

Captures:
- `captures/biomes_wired_walk_2026_05_12.png` — walk view at default
  spawn, showing a desert↔rocky hard border in eye-level perspective
- `captures/biomes_wired_topdown_2026_05_12.png` — topdown view of all
  4 biomes laid out across the 16-tile world (note: the L-shape crop
  is the known Axis 4 headless-topdown framing bug, not a biome bug)

## Pitfalls hit / avoided

- **Pitfall #1 (texture-driven speckle)**: no new occurrences. All 4
  biome materials inherit `albedo_luma_floor=0.08` and `ao_floor=0.72`
  from `terrain_scale_v1.gdshader` via the .tres bindings.

- **Pitfall #3 (PBR black quads)**: not hit. All biome materials use
  the unshaded `terrain_scale_v1.gdshader`.

- **JSON parsing in GDScript**: used `FileAccess.open` + `JSON.parse_string`
  rather than `JSON.parse` (deprecated in 4.x). Empty-file / null-parse
  paths fall through to legacy single-material behavior with a
  `push_warning`.

## What this session did NOT do

- **No soft transitions.** Hard borders only. Axis 6 proper.
- **No per-view per-biome shading.** Iso/topdown still single-material.
- **No procedural biome assignment.** Layout is hand-authored.
- **No per-tile shader-parameter variation.** All tiles in a biome
  share identical shader params from that biome's .tres.

## What unlocks now

- **Axis 6 (transition workflow)** is the next ranked item. We now
  have visible hard seams to look at — the concrete problem the
  blending workflow needs to solve.
- **Procedural biome assignment** is a sensible follow-up (read tile
  mean elevation / slope / aspect, route biome by rule). Currently
  parked.
- **Per-view × per-biome shading** is a sensible follow-up that wires
  Axis 4 ↔ Axis 2 properly. Currently parked.

## Cost recap

| Item | Estimate | Actual |
|---|---|---|
| Tile meta.json biome assignment | ~10 min | 5 min |
| ScaleWorld wiring + view-mode interaction | ~20 min | 15 min |
| scale_demo.tscn updates | ~5 min | 2 min |
| Multi-biome captures | ~10 min | 8 min |
| Build-note + roadmap updates | ~15 min | 10 min |
| **Total** | **~1 hour** | **~40 min** |
