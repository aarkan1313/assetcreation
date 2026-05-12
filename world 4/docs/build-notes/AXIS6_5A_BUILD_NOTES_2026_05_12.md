# Axis 6 Stage 5a Build Notes — 2026-05-12

> Foundation half of Axis 6 (soft biome transitions). The catalog → texture-
> array → splat → shader → ScaleWorld plumbing is in place end-to-end on
> branch `axis6-transitions`. This stage ships in hard-mode splats (every
> pixel of a tile = that tile's own biome at weight 1.0, no blending) —
> deliberately regression-equivalent to the 2026-05-12 per-tile-material
> baseline. Soft blending lands in Stage 5b.
>
> Spec: `plans/AXIS6_TRANSITIONS_DESIGN_2026_05_12.md`.
> Plan:  `plans/AXIS6_TRANSITIONS_PLAN_2026_05_12.md`.

## What got built

```
biome_catalog.json               (5 biomes, 2 tiers, hand-authored)
       │
       ▼
build_biome_arrays.py            (with auto-upsample + L→RGB convert)
       │
       ▼
layer_manifest.json              (12 standard + 3 hero = 15 layers total)
       │
       ▼
build_tile_splats.py --mode hard (16 tiles × splat.png + splat_meta.json)
       │
       ▼
write_global_terrain_material.py (1 .tres binding shader + lighting)
       │
       ▼
ScaleWorld._build_v2_arrays_if_needed (8 Texture2DArrays built at runtime)
       │
       ▼
ScaleWorld._make_v2_tile_material      (per-tile material duplicate w/ uniforms)
       │
       ▼
TileTerrain ← shared_material (Material)
       │
       ▼
terrain_world_v2.gdshader        (per-fragment splat → 4 (g/m/r) reads → blend)
```

## Pipeline output (concrete, scale_demo)

- `worlds/scale_demo/biome_catalog.json` (5 biomes × 3 slots, mixed tiers)
- `worlds/scale_demo/arrays/layer_manifest.json` (15 layers across 2 tiers)
- `materials/biome_*/<slot>/ao__upsampled1024_rgb.png` × 12 (auto-generated siblings; 512×512 L→1024×1024 RGB)
- `materials/biome_*/<slot>/roughness__rgb.png` × 13 (auto-generated; L→RGB at native res)
- `materials/anchor_v2/{scrub_dense,rocky_slope}/{ao,roughness}__upsampled4096_rgb.png` (16→4096 + L→RGB)
- `materials/biome_rocky/rock/{ao,roughness}__upsampled4096_rgb.png` (same; biome_rocky.rock inherits from anchor_v2.rocky_slope)
- `worlds/scale_demo/tiles/tile_X_Z/{splat.png,splat_meta.json}` × 16
- `worlds/scale_demo/material_world_v2.tres` (1 global material)
- `shaders/terrain_world_v2.gdshader` (new canonical scale-axis shader)

## Decisions made during build

- **Option C: per-slot tier+layer addressing.** Mid-execution it became
  clear the catalog allows a biome's 3 slots to live in *different*
  tiers (forest's ground+rock are hero 4096², its mid is standard 1024²;
  rocky's ground+mid are standard, its rock is hero from the inherited
  `rocky_slope`). The shader can't address them via a single
  `(tier, layer + {0,1,2})` formula. Three uniforms instead — one
  `ivec4` per slot, each channel of each `ivec4` packs `(tier_bit << 30)
  | (layer & 0x3FFFFFFF)`. Adds ~15 lines of shader + GDScript;
  preserves quality across mixed-resolution biomes. Spec updated
  inline as part of this session.

- **Texture2DArray runtime construction, not `.tres` files.** Godot 4.5
  doesn't serialize `Texture2DArray` with external Image references
  cleanly — `_images = Array[Image]([null, null, ...])` even with
  `FLAG_BUNDLE_RESOURCES`. ([godot-proposals#10601](https://github.com/godotengine/godot-proposals/issues/10601)
  tracks the gap.) Probed it directly with a one-off Godot script
  before committing to the architecture. Two paths exist: editor
  sprite-sheet import preset (rigid; one big PNG per array sliced into
  layers), or runtime construction from `Image` / `Texture2D` refs.
  We chose runtime. ScaleWorld reads `arrays/layer_manifest.json` at
  scene init, loads each layer's PNG, builds 8 arrays in-memory, sets
  them as `shader_parameter`s on the global material. Cost: one-shot
  ~hundreds of ms at scene init; acceptable.

- **Auto-upsample + L→RGB convert in the array builder.** Existing
  PBR maps are a mess:
  - StableMaterials outputs AO at half-res (512² when albedo is 1024²)
  - W3 real-ortho `_soft_composite` outputs AO at 16×16 (placeholder)
  - All AO and roughness maps are L-mode (single channel grayscale)
  - Albedo/normal maps are RGB or RGBA

  Forcing artists to regenerate every PBR set at the tier resolution
  was the wrong fix. Instead `_ensure_resolution` writes `__upsampled<N>_rgb.png`
  sibling files alongside any source that needs LANCZOS-upsample
  and/or `convert("RGB")`. Originals stay untouched. The manifest
  references the upsampled siblings. Idempotent — re-running checks
  for the sibling and reuses if size+mode match.

- **Format + mipmap normalization in ScaleWorld too.** Even after the
  pipeline normalizes source files, Godot's `.ctex` import can
  re-introduce per-file variation (e.g. `tundra_lichen/ao.png` loads
  with mipmaps=true while sibling `__upsampled` files load with
  mipmaps=false — because Godot bakes mipmaps based on the .import
  preset, which varies by file). `create_from_images` returns
  err=31 if `has_mipmaps()` or `get_format()` varies across layers.
  Belt-and-suspenders fix: ScaleWorld calls `convert(FORMAT_RGBA8)` +
  `clear_mipmaps()` on every image before passing to
  `create_from_images`. The array regenerates mipmaps internally.

- **`shared_material: Material` export on TileTerrain.** Originally
  TileTerrain only accepted `shared_material_path: String` (loaded
  at apply time). For the v2 path, ScaleWorld pre-builds a per-tile
  material instance and hands it directly — avoids re-loading the
  same .tres per tile and lets us set per-tile shader_parameters
  before the mesh is finalised. The path-based fallback still works
  for the pre-Axis-6 paths (biome_materials, material_override_path).

## What got tested

```
tests/test_biome_catalog.py        — 5 tests, all passing
tests/test_build_biome_arrays.py   — 5 tests, all passing
tests/test_build_tile_splats.py    — 5 tests, all passing
```

15 pytest cases total. Run via `cd "world 4" && python -m pytest tests/ -v`.

Visual verification: `captures/axis6_5a_walk_2026_05_12.png` matches the
2026-05-12 pre-5a baseline `captures/biomes_wired_walk_2026_05_12.png`
qualitatively — same biomes, same hard tile borders, same lighting.
**The whole point of Stage 5a is to ship the rebuilt plumbing without
changing the visible result.** Stage 5b is when the new plumbing
starts paying off.

## Pitfalls hit (now documented as PITFALLS #5 + #5b)

1. **Texture2DArray .tres doesn't serialize external Image refs cleanly.**
   Tracked at godot-proposals#10601. Workaround: runtime construction.
2. **Mixed image formats across array layers** (L8 vs RGB8 vs RGBA8) →
   err=31. Fix: force `FORMAT_RGBA8` on every image.
3. **Mixed mipmap state across array layers** → err=31. Fix:
   `clear_mipmaps()` on every image. Symptom is identical to #2;
   diagnostic is to print `has_mipmaps()` per layer.

All three landed in PITFALLS.md so a future session hitting err=31
from `create_from_images` goes straight to the symptom matrix and the
fix.

## Why not just pre-bake one big sprite-sheet PNG per (tier, map) and import as Texture2DArray via editor preset

Considered. Rejected for two reasons:

- **Rigidity.** A sprite-sheet PNG with 15 vertically-stacked
  1024×1024 layers is 1024×15360. Adding/removing/reordering biomes
  means rebuilding the sheet. Runtime construction has no such
  constraint — just edit the catalog and re-run the manifest builder.
- **Per-game packaging story.** The "drop into another Godot project"
  goal works best with portable per-PBR-map PNGs and a Python
  pipeline that converts them on demand. Sprite sheets are a baked
  product, harder to swap or re-author per-game.

The runtime construction cost (~hundreds of ms at scene init) is
absorbable. If it ever becomes a bottleneck (large biome counts +
slow disk), the sprite-sheet path stays an open lever to pull.

## Files touched

### Created
- `pipeline/biome_catalog.py` + `tests/test_biome_catalog.py`
- `pipeline/build_biome_arrays.py` + `tests/test_build_biome_arrays.py`
- `pipeline/build_tile_splats.py` + `tests/test_build_tile_splats.py`
- `pipeline/write_global_terrain_material.py`
- `tests/conftest.py`, `pytest.ini`
- `the world 4/shaders/terrain_world_v2.gdshader`
- `the world 4/worlds/scale_demo/biome_catalog.json`
- `the world 4/worlds/scale_demo/arrays/layer_manifest.json`
- `the world 4/worlds/scale_demo/material_world_v2.tres`
- `the world 4/worlds/scale_demo/tiles/tile_X_Z/{splat.png,splat_meta.json}` × 16
- `the world 4/materials/*/__upsampled*.png` and `__rgb.png` siblings (auto-generated)
- `the world 4/captures/axis6_5a_walk_2026_05_12.png`

### Modified
- `the world 4/scripts/ScaleWorld.gd` — `world_v2_material_path` export,
  `_build_v2_arrays_if_needed`, `_v2_pack`, `_make_v2_tile_material`,
  `_v2_manifest` cache, manifest-driven texture array construction
- `the world 4/scripts/TileTerrain.gd` — `shared_material: Material`
  export with priority over `shared_material_path`
- `the world 4/scenes/scale_demo.tscn` — `world_v2_material_path` set
- `docs/plans/AXIS6_TRANSITIONS_DESIGN_2026_05_12.md` — per-slot tier+layer uniforms (Option C)
- `docs/plans/AXIS6_TRANSITIONS_PLAN_2026_05_12.md` — Stage 5a.5 dropped (runtime construction)
- `docs/reference/PITFALLS.md` — added #5 + #5b
- `docs/reference/TOOLS.md` — Axis 6 pipeline subsection + new shader/script entries
- `docs/strategy/AXES.md` — Axis 6 current-state notes
- `docs/ROADMAP.md` — Stage 5a shipped row + reranked #1 to Stages 5b-5f

## What this stage did NOT do

- **No soft transitions.** Stage 5b is where `--mode feather` lands.
  Today's splats are pure-channel-0 hard splats.
- **No slot-pool indirection.** Stage 5c. v1 uses raw layer indices
  directly; the pool refactor is a streaming-ready preparation.
- **No streaming.** Slot pool is static; all biomes resident in VRAM.
  Listed in the portability doc as a known limitation.
- **No iso/topdown per-biome shading.** Iso/topdown still use single-
  material view shaders (`material_view_iso.tres`,
  `material_view_topdown.tres`), losing biome distinction in those
  views. Axis 4 ↔ Axis 2 cross-cut follow-up.

## What unlocks now

- **Stage 5b** is mechanical now — extend the splat builder, no
  shader change. The array+splat path consumes feathered splats
  unmodified.
- **Per-game biome packs** are functional today — swap the catalog
  + regenerate the manifest + restart. No shader or GDScript edit.
- **Adding a biome** is similarly catalog-only. Tested implicitly:
  forest's mixed-tier slot layout exercises Option C's per-slot
  addressing on every fragment.

## Cost recap

| Item | Plan estimate | Actual |
|---|---|---|
| 5a.1 — catalog JSON | trivial | 5 min |
| 5a.2 — catalog loader + tests | ~30 min | 30 min |
| 5a.3 — sanity check | 5 min | 5 min |
| 5a.4 — manifest builder + tests + auto-upsample | ~45 min | ~75 min (auto-upsample/RGB convert pass was extra) |
| 5a.5 — Texture2DArray.tres emitter | ~30 min | **dropped** — moved to runtime |
| 5a.6 — splat builder hard-mode + tests | ~30 min | 30 min |
| 5a.7 — shader | ~45 min | 30 min (no real shader bugs; Godot 4.5 sampler2DArray syntax worked first try) |
| 5a.8 — global material emitter | ~15 min | 10 min |
| 5a.9 — ScaleWorld wiring + 3 Godot pitfalls | ~45 min | ~90 min (the 3 pitfalls cost the budget) |
| Doc updates | ~30 min | ~45 min |
| **Total** | **~4-5 hr** | **~5 hr** |

Within the spec's "3-4 sessions for the full Axis 6" estimate — this
is the front half. Stages 5b-5f are mechanical now that the plumbing
is proven.
