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
