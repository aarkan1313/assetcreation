# world3

Real-DEM-driven world generator. OpenTopography heightmap → Godot 4.5 terrain
mesh → three view modes (iso, topdown, walkable). Fresh rebuild, no inherited
code from `worldgen_v2` or earlier attempts.

Status: M1-M7 are complete for workflow validation. `walk.tscn` renders visible
terrain through 256 m streamed `ChunkLoader.gd` chunks with the M4 unified splat
material, M6 runtime caches/collision, and M7 rule-driven transition masks. The
older MVP notes below are still useful for the base pipeline, but the current
workflow state lives in `docs/WORKFLOW_SNAPSHOT_2026_05_08.md`. M7 evidence is
in `docs/M7_BOUNDARY_RUNTIME_INTEGRATION.md`; before M8, run the visual audit
plan in `docs/M1_M7_VISUAL_AUDIT_PLAN_2026_05_08.md`.

## Layout

```
world3/
├── pipeline/
│   └── build_world.py          # DEM TIFF -> 16-bit heightmap PNG + meta.json
├── heightmap/
│   ├── heightmap.png           # current build, 1024x1024 u16
│   └── meta.json               # elev range, world size, source bounds
├── textures/
│   ├── rock_light/             # albedo / normal / ao / height + material.tres
│   ├── rock_dark/              # 5 PBR sets staged; only rock_light is wired in
│   ├── grass/
│   ├── desert/
│   └── forest_floor/
├── scripts/
│   ├── Terrain.gd              # builds subdivided mesh + collision from heightmap
│   ├── ChunkLoader.gd          # streams 256 m visual chunks around a target
│   ├── M5WalkStreamRunner.gd   # scripted walk-stream smoke test
│   ├── IsoCam.gd               # auto-frames the terrain AABB in ortho
│   ├── TopDownCam.gd           # auto-frames from straight above
│   ├── FlyCam.gd               # free-fly debug camera
│   ├── Walker.gd               # CharacterBody3D with fly/walk toggle
│   └── HeadlessCapture.gd      # screenshot + quit
├── scenes/
│   ├── iso.tscn                # 3/4 ortho view, auto-framed
│   ├── topdown.tscn            # straight-down ortho, auto-framed
│   ├── walk.tscn               # FPV walkable; F toggles fly
│   ├── capture_iso.tscn        # wraps iso.tscn + headless screenshot
│   ├── capture_topdown.tscn
│   └── capture_walk.tscn
└── project.godot               # main scene = iso.tscn; viewport 1920x1080
```

## Current source data

- **DEM**: `D:/assets/dems/COP30_-110.8500_+43.6500_-110.6500_+43.8500.tif`
  Grand Tetons, Wyoming. 720x720, COP30 (~30 m posting), elevation 1959–4059 m,
  ~16 km × 16 km on the ground. Already cached locally — pipeline does not
  call OpenTopography for this run.

- **Texture**: a single PBR set (`rock_light`, from `world/textures/library/rocks_ground_06`)
  applied via triplanar projection. The other four staged sets are unused so far.

## How it works

### Stage 1 — Python pipeline (DEM → heightmap)
`pipeline/build_world.py` reads a single-band float32 GeoTIFF, replaces nodata
with the local minimum, normalizes to [0, 1], LANCZOS-resamples to a square
target size, quantizes to 16-bit, and writes:

- `heightmap/heightmap.png` — 16-bit grayscale, square, mip-friendly
- `heightmap/meta.json` — `elevation_min_m`, `elevation_range_m`, `world_size_m`,
  source bounds, CRS, target material name

The `world_size_m` is computed from DEM bounds using local degree→meter scale at
the tile's mid-latitude (no projection — fine for tiles small relative to Earth).

### Stage 2 — Godot terrain build (runtime)
`scripts/Terrain.gd` is a `MeshInstance3D` script. On `_ready()` it:

1. Loads `meta.json` to get world size and elevation range
2. Loads the heightmap PNG (prefers `load()` for export safety; falls back to
   `Image.load_from_file()` to preserve 16-bit precision if Godot's import
   pipeline drops to 8-bit)
3. Builds a subdivided plane `ArrayMesh` (default 256×256 quads, ~131k tris)
   with vertex Y from heightmap, normals from finite differences
4. If a `collision_target` `StaticBody3D` is set in the scene, attaches a
   `HeightMapShape3D` matching the mesh. The body is uniformly scaled so each
   collision cell spans `world_size / subdivisions` meters; heights are stored
   pre-scale so post-scale Y matches mesh Y exactly.

### Stage 3 — Scene cameras
- **iso.tscn** — `IsoCam.gd` waits two frames, reads the terrain's AABB,
  positions itself on the +X+Y+Z diagonal, calls `look_at(center, UP)`, and
  computes the ortho `size` by projecting the AABB corners onto its right/up
  axes (tight fit at 16:9 aspect).
- **topdown.tscn** — `TopDownCam.gd` does the same from straight above
  (`Vector3.FORWARD` is the up reference for `look_at`).
- **walk.tscn** — Walker is a `CharacterBody3D` with a child `Camera3D` and
  `CapsuleShape3D`. Defaults to fly mode (impossible to fall through). **F**
  toggles. Camera-relative motion in fly, body-relative on the XZ plane in walk.
  Has a fall-recovery teleport if Y drops below `fall_recover_y`.

### Stage 4 — Headless capture
Each `capture_<mode>.tscn` instances the real scene + a `HeadlessCapture` node
that waits N frames, calls `get_viewport().get_texture().get_image().save_png()`,
and quits. Output goes to `D:/tmp/world3_screens/`.

## Run

### Build a heightmap from a DEM

```powershell
$env:PYTHONIOENCODING="utf-8"
python D:/assets/world3/pipeline/build_world.py `
  "D:/assets/dems/COP30_-110.8500_+43.6500_-110.6500_+43.8500.tif" `
  "D:/assets/world3/heightmap" `
  --size 1024 --material rock_light
```

### Open in Godot

```powershell
& "C:\Godot\Godot_v4.5-stable_win64.exe" --path "D:\assets\world3"
```

Main scene is `iso.tscn`. Open the other scenes from the FileSystem dock.

### Capture screenshots headlessly

```powershell
# Reimport once after any new heightmap or texture
& "C:\Godot\Godot_v4.5-stable_win64.exe" --path "D:\assets\world3" --headless --import

# Capture (any of the three)
& "C:\Godot\Godot_v4.5-stable_win64.exe" --path "D:\assets\world3" "res://scenes/capture_iso.tscn"
& "C:\Godot\Godot_v4.5-stable_win64.exe" --path "D:\assets\world3" "res://scenes/capture_topdown.tscn"
& "C:\Godot\Godot_v4.5-stable_win64.exe" --path "D:\assets\world3" "res://scenes/capture_walk.tscn"
```

PNGs land in `D:/tmp/world3_screens/{iso,topdown,walk}.png`.

## Walk-scene controls

| Input          | Action                                  |
|----------------|-----------------------------------------|
| WASD           | move                                    |
| Space          | jump (walk) / up (fly)                  |
| Ctrl           | down (fly)                              |
| Shift          | run / fast-fly multiplier               |
| F              | toggle fly mode                         |
| Esc            | release captured mouse                  |
| Mouse          | look (when captured)                    |

## Conscious choices and tradeoffs

- **Mesh built at runtime, not exported as a `.mesh`/`.tres`**. Lets us swap
  heightmaps and subdiv levels without an external export step. ~131k tris
  builds in <1 s and the cost is paid once at scene load.
- **`StaticBody3D` uniform scale, not per-axis**. Godot physics is fine with
  uniform scale on collision shapes; non-uniform scale causes drift. We pay
  one division per height value (`elev / s`) to compensate.
- **`Image.load_from_file()` fallback**. The default Godot PNG import is
  CompressedTexture2D RGB8, which would terrace 16-bit elevation to 256 steps
  (~8 m per step over 2.1 km). Falling back to a raw PNG read preserves
  precision in dev. Exported builds will need a different path.
- **Triplanar with `uv1_world_triplanar`**. Eliminates UV stretching on cliffs
  and the visible tile grid that dominated the early captures. World-space
  scale (`uv1_scale = 0.05` → 20 m per repeat) means tile period is constant
  regardless of view distance.
- **Fly mode is the default.** Until walk-mode physics is fully trusted on
  arbitrary DEMs, "impossible to fall through" beats "realistic but stuck."

## What's not done yet

- **M5 hardening.** The walk scene now has visible streamed splat chunks, but
  collision is still the hidden single terrain. Export-safe generated image
  loading, streamed collision, and boundary-strip sampling are still open.
- **Material indirection.** The M4/M5 splat path is fixed to five semantic
  slots. Arbitrary catalog material tables or texture arrays are not wired yet.
- **Iso/topdown scale tuning.** Camera framing is correct but the apparent
  scale of detail vs. mountain reads more "topographic survey" than "world
  you'd play in." Likely needs: shorter horizontal world size per tile (e.g.
  fetch a 4–8 km region instead of 16 km), more aggressive heightmap, and
  higher mesh subdivision in the foreground.
- **Real water / sea level.** No body-of-water handling. Anything below a
  configurable Y just renders as terrain.
- **Scatter / props / vegetation.** Not in scope for the MVP.
- **Multi-source world stitching.** The current stream tiles one source
  heightmap as a synthetic infinite field. Real adjacent DEM/source transitions
  still need CRS alignment, edge policy, and memory planning.

## What's archived/unused

These directories are stale or from earlier attempts and not referenced by
world3:

- `pipelines/worldgen_v2/`
- `worldgen2/` (Godot project)
- `original_workflow_godot/`, `world/worlds/llm_fjord_original/`
- `docs/superpowers/specs/2026-05-06-worldgen-v2-design.md` (old spec)
- `docs/superpowers/plans/2026-05-06-worldgen-v2.md` (old plan)

Safe to delete once you're confident world3 covers what you need.
