# Research Brief — VFX Shaders Pipeline (2026 SOTA)

## Goal

Identify 2026-current SOTA tools for **iterative shader generation** for game effects — magic circles, beams, dissolves, portals, force fields, ground glows, projectile trails. Current pipeline is an LLM-driven param-mutation framework against templates; never aimed at a production target.

## Hardware target

- RTX 5090 Laptop (24 GB VRAM, Blackwell sm_120, CUDA 12.8+ / torch >=2.7)
- Windows 11; Python 3.11/3.12 venvs
- Godot 4.5 is the runtime target — output is `.gdshader` files

## Context

This is a **separate VFX lane** from the content-baker (different brief). This one produces `.gdshader` files (Godot ShaderMaterial), not flipbooks. Use case: anything driven by `TIME` in a fragment shader — rings, beams, ripples, dissolves, portals, shields, force fields.

**Current framework** (`art_lab/`):
- 6 first-party `.gdshader` templates: beam_lightning_2d, dissolve_fire_2d, portal_swirl_2d, ring_field_2d, shield_ripple_2d, macro_detail_v1 (terrain). All `canvas_item` 2D except macro_detail.
- LLM-driven workflow: generate population (param mutations) → render previews (CPU proxy 128×128 OR Godot CLI render) → score with 12 image metrics + role-specific gates → diversity-filter promote shortlist → LLM review packet (compact JSON) for next iteration.
- 5 batches done; **all named `*_smoke_*` or `*_mutate_*`**. Reference set is **one image** (`smoke_portal_ref/ref_001.png`). Production batches don't exist yet.

The framework is well-designed. We've never aimed it at a real game-design target.

## Specific questions

1. **What's 2026 SOTA for AI shader generation?** Several "AI shader generator" claims existed in 2024/2025 era but most were unreliable. Has anything matured? Specifically: tools that take a *reference image of a desired effect* + a *natural-language description* and produce a working Godot/Unity/UE shader?

2. **Reference-based shader iteration.** Our scoring system uses `reference_sets/<name>/*.png` to compare candidate flipbooks against curated targets. Is the CV-metric approach (alpha-coverage + contrast + edge-energy + colorfulness + motion + flicker) still 2026-sensible, or has CLIP-based or other ML-driven similarity scoring become the standard for shader QA?

3. **Shader template libraries.** We have 6 templates. Are there 2026-current open-source libraries of game-shader templates (Godot 4.x compatible canvas_item / spatial / sky / particle_process shaders) that would expand our coverage cheaply? Specifically interested in: ground_glow, AOE_indicator, weapon_trail, projectile_trail, hit_flash, status_halo, dash_blur, charge_pulse, energy_weapon, water surface, terrain overlay.

4. **Genetic / evolutionary shader optimization.** Our `shader_evolve.py` does simple param mutation + diversity-filtered promotion. Is there a 2026 tool that does *real* genetic shader optimization (crossover + mutation + automated breeding cycles with ML-driven fitness)? Examples or papers?

5. **LLM-shader-loop workflows.** We have `llm_review_packet.json` that lets an LLM iterate on shader params without seeing screenshots. Is there a 2026 standard for "agent that writes/iterates shader code with metric feedback"? Tools like Cursor/Aider integrated with shader workflows?

6. **Shader-from-video.** Is there a 2026 method to take a reference *video* (e.g., a clip of an effect from another game) and synthesize a Godot shader that approximates it? Even partial success on known categories (rings, ripples, dissolves) would be huge.

7. **Production shader management.** Once we promote a shader from `review_queues/` to a winner, where should it live? Is there a 2026 game-shader-package convention? Versioning? Variant tracking? We have `art_lab/shaders/templates/` for first-party + `art_lab/shaders/batches/` for iterations + `art_lab/shaders/review_queues/` for shortlists; no "production" location exists.

## Format of response

Per question:
1. Top 2-3 tool/approach recommendations with one-paragraph why
2. Hardware/install fit
3. License + cost notes
4. Maturity check
5. **Honest comparison** — does the new approach actually beat our LLM-mutation framework when aimed at a real target, or is it lateral?

## Out of scope

- Visual shader editors (we want programmatic batch generation)
- Manual shader authoring tools (Shader Graph, etc.)
- Engine-locked solutions (UE-only, Unity-only — must work for Godot 4.5)

## After response returns

Update `docs/pipeline_reviews/07_vfx_shaders.md` and `art_lab/SHADER_WORKFLOW_STATUS.md`. Specifically the user wants to:
- Decide if the current LLM-mutation framework is the right path or should be replaced
- Identify 2-3 missing template categories to add
- Aim one real (non-smoke) batch at a production target — pick the right reference set + template combo
