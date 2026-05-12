# Axis 6 Transitions — Portability Guide

> How to lift the W4 biome-transitions system into another Godot 4.5
> project. The system is engine-agnostic from the host project's
> perspective — it knows about terrain heightmaps, tile layouts, and
> material binding, nothing W4-specific.
>
> Target audience: a developer dropping this into a new game/engine
> that isn't W4. If you're working *inside* W4, see
> `docs/reference/TOOLS.md` and `docs/build-notes/AXIS6_*.md` instead.

## What you're moving

### Required files (lift verbatim)

```
pipeline/
  biome_catalog.py                       — catalog loader/validator
  build_biome_arrays.py                  — layer manifest builder (auto-upsample + L→RGB convert)
  build_tile_splats.py                   — per-tile splat texture + meta builder (hard + feather modes)
  write_global_terrain_material.py       — emits the one global material .tres

the world 4/shaders/
  terrain_world_v2.gdshader              — unified array+splat shader (unshaded manual lighting)

tests/
  conftest.py
  test_biome_catalog.py
  test_build_biome_arrays.py
  test_build_tile_splats.py
pytest.ini
```

Nothing else is required. The pipeline is plain Python 3.12 +
`numpy` + `Pillow`. The shader is plain Godot 4.5 GLSL. No
W4-specific dependencies.

### Required runtime hooks (host project provides)

The host project's tile spawner must, for each tile:

1. Load `<tile_dir>/splat.png` as a `Texture2D`.
2. Read `<tile_dir>/splat_meta.json` (small JSON dict).
3. Duplicate the global terrain material (`.duplicate(false)` — cheap).
4. Set the duplicate's shader uniforms (per-tile):
   - `splat` (sampler2D) — the loaded splat texture
   - `splat_ground_indices` (Vector4i) — packed (tier, layer) per channel for the ground slot
   - `splat_mid_indices` (Vector4i) — same for mid slot
   - `splat_rock_indices` (Vector4i) — same for rock slot
   - `tile_origin_m` (Vector2) — world-XZ origin of this tile in meters
   - `tile_size_m` (float) — tile edge size in meters
5. Assign the duplicate to the tile's `MeshInstance3D.material_override`.

See `the world 4/scripts/ScaleWorld.gd::_make_v2_tile_material` for a
reference implementation. The pack encoding is:

```
packed_int = (tier_bit << 30) | (raw_layer & 0x3FFFFFFF)
  tier_bit:   0 = standard, 1 = hero  (extend to higher bits for more tiers)
  raw_layer:  the actual array layer index (after slot-pool indirection)
A value of -1 means "channel empty, skip in shader."
```

The shader iterates the 4 splat channels and skips any with weight <
1e-3 OR `splat_*_indices[i] < 0`.

### Required scene-init hooks (host project provides)

Before the first tile spawns, the host project must build the texture
arrays from the layer manifest and bind them as shader_parameters on
the global terrain material. ScaleWorld does this in
`_build_v2_arrays_if_needed`:

1. Load `arrays/layer_manifest.json` (output of `build_biome_arrays.py`).
2. For each `(tier, map_name)` in the manifest (typically 2 × 4 = 8):
   - For each layer in the tier (sorted by layer index):
     - Load the PNG as `Texture2D`, `.get_image()`.
     - If compressed, `img.decompress()`.
     - **Force uniform format**: `img.convert(Image.FORMAT_RGBA8)`.
     - **Force uniform mipmap state**: `img.clear_mipmaps()`.
   - `Texture2DArray.new().create_from_images([imgs])`.
   - Set as `shader_parameter/<tier>_<uniform_name>` on the global material.

The `convert(FORMAT_RGBA8)` + `clear_mipmaps()` calls are mandatory —
without them `create_from_images` will err=31 (`ERR_INVALID_DATA`)
because Godot's import pipeline can serve different layer formats /
mipmap states even when the source PNGs look identical. See
`docs/reference/PITFALLS.md` #5 in the W4 docs for the full incident.

### Required pipeline order (per world)

```bash
# Author the catalog (hand-edited JSON; one per world):
#   biome_catalog.json
# Per-tile biome assignment is host-project-specific; it must
# produce a "biome": "<name>" field in each tile's meta.json.

# 1. Build the layer manifest (auto-upsamples + L→RGB converts as needed).
python pipeline/build_biome_arrays.py \
    --catalog <bundle>/biome_catalog.json \
    --w4-root <godot-project-root> \
    --out     <bundle>/arrays/layer_manifest.json

# 2. Build per-tile splats. --mode hard for regression-check (no blending);
#    --mode feather --feather-width-m N for production.
python pipeline/build_tile_splats.py \
    --bundle   <bundle> \
    --manifest <bundle>/arrays/layer_manifest.json \
    --mode     feather --feather-width-m 32.0

# 3. Emit the global material .tres.
python pipeline/write_global_terrain_material.py \
    --w4-root <godot-project-root> \
    --out     <bundle>/material_world_v2.tres

# 4. Godot reimports + bakes texture imports.
godot --headless --path <godot-project-root> --import
```

Steps 1-3 are idempotent; rerun any time the catalog or biome PNGs
change.

## Catalog schema (`biome_catalog.json`)

```json
{
  "schema_version": 1,
  "tiers": [
    {"name": "standard", "resolution": 1024},
    {"name": "hero",     "resolution": 4096}
  ],
  "slots": ["ground", "mid", "rock"],
  "maps":  ["albedo", "normal", "roughness", "ao"],
  "biomes": [
    {
      "name": "forest",
      "kit_dir": "materials/anchor_v2",
      "slots": {
        "ground": {"source": "scrub_dense",   "tier": "hero"},
        "mid":    {"source": "tundra_lichen", "tier": "standard"},
        "rock":   {"source": "rocky_slope",   "tier": "hero"}
      }
    }
  ]
}
```

A biome's 3 slots can live in *different* tiers — `kit_dir` + `source`
identify the PBR set on disk, and `tier` says which array it joins.

### Tiers

`tiers` is an ordered list. The pipeline + shader assume 2 tiers
(standard + hero) by default. Adding a 3rd tier requires:

1. New entry in `biome_catalog.json` `tiers` array.
2. New sampler uniforms in `terrain_world_v2.gdshader` (4 per tier).
3. New branch in `sample_slot()` to pick the right array.
4. Bump the tier bit field — currently `tier_bit << 30`, only 2
   values fit (0/1). For 4 tiers use bits 28-29 and shrink the layer
   field to 28 bits (still 268M layers — plenty).
5. New tier_name → bit table in the host project's pack function.

About 30 lines of changes total. Plan for it if you need more than
two tiers.

### Slots

`slots` is a hand-authored list of slot names. The shader assumes
`["ground", "mid", "rock"]` for the within-biome slope blend (flat-vs-
sloped-vs-steep). Changing the slot count means rewriting the
`sample_biome_channel()` function in the shader and adding new
splat-meta record fields. The pipeline + ScaleWorld are agnostic to
the slot count above 3, but the shader has slot-specific logic.

### Maps

`maps` is the PBR map list. Default is `["albedo", "normal",
"roughness", "ao"]`. Each becomes one Texture2DArray per tier. Adding
maps (e.g. height) requires:

1. New entry in `maps`.
2. New sampler uniform in the shader.
3. New shader_parameter binding in the host project.
4. The pipeline auto-handles map enumeration.

### Per-slot field

```
"slots": {
  "ground": {"source": "<subdirectory>", "tier": "<tier_name>"}
}
```

- `source` is appended to `kit_dir` to find the PBR set on disk.
  E.g. `kit_dir="materials/biome_alpine"` + `source="ground"` →
  `materials/biome_alpine/ground/{albedo,normal,roughness,ao}.png`.
- `tier` must match one of the `tiers[].name` values.

## Splat-meta schema (`splat_meta.json`)

One per tile. 4 channels, each describes one biome contributing to
that tile, with per-slot (tier, slot-pool-index) addressing.

```json
{
  "splat_size": 64,
  "mode": "feather",
  "channels": [
    {
      "biome": "forest",
      "ground": {"tier": "hero",     "slot": 0},
      "mid":    {"tier": "standard", "slot": 0},
      "rock":   {"tier": "hero",     "slot": 1}
    },
    {"biome": "alpine", "ground": {...}, "mid": {...}, "rock": {...}},
    {"biome": null, "ground": null, "mid": null, "rock": null},
    {"biome": null, "ground": null, "mid": null, "rock": null}
  ]
}
```

`slot` is a **slot-pool index** — the position in the manifest's
`slot_pool[tier]` array that maps to the raw array layer. v1 pools are
identity (`pool[i] == i`) so the numbers match raw layers. The
indirection becomes meaningful when streaming layer paging activates
(pool[i] changes per frame as biomes page in/out).

Pre-5c builds emit `"layer"` in place of `"slot"`. ScaleWorld reads
both (see `_v2_read_slot_or_layer`).

## Customization knobs

### Different biome palette per game
Edit `biome_catalog.json` to reference different `kit_dir` paths +
biome names. Regenerate manifest + splats. Reimport. Shader unchanged.

### Different transition widths per world
Re-run `build_tile_splats.py --mode feather --feather-width-m <m>`.
Can be different per world bundle.

### Adding a biome
1. Drop PBR kit at the chosen `kit_dir/<biome_name>/` paths.
2. Append a biome entry to `biome_catalog.json`.
3. Re-run steps 1-4 of the pipeline order.

No shader/script edit needed.

### Per-tile biome variety inside a tile
Splats are 64×64 by default — but you can author them in any tool that
produces RGBA8 PNGs. Each pixel is a 4-channel weight selecting up to
4 biomes by index. The pipeline's `build_tile_splats.py` covers the
common case (hard borders + edge-feathering); for hand-painted
biome boundaries or procedural noise masks, write your own splat
producer with the same output contract.

## Known limitations (v1, 2026-05-12)

- **No streaming.** All biomes resident in VRAM. Slot pool is
  identity. The architecture is streaming-ready (CPU-side pool
  indirection in ScaleWorld) but no eviction/paging policy is built
  yet. Plan: add LRU + async layer-load on top of the existing
  contract when biome counts exceed ~30 (a comfortable VRAM ceiling).
- **Splat width is global per regeneration.** No per-pair authoring
  (alpine↔desert wider than alpine↔forest). Would need a per-pair
  table in the splat builder; small addition.
- **4-way junctions drop the 4th distinct neighbor.** A tile bordered
  by 4 different biomes only gets 3 in its splat (NESW iteration
  order, first 3 distinct win). Rare in practice. Splats have only 4
  channels by design; the 4th is reserved for the tile's own biome.
- **Iso/topdown views skip per-biome shading.** They fall back to
  single-material `material_view_iso.tres` / `material_view_topdown.tres`,
  losing biome distinction. To get per-biome shading in iso/topdown,
  author per-view biome materials or per-view shader_parameter
  overrides on the global material. Cross-cut with W4's Axis 4.
- **3-slot model (ground/mid/rock).** Hardcoded in the shader. Other
  slot counts require shader changes.
- **`Texture2DArray.tres` doesn't serialize external Image refs.**
  Arrays must be built at runtime from the manifest (see PITFALLS #5b
  in W4). `ResourceSaver.save` of a Texture2DArray produces a .tres
  with `_images = Array[Image]([null, ...])` even with
  `FLAG_BUNDLE_RESOURCES`.

## Test plan for the integration

From the host project root:

```bash
# 1. Pipeline tests (catalog validation, manifest builder, splat builder).
python -m pytest tests/ -v

# 2. End-to-end with --mode hard (regression check — no blending).
python pipeline/build_biome_arrays.py --catalog ... --out ...
python pipeline/build_tile_splats.py --mode hard ...
python pipeline/write_global_terrain_material.py ...
godot --headless --path <project> --import
godot --rendering-driver opengl3 --single-window <capture_scene>.tscn

# Expected: every tile renders with one solid biome, hard borders
# between adjacent different-biome tiles. If a tile renders as black /
# blank, check ScaleWorld's --import logs for create_from_images
# err=31 and inspect the per-layer format/mipmap diagnostic prints
# (PITFALLS #5).

# 3. Re-run with --mode feather --feather-width-m N.
# Expected: hard borders replaced by smooth weight ramps within N
# meters of every cross-biome tile edge.
```

## Files this guide doesn't carry (W4-specific)

- `ScaleWorld.gd`, `TileTerrain.gd` — W4's tile-paging runtime.
  Reference implementation; not portable as-is.
- `AnchorCameraRig.gd`, `HeadlessCapture*.gd` — W4's camera/capture
  helpers. Not portable.
- `pick_dem_crop*.py`, `slice_to_tiles.py` — W4's DEM crop + tile
  slicer. Host project picks its own heightmap source.
- `assign_biomes_scale_demo.py` — W4's hand-authored 4×4 layout.
  Host project decides how tiles get biome labels.
- `write_material_tres_biomes.py`, `terrain_scale_v1.gdshader`,
  `material_<biome>.tres` × 4 — pre-Axis-6 single-material-per-tile
  path. Useful as legacy fallback; not needed for portability.

## Update protocol for this doc

- The "Required files" list is the source of truth. If you add a
  pipeline script or shader that other projects need, add a row.
- Knobs that need host-project work to add (3rd tier, 4th slot)
  belong in the Customization section with enough detail that another
  developer can follow the recipe.
- Known limitations should age — when a v2 ships streaming, delete
  the streaming limitation row.
