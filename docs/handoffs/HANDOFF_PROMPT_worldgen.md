# Worldgen handoff prompt

Copy this into a fresh chat to pick up where we left off. References the existing workflow docs rather than restating them.

---

Continuing **D:\assets** worldgen lane (Godot 4.5 / TLTE asset factory).

**Read first** (these are the source of truth — don't restate, follow):

- `HANDOFF_2026_05_06_PM5_worldgen_swappoints.md` — most recent session state + open bug
- `../worldgen_v1/WORLDGEN_ARCHITECTURE.md` — pipeline audit, swap-point status, Phase 1/2/3 plan (v1-era)
- `../worldgen_v1/WORLDGEN_QUALITY.md` — knobs A/B/C/D + reserved knob E (Mikkelsen hex-tile) (v1-era)
- `../reference/OPENTOPO_API.md` — OpenTopography surface, OT+ tier matrix, regional-raster STAC unlock
- `../../art_lab/biomes/regions/README.md` — `region.config.v1` schema reference
- `../../PIPELINE_DIRECTORY.md` + `../../PIPELINE_GUIDE.md` + `../plans/ROADMAP.md` — wider factory context
- `../plans/EXPANSION_PLAN.md` — cross-pipeline plan (worldgen is one lane of many)

**Pre-flight every shell:**
```powershell
$env:OPENTOPOGRAPHY_API_KEY = [Environment]::GetEnvironmentVariable("OPENTOPOGRAPHY_API_KEY", "User")
```

**State summary:** Phase 1 worldgen swap-points landed (shader registry, splat mode, terrain extents, `region.config.v1` walker). 222 cached DEMs, OT+ Pro active, 23 marquee Godot scenes on legacy 512×64 scale all working at the `topdown` shader preset. Open bug: `--use-real-extents` mode produces correct .tscn node tree but renders mostly-empty in Godot — debugging notes + priority fixes in PM5 handoff.

**Lanes I do NOT touch:** `../../pipelines/{props,game_data,audio,ui,vfx}/`, `../../world/props/`, `biome_scatter_rules.json` (other Build chats own these).

**Likely next moves** (pick one):
1. Fix `--use-real-extents` open bug per PM5 handoff's priority list (camera far-plane is top suspect)
2. Phase 2 quality wins — start with `biome_terrain_hextile.gdshader` (Mikkelsen 2022; public Godot 4 port) per ../worldgen_v1/WORLDGEN_QUALITY.md knob E
3. Polish + breadth on legacy-scale scenes (forget real-extents for now)
4. Whatever the user asks for

Ask the user what they want to focus on. Don't redo work — read the handoffs first.
