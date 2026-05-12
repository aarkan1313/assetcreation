# Terracing on rendered terrain — root cause + diagnostic

> **⚠️ HISTORICAL — INCOMPLETE.** The diagnostic in this doc (hillshade
> visualization of the source DEM) is valid and pointed at a real
> directional bias in the data. But that bias *wasn't the dominant
> cause* of the rendered fingerprint banding. See
> [`PITFALLS.md`](PITFALLS.md) Pitfall #4 for the actual mechanism
> (adjacent-vertex normal correlation at narrow stencil widths) and
> the working fix (widen `TileTerrain.normal_stencil` from 1 to 8).
>
> Kept on disk because the diagnostic process is still useful, and the
> source-DEM angle isn't ruled out — it's just not load-bearing for the
> Blue Ridge crop currently in use. For a future DEM with strong
> geological grain (coastal cliffs, fault scarps), the hillshade
> diagnostic + FFT anisotropy penalty here would still be the right
> first move.

## What this doc claimed vs what the data showed

This doc claimed: if rendered terrain shows discrete stair-step
elevation bands, the source DEM is "fundamentally striated" and you
should re-crop.

The data refinement (run in a later session): per-meter slope delta
on the Blue Ridge crop is 0.37m and *constant across stencil widths
1, 2, 4, 8, 16*. That means the terrain isn't "noise on top of a
smooth surface" — it's rough at every measured scale. Widening the
stencil doesn't smooth the surface; it correlates adjacent vertex
normals. The fingerprint bands were adjacent-normal independence at
stencil=1, not directional bias in the DEM.

The source-DEM hillshade DOES show some directional bias. It's just
not the dominant signal. See `captures/diag_hillshade_stencil{1,4,8}.png`
for a direct comparison.

## Original content (read with skepticism)

USGS1m LiDAR products sometimes have **contour-parallel ridging baked
into the elevation values** — possibly real geology, possibly a previous
processing pass that incorporated hillshade-style lighting back into
the elevation field. Either way, the elevation data is genuinely
striated, and no amount of gaussian smoothing fixes it without erasing
real terrain.

**Fix at the source: pick a different crop region.** The crop scorer
now penalizes directional anisotropy via an FFT angular-power-bin
histogram (see `pipeline/pick_dem_crop_scale.py:directional_anisotropy`).

## How to recognize this bug

1. Open the source heightmap in Python, generate a hillshade
   visualization:

   ```python
   import numpy as np
   from PIL import Image
   arr = np.asarray(Image.open(path), dtype=np.int32).astype(np.float32)
   arr_m = arr / 65535.0 * elev_range_m
   dz_dx = np.gradient(arr_m, axis=1)
   dz_dy = np.gradient(arr_m, axis=0)
   slope = np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))
   aspect = np.arctan2(dz_dy, -dz_dx)
   altitude = np.radians(45); azimuth = np.radians(315)
   shaded = (np.sin(altitude) * np.cos(slope)
             + np.cos(altitude) * np.sin(slope) * np.cos(azimuth - aspect))
   Image.fromarray((255 * shaded.clip(0,1)).astype(np.uint8)).save("hill.png")
   ```

2. Look at `hill.png`. If it shows **clearly visible parallel ridges
   running in a consistent direction across the area**, the DEM has
   baked-in striation. Compare to a known-clean reference (the W4 anchor
   crop) — anchor hillshade shows organic dendritic drainage, no
   directional pattern.

## What does NOT fix this

These were tried during the bisect:

- Bilinear height sampling — vertices still land at exact pixel
  positions when mesh density is a clean multiple of heightmap density
- 2× upsampling the heightmap — same problem; mesh still skips to
  every-other-pixel
- Denser mesh (`resolution_m = 0.5`) — engages bilinear but makes
  micro-stripes from the source data more visible, not less
- More aggressive gaussian smoothing (sigma=3) — partially blurs the
  ridges but visibly destroys real features at the same time
- Different shader (lit v2, unshaded scale_v1, Godot StandardMaterial3D)
  — terracing is geometric, lives in the mesh

## What DOES fix this

- Picking a 1024m crop that lands in a region without baked striation
- The FFT anisotropy penalty (`RIDGE_PENALTY_WEIGHT` in
  `pipeline/pick_dem_crop_scale.py`) does this automatically

## Why the anchor doesn't have this bug

Pure luck. The anchor's chosen 256m crop happens to sit in a clean
region of the Blue Ridge tile. The anchor's scorer didn't include the
anisotropy penalty — it didn't need it because all 256m subregions of
the tile that are high-relief enough to be picked happened to be free
of striation.

The 1024m scale_demo crop was a much bigger window and caught a striated
region. Going forward, both crop scorers (anchor + scale) should use
the anisotropy penalty so the choice is robust regardless of crop size.

## Caveat: anisotropy penalty is not free

Penalizing directional ridging will reject some *legitimately* steep
mountain ridges that look directional in hillshade (e.g. a long
straight cliff face). For the Blue Ridge tile this is fine — there's
plenty of varied terrain. For tiles where the entire mountain range
runs in one direction (e.g. parts of the Rockies, the spine of the
Andes), you may need to disable or weaken the penalty.

Trade the `RIDGE_PENALTY_WEIGHT` against `RELIEF_WEIGHT` to taste.

## Decision tree (combined with black-patch bug)

```
Heightmap terrain looks wrong?
├── Pure black mesh quads, stationary, stair-step pattern?
│   → BLACK_PATCH_BUG_LESSONS doc, bug 2 (PBR pipeline). Fix: unshaded shader.
├── Dark stripes that shift when player walks (camera-stable)?
│   → BLACK_PATCH_BUG_LESSONS doc, bug 1 (LiDAR scan-line noise). Fix: sigma>=1 gaussian.
└── Discrete elevation steps aligned with world axes, look like stairs?
    → THIS DOC. Run hillshade diagnostic.
    │  If hillshade shows directional ridges → bad crop. Re-pick.
    └  If hillshade is clean → revisit one of the other docs.
```

## Files involved

- `pipeline/pick_dem_crop_scale.py` — has `directional_anisotropy()` + `RIDGE_PENALTY_WEIGHT`
- `captures/scale_hillshade.png` / `captures/anchor_hillshade.png` — diagnostic
  artifacts from this session, kept for reference
