# W4 Orchestrator Guide

> How to actually run the W4 anchor pipeline end-to-end. Where files
> live, which commands to run, what each step does, common failure
> modes. The TL;DR version is at the bottom.

## Directory layout

```
D:\assets\world 4\
├── docs\                         ← all human-readable docs (this folder)
│   ├── ANCHOR.md                 ← what the anchor IS (target spec)
│   ├── ANCHOR_BUILD_NOTES.md     ← what we ACTUALLY built + lessons learned
│   ├── AXES.md                   ← 6 axes of expansion + principles
│   ├── WISHLIST.md               ← parked ideas
│   ├── ORCHESTRATOR_GUIDE.md     ← this doc
│   └── AUDIT_HANDOFF_BLACK_ARTIFACTS_2026_05_11.md
│                                 ← full diagnostic history of the
│                                   black-speckle bug (now resolved)
│
├── pipeline\                     ← Python build scripts (NOT in Godot)
│   ├── pick_dem_crop.py          ← stage 1: crop DEM → heightmap
│   ├── build_splat_and_macro.py  ← stage 2 (v1, legacy): splat + macro
│   ├── build_anchor.py           ← orchestrator: runs all stages in order
│   ├── write_material_tres.py    ← stage 3 (v1, legacy): emit material.tres
│   ├── write_material_tres_v2.py ← stage 3 (v2, CURRENT): emit material.tres
│   └── fix_texture_imports.py    ← utility: patch .import settings
│
└── the world 4\                  ← the Godot 4.5 project
    ├── project.godot
    ├── shaders\
    │   ├── terrain_anchor.gdshader      ← v1 (legacy, 5-slot splat+macro)
    │   ├── terrain_anchor_v2.gdshader   ← v2 (current, 3-slot slope-blend)
    │   └── water_anchor.gdshader        ← water surface shader
    ├── scripts\
    │   ├── AnchorTerrain.gd      ← builds mesh, applies material
    │   ├── AnchorWater.gd        ← spawns water plane sized to underwater region
    │   ├── AnchorCameraRig.gd    ← 3-camera rig + hotkey switching
    │   └── HeadlessCapture.gd    ← snapshot helper for headless captures
    ├── scenes\
    │   ├── anchor.tscn           ← main runnable scene
    │   ├── capture_anchor_walk.tscn
    │   ├── capture_anchor_iso.tscn
    │   └── capture_anchor_topdown.tscn
    ├── materials\anchor_v2\      ← 3 PBR sets (current v2 textures)
    │   ├── scrub_dense\
    │   ├── tundra_lichen\
    │   └── rocky_slope\
    ├── worlds\anchor\            ← built artifacts (output)
    │   ├── heightmap.png         (16-bit, 256×256)
    │   ├── meta.json
    │   ├── material.tres
    │   └── layers\               (v1 leftovers: splat, macro, debug)
    └── captures\                 ← headless capture output
```

## v1 vs v2 — which to use

We pivoted shader approaches mid-session. Both versions are still on
disk; **v2 is current.**

| | v1 (legacy, kept for reference) | v2 (current) |
|---|---|---|
| Shader | `terrain_anchor.gdshader` (5-slot + macro + procedural splat) | `terrain_anchor_v2.gdshader` (3-slot slope-blend, no macro) |
| Materials | 5 W3 `temperate_forest_*` kit textures | 3 textures: 2 real-ortho + 1 ComfyUI |
| .tres writer | `pipeline/write_material_tres.py` | `pipeline/write_material_tres_v2.py` |
| Splat texture | Yes (`build_splat_and_macro.py`) | No (slope computed in shader) |
| Macro texture | Yes (procedural composite) | No |
| Status | Smeared, dead-end | Working mockup-quality |

**Always use v2 unless explicitly running the legacy comparison.**

## The pipeline, step by step

### Stage 1: DEM crop → heightmap

```
"C:/Program Files/Python312/python.exe" "D:/assets/world 4/pipeline/pick_dem_crop.py"
```

Reads the pinned DEM tile from `D:\assets\dems\` (currently
`USGS1m_-78.3520_+38.5147_-78.1980_+38.6500.tif` — Blue Ridge VA),
scans for the highest-relief 256×256m subregion, crops it, writes:
- `worlds/anchor/heightmap.png` (16-bit grayscale, 256×256px)
- `worlds/anchor/meta.json` (elev range + source provenance)

To use a different DEM, edit `SOURCE_TILE` near the top of the script.
The cache holds 659 DEMs across multiple datasets — see
`world3/data_catalog.json` for the index.

**Runs in:** system Python 3.12 (uses `rasterio`).

### Stage 2 (v2): texture material binding

```
"C:/Program Files/Python312/python.exe" "D:/assets/world 4/pipeline/write_material_tres_v2.py"
```

No need to run anything between stage 1 and stage 2 in v2 (the v1
`build_splat_and_macro.py` step is gone — slope-blending happens in the
shader at runtime, not pre-baked).

Reads the 3 PBR sets from `materials/anchor_v2/`, writes:
- `worlds/anchor/material.tres` — Godot ShaderMaterial binding 3 slots
  × 4 maps + shader uniform defaults

To change the texture mix, edit the `SLOT_MATERIALS` dict at the top
of the script. Each slot needs a corresponding folder in
`materials/anchor_v2/<material_name>/` with `albedo.png`, `normal.png`,
`roughness.png`, `ao.png`.

**Runs in:** system Python (no special deps).

### Stage 3: Godot reimport + scene render

```
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import
```

Godot caches imported resources. After any change to a texture, .import
file, or shader, run `--import` so Godot regenerates its `.ctex`
compressed-texture cache and `.gdshader` compiled bytecode. **Skipping
this is the #1 reason "nothing is changing in the editor."**

Then either open the editor or capture headless:

```
# Open the Godot editor
"C:/Godot/Godot_v4.5-stable_win64.exe" --path "D:/assets/world 4/the world 4"

# Headless capture (walk view)
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_anchor_walk.tscn"
```

## In-editor controls (anchor scene)

| Key | Action |
|---|---|
| 1 | 3D walk camera |
| 2 | 2.5D iso camera |
| 3 | 2D topdown camera |
| WASD | Move (walk mode only) |
| Mouse | Look (walk mode only, mouse-captured) |
| Shift | Sprint (4×) |
| Esc | Release mouse |
| F | Re-capture mouse |

## When to run what (cheat sheet)

| Scenario | Run |
|---|---|
| Fresh clone / first run | `build_anchor.py` (orchestrator) → `--import` → open editor |
| Changed texture pixels | `--import` → editor |
| Changed `.import` settings | `--import` → editor |
| Changed shader code | `--import` → editor (or right-click shader in Godot FileSystem → Reimport) |
| Changed GDScript | Reopen the scene in editor (scripts are hot-reloaded by editor but not by running game) |
| Changed `write_material_tres_v2.py` outputs | Run the script → `--import` → editor |
| Changed DEM crop | Run `pick_dem_crop.py` → `--import` → editor |
| Changed slot material assignments | Edit `SLOT_MATERIALS` in `write_material_tres_v2.py`, run it → `--import` → editor |

## Common failure modes

### "I changed the shader/script but nothing happens in editor"
Godot caches imports. **Run `--headless --import` before reopening.**
Or right-click the file in Godot's FileSystem panel and pick "Reimport."

### "Headless capture is fine but the editor shows artifacts"
Headless (`opengl3` Compatibility renderer) and editor (Forward+ Vulkan)
have different render paths. **Always trust user editor screenshots
over headless captures.** Headless can hide problems that the live
renderer shows (and vice versa, rarely). See
`AUDIT_HANDOFF_BLACK_ARTIFACTS_2026_05_11.md` for the canonical example
where this burned 5 hours.

### "Black speckles all over the terrain"
See the lesson in `ANCHOR_BUILD_NOTES.md` (top section). The shader v2
has guardrails (`luma_floor`, `ao_floor`, NaN guards, tangents) that
prevent it. If you add new textures and see speckles again:
1. Don't tune shader params first. Check if the new texture has near-
   black texels in its albedo or AO. Most likely cause.
2. Confirm shader still has guardrails intact.
3. Confirm `SurfaceTool.generate_tangents()` is still being called in
   `AnchorTerrain.gd:_build_mesh()`.

### "Water plane renders as a black slab"
Water shader requires depth_draw_always + the plane needs
`cast_shadow = OFF` (set in `AnchorWater.gd`). If you see a flat
black rectangle: the plane is rendering but the shader is drawing
near-black due to fresnel-at-grazing-angle. Increase `fresnel_floor` in
the water shader uniforms.

### "Macro UV seam down the middle of topdown view"
Already fixed in v2 shader. If it returns: the shader's macro_uv math
needs the `+ 0.5` shift to account for the mesh being centered on
origin. See `terrain_anchor_v2.gdshader` for the working version.

## Adding new things to the anchor

**This is high-stakes. Follow the rule from `ANCHOR_BUILD_NOTES.md`:**

1. **One slot/map at a time.** Never bring in 3 new textures
   simultaneously and try to debug a stacked failure.
2. **Validate every new albedo + AO map** for near-black islands before
   binding. Use the python helper:
   ```
   python -c "import numpy as np; from PIL import Image;
   a = np.asarray(Image.open('PATH/albedo.png').convert('RGB'), dtype=np.float32) / 255;
   l = 0.2126*a[...,0] + 0.7152*a[...,1] + 0.0722*a[...,2];
   print('min:', l.min(), 'p5:', np.percentile(l, 5), 'mean:', l.mean())"
   ```
   Anything below 0.05 luminance in `p5` will speckle without the luma
   floor. Anything below 0.05 in min just needs the luma floor active.
3. **Keep the safety floors active.** `albedo_luma_floor`, `ao_floor`,
   the NaN guards on weights, the mesh tangent generation. These are
   non-optional.
4. **Start `normal_strength` low** (≤ 0.25). Increase only after
   everything else looks right.
5. **Capture walk + iso + topdown after every change.** Compare against
   the previous capture. Don't batch changes.
6. **Live editor view is the truth, not headless captures.**

## TL;DR — the three commands

```
# Build everything from scratch (DEM crop + material.tres):
"C:/Program Files/Python312/python.exe" "D:/assets/world 4/pipeline/pick_dem_crop.py"
"C:/Program Files/Python312/python.exe" "D:/assets/world 4/pipeline/write_material_tres_v2.py"

# Refresh Godot's import cache:
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import

# Open it:
"C:/Godot/Godot_v4.5-stable_win64.exe" --path "D:/assets/world 4/the world 4"
# Then double-click scenes/anchor.tscn in the editor and hit F6
```

That's the entire pipeline.
