# W4 Pitfalls

> Visible terrain artifacts we've hit, with the actual root cause and the
> actual fix for each. These are **solutions to look up when problems
> appear**, not rules to follow upfront. Read the symptom matrix first,
> then jump to the matching section.
>
> Important: this doc supersedes the per-incident lesson docs
> (`AUDIT_HANDOFF_BLACK_ARTIFACTS_2026_05_11.md`,
> `BLACK_PATCH_BUG_LESSONS_2026_05_11.md`,
> `TERRACING_BUG_LESSON_2026_05_11.md`). Those are kept on disk for
> historical reference but the canonical answers live here.

## Symptom matrix

| What you see | Most likely pitfall |
|---|---|
| Black hex/square pixel speckles overlaid on otherwise-fine terrain | **#1 — Source-texture black texels** |
| Stripe/dot patterns that **shift when the player walks** | **#2 — Source-DEM LiDAR scan-line noise** |
| **Stationary** pure-black mesh quads at world scale, aligned to mesh edges | **#3 — Godot PBR pipeline at large scale** |
| Contour-aligned fingerprint bands across slopes | **#4 — Normal stencil too narrow vs heightmap pixel scale** |
| Hard cliff/seam at tile boundaries | (Not yet documented — file an entry if you hit this) |
| `Texture2DArray.create_from_images` returns err=31 / `ERR_INVALID_DATA` at scene init | **#5 — Texture2DArray layer uniformity** |
| Hard diagonal color lines at tile boundaries between biomes in walk view (editor only — headless captures hide it) | **#6 — Per-tile splat boundaries can't bilinear-interpolate** |
| Clipmap skirts collapse onto surface; gaps visible at ring boundaries | **#7 — Heightmap displacement clobbers skirt offset** |
| Adjacent clipmap rings disagree at shared edge by ~half a texel | **#8 — Half-texel UV offset for heightmap sampling** |
| Clipmap rings don't overlap; thin dark gap visible at every ring boundary | **#9 — `inner_grid_n` rounded UP creates gap, not overlap** |
| Worker-thread errors on scene shutdown: "null instance" from worker functions | **#10 — `WorkerThreadPool` outlives its shared dependencies** |
| Elevation cliff at every clipmap ring boundary; persists with no other artifacts | **#11 — Clipmap rendering without morph zones** |

## Pitfall #1 — Source-texture black texels become speckle noise

### Symptom
- Pure-black pixels appear in hex/square clusters overlaid on the terrain
- Pattern shifts subtly as the camera moves (mipmap-selection-dependent)
- Visible in live editor view, much less visible in headless captures
- Doesn't track the geometry — looks "painted on" the surface

### What's actually happening
Some PBR textures (especially ComfyUI-generated tilable like
`tundra_lichen/albedo.png` and the corresponding `ao.png`) contain
genuine near-black texels representing cracks, deep shadow, organic
detail. When a terrain shader blends these textures at small UV scale
(~25m per repeat), those black pixels appear hundreds of times across
the visible view. AO maps with low minimums (0.08–0.20) amplify the
darkness. Normal-map detail at high strength produces high-contrast
speckling on top.

### Working fix (current shaders have this)
1. **`luma_floor()` per-slot in the shader** — clamp each sampled albedo
   to a minimum luminance (~0.08) before blending. Black texels can't
   propagate.
2. **`ao_floor` uniform** — clamp the blended AO to ~0.72 minimum.
   Default 0.0 is too aggressive when source AO maps bake in cracks.
3. **NaN guards on blend weights** — `max(total, 1e-4)` before dividing.
4. **No manual `normalize()` on blended normals** — zero-vectors NaN.
   Let Godot's PBR pipeline normalize internally.
5. **Final `clamp(NORMAL_MAP, 0, 1)`** as last-resort safety.
6. **`SurfaceTool.generate_tangents()`** if building ArrayMesh manually
   — Godot does NOT auto-generate tangents and missing tangents produces
   pixel-aligned NaN artifacts of its own.
7. **Mesh `cast_shadow = OFF`** on terrain — self-shadowing on heightmap
   meshes can amplify already-dim regions.

`shaders/terrain_anchor_v2.gdshader` and `terrain_scale_v1.gdshader`
both contain these guardrails.

### What DIDN'T fix it (don't waste time)
- Tuning `normal_strength`, `albedo_gain`, `ambient_light_energy`, etc.
  alone — the problem is in the source texture data, not the shader math
- Changing texture import settings (`compress/mode`, `compress/normal_map`)
  — actually made it worse on first attempt; reverted to defaults
- Disabling backface culling
- Increasing tonemap exposure
- Bumping shadow biases

### How to recognize it next time
Check source albedo and AO maps for near-black texels:
```python
import numpy as np
from PIL import Image
a = np.asarray(Image.open('PATH/albedo.png').convert('RGB'), dtype=np.float32) / 255
l = 0.2126*a[...,0] + 0.7152*a[...,1] + 0.0722*a[...,2]
print('min:', l.min(), 'p5:', np.percentile(l, 5), 'mean:', l.mean())
```
If `min` or `p5` is below ~0.05, the texture WILL speckle without the
luma floor. Either pick a different texture or keep the floor active.

### Rule of thumb when adding new materials
Add **one slot/map at a time** and capture walk+iso+topdown after each
change. Never stack 3 new textures into a blend at once.

---

## Pitfall #2 — Source-DEM LiDAR scan-line noise

### Symptom
- Dark/light bands aligned diagonally across slopes
- Pattern **shifts when the player walks**, stays stable when only camera rotates
- Banding direction matches the source DEM's LiDAR flight direction
- Worse on flatter/gentler slope regions of a DEM (real signal is small relative to noise)
- Invisible on steep, chaotic real-terrain regions (real features dominate)

### What's actually happening
USGS1m and similar LiDAR products have ~1cm scan-line noise baked into
the elevation values. At 1m sampling the noise becomes per-pixel
elevation jitter. The lambertian dot product amplifies any
high-frequency normal noise into visible banding.

### Working fix
Apply a small gaussian blur to the heightmap **before slicing into
tiles**. `scipy.ndimage.gaussian_filter(arr, sigma=1.0, mode="nearest")`
is enough to suppress per-pixel noise while preserving real features
down to ~2-3m scale.

In W4 this is wired into `pipeline/slice_to_tiles.py` as
`SMOOTH_SIGMA_PX = 1.0`. Bump to 2.0 if striping persists.

For raw research that prefers fidelity over visual cleanness, set
sigma to 0.

### Diagnostic test that pins it
```python
import numpy as np
from PIL import Image
src = np.asarray(Image.open(path), dtype=np.int32).astype(np.float32)
slope_mag = np.sqrt(np.gradient(src, axis=0)**2 + np.gradient(src, axis=1)**2)
norm = (255 * slope_mag / slope_mag.max()).clip(0, 255).astype(np.uint8)
Image.fromarray(norm).save("slope_mag.png")
```
If `slope_mag.png` shows parallel diagonal fishbone striping, that's
LiDAR scan-line noise. Organic dendritic patterns = clean DEM.

### What DIDN'T fix it (don't waste time)
- Changing the renderer's anisotropic filtering settings
- Changing the shader's lighting math
- Bigger mesh density — the noise is in the source data, not the mesh

---

## Pitfall #3 — Godot PBR pipeline produces stationary black quads at scale

### Symptom
- **Pure-black** mesh quads (not dim, not back-faces, fully zeroed RGB)
- **Stair-step or rectangular patterns** aligned with the heightmap pixel grid
- **Fixed in world space** — don't move when player walks or camera rotates
- Appears under **any lit shader**, even a 3-line minimal shader using Godot's PBR
- Disappears entirely under **`unshaded`** render_mode
- Mostly invisible in headless OpenGL Compatibility captures; visible in editor Forward+ Vulkan

### What's actually happening
**Not fully isolated.** Strong evidence that Godot's PBR pipeline does
something to certain fragments at large world coordinates × steep
normal magnitudes that drives the output to zero. Could be tangent-space
transform on edge fragments, Forward+ reflection cubemap sampling, or
specular pipeline producing clamp-to-zero output.

### Working fix
**`render_mode unshaded`** on the shader, with manual lambertian +
ambient math computed in the shader itself.

`shaders/terrain_scale_v1.gdshader` is the canonical example:
- 3-slot slope-blended albedo (same as anchor v2)
- Manual `dot(normal, sun_dir)` clamped above `lambert_floor`
- Soft ambient term from uniform sky/ground colors mixed by `normal.y`
- No reads of Godot light sources, no PBR pipeline, no GI/reflection

### What DIDN'T fix it (don't waste time)
- Setting `light_energy = 0` on the sun (artifact stays)
- Disabling shadows
- Setting `ambient_light_sky_contribution = 0`
- Tweaking custom PBR uniforms (AO/ROUGHNESS/SPECULAR/METALLIC)
- Removing `SurfaceTool.generate_tangents()` from the mesh
- v2 shader math tweaks (luma_floor, slope blending, normal blending)

### How to recognize it next time
Bisect: swap the shader for a minimal **unshaded** 3-line shader
(`ALBEDO = vec3(0.5)`). If the artifact vanishes → you've hit this
pitfall. Use the scale_v1 manual-lighting pattern.

### Where this matters
- Anchor (256m world, 232m relief) has this bug **latent** but the
  artifact lands in regions where `luma_floor` clamps it below
  visibility. Anchor uses `terrain_anchor_v2.gdshader` (lit, PBR) and
  is locked as regression baseline. Don't change it.
- Scale (1024m world, 522m relief) and anything larger should use
  `terrain_scale_v1.gdshader` or its descendants — unshaded with manual
  lighting.

### Open question (not blocking)
If we ever need real-time lighting on terrain (dynamic time-of-day,
moving lights, shadow cascades from Godot's DirectionalLight), this
needs to be resolved. Until then, manual lighting in shader is the
right choice — faster and gives direct control over the visual.

---

## Pitfall #4 — Contour-aligned fingerprint bands on slopes

### Symptom
- Evenly-spaced parallel light/dark bands running across slopes
- Bands are oriented **perpendicular to the slope direction** (i.e. along contours)
- Each band is ~1 heightmap pixel wide
- Visible in BOTH live editor view AND headless captures
- Worse on the smoother / cleaner regions of the DEM (where the only signal IS the bands)

### What's actually happening
The fix works via **adjacent-vertex normal correlation**, not by
averaging out noise. The mechanism:

- With `stencil = 1m` on a 1m mesh, vertex A's normal samples heights
  at `(A-1, A+1)`. Adjacent vertex B (at A+1) samples `(A, A+2)`. They
  share **1 of 2 samples** per axis → adjacent normals are largely
  independent → lambertian over the slope produces 1-pixel-wide
  light/dark bands aligned with contour lines.
- With `stencil = 8m` on a 1m mesh, vertex A samples `(A-8, A+8)`,
  adjacent vertex B samples `(A-7, A+9)`. They share **15 of 16
  samples** per axis → adjacent normals are nearly identical →
  smooth lambertian → no bands.

The reframe matters because the slope MAGNITUDE doesn't change with
stencil width — measured per-meter average X-delta is 0.37m at
stencil 1m through 16m (see `captures/diag_hillshade_stencil{1,4,8}.png`
and the diagnostic numbers below). The terrain isn't "noise on a smooth
surface"; it's genuinely rough at every scale. Widening the stencil
doesn't make the surface smoother — it makes neighboring normals more
correlated, which is what the eye reads as "smooth shading."

**Measured baseline for the scale_demo crop (1024m, 522m relief):**
- Per-pixel X delta: mean 0.37m, p99 1.06m, max 3.72m
- Per-meter avg delta is identical (0.37m) across stencil widths 1, 2, 4, 8, 16

This means a simple "denoise the heightmap" approach won't fix the
banding — there's no high-frequency noise to remove. Normal correlation
via wider stencil is the right lever.

### Why this contradicts the earlier TERRACING_BUG_LESSON doc
The earlier doc (`TERRACING_BUG_LESSON_2026_05_11.md`) ran a hillshade
diagnostic and saw real directional bias in the source DEM, concluding
"the DEM is striated, pick a different crop." The diagnostic was real
— there IS some directional bias visible at stencil=1. But the bias is
small enough that real terrain features dominate at any reasonable
rendering scale; it wasn't the dominant cause of the rendered bands.
The dominant cause was adjacent-normal independence at narrow stencils.

If you ever hit a DEM with strong directional bias (a coastal cliff,
a fault scarp, anywhere with one dominant geological grain), the
hillshade diagnostic is still useful and the source-DEM angle isn't
ruled out — it just wasn't load-bearing for the Blue Ridge crop.

### Working fix
**Widen the normal stencil** so it averages over a multi-meter window,
smoothing the lambertian without changing the geometry.

In `scripts/TileTerrain.gd`, the normal stencil is the `normal_stencil`
exported variable (current default: 8 meters). The geometry samples are
still at `resolution_m` (1m), so vertex positions are unchanged.
Normals are computed by calling `_sample_height()` at `±normal_stencil`
meters from each vertex, then doing the finite-difference.

Default 8 is what worked for scale_demo. Anything from 4 to 16 is
reasonable; smaller = more terrain detail in lighting but more banding,
larger = smoother lighting but lighting reads less crisp.

### What DIDN'T fix it (don't waste time)
- Gaussian smoothing the heightmap further (sigma=1, 2, 3 all tried;
  destroys real features long before banding goes away)
- Upsampling the heightmap 2× (mesh vertices still land at integer
  pixel positions on the upsampled grid → no bilinear blend → same noise)
- Picking a different DEM crop. The `pick_dem_crop_scale.py` FFT
  anisotropy penalty (`directional_anisotropy()` + `RIDGE_PENALTY_WEIGHT`)
  was built to auto-reject crops with strong directional bias. **It works
  as designed, but isn't necessary at current scale** — the dominant
  cause of fingerprint bands is adjacent-normal independence, not
  source-DEM bias. The machinery stays in the codebase as an alternative
  lever for future DEMs with strong geological grain (coastal cliffs,
  fault scarps, parallel-ridge tectonic terrain). For the Blue Ridge
  region currently used, leave it disabled.
- Increasing mesh density to 0.5m (engages bilinear but exposes
  source-data noise as smaller-scale bands)
- Changing the shader (banding is geometric, not in the shader math)

### Why the anchor doesn't show this
Anchor is 256m world, 232m relief — steep, chaotic per-pixel topology
swamps the band signal. The bands are technically present but hidden
in the visual noise of the steeper crop. Scale_demo's 1024m, 522m relief
crop has wider smooth-slope regions where the bands have nothing to
hide behind.

### Diagnostic artifacts on disk
- `captures/diag_hillshade_stencil1.png` — source DEM hillshade at
  ±1m stencil (matches rendered banding pattern when shader has
  `normal_stencil = 1`)
- `captures/diag_hillshade_stencil4.png` — ±4m stencil hillshade
- `captures/diag_hillshade_stencil8.png` — ±8m stencil hillshade
  (matches current default; visibly smoother)

Eyeballing these is enough to confirm "normal correlation widens with
stencil." If the data ever drifts (different DEM, different scale),
re-run the diagnostic Python snippet under "How to recognize it next
time" below to regenerate them.

### Live reproduction setup
The diagnostic captures were produced against:
- `pipeline/pick_dem_crop_scale.py` with `ALLOW_RIDGED_OVERRIDE = True`
  (pins the crop at world pixel `(1280, 5888)` — the original striated
  region that surfaced this bug; 522m relief)
- `pipeline/slice_to_tiles.py` with `SMOOTH_SIGMA_PX = 1.0`
- `scripts/TileTerrain.gd` with `normal_stencil = 8`

To reproduce the bug live in the editor: open `scenes/scale_demo.tscn`,
select any `TileMesh_*` node, change `normal_stencil` to `1` in the
inspector. Bands should appear within one frame. Reset to 8 to confirm
they collapse. No rebuild or `--import` needed — the export reads at
build time inside `_ready` so you'd need to reload the scene; alternatively
edit the script default and reopen the scene tab.

To rebuild against a non-striated crop later: set
`ALLOW_RIDGED_OVERRIDE = False` and re-run both pipeline scripts.

### How to recognize it next time
1. Look at the source heightmap's hillshade. If it shows real
   directional bias that's much stronger than the diagnostic captures
   above, the source-DEM angle may be relevant after all (run the FFT
   anisotropy diagnostic in the historical terracing doc).
   Otherwise, the bands are normal-correlation, not source bias.
2. Confirm: temporarily set `TileTerrain.normal_stencil = 1`. Banding
   should get **much worse**. Then set it to 8 or 16 — banding should
   collapse.

---

## Pitfall #5 — Texture2DArray layer uniformity in Godot 4.5

### Symptom
- `Texture2DArray.create_from_images(imgs)` returns err=31
  (`ERR_INVALID_DATA`) at scene init
- Source PNGs all look fine individually — same dimensions, all valid
- Affected: any pipeline that bundles per-biome PBR maps into a shared
  array (W4 Axis 6 array+splat path uses this)
- Often only affects ONE array (e.g. AO) while the others
  (albedo/normal/roughness) build successfully

### What's actually happening
`create_from_images` requires every layer to share three things, not
just resolution:

1. **Pixel format.** `Image.get_format()` must match across all layers.
   PIL saves L-mode PNGs as `FORMAT_L8`, RGB-mode as `FORMAT_RGB8`,
   RGBA-mode as `FORMAT_RGBA8`. A single L-mode source in an otherwise
   RGB array breaks the whole array.
2. **Mipmap state.** `Image.has_mipmaps()` must match across all
   layers. Godot's import pipeline bakes mipmaps into some PNGs (the
   defaults for albedo/normal) and not others (depending on import
   preset, .import file age, or the file's source pipeline). One
   layer with mipmaps + one without → err=31.
3. **Resolution.** Already documented in the array builder; this one
   you'd notice immediately.

The error code is the same (err=31) for all three causes, and Godot
doesn't print which dimension mismatched. Hence the symptom of "all my
files are fine individually."

### Working fix (W4 implementation)
Two-pronged: convert in the Python pipeline + force at runtime in the
GDScript array builder.

**At pipeline time** (`pipeline/build_biome_arrays.py`):
- The `_ensure_resolution` helper now does mode conversion alongside
  upsampling. L-mode → RGB; mismatched-resolution → LANCZOS upsample.
- Output siblings get suffixes like `__upsampled1024_rgb.png` so the
  cache check can find them on rerun.

**At runtime** (`ScaleWorld.gd::_build_v2_arrays_if_needed`):
- Decompress imported textures (`img.decompress()` if compressed).
- Force `FORMAT_RGBA8`: `img.convert(Image.FORMAT_RGBA8)` always.
- Drop mipmaps: `img.clear_mipmaps()` always. The `Texture2DArray`
  regenerates them as needed at sampling time, and uniformity is
  guaranteed.

The runtime forcing is what we ship — even if the pipeline gets the
formats right, Godot's import path can re-introduce mismatches
(mipmaps on/off varies by import preset). Belt and suspenders.

### What DIDN'T fix it (don't waste time)
- Re-running `--import` repeatedly. Godot caches `.ctex` outputs and
  re-running doesn't force the format/mipmap state to converge.
- Deleting `.godot/imported/` and re-running. Useful but didn't
  resolve the underlying mismatch; the import preset itself encodes
  the format inconsistency.
- Setting `compress/mode = 0` in `.import` files. Affected on-disk
  compression but didn't change in-memory Image format after load.
- Changing the .tres / catalog format — the bug is downstream of
  catalog loading.

### How to recognize it next time
1. The first build of a multi-layer Texture2DArray throws err=31.
2. Add a diagnostic print before `create_from_images`:
   ```gdscript
   for k in range(imgs.size()):
       var im_d: Image = imgs[k]
       print("[%d] sz=%s fmt=%d mips=%s" % [
           k, im_d.get_size(), im_d.get_format(),
           str(im_d.has_mipmaps())])
   ```
3. If any column varies across layers, that's the mismatch. Fix in
   ScaleWorld with `convert(FORMAT_RGBA8)` + `clear_mipmaps()` for
   uniform state.

### Bonus pitfall #5b — Texture2DArray doesn't serialize to .tres cleanly
Godot 4.5 saves a `Texture2DArray` with `_images = Array[Image]([null, null, ...])`
even with `ResourceSaver.FLAG_BUNDLE_RESOURCES`. The supported paths
for shipping a Texture2DArray are:
- **Editor sprite-sheet import preset** (one big PNG, sliced via
  `.import` config). Works but rigid.
- **Runtime construction** from `Image` / `Texture2D` resources
  (W4's choice for Axis 6 — see `ScaleWorld._build_v2_arrays_if_needed`).

Trying to hand-write a `Texture2DArray.tres` that references external
PNGs via `_data = [ExtResource("layer0"), ...]` does NOT work. The
property is `_images` (not `_data`), and even when set to ExtResource
references it deserialises to null images. Tracked at
[godot-proposals#10601](https://github.com/godotengine/godot-proposals/issues/10601).

---

## Pitfall #6 — Per-tile splat boundaries can't bilinear-interpolate

### Symptom
- Hard diagonal color lines at tile boundaries between adjacent
  different-biome tiles in walk view
- Visible only in editor (Forward+ Vulkan), invisible in headless
  OpenGL Compatibility captures — so passes the regression suite
  but breaks the live view
- Persists even after fixing pixel-center continuity in the splat
  builder

### What's actually happening
Per-tile splat textures (one RGBA8 per tile, mapped 0..1 across the
tile) sample independently at each tile's edge. When the GPU's
bilinear filter samples fragments near a tile boundary, it
interpolates between two pixels INSIDE that tile — it can't cross
into the neighbor tile's splat. Even if both tiles' edge pixel
centers contain identical weights (`[128, 128, 0, 0]`) by
construction, fragments at intermediate world positions read
*different* texels from the *two different splats* and get
*different* colors. Hard line.

### Working fix
**One world-spanning Texture2DArray splat, sampled by world XZ.**
Adjacent tiles are different meshes but share the SAME splat
texture. Fragments at any world XZ — including the tile-edge zone —
sample the same texels with continuous bilinear interpolation.
Boundary problem dissolves.

Architecture lives in:
- `pipeline/build_world_splat.py` — emits N R8 PNGs (one per biome)
  at world resolution.
- `terrain_world_v2.gdshader` — `world_splat: sampler2DArray` +
  `num_biomes: int` loop bound + per-biome packed `(tier, layer)`
  arrays for the within-biome ground/mid/rock slot lookup.
- `ScaleWorld.gd::_build_v2_arrays_if_needed` — builds the splat
  array at scene init and binds it to the global terrain material.
  Every tile uses the SAME global material.

### Why this is also the right answer for N > 4 biomes
A single RGBA8 splat caps at 4 active biomes per fragment. The
sampler2DArray splat has one layer per biome with no channel cap.
For our 5-biome scale_demo we have 5 layers; for a future 15-biome
world we'd have 15. The shader's per-fragment cost stays small
because the loop early-outs on near-zero weights — most fragments
read 1-2 active layers.

### What DIDN'T fix it (don't waste time)
- Pixel-center continuity in the per-tile splat builder
  (`(px - 1) * m_per_px` instead of `(px - 0.5) * m_per_px`).
  Adjacent edge pixels agreed exactly but interior fragments still
  read different texels from different tiles → hard line.
- Adding shader hints `filter_linear, repeat_disable` on the
  per-tile `splat: sampler2D`. Sampling was already correct; the
  problem was the two tiles' splats being separate textures.
- Wider feather widths in the per-tile splat builder. More smoothing
  inside each tile didn't help because the discontinuity is AT the
  tile boundary, not inside the feather zone.

### How to recognize it next time
Look for hard lines that align with tile-edge XZ coordinates. If
the seam is along tile boundaries specifically (not biome
boundaries), this is the cause. The fix is a world-splat refactor,
not a splat-builder tweak.

### Bonus pitfall #6b — Trusting headless captures over editor
Headless captures hid this bug entirely. Don't approve a
splat/blend change based on the headless walk capture alone — open
the editor and walk across at least one biome boundary first. See
methodology section.

---

## Pitfall #7 — Heightmap displacement clobbers skirt offset

### Symptom
- Clipmap terrain renders correctly across rings BUT thin dark bands /
  z-fight pepper appear at ring boundaries from certain camera angles
- Looking topdown, no actual gap visible — but the bands persist
- Walk view shows the bands as horizon-aligned slivers between adjacent
  rings

### What's actually happening
Skirt verts in the donut mesh arrive with `VERTEX.y = -skirt_depth_m`
(typically -10m). A vertex shader that writes `VERTEX.y = h` (where `h`
is the heightmap sample) **clobbers** the skirt offset — surface and
skirt verts both end up at `h`, collapsing the skirt onto the surface.
The skirt no longer hides the ring-boundary discontinuity it was built
for.

### Fix
```glsl
void vertex() {
    float h = sample_heightmap(world_xz);
    VERTEX.y += h;   // ADD, don't replace
}
```

Skirt verts then sit at `h - skirt_depth_m`, properly tucked under the
surface, hiding the crack.

### What this is NOT
Not a heightmap precision issue. Not a UV alignment issue. The skirt
math is correct in the GDScript mesh builder; the shader is what's
breaking it.

## Pitfall #8 — Half-texel UV offset for heightmap sampling

### Symptom
- Adjacent clipmap rings render at *slightly* different heights at
  their shared boundary
- The disagreement is consistent — same direction every time, about
  half a texel worth
- Visible as a faint cliff at every ring boundary; not a gap, but
  not flat either

### What's actually happening
A clipmap ring with N×N vertices spaced `step` meters apart spans
`(N-1) * step` meters edge-to-edge. The displacement texture stored
for the ring is N×N texels. With `filter_linear, repeat_disable`, UV
(0, 0) samples the **center** of texel (0, 0), not its corner.

So vertex (i, j) at world XZ `(origin + i*step, origin + j*step)`
should sample at UV `((i + 0.5) / N, (j + 0.5) / N)`, which equals
`(world - origin) / (extent * N/(N-1))` — NOT `(world - origin) / extent + 0.5`.

If the shader uses the naive `(world - origin) / extent`, sampling
lands half a texel off-grid. Adjacent rings sample the same world XZ
from different texture grids, with the offset error in different
directions, producing a height mismatch at the boundary.

### Fix
```glsl
float extent_n = ring_extent_m * float(n) / max(float(n) - 1.0, 1.0);
vec2 uv = (world_xz - ring_origin_m) / extent_n;
```

`extent_n` is "the world-XZ distance covered by N texels including
half a texel of padding at each edge" — exactly what
`filter_linear`'s sampling assumes.

### What this is NOT
Not a heightmap math bug. The kernel produces the right values; the
sampler is reading them at the wrong UV.

## Pitfall #9 — `inner_grid_n` rounded UP creates gap, not overlap

### Symptom
- Clipmap rings render with a thin dark band between every adjacent
  pair
- Bands scale with ring step (1m wide between rings 0 and 1, 2m
  between 1 and 2, etc)
- Visible in topdown view; partially hidden by skirts in walk view

### What's actually happening
Ring `i+1`'s hole (in meters) should cover *less* world XZ than ring
`i`'s outer extent. Otherwise there's a strip of world where ring
`i+1` has a hole AND ring `i` has ended — i.e. a real gap.

Math: ring `i`'s outer half-extent is `(N - 1) * step_i / 2`. Ring
`i+1`'s hole half-extent is `inner_grid_n * step_(i+1) / 2 = inner_grid_n * step_i`.

For overlap: `inner_grid_n * step_i ≤ (N - 1) * step_i / 2 → inner_grid_n ≤ (N - 1) / 2`.

For N = 64, the boundary is `inner_grid_n = 31.5`. The plan rounded UP
to 32, giving a half-step gap on each side. **Round DOWN** instead —
`((N - 1) / 2) & ~1` floors to the nearest even integer = 30 for N=64,
guaranteeing the hole is smaller than the inner ring's outer extent.

### Fix
```gdscript
ring.inner_grid_n = ((ring_grid_n - 1) / 2) & ~1
```

The trade-off is a thin overlap zone (z-fight pepper at boundaries),
which is the standard clipmap artifact addressable by a morph zone in
a future stage. **Overlap is the correct default**; the morph
smooths it; rounding UP is just wrong.

### What this is NOT
Not a camera-snap issue. Not a skirt issue. Pure clipmap geometry math.

## Pitfall #10 — `WorkerThreadPool` outlives its shared dependencies

### Symptom
- During scene shutdown (e.g. `HeadlessCapture` calling `quit()`),
  a flurry of "null instance" errors stream from a worker thread
  function
- The errors don't actually crash the scene; they appear AFTER the
  real work is done
- Visible only in logs; visual output is unaffected
- Will look like log spam in any shipping build

### What's actually happening
`WorkerThreadPool.add_task` enqueues tasks that may not start
immediately. When the scene tears down, the scene tree frees nodes
in some order — including the resource(s) the worker function reads
from (e.g. the kernel composer, the catalog dict).

If the worker function starts after the resource is freed, accessing
it throws "null instance" errors. The errors are harmless in the
sense that no data is corrupted (the result is discarded anyway),
but they pollute logs and can mask real errors.

### Fix
Two-layer defense:

1. **`_exit_tree` drains pending tasks**: before the scene frees the
   shared resource, wait for in-flight tasks to complete.
   ```gdscript
   func _exit_tree() -> void:
       for ring_idx_v in _ring_tasks.keys():
           var task: Dictionary = _ring_tasks[ring_idx_v]
           WorkerThreadPool.wait_for_task_completion(int(task["task_id"]))
       _ring_tasks.clear()
   ```

2. **Null-guard inside the worker function** (defense-in-depth in case
   a worker starts mid-shutdown):
   ```gdscript
   func _worker_compute(payload):
       if _shared_resource == null:
           return  # or return a zero-filled buffer
       # ... do work
   ```

### What this is NOT
Not a data corruption issue. The errors are noisy but harmless. Skipping
the fix means production logs will contain shutdown spam — annoying for
debugging real issues later.

## Pitfall #11 — Clipmap rendering without morph zones

### Symptom
- Visible elevation cliff / step at every ring boundary on a clipmap
  terrain renderer
- Cliff persists from any camera angle and any walking direction
- Cliff is stable (doesn't flicker) when the camera is still — it's
  a real geometric mismatch, not a timing bug
- More dramatic on outer rings (coarser grids alias the heightmap more)

### What's actually happening
Each clipmap ring stores its heightmap at its own grid resolution. Ring
0 at 2m grid captures fine kernel detail; ring 1 at 4m grid stores a
downsampled (effectively low-pass-filtered) version of the same world
heightfield. In the rings' overlap zone they sample the same world XZ
but their textures encode different values — ring 0 the fine truth,
ring 1 the blurred version.

The geometry has to be at *some* elevation, and the GPU's z-fight
arbitrarily picks one ring's fragment per pixel. Adjacent pixels can
land on different rings → visible step.

### Working fix
**Morph zones (geomorphing).** Each non-outermost ring's vertex shader
samples both this ring's heightmap AND the next coarser ring's, blends
them by a `[0..1]` factor that's 0 in the ring interior and ramps to 1
inside a thin band near the ring's outer edge:

```glsl
float h_inner = sample_height(world_xz);
float h_outer = sample_coarse_height(world_xz);
float m = compute_morph_factor(world_xz);
float h = mix(h_inner, h_outer, m);
```

At the precise boundary, `m = 1` → inner ring's vertices displace
using the outer ring's heightmap, which is exactly what the outer ring
shows. Heights converge → cliff disappears.

Per-fragment normals must morph identically so lighting matches the
morphed geometry.

The morph band is a quality-tier knob (`morph_band_fraction`); wider on
low tiers (more averaging acceptable on weak hw), narrower on ultra.

### What this is NOT
Not the same as PITFALLS #8 (half-texel UV offset) — that's a sampling
alignment issue. The morph cliff exists even with #8 fixed because the
two rings' heightmaps genuinely encode different values.

Not the same as PITFALLS #6 (per-tile splat boundaries) — that was
RGBA color discontinuity in the tile-paging renderer; this is height
geometry in the clipmap renderer.

### How to recognize it next time
If you build a clipmap-style renderer with per-ring heightmaps and you
see boundary cliffs even after fixing UV alignment and async-latency
issues — you need morph zones.

## Methodology lessons (not rules — just what costs the most time)

Things that consistently helped, captured from incident retros:

- **One change at a time** during visual debugging. We've burned hours
  multiple times changing 3-5 shader/scene/material params per
  iteration and being unable to bisect which one had effect.
- **Trust user editor screenshots as ground truth, not headless captures.**
  Headless OpenGL Compatibility doesn't reproduce some bugs that
  Forward+ Vulkan editor does. If a "fix" looks good in headless,
  verify in editor before declaring success.
- **Run `--headless --import` after editing any shader/texture/script**
  from outside Godot. Otherwise edits don't take effect — Godot caches
  imported resources and you'll convince yourself the edit didn't help
  when actually it was never picked up.
- **Read prior incident docs first.** Several sessions repeated bisects
  that were already documented. This doc is the index — start here when
  the symptom matches one of the four entries above.
- **Be willing to declare "this iteration fixed *one* bug" rather than
  chasing total cleanup in one pass.** Stacked bugs look like one bug.
  When the artifact gets noticeably smaller or less frequent, that's
  signal — investigate what changed before adjusting other knobs.
- **Claim discipline when overriding a prior conclusion.** Say *which
  specific claim* and *what the data showed*. "Doc X was wrong" loses
  information; "Doc X attributed the banding to source-DEM striation,
  but stencil-width tests showed adjacent-normal independence was the
  dominant mechanism" preserves it. Several entries in this doc are
  refinements of prior conclusions — that's healthy. The wording should
  make the refinement visible.

## What's NOT a rule

These pitfalls describe failure modes and the fixes that worked. They
do NOT say:

- Don't use lit shaders (#3 fix is unshaded, but anchor still uses lit
  fine — both have a place)
- Don't use ComfyUI textures with deep shadows (#1 fix is the luma
  floor, not avoiding textures)
- Always gaussian-smooth heightmaps (#2 fix is sigma=1, but for raw
  research a sigma=0 path should stay open)
- Always widen the normal stencil (#4 fix is `normal_stencil=8`, but
  for close-up detail rendering a stencil=1 might be wanted)

Tune to taste, but if you hit one of the four symptoms, the relevant
section is the place to start.
