# Worldgen v2 — Milestone 1 Handoff (2026-05-07)

Where we ended up after the v2 rewrite + visual debugging session. **Worldgen v2
renders Death Valley end-to-end at v1 diorama scale, with FLUX-generated biome
textures, verified via headless Godot screenshots.** The canonical workflow
below is the proven path through the system; treat it as the source of truth.

## What v2 produces

One-line goal: a real OpenTopography DEM → a Godot 4.5 scene you can open and
press F6 on, with FLUX-generated biome textures painted on top.

**On disk after a successful run:**

```
D:/assets/worldgen2/                            # Godot 4.5 project (v2 output)
  shaders/biome_terrain_topdown.gdshader        # 4-channel splat shader, v1-pattern
  scripts/FlyCam.gd                             # noclip camera (WASD+QE+mouse)
  scripts/HeadlessScreenshots.gd                # multi-view capture harness
  terrain/death_valley/
    height_16.png + .import                     # 16-bit DEM (lossless import)
    biome_splat_rgba.png + .import              # 4-biome blend (lossless)
    albedo_0_desert.png ... albedo_3_sparse_pine.png   # FLUX 1024² PBR albedos
    terrain_death_valley_material.tres          # ShaderMaterial bound to all 6
    terrain_death_valley_collision.tres         # HeightMapShape3D, 256×256
  scenes/
    death_valley_character.tscn                 # FlyCam-driven view
    headless_capture.tscn                       # screenshot harness wrapper

D:/assets/pipelines/worldgen_v2/                # the pipeline source code
  batch_pipeline.py                             # entry point
  jobs/death_valley.json                        # job recipe
  presets/{quality,cameras,biomes}.json         # tunable knobs
  shaders/biome_terrain_topdown.gdshader        # canonical shader source
  stages/{fetch_dem,edit_dem,paint_biomes,compile_splat,bind_textures,stage_godot,flux_albedo}.py
  godot_writers/{shader_files,heightmap_image,material_tres,collision_tres,player_controller,scene_tscn}.py
```

## Canonical workflow (proven, works end-to-end)

```powershell
# 0. Pre-flight (every shell)
$env:OPENTOPOGRAPHY_API_KEY = [Environment]::GetEnvironmentVariable("OPENTOPOGRAPHY_API_KEY","User")
$env:PYTHONIOENCODING = "utf-8"

# 1. Start ComfyUI for FLUX (only if you'll regenerate textures; cached works without it)
& "D:\assets\animators\ComfyUI\venv\Scripts\python.exe" "D:\assets\animators\ComfyUI\main.py" --listen 127.0.0.1 --port 8188

# 2. Stage the world (uses cached FLUX textures by default)
$env:WORLDGEN_V2_USE_FLUX = "1"
python -m pipelines.worldgen_v2.batch_pipeline pipelines/worldgen_v2/jobs/death_valley.json

# 3. Wipe Godot's import cache so changed sidecars take effect
Remove-Item -Recurse -Force D:\assets\worldgen2\.godot
Get-ChildItem D:\assets\worldgen2\terrain\death_valley\*.import | Remove-Item

# 4. Re-import (Godot patches our partial sidecars with uid+path+metadata)
& "C:\Godot\Godot_v4.5-stable_win64.exe" --path "D:\assets\worldgen2" --headless --import

# 5. Capture headless screenshots
& "C:\Godot\Godot_v4.5-stable_win64.exe" --path "D:\assets\worldgen2" "res://scenes/headless_capture.tscn"
# Output: D:/tmp/wgv2_screens/{overview_high,overview_close,ridge_side,low_ground,topdown}.png

# 6. (Optional) Open in Godot for FlyCam exploration
& "C:\Godot\Godot_v4.5-stable_win64.exe" --path "D:\assets\worldgen2"
# In editor: open scenes/death_valley_character.tscn, F6
# WASD = horizontal, QE = up/down, mouse = look, Shift = sprint
```

## Critical lessons (from v1 PM handoffs + v2 debugging)

These are the things that took us hours to find. Don't lose them.

### 1. v1 always shipped at 512m × 64m diorama scale, never at real km extents
v1 produced 23 working scenes — all at the legacy diorama scale. The PM5
handoff explicitly says "**For phase 2 work, ignore --use-real-extents and
stay on legacy scale.**" v2 follows that: `presets/quality.json` defines
`render_size_m=512.0` and `render_height_m=64.0`. The DEM heightmap is still
real-world topology, just visually scaled to fit the diorama.

Why this matters: at km scale, 3-meter texture tiles average to grey via
mipmapping. Sun-fill, scatter density, camera FOVs, fog density all break.
The v1 team fought km-scale rendering and didn't solve it before v2.

### 2. Godot 4 spatial-shader VERTEX semantics differ between vertex() and fragment()
- vertex(): VERTEX is in **model space** (PlaneMesh local XZ from -size/2 to +size/2)
- fragment(): VERTEX is in **view space** (camera-relative, can be huge negatives)

So in fragment(), use:
- `UV` (interpolated from vertex stage automatically) for splat sampling
- A `varying vec3 v_world` for tile-meter lookups in world space
Not VERTEX.xz. That bug painted black holes for hours.

### 3. The shader needs an "ocean blend" fallback
v1's PM3 explicitly added this to fix "pitch-black valleys". Without it,
fragments where splat samples to (0,0,0,0) (e.g. UV drift outside [0,1])
multiply albedo by zero → solid black. v2's shader has:

```glsl
float wsum_raw = w_raw.r + w_raw.g + w_raw.b + w_raw.a;
float fallback_blend = 1.0 - clamp(wsum_raw * 8.0, 0.0, 1.0);
ALBEDO = mix(alb_biome, fallback_color, fallback_blend);
```

### 4. Heightmap & splat are data textures, not view textures
Their import sidecars MUST set `compress/mode=0` and `mipmaps/generate=false`.
Godot's default 3D import compresses to S3TC and generates mipmaps; that
visibly cracks the heightmap displacement and creates black biome holes from
mip averaging. `heightmap_image.py` writes the right sidecar params and
clears stale `.godot/imported/*.ctex` so they take effect.

### 5. Material goes on the PlaneMesh sub_resource, not material_override
v1 pattern: `[sub_resource type="PlaneMesh" ...] material = ExtResource("1")`.
Don't use `material_override` on the MeshInstance3D — the sub_resource path
is what v1's 23 working scenes used.

### 6. extra_cull_margin is required at scale
PlaneMesh's AABB is computed from the un-displaced flat mesh. When the
shader displaces vertices by terrain_height_m upward, those vertices are
outside the flat AABB and get culled. Set `extra_cull_margin = 16384.0` on
the MeshInstance3D so the cull test sees the displaced extents.

Same for `lod_bias = 128.0` — Godot's mesh LOD reduces vertex count at
distance, creating thin sliver triangles with broken normals. Disable.

### 7. The `--import` step must run between stage and capture
Our `heightmap_image.py` writes a partial `.import` sidecar (compress/mode=0
and friends — what we want) but lacks `uid=` and `path=` (Godot generates
those on import). Workflow: stage → wipe `.godot/` → `--headless --import`
(Godot fills in the missing fields and rebuilds `.ctex` cache) → capture.

### 8. Iso/topdown/worldview cameras need script-driven `look_at`, not pre-computed basis
Pre-computing the orthographic camera basis in Python (forward/right/up cross
products) is math-correct (orthonormal, right-handed, det=1, points at target)
but Godot 4 silently culls/discards rendering when the camera transform is
written that way. The proven path: write the camera at the correct world
position with identity basis, attach `IsoCam.gd` (one-line `look_at(target,
Vector3.UP)` on `_ready`), and Godot orients it correctly on scene load.

This affects the `iso`, `topdown`, and `worldview` camera presets. The
character preset uses `FlyCam.gd` and is unaffected.

### 9. tile_meters must be large enough that screen-space UV derivatives don't blow out mip selection
With `world.xz / tile_meters` UV math and a 1m-per-quad densely-subdivided
mesh, screen-space derivatives of the tile UV are large. Mip selection picks
high mip levels that average to the texture's mean color, so FLUX detail
vanishes. The terrain renders correctly (geometry, lighting, biome blending)
but the surface looks like flat-shaded clay.

The fix is **tile_meters = ~128m at diorama scale** (512m terrain). That
brings screen-space UV gradients into a range where mip selection lands on
detail-bearing levels. v1 used 3-4m tile_meters but v1 also used a different
shader path; v2 needs the larger tile to actually show FLUX detail.

If you change rendering scale, scale tile_meters proportionally:
- 512m terrain (diorama): tile_meters ~128
- 1024m terrain: tile_meters ~256
- 35km terrain (real km-scale): tile_meters would need to be ~5km, at which
  point the texture is "global ground tone" not "ground texture" — this
  is part of why km-scale rendering doesn't work with this shader pattern.

### 10. ComfyUI for FLUX runs locally on port 8188
- Server: `D:\assets\animators\ComfyUI\venv\Scripts\python.exe` + `main.py`
- Models in `models/diffusion_models/flux-2-klein-4b.safetensors` (16 GB)
- Wrapper: `pipelines/textures/flux_seamless.py` (4-pass tile-heal algorithm)
- v2 caches each (job_id, biome) FLUX output under
  `D:/assets/world/textures/library/wgv2_<job>_<biome>/<id>_albedo.png`
- v2's `bind_textures.py` re-uses the cache instead of regenerating

## Visual quality status (as of milestone 1)

What works (verified in headless screenshots at `D:/tmp/wgv2_screens/`):
- Real Death Valley topology — recognizable Panamint Range silhouette,
  Badwater Basin floor, alluvial fans
- FLUX texture detail visible at character / overview ranges
- Biome splat softly blends 4 biomes (desert/salt_flat/rocky_highland/sparse_pine)
- Sun lighting + sky + ambient + tonemap all loading without errors
- FlyCam noclip camera works for free exploration

What still looks rough:
- Slopes facing away from sun read very dark (no shadow fill yet)
- At overhead views the biomes mostly average to similar tan because they're
  individually mid-saturation
- Topdown view is heavily blue-tinted because sky-driven ambient dominates
- No scatter / props (deferred to milestone 2)

These are visual polish; the pipeline correctness is verified.

## What's deferred to v2.1+

Per spec at [docs/superpowers/specs/2026-05-06-worldgen-v2-design.md](../superpowers/specs/2026-05-06-worldgen-v2-design.md):

- Scatter / props (Build chat G's lane)
- Real PBR maps (currently FLUX albedo only — no normal/roughness/ao)
- 2D and isometric output renderers (camera presets exist, only 3D output wired)
- Procedural FastNoise terrain alternative
- Multi-DEM stitching
- Hand-edited heightmap overrides
- Biome painting that actually uses elevation+slope+climate (current is
  softmax-temperature affinities with Gaussian blur)

## Pipeline contract (per-stage)

| Stage | Reads | Writes |
|---|---|---|
| `fetch_dem` | job.dem.bbox + dataset | `output/<id>/height_16.png`, `dem_meta.json` |
| `edit_dem` | `height_16.png` | `height_16_edited.png` (passthrough for `realistic`) |
| `paint_biomes` | `height_16_edited.png` | `biome_mask.png` (debug only) |
| `compile_splat` | `height_16_edited.png` | `biome_splat_rgba.png` (softmax+blur) |
| `bind_textures` | `biome_mask.png` (no longer used), env `WORLDGEN_V2_USE_FLUX` | 4× `albedo_*.png`, `pbr_pack.json` |
| `stage_godot` | all of above + `presets/quality.json` | godot project files |

`stage_godot` orchestrates 6 godot_writers — see `pipelines/worldgen_v2/godot_writers/`.

## Tests

```powershell
cd D:/assets/tests/worldgen_v2
python -m pytest . -v
```

46 tests, ~1.7s. Run before any pipeline change.

## Iso scene capture

```powershell
# After step 1 (stage) above, with cameras: ["character", "iso"] in the job:
& "C:\Godot\Godot_v4.5-stable_win64.exe" --path "D:\assets\worldgen2" --headless --import
& "C:\Godot\Godot_v4.5-stable_win64.exe" --path "D:\assets\worldgen2" "res://scenes/headless_iso_capture.tscn"
# Output: D:/tmp/wgv2_screens/iso_view.png
```

Iso scene file: `D:/assets/worldgen2/scenes/death_valley_iso.tscn`. Diablo-style
30deg pitch / 45deg azimuth, ortho size 0.85 × terrain_size, framed on the whole
diorama. Confirmed renders Death Valley topology cleanly via headless.

## Open questions for next session

1. **Biome contrast is low** — desert / salt_flat / rocky_highland all mid-tan.
   Either tune FLUX prompts for more saturated outputs, or apply a
   per-biome color multiplier in the shader before the texture sample.
2. **Lighting tuning** — current sun_energy=2.0 + ambient_energy=1.0 +
   sky_contribution=0.6 is "ok-ish". A SDFGI bake or a single fill light
   would lift the dark slopes.
3. **Iso/topdown camera variants** — milestone 1 only ships character cam.
   Iso/topdown are presets in `cameras.json` but no wiring to scene_tscn yet.
4. **Smaller bbox** — current Death Valley is 0.4° × 0.4° (≈35×44 km of real
   topology compressed into 512m). A 0.15° bbox around Badwater would give
   sharper relief at diorama scale.

## Don't-touch list (v1 / other lanes)

- `pipelines/terrain/` — v1 worldgen, retained read-only
- `pipelines/godot_export/stage_biome_terrain.py` — v1 stager, reference only
- `godot_pack/shaders/biome_terrain.gdshader` — v1 shader, reference only
- `pipelines/{props,game_data,audio,ui,vfx}/` — other Build chats
- `world/textures/library/biome_*` — v1 biome texture sets

v2 lives at `pipelines/worldgen_v2/` and `worldgen2/`. Modify those.
