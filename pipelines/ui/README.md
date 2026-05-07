# UI / Icons Pipeline

**Status:** ✅ **v2 SOTA push complete (2026-05-06)** — end-to-end offline procedural, cloud OpenAI Images / Recraft V3 activated by their respective keys, FLUX.1 schnell local adapter plumbed and waiting on a free GPU. See [`../../_archive/handoffs_2026_05_06/HANDOFF_ui_v2_2026_05_06.md`](../../_archive/handoffs_2026_05_06/HANDOFF_ui_v2_2026_05_06.md).

```
synth_icons.py (37 presets)            →  ui/icons/<id>.png + manifest.json
openai_icons.py | recraft_icons.py     →  (same manifest schema; cloud-gated)
local_diffusion_icons.py               →  (plan-only by default; --run when GPU is free)
freelib_ingest.py (CC-BY/MIT/ISC)      →  ingests external libraries; auto-writes ATTRIBUTION.md
                                            ↓
                              pack_atlas.py  → ui/atlas/atlas.png + atlas.json
                                            ↓
nine_slice.py (panel/button/frame/healthbar) →  ui/9slice/<id>.png + <id>.json
frame_compose.py --sweep (4 bases × 4 palettes = 16 faction variants)
                                            ↓
                              export_godot.py → ui/godot/
                                  • atlas.png
                                  • <id>_atlas.tres            (AtlasTexture)
                                  • <element>_<faction>_stylebox.tres   (per faction)
                                  • theme.tres                 (Godot 4.5 Theme)
                                  • 9slice/<id>.png
                                            ↓
                              hud_mockup.py  → ui/godot/hud_<faction>.tscn (one per faction)
                                              + ui/hud_preview_<faction>.png
```

## Files

| File | Role |
|---|---|
| [synth_icons.py](synth_icons.py) | Pure-PIL procedural icon set. v2: 37 presets (8 weapons / 4 consumables-gems / 8 spells one-per-school / 9 buffs-chrome + the 8 v1 originals). Single palette across all → coherent set. |
| [openai_icons.py](openai_icons.py) | OpenAI `gpt-image-1` adapter. Gated on `OPENAI_API_KEY`. |
| [recraft_icons.py](recraft_icons.py) | **v2** Recraft V3 cloud adapter. Gated on `RECRAFT_API_KEY`. Best 2026 set-style consistency via `--style-id <UUID>`; `--style icon|vector_illustration|...`, `--svg` for the vector lane. |
| [local_diffusion_icons.py](local_diffusion_icons.py) | **v2** FLUX.1 schnell (Apache-2.0) adapter. Default mode `--plan` writes a deterministic diffusion plan JSON without GPU. `--run` lazy-imports diffusers + torch. **License gate** hard-blocks FLUX.1 [dev]/[Krea-dev] (non-commercial). |
| [freelib_ingest.py](freelib_ingest.py) | **v2** game-icons.net / Lucide / Phosphor / Tabler ingester. Three-tier SVG rasterizer (resvg-py / cairosvg / PIL silhouette). License-correct: every entry preserves author/license/URL; aggregate `ui/ATTRIBUTION.md` auto-written. |
| [nine_slice.py](nine_slice.py) | Panel / button / frame / healthbar synth + alpha-bbox margin detector. Writes `<id>.json` margin sidecars. |
| [frame_compose.py](frame_compose.py) | **v2** faction-themed 9-slice variant composer. Base × ornament × palette → 16-32 visual variants. `--sweep` runs all bases × all palettes. |
| [pack_atlas.py](pack_atlas.py) | Greedy shelf atlas packer, POT dimensions. |
| [export_godot.py](export_godot.py) | Per-icon `AtlasTexture.tres`, per-9slice `StyleBoxTexture.tres` (one per faction variant when present), unified `Theme.tres`. |
| [hud_mockup.py](hud_mockup.py) | **v2** real Godot 4.5 HUD `.tscn` generator. One per faction palette, plus PIL preview PNGs. |
| [preview_grid.py](preview_grid.py) | Single-PNG preview at 32/64/128 px per icon + 9-slice strip. |

## Quickstart (v2 full pipeline)

```powershell
# 1. Generate 37 procedural icons (offline, deterministic)
python pipelines\ui\synth_icons.py --size 256

# 2. (optional) Ingest free CC-BY library — drop a game-icons.net zip first
python pipelines\ui\freelib_ingest.py --source game-icons-net `
    --zip <bulk_archive.zip> --out D:\assets\ui\icons --pick 30

# 3. Original 4 9-slice elements (still authoritative defaults)
python pipelines\ui\nine_slice.py panel     --size 256x256 --margin 24 --out D:\assets\ui\9slice\panel.png
python pipelines\ui\nine_slice.py button    --size 256x80  --margin 18 --out D:\assets\ui\9slice\button.png
python pipelines\ui\nine_slice.py frame     --size 192x192 --margin 24 --out D:\assets\ui\9slice\frame.png
python pipelines\ui\nine_slice.py healthbar --size 256x32  --margin 8  --out D:\assets\ui\9slice\healthbar.png

# 4. v2: faction-themed 9-slice sweep (writes 16 variants)
python pipelines\ui\frame_compose.py --sweep `
    --palettes D:\assets\ui\palettes --out-dir D:\assets\ui\9slice

# 5. Pack atlas + export Godot resources (now sees faction styleboxes too)
python pipelines\ui\pack_atlas.py
python pipelines\ui\export_godot.py

# 6. v2: HUD .tscn scenes (one per faction palette) + PIL previews
python pipelines\ui\hud_mockup.py

# 7. Visual sanity check (one PNG of everything)
python pipelines\ui\preview_grid.py
```

## Cloud / GPU lanes (v2)

```powershell
# Recraft V3 — best 2026 cloud option for set-style consistency
$env:RECRAFT_API_KEY = "..."
python pipelines\ui\recraft_icons.py --prompts D:\assets\ui\prompts.json `
    --style icon --style-id <UUID> --size 1024

# FLUX.1 schnell — Apache-2.0 (commercially shippable). Plan-only by default.
python pipelines\ui\local_diffusion_icons.py --prompts D:\assets\ui\prompts.json --plan
# When the 5090 is free:
python pipelines\ui\local_diffusion_icons.py --prompts D:\assets\ui\prompts.json --run `
    --lora <path/to/icon-lora.safetensors> --lora-weight 0.85
```

Drop `ui/godot/` into a Godot 4.5 project at `res://ui/`:

```gdscript
# Apply the Theme to any Control:
$Control.theme = load("res://ui/theme.tres")

# Use any icon directly:
$TextureRect.texture = load("res://ui/ico_sword_atlas.tres")

# Or via the IconSet on the theme:
var t: Texture2D = $Control.theme.get_icon("ico_sword", "IconSet")
```

## Cloud route (OpenAI Images)

`prompts.json` example:

```json
[
  {"id": "ico_dragon",       "prompt": "fantasy game icon: a roaring red dragon head"},
  {"id": "ico_amulet_lunar", "prompt": "fantasy game icon: a silver amulet shaped like a crescent moon"}
]
```

```powershell
python pipelines\ui\openai_icons.py --prompts ui\prompts.json --size 1024 --out ui\icons
python pipelines\ui\pack_atlas.py
python pipelines\ui\export_godot.py
```

The exporter doesn't care which backend produced the PNGs — it only reads `manifest.json`.

## What we did NOT add (and why)

- **FLUX-icons local run / Recraft** — both are higher-end alternatives the research recommends. Recraft is API-paid; FLUX needs the GPU. Slot-in points: the manifest schema is identical, so a `flux_icons.py` or `recraft_icons.py` that writes `<id>.png` will compose with the rest unchanged.
- **PixelLab / pixel-art LoRA path** — requires both a GPU and the LoRA weights. Not in scope. The procedural backend can be tweaked to a pixel-style by quantizing palette + integer scaling; deferred.
- **Free icon libraries** (game-icons.net, OGA) — easy ingester to add. Same manifest shape.
- **TexturePacker CLI** — our shelf packer covers the demo; for production batches with rotation + tight bin-packing, swap to `rectpack` (`pip install rectpack`).

## Output contract

```
ui/
  icons/<id>.png                     8 icons (256 px transparent)
  icons/manifest.json                inventory + provenance
  9slice/<id>.png                    panel/button/frame/healthbar
  9slice/<id>.json                   patch_margin metadata
  atlas/atlas.png + atlas.json       packed atlas + region rects
  preview.png                        visual sanity grid
  godot/                             Godot drop-in
    atlas.png
    9slice/<id>.png
    <id>_atlas.tres                  AtlasTexture per icon
    <id>_stylebox.tres               StyleBoxTexture per 9-slice
    theme.tres                       Theme wiring it all
    README.txt
```

## v3 additions (2026-05-06)

See [`../../docs/handoffs/HANDOFF_ui_v3_2026_05_06.md`](../../docs/handoffs/HANDOFF_ui_v3_2026_05_06.md).

| File | Role |
|---|---|
| [pixellab_icons.py](pixellab_icons.py) | **v3** PixelLab cloud adapter for native pixel-art icons (16/32/48/64 px). Mirrors openai_icons / recraft_icons shape. Plan-only by default; `--run` requires `PIXELLAB_API_KEY` + `--max-cost-usd` cap. |
| [suggest_icon_for_record.py](suggest_icon_for_record.py) | **v3** tag-overlap matcher: for every game_data record, ranks the top-K ui icons by cosine + category bonuses. Outputs `ui/icons/suggestions.{json,md}`. |
| [lint_icons.py](lint_icons.py) | **v3** strict-icons gating wrapper around `pipelines/_meta/link_validator.py`. Standalone tag-based checks: unused, missing semantic_tags, record→icon category mismatch (prefix tokens), RTL flag review. Exit 1 in `--strict` mode if any check trips. |
| [icon_validator.py](icon_validator.py) | **v3** companion to `lint_icons.py` that reads `suggestions.json` from `suggest_icon_for_record.py` and gates on the **score-delta** between the current and best-suggested icon. Use `lint_icons.py` for fast deterministic gating, `icon_validator.py` when you also want the suggester's cosine-overlap score in the loop. |
| [lora_train.py](lora_train.py) | **v3** plan-only kohya-ss / sd-scripts dataset prep + train command. Writes `ui/lora/<run_id>/{dataset/, dataset.toml, train_lora.toml, train_command.sh, metadata.json}`. License-correct: only icons under permissive licenses are included. Verify command runs on the 5090 when free. |
| [vtracer_roundtrip.py](vtracer_roundtrip.py) | **v3** raster→SVG round-trip via `vtracer` (BSD-3). Plan-only when vtracer not installed; `--annotate-manifest` writes `svg_traced` paths back into `ui/icons/manifest.json` so Recraft / frame_compose can find vector forms by id. |
| [freelib_curated_slugs.txt](freelib_curated_slugs.txt) | **v3** curated 190-slug allowlist for `freelib_ingest.py --filter-by-list`. Categories: weapons / armor / consumables / spell schools (fire/ice/lightning/nature/shadow/arcane/holy) / buffs / UI primitives / world+map. |

The HUD generator gained a `--scenario` knob (default / full_hp / low_hp /
combat_active / inventory_full / dialog_open / level_up) and a `--fixtures`
mode that emits the full 4 factions × 6 scenarios = 24 PNG grid for
faction-palette spot checks.

## Decision tree: which icon backend?

> Same shape as the character pipeline's "which rigger" matrix. Pick the
> earliest row whose constraints match your situation.

```
Need pixel-art icons (16-64 px native, hand-pixeled feel)?
  YES -> pixellab_icons.py             (cloud, paid; PIXELLAB_API_KEY)
  NO  -> continue

Need set-style consistency across 20+ icons (one visual mood)?
  YES + cloud OK     -> recraft_icons.py --style icon --style-id <UUID>
  YES + GPU later    -> local_diffusion_icons.py --plan  (FLUX schnell + LoRA)
  YES + cloud + GPU  -> recraft_icons.py for the hero set, FLUX for variants
  NO  -> continue

Need a one-off illustration (single concept icon, no set)?
  YES + cloud + budget -> openai_icons.py     (gpt-image-1, simplest API)
  YES + cloud premium  -> recraft_icons.py    (better quality, slightly more $$)
  YES + GPU later      -> local_diffusion_icons.py --plan
  NO  -> continue

Need a UI primitive (chevron, gear, x, plus, search)?
  YES -> freelib_ingest.py --source mit-iso-libs --library lucide
                                       (or phosphor/tabler; MIT/ISC; free)
  NO  -> continue

Need a fantasy/RPG silhouette (sword, dragon, spell, NPC bust)?
  YES + ship-soon -> freelib_ingest.py --source game-icons-net --zip <archive>
                                       --filter-by-list pipelines/ui/freelib_curated_slugs.txt
                                       (~190 high-utility slugs; CC-BY)
  YES + bespoke   -> recraft_icons.py / openai_icons.py / FLUX with LoRA
  NO  -> continue

Need a fast deterministic placeholder for the build?
  YES -> synth_icons.py                (procedural PIL, 37 presets,
                                         no GPU, no cloud, no internet)
```

If multiple backends could fit, prefer the lower-friction one *first*
(synth → freelib → openai → recraft → FLUX local → PixelLab). The contract
is the same `manifest.json` shape — every backend's output drops into the
same atlas + Theme via `pack_atlas.py` + `export_godot.py`. Mix freely.

### When to gate vs build

| Lane | Status today | Ungate by |
|---|---|---|
| `synth_icons.py` | Always available | — |
| `openai_icons.py` | Available with `OPENAI_API_KEY` | (already set) |
| `recraft_icons.py` | Adapter shipped; needs `RECRAFT_API_KEY` | Subscribe + set env var |
| `freelib_ingest.py game-icons-net` | Allowlist + ingester shipped; needs the public 50 MB zip | One manual download from <https://game-icons.net/about.html> |
| `freelib_ingest.py mit-iso-libs` | Built-in URL templates for Lucide/Phosphor/Tabler | Just add `--accept-license` |
| `local_diffusion_icons.py` (FLUX schnell) | Adapter + plan shipped; needs free 5090 + accepted gated HF license | Free 5090 + `huggingface-cli login` + accept license |
| `pixellab_icons.py` | Adapter + plan shipped; needs `PIXELLAB_API_KEY` + pixel-art region of TLTE | Subscribe + set env var |
| `lora_train.py` | Plan + dataset prep shipped; train run needs free 5090 + sd-scripts | Free 5090 + `pip install` setup per the train command's preamble comment |
| `vtracer_roundtrip.py` | Plan-only out of the box; full run needs `pip install vtracer` | Just `pip install vtracer` |

## Cloud-key contract

| Env var | Activates | Falls back to |
|---|---|---|
| `OPENAI_API_KEY` | `openai_icons.py` real generation | (caller picks; default flow uses synth) |
| `RECRAFT_API_KEY` | `recraft_icons.py` real generation | exit 2; synth always available |
| `PIXELLAB_API_KEY` | `pixellab_icons.py --run` | `--plan-only` writes API plan JSON |
| `FREESOUND_API_KEY` *(future)* | `freelib_ingest.py --source freesound` if added | n/a |
