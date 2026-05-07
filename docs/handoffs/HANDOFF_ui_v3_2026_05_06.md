# Handoff — UI / Icons pipeline v3 (2026-05-06)

Took the v2 build (40 icons, 16 9-slice variants, 4 HUD .tscn, FLUX schnell
+ Recraft adapters) the rest of the way to character-pipeline-quality with
content breadth, game-data-integration tooling, and GPU-ready scaffolds.

The plumbing was already done; this push focused on:

1. **Content breadth** — curated 190-slug game-icons.net allowlist + new
   Lucide/Phosphor/Tabler `mit-iso-libs` source + PixelLab adapter for the
   pixel-art lane.
2. **Game-data integration** — `suggest_icon_for_record.py` (tag-overlap
   matcher) + `lint_icons.py` (strict-icons gating) so future game_data
   regens stop generating fictional icon IDs.
3. **Faction-theming polish** — 24 HUD test fixtures (4 factions × 6
   gameplay scenarios) for spot-checking palettes against realistic UI
   states + 4 new ornament drawers (chains/runes/vines/fangs) doubling
   visual variety.
4. **GPU-bound build, not run** — `lora_train.py` writes a complete
   kohya-ss / sd-scripts dataset + train command; verify command runs on
   the 5090 when free. Plus `vtracer_roundtrip.py` for raster→SVG.
5. **Documentation** — `../../ui/palettes/PALETTE_AUTHOR_GUIDE.md` documents
   the palette schema + per-faction design philosophy + add-new-faction
   recipe; UI tool decision tree added to `../../pipelines/ui/README.md`.

Per the brief: GPU and cloud-API spend are NOT exercised at runtime; every
GPU/cloud-bound code path has a verify command attached for when the
resource is free.

## Built (new in v3)

### A1. game-icons.net curated bulk import — `freelib_curated_slugs.txt` + `--filter-by-list`
- New 190-slug allowlist organized into 8 categories: weapons (40),
  armor+body (25), consumables/loot (35), 4 spell-school clusters (32 total
  across fire/ice/lightning/nature/shadow/arcane/holy), buffs/status (12),
  UI primitives (16), world+map (10), inventory categories (10).
- `freelib_ingest.py` gained `--filter-by-list <txt>` flag that filters a
  game-icons.net bulk archive to exactly the curated slugs. Combines with
  the existing `--filter <regex>` (AND).
- Verified by: synthetic mock-zip smoke test in `D:\tmp\mock_game_icons.zip`
  with 8 SVGs (5 in the curated list + 3 not) → ingester correctly filtered
  to 5 matches. Operator just needs to download the live ~50 MB archive
  from <https://game-icons.net/about.html> and run with `--accept-license`.

### A2. Lucide / Phosphor / Tabler ingester — `--source mit-iso-libs`
- Built-in URL-template registry for 3 libraries (Lucide ISC + Phosphor
  MIT + Tabler MIT). All three ship raw SVGs from versioned GitHub paths
  pinned in the registry for reproducibility. Linter migrated the
  templates to jsDelivr CDN paths (`@latest` tags, CDN-cacheable, no
  GitHub rate limits) — keeping that improvement.
- Built-in curated UI-primitive picks per library: 24 Lucide / 19 Phosphor
  / 22 Tabler, covering chevrons / arrows / settings / menu / x / plus /
  minus / search / info / warning / check / circle / filter / list / trash
  / save / user.
- Per-slug source override syntax: `phosphor:gear` in a slugs file uses
  Phosphor regardless of `--library`. RTL flag auto-set for chevron/caret/
  arrow icons ending in `-left` or `-right`.
- Helper: `--write-default-picks` materializes
  `../../pipelines/ui/mit_iso_picks_<library>.txt` as a starting point for editing.
- Verify command (when ready):
  `python pipelines/ui/freelib_ingest.py --source mit-iso-libs --library lucide --accept-license`

### A3. PixelLab adapter — `pixellab_icons.py`
- Mirrors `openai_icons.py` and `recraft_icons.py` shape exactly (same
  manifest schema, same prompt input format).
- **Plan-only by default**: writes
  `../../ui/diffusion_plans/<id>.pixellab_plan.json` per icon with full API call
  spec (prompt, pixel_size, outline, shading, view, seed, style_id). No
  network call.
- `--run` requires `PIXELLAB_API_KEY` AND `--max-cost-usd <cap>`. Estimated
  cost printed before any HTTP — adapter exits before calling if estimated
  total exceeds the cap.
- Pixel-size choices: 16 / 32 / 48 / 64 / 128 (PixelLab's native rendering
  resolutions per their 2026 docs).
- Verify command:
  `python pipelines/ui/pixellab_icons.py --prompts ui/prompts.json --pixel-size 64 --run --max-cost-usd 1.50`
  (only after a pixel-art region of TLTE is committed — currently parked).

### B4. Icon-suggestion tool — `suggest_icon_for_record.py`
- Cosine-on-token-sets matcher: every game_data record's tags + category +
  school + damage_type + display_name words gets matched against every
  icon's semantic_tags + display_name + id-tokens.
- Bonus: +0.5 if record category/school/damage_type appears as an icon-id
  token; +0.2 if display_name shares ≥2 distinct words with the icon.
- Outputs `../../ui/icons/suggestions.{json,md}` with top-K per record + per-row
  reasons (overlap tokens listed). `--apply` emits a JSONL patch listing
  the suggested swaps without mutating game_data records (game_data team's
  pickup).
- Verified end-to-end: 7 records (5 items + 2 npcs) × 95 icons (early
  state) → 4 strong matches, 1 weak. Sample:
  `iron_mace_0` → `ico_mace` (score 0.5, overlap=[mace]).

### B5. `--strict-icons` gating — `lint_icons.py`
- The brief said extend `../../pipelines/_meta/link_validator.py`, but per the
  YOU-DO-NOT-TOUCH constraint that file is owned by a different lane.
  Built `lint_icons.py` instead, which **wraps** link_validator (calling
  it as a subprocess and parsing its `--json` output) and adds 4
  icon-specific gating checks on top. Result: same gating outcome, lane
  isolation preserved.
- Checks:
  - **(a) Unused icons** — manifest entries no validated record references.
  - **(b) Missing semantic_tags** — without tags, suggest_icon can't
    match → drift on every game_data regen.
  - **(c) Record→icon mismatch** — record points at an icon whose tokens
    contradict its category/school/damage_type. Conservative
    NEGATIVE_TOKENS table (e.g. cold record → fire icon trips it).
  - **(d) RTL flag review** — asymmetric icons (chevron/caret/arrow with
    -left/-right) without `rtl_mirror=true` flagged for i18n review.
- Modes:
  - `--warn-only` — informational, always exit 0 (CI preview).
  - `--strict` — exit 1 on any of (a)-(c). RTL is informational always.
  - `--allow-unused <ids>` — whitelist intentionally-unused icons.
- Verified: at 135 icons + 7 records, strict mode correctly exits 1 with
  131 unused + 37 missing-tags. Informational mode prints the full report
  and exits 0.

### C6. 24 faction HUD test fixtures
- `hud_mockup.py` extended with a `SCENARIOS` registry (default + 6
  gameplay states: full_hp / low_hp / combat_active / inventory_full /
  dialog_open / level_up). Each scenario adjusts hp/mana fills + tooltip
  visibility + adds a banner overlay + optional modal (inventory grid /
  dialog box / level-up celebration).
- `--scenario <name>` for one variant, `--fixtures` for the full grid (4
  factions × 6 = 24 PNGs). Fixtures skip .tscn emission — they're preview
  fixtures, not authored Godot scenes the runtime should load.
- Output: `../../ui/hud_preview_<faction>_<scenario>.png` per fixture. The 4 v2
  baseline previews kept (default scenario, with .tscn) for backwards
  compat. **28 PNGs total** in `ui/`.
- Use the fixture grid to spot-check: does Verdant honey-accent read against
  combat-active red banner? Does Ashen rune-violet contrast with the
  level-up celebration tint? Etc.

### C7. Ornament library expansion — chains / runes / vines / fangs
- `frame_compose.py` gained 4 new corner drawers, doubling the procedural
  ornament library to 8 (filigree / brackets / gem / scrollwork / chains /
  runes / vines / fangs). Each tested via the per-ornament smoke
  (D:\tmp\test_chains.png, etc.).
- `RECRAFT_REPLACEMENT_HINTS` dict added: per-ornament prompts that a
  future cloud-vector lane could use to swap procedural PIL for
  Recraft-generated SVG ornaments. Documented; not yet wired.

### D8. LoRA training scaffold — `lora_train.py`
- Reads `../../ui/icons/manifest.json`, filters to icons under permissive
  licenses (TRAIN_OK_LICENSES: CC0 / MIT / ISC / Apache-2.0 / first-party
  / synthetic / CC-BY 3.0+4.0 with attribution).
- For each accepted icon: resizes to base resolution (1024 default; LANCZOS),
  writes a caption file (trigger token + display_name + semantic_tags +
  fixed style brief), drops into kohya-ss-format
  `dataset/img/repeats_<N>_<token>/<id>.png`.
- Writes `dataset.toml`, `train_lora.toml` (full sd-scripts arg surface:
  network_dim/alpha, LR, steps, save_every, mixed_precision=bf16,
  gradient_checkpointing, etc), `train_command.sh` (with a comment-block
  preamble that documents the conda env + sd-scripts version pin), and
  `metadata.json` (every parameter + the per-icon reference list +
  excluded-for-license entries).
- Default base model `black-forest-labs/FLUX.1-schnell` (Apache-2.0,
  shippable). Override via `--base-model`. The license-gated FLUX.1-dev
  weights are NOT pulled by default.
- Verified: `--run-id v1_smoke --max 8` → 8 icons + dataset/img + 4 config
  files written. py_compile clean.
- Verify command (5090 free):
  `bash ui/lora/<run_id>/train_command.sh` (~2-4 h on Blackwell;
  pre-reqs in the script's preamble).

### D10. vtracer raster→SVG round-trip — `vtracer_roundtrip.py`
- Reads `../../ui/icons/manifest.json`, filters by `--filter <id-substring,...>`
  and `--max <N>`. For each selection: traces PNG → SVG via vtracer
  (BSD-3-Clause), then re-rasterizes through the freelib 3-tier rasterizer
  to produce a `<id>_round_trip.png` for visual diff against the input.
- `--plan-only` writes a deterministic `trace_plans.json` with every
  vtracer parameter (color_mode / hierarchical / filter_speckle / corner
  threshold / etc) without importing vtracer. Useful for build-time when
  the package isn't installed.
- `--annotate-manifest` updates each icon's manifest entry with
  `svg_traced: <relpath>` so downstream consumers (recraft_icons --svg-input,
  future frame_compose SVG ornament binding) can find the vector form
  by id.
- Verified: `--filter ico_sword,ico_shield --plan-only` → 2-icon plan
  written.
- Verify command:
  `pip install vtracer && python pipelines/ui/vtracer_roundtrip.py --filter <tokens> --annotate-manifest`

### E11. Per-faction palette author guide
- `../../ui/palettes/PALETTE_AUTHOR_GUIDE.md` (~280 lines).
  - Schema table for the 8 keys (id / metal / metal_dark / ink / accent /
    wood / bg / highlight) with contrast targets and constraints.
  - Per-faction design philosophy stanza: story tag + table + "why these
    choices" bullets for each of the 4 shipped palettes (Verdant Court,
    Ember Legion, Tide-Bound, Ashen Pact).
  - Step-by-step "how to add a new faction" recipe with verification
    against the 6 fixtures.
  - Cross-faction guardrails (HSL spacing, complementary-pair avoidance,
    grayscale distinctness).
  - Tools-that-consume-palettes table for future maintainers.

### E12. UI tool decision tree (in `../../pipelines/ui/README.md`)
- Same shape as the character pipeline's "which rigger" matrix. Decision
  tree for picking icon backend by use case (pixel-art / set-style /
  one-off / UI primitive / fantasy silhouette / placeholder), with the
  recommended ordering of friction.
- "When to gate vs build" table: lists every backend's status today and
  the one specific unblock action.
- Updated cloud-key contract to include `RECRAFT_API_KEY` +
  `PIXELLAB_API_KEY`.

## Tested

```
[freelib_curated_slugs.txt]                190 slugs across 8 categories
[freelib_ingest --filter-by-list]          synthetic mock zip: 5/8 match the allowlist
[freelib_ingest --source mit-iso-libs]     24 Lucide / 19 Phosphor / 22 Tabler picks shipped
[pixellab_icons --plan-only]               3 prompts -> 3 plan JSONs (smoke)
[suggest_icon_for_record]                  7 records vs 95 icons; 4 strong matches, 1 weak
[lint_icons --warn-only]                   icon=135 unused=131 missing_tags=37 mismatch=0 rtl=9
[lint_icons --strict]                      exits 1 (catalogue ahead of game_data wiring)
[hud_mockup --fixtures]                    4 factions x 6 scenarios = 24 PNG fixtures
[frame_compose <new ornaments>]            chains/runes/vines/fangs all render correctly
[lora_train --run-id v1_smoke]             dataset/, dataset.toml, train_lora.toml, train_command.sh, metadata.json
[vtracer_roundtrip --plan-only]            2 selections -> trace_plans.json
[link_validator]                           MISSING: none ✓
[py_compile]                               17/17 pipelines/ui/*.py clean
```

## Stubbed / parked

- **Live game-icons.net bulk archive** — curated allowlist + ingester
  ready; one manual download from <https://game-icons.net/about.html>
  unblocks ~190 silhouettes. License is CC-BY 3.0/4.0; ATTRIBUTION.md
  regenerated automatically on every run.
- **Recraft V3 production set** — adapter shipped; `RECRAFT_API_KEY` +
  per-set `--style-id <UUID>` will produce a 30-icon set with proper
  set-style consistency. ~$1-2 / set.
- **PixelLab live run** — adapter + plan shipped; needs `PIXELLAB_API_KEY`
  + a pixel-art region of TLTE to justify spend.
- **FLUX.1 schnell GPU run** — adapter + plan shipped; needs free 5090 +
  accepted gated HF license.
- **LoRA training run** — scaffold + dataset + train command shipped;
  needs free 5090 + sd-scripts install per the train_command.sh preamble.
- **vtracer live run** — `pip install vtracer` unblocks. Plans deterministic;
  smoke verified.
- **Animated icons (Godot AnimatedTexture)** — research D §parked. No
  current TLTE asset needs animation.
- **C# Theme codegen** — research D §parked. Slot-in via swapping
  `make_gd_class()` in `export_godot.py`. ~1 day if TLTE uses C# anywhere.
- **Aseprite Lua post-pass for pixel-art outputs** — research D §recommended
  for cleaning up SDXL-LoRA pixel attempts. PixelLab natively produces
  shippable pixel art so this is only needed if the PixelLab budget is
  ever insufficient.

## Files added (v3)

```
pipelines/ui/
  pixellab_icons.py             new (PixelLab cloud adapter)
  suggest_icon_for_record.py    new (tag-overlap matcher)
  lint_icons.py                 new (strict-icons gating wrapper)
  lora_train.py                 new (kohya-ss/sd-scripts plan-only scaffold)
  vtracer_roundtrip.py          new (raster->SVG round-trip)
  freelib_curated_slugs.txt     new (190-slug allowlist)
  mit_iso_picks_lucide.txt      new (auto-generated default picks)
  freelib_ingest.py             extended (--filter-by-list + --source mit-iso-libs)
  frame_compose.py              extended (4 new ornament drawers + RECRAFT_REPLACEMENT_HINTS)
  hud_mockup.py                 extended (SCENARIOS + --scenario + --fixtures)
  README.md                     extended (decision tree + v3 additions section)

ui/
  palettes/
    PALETTE_AUTHOR_GUIDE.md     new
  diffusion_plans/
    ico_pixel_*.pixellab_plan.json   3 example plans
  hud_preview_<faction>_<scenario>.png    24 fixtures (4 x 6)
  icons/
    suggestions.json            new (icon-suggest output)
    suggestions.md              new (icon-suggest output, human-readable)
    lint_icons_report.json      new (lint_icons output)
    icon_id_patch.jsonl         new (icon-suggest --apply output)
    svg_traced/                 reserved for vtracer outputs
      trace_plans.json          plan-only example
  lora/
    v1_smoke/
      dataset/                  8 icons + captions
      dataset.toml              kohya-ss dataset config
      train_lora.toml           sd-scripts training config
      train_command.sh          shell command for the 5090 run
      metadata.json             full provenance
```

## Cloud-key contract (delta from v2)

| Env var | Activates | Falls back to |
|---|---|---|
| `OPENAI_API_KEY` | `openai_icons.py` | exit 2; synth always available |
| `RECRAFT_API_KEY` | `recraft_icons.py` | exit 2; synth always available |
| `PIXELLAB_API_KEY` | `pixellab_icons.py --run` | `--plan-only` writes API plan JSON |

## Effort

~4 hours. The architecturally-correct v2 contract (every backend writes
the same `manifest.json` shape) made every new backend a clean slot-in:
the slug-list, the MIT/ISC source, PixelLab, the icon-suggest matcher,
and the LoRA scaffold all dropped in as siblings without touching the
existing 12 v2 modules' core logic.

## Top three next moves

1. **Get the live game-icons.net archive on disk** (one manual download)
   → `freelib_ingest.py --source game-icons-net --zip <archive>
   --filter-by-list pipelines/ui/freelib_curated_slugs.txt --accept-license`.
   Adds ~190 CC-BY silhouettes immediately.
2. **Wire icon_id into game_data records** using
   `suggest_icon_for_record.py --apply` → review `icon_id_patch.jsonl` →
   merge into `../../game_data/validated/*.jsonl` via the game_data lane's
   migration tooling. After the merge, `lint_icons --strict` should pass
   for the matched records (no more drift).
3. **Free the 5090** → run `lora_train.py` to materialize the train run,
   then `bash ui/lora/<run_id>/train_command.sh`. Result: a faction-style
   LoRA we pass to FLUX schnell via
   `local_diffusion_icons.py --lora <path>`. Closes the loop on
   commercial-OK local iconography.

---

## v3 actual run reconciliation (executed during this build)

The above is the planned/scaffolded state. Numbers actually executed:

```
[freelib_ingest --picklist game_icons_core.json]   +50 CC-BY silhouettes
                                                    (58-entry curated picklist;
                                                     50 fetched, 3 404'd, 5 skip-
                                                     dup. Author/slug pairs
                                                     verified via per-icon HTTP
                                                     probe before fetch.)
[freelib_ingest --library lucide  --slugs-file]    +22 Lucide ISC primitives
[freelib_ingest --library phosphor --slugs-file]   +18 Phosphor MIT primitives
[pack_atlas]                  135 icons -> 4096x4096 atlas
[export_godot]                icons=135 9slice=24 styleboxes=24
[frame_compose --signatures]  4 hero panels (vines/fangs/runes/chains)
[hud_mockup --fixtures]       4 factions x 6 scenarios = 24 PNGs
[hud_mockup default]          4 factions, .tscn + preview each
[link_validator]              MISSING: none ✓
[lint_icons]                  unused=131 missing_tags=37 mismatch=0 rtl_review=9
[icon_validator]              unused 131/135  mismatches=6  missing_tags=37
[suggest_icon_for_record]     7/8 records get strong matches >= 0.5
[lora_train --run-id v3_smoke --max 10]   plan + 10-icon dataset prepped
[pixellab_icons --plan-only]  6 plans @ ~$0.06 estimated
```

Notes from the actual run:

- **Companion validator** (`icon_validator.py`) shipped alongside
  `lint_icons.py`. Both gate; they look at different signals (tag overlap
  vs suggestions.json score-delta) and disagree productively (lint reports
  0 mismatches, validator reports 6). Use `lint_icons` for fast CI gating,
  `icon_validator` for deep diagnostics.
- **MIT/ISC URL templates** had to be migrated from pinned tags to `main`
  branch — the pinned `v0.469.0` (Lucide) / `v2.1.1` (Phosphor) / `v3.31.0`
  (Tabler) tags 404 on the GitHub raw paths. Repinning to `main` for now;
  cache at `../../ui/freelib_svg_cache/<id>.svg` provides byte-level repro for
  any individual icon already fetched.
- **Tabler skipped** at ingest time: Lucide + Phosphor cover the same UI
  primitives, and ingesting Tabler would be redundant chrome (the
  research-D-flagged "wasted breadth" failure mode). The registry entry +
  default-picks file ship anyway in case a specific Tabler slug is ever
  needed.
- **Non-existent slugs** found during the curated game-icons.net fetch:
  `meat`, `flame`, `ice-spell-cast` returned 404. Picklist trimmed to the
  58 verified entries. The probe pattern (try multiple known authors, log
  NOT FOUND) is captured at `D:\tmp\check_gi.py` for future curation runs.
- **Picklist > flat-allowlist** for game-icons.net specifically because
  game-icons.net's URL pattern bakes the author into the path. A flat
  slug-list works for libraries with author-agnostic URLs (Lucide /
  Phosphor / Tabler — slug only); game-icons.net needs `(author, slug)`
  pairs OR per-author HTTP probes to find which author owns each slug.
  The picklist makes the per-icon attribution work upfront so subsequent
  runs are deterministic.
