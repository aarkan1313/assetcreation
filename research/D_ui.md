# Assignment D - UI / Icons / Theme Pipeline

Date: 2026-05-06
Scope: AI icon generation, pixel-art lanes, 9-slice/9-patch authoring, atlas packing, free icon libraries, Godot 4.5 Theme workflows, HUD/frame design, diegetic UI, and localization-aware icon design. Builds on top of UI/Icons v1 (`pipelines/ui/synth_icons.py`, `openai_icons.py`, `nine_slice.py`, `pack_atlas.py`, `export_godot.py`, `preview_grid.py`).

## Executive Recommendation

The v1 build is small but architecturally correct. The icon, 9-slice, atlas, and `Theme.tres` pieces all share a single `manifest.json` contract, which means new generators slot in as siblings to `synth_icons.py`/`openai_icons.py`. The right 2026 expansion is **breadth across source lanes plus a tiny number of cloud-quality upgrades**, not a rewrite.

Use this 2026 starter kit for v2:

1. **Recraft V3 (cloud)** as the primary "stylistically consistent set of N icons" generator. Recraft has explicit "icon" and "vector" image types, returns SVG when asked, and has the strongest reputation for set-level style consistency in 2026 ([Recraft API](https://www.recraft.ai/docs)). It is the cleanest commercial-license path for shipping game icons. Build `ui/recraft_icons.py` mirroring the `openai_icons.py` shape.
2. **FLUX.1 \[dev\] + game-icon LoRA (local)** as the GPU lane. FLUX.1 \[dev\] is non-commercial under the FLUX.1 \[dev\] Non-Commercial License but works as the daily prototyping driver; **FLUX.1 \[schnell\]** (Apache-2.0) and **FLUX.1 Krea \[dev\]** are the shippable variants for commercial output ([Black Forest Labs](https://blackforestlabs.ai/), [HF flux.1-dev](https://huggingface.co/black-forest-labs/FLUX.1-dev), [HF flux.1-schnell](https://huggingface.co/black-forest-labs/FLUX.1-schnell)). Drive both through ComfyUI or `diffusers`. The 5090 has the VRAM headroom.
3. **game-icons.net normalizer** as the "free assets you can ship today" lane. ~5000 CC-BY 3.0/4.0 monochrome silhouette icons, exactly the corpus most ARPG-style HUDs and ability bars are built from ([game-icons.net](https://game-icons.net/about.html)). Build `ui/freelib_ingest.py` with attribution metadata baked into the manifest.
4. **Godot Theme presets per faction/biome** — extend `export_godot.py` so the same icon/9-slice set can be re-themed by swapping a palette JSON. This is the cheapest visual-variety multiplier we have.
5. Keep `synth_icons.py` for placeholder/CI/regression coverage. It is not pretty, but it lets the entire downstream path build with no API keys, no GPU, and no internet.

Add later: **PixelLab API** for retro pixel-art icons (best-of-class in 2026 for that style), **Lucide/Phosphor** monochrome libraries for menu/UI chrome (ASCII-friendly, MIT/ISC, no attribution), and a **HUD frame templater** that procedurally composes ornament overlays on top of the existing `nine_slice.py` panel/frame outputs.

## Current Local State

`pipelines/ui/` ships:

```text
synth_icons.py     8 PIL-procedural icons sharing one palette
openai_icons.py    gpt-image-1 cloud adapter, gated on OPENAI_API_KEY
nine_slice.py      4 synth elements (panel/button/frame/healthbar) + alpha-bbox derive mode
pack_atlas.py      greedy shelf packer, POT, configurable padding
export_godot.py    AtlasTexture.tres + StyleBoxTexture.tres + Theme.tres + IconSet
preview_grid.py    visual sanity sheet
```

The contract is good. Every icon source writes the same `manifest.json` shape (`id`, `path`, `size`, optional `prompt`, `model`, `seed`, `license`, `attribution`). Every 9-slice element writes a `<id>.json` with `{ left, top, right, bottom }` margins. The atlas packer reads any directory of PNGs. The Godot exporter consumes the manifests and writes a single `theme.tres` plus per-asset `.tres` files.

What v1 deliberately does **not** do, and where v2 should expand:

- No GPU diffusion lane. The 5090 is unused for UI.
- No vector/SVG output. Everything is rasterized PNG, which is fine for fixed-resolution HUDs but loses scalability.
- No retro/pixel-art preset. Current style is flat-design vector.
- No free-library ingester. Manual download only.
- No HUD-mockup tool. The Godot exporter writes resources, not a sample HUD scene.
- No frame-variant generator. Each 9-slice frame is a single asset.
- No localization-aware sizing or RTL flagging.

## 1. AI Icon Generation 2026

| Tool | Local/Cloud | License of generations | SVG/Vector | Set-style consistency | Why it matters | Caveat |
|---|---|---|---|---|---|---|
| [Recraft V3](https://www.recraft.ai/docs) | Cloud API | Recraft commercial use; user owns generations | **Yes** (`recraft-v3-svg`) | **Best in class for icon sets** | Explicit "icon"/"vector_illustration" image types, style references, brand kits | Paid, ~$0.04-0.08/image; rate-limited |
| [Ideogram 3.0](https://about.ideogram.ai/3.0) | Cloud API | Commercial use on paid plans | No | Strong, especially with `style_reference` | Best in class for typographic/text-on-image; great for buttons with labels | Closed model; paid |
| [Midjourney v7](https://docs.midjourney.com/) | Cloud (Discord/web) | Commercial on paid plans | No | Strong on aesthetic, weaker on icon-set consistency | Best aesthetic ceiling for hero/menu art | No first-class API; automation requires Discord scraping or third-party gateways. **Not LLM-driveable** in the way Recraft/Ideogram/OpenAI are |
| [Adobe Firefly Image 4](https://firefly.adobe.com/) | Cloud API | Commercially safe (Adobe IP-indemnified) | No native vector; SVG via Illustrator | Medium | The legally cleanest cloud option for studios that worry about training-data lawsuits | Paid; API access via Firefly Services, gated |
| [GPT-Image-1](https://platform.openai.com/docs/guides/images) | Cloud API (already wired) | OpenAI commercial use | No | Medium; style drift across batch | Already integrated; good for one-offs and structured prompt work | No vector; costs $0.04-0.19/image depending size; style consistency across 30 icons is the weak point |
| [Imagen 3 / Imagen 4](https://deepmind.google/models/imagen/) | Cloud API (Vertex/Gemini) | Commercial on paid tier; SynthID watermark | No | Strong photorealism, medium for stylized icons | Good fallback if OpenAI/Recraft are down | Gated through Google Cloud; setup overhead |
| [FLUX.1 \[dev\]](https://huggingface.co/black-forest-labs/FLUX.1-dev) | **Local** | Non-commercial only | No | High **with LoRA** | Best local quality; runs comfortably on the 5090 | License blocks commercial shipping unless using \[schnell\] or \[Krea-dev\] |
| [FLUX.1 \[schnell\]](https://huggingface.co/black-forest-labs/FLUX.1-schnell) | **Local** | Apache-2.0 | No | Medium-high | The shippable FLUX variant; 4-step inference | Slightly lower fidelity than \[dev\] |
| [FLUX.1 Krea \[dev\]](https://huggingface.co/black-forest-labs/FLUX.1-Krea-dev) | **Local** | FLUX.1 \[dev\] license but explicit commercial path via Krea | No | High | Trained for "no AI look"; better realism/photographic feel | Same dev license terms; check exact commercial use clause |
| [SDXL + game-icon LoRAs](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0) | **Local** | OpenRAIL-M | No | Medium with LoRA | Mature, lots of LoRA ecosystem, lighter VRAM | Lower ceiling than FLUX |
| [Stable Diffusion 3.5 Large](https://huggingface.co/stabilityai/stable-diffusion-3.5-large) | **Local** | Stability Community License (free under revenue threshold) | No | High | Strong all-rounder, prompt-following improved over SDXL | License revenue threshold matters once a game ships |

### Set-style consistency: the actual question

For a 30-icon ability bar where every icon must read as "from the same set," the practical 2026 answer is:

1. **Recraft V3** with a **style reference** (or a Recraft "Brand" / style fine-tune) is the most reliable. It was built for this use case (illustrators producing icon sets, brand kits) and the docs expose `style_id` / style references directly.
2. **FLUX with a single icon LoRA + tight prompt template** is the closest local equivalent. Public LoRAs exist on Civitai/HuggingFace targeting "flat icon," "fantasy game icon," "stylized RPG icon" looks; quality varies. Training your own LoRA from 20-40 reference icons is feasible on the 5090 in ~2-4 hours and gives the highest set-cohesion you can get locally.
3. **GPT-Image-1** is the weakest of the three for set consistency because it does not expose a stable style handle. Style references via `image` input help but drift across larger batches.
4. **Midjourney** has the highest individual-image aesthetic but the worst LLM-automation story; not recommended as the icon backbone unless someone is prepared to script Discord.

### Vector output

Only **Recraft V3** (`recraft-v3-svg`) returns true SVG today. Everything else returns raster PNG. For game UI that ships at fixed resolution this is fine; for a UI that needs to scale across phone-to-4K, the Recraft vector lane is meaningfully different.

For raster-to-vector, [vtracer](https://github.com/visioncortex/vtracer) (MIT, Rust CLI) is the go-to open-source path and works well on flat-color icons. It does not work well on painterly/photographic icons.

### Commercial-license cleanliness

| Model | Commercially shippable? | Notes |
|---|---|---|
| Recraft V3 | Yes | User owns generations on paid tier |
| Ideogram 3 | Yes (paid plans) | Free tier disallows commercial |
| Midjourney v7 | Yes (paid plans) | Free trial generations are not commercially usable |
| Adobe Firefly | Yes, with IP indemnity | Strongest legal cover |
| GPT-Image-1 | Yes | OpenAI usage policies apply |
| Imagen 3/4 | Yes (paid) | SynthID watermarking |
| **FLUX.1 \[dev\]** | **No** (non-commercial) | Use only for prototyping/internal |
| FLUX.1 \[schnell\] | Yes (Apache-2.0) | The default commercial-FLUX choice |
| FLUX.1 Krea \[dev\] | Conditional | Krea offers commercial path; verify before ship |
| SDXL | Yes | OpenRAIL-M with usage restrictions |
| SD 3.5 Large | Yes (under revenue threshold) | Community license has revenue cap |

The simplest "ship without thinking about lawyers" pair for this project is **Recraft V3 (cloud) + FLUX.1 \[schnell\] (local)**.

## 2. Pixel-Art / Retro Icons

The pixel-art lane is genuinely different from the flat-vector lane and most general-purpose models do it badly. In 2026:

- **[PixelLab](https://www.pixellab.ai/)** — Cloud API targeted specifically at pixel-art game assets. Generates icons, characters, tilesets at 16/32/48/64 px native resolutions. The dominant 2026 winner for "I want pixel-art icons that look hand-pixeled, not downscaled." API is clean and LLM-driveable.
- **Pixel-Art XL / Pixel-Art Diffusion** — community SDXL LoRAs and fine-tunes. Quality is medium; outputs almost always need a "snap to pixel grid + reduce palette" post-pass to actually look pixel-art instead of "blurry image of pixel art."
- **FLUX with retro/pixel LoRAs** — emerging on Civitai. Higher ceiling than SDXL pixel LoRAs but still requires the same post-pass.
- **Aseprite Lua scripting** — not generative, but the right tool for **post-processing** AI outputs into clean pixel art: indexed palette, grid snap, outline cleanup, dither passes. Aseprite has a Lua scripting API and can run headless via CLI. This is the pixel-art equivalent of `nine_slice.py`'s alpha-bbox detection — the deterministic cleanup step.
- **Procedural pixel-art icons** — for very small icons (16x16, 32x32), procedural generation like our `synth_icons.py` is competitive with AI because the resolution is so low that "polygon + palette + 2px outline" is most of what you need. A `synth_pixel_icons.py` sibling at 32-px resolution would be a useful complement.

The **2026 quality bar** for pixel-art icons specifically: PixelLab is the only dedicated tool that consistently nails it without manual cleanup. Everything else needs Aseprite-style post-processing to be shippable.

## 3. 9-Slice / 9-Patch Generation

Three real options:

1. **Manual margin authoring** — the v1 default. `nine_slice.py` either synthesizes elements with known margins, or runs `derive` mode that uses alpha-bbox detection to auto-pick margins on imported PNGs. This is fine for ~80% of cases.
2. **Auto-detection of stretch regions** — for arbitrary art, the established trick is detecting the **largest constant-color or low-variance band** along each axis and treating that as the stretchable region. This is what Android's `9.png` tooling does. Our `derive` mode does an alpha-only version of this; a v2 upgrade would extend to RGB constancy detection so it works on opaque frames, not just transparent-bordered ones. Effort: ~3-4 hours.
3. **AI-generated frames pre-tagged for 9-slice** — there is no production tool that emits "ready-to-9-slice" frames as a first-class output. The right pattern is: generate a frame with a clearly-uniform middle band (prompt the model for "ornate fantasy panel with simple flat center, decorative borders only on edges"), then run derive. Recraft V3 with a "UI panel" style consistently produces 9-slice-friendly outputs because vector illustration tends to keep flat fills.

For Godot specifically, the relevant doc is [StyleBoxTexture](https://docs.godotengine.org/en/4.5/classes/class_styleboxtexture.html). The four margins map directly to `texture_margin_left/top/right/bottom`. v1 already wires this correctly.

A useful **frame-variant tool** does not exist as a single tool. Build it: take a base 9-slice frame and an "ornament library" (corner brackets, edge filigree, gem insets), composite procedurally for N variants. Effort: ~6-10 hours, high payoff for faction/biome variety.

## 4. Atlas Packing

| Tool | License | Interface | Strengths | Caveat |
|---|---|---|---|---|
| [TexturePacker](https://www.codeandweb.com/texturepacker) | Commercial | GUI + CLI (`TexturePacker` CLI) | Best-in-class packing, MaxRects + variants, multi-format export, supports Godot SpriteFrames | Paid; pro license required for CLI use |
| [free-tex-packer](https://free-tex-packer.com/) ([CLI](https://github.com/odrick/free-tex-packer-cli)) | MIT | Node.js CLI | Free, multiple algorithms (MaxRects, OptimalPacker), JSON/Cocos2D/Phaser/Godot exports | Less battle-tested than TexturePacker |
| [rectpack](https://github.com/secnot/rectpack) | Apache-2.0 | Python lib | Pure-Python rectangle packer (MaxRects, GuillotineBnf, Skyline) | Library, not a finished tool; needs glue |
| [pyTexturePacker](https://github.com/wo1fsea/pyTexturePacker) | MIT | Python lib + CLI | Direct drop-in for what we have; MaxRects with rotation | Less active maintenance |
| **Our `pack_atlas.py`** | First-party | Python CLI | Greedy shelf, POT, deterministic, zero deps | Lower packing efficiency than MaxRects on heterogeneous sets |
| Godot 4.5 built-in `AtlasTexture` import | Engine | Editor / `.import` | Works at import time, no external tool | Requires manual region authoring or sprite-sheet input |

### Sparse vs dense

- **Dense atlas** (greedy shelf or MaxRects with tight padding): smallest VRAM, best for ~50-200 icons that ship in one set, faster sampler cache hits.
- **Sparse atlas** (uniform grid, e.g. 8x8 cells of 256px): less efficient, but trivially indexable by `(row, col)`, deterministic across regenerations, far easier to diff in version control, and lets you do `region = Rect2(col*256, row*256, 256, 256)` math at runtime instead of looking up JSON. Useful when icons get added/removed frequently and atlas churn matters.

For our scale (8 icons today, plausibly 50-150 in v2), the current greedy shelf packer is fine. Switching to **rectpack's MaxRects** is a 2-3 hour drop-in upgrade if/when packing efficiency starts to matter (probably ~100+ icons). Switching to a **sparse uniform grid** is a ~1-hour change and might be the right call for the icon set specifically because regenerations are frequent.

## 5. Free / CC-BY Icon Libraries

| Source | Count | License | Attribution | Style | Programmatic access | Notes |
|---|---:|---|---|---|---|---|
| [game-icons.net](https://game-icons.net/) | ~5000 | CC-BY 3.0 / CC-BY 4.0 | **Required** (collective credit OK) | Monochrome silhouette, fantasy/RPG-leaning | Bulk download (zip), per-icon SVG download | The single best free source for ARPG ability/item icons. By far. |
| [Lucide](https://lucide.dev/) | ~1700 | ISC | None | Outline, modern UI | npm/CDN/GitHub; SVG | Best for menu/UI chrome (gear, X, arrow, settings) |
| [Phosphor](https://phosphoricons.com/) | ~1500 (×6 weights) | MIT | None | Outline/filled, six weights | npm/CDN/GitHub; SVG | Six visual weights = built-in style variants |
| [Material Symbols](https://fonts.google.com/icons) | ~3500 | Apache-2.0 | None | Outline/rounded/sharp | Variable font + SVG | Largest "no attribution required" set |
| [Heroicons](https://heroicons.com/) | ~300 | MIT | None | Outline/solid/mini | npm/GitHub; SVG | Tailwind ecosystem; small set |
| [Tabler Icons](https://tabler.io/icons) | ~5800 | MIT | None | Outline/filled | npm/GitHub; SVG | Largest MIT-licensed set; UI chrome focus |
| [Noun Project](https://thenounproject.com/) | millions | Mixed (CC-BY + paid royalty-free) | CC-BY items require attribution | Wildly varied | API on paid tier | License hygiene is the burden; paid plans waive attribution |
| [Open Game Art](https://opengameart.org/) | thousands | Mixed (CC0/CC-BY/CC-BY-SA/GPL) | Per-asset | Wildly varied | None; manual browsing | Per-asset license hygiene is the burden |
| [itch.io asset packs](https://itch.io/game-assets/free) | thousands | Per-pack | Per-pack | Wildly varied | None | Best for pixel-art packs; license hygiene per-pack |
| [Kenney UI Pack](https://kenney.nl/assets/ui-pack-rpg-expansion) | hundreds | CC0 | None | Cartoon RPG, pixel, sci-fi | Bulk download | Already a known-good source for our project |

### Recommendation for v2

Build two ingesters first:

1. **`ui/freelib_ingest.py --source game-icons-net <input.zip>`** — read the bulk CC-BY archive, normalize sizes (256px or 512px), keep the SVG + render PNG, write `manifest.json` entries that include `attribution: "Lorc / game-icons.net / CC BY 3.0"` per icon. Game-icons.net also ships a CSV of author/license metadata per icon — preserve it. Effort: ~4-6 hours.
2. **`ui/freelib_ingest.py --source lucide`** (or Phosphor / Tabler) — fetch from npm/GitHub, no attribution, ideal for menu/HUD chrome (gears, X, arrows, settings). Effort: ~2-3 hours.

After that, **Kenney CC0 packs** are the obvious third because we already use Kenney audio elsewhere and the licensing is the simplest possible (CC0, zero requirements).

## 6. Godot 4.5 Theme Workflows

Godot's theming is well-documented but underused in most indie projects. The relevant doc set:

- [Introduction to GUI skinning](https://docs.godotengine.org/en/4.5/tutorials/ui/gui_skinning.html)
- [Theme](https://docs.godotengine.org/en/4.5/classes/class_theme.html)
- [StyleBox](https://docs.godotengine.org/en/4.5/classes/class_stylebox.html), [StyleBoxFlat](https://docs.godotengine.org/en/4.5/classes/class_styleboxflat.html), [StyleBoxTexture](https://docs.godotengine.org/en/4.5/classes/class_styleboxtexture.html)
- [Control](https://docs.godotengine.org/en/4.5/classes/class_control.html) (`add_theme_*_override` methods)

### Theme vs StyleBox vs ThemeOverride: when

- **Theme.tres**: use this for the **default look of every Control of a given type**. `Button` styles, `Panel` styles, default fonts, default icons. v1 already does this correctly.
- **StyleBox**: use these as the **building blocks**. `StyleBoxFlat` for solid-color UI (procedural, no texture), `StyleBoxTexture` for 9-slice frames, `StyleBoxLine` for separators, `StyleBoxEmpty` for transparent fills. v1 generates `StyleBoxTexture` for each 9-slice; consider adding `StyleBoxFlat` defaults for fallback.
- **ThemeOverride** (`add_theme_stylebox_override("normal", ...)` etc.): use this **only for one-off exceptions**. The "boss-fight HP bar uses a special style" case. Heavy use of overrides is a sign your Theme is undersegmented.

### Theme variations

Godot 4 has [theme type variations](https://docs.godotengine.org/en/4.5/tutorials/ui/gui_theme_type_variations.html) — a Control can declare `theme_type_variation = "DangerButton"` and Theme can register `DangerButton` as a variation of `Button`. This is the right way to do "red destructive action button," "compact inventory button," "ornate quest button" without making N separate scene-level overrides. v2 should generate variations: `Button`, `IconButton`, `DangerButton`, `QuietButton`. Effort: ~2-3 hours.

### Plugin ecosystem (Godot 4.5)

- [Themed Controls](https://github.com/limbonaut/limboai) and similar plugins exist but the ecosystem is thin compared to Unity's. Most production teams just author Theme directly.
- [Godot UI Design](https://github.com/godotengine/godot-demo-projects/tree/master/gui) demo projects from godotengine are still the cleanest reference for "how a real Theme should look."
- [Beehave](https://github.com/bitbrain/beehave) and other Godot ecosystem plugins are not UI-relevant.

### Recommended workflow for a full RPG UI

For a HUD + inventory + dialog + menu suite:

1. **One root Theme.tres** with all default Control styles.
2. **Theme type variations** for each functional UI region: `HUD_Panel`, `Inventory_Slot`, `Dialog_Box`, `Menu_Background`, `Tooltip`. v1's exporter already supports the synthetic `IconSet` type — extend that pattern.
3. **Per-faction palette swaps**: keep one Theme.tres but generate it from a `theme_palette.json`. Effort: ~3-4 hours, very high leverage for visual variety.
4. **HUD scene templates**: pre-built `.tscn` for HUD, inventory, dialog, menu, tooltip. v1 ships none; v2 should ship at least one HUD `.tscn` mockup that imports the generated Theme and shows the icons in a real layout. Effort: ~4-6 hours.

## 7. HUD Frame Design + Faction-Themed UI

Modern AAA references (Diablo 4, Path of Exile 2, Last Epoch, Lost Ark) and indie references (Tunic, Hades, Children of Morta) converge on the same design language:

- **Strong frame around portraits, action bars, and minimap** — heavy in dark fantasy, lighter in stylized.
- **Filigree corner ornaments** — easily parameterizable.
- **Faction palette swaps** — same structural frame, different metals/inks/gems.
- **Diegetic vs HUD blending** — Last Epoch and Diablo 4 both use slightly translucent panels with metallic borders; pure flat HUDs (Tunic) and pure diegetic UIs (Dead Space) are the extremes.

### Parameterizable frame templates

The pattern that works:

1. Generate a base 9-slice panel (existing `nine_slice.py`).
2. Composite **ornament overlays** at corners and edges.
3. Recolor through palette JSON.

Build `ui/frame_compose.py`:

```python
compose_frame(
    base="panel_v1",
    corners="ornament_filigree_a",
    edges=None,
    palette={"metal": "#a89060", "ink": "#1c160a", "gem": "#7c2"},
    out="ui/9slice/panel_gold.png"
)
```

This produces N visual variants from one base + one ornament library + N palettes. For 4 factions × 3 panel sizes × 2 states = 24 panels from ~3 source assets. Effort: ~6-10 hours, very high payoff.

### Ornament overlay sources

- Generated by Recraft V3 with prompt "isolated ornamental corner filigree, vector, transparent background"
- Free libraries: [Heraldicon](https://heraldicon.org/), public-domain heraldry SVGs (Wikimedia Commons), [The Noun Project](https://thenounproject.com/) ornament category
- Procedural: parametric scrollwork generators exist (e.g. [generative SVG repos on GitHub]) but quality is mid

## 8. Diegetic vs HUD UI

Quick reference for ARPG-likes:

- **Pure HUD** (Diablo 4, PoE 2, Lost Ark, Last Epoch): info-dense, fast to scan, locale-flexible. **Use for TLTE if combat is fast-paced and skill-rotation-heavy.** All v1 work targets this case.
- **Pure diegetic** (Dead Space, Alien Isolation): immersion ceiling is higher, but bandwidth is lower (you can't show 12 cooldowns on a hologram without it becoming HUD). **Wrong for ARPG-likes.**
- **Hybrid** (Hellblade, Resident Evil 2 inventory): worth selectively for inventory and lore-doc reading, not core combat.

For TLTE specifically — an ARPG with heavy skill rotation — **HUD-first is correct**. The interesting question is not "diegetic or not" but "how visually distinctive is the HUD vs the surrounding genre." Faction-themed Theme variations are the high-leverage answer.

## 9. Localization-Aware Icon Design

Common pitfalls:

- **Text on icons** — never bake glyphs into icon textures unless they are abstract logos. Numbers (cooldown displays, stack counts) belong in `Label` overlays inside the Control, not the icon PNG.
- **Direction-dependent icons** — arrows, flowing capes, draw-bow icons, "next page" chevrons. RTL languages (Arabic, Hebrew, Persian) flip UI directionality. Godot Controls auto-mirror layout when `layout_direction = LAYOUT_DIRECTION_RTL`, but they do **not** flip texture content. Tag direction-dependent icons in the manifest and provide either a horizontally-flipped variant or a runtime mirror flag.
- **Cultural icon-meaning mismatches** — skull = "death" in most cultures, but skull = "poison" in some game conventions and "danger/toxic" in others. Mailbox icons, OK/check marks, gestures (thumbs-up), animals (owl = wisdom in West, ill omen in some Asian cultures). Document icon semantic meaning in the manifest and avoid culturally loaded icons for system-critical UI (use abstract symbols instead).
- **Color-coding** — red/green for danger/safe is the dominant convention but accessibility demands a non-color channel as well (shape, position, label). Color-blind-safe palettes should be a generated Theme variation.
- **Icon size** — icons that need to communicate at 16px are usually different designs than icons that work at 64px. Generate at a high resolution (256+ px), but design-test at the **smallest** intended display size.

Add to manifest schema:

```json
{
  "id": "ico_arrow_next",
  "rtl_safe": false,
  "rtl_mirror": true,
  "min_display_px": 24,
  "semantic_tags": ["navigation", "forward"]
}
```

Effort: ~1 hour to add the schema fields, ~ongoing to populate them. The high-value thing is the `rtl_mirror` flag — it forces the question to be answered when the icon is created.

## What to Build Next

Ranked by leverage (highest first), with effort estimates and the existing v1 slot they extend.

### 1. `ui/freelib_ingest.py` — game-icons.net normalizer (HIGHEST LEVERAGE)

**Effort: 4-6 hours.** Slot: new sibling to `synth_icons.py`/`openai_icons.py`.

Single biggest jump in icon variety we can get for the project. ~5000 CC-BY icons normalized into our manifest schema, with attribution preserved. This unblocks ability/item iconography for prototyping immediately, gives the LLM (me) a real corpus to pick from when generating game data, and only requires writing a CC-BY zip parser + size normalizer + attribution-preserving manifest writer.

### 2. `ui/recraft_icons.py` — cloud generator with set consistency

**Effort: 3-5 hours.** Slot: new sibling to `openai_icons.py`.

Mirror the `openai_icons.py` shape exactly. Add `style_id` parameter (Recraft's style handle). Optionally request `recraft-v3-svg` and store both SVG + rendered PNG. Best path to "30 icons that all look like one set" without GPU work. Costs ~$1-2 for a 30-icon set.

### 3. `ui/local_diffusion_icons.py` — FLUX/SDXL local lane

**Effort: 8-12 hours.** Slot: new sibling to `openai_icons.py`.

Drive FLUX.1 \[schnell\] (Apache, shippable) through `diffusers` or a ComfyUI workflow JSON. Accept a LoRA path so the icon-LoRA can be swapped. Write the same manifest schema. The 5090 sits idle for UI work today; this puts it to use. The sub-task here is **finding or training a usable game-icon LoRA** — start with public Civitai LoRAs, train our own if none holds the style we want (~2-4 hours of LoRA training on the 5090).

### 4. `ui/frame_compose.py` — faction-variant frame templater

**Effort: 6-10 hours.** Slot: extends `nine_slice.py`.

Composes a base 9-slice + corner/edge ornaments + palette into N variants. Multiplies our 4 9-slice elements into 16-32 visual variants for free. The key file additions are an `ornaments/` library and a `palette.json` per faction/biome. This is the cheapest visual-variety multiplier we have. Pair with a Theme-variation generator in `export_godot.py` so each frame variant becomes a Theme type variation (`Panel_Faction1`, `Panel_Faction2`).

### 5. `ui/hud_mockup.py` — sample HUD scene generator

**Effort: 4-6 hours.** Slot: extends `export_godot.py`.

Generate a sample `hud.tscn` that imports the Theme, places action bar slots with the icon set, a healthbar 9-slice, an inventory button, and a tooltip Control. This is the "demo scene" everything ships with. Closes the loop: v1 generates resources but never shows them in a real layout. Adds a `preview_hud.png` rendered from the Godot scene as part of the preview grid. Most useful piece of dogfooding.

### Honorable mentions (lower leverage, do later)

- **`ui/pixellab_icons.py`** — pixel-art lane via PixelLab API. Effort 3-5 hours. Only build when a pixel-art region of the project actually exists.
- **`ui/svg_to_png.py`** — wraps `cairosvg` or `resvg` for SVG-input ingesters. Effort 1-2 hours. Probably part of `freelib_ingest.py`.
- **`pack_atlas.py` MaxRects upgrade** — swap shelf for `rectpack` MaxRects. Effort 2-3 hours. Defer until icon count > ~80.
- **`ui/aseprite_clean.py`** — pixel-grid + palette snap post-processor for pixel-art outputs. Effort 4-8 hours. Deferred with PixelLab.
- **`ui/localization_audit.py`** — scans manifest for missing `rtl_mirror`, `min_display_px`, baked text. Effort 2-3 hours.
- **Vector output via vtracer** — optional rasters-to-SVG conversion for atlas-free scaling. Effort 2-4 hours.

### Free libraries to ingest first

The two ingesters worth building immediately, in priority order:

#### A. game-icons.net (CC-BY 3.0/4.0)

- **Why first**: ~5000 icons, the single largest free RPG/fantasy icon corpus. Single consistent silhouette style. Most published indie ARPGs and roguelikes use this set — there is no faster way to look like a real game.
- **Build**: `ui/freelib_ingest.py --source game-icons-net --input <zip>`
- **Inputs**: the bulk archive zip (manual download once) **plus** the per-icon CSV that game-icons.net ships with author/license/tag metadata.
- **Outputs**: per-icon PNG at 256px, preserved SVG at original resolution, manifest entries with `attribution: "<author> / game-icons.net / CC BY <version>"`, and a top-level `ATTRIBUTION.md` aggregating all credits.
- **Style note**: monochromatic silhouettes. Recolor by Theme palette or by icon-time tinting. The **silhouette** convention also pairs perfectly with our 9-slice button styles — colored frame + monochrome icon is a clean default.
- **License hygiene**: CC-BY 3.0/4.0 require attribution. The aggregate-credits-page approach is explicitly allowed by game-icons.net's about/FAQ. Do not skip it.

#### B. Lucide (or Phosphor, or Tabler) — UI chrome

- **Why second**: zero-attribution MIT/ISC license, modern UI outline style, ideal for menu chrome (gear, close, arrow, search, settings). Complements game-icons.net rather than competing with it.
- **Build**: `ui/freelib_ingest.py --source lucide --names gear,x,arrow-right,search,settings,...`
- **Inputs**: pulled from the npm package or GitHub raw URLs; no manual download needed.
- **Outputs**: PNG + SVG, manifest entries with `attribution: null`, `license: "ISC"` (Lucide) or `MIT` (Phosphor/Tabler). Optionally generate weights/states (Lucide is single-weight, Phosphor has six).
- **Style note**: thin-line outline, modern, neutral. Does not collide with game-icons.net silhouette style — they coexist well in the same UI as long as system chrome (menus, settings) uses one and gameplay icons (abilities, items) uses the other. This is the convention most modern games follow.

If a third library is wanted: **Kenney UI Pack RPG / Kenney UI Pack** (CC0). Same project already ingests Kenney elsewhere; reuse the loader.

## Honest Tradeoffs

- The v1 build is small but the contract is right. Most of the leverage in v2 comes from **populating** the icon source lanes (game-icons.net + Recraft + FLUX), not from rewriting the spine.
- **FLUX.1 \[dev\] cannot be used for shipping commercial output.** This is the single most-frequently-missed fact about FLUX. Use \[schnell\] (Apache) or wait for an explicit Krea commercial path. Prototype freely on \[dev\] but the artifacts that go into a release have to come from \[schnell\] or a different model.
- **Recraft V3 is genuinely the best 2026 cloud option for icon sets.** It is cheap, LLM-driveable, and produces the most consistent set output. The only reason not to lead with it is if you have a religious objection to cloud APIs. Even so, building the local FLUX lane in parallel is the right hedge.
- **Pixel-art icons require a dedicated pipeline.** Do not try to make general-purpose models produce shippable pixel art. PixelLab plus Aseprite Lua post-processing is the working pattern.
- **Atlas packing is a solved problem at our scale.** Greedy shelf is fine for ~50 icons. Don't optimize this prematurely.
- **The biggest UI multiplier you can build is `frame_compose.py` plus Theme variations.** One base 9-slice + 4 ornament sets + 4 palettes = 16 visually distinctive frames. Most studios spend artist time on this. We should script it.
- **Localization-aware icon design is mostly process discipline.** The schema fields are easy. Remembering to populate them is the work.
- **HUD mockup scenes are dogfooding.** v1 ships resources and never assembles them. v2 should ship at least one assembled HUD scene per major Theme variation, even if the layout is rough.
- **AI generators that can't be driven from Python/CLI are not useful for this project.** Midjourney is the obvious example: best aesthetic ceiling, worst automation story. Skip until/unless an official API exists.

## Sources

- Recraft API: https://www.recraft.ai/docs
- Ideogram 3.0: https://about.ideogram.ai/3.0
- Midjourney docs: https://docs.midjourney.com/
- Adobe Firefly: https://firefly.adobe.com/, https://www.adobe.com/products/firefly.html
- OpenAI Images: https://platform.openai.com/docs/guides/images
- Google Imagen: https://deepmind.google/models/imagen/
- Black Forest Labs FLUX: https://blackforestlabs.ai/, https://huggingface.co/black-forest-labs/FLUX.1-dev, https://huggingface.co/black-forest-labs/FLUX.1-schnell, https://huggingface.co/black-forest-labs/FLUX.1-Krea-dev
- Stable Diffusion: https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0, https://huggingface.co/stabilityai/stable-diffusion-3.5-large
- PixelLab: https://www.pixellab.ai/
- Aseprite scripting: https://www.aseprite.org/docs/cli/, https://github.com/aseprite/api
- Free icons: https://game-icons.net/about.html, https://lucide.dev/, https://phosphoricons.com/, https://fonts.google.com/icons, https://heroicons.com/, https://tabler.io/icons, https://thenounproject.com/, https://opengameart.org/, https://kenney.nl/assets
- Atlas packers: https://www.codeandweb.com/texturepacker, https://free-tex-packer.com/, https://github.com/odrick/free-tex-packer-cli, https://github.com/secnot/rectpack, https://github.com/wo1fsea/pyTexturePacker
- Vector tools: https://github.com/visioncortex/vtracer, https://github.com/RazrFalcon/resvg, https://cairosvg.org/
- Godot 4.5 UI: https://docs.godotengine.org/en/4.5/tutorials/ui/gui_skinning.html, https://docs.godotengine.org/en/4.5/tutorials/ui/gui_theme_type_variations.html, https://docs.godotengine.org/en/4.5/classes/class_theme.html, https://docs.godotengine.org/en/4.5/classes/class_stylebox.html, https://docs.godotengine.org/en/4.5/classes/class_styleboxtexture.html, https://docs.godotengine.org/en/4.5/classes/class_styleboxflat.html, https://docs.godotengine.org/en/4.5/classes/class_control.html
- Local v1 docs: `D:\assets\HANDOFF_ui_2026_05_06.md`, `D:\assets\pipelines\ui\README.md`, `D:\assets\../docs/plans/RESEARCH_HANDOFF.md`
