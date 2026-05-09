# world3 — Docs Index

What lives where, in one page. Read this first if you're trying to
find something.

## When you want to know...

| Question                                                     | Read                                                  |
|--------------------------------------------------------------|-------------------------------------------------------|
| "How is the docs system organized? Where do new findings go?" | [DOCS_GUIDE.md](DOCS_GUIDE.md)                       |
| "What is world3 and how do I run it end-to-end?"             | [WORKFLOW.md](WORKFLOW.md)                            |
| "What's the current operating model + state of the project?" | [WORLD3_STATE_2026_05_08.md](WORLD3_STATE_2026_05_08.md) (orchestrator/worker model + M1-M6 state + M7-M12 lane + worker infra inventory) |
| "What are we building toward, in phases?"                    | [ROADMAP.md](ROADMAP.md) (v2 — reframed 2026-05-07; updated 2026-05-08 with M1-M6 and M7-M12 sequence)   |
| "What was the original roadmap before reframing?"            | [ROADMAP_v1_archived.md](ROADMAP_v1_archived.md)      |
| "What's the current iteration's scope?"                      | [PLAN.md](PLAN.md)                                    |
| "What are the next six milestones after M6?"                 | [M7_M12_NEAR_ROADMAP.md](M7_M12_NEAR_ROADMAP.md)      |
| "How did M7 automatic boundary placement work?"              | [M7_BOUNDARY_RUNTIME_INTEGRATION.md](M7_BOUNDARY_RUNTIME_INTEGRATION.md) |
| "How should we review M1-M7 visually before M8?"             | [M1_M7_VISUAL_AUDIT_PLAN_2026_05_08.md](M1_M7_VISUAL_AUDIT_PLAN_2026_05_08.md) |
| "What did the M1-M7 visual audit find?"                      | [M1_M7_VISUAL_AUDIT_2026_05_08.md](M1_M7_VISUAL_AUDIT_2026_05_08.md) |
| "What visual gaps did Codex see in the actual M1-M7 captures?" | [M1_M7_VISION_GAP_REVIEW_2026_05_08.md](M1_M7_VISION_GAP_REVIEW_2026_05_08.md) |
| "How do we repair the failed M1-M7 visual gate?"             | [M1_M7_VISUAL_REMEDIATION_PLAN_2026_05_08.md](M1_M7_VISUAL_REMEDIATION_PLAN_2026_05_08.md) |
| "What did the first source-stack runtime remediation ship?"  | [SOURCE_STACK_RUNTIME_REMEDIATION_2026_05_08.md](SOURCE_STACK_RUNTIME_REMEDIATION_2026_05_08.md) |
| "How were the worst organic textures repaired/quarantined?"  | [M1_M7_ORGANIC_TEXTURE_REPAIR_2026_05_08.md](M1_M7_ORGANIC_TEXTURE_REPAIR_2026_05_08.md) |
| "What is the current ComfyUI texture workflow inventory?"    | [COMFYUI_TEXTURE_WORKFLOW_INVENTORY_2026_05_08.md](COMFYUI_TEXTURE_WORKFLOW_INVENTORY_2026_05_08.md) |
| "What happened in the first M8 ComfyUI regeneration pass?"   | [M8_COMFYUI_TEXTURE_REGEN_PASS_2026_05_08.md](M8_COMFYUI_TEXTURE_REGEN_PASS_2026_05_08.md) |
| "Did the first M8 ComfyUI candidate work in terrain context?" | [M8_COMFYUI_TERRAIN_CONTEXT_REVIEW_2026_05_08.md](M8_COMFYUI_TERRAIN_CONTEXT_REVIEW_2026_05_08.md) |
| "How noisy is the first M8 ComfyUI candidate?"               | [M8_COMFYUI_CANDIDATE_NOISE_AUDIT.md](M8_COMFYUI_CANDIDATE_NOISE_AUDIT.md) |
| "What happened with the next ComfyUI grass attempts?"         | [M8_GRASS_REGEN_ATTEMPTS_REVIEW_2026_05_08.md](M8_GRASS_REGEN_ATTEMPTS_REVIEW_2026_05_08.md) |
| "Which grass attempts hit the visual veto helper?"            | [M8_GRASS_VISUAL_VETO_AUDIT.md](M8_GRASS_VISUAL_VETO_AUDIT.md) |
| "What did M6 harden in the streamed runtime?"                | [M6_RUNTIME_HARDENING.md](M6_RUNTIME_HARDENING.md)    |
| "Which green/organic source materials are too noisy?"        | [M6_SOURCE_MATERIAL_NOISE_AUDIT.md](M6_SOURCE_MATERIAL_NOISE_AUDIT.md) |
| "What did the first M4 splat shader prototype prove?"        | [M4_SPLAT_SHADER_PROTOTYPE.md](M4_SPLAT_SHADER_PROTOTYPE.md) |
| "What does a streamed chunk provide to the splat shader?"     | [M4_CHUNK_MATERIAL_CONTRACT.md](M4_CHUNK_MATERIAL_CONTRACT.md) |
| "Why did we choose X over Y?"                                | [DECISIONS.md](DECISIONS.md)                          |
| "What's the canonical command for [common task]?"            | [../../pipelines/textures/RECIPES.md](../../pipelines/textures/RECIPES.md) |
| "How does the texture pipeline work internally?"             | [../../pipelines/textures/PIPELINE.md](../../pipelines/textures/PIPELINE.md) |
| "What every texture-pipeline tool does + when to use it"     | [../../pipelines/textures/TOOLS.md](../../pipelines/textures/TOOLS.md) |
| "What prompts work, what we learned from sweeps"             | [../../pipelines/textures/TEXTURE_RND.md](../../pipelines/textures/TEXTURE_RND.md) |
| "What did we learn that surprised us?"                       | [../../pipelines/textures/LESSONS.md](../../pipelines/textures/LESSONS.md)   |
| "What does the rest of the world do for tileable PBR?"       | [../../pipelines/textures/EXTERNAL_TECHNIQUES.md](../../pipelines/textures/EXTERNAL_TECHNIQUES.md) (snapshot, 2026-05-07) |
| "What was broken about the texture pipeline + how was it fixed?" | [TEXTURE_PIPELINE_FIX_PLAN.md](TEXTURE_PIPELINE_FIX_PLAN.md) |
| "How do I view the OpenTopo pilot scenes?"                   | [../toporeview/README.md](../toporeview/README.md) |
| "How do I pull/process OpenTopography data?"                 | [OPENTOPO_GUIDE.md](OPENTOPO_GUIDE.md), [OPENTOPO_DATA_TYPES.md](OPENTOPO_DATA_TYPES.md), [OPENTOPO_MOSAIC_FUSION_WORKFLOWS.md](OPENTOPO_MOSAIC_FUSION_WORKFLOWS.md), [../opentopo/STATUS.md](../opentopo/STATUS.md) |
| "What OpenTopo tooling/knobs do we have, and what should I turn?" | [OPENTOPO_TOOLING_KNOBS_GUIDE.md](OPENTOPO_TOOLING_KNOBS_GUIDE.md) |
| "What are the current final OpenTopo master stacks?" | [OPENTOPO_MASTER_STACKS_AUDIT.md](OPENTOPO_MASTER_STACKS_AUDIT.md) |
| "How do we stitch tiles or fuse height/color/canopy layers?" | [OPENTOPO_MOSAIC_FUSION_WORKFLOWS.md](OPENTOPO_MOSAIC_FUSION_WORKFLOWS.md) |
| "How do OpenTopo textures, real-place scenes, and HD zoom fit together?" | [OPENTOPO_TEXTURE_SCENE_ROADMAP.md](OPENTOPO_TEXTURE_SCENE_ROADMAP.md) |
| "How do we rebuild the finished OpenTopo ground materials?" | [OPENTOPO_TILEABLE_REAL_TEXTURE_WORKFLOW.md](OPENTOPO_TILEABLE_REAL_TEXTURE_WORKFLOW.md#current-endpoint-quickstart) |
| "How do we turn real OpenTopo ground into tileable textures?" | [OPENTOPO_TILEABLE_REAL_TEXTURE_WORKFLOW.md](OPENTOPO_TILEABLE_REAL_TEXTURE_WORKFLOW.md) |
| "How do we review unlike biome tile-to-tile transitions?" | [OPENTOPO_BIOME_TILE_TRANSITION_REVIEW.md](OPENTOPO_BIOME_TILE_TRANSITION_REVIEW.md) |
| "What happened in the BC Coast DTM/DSM no-color stack?" | [OPENTOPO_BC_COAST_DTM_DSM_AUDIT.md](OPENTOPO_BC_COAST_DTM_DSM_AUDIT.md) |
| "What happened in the first tileable real-ground texture pilot?" | [OPENTOPO_TILEABLE_TEXTURE_PILOT_AUDIT.md](OPENTOPO_TILEABLE_TEXTURE_PILOT_AUDIT.md) |
| "What happened in the Phase 2 HD review pass?"             | [OPENTOPO_PHASE2_HD_REVIEW.md](OPENTOPO_PHASE2_HD_REVIEW.md) |
| "What happened in the Phase 2 max review pass?"            | [OPENTOPO_PHASE2_MAX_REVIEW.md](OPENTOPO_PHASE2_MAX_REVIEW.md) |
| "What is the next huge 4-call OpenTopo plan?"              | [OPENTOPO_LARGE_4CALL_PLAN.md](OPENTOPO_LARGE_4CALL_PLAN.md) |
| "What happened in the Smokies 4-call `USGS1m` run?"        | [OPENTOPO_PHASE3_SMOKIES_4CALL_AUDIT.md](OPENTOPO_PHASE3_SMOKIES_4CALL_AUDIT.md) |
| "What happened in the first OpenTopo mosaic pilot?"          | [OPENTOPO_PILOT1_GRAND_CANYON_USGS10M_AUDIT.md](OPENTOPO_PILOT1_GRAND_CANYON_USGS10M_AUDIT.md) |
| "What happened in the first OpenTopo fusion pilot?"          | [OPENTOPO_PILOT2_GUADALUPE_CYPRESS_FUSION_AUDIT.md](OPENTOPO_PILOT2_GUADALUPE_CYPRESS_FUSION_AUDIT.md) |
| "What do the Phase A texture before/after captures look like?" | [captures/phase_a/](captures/phase_a/) (per-material before/after) |
| "What do the Phase C zoom-level captures look like?" | [captures/phase_c/](captures/phase_c/) (40m ARPG / 300m strategy / 50m game-tile / 10km minimap on Tetons) |
| "What do the Phase E per-mode tuning captures look like?" | [captures/phase_e/](captures/phase_e/) (alpine walk/iso/topdown) |
| "What do the Phase E region gallery captures look like?" | [captures/phase_e_gallery/](captures/phase_e_gallery/) (7 regions x iso + topdown across all 5 kits) |
| "What do the M6 runtime hardening captures look like?" | [captures/m6/](captures/m6/) (walk cache/collision + runtime transition-strip review) |
| "What do the M7 automatic boundary captures look like?" | [captures/m7/](captures/m7/) (same-source control, biome stress, walk crossing + metrics; diagnostics, not visual promotion) |
| "What do the M1-M7 remediation captures look like?" | [captures/visual_remediation/](captures/visual_remediation/) (source-stack parity + organic repair candidates) |
| "What do the historical iteration screenshots look like?"    | [captures/](captures/) iter*/, phase2_*/ — kept locally only, gitignored |

## Doc roles, in one sentence each

- **WORKFLOW.md** — *as-built* operational steps. The "how to recreate
  what we have today" guide. Updated when behaviour changes.
- **ROADMAP.md** — phased plan toward the long-term vision. v2 reframe
  (2026-05-07) sequences A→B→D→C→E→F. Phases A–E done as of 2026-05-07
  evening; F (multi-tile / continuous world) is next.
- **PLAN.md** — current iteration only. What's in scope right now,
  what's deliberately deferred, exit criteria. Rewritten each iteration.
- **DECISIONS.md** — append-only log of architectural choices and the
  alternatives we considered. Never edit history; new decisions get
  new entries even when they reverse old ones.
- **TEXTURE_PIPELINE_FIX_PLAN.md** — the audit + fix doc for the
  texture pipeline overhaul on 2026-05-07. Reference / archive value.
- **COMFYUI_TEXTURE_WORKFLOW_INVENTORY_2026_05_08.md** - current
  ComfyUI/`aaa_texture.py` material inventory, M8 regeneration blockers,
  staging gaps, and shared promotion gate.
- **M8_COMFYUI_TERRAIN_CONTEXT_REVIEW_2026_05_08.md** - first sidecar
  ComfyUI candidate terrain-context gate; candidate pass, no canonical
  promotion.
- **M8_GRASS_REGEN_ATTEMPTS_REVIEW_2026_05_08.md** - failed `grass`
  regeneration attempts and the resulting visual landmark/object veto rule.
- **pipelines/textures/RECIPES.md** — canonical commands per use case.
  *Operator's guide.* "I want X, here's the invocation." Reach for
  this first when actually running the pipeline.
- **pipelines/textures/PIPELINE.md** — runbook explaining how the
  pipeline works internally (stages, presets, gate logic, output
  layout, failure modes, world3 staging convention). Reach for this
  when something fails or you need to understand the mechanics.
- **pipelines/textures/TOOLS.md** — inventory of every texture-pipeline
  tool script + when to reach for each.
- **pipelines/textures/TEXTURE_RND.md** — append-only R&D log:
  experiments/sweeps in Part 1, prompt cookbook in Part 2.
- **pipelines/textures/LESSONS.md** — surprises, gotchas, and "why
  the obvious thing was wrong" entries. Append-only.
- **OPENTOPO_GUIDE.md / OPENTOPO_DATA_TYPES.md /
  OPENTOPO_TOOLING_KNOBS_GUIDE.md /
  OPENTOPO_MOSAIC_FUSION_WORKFLOWS.md /
  OPENTOPO_TEXTURE_SCENE_ROADMAP.md /
  OPENTOPO_MASTER_STACKS_AUDIT.md /
  OPENTOPO_PHASE2_HD_REVIEW.md /
  OPENTOPO_PHASE2_MAX_REVIEW.md /
  OPENTOPO_LARGE_4CALL_PLAN.md /
  OPENTOPO_PHASE3_SMOKIES_4CALL_AUDIT.md /
  OPENTOPO_BC_COAST_DTM_DSM_AUDIT.md /
  OPENTOPO_PILOT1_GRAND_CANYON_USGS10M_AUDIT.md /
  OPENTOPO_PILOT2_GUADALUPE_CYPRESS_FUSION_AUDIT.md / opentopo/STATUS.md** —
  OpenTopography sourcing, tooling knobs, data-type findings, mosaic/fusion
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
│   ├── OPENTOPO_GUIDE.md / OPENTOPO_DATA_TYPES.md / OPENTOPO_TOOLING_KNOBS_GUIDE.md / OPENTOPO_MOSAIC_FUSION_WORKFLOWS.md
│   ├── OPENTOPO_PILOT1_GRAND_CANYON_USGS10M_AUDIT.md
│   ├── OPENTOPO_PILOT2_GUADALUPE_CYPRESS_FUSION_AUDIT.md
│   └── captures/                   # before/after screenshots
│       ├── phase_a/                 # Phase A texture evidence (tracked)
│       │   ├── snow_{before,after}/                  # A.3
│       │   ├── forest_floor_{before,after}/          # A.3
│       │   ├── tundra_ice_{before,after}/            # A.6
│       │   ├── desert_canyon_rock_{before,after}/    # A.6
│       │   ├── A8_chord_ab/                          # A.8 CHORD vs SM A/B
│       │   └── A9_variant_blend_ab/                  # A.9 select vs blend A/B
│       ├── phase_c/                 # Phase C anchor-framing zoom captures (Tetons)
│       │   ├── iso_arpg_40m.png
│       │   ├── iso_strategy_300m.png
│       │   ├── topdown_game_tile_50m.png
│       │   └── topdown_minimap_10km.png
│       ├── phase_e/                 # Phase E per-mode sanity captures (alpine)
│       │   ├── alpine_walk.png
│       │   ├── alpine_iso.png
│       │   └── alpine_topdown.png
│       ├── phase_e_gallery/         # Phase E region gallery — 7 regions x iso+topdown
│       │   ├── tcf_pnw_cascades_usa/{iso,topdown}.png    # alpine
│       │   ├── tbm_appalachians_usa/{iso,topdown}.png    # alpine
│       │   ├── des_mojave_usa/{iso,topdown}.png          # desert
│       │   ├── tun_arctic_alaska/{iso,topdown}.png       # tundra
│       │   ├── med_california_chaparral/{iso,topdown}.png # temperate_forest
│       │   ├── mgs_tibetan_plateau/{iso,topdown}.png     # grassland
│       │   └── tgs_serengeti_tanzania/{iso,topdown}.png  # grassland
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
