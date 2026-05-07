# Shader Research Integration Plan

Date: 2026-05-06  
Scope: Godot 4.5 / C# asset factory, shader/effect/material generation workflow  
Inputs reviewed:

- `D:\assets\research\shades.md`
- `D:\assets\research\shades_intake_review.md`
- `D:\assets\research\deep_research_report_5_image_to_shader.md`
- `D:\assets\research\deep_report_5_intake_review.md`
- `D:\assets\art_lab\SHADER_WORKFLOW_STATUS.md`

## Executive Recommendation

Add the useful research in layers. Do not pivot to a new "AI shader generator."
The current architecture is still the correct backbone:

```text
Godot templates -> batch render -> metric review -> reference/evolution -> promotion queue -> human review
```

The research adds five practical upgrades:

1. Formal template metadata and schemas.
2. LLM-guided mutation/crossover on top of existing parameter evolution.
3. A license-safe ShaderToy/RAG reference lane.
4. Better optional critics for reference/style scoring.
5. A separate PBR/material generator bench for StableMaterials, Chord,
   MaterialPicker, and later MaterialX/OpenPBR.

The immediate implementation should focus on **making the existing Godot shader
lab more controllable and auditable**, not adding heavyweight research stacks.

## Non-Negotiable Constraints

- Godot `.gdshader` remains the live effect target.
- LLMs operate through structured JSON, schemas, metrics, and commands.
- No final ranking by OCR or free-form screenshot descriptions.
- Every candidate must produce inspectable outputs: PNG previews, flipbooks,
  galleries, and eventually Godot-rendered frames.
- Community shader code is inspiration/reference only until license provenance is
  explicit.
- Texture/PBR tools belong in the texture pipeline unless they directly support
  live effect shaders.

## Representation Ladder

Use this ladder to keep future research from mixing incompatible tasks:

| Lane | Purpose | Current status | Near-term action |
|---|---|---|---|
| Effect parameter lane | Existing Godot templates plus `request.json` params | Implemented | Add metadata/schema sidecars |
| Effect DSL lane | Cauldron-style expression grammar compiled to Godot | Not built | Design after metadata |
| External GLSL lane | Shadertoy/RAG/import with license tracking | Not built | Prototype read-only reference index |
| PBR material lane | PBR maps for StandardMaterial3D / terrain/world materials | Existing texture pipeline | Test StableMaterials/Chord/etc. separately |
| Material graph lane | MaterialX / Material Maker / Blender nodes | Research/backlog | Watch and test for surface materials |
| Neural material lane | Learned runtime material representations | Research only | Watch, do not build around |

## Phase 0 - Audit And Baseline Lock

Goal: make sure the existing workflow is stable before expanding it.

### Tasks

1. Verify the current shader tools still compile:

```powershell
python -m py_compile `
  art_lab\tools\shader_batch_review.py `
  art_lab\tools\shader_evolve.py `
  art_lab\tools\shader_promote.py `
  art_lab\tools\shader_reference_score.py `
  art_lab\tools\shader_godot_render.py `
  art_lab\tools\shader_lab_index.py
```

2. Run one small batch, one evolution batch, and one promotion queue.
3. Locate Godot 4.5 executable or set `GODOT_EXE`.
4. Run `shader_godot_render.py` on at least one promoted queue.
5. Store the baseline outputs as reference examples.

### Acceptance

- Existing smoke tests pass.
- At least one candidate has both CPU proxy and Godot-rendered preview.
- Dashboard regenerates.
- Any Godot render issue is documented as a blocker, not hidden.

### Files touched

- No feature code unless a bug is found.
- Update `SHADER_WORKFLOW_STATUS.md` with Godot render result.

## Phase 1 - Template Metadata And Schemas

Goal: give LLMs and tools a strict control surface for every shader template.

### Why

Both research reports point to constrained representations. The current templates
already expose uniforms, but the surrounding meaning is implicit. We need sidecar
metadata so tools can know what each knob means, how to mutate it, what output
shape is expected, and what failures look like.

### Add

Create:

```text
art_lab/shaders/templates/schema/
  template_schema.schema.json
  ring_field_2d.meta.json
  beam_lightning_2d.meta.json
  dissolve_fire_2d.meta.json
  shield_ripple_2d.meta.json
  portal_swirl_2d.meta.json
  macro_detail_v1.meta.json
```

Each `.meta.json` should include:

```json
{
  "id": "portal_swirl_2d",
  "version": 1,
  "target": "canvas_item",
  "role": "portal",
  "summary": "Spiraling portal/vortex mask with radial motion.",
  "intended_uses": ["portal", "summon circle", "world-map magical gate"],
  "avoid_uses": ["thin beam", "realistic smoke"],
  "runtime_tier": "cheap|medium|expensive",
  "preview_defaults": {
    "size": [256, 256],
    "frames": 8,
    "duration_s": 2.0,
    "background": [0.02, 0.02, 0.06, 1.0]
  },
  "expected_metrics": {
    "coverage": [0.10, 0.62],
    "motion": [0.010, 0.28],
    "center_max": 0.20
  },
  "parameters": {
    "radius": {
      "type": "float",
      "range": [0.1, 0.8],
      "default": 0.42,
      "mutation_group": "silhouette",
      "description": "Main portal radius."
    }
  },
  "failure_modes": [
    "full-screen wash",
    "static low-motion ring",
    "center overfilled"
  ],
  "tags": ["radial", "looping", "transparent", "magic", "vortex"]
}
```

### Tool changes

Update:

- `shader_batch_review.py`
- `shader_evolve.py`
- `shader_promote.py`
- `shader_lab_index.py`

Behavior changes:

- Load metadata when available.
- Use metadata preview defaults instead of hardcoded defaults.
- Use metadata expected metrics instead of duplicating role rubrics where possible.
- Include metadata tags in `batch_summary.json` and `llm_review_packet.json`.
- Add metadata validation command:

```powershell
python art_lab\tools\shader_template_validate.py
```

### Acceptance

- All current templates have valid `.meta.json` files.
- Running the old batch command still works.
- `llm_review_packet.json` includes tags, role, intended uses, and failure modes.
- No change reduces existing smoke output quality.

## Phase 2 - Godot Render Acceptance Gate

Goal: make Godot-rendered frames the acceptance artifact for promoted candidates.

### Why

CPU proxy previews are useful for broad search, but they are not proof that the
shader works in Godot. The final queue should show engine frames.

### Tool changes

Update `shader_godot_render.py`:

- Better Godot executable discovery.
- Clear diagnostics for headless vs non-headless failures.
- Optional `--queue-dir` input in addition to `--batch-dir` and `--candidate-dir`.
- Write a compact `godot_render_summary.json`.
- Add failure reason to each candidate `request.json`.

Update `shader_promote.py`:

- Optional `--require-godot-render`.
- Optional `--prefer-godot-preview` so galleries use `preview_godot.png` when
  available.

### Acceptance

- A promoted queue can be rendered through Godot with one command.
- Queue HTML prefers Godot previews when present.
- Failed candidates are not silently promoted as accepted.

## Phase 3 - LLM-Guided Mutation And Crossover

Goal: add the useful AI Co-Artist idea without opening the door to arbitrary GLSL
chaos.

### Why

`shader_evolve.py` currently mutates numeric parameters. AI Co-Artist suggests a
more creative loop: mutation/crossover descriptions such as "more chaotic",
"faster inner pulse", "ice palette", "sharper branches." We should support that
through structured operations.

### Add

Create:

```text
art_lab/shaders/mutations/
  mutation_ops.schema.json
  default_mutation_policy.json
art_lab/tools/shader_llm_mutation_plan.py
```

`shader_llm_mutation_plan.py` should read:

- Parent `request.json`
- Template metadata
- Candidate review metrics
- Optional human/LLM intent

It should output a mutation plan:

```json
{
  "parent": "...request.json",
  "intent": "make the portal more violent but keep readable silhouette",
  "ops": [
    {"op": "scale_param", "param": "swirl_strength", "factor": 1.18},
    {"op": "shift_palette", "target": "storm"},
    {"op": "narrow_range", "param": "radius", "range": [0.34, 0.48]}
  ],
  "guardrails": {
    "preserve_role": true,
    "max_mutation_strength": 0.16,
    "reject_if_gate_issues": true
  }
}
```

Update `shader_evolve.py`:

- Optional `--mutation-plan <json>`.
- Optional crossover between two parent requests, limited to compatible template
  and metadata groups.

### Allowed operations first

- Scale numeric param.
- Shift numeric param.
- Clamp/narrow param range.
- Swap palette.
- Lock param.
- Prefer motion group.
- Prefer silhouette group.
- Crossover parameter groups between same-template parents.

### Not allowed yet

- Arbitrary shader source edits.
- New functions/includes.
- Cross-template code mixing.

### Acceptance

- A mutation plan can produce a batch.
- Mutation operations are recorded in candidate provenance.
- Bad mutation plans fail validation before rendering.
- Crossover only runs when templates and metadata groups are compatible.

## Phase 4 - External Shader Reference Lane

Goal: use ShaderToy/Shadertoy-like corpora as inspiration and retrieval without
polluting production assets or licensing.

### Why

The research identifies ShaderToy-MCP, `shaders21k`, and `shadermatch` as useful.
They are useful, but only behind provenance and license controls.

### Add

Create:

```text
art_lab/shaders/external_refs/
  sources/
  rendered/
  index.jsonl
  LICENSE_POLICY.md
art_lab/tools/shader_external_index.py
art_lab/tools/shader_shadertoy_render.py
art_lab/tools/shader_shadertoy_to_godot_notes.py
```

### License policy

Each external record must include:

```json
{
  "source": "shadertoy",
  "url": "https://www.shadertoy.com/view/...",
  "author": "...",
  "license": "CC0|MIT|CC-BY-NC|unknown|...",
  "commercial_use": true,
  "direct_code_use": false,
  "allowed_use": ["reference", "rag", "visual inspiration"],
  "notes": "Do not copy code; use as idiom reference."
}
```

Default policy:

- Unknown license: reference only.
- Noncommercial license: reference only, no training for commercial output.
- GPL/copyleft: do not ingest into production code; reference only.
- Permissive/CC0: may be converted only with provenance and review.

### Rendering

Start with one of:

- `pygfx/shadertoy`
- browser WebGL harness
- WGPU/Shadertoy runner if already easy to install

Do not block on `shadermatch`. First goal is a reference gallery.

### Outputs

For each external ref:

```text
external_refs/rendered/<id>/
  source.json
  preview.png
  flipbook.png
  frames/
  tags.json
```

### Integration with local lab

- Add external references as searchable inspiration.
- Add optional "similar external refs" section to `llm_review_packet.json`.
- Let LLMs propose new first-party template ideas from external references.
- Do not automatically convert external code into production templates.

### Acceptance

- 10 external references indexed with license/provenance.
- 10 previews rendered into a gallery.
- No direct code copied into `templates/`.
- One hand-authored Godot template idea is derived from references and documented
  as original work.

## Phase 5 - Better Critics And Reference Scoring

Goal: improve "looks like this target" scoring without replacing deterministic
role gates.

### Why

Current reference scoring is cheap and deterministic. It is a good baseline but
not enough for subtle style matching.

### Add optional scoring backends

Create:

```text
art_lab/tools/shader_reference_embed.py
art_lab/tools/shader_temporal_score.py
```

Backends in priority order:

1. Deterministic features: current baseline, always available.
2. Temporal features: motion curve, flicker frequency, expanding/contracting
   radial change, loop continuity.
3. LPIPS for material/texture-like references if dependencies are manageable.
4. CLIP/SigLIP/DINO embeddings for broad style retrieval and clustering.
5. `shadermatch` only for Shadertoy-format candidates.

### Data contract

Add to `request.json`:

```json
{
  "review": {
    "score": 82.1,
    "grade": "review"
  },
  "reference_review": {
    "deterministic_score": 73.2,
    "embedding_score": null,
    "temporal_score": 61.0,
    "nearest_reference": "..."
  }
}
```

### Acceptance

- Deterministic scoring remains default and dependency-free.
- Optional model scoring can be skipped cleanly when dependencies are missing.
- Temporal score is computed from existing frames.
- Scores are displayed separately, not collapsed into one unexplained number.

## Phase 6 - Template Library Expansion

Goal: improve actual output quality. This is the main creative bottleneck.

### Add template families

First wave:

- `projectile_core_2d`: orb/comet/missile cores and tails.
- `impact_shockwave_2d`: expanding rings, cracks, bursts.
- `ground_aoe_2d`: rune circles, danger telegraphs, poison pools.
- `ui_glow_frame_2d`: HUD frames, rarity borders, cooldown glows.
- `heat_haze_2d`: distortion field for fire/lava/air shimmer.
- `water_ripple_2d`: ripples, pools, world-map water overlay.
- `forcefield_spatial`: spatial shield/force field material.
- `terrain_overlay_spatial`: moss/snow/wetness/magic overlay.

Second wave:

- Particle process shaders for sparks, embers, orbitals, swarms.
- Flipbook bake templates for expensive smoke/fire/portal raymarch effects.
- Map shaders for fog-of-war, contours, political hover, parchment treatment.

### For each template

Required:

- `.gdshader`
- `.meta.json`
- CPU proxy renderer support or explicit "Godot render only"
- smoke request JSON
- preview in dashboard
- role rubric or metadata metric expectations

### Acceptance

- At least 5 new templates produce valid batch outputs.
- At least 3 promote candidates above threshold.
- New templates cover different roles; not only palette variants.

## Phase 7 - Cauldron-Derived DSL

Goal: recover the useful old Cauldron procedural expression grammar in a safer
Python/Godot pipeline.

### Why

Templates alone limit novelty. Arbitrary GLSL is too risky. A bounded DSL is the
middle ground.

### Add

Create:

```text
art_lab/shaders/dsl/
  shader_dsl.schema.json
  primitives.json
  palettes.json
art_lab/tools/shader_dsl_compile.py
art_lab/tools/shader_dsl_mutate.py
```

Initial primitive groups:

- Noise: value, fbm, domain warp, voronoi.
- SDF: circle, ring, box, capsule, segment, arc.
- Polar: angle, radius, spiral, radial repeat.
- Masks: threshold, smoothstep, dissolve, edge glow.
- Color: ramp, palette blend, hue shift, emissive boost.
- Motion: scroll, pulse, rotate, expand, flicker.

DSL output target:

- First: insert generated expression blocks into known templates.
- Later: generate whole small `canvas_item` effects.

### Guardrails

- No loops in generated DSL v1.
- No texture sampling except declared inputs.
- No dynamic arrays.
- Instruction-budget estimate if practical.
- Always compile and render after generation.

### Acceptance

- DSL can generate at least 20 variations inside one template.
- Compile/render pass rate above 90%.
- DSL candidates preserve provenance and can be promoted like normal candidates.

## Phase 8 - PBR / Material Generator Bench

Goal: evaluate material tools from the research without disrupting shader VFX.

### Candidate tools

Test:

- StableMaterials.
- Chord / Generative Base Material.
- MaterialPalette if photo-to-PBR becomes important.

Watch:

- MaterialPicker.
- ControlMat.
- Generative Neural Materials.
- MaterialX/OpenPBR export.

### Test prompts/materials

Use hard, game-relevant cases:

- magical oxidized bronze with glowing rune inlay,
- wet black basalt with moss in cracks,
- cursed organic ground with subtle veins,
- frosted blue crystal wall,
- parchment map material with ink bleed,
- charred battlefield dirt with ash and embers.

### Compare against

Existing:

- `pipelines/textures/aaa_texture.py`
- Material Anything path if available.
- Blender preview and seam QA.

### Acceptance

- Each tested tool outputs maps that fit the existing material contract.
- Existing QA can score seam/tile/preview quality.
- Results are logged in a small comparison report.
- No PBR tool is allowed to become a dependency until it beats or complements the
  current pipeline on at least two material classes.

## Phase 9 - Local Paired Corpus

Goal: create clean project-owned data for retrieval, ranking, and possible
fine-tuning.

### Why

Both research intakes point to data scarcity. The safest corpus is one generated
from our own accepted templates and outputs.

### Add

Create:

```text
art_lab/shaders/corpus/
  corpus.jsonl
  renders/
  manifests/
art_lab/tools/shader_corpus_export.py
```

Each corpus row:

```json
{
  "id": "...",
  "source": "first_party",
  "template": "portal_swirl_2d",
  "template_version": 1,
  "params": {},
  "shader_path": "...",
  "preview": "...",
  "flipbook": "...",
  "metrics": {},
  "tags": ["portal", "radial", "storm"],
  "license": "project-owned",
  "approved": true
}
```

### Use cases

- Similarity retrieval for LLM context.
- Reference-set creation.
- Regression tests.
- Future fine-tuning if ever justified.

### Acceptance

- Export promoted queues into corpus.
- Corpus contains only first-party or explicitly approved assets.
- Every row has provenance, template version, and rendered preview.

## Phase 10 - Review UI And Promotion-To-Library

Goal: make human review faster and turn winners into reusable assets.

### Add

Improve review queue `index.html`:

- Side-by-side reference and candidate.
- Animated flipbook playback controls.
- Show score breakdown and gate issues.
- Show template metadata.
- Show mutation/evolution lineage.
- Copy command buttons.
- Human notes stored in `review_notes.json`.

Add:

```text
art_lab/tools/shader_library_promote.py
art_lab/shaders/library/
```

Library promotion should copy:

- `.gdshader`
- `.tscn`
- request/params
- preview/flipbook
- metadata
- notes
- tags
- provenance

### Acceptance

- A human can mark keep/reject/rework.
- Approved candidates can be promoted to `shaders/library/`.
- Promoted library entries can be used as parents for mutation/evolution.

## Phase 11 - Optional Godot AI MCP Test

Goal: decide whether editor automation adds value after CLI rendering works.

### Test only after

- Godot CLI render acceptance works.
- Template metadata exists.
- At least one review queue is promoted.

### Test scenario

- Create a Godot scene using one generated `ShaderMaterial`.
- Add a simple `GPUParticles` preset around it.
- Render or inspect scene.
- Record what MCP does better/worse than direct CLI scripts.

### Acceptance

- Clear decision: adopt, watch, or ignore.
- No dependency introduced unless it improves a real workflow.

## Suggested Implementation Order

### Week 1

1. Phase 0: validate Godot render path.
2. Phase 1: add template metadata/schema sidecars.
3. Update existing tools to read metadata.
4. Add 2-3 curated reference sets.
5. Run broad/evolve/promote with metadata included.

### Week 2

1. Phase 3: implement mutation-plan JSON.
2. Add LLM-guided parameter mutation commands.
3. Phase 6: add first 3 new templates.
4. Improve queue gallery with metadata and gate details.

### Week 3

1. Phase 4: implement license-safe external reference lane.
2. Render 10 external references.
3. Derive one original Godot template from reference idioms.
4. Start corpus export from accepted first-party candidates.

### Week 4

1. Phase 5: add temporal scoring.
2. Optional CLIP/DINO/LPIPS experiment if dependencies are manageable.
3. Phase 8: run StableMaterials or Chord comparison through texture QA.
4. Promote first accepted shader library entries.

### Later

- Cauldron DSL.
- MaterialX/OpenPBR material export experiments.
- Godot AI MCP.
- Slang/Slang.D.
- Neural material tracking.

## Audit Checklist

An auditing chat should answer:

- Is Godot render validation correctly first?
- Is the template metadata schema too broad or missing fields?
- Are external shader license rules strict enough?
- Should ShaderToy/RAG happen before or after DSL?
- Which optional critic should be tested first: temporal, LPIPS, CLIP/DINO, or
  `shadermatch`?
- Are StableMaterials/Chord/MaterialPicker correctly separated from live VFX?
- Is any plan item overbuilt for the immediate goal?
- Are there missing file contracts for Godot pack/export?
- Are there security risks in LLM mutation plans or future DSL blocks?
- What is the smallest reviewable implementation slice?

## Drop / Avoid List

Do not implement these until the core loop is stronger:

- Arbitrary image-to-GLSL generation as a production path.
- Direct shipping code from Shadertoy without license clearance.
- MaterialX/OpenPBR as the spell/VFX canonical IR.
- Neural materials in Godot runtime.
- Full Slang cross-backend compiler work.
- Unity/Unreal Shader Graph conversion.
- Training/fine-tuning on community shader data.
- Godot AI MCP as a required dependency.

## Smallest Useful Implementation Slice

If the audit wants a minimal first merge, do this:

1. Add template metadata sidecars for existing templates.
2. Add `shader_template_validate.py`.
3. Update `shader_batch_review.py` and `shader_evolve.py` to include metadata in
   outputs.
4. Add `--queue-dir` support to `shader_godot_render.py`.
5. Run one Godot-rendered promoted queue.

That slice improves the current system immediately and prepares the later LLM,
DSL, RAG, and corpus work without adding risky dependencies.
