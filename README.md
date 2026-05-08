# D:\assets — Asset Factory

Self-generated AAA-grade assets for **Godot 4.5 / JK Engine / TLTE**. Everything from prompt to ready-to-import Godot resource lives here.

## Doc map

Open these in order if you're new:

| Doc | What it's for |
|---|---|
| [WORKFLOWS.md](WORKFLOWS.md) | 🌳 **Master workflow list** — per-asset trees, tool branches, run order. **Start here if you want to make something.** |
| [DOCS_INDEX.md](DOCS_INDEX.md) | Canonical doc-ownership map |
| [PIPELINE_DIRECTORY.md](PIPELINE_DIRECTORY.md) | Live status table — what works today, in one page |
| [PIPELINE_GUIDE.md](PIPELINE_GUIDE.md) | Copy-paste recipes for every workflow |
| [TOOLS_INDEX.md](TOOLS_INDEX.md) | Tool directory — every script + env |
| [docs/tools/README.md](docs/tools/README.md) | **In-tree doc map** — index of every per-tool/per-pipeline doc that lives next to its code |
| [animators/INSTALL_MATRIX.md](animators/INSTALL_MATRIX.md) | **Animator install recipes** — RTX 5090 / Win11 stacks for the 13 animator tools |
| [docs/plans/ROADMAP.md](docs/plans/ROADMAP.md) | What's next — current focus + priorities |
| [docs/audits/AUDIT_2026_05_07_post_nuke.md](docs/audits/AUDIT_2026_05_07_post_nuke.md) | **Latest audit** — truth-from-disk, post-worldgen-nuke |
| [docs/pipeline_reviews/](docs/pipeline_reviews/README.md) | **Per-pipeline review pass** (2026-05-07) — honest quality verdicts per lane |
| [docs/audits/REVIEW.md](docs/audits/REVIEW.md) | Pipeline post-mortems (bugs found + fixed) |
| [docs/plans/RESEARCH_HANDOFF.md](docs/plans/RESEARCH_HANDOFF.md) | Briefs for sub-agents researching SOTA per category |
| [research/](research/) | Returned reports (A terrain, B textures, C/C2 VFX, D UI, E/E2 audio, F/F2 game data, G deep dive, J2 props, K open-weights) |
| [docs/reference/OPENTOPO_API.md](docs/reference/OPENTOPO_API.md) | OpenTopography API reference |
| [docs/reference/CLOUD_KEYS.md](docs/reference/CLOUD_KEYS.md) | Cloud env-var index |
| [docs/plans/LONG_TERM_VISION.md](docs/plans/LONG_TERM_VISION.md) | Multi-month directional intent |
| [docs/handoffs/HANDOFF_2026_05_07_night_path2_parked.md](docs/handoffs/HANDOFF_2026_05_07_night_path2_parked.md) | **Latest cross-cutting handoff** — whole-project orientation + Path 2 parked + open backlog |
| [docs/handoffs/](docs/handoffs/) | Per-pipeline deep-dive handoff snapshots |
| `_archive/` | Superseded snapshots. Historical only — never edit. |

**Current focus (2026-05-07 night):**
- ✅ **world3 Phases A–E complete.** Texture pipeline (B), iso/topdown framing (C), all 5 biome kits with bound .tres (D), per-game-mode material variants (E). 7-region gallery captures across all 5 kits at `world3/docs/captures/phase_e_gallery/`. See [world3/docs/PLAN.md](world3/docs/PLAN.md) and [world3/docs/ROADMAP.md](world3/docs/ROADMAP.md).
- ✅ **Per-pipeline manual review pass complete.** 7 of 8 pipelines reviewed at `docs/pipeline_reviews/`. Calibrated honest verdicts per lane against user judgment.
- ✅ **All 13 animator tools install-validated.** Including Anytop (Windows-ported from Linux conda) and MaterialAnything (kaolin install path corrected). See `animators/INSTALL_MATRIX.md`.
- ✅ **Audio output archived** (189 MB, was noise-tier). Pipeline retained.
- 🟡 **Path 2 character_inpaint pipeline** mechanically correct end-to-end (2026-05-07 night, 5 bugs fixed). FLUX prompt quality is the remaining open gap. See [docs/plans/PATH_2_INPAINT_DESIGN_2026_05_07.md](docs/plans/PATH_2_INPAINT_DESIGN_2026_05_07.md).
- 📋 **Next planned (world3):** Phase F (multi-tile / continuous world) — research + prototype phase. Open polish items: grassland slope/height tuning, non-alpine per-mode review, walk-mode anchor wiring, gallery walk shot.
- 📋 **Other queued:** FLUX prompt engineering / ControlNet on chest insignia, then characters animation deep-dive.

## What's in here (highest level)

```
D:\assets\
├── meshy/             Character pipeline (Meshy API + preprocess + bake + atlas)
├── animators/         AI rigging/animation/generation tools (each in own venv)
├── pipelines/         Non-character pipelines (terrain DEMs, textures, godot export, props, ui, vfx, audio, game_data, character_inpaint)
├── art_lab/           Magic/World Art Lab (shaders, maps, biomes — first-party; references to baked worlds now stale)
├── world/             Outputs: textures library, props library (terrain/worlds/maps moved to _archive/worldgen_2026_05_07/)
├── characters/        Reserved for future character outputs
├── dems/              222 cached OpenTopography TIFFs (~8.1 GB) — relocated 2026-05-07 from pipelines/terrain/source_dems/
├── godot_pack/        Godot exporter output — drop into a Godot 4.5 project
└── research/          Returned research reports
```

## Today's state (one paragraph)

**Pipelines work, content is mostly placeholder.** A 2026-05-07 manual review pass (see `docs/pipeline_reviews/`) calibrated the gap between **pipeline plumbing** (real, mature, deserves keeping) and **current content output** (procedural/unprompted, mostly throwaway). Audio output was archived 2026-05-07 after auditioning revealed noise-tier quality. UI is "good placeholders," VFX has 18 of 24 spell effects as palette-swap recolors, game data has 14 toy records, props has 1 hero (obelisk) + 14 procedural-variant families. **Reframe:** pipelines are the deliverable; content gets re-authored with focus when game-design intent is clear, not procedurally fanned out. Character pipeline (Meshy → 5 riggers → animate → bake → atlas, ~33 GLBs + 5 animations) is the one lane that may produce production content — but the **animation step is uncalibrated** and needs deep-dive. **Worldgen** is being rebuilt at `world3/` after v1/v2 nuke; **OpenTopography DEM fetching still works end-to-end** (cache-aware, OT+ Pro active, 220 regions / 8.1 GB at `dems/`). All 13 animator tools install-validated end-to-end as of 2026-05-07.

## One-command starting points

```powershell
# Pre-flight (each new shell): make the env var available to subprocesses.
# OT+ tier active 2026-05-06: All Access (USGS 1m unlocked), 400 calls/24h.
$env:OPENTOPOGRAPHY_API_KEY = [Environment]::GetEnvironmentVariable("OPENTOPOGRAPHY_API_KEY", "User")

# Bulk-pull DEMs from the wishlist (resumable, cache-aware, rate-limit-aware; ~50GB at full)
python pipelines\terrain\bulk_pull.py --tier premium --dry-run    # plan
python pipelines\terrain\bulk_pull.py --tier premium              # do (default 400/24h OT+ quota; use --quota 50 on free tier)

# Search the OpenTopo catalog for what's available at any bbox (no quota cost)
python pipelines\terrain\catalog_search.py --bbox -112.20 37.55 -112.00 37.75

# Pull at US LiDAR-grade 10m (free tier, no Pro needed)
python pipelines\terrain\import_dem.py --id yose_10m --source opentopo --bbox -119.65 37.70 -119.50 37.80 --dataset USGS10m --size 1024

# Pull at US 1m LiDAR (OT+ subscription required; verified working)
python pipelines\terrain\import_dem.py --id half_dome_1m --source opentopo --bbox -119.540 37.740 -119.520 37.755 --dataset USGS1m --size 1024

# Tile-stitch a huge DEM (e.g. full Yosemite at 1m as 9-tile composite)
python pipelines\terrain\tile_stitch.py --id yosemite_full_1m --bbox -119.75 37.65 -119.40 37.90 --dataset USGS1m --rows 3 --cols 3 --size 4096

# Pull a regional STAC-only raster (ArcticDEM / REMA / LINZ — bypasses OT /globaldem)
python pipelines\terrain\fetch_regional_stac.py --id milford_1m --bbox 167.85 -44.70 167.95 -44.60 --provider linz

# Generate one AAA texture from a prompt (StableMaterials backend)
python pipelines\textures\aaa_texture.py --prompt "weathered cobblestone, mossy gaps" --id cobble --category Bricks --quality default
```

## Curated DEM presets

The OpenTopography wishlist at `art_lab/biomes/data_wishlist.json` ships 172 named regions across stitched / highres-open / showcase / premium / standard / bathymetric tiers. `bulk_pull.py --tier <name>` resumably fetches them. The biome / world-catalogue / region_pipeline machinery that consumed them is **gone** — those 222 cached TIFFs are now seed data for whatever new worldgen pipeline gets built.

# assetcreation
