# Handoff — 2026-05-07 night (Path 2 parked, project state snapshot)

**Tonight's work in one line:** brought the character_inpaint (Path 2) pipeline mechanically correct end-to-end, then user parked it ("factions aren't a big deal right now"). Pipeline is in a known-good state for later pickup.

This handoff is also the **whole-project orientation doc** for whoever picks up next — read top-to-bottom if you're new to `D:\assets`.

## Where to start (in order)

1. [README.md](../../README.md) — project intro + doc map + current focus
2. [PIPELINE_DIRECTORY.md](../../PIPELINE_DIRECTORY.md) — at-a-glance status of every pipeline
3. [docs/plans/ROADMAP.md](../plans/ROADMAP.md) — current priorities + per-brief completed work
4. [docs/plans/NEXT_STEPS_2026_05_07.md](../plans/NEXT_STEPS_2026_05_07.md) — cross-cutting state, free-wins backlog, Path 2 progress table
5. [docs/pipeline_reviews/](../pipeline_reviews/) — honest quality verdicts per lane (the calibration pass)

## What `D:\assets` is

Self-generated AAA-grade asset factory for **Godot 4.5 / JK Engine / TLTE**. Eleven pipelines (Characters, Props, Audio, UI, VFX 3D, VFX shaders, Game Data, Textures, DEM Fetch, Character Inpaint, Scene composition) plus 13 animator tools (each in its own venv). Pipeline plumbing is the deliverable; content is mostly placeholder until game-design intent dictates focused authoring passes.

## Project state — honest read

| Pipeline | Pipeline state | Content state |
|---|---|---|
| **Characters** | ✅ most-complete | 33 GLBs, animation step uncalibrated |
| **Props** | ✅ Phase 11 mature | 1 hero (obelisk) + 14 procedural-variant families |
| **Game Data** | ✅ best infrastructure | 14 toy records, balance review long-term |
| **VFX (3D bake)** | ✅ working | 46 effect.json, 18 are palette-swap recolors |
| **VFX (shaders)** | ✅ best framework | 5 batches, all smoke tests, never aimed |
| **UI / Icons** | ✅ working placeholders | 135 icons mixed sources |
| **Audio** | ✅ pipeline kept | Output archived 2026-05-07 (was noise) |
| **Textures** | 🟡 worker active | Phase B+D done, Phase C next |
| **DEM Fetch** | ✅ working | 222 TIFFs / 8.1 GB at `dems/` |
| **Character Inpaint** | 🟡 mechanically correct | FLUX prompt quality is the open gap (parked tonight) |
| **Scene composition** | ❌ gone | `world3/` rebuilding |

Full detail in [PIPELINE_DIRECTORY.md](../../PIPELINE_DIRECTORY.md). Honest verdicts in [docs/pipeline_reviews/](../pipeline_reviews/).

## Tonight's actual work — Path 2 inpaint pipeline

User direction: bring `pipelines/character_inpaint/` from "runs without errors but output looks unchanged" to "actually works visually." We diagnosed five real bugs by inspecting intermediate PNGs:

1. Camera orbit started at azimuth 0° → all 6 views were side profiles. Fixed: start at 270° (front-facing for Meshy/Trellis2 GLBs which face +Y).
2. Mask circle was at 66% down (hip/loincloth) → fixed to 45% (sternum/pec).
3. FLUX.1-Redux is a style adapter, not a logo compositor → `use_redux=False` default; prompt-only inpaint with denoise=0.95.
4. `_build_workflow()` was missing the Redux conditional block AND the `return nodes` statement → function returned `None`. Fixed.
5. FLUX result was being pasted raw (whole 512x512 including transparent background) → fixed to composite only inside (mask AND source-character-alpha > 128).
6. `back_project._nvdiffrast_backend` was using azimuths starting at 0° while renderer uses 270° → fixed to match renderer's `front_azimuth_deg=270`.

After all six fixes, `goblin_p_ashen_v5.glb` produces cleanly. **Remaining open gap:** FLUX.1-Fill fills the masked chest with "more goblin skin" rather than a distinct insignia — the surrounding green-skin context overwhelms the text prompt. Parked here.

Commits: `d2b6f72` (code + plans-doc updates), `81eebf9` (top-level docs).

## Path 2 — when to resume

User said: "factions aren't a big deal right now, i know inpainting is cool but its a longer workflow." So this is parked, not abandoned. When it matters, three approaches in order of effort:

1. Prompt + denoise tuning (sub-hour) — explicit emblem shape, denoise=1.0, maybe negative prompt
2. Composite-then-refine (1-2 hours) — paste reference into mask first, FLUX with low denoise to integrate
3. ControlNet-reference (half-day) — proper reference conditioning, the actual SOTA answer

Pipeline lives at `pipelines/character_inpaint/`, design at [docs/plans/PATH_2_INPAINT_DESIGN_2026_05_07.md](../plans/PATH_2_INPAINT_DESIGN_2026_05_07.md), and the venv at `pipelines/character_inpaint/.venv/`. ComfyUI must be running at `127.0.0.1:8188` with FLUX models loaded for the live backend.

## What's open / not parked

From [docs/plans/NEXT_STEPS_2026_05_07.md](../plans/NEXT_STEPS_2026_05_07.md), the active backlog:

**The "next planned" candidate:** Characters animation deep-dive — recover the run config, verify rigging quality on humanoid + non-humanoid. The animation step is the one quality-uncalibrated stage in the most-mature pipeline.

**Free-wins items 4-12** (sub-day each, no cloud, no curation gating):
- #4 Schneider-Vos cloud noise upgrade in `baker_volumetric_fog.py`
- #5 `audio_clip` field on VFX manifest schema
- #6 `getsentry/json-schema-diff` CI gate for migrations
- #7 Hash-based incremental linker (~50 LOC) for `pipelines/game_data/`
- #8 Import 3 curated shader templates with license sidecars
- #9 `art_lab/library/<category>/<name>/manifest.json` convention + promote helper
- #10 100-line Yarn static analyzer
- #11 DSPy + GEPA scaffold for items/abilities
- #12 Visual A/B inspection of decimate vs meshopt LODs (quantitative side done; needs eyes-on)

**Background workers:**
- `world3/` Godot scene-composition rebuild
- Texture quality improvement in `world/textures/library/` + `pipelines/textures/`

**Cloud-parked** (per "no cloud right now"): Rodin Gen-2, Stable Audio 2.5, Recraft V4 Pro Vector run, DeepSeek V4-Pro, Claude API runs.

## Memory + persistent context

User-level memory at `C:\Users\josep\.claude\projects\d--assets\memory\` covers:
- D: drive space constraint (check before bulk pulls)
- Quality over coverage (polish existing scenes, don't build more)
- Write-tool UTF-16 gotcha on Windows
- Research-before-installing rule
- One-venv-per-lane architecture
- Path 2 UV fragmentation finding
- FLUX.1-Fill+Redux model stack (the non-obvious correct choices)
- nvdiffrast Blackwell build gotcha
- torch 2.6+ weights_only trap

Index at `MEMORY.md` in that directory. New agents pick this up automatically.

## Don't-do list (decided by 2026 SOTA, don't re-investigate)

From the brief sift in NEXT_STEPS — abbreviated:
- Don't fine-tune game-content LoRAs (general models do this well enough)
- Don't migrate Yarn → Ink / Dialogic 2 (lateral)
- Don't adopt USD for VFX manifest (overkill)
- Don't keep AniMo or MocapAnything on the install list (no checkpoints)
- Don't deepen MaterialAnything for hero terrain (Hunyuan3D-Paint 2.1 is the upgrade)
- Don't pursue diffusion VFX (wrong tool for alpha-matted flipbooks)
- Don't adopt Neo4j / KuzuDB at <20K records

Full list at the bottom of [NEXT_STEPS_2026_05_07.md](../plans/NEXT_STEPS_2026_05_07.md).

## TL;DR for whoever picks up next

Pipeline plumbing is real, content is placeholder, focused authoring passes are the unlock. Path 2 inpaint is parked in a known-good state. The natural "next" candidate is the characters animation deep-dive. Free-wins items 4-12 are sub-day fillers. Cloud is parked entirely.

User cadence: doesn't want a ton of edits; surgical updates only; explain decisions concisely; don't fan things out without explicit direction.
