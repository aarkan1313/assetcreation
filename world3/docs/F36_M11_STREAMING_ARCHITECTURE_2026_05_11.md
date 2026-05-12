# Phase F.3.6 — M11 streaming architecture (course correction)

> The F.7 `MultiBundleStreamer` approach was the wrong architecture.
> This doc captures what M11 got right, why the streamer broke it, and
> the replacement architecture that scales M11's render path to a
> multi-bundle streaming world without inventing parallel rendering
> codepaths. Course-corrected 2026-05-11 mid-session after the 5-biome
> streamer capture rendered as flat color blocks.

## What M11 got right

M11's fourway tour scene renders correctly because **every chunk in
the view shares one material, one source set, and one coordinate
frame.** Concretely, `World3AutoReviewTour._setup_terrain`:

1. Loads the bundle's `material.tres`, `.duplicate()`s it.
2. Explicitly sets `review_*` shader params on the duplicate
   (`source_macro_strength`, `roughness_floor`, `normal_strength`, ...).
3. Explicitly re-binds `source_macro_albedo` and `source_macro_valid_mask`
   via `RuntimeImageCache.load_texture` — the .tres-side ExtResource
   binding doesn't survive `duplicate()` for runtime sampling.
4. Hands the material + the bundle's heightmap + meta + splat to ONE
   `ChunkLoader`.
5. `ChunkLoader` builds a chunk grid around the camera, every chunk
   uses the same material, every chunk samples the same single source
   heightmap by world XZ.

**Key invariant:** every chunk in M11's view renders against the SAME
source. No per-chunk material variation, no multi-bundle paging, no
coordinate-frame translation. The macro UV is world-relative, splat UV
is world-relative, height sampling is world-relative. Uniformity is
load-bearing.

## What the F.7 streamer broke

`MultiBundleStreamer` violated M11's uniformity by spawning N
`ChunkLoader`s, one per bundle, each parented at the bundle's world
origin. Consequences (all visible in the 2026-05-11 5-biome capture):

- Each loader runs its own `_load_source` which mutates a duplicated
  per-bundle material — the macro binding silently drops after
  `duplicate()`, so the macro is never sampled
- Each loader builds its own 25-chunk grid (5km / 256m × 25 chunks
  per bundle = ~600 chunks for 25 bundles); none share verts with
  neighboring bundles' chunks
- Adjacent bundles' chunk grids touch but don't share an edge → hard
  seams between bundles
- The per-bundle material binds only that bundle's 5 slot textures;
  there's no path for cross-bundle splat blending
- Each loader rebuilds independently on camera moves → lag

The capture showed each bundle as a flat solid color (the dominant
slot albedo for that biome) with hard color jumps at bundle borders.
The macros we baked into the 5-biome bundles never reached the
shader.

## Replacement: `WorldChunkLoader`

One loader for the whole streaming world. Mirrors `ChunkLoader`'s
internals but resolves per-chunk source data by querying the
`world_map.json` for which bundle owns each chunk's world center.

### Data model

```
WorldChunkLoader
├── _map: WorldMapService            # reads world_map.json
├── _bundle_cache: Dictionary        # bundle_id -> {heightmap_img,
│                                    #   macro_tex, splat_tex,
│                                    #   valid_mask_tex,
│                                    #   material_template, meta,
│                                    #   elev_min_m, elev_range_m}
├── _chunks: Dictionary              # global "cx_cz" -> MeshInstance3D
└── chunk_size_m / view_radius_chunks  # M11-tour-style globals
```

### Build path (per chunk)

```
update_for_position(world_pos)
├── center = chunk_coords_for(world_pos)
├── wanted = {(cx, cz) | within view_radius_chunks}
├── for each wanted (cx, cz):
│    chunk_center_world = ((cx+0.5)*chunk_size_m, (cz+0.5)*chunk_size_m)
│    owning_bundle = _map.tile_for_world_pos(chunk_center_world.x, chunk_center_world.z)
│    if owning_bundle not in _bundle_cache:
│        _load_bundle(owning_bundle)
│    mesh_inst = _build_chunk(cx, cz, owning_bundle)
│        # mesh vertices: world-space XYZ, heights sampled from
│        #   owning_bundle.heightmap_img using bundle-local source UVs
│        #   (world XZ → bundle XZ → image fraction)
│        # material: duplicated material_template + macro/splat/mask
│        #   bound from owning_bundle's textures, review_* params set,
│        #   source_world_size_m = bundle tile_size_m
└── unload chunks not in wanted
```

### Height sampling per chunk

The chunk's world XZ vertices each project into the owning bundle's
local image coords:

```
bundle_origin_world = (tile_xy[0] * tile_size_m, tile_xy[1] * tile_size_m)
local_x = world_x - bundle_origin_world.x
local_z = world_z - bundle_origin_world.y
img_u = local_x / bundle.tile_size_m
img_v = local_z / bundle.tile_size_m
elev_norm = sample(bundle.heightmap_img, img_u * (img_w-1), img_v * (img_h-1))
elev_m = bundle.elev_min_m + elev_norm * bundle.elev_range_m
```

F.3.1 guarantees byte-exact heightmap edge agreement between adjacent
bundles, so a chunk whose world rect straddles a bundle boundary
samples matching heights at the seam (its left-half samples bundle A,
right-half samples bundle B, but the seam values agree).

### Material binding per chunk

```
mat = bundle.material_template.duplicate()
_apply_review_overrides(mat)
mat.set_shader_parameter("source_macro_albedo", bundle.macro_tex)
mat.set_shader_parameter("use_source_macro_albedo", true)
mat.set_shader_parameter("source_macro_valid_mask", bundle.valid_mask_tex)
mat.set_shader_parameter("splat_weights", bundle.splat_tex)
mat.set_shader_parameter("source_world_size_m", Vector2(tile_size_m, tile_size_m))
mat.set_shader_parameter("elev_min_m", bundle.elev_min_m)
mat.set_shader_parameter("elev_range_m", bundle.elev_range_m)
mat.set_shader_parameter("use_source_macro_world_uv", true)
mesh_inst.material_override = mat
```

The shader samples macro/splat in source-UV space. Because each chunk
binds its OWNING bundle's textures and the shader's UV is
world-position / source_world_size_m, the macro tiles seamlessly
across all chunks belonging to the same bundle, and switches to the
neighbor's macro at chunks whose center crosses into the neighbor's
tile.

### Why this is the right architecture

- Single chunk grid → no overlapping chunks, no seam between bundles'
  chunk grids; adjacent chunks share verts naturally
- Single loader update → camera moves cost one update pass, not N
- Material binding mirrors M11's tour exactly (the only path proven
  to render the macro correctly)
- Bundles cached on first encounter, unloaded when far away
- Crossfade between bundles is a future shader extension (read two
  bundles' splats at boundary chunks, mix with a per-chunk mask)

### What's NOT in v1

- Cross-bundle splat blending. Hard switches at chunk centers; the
  F.3.1 height contiguity keeps the *geometry* seamless, only the
  texture transition is sharp. Acceptable for the first capture;
  ecotone-style boundary blending is a follow-up.
- LOD. All chunks render at the same resolution. Distance-LOD is a
  G-phase feature.
- Collision. Off by default like the existing streamer.

## Migration plan

1. Write `world3/scripts/WorldChunkLoader.gd` (single-loader,
   bundle-paged renderer).
2. Write `world3/scenes/review/f36_world_streamer_tour.tscn` — a
   tour-style scene that points at `world_map.json` instead of a single
   bundle.
3. Capture iso vs M11 fourway. Quality bar: per-bundle macro visible,
   no hard color blocks, smooth chunk transitions within a bundle,
   sharp-but-aligned transitions between bundles.
4. Mark `MultiBundleStreamer.gd` deprecated; keep one cycle for
   comparison, remove after the new path proves out.
5. Update `F35_M11_PARITY_REFACTOR_2026_05_11.md`'s issue list to
   close the F.7 streamer revalidation item.

## Status

- [x] Design note
- [ ] `WorldChunkLoader.gd` written
- [ ] Tour-style scene + capture wrapper
- [ ] Iso capture passes M11 fourway quality bar
- [ ] Old streamer marked deprecated
