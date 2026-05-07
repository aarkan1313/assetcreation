# D:\assets — Asset Factory

Self-generated AAA-grade assets for **Godot 4.5 / JK Engine / TLTE**. Everything from prompt to ready-to-import Godot resource lives here.

## Doc map

Open these in order if you're new:

| Doc | What it's for |
|---|---|
| [DOCS_INDEX.md](DOCS_INDEX.md) | **Canonical doc-ownership map** — which doc owns what, where to update first |
| [PIPELINE_DIRECTORY.md](PIPELINE_DIRECTORY.md) | **Live status table** — what works today, in one page |
| [PIPELINE_GUIDE.md](PIPELINE_GUIDE.md) | **Walkthroughs** — copy-paste recipes for every workflow |
| [TOOLS_INDEX.md](TOOLS_INDEX.md) | **Tool directory** — every script + env + quick-reference table |
| [docs/plans/ROADMAP.md](docs/plans/ROADMAP.md) | **What's next** — current focus + priorities + parity scorecard |
| [docs/plans/EXPANSION_PLAN.md](docs/plans/EXPANSION_PLAN.md) | **Living checklist** — phased plan + per-phase punch lists + decision log |
| [docs/audits/REVIEW.md](docs/audits/REVIEW.md) | Pipeline post-mortems (bugs found + fixed, REVIEW-discipline format) |
| [docs/plans/RESEARCH_HANDOFF.md](docs/plans/RESEARCH_HANDOFF.md) | Briefs for sub-agents researching SOTA per category |
| [research/](research/) | Returned reports (A terrain, B textures, C/C2 VFX, D UI, E/E2 audio, F/F2 game data, G deep dive, J2 props, K open-weights) |
| [docs/reference/OPENTOPO_API.md](docs/reference/OPENTOPO_API.md) | **Full OpenTopography API reference** — 3944 datasets, all endpoints, bbox limits, rate limits |
| [docs/reference/CLOUD_KEYS.md](docs/reference/CLOUD_KEYS.md) | **Cloud env-var index** — every `*_API_KEY` we read, what tool it activates, fallback when missing |
| [docs/plans/LONG_TERM_VISION.md](docs/plans/LONG_TERM_VISION.md) | Multi-month directional intent for the asset factory |
| `docs/handoffs/HANDOFF_phase11_props_2026_05_06.md` | Phase 11 props deep-dive (latest props snapshot; supersedes `HANDOFF_props_v2`) |
| `docs/handoffs/HANDOFF_phase12_audio_2026_05_06.md` | Phase 12 audio deep-dive — real Stable Audio Open 1.0 bake on all 10 biomes (latest audio snapshot; supersedes `HANDOFF_audio_v3`) |
| `HANDOFF_<pipeline>_<v>_2026_05_06.md` | Older per-pipeline build snapshots (ui v3, vfx v2, game_data v2, phase9, audit_expand). Kept for forensics. |
| `docs/audits/AUDIT_2026_05_07.md` | Most recent project-state audit (drift flags + reconciliation TODO list). |
| `_archive/` | Superseded handoffs, old audits, orphan research. Historical only — never edit. |

**Current focus:** Phase 11 (props) + Phase 12 (audio) deep-dives both **complete** as of 2026-05-06 PM.

**Next-step menu** (pick one; see [ROADMAP](docs/plans/ROADMAP.md) "What comes next" for details):
- **A.** Phase 13 — VFX GPU baker deep-dive (parallels Phase 11/12). ~half day.
- **B.** Worldgen v2 status check + push. ~30-90 min. Unblocks scene integration if v2 is close.
- **C.** Small closeouts: listen-test Phase 12 audio, re-export to Godot import, multi-prop test. ~30 min.

**Active blocker:** worldgen v1 broke 2026-05-06; v2 rebuild lives at `pipelines/worldgen_v2/`. Blocks scene-integration of Phase 11 props + Phase 12 ambience.

## What's in here (highest level)

```
D:\assets\
├── meshy/             Character pipeline (Meshy API + preprocess + bake + atlas)
├── animators/         AI rigging/animation/generation tools (each in own venv)
├── pipelines/         Non-character pipelines (terrain, textures, world maps, godot export)
├── art_lab/           Magic/World Art Lab (shaders, maps, biomes — first-party)
├── world/             Outputs: terrain bundles, texture library, world maps
├── characters/        Reserved for future character outputs
├── godot_pack/        Godot exporter output — drop into a Godot 4.5 project
└── research/          Returned research reports
```

## Today's state (one paragraph)

**22+ working pipelines, all 5 formerly-vapor categories shipped v2/v3 SOTA. Phase 11 (props) + Phase 12 (audio) deep-dives complete as of 2026-05-06 PM.** Coverage on disk (verified by `docs/audits/AUDIT_2026_05_07.md`): **51 props** (was 24 v2; +1 Phase 11 hero obelisk) with 4-tier LOD + CoACD collision + AAA-PBR binding + AI route adapters (Trellis2 default, HY3D-2.1 fallback); 135 icons + 28 HUD scenes; 39 sounds / 112 SFX variants + **142 real Stable Audio Open ambience stems across 10 biomes** (Phase 12, not dry-run anymore — 56 MB of real audio); 57 effect.json entries (46 in current catalog + 11 migrated legacy, 4 export targets, volumetric_fog backend, MeshTrail3D + AudioCueBus runtime); 14/14 game_data records round-trip + balance TOML + kill-dummy sim + DuckDB reports + Yarn link validator. **10 biomes** registered. The world-gen stack reached maturity at v1 then **broke and is rebuilding at `pipelines/worldgen_v2/` (milestone 1, terrain only)**. Character pipeline (Meshy → 5 riggers → animate → bake → atlas, ~33 GLBs) is mature and unaffected. **Reframe (2026-05-06 PM):** the assets being produced today are **mostly throwaway** — except possibly the characters. The point is to figure out which pipelines work, not to build a content library. **The honest drag now**: cross-pipeline seams partly proven (Phase 10A scatter v3 prop_pool path landed + spawn-on-terrain raycast landed; one-button "biome + props + ambience + VFX + HUD" demo NOT yet built); several **pipelines not yet built** (cinematics / quest / save-load / localization / performance budgets / cross-pipeline gallery); **remaining GPU flips queued** (FLUX schnell + LoRA, Taichi VFX, Hunyuan3D-Omni, F5-TTS, vLLM, Wan, YuE — Stable Audio + Trellis2 done in Phase 11/12). Real content authoring is gated on user intent, not pipeline readiness.

## One-command starting points

```powershell
# Pre-flight (each new shell): make the env var available to subprocesses.
# OT+ tier active 2026-05-06: All Access (USGS 1m unlocked), 400 calls/24h.
$env:OPENTOPOGRAPHY_API_KEY = [Environment]::GetEnvironmentVariable("OPENTOPOGRAPHY_API_KEY", "User")

# THE BIG ONE: real DEM → fantasy style → biome paint → AAA bind → 3 Godot scenes
python pipelines\terrain\region_pipeline.py `
  --preset bryce_hoodoo --style spired --strength 1.5 `
  --biomes mana_crystal,mana_crystal,grassland,grassland `
  --id spire_garden --project C:\Users\josep\test\new-game-project --size 1024

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

# Apply a fantasy style to an existing heightmap
python pipelines\terrain\dem_fantasy_edit.py --in <bundle>/height_16.png --out fantasy.png --style mythic --strength 1.2

# Generate one AAA texture from a prompt (StableMaterials backend)
python pipelines\textures\aaa_texture.py --prompt "weathered cobblestone, mossy gaps" --id cobble --category Bricks --quality default

# Build a synthetic mountain terrain with hydraulic erosion
python pipelines\terrain\terrain_bundle.py --id alpine_a --biome mountains --erosion 60 --erosion-mode hydraulic

# Build a strategic political world map (settlements, factions, rivers, labels)
python art_lab\maps\generators\generate_world_map.py --id mythos_a --size 1024 --seed 7
```

## Curated starter recipes

`art_lab/biomes/world_catalogue.json` ships 10 known-good `(preset × style × biome-mix)` combos: `frostfang_fjord`, `embercaldera`, `spire_garden`, `stormhalls`, `obsidian_mesas`, `skyforest`, `alpenheart`, `endless_dunes`, `kami_alps`, `the_titansteps`. Each is a one-line `region_pipeline.py` command — copy and run.

# assetcreation
