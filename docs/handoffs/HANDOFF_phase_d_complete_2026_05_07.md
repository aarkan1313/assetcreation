# world3 Texture Pipeline — Phase D Complete Handoff (2026-05-07 evening)

**Branch:** main  
**Last commits:** `8ee6a94` (PIPELINE_DIRECTORY update), `ca171e9` (Phase D docs), `6e62b37` (B.5 aaa_pipeline.json fix)  
**Next work:** Phase C — iso/topdown scale review

---

## What was done this session

### Phase B — Upscaling + multi-resolution pipeline (DONE)

Full SR → bake → mip → per-tier QA pipeline wired and shipped. Key tools:

| Tool | What it does |
|------|-------------|
| `sr_upscale.py` | Real-ESRGAN x4plus via ComfyUI; offset+heal trick preserves tiling |
| `bake_pbr.py` | Re-derives normal/AO/roughness from upscaled height (avoids ESRGAN color artifacts on normal maps) |
| `mip_ladder.py` | Downsamples 2K master to 2K/1K/512 with per-map correct filtering (vector-field normals, gamma-aware albedo) |
| `texture_qa.py --ladder` | Per-tier QA + cross-tier contact sheet at `ladder/cross_tier_sheet.png` |
| `aaa_texture.py --ladder` | Stage 8: chains all of the above after the quality gate |

**Flagship:** `wgv3_rock_dark` full ladder shipped — all 3 tiers grade B (junction ratio increases at lower res as expected for high-contrast material; documented in TEXTURE_RND B.4).

**Key decisions locked in:**
- `--ladder` is opt-in (not default) — only for hero/strict materials
- `--working-res` is informational (Real-ESRGAN is fixed 4×; there is no `--size` flag in `sr_upscale.py`)
- Bake-by-default confirmed: ESRGAN misinterprets normal map RGB channels; baking from height is strictly better
- `chord_sm_rough` backend is the canonical choice for Rock-class hero materials (CHORD normals/height + SM roughness)
- `aaa_pipeline.json` always written in `finally` block even on ladder exception (fixed in 6e62b37)

**B.6 (alt SR backends):** deferred. Pursue only if a material class surfaces a gap.

---

### Phase D — Biome generalization (DONE — texture half)

The temperate_forest and grassland kits previously reused alpine textures (wrong biome). Now have purpose-built sets.

**temperate_forest kit** (anchor: `wgv3_tf_leaf_litter`):

| Slot | ID | Grade | Consistency |
|------|----|-------|-------------|
| grass/anchor | wgv3_tf_leaf_litter | B (2K: A) | — |
| dirt | wgv3_tf_loamy_soil | A | drift |
| rock_light | wgv3_tf_mossy_rock | A | drift |
| rock_dark | wgv3_tf_bark_rock | A | in_palette |
| snow/canopy | wgv3_tf_fern_ground | A | drift |

**grassland kit** (anchor: `wgv3_gl_tall_grass`):

| Slot | ID | Grade | Consistency |
|------|----|-------|-------------|
| grass/anchor | wgv3_gl_tall_grass | B (2K: A) | — |
| dirt | wgv3_gl_dry_thatch | B | in_palette |
| rock_light | wgv3_gl_hardpan_soil | A | in_palette |
| rock_dark | wgv3_gl_grass_rock | A | in_palette |
| snow | wgv3_gl_weathered_stone | B | drift |

**What "B (2K: A)" means for anchors:** The anchor textures run with `--ladder`. The base 512px grade is B (structural — leaf litter and savanna grass have high-frequency patterns that produce edge_mse just above the 0.005 strict threshold at 512px). The 2K ladder tier grades A — that is the in-engine render resolution. Same pattern as `wgv3_rock_dark` in B.4; documented in TEXTURE_RND Phase D entry.

**biome_kits.json updated:** `world3/jobs/biome_kits.json` — both kits now reference `wgv3_tf_*` / `wgv3_gl_*` IDs. All 5 kits have unique material sets.

**Phase D still open (Godot-side):**
- Region gallery recapture with all 5 kits visible (needs Phase C zoom levels first)
- Optional: alternate slot variants for visual variety (3 grass-types, randomized per region)

---

## State of key files

| File | Status |
|------|--------|
| `pipelines/textures/aaa_texture.py` | Full pipeline with `--ladder`, `--working-res`, `--ladder-tiers`, `--pbr-backend chord_sm_rough` |
| `pipelines/textures/texture_qa.py` | `--ladder` + `--ladder-dir` modes, cross-tier contact sheet |
| `pipelines/textures/sr_upscale.py` | Real-ESRGAN x4plus, offset+heal trick, fixed 4× scale |
| `pipelines/textures/bake_pbr.py` | Re-derive normal/AO/roughness at full SR resolution |
| `pipelines/textures/mip_ladder.py` | 2K→2K/1K/512 with per-map correct filtering |
| `pipelines/textures/palette_lock.py` | Kit generation with histogram-match LAB palette locking |
| `pipelines/textures/biome_consistency.py` | LAB delta + hue histogram intersection verdicts |
| `world3/jobs/biome_kits.json` | All 5 kits with purpose-built slot IDs |
| `pipelines/textures/TEXTURE_RND.md` | Phase D entry at top of Part 1; B.1–B.5 below it; Part 2 Cookbook |
| `world3/docs/ROADMAP.md` | Phase A done, Phase B done (B.6 deferred), Phase D 4/6 done |
| `pipelines/textures/TOOLS.md` | aaa_texture.py entry updated with --ladder flags |
| `pipelines/textures/RECIPES.md` | Hero recipe (--ladder --pbr-backend chord_sm_rough) added |
| `pipelines/textures/PIPELINE.md` | SR section updated to reflect Stage 8 wiring |
| `PIPELINE_DIRECTORY.md` | Texture row + recent activity updated |

All generated textures live in `world/textures/library/` which is **gitignored** (disk-only). The mip ladder lives under `world/textures/library/<id>/ladder/`.

---

## Phase C — what it is and where to start

**ROADMAP section:** `world3/docs/ROADMAP.md` → "Phase C — Iso/topdown scale review"

**The problem:** IsoCam and TopDownCam currently auto-frame to the AABB of the terrain mesh. They don't have a concept of "frame around a player position at a specific game-relevant zoom level." Phase C adds this.

**Checklist from ROADMAP:**
- [ ] Define target zoom levels (Iso ARPG ~30-50m diameter, Iso strategy ~200-500m, Topdown minimap ~10km, Topdown game-tile ~50m)
- [ ] Add "framing target" mode to IsoCam/TopDownCam — frame around a world position with configurable visible diameter
- [ ] "Player anchor" concept (a Vector3 the cameras can frame relative to)
- [ ] Decide: shared player anchor across walk/iso/topdown, or separate?
- [ ] Capture the same region at each zoom level for visual review

**Exit criteria:** Each game mode has 1-2 documented "good" framings with example captures; IsoCam/TopDownCam support both auto-AABB and framed-around-anchor modes.

**Where to look:** The camera scripts are in the `world3/` Godot project — grep for `IsoCam` or `TopDownCam`. Existing captures are in `world3/docs/captures/`. Screenshot tooling is `pipelines/godot_export/screenshot_scenes.py`.

**This is Godot GDScript work**, not Python pipeline work.

---

## Planned phase ordering

1. **Phase C** — iso/topdown scale review (next)
2. **Phase E** — per-game-mode material tuning (walk/iso/topdown get separate `terrain_blend_<kit>_<mode>.tres`)
3. **Phase D remainder** — region gallery recapture (needs Phase C zoom levels locked first)
4. **Phase F** — multi-tile / continuous world (long-term)

---

## How to run the texture pipeline

### Prerequisites

```powershell
$env:PYTHONIOENCODING = "utf-8"
cd D:/assets

# ComfyUI must be running on 127.0.0.1:8188
curl -fsS http://127.0.0.1:8188/system_stats
# If down:
& "D:\assets\animators\ComfyUI\venv\Scripts\python.exe" "D:\assets\animators\ComfyUI\main.py" --listen 127.0.0.1 --port 8188
```

### Generate a hero-quality material with full ladder

```powershell
python pipelines/textures/aaa_texture.py `
  --prompt "<cookbook prompt from TEXTURE_RND.md Part 2>" `
  --id <id> --category Rock `
  --quality strict --pbr-backend chord_sm_rough --ladder
```

### Generate a biome kit from scratch

```powershell
# Step 1: anchor with ladder
python pipelines/textures/aaa_texture.py `
  --prompt "<anchor prompt>" --id <kit>_anchor --category Ground `
  --quality strict --variants 6 --pbr-backend chord_sm_rough --ladder

# Step 2: palette-lock the rest (no --ladder for kit slots)
python pipelines/textures/palette_lock.py `
  --kit <name> --anchor <kit>_anchor `
  --quality strict --variants 4 --strength 0.6 `
  --add "<prompt>:<id>:<Category>" `
  --add "<prompt>:<id>:<Category>"

# Step 3: validate cohesion
python pipelines/textures/biome_consistency.py --anchor <kit>_anchor --candidates <id1> <id2>
```

---

## Known quirks

- **`--working-res` is informational** — Real-ESRGAN is fixed 4× scale; no `--size` flag in `sr_upscale.py`.
- **Base grade B on anchors is structural** — high-frequency materials (leaf litter, grass) land at B on 512px base (edge_mse ~0.006 vs 0.005 threshold). 2K ladder tier is A. Don't re-run to fix it.
- **Roughness near-zero variance on loam/clay** — StableMaterials is correct; those materials are physically low-variance. Sanity flag is advisory.
- **`passed_gate: false` in kit slots** — `palette_lock.py` uses `--no-gate` internally. Grade B meets the spec floor; strict gate requires A. Expected and correct.
- **`wgv3_gl_weathered_stone` periodic=150.2** — grey limestone is genuinely uniform. Not a generation failure.
- **Library is gitignored** — `world/textures/library/` does not appear in git. All maps live on disk only.

---

## Useful references

- `world3/docs/ROADMAP.md` — canonical phase tracker
- `pipelines/textures/TEXTURE_RND.md` — experiment log + prompt cookbook (Part 2)
- `pipelines/textures/TOOLS.md` — per-tool reference
- `pipelines/textures/RECIPES.md` — copy-paste commands
- `pipelines/textures/PIPELINE.md` — full pipeline mechanics
- `world3/jobs/biome_kits.json` — 5 biome kit definitions with slot IDs
