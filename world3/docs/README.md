# world3 — Docs Index

What lives where, in one page. Read this first if you're trying to
find something.

## When you want to know...

| Question                                                     | Read                                                  |
|--------------------------------------------------------------|-------------------------------------------------------|
| "How is the docs system organized? Where do new findings go?" | [DOCS_GUIDE.md](DOCS_GUIDE.md)                       |
| "What is world3 and how do I run it end-to-end?"             | [WORKFLOW.md](WORKFLOW.md)                            |
| "What are we building toward, in phases?"                    | [ROADMAP.md](ROADMAP.md) (v2 — reframed 2026-05-07)   |
| "What was the original roadmap before reframing?"            | [ROADMAP_v1_archived.md](ROADMAP_v1_archived.md)      |
| "What's the current iteration's scope?"                      | [PLAN.md](PLAN.md)                                    |
| "Why did we choose X over Y?"                                | [DECISIONS.md](DECISIONS.md)                          |
| "How do I generate a new texture?"                           | [../../pipelines/textures/PIPELINE.md](../../pipelines/textures/PIPELINE.md) |
| "What every texture-pipeline tool does + when to use it"     | [../../pipelines/textures/TOOLS.md](../../pipelines/textures/TOOLS.md) |
| "What prompts work, what we learned from sweeps"             | [../../pipelines/textures/TEXTURE_RND.md](../../pipelines/textures/TEXTURE_RND.md) |
| "What did we learn that surprised us?"                       | [../../pipelines/textures/LESSONS.md](../../pipelines/textures/LESSONS.md)   |
| "What does the rest of the world do for tileable PBR?"       | [../../pipelines/textures/EXTERNAL_TECHNIQUES.md](../../pipelines/textures/EXTERNAL_TECHNIQUES.md) (snapshot, 2026-05-07) |
| "What was broken about the texture pipeline + how was it fixed?" | [TEXTURE_PIPELINE_FIX_PLAN.md](TEXTURE_PIPELINE_FIX_PLAN.md) |
| "How do I view the OpenTopo pilot scenes?"                   | [../toporeview/README.md](../toporeview/README.md) |
| "How do I pull/process OpenTopography data?"                 | [OPENTOPO_GUIDE.md](OPENTOPO_GUIDE.md), [OPENTOPO_DATA_TYPES.md](OPENTOPO_DATA_TYPES.md), [OPENTOPO_MOSAIC_FUSION_WORKFLOWS.md](OPENTOPO_MOSAIC_FUSION_WORKFLOWS.md), [../opentopo/STATUS.md](../opentopo/STATUS.md) |
| "How do we stitch tiles or fuse height/color/canopy layers?" | [OPENTOPO_MOSAIC_FUSION_WORKFLOWS.md](OPENTOPO_MOSAIC_FUSION_WORKFLOWS.md) |
| "How do OpenTopo textures, real-place scenes, and HD zoom fit together?" | [OPENTOPO_TEXTURE_SCENE_ROADMAP.md](OPENTOPO_TEXTURE_SCENE_ROADMAP.md) |
| "What happened in the Phase 2 HD review pass?"             | [OPENTOPO_PHASE2_HD_REVIEW.md](OPENTOPO_PHASE2_HD_REVIEW.md) |
| "What happened in the Phase 2 max review pass?"            | [OPENTOPO_PHASE2_MAX_REVIEW.md](OPENTOPO_PHASE2_MAX_REVIEW.md) |
| "What is the next huge 4-call OpenTopo plan?"              | [OPENTOPO_LARGE_4CALL_PLAN.md](OPENTOPO_LARGE_4CALL_PLAN.md) |
| "What happened in the first OpenTopo mosaic pilot?"          | [OPENTOPO_PILOT1_GRAND_CANYON_USGS10M_AUDIT.md](OPENTOPO_PILOT1_GRAND_CANYON_USGS10M_AUDIT.md) |
| "What happened in the first OpenTopo fusion pilot?"          | [OPENTOPO_PILOT2_GUADALUPE_CYPRESS_FUSION_AUDIT.md](OPENTOPO_PILOT2_GUADALUPE_CYPRESS_FUSION_AUDIT.md) |
| "What do the current Phase A before/after captures look like?" | [captures/phase_a/](captures/phase_a/) (per-material before/after) |
| "What do the historical iteration screenshots look like?"    | [captures/](captures/) iter*/, phase2_*/ — kept locally only, gitignored |

## Doc roles, in one sentence each

- **WORKFLOW.md** — *as-built* operational steps. The "how to recreate
  what we have today" guide. Updated when behaviour changes.
- **ROADMAP.md** — phased plan toward the long-term vision. Phase 0
  done, Phase 1 in progress, Phases 2–6 sketched. Updated rarely.
- **PLAN.md** — current iteration only. What's in scope right now,
  what's deliberately deferred, exit criteria. Rewritten each iteration.
- **DECISIONS.md** — append-only log of architectural choices and the
  alternatives we considered. Never edit history; new decisions get
  new entries even when they reverse old ones.
- **TEXTURE_PIPELINE_FIX_PLAN.md** — the audit + fix doc for the
  texture pipeline overhaul on 2026-05-07. Reference / archive value.
- **pipelines/textures/PIPELINE.md** — runbook for the texture
  generation pipeline (commands, presets, output layout, failure
  modes, world3 staging convention).
- **pipelines/textures/TOOLS.md** — inventory of every texture-pipeline
  tool script + when to reach for each.
- **pipelines/textures/TEXTURE_RND.md** — append-only R&D log:
  experiments/sweeps in Part 1, prompt cookbook in Part 2.
- **pipelines/textures/LESSONS.md** — surprises, gotchas, and "why
  the obvious thing was wrong" entries. Append-only.
- **OPENTOPO_GUIDE.md / OPENTOPO_DATA_TYPES.md /
  OPENTOPO_MOSAIC_FUSION_WORKFLOWS.md /
  OPENTOPO_TEXTURE_SCENE_ROADMAP.md /
  OPENTOPO_PHASE2_HD_REVIEW.md /
  OPENTOPO_PHASE2_MAX_REVIEW.md /
  OPENTOPO_LARGE_4CALL_PLAN.md /
  OPENTOPO_PILOT1_GRAND_CANYON_USGS10M_AUDIT.md /
  OPENTOPO_PILOT2_GUADALUPE_CYPRESS_FUSION_AUDIT.md / opentopo/STATUS.md** —
  OpenTopography sourcing, tooling commands, data-type findings, mosaic/fusion
  plans, pilot audits, and fetched output inventory.
- **toporeview/README.md** - Godot scene paths, controls, and layer
  inventories for the OpenTopo mosaic and fusion pilots.

## File layout reference

```
world3/
├── docs/                           # this directory
│   ├── README.md                   # ← you are here
│   ├── WORKFLOW.md
│   ├── ROADMAP.md
│   ├── PLAN.md
│   ├── DECISIONS.md
│   ├── TEXTURE_PIPELINE_FIX_PLAN.md
│   ├── OPENTOPO_GUIDE.md / OPENTOPO_DATA_TYPES.md / OPENTOPO_MOSAIC_FUSION_WORKFLOWS.md
│   ├── OPENTOPO_PILOT1_GRAND_CANYON_USGS10M_AUDIT.md
│   ├── OPENTOPO_PILOT2_GUADALUPE_CYPRESS_FUSION_AUDIT.md
│   └── captures/                   # before/after screenshots
│       ├── phase_a/                 # CURRENT — Phase A texture before/after (tracked)
│       │   ├── snow_{before,after}/
│       │   ├── forest_floor_{before,after}/
│       │   ├── tundra_ice_{before,after}/
│       │   └── desert_canyon_rock_{before,after}/
│       └── iter*/, phase2_*/        # historical iteration screenshots (gitignored — local only)
├── pipeline/                       # Python: OpenTopo + DEM processing
│   ├── opentopo_fetch.py
│   ├── fetch_opentopo_tile_grid.py
│   ├── build_opentopo_mosaic.py
│   ├── validate_opentopo_mosaic.py
│   ├── export_opentopo_rgb_mosaic.py
│   ├── export_opentopo_vegetation_mask.py
│   ├── export_opentopo_review_texture.py
│   ├── build_opentopo_stack_manifest.py
│   ├── build_world.py
│   ├── process_laz_samples.py
│   ├── export_opentopo_texture.py
│   └── export_opentopo_mosaic.py
├── opentopo/                       # OpenTopo plans, raw/processed data, status
├── toporeview/                     # Godot review scenes for OpenTopo pilots
├── heightmap/                      # current heightmap output
├── textures/wgv3/                  # staged PBR sets + materials
├── shaders/                        # GLSL shaders (terrain_hex, _detail, _blend)
├── scripts/                        # Godot GDScript
├── scenes/                         # Godot .tscn scenes
└── project.godot
```

External (used by but not part of) world3:

```
pipelines/textures/                 # texture generation pipeline
├── PIPELINE.md                     # runbook
├── TOOLS.md                        # tool inventory + when to reach for each
├── TEXTURE_RND.md                  # experiments + prompt cookbook (append-only)
├── LESSONS.md                      # surprises log (append-only)
├── aaa_texture.py                  # orchestrator
├── texture_qa.py                   # 3-check seam metric + sanity
├── seam_repair.py                  # offset+quilt repair (in-place + backup)
├── stablematerials_image2pbr.py    # image → PBR via SM diffusion model
├── flux_seamless.py                # FLUX 2 klein with offset+heal seamless trick
├── delight.py                      # LAB-space lighting flatten
├── derive_pbr_v2.py                # heuristic PBR (no model, fast preset)
├── variant_select.py               # multi-seed best-pick
├── palette_lock.py                 # biome-cohesive multi-texture generation
├── detail_variant.py               # detail-layer companion texture
├── relock_palette.py               # re-palette-lock without regenerating
├── biome_consistency.py            # advisory: does this fit the kit?
├── high_pass_detail.py             # extract / sharpen detail
├── experiment.py                   # sweep harness for R&D
├── blender_preview.py              # Blender CYCLES preview render (optional)
└── ... (other tools — see TOOLS.md)

world/textures/library/             # generated PBR sets live here
└── <id>/                           # one folder per material
    ├── <id>_<map>.png              # 6 PBR maps
    ├── <id>_<map>.pre_*.png        # delight / repair / palette backups
    ├── aaa_pipeline.json           # full pipeline log + grade
    └── qa/                         # seam_score.json, tile_2x2.png, sphere/plane previews

world/textures/catalog/
└── materials.jsonl                 # one JSON line per generated material
```

## Quick cheatsheet

```powershell
# Generate one texture
$env:PYTHONIOENCODING="utf-8"
cd D:/assets
python pipelines/textures/aaa_texture.py `
  --prompt "rich brown dirt, top-down photo, photoreal" `
  --id wgv3_dirt --category Ground --quality default

# Generate a detail variant (paired with macro)
python pipelines/textures/detail_variant.py --of wgv3_rock_dark --strength 0.5

# Generate a palette-locked biome (kit of cohesive textures)
python pipelines/textures/palette_lock.py `
  --kit alpine --anchor wgv3_rock_dark `
  --add "moss-covered alpine boulder, top-down photo:wgv3_alpine_moss:Foliage" `
  --add "scree slope, top-down photo:wgv3_alpine_scree:Rock" `
  --strength 0.6

# Build a heightmap from a cached DEM (cropped)
python world3/pipeline/build_world.py `
  "D:/assets/dems/COP30_-110.85_+43.65_-110.65_+43.85.tif" `
  "D:/assets/world3/heightmap" `
  --center -110.803 43.741 --extent-km 4

# Reimport Godot project
& "C:/Godot/Godot_v4.5-stable_win64.exe" --path "D:/assets/world3" --headless --import

# Capture (terrain scenes)
& "C:/Godot/Godot_v4.5-stable_win64.exe" --path "D:/assets/world3" "res://scenes/capture_iso.tscn"
& "C:/Godot/Godot_v4.5-stable_win64.exe" --path "D:/assets/world3" "res://scenes/capture_topdown.tscn"
& "C:/Godot/Godot_v4.5-stable_win64.exe" --path "D:/assets/world3" "res://scenes/capture_walk.tscn"

# Capture (texture viewer grids — for shader iteration A/B)
& "C:/Godot/Godot_v4.5-stable_win64.exe" --path "D:/assets/world3" "res://scenes/capture_texture_grid.tscn"        # baseline
& "C:/Godot/Godot_v4.5-stable_win64.exe" --path "D:/assets/world3" "res://scenes/capture_texture_grid_hex.tscn"    # hex+macro
& "C:/Godot/Godot_v4.5-stable_win64.exe" --path "D:/assets/world3" "res://scenes/capture_texture_grid_hex_detail.tscn"     # +macro+detail (self-detail)
& "C:/Godot/Godot_v4.5-stable_win64.exe" --path "D:/assets/world3" "res://scenes/capture_texture_grid_hex_detail_v2.tscn"  # +macro+detail (dedicated detail variant)
```
