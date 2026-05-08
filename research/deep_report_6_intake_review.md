# Intake Review - deep-research-report (6)

Date: 2026-05-06  
Source: `D:\assets\deep-research-report (6).md`  
Topic: image -> hand-written fragment shader generation

## Short Answer

Yes, there is useful new material, but it is mostly **long-term shader R&D architecture**, not an immediate replacement for the current Godot shader-template workflow.

The report agrees with our core conclusion:

- There is no mature public end-to-end model that reliably does single-image -> production-quality arbitrary handwritten GLSL/HLSL/Slang.
- The practical route is retrieval + constrained synthesis + compiler/render/profiling feedback.
- One image is underconstrained; exact source recovery is not identifiable.

The new value is sharper detail on:

1. license-clean shader corpus construction;
2. normalized raw-source plus compiler-derived AST/IR as dual representation;
3. Slang as a future canonical export surface for cross-backend work;
4. benchmark/CI design for shader generation;
5. legal/security controls for shader crawlers and generated GPU code.

## What Is Actually New Or Stronger

### 1. Slang-Centered Export Is More Strongly Argued

Earlier docs mentioned Slang/Slang.D as a watch item. This report argues more strongly that, for a future cross-engine shader system, Slang should be the canonical editable/export surface:

```text
internal truth: normalized AST/IR + raw source + runtime manifest
canonical editable source: Slang or restricted HLSL-like superset
target backends: HLSL via DXC, GLSL/SPIR-V via Slang/glslang validation, engine wrappers
```

Immediate impact:

- Do not change the current Godot-first shader lab yet.
- Add Slang to the **future cross-backend compiler track**, not the first-week implementation path.
- If we build a serious external-shader corpus/retrieval system, normalize toward an AST/IR and consider Slang output early.

### 2. Corpus Licensing Guidance Is Much More Concrete

The report gives a practical source policy:

- Explicitly licensed GitHub repos: usable if MIT/Apache/BSD/CC0 and provenance is preserved.
- No-license GitHub repos: exclude from training/redistribution.
- Shadertoy: restricted by default; use official API only and treat as noncommercial/share-alike unless individual shaders declare otherwise.
- GLSL Sandbox: user-code licensing unresolved; avoid bulk training.
- Unity built-in shader archives: favorable where MIT.
- Epic official content: avoid for broad ML training unless legal approves.
- The Stack v2 / BigCode: discovery/governance source, not a reason to skip upstream license filtering.

This should become the policy for any future reference importer or RAG corpus. The current `shader_batch_review.py` path uses first-party templates, so it is unaffected.

### 3. Shader Dataset Schema Is Worth Adopting Later

The report recommends storing:

- `source_id`;
- `license_declared`;
- `license_policy`;
- `provenance`;
- normalized source;
- AST/IR;
- pass topology;
- uniforms/resources;
- render packs;
- metrics;
- performance data.

This is more detailed than the current candidate manifests. It matters if we add a shader reference/corpus crawler.

Near-term useful subset:

- Add `license_policy`, `source_id`, and `provenance` fields to any future imported external shader reference.
- Keep first-party generated shaders separate from external references.

### 4. Retrieval Baseline Before Fine-Tuning

The report explicitly says: build a retrieval baseline before training anything.

This matches our practical workflow, but makes the future route clearer:

```text
render packs -> visual embedding index
normalized source/AST -> code embedding index
input image/reference -> retrieve exemplars
LLM edits retrieved exemplars
compile/render/repair loop
```

This is a better near-term research target than fine-tuning Qwen/DeepSeek immediately.

### 5. Benchmark/CI Subsets Are Useful

The report proposes benchmark subsets:

- image-only single-pass procedural shaders;
- texture-dependent filters/post effects;
- animated shaders;
- multi-pass/feedback shaders;
- material-like shaders.

Metrics:

- compile/link success;
- uniform/texture binding correctness;
- deterministic rendering;
- MSE/RMSE plus perceptual metrics such as LPIPS;
- CLIP-space semantic similarity;
- temporal consistency;
- performance/runtime profiling.

Immediate impact:

- Our current shader scorer already has deterministic image/motion metrics.
- Add optional benchmark labels to batches later: `single_pass`, `animated`, `material_like`, `post_effect`, `multipass`.
- Add security/runtime caps before accepting arbitrary external shader code.

### 6. Security Controls Are More Explicit

The report treats generated shaders as untrusted GPU programs. It recommends:

- isolated workers;
- strict timeouts;
- memory limits;
- resolution caps;
- resource-binding quotas;
- pass-count budgets;
- reject before human review if policy is exceeded.

Current status:

- `shader_godot_render.py` has a timeout.
- The shader lab does not yet have a full sandbox/resource policy.

Near-term addition:

- Add a `shader_policy.json` with max frames, max resolution, max render time, allowed template ids, and external-code disabled by default.

## What Is Not New

Already covered in our docs:

- Single-image -> arbitrary source is underconstrained.
- Template/DSL generation is more practical than freeform raw GLSL.
- MaterialX/OpenPBR belong mostly to the surface-material lane, not spell/VFX shaders.
- LPIPS/CLIP/DINO-style scoring is useful but optional.
- Shadertoy scraping is risky without license controls.
- Qwen2.5-VL / Qwen2.5-Coder / DeepSeek-style models are plausible for a future branch, not needed for the immediate Godot template loop.
- Human review should see shortlists, not raw large batches.

## Recommended Updates To Our Plan

### Add A Future Shader Corpus Track

Do not build this before improving the live shader workflow, but add it to the roadmap:

```text
art_lab/shaders/corpus/
  sources/
  normalized/
  render_packs/
  indices/
  policies/
```

Core first tool:

```text
shader_source_catalog.py
```

It should ingest only first-party or explicitly permissive source references and write license/provenance metadata. No Shadertoy bulk import without per-shader license review.

### Add A Shader Policy File

Near-term, cheap:

```text
art_lab/shaders/policies/shader_policy.json
```

Fields:

```json
{
  "allow_external_source": false,
  "max_preview_size": 512,
  "max_frames": 32,
  "max_render_seconds": 90,
  "allowed_templates": ["ring_field_2d", "beam_lightning_2d", "dissolve_fire_2d", "shield_ripple_2d", "portal_swirl_2d"],
  "external_license_allowlist": ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "CC0-1.0"]
}
```

### Track Slang As A Future Export Experiment

Not for the current Godot-first loop. Later test:

```text
template/DSL -> restricted HLSL-like block -> Slang compile -> GLSL/SPIR-V validation -> Godot wrapper
```

This becomes relevant if we target Unity/Unreal/WebGPU/Vulkan too, or if we attempt differentiable shader fitting.

## Recommendation

Do not pivot the current implementation. The current template/evolve/promote workflow is still the right practical spine.

Fold in three things:

1. stricter license/provenance policy for future external shader references;
2. shader policy/sandbox limits;
3. a future Slang/corpus/RAG track after Godot preview/render quality is better.

## Sources

- Local source report: `D:\assets\deep-research-report (6).md`
- Existing shader handoff: `D:\assets\art_lab\SHADER_WORKFLOW_STATUS.md`
- Existing shader integration plan: `D:\assets\art_lab\SHADER_RESEARCH_INTEGRATION_PLAN.md`
- Existing overall handoff: `D:\assets\ART_LAB_HANDOFF_2026_05_06.md`

