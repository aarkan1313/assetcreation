# AUDIT HANDOFF — Black artifact rendering bug in W4 anchor

> **⚠️ HISTORICAL — see `PITFALLS.md` for the current canonical answer.**
> This doc captures the original "stuck" state and diagnostic ladder
> from the session that hit the speckle bug for the first time. The
> resolution (source-texture black texels + luma_floor + AO_floor +
> tangents) is now consolidated as **Pitfall #1** in
> [`PITFALLS.md`](PITFALLS.md). Read that first.
>
> Kept on disk for diagnostic history and the post-mortem at the bottom.

> **Status (when written): STUCK.** Multiple hours and ~6 distinct
> diagnostic attempts had failed to identify or fix the root cause.
> The original agent kept guessing at single causes, applying fixes
> that didn't work or made things worse. Saved for posterity so the
> failure modes are visible.

## What I need from you (the auditor)

1. Read this entire doc before touching code.
2. Form a hypothesis from the symptom evidence + diagnostic logs, NOT
   from my failed guesses.
3. Verify the hypothesis with a single targeted test before applying any
   shader/texture/scene changes.
4. The bug is genuinely puzzling — please don't dismiss it as obvious.

## The symptom

The W4 anchor demo scene (`D:\assets\world 4\the world 4\scenes\anchor.tscn`)
renders mostly-correct terrain BUT contains black pixel artifacts that:

- **Move/shift as the camera moves.** Not static. Reposition the camera
  and the pattern of black pixels rearranges itself.
- **Appear in semi-regular geometric patterns**: hexagonal speckles,
  square clusters, contour-aligned stripes, "stairs"-like orthogonal
  blocks. Different camera angles produce different pattern types.
- **Are pure black** — alpha-correct, not transparent, not partial darkening.
- **Only manifest in live editor view**, NOT in headless `--rendering-driver
  opengl3` captures. The headless captures (used by my fix-validation
  loop) always look fine, hiding the bug from me until the user screenshots.
- **Persist across multiple shader/import/scene changes** — what changes
  is the *shape* and *density* of the artifacts, not whether they
  appear.

Screenshots showing the artifacts:
- See `D:\assets\world 4\` for any screenshots the user attached
- The artifacts are unmistakable: pure black pixels in geometric patterns
  overlaid on otherwise-fine terrain texture

## What I already verified is NOT the cause

I tested these systematically. Each was wrong:

### 1. Self-shadowing on the terrain mesh
**Hypothesis:** Terrain mesh cast_shadow=ON causes mesh to shadow its
own crevices, producing dark pattern.
**Test:** Set `_mesh_instance.cast_shadow = SHADOW_CASTING_SETTING_OFF`
in `AnchorTerrain.gd:42`.
**Result:** Artifacts unchanged.
**Verdict:** Not the cause. (Setting left in place — it's still good
hygiene for a terrain mesh.)

### 2. NaN/Inf in shader math
**Hypothesis:** Division by near-zero `total` in slope-weight normalize,
or `normalize()` on zero-vector blended normal, produces NaN that Godot
renders as black.
**Test:** Added `max(total, 1e-4)` guard; removed manual `normalize()`
on blended normal; added final `clamp(albedo, 0, 1)` and `clamp(NORMAL_MAP,
0, 1)`.
**Result:** Artifacts unchanged.
**Verdict:** Not the cause. (Guards left in place — also good hygiene.)

### 3. Missing mesh tangents
**Hypothesis:** `ArrayMesh.add_surface_from_arrays` doesn't auto-generate
`ARRAY_TANGENT`. Without tangents, normal-mapping math reads garbage.
**Test:** Wrapped mesh build in SurfaceTool, called `generate_tangents()`,
committed to new ArrayMesh. See `AnchorTerrain.gd:_build_mesh()` last
block.
**Result:** **Partial improvement.** Original hex+square+spike artifacts
became less severe. Some moving-stripes artifact remained.
**Verdict:** Tangents were missing AND missing tangents WAS a contributing
bug, but didn't fully fix the rendering.

### 4. Texture .import file settings
**Hypothesis:** Normal maps imported with `compress/normal_map=0` (Detect)
and `compress/mode=0` (Lossless) produce wrong mipmaps, causing moving
black pixels at grazing angles.
**Test:** Changed all 12 texture .import files (3 materials × 4 maps) to
match W3's working settings:
- `compress/mode=2` (VRAM Compressed)
- `compress/normal_map=2` on normal maps, `=1` on color/PBR
- `detect_3d/compress_to=0` on normal maps, `=1` on others

Reimported via `--headless --import`.
**Result:** **MADE IT WORSE.** The albedo decoded to olive-yellow
(wrong channel order on VRAM compression). Black artifacts still
present, just on a yellow background instead of normal colors.
**Verdict:** Not the cause. The patch was REVERTED — see
`pipeline/fix_texture_imports.py` (now contains the revert).

### 5. Backface culling
**Hypothesis:** `cull_back` in shader's render_mode causes triangles on
steep slopes to be culled when their normals end up slightly facing away.
**Test:** Changed to `cull_disabled`.
**Result:** User reported no change before I could verify.
**Verdict:** Probably not the cause. Reverted to `cull_back`.

## What I observed but couldn't explain

- **The artifact pattern moves with the camera, not with the world.**
  Walk forward → pattern shifts. Look left/right → pattern shifts.
  This pattern of behavior is consistent with:
  - **Anisotropic filtering / mipmap selection issues**
  - **Specular highlight aliasing on grazing-angle surfaces**
  - **View-dependent NaN propagation in a screen-space pass (SSAO/SSR/SSIL)**
- **Headless captures (low resolution, opengl3 compatibility renderer) don't
  reproduce the bug.** Native editor view at ~2548×1473 always does.
  This suggests the bug is sensitive to either:
  - **Higher mip levels** (high-res view samples lower-mip detail)
  - **The Forward+ renderer** (editor default) vs Compatibility (headless)
  - **Pixel-level precision** (low-res averages over the problem)
- **The user reports "the textures are there, they just turn black"** —
  i.e., the texture isn't geometrically missing, it's the SHADED COLOR
  output that's going to black. Suggests issue is in shading math, not
  geometry/visibility.
- **Pattern shape variation across attempts:**
  - Before tangent fix: hexagons + squares + spike shapes
  - After tangent fix: contour-aligned stripes + smaller squares
  - After import patch + revert: persistent smaller artifacts in clusters
  Suggests at least 2 bugs may be stacked, partial fixes uncovering deeper layers.

## Critical files to audit (read in this order)

| File | Why audit |
|------|-----------|
| `D:\assets\world 4\the world 4\shaders\terrain_anchor_v2.gdshader` | The active terrain shader. 3-slot slope-blended PBR. Last touched: tangent fix attempt, normalize removal. |
| `D:\assets\world 4\the world 4\scripts\AnchorTerrain.gd` | Mesh builder. Builds heightmap-based ArrayMesh, NOW uses SurfaceTool.generate_tangents(). |
| `D:\assets\world 4\the world 4\worlds\anchor\material.tres` | Material binding. Bound texture paths + uniform values. |
| `D:\assets\world 4\the world 4\scenes\anchor.tscn` | Scene root. Environment, sun, water plane, camera rig. |
| `D:\assets\world 4\the world 4\materials\anchor_v2\*\*.png.import` | Texture import settings (currently at Godot defaults after my revert). |
| `D:\assets\world 4\the world 4\project.godot` | Project settings — renderer, default texture filter. |

## Known-good comparison

W3 had a similar 5-slot terrain shader (`world3/shaders/terrain_splat_unified.gdshader`)
that rendered FINE in the same Godot 4.5 build, in the same operator
workflow, with the same kind of input data. The W4 shader is structurally
SIMPLER than W3's. If W3 worked, mine should too — unless I'm missing
something W3 did that I didn't replicate.

The user has the W3 project still intact at `D:\assets\world3\` for direct comparison.

**Specifically W3-versus-W4 deltas to investigate:**

1. **Shader macro-UV setup.** W3 uses `use_source_macro_world_uv` and a
   `source_world_size_m` Vector2. W4 has neither — I built a simpler
   shader without the macro path. Could the macro path implicitly
   provide UV clamping that prevents the broken-mipmap edge cases?
2. **Mesh chunking.** W3 builds many smaller chunks via ChunkLoader.gd
   (each its own MeshInstance3D). W4 builds ONE big 256×256 mesh.
   Could the all-in-one mesh be hitting precision issues at extreme
   vert-distance-from-origin?
3. **Render mode flags.** W3 uses `cull_back, depth_draw_opaque,
   specular_schlick_ggx`. W4 same. Match.
4. **Tangents.** W3's ChunkLoader.gd ALSO does manual `add_surface_from_arrays`
   without tangents (verify by searching!) — yet W3 works. Maybe Godot
   auto-generates tangents in some path I'm not aware of, OR W3 isn't
   actually rendering normals at all and that's why it works.

## What to try (in priority order)

### A. Diff shader output between Forward+ and Compatibility renderers

Run anchor.tscn under both renderers and compare:
```
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver vulkan --path "..." anchor.tscn
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "..." anchor.tscn
```
If artifacts appear under Vulkan/Forward+ but not OpenGL/Compatibility,
the bug is renderer-specific (probably mipmap or SSAO).

### B. Disable shadows entirely on the DirectionalLight

In anchor.tscn, set `shadow_enabled = false` on the Sun node. If
artifacts vanish: shadow-acne / depth-bias / cascade-transition issue.

### C. Disable the water plane entirely

Comment out the Water node in anchor.tscn (it has cast_shadow=OFF already
but maybe it's still doing something weird at runtime). If artifacts
vanish: water plane interacting with terrain.

### D. Replace the shader with `BaseMaterial3D` (Godot's standard PBR)

Create a new StandardMaterial3D with one of the W4 anchor_v2 textures
bound as albedo, normal_texture, roughness_texture, ao_texture. Assign
it to the terrain mesh in place of the shader material. If artifacts
vanish under BaseMaterial3D: bug is in my shader code.
If artifacts persist under BaseMaterial3D: bug is in the mesh or scene.

### E. Test with a flat PlaneMesh instead of the heightmap mesh

Build a 256×256m flat PlaneMesh, apply the same material, drop it in
the scene. If artifacts vanish on the plane: bug is in mesh tangent/
normal generation. If artifacts persist on the plane: bug is in the
shader or material.

### F. Test with simpler shader

Strip terrain_anchor_v2.gdshader down to just:
```
ALBEDO = texture(ground_albedo, v_world_pos.xz * 0.04).rgb;
```
No normals, no blending, no AO. If artifacts vanish: bug is in normal-
blending or AO math. If artifacts persist: bug is somewhere else
entirely (mesh, scene, viewport).

### G. Inspect the actual texture pixels at the artifact locations

Use Godot's debugger to inspect the rendered pixel at a black-artifact
location. Get the world-space UV, manually sample the texture at that
UV in code, see if the sampled value is genuinely black or if shading
is producing black from valid input.

## Current state of the codebase

After 5+ failed attempts:

- `shaders/terrain_anchor_v2.gdshader` has NaN guards + clamps + no
  normalize. `cull_back`. `render_mode cull_back, depth_draw_opaque,
  specular_schlick_ggx`.
- `scripts/AnchorTerrain.gd` builds mesh, wraps in SurfaceTool, calls
  `generate_tangents()`. Mesh `cast_shadow = OFF`.
- `materials/anchor_v2/{scrub_dense,tundra_lichen,rocky_slope}/*.png` —
  textures copied from W3, .import files at Godot defaults (just reverted
  the failed VRAM-compression patch).
- `worlds/anchor/material.tres` — 3-slot binding to those textures.
- `scenes/anchor.tscn` — uses procedural sky, single DirectionalLight,
  shadow_enabled=true, water plane sized to actual water region.

Nothing is "in a broken intermediate state" — every component is at a
last-known coherent configuration. The bug is in steady-state, not from
recent edits.

## Why I (previous agent) failed

For posterity / so the next agent doesn't repeat the mistakes:

1. **I trusted headless captures over editor screenshots.** Repeatedly
   declared "fixed" based on captures while the user's editor view still
   showed the bug. Should have asked for editor screenshots earlier.
2. **I changed multiple parameters per iteration.** Cycling shader
   params + scene env + material settings at once made it impossible to
   identify which change had what effect. Should have done strict
   one-knob-per-cycle.
3. **I didn't read the existing W3 working files until very late.**
   When I finally did, I found the right shader values and AO-handling
   conventions, but by then the W4 anchor's architecture had drifted.
4. **I overfit to one diagnostic per turn.** Each "fix" assumed a single
   root cause. The evidence (artifacts shape changes between
   iterations) suggests multiple bugs are stacked. Future agent: solve
   them one at a time, with regression-test commits between each.
5. **I never did the minimal-shader test (option F above).** Should
   have been step ONE: prove the simplest possible shader works, then
   add complexity until the bug returns.

## Bottom line for the auditor

The bug is real. The current shader/textures look fine in isolation
(in headless captures, in Godot's editor texture preview). When applied
to the terrain mesh and rendered live, black geometric artifacts appear
that move with the camera.

**Start with option F (simplest possible shader on the terrain) to
isolate where the bug lives.** That's the test I should have done first.
If even a 3-line shader produces the artifacts, the problem is in the
mesh or the scene. If a 3-line shader is clean, the problem is in my
shader's math somewhere I haven't found.

Good luck. The user deserves a working anchor and I haven't delivered it.
