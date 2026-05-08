# Research Brief — UI / Icons Pipeline (2026 SOTA)

## Goal

Identify 2026-current SOTA tools for **game UI icon generation** + **HUD composition** + **faction-style differentiation**. Current pipeline produces good placeholders but no hero-quality content.

## Hardware target

- RTX 5090 Laptop (24 GB VRAM, Blackwell sm_120, CUDA 12.8+ / torch >=2.7)
- Windows 11; Python 3.11/3.12 venvs preferred

## Context

We have a working UI icon pipeline that produces 256×256 RGBA PNG icons + a 4096² atlas + per-faction 9-slice frames + per-faction HUD mockups. **135 icons total** mixing three sources:
- ~37 first-party procedural (`synth_icons.py`, 1-3 KB each — simple line drawings)
- 55 game-icons.net (CC-BY 3.0, 13-22 KB each — real artist work)
- 22 lucide + 18 phosphor (MIT — UI utility icons)

**4 factions** (ashen_pact, ember_legion, tide_bound, verdant_court) with palette JSONs + per-faction 9-slice frames + 28 HUD preview PNGs (4 factions × 7 states). User audition verdict on factions: "**just a color swap.**" The system *can* express diversity but the procedural generator hasn't been pushed to use that range.

**Cloud routes plumbed but never run:**
- `openai_icons.py` (gpt-image-1)
- `recraft_icons.py` (Recraft V3, supports SVG output + set-style consistency)
- `pixellab_icons.py` (PixelLab API)
- `local_diffusion_icons.py` (FLUX-schnell via ComfyUI — GPU-gated)

**LoRA training plumbed but never trained:** `lora_train.py` exists, `ui/lora/v1_smoke/` has scaffold dataset + train_command.sh, no checkpoint produced.

**6 cloud-route prompts** in `prompts.json` (e.g. "fantasy game icon: a roaring red dragon head, side profile") — never executed.

## Specific questions

1. **2026 SOTA for game icon generation.** Recraft V3 was strong in 2025. Is it still the best for *game icons specifically* (not generic vector / illustration), or has FLUX 2 / Imagen 4 / something else taken over? Specifically: "fantasy game inventory icon" / "spell icon" / "item icon" use cases.

2. **Faction-style LoRA training in 2026.** We have a scaffold to train a per-faction style LoRA so `local_diffusion_icons.py` can produce icons in faction-specific styles. What's the 2026-current best practice? FLUX-LoRA via ComfyUI? Kohya scripts? Replicate-fine-tuning?
   - Specifically: how many reference images per faction to seed it (we'd hand-author or collect 10-30 per faction)?
   - What training time on RTX 5090?
   - What's the 2026-current LoRA *runtime* — apply trained LoRA at inference time via ComfyUI workflow?

3. **HUD composition / mockup tools.** Our HUD mockups are tiny (16-19 KB PNGs) procedurally composed via PIL. They read as color-swap. Is there a 2026 tool for "given faction palette + icon set + 9-slice frames, produce a hero-quality HUD mockup that *feels* different per faction"? Beyond just programmatic compositing.

4. **9-slice + atlas tooling.** We use `pack_atlas.py` for atlas + `nine_slice.py` for slicing. Are these still 2026-current, or has there been progress in atlas packing or 9-slice generation?

5. **SVG → PNG reverse.** `vtracer_roundtrip.py` does PNG ↔ SVG via vtracer. Is vtracer still the 2026 standard, or has there been an upgrade?

6. **Hero icon pass.** Many games ship with ~30-50 hero icons (key spells/weapons/consumables) that are individually painted, then bulk procedural for the rest. What's the 2026 workflow for the "hero-pass" specifically? Is it (a) cloud diffusion (Recraft / FLUX), (b) cloud LLM with vision (OpenAI gpt-image-1), (c) commission, (d) something else?

7. **Style-unification across mixed-source library.** Our 135 icons mix procedural + game-icons.net (CC-BY) + lucide/phosphor (MIT). They don't visually match. Is there a 2026 "stylize a batch of icons to match a reference style" tool? ControlNet pass? Fine-tuned Img2Img model?

8. **CC0 SVG library quality 2026.** `freelib_ingest.py` ingests from game-icons.net, lucide, phosphor. Are there 2026-current free-license fantasy-icon libraries we should add (e.g., new 2025 releases)?

## Format of response

Per question:
1. Top 2-3 tool/approach recommendations with one-paragraph why
2. Hardware/install fit (RTX 5090 / Windows native; ComfyUI integration plus)
3. License + cost notes (open-weights preferred; cloud OK if cheap per icon — we'd run ~30 hero icons)
4. Maturity check
5. **Honest comparison** — does the new tool actually beat Recraft V3 / synth_icons / FLUX-schnell for game icons, or is it lateral?

## Out of scope

- 2D UI editors (we won't Figma/Affinity)
- Generic logo design
- Web UI components (we ship Godot Control nodes)

## After response returns

Update `docs/pipeline_reviews/01_ui_icons.md` and `pipelines/ui/README.md`. The user said:
- Faction system is "just a color swap" — needs real differentiation work
- Atlas + icons are "good placeholders" — would need much better work to ship
- LoRA training is the unblocking step we haven't taken
