# Shader Workflow Status And Research Handoff

Date: 2026-05-06

This document explains what was added to the shader workflow, what is verified,
what still needs work, and where new research results should be attached.

Full implementation plan for integrating the current research:

`D:\assets\art_lab\SHADER_RESEARCH_INTEGRATION_PLAN.md`

## Goal

Build a semi-automated shader creation and review pipeline where an LLM can:

1. Generate or mutate many shader candidates.
2. Render inspectable previews, flipbooks, and galleries.
3. Score candidates using metrics rather than screenshot OCR.
4. Evolve candidates toward curated visual references.
5. Promote only a small set of strong, diverse outputs for human review.

The intended scope is broad: spell VFX, projectiles, auras, shields, portals,
ground/world shaders, UI glows, dissolves, force fields, decals, and eventually
material/world-map shaders.

## Older Project Found

The likely older HTML shader workflow was found here:

`C:\Users\josep\Downloads\shader-cauldron-v6.html`

A preserved copy now lives here:

`D:\assets\art_lab\legacy\shader-cauldron-v6.html`

Notes are here:

`D:\assets\art_lab\legacy\FOUND_OLD_SHADER_WORKFLOW.md`

What it had:

- WebGL live shader preview.
- Procedural expression grammar.
- Style pools and random generation.
- Knobs/sliders.
- Mutate and auto-cycle modes.
- Screenshots, favorites, history.
- GLSL and Godot shader export.

Why it was not enough:

- No durable batch artifact folders.
- No objective review/ranking layer.
- No reference-image scoring.
- No promotion queue.
- No engine-rendered acceptance pass.
- Too dependent on human browsing and visual judgment.

## What Was Implemented

### Batch Generation And Review

File:

`D:\assets\art_lab\tools\shader_batch_review.py`

Purpose:

- Generates many variants from first-party Godot shader templates.
- Writes `.gdshader`, `.tscn`, `request.json`, PNG frames, preview, flipbook.
- Scores candidates from pixels and motion, not OCR.
- Writes `gallery.html`, `batch_summary.json`, `llm_review_packet.json`,
  and `llm_review.md`.

Current score signals include:

- Alpha coverage.
- Brightness and contrast.
- Colorfulness.
- Edge/detail energy.
- Center balance.
- Animation motion.
- Flicker.
- Highlight clipping.
- Role-specific fit for aura, beam, projectile, shield, portal, dissolve,
  ground, UI, and AOE.

Important behavior:

- Numeric score and `grade` are now gated separately.
- A candidate can score well but still be held at `review` or `reject` if it has
  serious gate issues.

### Review Queue Promotion

File:

`D:\assets\art_lab\tools\shader_promote.py`

Purpose:

- Copies high-scoring candidates from one or more batches into a compact human
  review queue.
- Applies simple visual diversity filtering so the queue does not fill with
  near-duplicates.
- Writes `manifest.json`, `index.html`, and `review.md`.
- Includes mutation commands for follow-up exploration.

### Reference-Set Scoring

File:

`D:\assets\art_lab\tools\shader_reference_score.py`

Purpose:

- Compares a batch against curated reference image folders.
- Uses deterministic image features, not an LLM screenshot read.
- Writes `reference_scores.json` and `reference_review.md`.
- Optionally updates `batch_summary.json`.

Reference image folders live here:

`D:\assets\art_lab\shaders\reference_sets\<name>\`

This is useful when the question is:

- "Which candidates are closest to these storm projectile references?"
- "Which portal variants match this occult/rune target?"
- "Which UI glow looks closest to this HUD treatment?"

### Evolutionary Search

File:

`D:\assets\art_lab\tools\shader_evolve.py`

Purpose:

- Evolves valid Godot template parameters toward one or more reference images.
- Keeps the normal shader-quality gate.
- Adds reference similarity as selection pressure.
- Writes normal batch artifacts plus `evolution_summary.json`.

Example:

```powershell
python art_lab\tools\shader_evolve.py `
  --reference art_lab\shaders\reference_sets\storm_projectile `
  --batch-id storm_projectile_evolve_001 `
  --template beam_lightning_2d `
  --template portal_swirl_2d `
  --population 36 `
  --generations 5 `
  --elites 6 `
  --frames 8 `
  --size 256
```

This is the practical version of the genetic shader idea. It does not evolve
arbitrary GLSL yet; it evolves parameters over valid templates. That is deliberate
because it avoids compile-failure noise and keeps outputs Godot-compatible.

### Godot Render Wrapper

File:

`D:\assets\art_lab\tools\shader_godot_render.py`

Purpose:

- Runs generated candidate projects through Godot CLI when a Godot binary is
  available.
- Writes `preview_godot.png`, `flipbook_godot.png`, `godot_frames/`, and a
  `godot_render` block into `request.json`.

Status:

- The wrapper was syntax-tested.
- Full Godot rendering was not validated in this pass because no Godot executable
  path was found by the script during the session.

### Dashboard

File:

`D:\assets\art_lab\tools\shader_lab_index.py`

Output:

`D:\assets\art_lab\shaders\index.html`

Purpose:

- Static index of recent batches, review queues, reference sets, templates, the
  operator prompt, and the recovered Shader Cauldron HTML.

### LLM Operator Prompt

File:

`D:\assets\art_lab\shaders\prompts\llm_shader_operator.md`

Purpose:

- Gives an LLM the concrete command loop:
  broad batch, read packet, mutate winners, use references/evolution when
  available, promote a small review queue, optionally render through Godot.

Key rule:

- Do not rank shaders by OCR or free-form screenshot descriptions. Use metrics,
  structured packets, reference scoring, and galleries.

## Current Shader Templates

Folder:

`D:\assets\art_lab\shaders\templates\`

Current first-party Godot templates:

- `ring_field_2d.gdshader`: magic circles, rings, runes, aura fields.
- `beam_lightning_2d.gdshader`: beams, bolts, lightning slashes.
- `dissolve_fire_2d.gdshader`: burn edges and fire dissolve.
- `shield_ripple_2d.gdshader`: shield surfaces and hit ripples.
- `portal_swirl_2d.gdshader`: portal/vortex effects.
- `macro_detail_v1.gdshader`: spatial macro/detail material shader for terrain
  or close-up surfaces.

The template library is still small. This is the biggest creative bottleneck.

## Verified Smoke Tests

The following were run successfully:

```powershell
python -m py_compile `
  art_lab\tools\shader_batch_review.py `
  art_lab\tools\shader_promote.py `
  art_lab\tools\shader_reference_score.py `
  art_lab\tools\shader_godot_render.py `
  art_lab\tools\shader_lab_index.py `
  art_lab\tools\shader_evolve.py
```

Batch smoke:

`D:\assets\art_lab\shaders\batches\shader_review_upgrade_smoke_001`

Evolution smoke:

`D:\assets\art_lab\shaders\batches\shader_evolve_smoke_001`

Promotion smoke:

`D:\assets\art_lab\shaders\review_queues\evolve_smoke_review_001`

Dashboard regenerated:

`D:\assets\art_lab\shaders\index.html`

## Research Integrated So Far

The current architecture reflects these conclusions:

- ShaderGPT-style text-to-GLSL tools are useful for ideation, but not reliable
  enough to be the backbone of a Godot asset factory.
- VLMaterial and MultiMat are strong evidence for constrained program/node-graph
  generation, renderer-in-loop validation, and search over valid graph/program
  space.
- LLMs are better used for template authoring, critique text, tagging, and
  parameter strategy than as final screenshot judges.
- Evolutionary search is useful now if it operates over known-good templates and
  reference images.
- Reference scoring should start simple and deterministic before adding heavier
  LPIPS/CLIP/DINO-style model scoring.

Longer research writeup:

`D:\assets\research\H_shader_generation_review_pipeline.md`

Research intake #1:

`D:\assets\research\shades.md`

Review of what changed from that intake:

`D:\assets\research\shades_intake_review.md`

Main deltas from that research:

- **AI Co-Artist** validates the evolutionary shader direction. Our local
  `shader_evolve.py` is the safer Godot-template version of that idea.
- **ShaderToy-MCP**, `shaders21k`, and `shadermatch` are worth testing as an
  external-reference/RAG lane, but only with explicit license tracking.
- **StableMaterials** and **Chord** belong in the PBR/material backlog, not the
  live spell-shader backbone.
- **Godot AI MCP** is worth watching for editor integration after the Godot CLI
  render path is validated.

Research intake #2:

`D:\assets\research\deep_research_report_5_image_to_shader.md`

Review of what changed from that intake:

`D:\assets\research\deep_report_5_intake_review.md`

Main deltas from that research:

- Use a formal **representation ladder**: parameter set, PBR maps, bounded graph
  or DSL, raw source code, neural material.
- Keep **MaterialX/OpenPBR** on the surface-material/interchange roadmap, not as
  a blocker for live spell/VFX shaders.
- Add **MaterialPicker**, **ControlMat**, and **Generative Neural Materials** to
  the material/PBR watchlist.
- Track **Slang/Slang.D** for future cross-backend or differentiable shader
  experiments, but do not make it first-week Godot work.
- Plan to synthesize our own paired corpus from accepted local shader templates:
  `(reference render, template, params, shader source, metrics)`.

## What Still Needs Work

### 1. Godot Engine Render Validation

Need:

- Find or install the Godot 4.5 executable.
- Run `shader_godot_render.py` on a promoted queue.
- Confirm headless vs non-headless behavior on Windows RTX hardware.
- Check that generated `.tscn` files render exactly like the CPU proxy previews.

Why it matters:

- CPU previews are useful for broad search, but Godot-rendered flipbooks should
  be the acceptance artifact.

### 2. Larger Template Library

Need more templates for:

- Projectile cores and trails.
- Impact bursts and shockwaves.
- Ground AOEs and decals.
- UI glows, frames, borders, cooldown fills, rarity effects.
- Spatial force fields and shields.
- Water, lava, fog, heat haze, poison pools.
- Terrain overlay shaders.
- Particle process shaders.

The workflow will only become "AAA-ish" when the template vocabulary becomes
rich. Parameter mutation cannot invent all missing structure by itself.

### 3. Better Reference Scoring

Current scoring is intentionally lightweight. It should be upgraded in stages:

1. Keep deterministic features as a baseline.
2. Add LPIPS-style perceptual distance for texture/material references.
3. Add CLIP/DINO image embeddings for broad style clustering.
4. Add temporal metrics for flipbooks, not only still previews.
5. Add role-specific reference matching, such as silhouette for projectiles,
   radial structure for portals, frame regularity for UI, and surface coverage
   for ground shaders.

### 4. True Shader DSL / Expression Grammar

The old Cauldron had a procedural expression grammar. The new pipeline currently
uses fixed templates plus parameter mutation.

Needed next:

- Port useful Cauldron expression families into Python.
- Restrict generated expressions to safe, tileable, real-time-safe primitives.
- Compile DSL blocks into Godot shader code.
- Add compile and render checks after every generated code mutation.

This is where LLMs should help: propose DSL blocks and refactor common patterns,
not write arbitrary large GLSL files from scratch.

### 5. Material / Node-Graph Path

Research points toward a second path for materials:

- Image or prompt to procedural material program/node graph.
- Render in Blender, Mitsuba, MaterialX, or Godot.
- Compare to reference maps or PBR outputs.
- Store editable procedural source plus baked maps.

Possible targets to evaluate:

- VLMaterial as a research reference.
- MaterialX as an interchange/export layer.
- Blender shader nodes via Python.
- Material Maker graph/source formats.
- Mitsuba or Blender as renderer-in-loop.

This is more relevant for ground/world/UI/material shaders than for spell VFX.

### 6. Dataset And License Audit

Found older related folder:

`C:\Users\josep\Documents\Newest\shader-training-pipeline`

It appears to be a Shadertoy scraping / Qwen2.5-VL LoRA experiment.

Before using it:

- Audit licenses.
- Separate permissive sources from non-reusable sources.
- Use it for idiom/reference mining before fine-tuning.
- Do not train or generate production assets from unclear data.

### 7. Human Review UX

Review queues are functional but basic.

Need:

- Better HTML compare view.
- Candidate favoriting/notes.
- Side-by-side reference vs render.
- Animated preview playback controls.
- One-click "mutate this" command copying.
- "Promote to library" step with tags and Godot pack export.

### 8. External Shader Reference Lane

The first research intake makes a strong case for a separate Shadertoy/RAG lane.

Need:

- Define license policy before importing any community shader code.
- Store source URL, author, license, tags, and conversion notes for every
  imported reference.
- Test read-only ShaderToy-MCP or a direct Shadertoy API/script workflow.
- Test `shaders21k` only as a reference/evaluation corpus until licensing is
  clear.
- Evaluate `shadermatch` as an optional Shadertoy-style critic, not as the main
  Godot quality gate.

Why it matters:

- Shadertoy contains many canonical fire, lightning, portal, water, SDF, and
  raymarching idioms.
- It can improve template authoring and RAG-assisted code suggestions.
- It should not become a copy-paste production source.

### 9. PBR Material Generator Bench

The shader lab should stay focused on live/effect shaders, but the material side
should test the stronger candidates from `shades.md`.

Need:

- Run StableMaterials on 3 hard materials and compare against the existing
  `aaa_texture.py` workflow.
- Run Chord if ComfyUI nodes/weights are practical to install.
- Keep MaterialPalette as a photo-to-PBR candidate if that use case becomes
  important.
- Track MaterialPicker for photo/text-to-material map generation.
- Track ControlMat for tileability/noise-rolling ideas if code/weights become
  practical.
- Track Generative Neural Materials as research only.

Why it matters:

- Ground/world/UI shaders often need strong texture maps as inputs.
- These tools may improve Path B without changing the live shader architecture.

### 10. Representation Ladder And Template Metadata

The second research intake makes the "shader" ambiguity explicit. We need to
make the local pipeline explicit too.

Current lanes:

- Effect parameter lane: Godot `.gdshader` templates plus `request.json`.
- Effect DSL lane: future Cauldron-style expression grammar compiled to Godot.
- External GLSL lane: Shadertoy/RAG/import with license tracking.
- PBR material lane: texture maps and StandardMaterial3D inputs.
- Material graph lane: MaterialX / Material Maker / Blender nodes.
- Neural material lane: research only.

Need:

- Add sidecar metadata/schema files for every shader template.
- Store role, target, intended use, parameter ranges, preview defaults, expected
  coverage/motion, performance tier, and known failure modes.
- Use this metadata as the future retrieval and validation surface for LLMs.

## Where To Put Incoming Research

Use this structure when giving new findings:

```text
Tool / paper / repo:
Link:
License:
Last meaningful update:
Runs locally on Windows/WSL?:
API/CLI available?:
Shader target: Godot / GLSL / WGSL / HLSL / MaterialX / Blender / Unity / Unreal
What it can actually generate:
What it cannot do:
Integration idea:
Recommended action: adopt / test / watch / ignore
```

Best landing spots:

- General shader workflow research:
  `D:\assets\research\H_shader_generation_review_pipeline.md`
- Operational status and TODOs:
  `D:\assets\art_lab\SHADER_WORKFLOW_STATUS.md`
- Tool commands:
  `D:\assets\art_lab\README.md`
- LLM operating procedure:
  `D:\assets\art_lab\shaders\prompts\llm_shader_operator.md`
- Source code:
  `D:\assets\art_lab\tools\`
- Shader templates:
  `D:\assets\art_lab\shaders\templates\`

## Recommended Next Build Sequence

1. Add three curated reference sets:
   - `storm_projectile`
   - `occult_portal`
   - `holy_shield`
2. Run one broad batch per target.
3. Run `shader_evolve.py` for 3-5 generations per reference set.
4. Promote 12-24 candidates per target.
5. Validate the promoted queues through Godot rendering.
6. Add 5-10 new templates from the most obvious missing categories.
7. Define the Shadertoy/external-reference license and ingestion policy.
8. Add template metadata/schema sidecars.
9. Port the old Cauldron expression grammar into a constrained Python DSL.
10. Add perceptual/image-embedding scoring after the deterministic baseline is
   producing useful queues.

## Current Honest Assessment

The workflow is now a real batch-and-review system, not just a research note.
It can generate, score, evolve, and promote Godot shader candidates.

It is not yet an AAA shader factory. The limiting factors are:

- Too few high-quality template families.
- No verified Godot-render acceptance run yet.
- Reference scoring is still simple.
- No true code-generating DSL beyond fixed templates.
- No polished human review UI.

The right next move is not to chase a hosted AI shader generator. The right next
move is to expand the first-party template/DSL vocabulary and make the render
and review loop stricter.
