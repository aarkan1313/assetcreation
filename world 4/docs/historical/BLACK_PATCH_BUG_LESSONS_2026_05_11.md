# Black-patch terrain artifacts — root causes + fixes

> **⚠️ HISTORICAL — see `PITFALLS.md` for the current canonical answer.**
> This doc captures the original bisect session that identified TWO
> stacked bugs (moving = scan-line noise, stationary = PBR pipeline at
> scale). Both are now consolidated as **Pitfall #2 (scan-line noise)**
> and **Pitfall #3 (PBR pipeline)** in [`PITFALLS.md`](PITFALLS.md). Read
> that first.
>
> Kept on disk because the diagnostic methodology + what-was-eliminated
> sections are still valuable raw material.

> Captured 2026-05-11 after a long bisect on scale_demo. Permanent
> record of the actual ~90-minute diagnosis path.

## TL;DR

**Two stacked, independent bugs cause black patches on heightmap terrain
at scale.** They look similar but have different fixes.

| Bug | Symptom | Root cause | Fix |
|---|---|---|---|
| 1 — Moving | Stripes/dots that shift as the player moves | LiDAR scan-line noise in source DEM, amplified by lambertian shading | Gaussian smooth the heightmap before slicing |
| 2 — Stationary | Pure-black mesh quads, fixed in world space | Godot's PBR pipeline does something to fragments on this mesh that goes to black under lighting — even with minimal shader, no sun, uniform ambient. Root cause not fully isolated. | Use an `unshaded` shader and do lambertian + ambient in shader math |

The anchor demo *also* has bug #2 latent, but its crop has a relief +
slope distribution where the artifact lands below visibility threshold.
Scale_demo's larger world (1024m, 522m relief, more slope orientations)
makes both bugs unmissable.

## Bug 1 — moving with player ("LiDAR scan-line bug")

### Symptom
- Dark/light bands aligned diagonally across slopes
- Pattern **shifts when the player walks**, stays stable when only camera rotates
- Banding direction matches the source DEM's scan-line flight direction
- Worse on flatter/gentler slope regions of a DEM (where the real signal is small relative to scan-line noise)
- Invisible on steep, chaotic real-terrain regions (real features dominate)

### Diagnostic test that pins it
Open the source heightmap in Python, compute a slope-magnitude image:

```python
import numpy as np
from PIL import Image
src = np.asarray(Image.open(path), dtype=np.int32).astype(np.float32)
slope_mag = np.sqrt(np.gradient(src, axis=0)**2 + np.gradient(src, axis=1)**2)
norm = (255 * slope_mag / slope_mag.max()).clip(0, 255).astype(np.uint8)
Image.fromarray(norm).save("slope_mag.png")
```

If `slope_mag.png` shows **parallel diagonal fishbone striping**, that's
LiDAR scan-line noise. If it shows organic dendritic patterns matching
real drainage networks, the DEM is clean and the bug is elsewhere.

### Fix
Apply a small gaussian blur to the heightmap **before slicing into tiles**.
`scipy.ndimage.gaussian_filter(arr, sigma=1.0, mode="nearest")` is enough
to suppress per-pixel noise while preserving real features down to ~2-3m
scale. Bump sigma up to 2.0 if striping persists.

In W4 this is wired into `pipeline/slice_to_tiles.py` as `SMOOTH_SIGMA_PX = 1.0`.
For raw research that prefers fidelity over visual cleanness, set to 0.

### Why this isn't the same as bug 2
Smoothing alone removes the moving-banding artifact. Stationary
black patches remain. They're independent.

## Bug 2 — stationary black mesh quads ("PBR pipeline bug")

### Symptom
- **Pure-black** mesh quads (not dim, not back-faces, fully zeroed RGB)
- **Stair-step or rectangular patterns** aligned with the heightmap pixel grid
- **Fixed in world space** — don't move when player walks, don't move when camera rotates
- Appears under **any lit shader**, even a 3-line minimal shader
- Disappears entirely under **unshaded** render_mode
- Disappears with `StandardMaterial3D` ← actually, untested cleanly in this session

### What we eliminated as the cause

Listed so future bisects don't waste time on these:

- Directional sun (set `light_energy = 0`: artifact stays)
- Shadows (already `shadow_enabled = false`)
- Ambient sky-direction sampling (set `ambient_light_sky_contribution = 0`: artifact stays)
- Custom PBR uniforms — AO/ROUGHNESS/SPECULAR/METALLIC writes explicitly set to defaults: artifact stays
- Vertex normals — debug visualization (`ALBEDO = world_normal * 0.5 + 0.5`) showed clean smoothly-varying normal colors, no NaN/black
- Mesh tangents — removing `SurfaceTool.generate_tangents()`: artifact stays
- v2 shader math (luma_floor, slope blending, normal blending) — minimal 3-line shader shows the same artifact
- LiDAR noise (this is bug 1, fixed separately)

### What does fix it

- `render_mode unshaded` on the shader
- Manual lambertian + ambient math written in the shader using `MODEL_MATRIX × NORMAL` and uniforms (no Godot light source reads, no PBR pipeline)

The fix is structural: **bypass Godot's PBR pipeline entirely** for
heightmap terrain at this world scale.

### Why this matters across the project

- Anchor (256m world, 232m relief) **also has this bug latent** but the
  artifact lands in regions/orientations where `luma_floor = 0.08`
  clamps it below visibility. The fix that "worked" for anchor (the
  luma floor + ao floor + tangent regeneration) is a bandage; the
  artifact returns at any scale where slopes get steeper or world UVs
  reach a wider range.
- For W4, the canonical terrain shader going forward should be `unshaded`
  with manual lighting math. `terrain_scale_v1.gdshader` is the first
  such shader.
- The anchor's `terrain_anchor_v2.gdshader` is **kept as-is** because
  the anchor demo is locked as the regression baseline. Anchor doesn't
  need this fix today. It will if we ever swap its crop for one with
  different slope distribution.

### Open question (not blocking)
Why does the Godot PBR pipeline produce pure black on these
specific fragments? Theories that survived testing but weren't
conclusively confirmed:
- Tangent-space transform on edge fragments where adjacent vertices
  have very different normal magnitudes (despite tangent regen)
- A Forward+ specific feature (reflection cubemap sample? GI?) that
  goes degenerate at large world coordinates × steep normals
- Specular pipeline producing negative output that clamps to black

If we ever need real-time lighting on terrain (dynamic time-of-day,
moving lights), this needs to be resolved. Until then, manual lighting
in the shader is the right choice for terrain — it's also faster and
gives us direct control over the visual.

## How to recognize this bug class quickly (decision tree)

```
Black patches on terrain?
├── Do they move when player walks (not camera)?
│   ├── YES → Bug 1 (LiDAR noise). Run the slope_mag.py diagnostic.
│   │        Fix: bump SMOOTH_SIGMA_PX in slice_to_tiles.py.
│   └── NO (stationary in world space) → Bug 2 (PBR pipeline).
│       ├── Quick test: change shader render_mode to `unshaded`.
│       │  ├── If patches GONE → confirmed bug 2.
│       │  │  Fix: use scale_v1-style unshaded shader with manual lighting.
│       │  └── If patches STILL THERE → something else, follow the audit
│       │     doc's Option F (minimal shader) and bisect.
```

## Methodology lessons (what cost the most time this session)

- **Don't keep adjusting parameters when the audit doc explicitly told
  you to read it first.** I burned 30 minutes guessing at sun/ambient/
  tangents before reading `AUDIT_HANDOFF_BLACK_ARTIFACTS_2026_05_11.md`.
  Always read prior incident docs first.
- **Headless captures don't reproduce bug 2.** The bug is in Godot's
  Forward+ Vulkan PBR pipeline; headless OpenGL Compatibility doesn't
  hit the same code path. Editor screenshots from the user are the
  only ground truth.
- **Two stacked bugs look like one bug.** Be willing to declare "this
  iteration fixed *one* of them" rather than chasing total cleanup in
  one pass. After bug 1 fix the patches dropped from ~50% screen area
  to ~15% screen area but I almost missed that change because I was
  looking for total cleanup.
- **Bisect with strict one-change-per-iteration.** This was the
  consistent advice in the audit doc and we landed on the answer
  fastest when we followed it strictly (lit minimal → unshaded minimal,
  one knob).

## Files involved in the fix

- `pipeline/slice_to_tiles.py` — gaussian smoothing pass (bug 1 fix)
- `shaders/terrain_scale_v1.gdshader` — unshaded shader with manual
  lighting (bug 2 fix)
- `pipeline/write_material_tres_scale_v1.py` — emits material bound to
  the new shader
- `worlds/scale_demo/material_scale_v1.tres` — built artifact
- `scenes/scale_demo.tscn` — points at material_scale_v1.tres via
  `ScaleWorld.material_override_path`

## Diagnostic artifacts kept on disk

- `worlds/scale_demo/material_minimal.tres` — 3-line shader test material
- `worlds/scale_demo/material_standard.tres` — Godot StandardMaterial3D
  test material
- `shaders/terrain_anchor_v2_minimal.gdshader` — used as the bisect
  vehicle, kept for future debugging

Don't delete these. Next time the bug shows up at a new scale or with a
new texture set, swapping `ScaleWorld.material_override_path` to one of
these is the cheapest first diagnostic.
