# Phase D — Biome Generalization (temperate_forest + grassland kits) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate purpose-built textures for the temperate_forest and grassland biome kits so all 5 kits have unique materials; update `biome_kits.json` to point at the new IDs; validate every kit with `biome_consistency.py`.

**Architecture:** Each kit gets an anchor texture generated fresh via `aaa_texture.py --ladder --quality strict --pbr-backend chord_sm_rough`, then the 4 remaining kit slots are generated and palette-locked to that anchor via `palette_lock.py`. After both kits are built, `biome_consistency.py --kit <name>` validates internal cohesion. `biome_kits.json` is updated in-place to wire the new IDs into the engine slots. Existing kits (alpine/desert/tundra) are untouched.

**Tech Stack:** Python 3.12, `aaa_texture.py`, `palette_lock.py`, `biome_consistency.py`, `biome_kits.json`, no new deps.

**Reading before starting:**
- `pipelines/textures/TEXTURE_RND.md` Part 2 (Cookbook) for prompt patterns and anti-patterns
- `world3/jobs/biome_kits.json` for current slot structure
- `world3/docs/ROADMAP.md` Phase D checklist

---

## Slot plan

### temperate_forest kit (anchor: `wgv3_tf_leaf_litter`)

| Slot | New ID | Prompt |
|------|--------|--------|
| grass | `wgv3_tf_leaf_litter` (anchor) | `forest floor covered in deciduous leaf litter, brown and orange oak leaves, damp humus soil visible below, top-down photo, even diffuse light, photoreal` |
| dirt | `wgv3_tf_loamy_soil` | `loamy forest soil, dark brown, slightly moist, small root fragments, no leaves, top-down photo, even diffuse light, photoreal` |
| rock_light | `wgv3_tf_mossy_rock` | `weathered granite rock surface, green moss patches, rough texture, outdoor forest, top-down photo, even diffuse light, photoreal` |
| rock_dark | `wgv3_tf_bark_rock` | `dark weathered basalt rock, surface cracked and stained, forest environment, no vegetation, top-down photo, even diffuse light, photoreal` |
| snow | `wgv3_tf_fern_ground` | `dense low fern undergrowth, green fronds, forest floor, dappled texture, top-down photo, even diffuse light, photoreal` |

### grassland kit (anchor: `wgv3_gl_tall_grass`)

| Slot | New ID | Prompt |
|------|--------|--------|
| grass | `wgv3_gl_tall_grass` (anchor) | `tall savanna grass, golden-yellow, dry season, close-packed stems, top-down photo, even diffuse light, photoreal` |
| dirt | `wgv3_gl_dry_thatch` | `dry thatch and dead grass mat, tan and beige, slightly compacted, open plains, top-down photo, even diffuse light, photoreal` |
| rock_light | `wgv3_gl_hardpan_soil` | `hardpan cracked clay soil, pale tan, shallow surface cracks, semi-arid grassland, no vegetation, top-down photo, even diffuse light, photoreal` |
| rock_dark | `wgv3_gl_grass_rock` | `dark weathered volcanic rock embedded in dry grass, rough surface, savanna, top-down photo, even diffuse light, photoreal` |
| snow | `wgv3_gl_weathered_stone` | `pale weathered limestone or sandstone surface, worn smooth, light grey, grassland hilltop, top-down photo, even diffuse light, photoreal` |

---

## Prompt notes (apply Phase A learnings)

- **No directional cues** in prompts (`top-down photo, even diffuse light` is in every prompt — never `sunlit from north`, `in afternoon light`, etc.)
- **No rare jargon** names (`deciduous leaf litter` not `quercus detritus`)
- **No mismatched substrate descriptors** (fern slot says `dappled texture` not `rocky ground`)
- **Contrast slots** (`rock_dark` in temperate_forest, `grass_rock` in grassland) are intentionally darker than the anchor — `biome_consistency.py` will flag them `way_off`; that is expected and correct

---

## File structure

| File | Status | Responsibility |
|------|--------|----------------|
| `world3/jobs/biome_kits.json` | MODIFY | Update temperate_forest + grassland slot IDs to new wgv3_ IDs; update anchors |
| `pipelines/textures/TEXTURE_RND.md` | MODIFY | Prepend Phase D entry (what generated, grades, consistency verdicts) |
| `world3/docs/ROADMAP.md` | MODIFY | Check off Phase D checklist items |

Generated textures live in `world/textures/library/` (gitignored disk-only). No new Python files.

---

## Task 1: Generate temperate_forest anchor — `wgv3_tf_leaf_litter`

**Files:**
- Read: `world/textures/library/wgv3_tf_leaf_litter/` (output dir, check if exists)
- Read: `world/textures/library/wgv3_tf_leaf_litter/aaa_pipeline.json` (verify when done)

- [ ] **Step 1: Check if anchor already exists**

```powershell
Test-Path "d:\assets\world\textures\library\wgv3_tf_leaf_litter"
```

If it already exists and `aaa_pipeline.json` shows grade A or B, skip to Step 3. Otherwise continue.

- [ ] **Step 2: Generate anchor via aaa_texture.py --ladder**

```powershell
cd d:\assets
python pipelines/textures/aaa_texture.py `
  --prompt "forest floor covered in deciduous leaf litter, brown and orange oak leaves, damp humus soil visible below, top-down photo, even diffuse light, photoreal" `
  --id wgv3_tf_leaf_litter `
  --category Ground `
  --quality strict `
  --variants 6 `
  --pbr-backend chord_sm_rough `
  --ladder
```

Expected output: all 3 tier grades A or B in `ladder.tier_grades`; no `sanity ok=False` that blocks. If gate fails, re-run with `--no-gate` to inspect and iterate prompt.

- [ ] **Step 3: Verify output**

```powershell
Get-Content "d:\assets\world\textures\library\wgv3_tf_leaf_litter\aaa_pipeline.json" | python -c "import json,sys; d=json.load(sys.stdin); print('grade:', d.get('seam_grade')); print('ladder:', d.get('ladder', {}).get('tier_grades'))"
```

Expected: `grade: A` or `B`; `ladder: {'2k': 'A'/'B', '1k': ..., '512': ...}`.

- [ ] **Step 4: Commit**

```powershell
cd d:\assets
git add world3/
git commit -m "phase D: generate wgv3_tf_leaf_litter anchor (temperate_forest kit)"
```

---

## Task 2: Generate remaining temperate_forest kit textures via palette_lock.py

**Files:**
- Read: `world/textures/library/wgv3_tf_loamy_soil/` (output, check grade)
- Read: `world/textures/library/wgv3_tf_mossy_rock/` (output, check grade)
- Read: `world/textures/library/wgv3_tf_bark_rock/` (output, check grade)
- Read: `world/textures/library/wgv3_tf_fern_ground/` (output, check grade)

- [ ] **Step 1: Run palette_lock.py for the 4 remaining temperate_forest slots**

```powershell
cd d:\assets
python pipelines/textures/palette_lock.py `
  --kit temperate_forest `
  --anchor wgv3_tf_leaf_litter `
  --quality strict `
  --variants 4 `
  --strength 0.6 `
  --add "loamy forest soil, dark brown, slightly moist, small root fragments, no leaves, top-down photo, even diffuse light, photoreal:wgv3_tf_loamy_soil:Ground" `
  --add "weathered granite rock surface, green moss patches, rough texture, outdoor forest, top-down photo, even diffuse light, photoreal:wgv3_tf_mossy_rock:Rock" `
  --add "dark weathered basalt rock, surface cracked and stained, forest environment, no vegetation, top-down photo, even diffuse light, photoreal:wgv3_tf_bark_rock:Rock" `
  --add "dense low fern undergrowth, green fronds, forest floor, dappled texture, top-down photo, even diffuse light, photoreal:wgv3_tf_fern_ground:Ground"
```

Expected: each slot generates, palette-matches, re-runs QA, and prints `catalog refreshed for wgv3_tf_<name>`.

- [ ] **Step 2: Check biome_consistency on temperate_forest kit**

Biome consistency checks whether each slot's albedo is color-family-compatible with the anchor. The contrast slots (bark_rock) are *expected* to be `way_off` — that's correct.

```powershell
cd d:\assets
python pipelines/textures/biome_consistency.py `
  --anchor wgv3_tf_leaf_litter `
  --candidates wgv3_tf_loamy_soil wgv3_tf_mossy_rock wgv3_tf_bark_rock wgv3_tf_fern_ground
```

Expected verdicts:
- `wgv3_tf_loamy_soil`: `in_palette` or `drift` (acceptable)
- `wgv3_tf_mossy_rock`: `in_palette` or `drift` (acceptable — green/grey rock near leaf-litter browns)
- `wgv3_tf_bark_rock`: `way_off` expected (intentional dark contrast slot)
- `wgv3_tf_fern_ground`: `in_palette` or `drift` (acceptable — green ferns near brown litter)

If any of `loamy_soil`, `mossy_rock`, or `fern_ground` returns `way_off`, regenerate that slot (re-run `aaa_texture.py` directly and re-apply palette match).

- [ ] **Step 3: Record verdicts for TEXTURE_RND.md**

Note the exact verdicts printed. They go into the Phase D entry in Task 5.

- [ ] **Step 4: Commit**

```powershell
cd d:\assets
git add world3/
git commit -m "phase D: generate temperate_forest kit (4 palette-locked slots)"
```

---

## Task 3: Generate grassland anchor — `wgv3_gl_tall_grass`

**Files:**
- Read: `world/textures/library/wgv3_gl_tall_grass/` (output dir)
- Read: `world/textures/library/wgv3_gl_tall_grass/aaa_pipeline.json`

- [ ] **Step 1: Check if anchor already exists**

```powershell
Test-Path "d:\assets\world\textures\library\wgv3_gl_tall_grass"
```

If it exists with grade A or B, skip to Step 3.

- [ ] **Step 2: Generate anchor**

```powershell
cd d:\assets
python pipelines/textures/aaa_texture.py `
  --prompt "tall savanna grass, golden-yellow, dry season, close-packed stems, top-down photo, even diffuse light, photoreal" `
  --id wgv3_gl_tall_grass `
  --category Ground `
  --quality strict `
  --variants 6 `
  --pbr-backend chord_sm_rough `
  --ladder
```

Grass is one of the documented Phase A "variance-sensitive" materials. If the seam grade fails, try `--variants 6 --seed-base 100` and re-run. Do not use `aerial-photograph-of-field` or species names in the prompt (Phase A anti-patterns).

- [ ] **Step 3: Verify output**

```powershell
Get-Content "d:\assets\world\textures\library\wgv3_gl_tall_grass\aaa_pipeline.json" | python -c "import json,sys; d=json.load(sys.stdin); print('grade:', d.get('seam_grade')); print('ladder:', d.get('ladder', {}).get('tier_grades'))"
```

- [ ] **Step 4: Commit**

```powershell
cd d:\assets
git add world3/
git commit -m "phase D: generate wgv3_gl_tall_grass anchor (grassland kit)"
```

---

## Task 4: Generate remaining grassland kit textures via palette_lock.py

**Files:**
- Outputs: `world/textures/library/wgv3_gl_dry_thatch/`, `wgv3_gl_hardpan_soil/`, `wgv3_gl_grass_rock/`, `wgv3_gl_weathered_stone/`

- [ ] **Step 1: Run palette_lock.py for the 4 remaining grassland slots**

```powershell
cd d:\assets
python pipelines/textures/palette_lock.py `
  --kit grassland `
  --anchor wgv3_gl_tall_grass `
  --quality strict `
  --variants 4 `
  --strength 0.6 `
  --add "dry thatch and dead grass mat, tan and beige, slightly compacted, open plains, top-down photo, even diffuse light, photoreal:wgv3_gl_dry_thatch:Ground" `
  --add "hardpan cracked clay soil, pale tan, shallow surface cracks, semi-arid grassland, no vegetation, top-down photo, even diffuse light, photoreal:wgv3_gl_hardpan_soil:Ground" `
  --add "dark weathered volcanic rock embedded in dry grass, rough surface, savanna, top-down photo, even diffuse light, photoreal:wgv3_gl_grass_rock:Rock" `
  --add "pale weathered limestone or sandstone surface, worn smooth, light grey, grassland hilltop, top-down photo, even diffuse light, photoreal:wgv3_gl_weathered_stone:Rock"
```

- [ ] **Step 2: Check biome_consistency on grassland kit**

```powershell
cd d:\assets
python pipelines/textures/biome_consistency.py `
  --anchor wgv3_gl_tall_grass `
  --candidates wgv3_gl_dry_thatch wgv3_gl_hardpan_soil wgv3_gl_grass_rock wgv3_gl_weathered_stone
```

Expected verdicts:
- `wgv3_gl_dry_thatch`: `in_palette` (golden-tan, close to anchor)
- `wgv3_gl_hardpan_soil`: `in_palette` or `drift` (pale tan — similar range)
- `wgv3_gl_grass_rock`: `way_off` expected (intentional dark contrast)
- `wgv3_gl_weathered_stone`: `drift` or `way_off` (grey — lighter than anchor)

If `dry_thatch` or `hardpan_soil` returns `way_off`, regenerate that slot.

- [ ] **Step 3: Record verdicts for TEXTURE_RND.md**

Note exact verdicts.

- [ ] **Step 4: Commit**

```powershell
cd d:\assets
git add world3/
git commit -m "phase D: generate grassland kit (4 palette-locked slots)"
```

---

## Task 5: Update biome_kits.json + docs

**Files:**
- Modify: `world3/jobs/biome_kits.json`
- Modify: `pipelines/textures/TEXTURE_RND.md`
- Modify: `world3/docs/ROADMAP.md`

### Step 1: Update biome_kits.json

Read the current file, then rewrite the `temperate_forest` and `grassland` entries. The changes are:

- [ ] **Edit `world3/jobs/biome_kits.json`**

`temperate_forest` new slots:
```json
"temperate_forest": {
  "description": "Lowland forest with bare rock peaks. Forest floor low, grass/dirt mid, rock above tree line.",
  "anchor": "wgv3_tf_leaf_litter",
  "slots": {
    "grass": "wgv3_tf_leaf_litter",
    "dirt": "wgv3_tf_loamy_soil",
    "rock_light": "wgv3_tf_mossy_rock",
    "rock_dark": "wgv3_tf_bark_rock",
    "snow": "wgv3_tf_fern_ground"
  },
  "height_bands": {
    "_comment": "Tree line (rock takes over) is around 60-70% elevation in temperate latitudes.",
    "h_grass_dirt": 0.30,
    "h_dirt_rockdark": 0.65,
    "h_rockdark_snow": 0.90
  },
  "slope_threshold": 0.45,
  "regions": ["med_california_chaparral", "tdf_yucatan_mexico", "tmf_amazon_brazil"]
}
```

`grassland` new slots:
```json
"grassland": {
  "description": "Open plains with subtle relief. Mostly grass + dirt; rock only on rare hilltops.",
  "anchor": "wgv3_gl_tall_grass",
  "slots": {
    "grass": "wgv3_gl_tall_grass",
    "dirt": "wgv3_gl_dry_thatch",
    "rock_light": "wgv3_gl_hardpan_soil",
    "rock_dark": "wgv3_gl_grass_rock",
    "snow": "wgv3_gl_weathered_stone"
  },
  "height_bands": {
    "h_grass_dirt": 0.40,
    "h_dirt_rockdark": 0.75,
    "h_rockdark_snow": 0.95
  },
  "slope_threshold": 0.50,
  "regions": ["tgr_great_plains_usa", "tgs_serengeti_tanzania", "mgs_tibetan_plateau", "fgs_pantanal_brazil"]
}
```

- [ ] **Step 2: Prepend Phase D entry to TEXTURE_RND.md**

Prepend to Part 1 (after the `## B.5` entry or as the new first entry). Fill in the actual grades and consistency verdicts from Tasks 2/4:

```markdown
## Phase D — Biome generalization: temperate_forest + grassland kits (2026-05-07)

**What:** Generated purpose-built textures for the two missing biome kits. Previously
both reused alpine slots (rock_dark, grass, etc.), making California chaparral and
Serengeti regions render with alpine materials.

**temperate_forest kit:**
| Slot | ID | Grade | Consistency |
|------|----|-------|-------------|
| grass (anchor) | wgv3_tf_leaf_litter | <grade> | — |
| dirt | wgv3_tf_loamy_soil | <grade> | <verdict> |
| rock_light | wgv3_tf_mossy_rock | <grade> | <verdict> |
| rock_dark | wgv3_tf_bark_rock | <grade> | way_off (expected — contrast slot) |
| snow | wgv3_tf_fern_ground | <grade> | <verdict> |

**grassland kit:**
| Slot | ID | Grade | Consistency |
|------|----|-------|-------------|
| grass (anchor) | wgv3_gl_tall_grass | <grade> | — |
| dirt | wgv3_gl_dry_thatch | <grade> | <verdict> |
| rock_light | wgv3_gl_hardpan_soil | <grade> | <verdict> |
| rock_dark | wgv3_gl_grass_rock | <grade> | way_off (expected — contrast slot) |
| snow | wgv3_gl_weathered_stone | <grade> | <verdict> |

**Prompting:** Applied Phase A learnings throughout. No directional cues, no rare
jargon names, `top-down photo, even diffuse light, photoreal` in every prompt.
Variance-sensitive anchor slots ran at 6 variants; kit slots at 4.

**biome_kits.json updated:** Both kits now reference purpose-built IDs.
All 5 kits have unique material sets.
```

Replace `<grade>` and `<verdict>` with actual values recorded in Tasks 2 and 4.

- [ ] **Step 3: Update ROADMAP.md Phase D checklist**

Check off the completed items in `world3/docs/ROADMAP.md`:

```markdown
- [x] Generate temperate_forest kit (5 textures, palette-locked).
      wgv3_tf_leaf_litter (anchor) / wgv3_tf_loamy_soil / wgv3_tf_mossy_rock /
      wgv3_tf_bark_rock / wgv3_tf_fern_ground. All at grade A or B.
- [x] Generate grassland kit (5 textures, palette-locked).
      wgv3_gl_tall_grass (anchor) / wgv3_gl_dry_thatch / wgv3_gl_hardpan_soil /
      wgv3_gl_grass_rock / wgv3_gl_weathered_stone. All at grade A or B.
- [x] Apply Phase A learnings (better prompts, better settings) so
      these kits ship at higher first-pass quality than desert/tundra.
- [x] Re-run biome_consistency on every kit. Document the verdict table.
- [ ] Re-capture region gallery with all 5 kits visible. Verify each
      region renders with appropriate biome.
- [ ] Optional: generate alternate variants of a slot for visual
      variety (3 grass-types in the grassland kit, randomized per
      region).
```

The gallery recapture item stays unchecked — it's a Godot-side task that requires a full scene render pass, not something the texture pipeline does. Flag it as a remaining item for a follow-up session.

- [ ] **Step 4: Commit all doc + json changes**

```powershell
cd d:\assets
git add world3/jobs/biome_kits.json pipelines/textures/TEXTURE_RND.md world3/docs/ROADMAP.md
git commit -m "phase D: update biome_kits.json + docs (temperate_forest + grassland kits complete)"
```

---

## Self-review

**Spec coverage:**
- ✅ 5 temperate_forest textures (anchor + 4 via palette_lock)
- ✅ 5 grassland textures (anchor + 4 via palette_lock)
- ✅ Phase A prompting learnings applied (no directional cues, no rare jargon)
- ✅ biome_consistency run on both kits
- ✅ biome_kits.json updated to new IDs
- ✅ TEXTURE_RND.md Phase D entry
- ✅ ROADMAP.md Phase D checklist updated
- ⚠️ Region gallery recapture — deferred (Godot-side, out of texture pipeline scope); item left unchecked in ROADMAP

**Placeholder scan:** `<grade>` and `<verdict>` in TEXTURE_RND.md entry are intentional runtime fill-ins (the actual grades aren't known until generation runs). The instructions in Task 5 Step 2 tell the implementer to fill them in from recorded values.

**Type consistency:** All IDs use the `wgv3_tf_*` / `wgv3_gl_*` prefix consistently across the slot plan, the palette_lock commands, the biome_kits.json JSON, and the TEXTURE_RND table.

**Dependency order:** Task 1 (anchor) must complete before Task 2 (palette_lock references anchor). Task 3 (anchor) before Task 4. Task 5 can run after Tasks 2 and 4.
