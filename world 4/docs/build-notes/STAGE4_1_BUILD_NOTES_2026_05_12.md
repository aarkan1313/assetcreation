# Stage 4.1 — Single-biome rendering proof

> Proves the per-ring splat + global PBR ground texture-array
> plumbing works end-to-end. No biome variation yet (slot 0 only,
> full weight); biome culler + multi-biome blending lands in Stage
> 4.2. Shipped 2026-05-12 on `main`. Commits `611bb2f`…`b3ee9f1`.

## What shipped

| Task | Component | Commit |
|---|---|---|
| 1 | Shader: splat + PBR uniforms | `611bb2f` |
| 2 | Shader: fragment splat loop with base_albedo fallback | `5b39d4d` |
| 3 | ClipmapRing.set_splat_uniforms API | `4296d8f` |
| 4 | ClipmapWorld._compute_splat_bytes_single_biome helper | `6a24a23` |
| 5 | ClipmapWorld._load_pbr_ground_array (global Texture2DArray) | `ed3c11c` |
| 6 | ClipmapWorld builds per-ring splat + binds PBR array | `22ad000` |
| 7 | material_world_v3.tres adds new defaults | `3321214` |
| 8 | A/B captures + editor verification | `b3ee9f1` |

**Test count:** 56 → 56 (no new pytest; visual sign-off only).

## Visual delta

Before: flat brown `base_albedo` covered every ring.
After: alpine's ground albedo (scale_demo's existing 1024² PNG) tiles
the entire clipmap world at 4m / tile. The texture wraps via the PBR
sampler's `repeat_enable` and is lit by the existing per-fragment
normal shading.

Captures:
- `captures/axis1_clipmap_stage4_1_walk_2026_05_12.png`
- `captures/axis1_clipmap_stage4_1_topdown_2026_05_12.png`

## Architecture summary

```
ClipmapWorld._ready:
  _load_catalog_and_composer → catalog has N biomes
  _load_pbr_ground_array → loads each biome's
                            materials/biome_<name>/ground/albedo.png
                            into a single global Texture2DArray.
                            Falls back to scale_demo's existing
                            biome paths if catalog kit_dir is
                            empty / missing on disk.
                            Missing entirely → magenta fallback.
                            Records biome → PBR slot in
                            _biome_pbr_slot_by_name.

ClipmapWorld._finalize_ring_upload (per ring per regen):
  1. heightmap upload (Stage 3)
  2. morph plumbing (Stage 3.6)
  3. NEW: splat builder builds 1-layer R8 Texture2DArray (all 255)
  4. NEW: ring.set_splat_uniforms(splat_array, 1, [first_biome_slot])
  5. NEW: per-ring material gets the GLOBAL pbr_ground_array bound

Shader fragment:
  loop i in 0..active_biomes_n:
      w = splat_array[i] at uv_ring
      c = pbr_ground_array[biome_pbr_slot[i]] at uv_pbr (tiling)
      albedo += w * c
  fall back to base_albedo if total_w ≈ 0
```

## Plan deviations

**One small fix during execution** (Task 5):

`Image.convert(FORMAT_RGBA8)` fails on images that Godot's importer
has stored in a compressed format (BPTC / VRAM). Fixed by calling
`img.decompress()` first when `img.is_compressed()` returns true. The
unguarded path threw "Cannot convert to (or from) compressed formats"
errors at startup but still managed to build the array — fragile.
The decompress-first path is clean.

## Lessons + new pitfalls

No new PITFALLS entries — the compressed-image gotcha is well-known
in Godot 4 and shows up in many tutorials. Captured as a code
comment in `_load_pbr_ground_array` instead.

## What's still missing (Stage 4.2+)

- **Biome culler**: every ring renders as if biome 0 dominates
  everywhere. Stage 4.2 samples `KernelComposer.sample_biome_weights`
  to build real per-biome splat layers.
- **Splat morph zones**: Stage 4.3.
- **Hysteresis**: Stage 4.4.
- **Per-biome PBR for scale_v2 specifically**: Stage 4.5 — currently
  borrowing scale_demo's PBR via the fallback path. Long-term scale_v2
  should generate its own kit so the textures can be tuned.
- **mid + rock slot blending**: deferred past Stage 4.5.

## What's next

**Stage 4.2** — biome culler + multi-biome shader loop. The culler
runs in the worker (alongside heightmap regen), produces a per-ring
biome list, builds an N-layer splat. The shader loop already iterates
`active_biomes_n` so the changes are mostly CPU-side.
