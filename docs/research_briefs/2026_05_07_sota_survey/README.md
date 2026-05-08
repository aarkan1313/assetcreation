# SOTA Tooling-Gap Survey — 2026-05-07

7 independent research briefs, one per pipeline. **Dispatch one at a time** to a research agent (Perplexity, Claude/GPT with web access, etc.).

Each brief is self-contained: a fresh agent can act on it without project context.

## How to use

1. Read a brief (e.g. `01_ui_icons.md`)
2. Copy the brief text into a research agent / new chat
3. Get the response back, save as `01_ui_icons.response.md` next to it
4. We update the relevant pipeline review + docs based on findings
5. Repeat for the next brief

## Brief order (suggested, by leverage)

| # | Pipeline | Why it's worth surveying |
|---|---|---|
| 01 | [Characters / Animation](01_characters_animation.md) | Production-content lane; current animation step uncalibrated. Highest leverage. |
| 02 | [Textures (now active)](02_textures.md) | **Active** — covers both tileable ground (worker lane) AND mesh-driven hero terrain (MaterialAnything retrofit) |
| 03 | [Props (image-to-3D)](03_props_image_to_3d.md) | Trellis2 default; what surpasses it in 2026? |
| 04 | [VFX 3D Bake (GPU)](04_vfx_3d_bake.md) | CPU bakers shipped; Phase 13 needs GPU |
| 05 | [VFX Shaders](05_vfx_shaders.md) | Best framework, never aimed |
| 06 | [Audio](06_audio.md) | Output archived; need real per-asset path |
| 07 | [UI / Icons](07_ui_icons.md) | Faction LoRA + hero-icon generators |
| 08 | [Game Data Balance](08_game_data_balance.md) | Long-term goal; ML-driven balance? |

## Cross-cutting notes for every brief

Every brief includes the same hardware context block so the research agent can filter for compatibility:

> **Hardware:** RTX 5090 Laptop (24 GB VRAM, Blackwell sm_120, requires CUDA 12.8+ / torch >=2.7). Windows 11. Python 3.11/3.12 venvs. We do native Windows installs where possible, WSL2 only when forced (Linux-only deps).
