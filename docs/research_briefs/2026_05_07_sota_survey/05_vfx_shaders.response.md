# Research Response — VFX Shaders Pipeline 2026 SOTA

Date: 2026-05-07
Brief: [05_vfx_shaders.md](05_vfx_shaders.md)
Hardware target: RTX 5090 Laptop, 24 GB VRAM, Blackwell sm_120, CUDA 12.8+, torch 2.7+, Windows 11; Godot 4.5 runtime, `.gdshader` output.

## Executive summary

The current LLM-mutation framework in [art_lab/](../../../art_lab/) is **architecturally correct for 2026** and the published research validates the design rather than dethroning it. The two SIGGRAPH/AR papers that touched this exact problem in late 2025 / early 2026 — **AI Co-Artist (arXiv 2512.08951, Nov 2025)** and **ShadAR (arXiv 2602.17481, Feb 2026 ISMAR)** — implement **the same loop you already built**: LLM proposes / mutates GLSL, render, judge, evolve. Your framework's only structural difference is that it (correctly) constrains generation to validated `.gdshader` templates with a numeric gate, which avoids the compile-failure noise both papers explicitly call out as a limitation. **Do not replace the framework.**

The real gaps versus 2026 SOTA are not architectural; they are operational and three are concrete:

1. **Reference scoring is too primitive.** CV metrics (alpha/contrast/edge/colorfulness) are still useful as a fast pre-filter but the 2025 frontier for "is candidate X close to reference Y" is **DreamSim** (concatenated CLIP+OpenCLIP+DINO embeddings fine-tuned on human judgments, ICASSP 2025 family) plus **LPIPS** as a low-level companion. Single-pip install, runs on RTX 5090 in <50 ms per pair. This is the cheapest, highest-impact upgrade in the whole brief.
2. **Template vocabulary is the actual bottleneck.** Your own status doc says it; nothing in 2026 changes that. Three template families (`ground_glow_2d`, `projectile_trail_2d`, `hit_flash_2d`) cover ~70% of the missing categories the brief lists. Bulk-import GDQuest + Hollow Pixel as licensed seed material; do not write them from scratch.
3. **The framework has never been aimed at a real production target.** Five batches, all `*_smoke_*` or `*_mutate_*`, one reference image. Pick a real game-design target (the brief's own status doc proposes `storm_projectile`, `occult_portal`, `holy_shield`) and run one full evolution loop end-to-end. This is far more valuable than any tool swap.

What does **not** exist as a usable open release in 2026:

- A reliable "reference image + natural language → working `.gdshader`" tool. AIShader (Keijiro, Unity-only) and ShaderToy-MCP get close to ideation, neither produces production assets.
- Video-to-shader synthesis. NeRF-style differentiable methods are research-only, not Godot-targeted.
- A genetic shader optimizer with crossover + ML fitness specifically for game shaders. CodeEvolve / AlphaEvolve are general LLM-driven evolutionary frameworks (not shader-specific) and their cost profile is wrong for this lane.
- A "production shader package" convention beyond Godot's existing addon + Asset Library. Roll your own simple manifest.

The rest of this document treats each question, then ends with the three concrete decisions the brief asked for.

---

## Q1. 2026 SOTA for AI shader generation (reference image + NL → working shader)

### Top recommendations

1. **AI Co-Artist (Yuksel & Sawaf, arXiv 2512.08951, Nov 2025).** LLM-powered framework for interactive **GLSL** shader animation evolution; uses GPT-4 to perform crossover and mutation on shader source under user-guided aesthetic selection (Picbreeder lineage). Outputs are GLSL fragments — not `.gdshader`, but the porting friction is small (Godot's shading language is GLSL ES 3.0-derived). https://arxiv.org/abs/2512.08951
2. **ShadAR (Yang et al., ISMAR 2025, arXiv 2602.17481, Feb 2026).** Real-time HLSL shader generation from voice/NL by an LLM agent for AR passthrough. Demonstrates that the "NL → shader code → compile → apply" loop works in production-quality real-time, but is HLSL/Unity-MR oriented and not a portable open tool. https://arxiv.org/abs/2602.17481
3. **ShaderToy-MCP (wilsonchenghy, MCP server, active Dec 2025–Jan 2026).** RAG-style bridge that lets Claude/Cursor query Shadertoy and use community shaders as inspiration/idiom source. Best treated as a *retrieval* lane, not a generator. https://github.com/wilsonchenghy/ShaderToy-MCP
4. **AIShader (Keijiro, Unity).** ChatGPT-powered Unity shader generator. Mature but Unity-only, not relevant to Godot output. https://github.com/keijiro/AIShader

### Hardware/install fit
All four are external services or thin wrappers (no local inference required); the LLM call is what matters. RTX 5090 + Blackwell is irrelevant to these — they run wherever the LLM API runs.

### License + cost notes
- AI Co-Artist: paper + framework description, no public weights/code release as of 2026-05-07. License unstated. Reproducible from paper.
- ShadAR: IEEE conference paper, no public reference implementation.
- ShaderToy-MCP: MIT-style, free; **shaders queried from Shadertoy retain their authors' licenses** — critical license-tracking burden.
- AIShader: MIT (Keijiro's standard), Unity-locked.

### Maturity
None of the four is "drop in and produce a Godot-ready production shader from a reference image" in 2026. AI Co-Artist and ShadAR are the academic state of the art and **both implement what you've already implemented locally**, with AI Co-Artist explicitly citing "compile-failure noise" as a problem they did not fully solve. Your template-bounded mutation deliberately avoids that.

### Honest comparison vs current LLM-mutation framework
**Lateral, slightly behind on freedom, ahead on reliability.** Your framework cannot generate a never-seen-before shader topology; AI Co-Artist can, sometimes, at the cost of frequent compile failures. For the user's stated goal (Godot asset factory, not creative coding playground) the trade favors the current design. The right adaptation is to add an *optional* "AI Co-Artist mode" lane: a separate experimental subprocess where an LLM proposes free-form GLSL fragments, those are wrapped into a `.gdshader` skeleton, compiled via Godot CLI, and only validated outputs enter the regular review queue. Keep this lane gated; do not replace the bounded-template path.

---

## Q2. Reference-based shader iteration — CLIP-based scoring vs current CV metrics

### Top recommendations

1. **DreamSim (Sundaram et al., NeurIPS 2023; updated NeurIPS 2024).** Concatenates CLIP + OpenCLIP + DINO embeddings, fine-tuned on synthetic human-judgment data; achieves 96.16% agreement with human perceptual judgment. `pip install dreamsim`, runs in milliseconds per pair on RTX 5090. **This is the cleanest 2026 answer for "is candidate X close to reference Y in style/content."** https://github.com/ssundaram21/dreamsim
2. **LPIPS (richzhang/PerceptualSimilarity).** Still the standard low-level perceptual metric; complements DreamSim (DreamSim catches *conceptual* similarity, LPIPS catches *pixel-level* similarity). `pip install lpips`. https://github.com/richzhang/PerceptualSimilarity
3. **DINOv2 embedding cosine.** Cheaper than DreamSim (one model, one forward pass), excellent for clustering/diversity-filtering in promotion. Tested in 2025 to outperform LPIPS on object-similarity tasks but not on low-level fidelity. Pair with LPIPS for full coverage.
4. **Foundation Models Boost Low-Level Perceptual Similarity Metrics (ICASSP 2025, arXiv 2409.07650).** Survey-style paper documenting that DINO/CLIP backbones + LoRA tuning consistently outperform pure LPIPS on low-level perceptual tasks. Useful as the citation supporting the migration. https://arxiv.org/html/2409.07650

### Hardware/install fit
DreamSim, LPIPS, DINOv2 all install via pip and run comfortably on a 24 GB Blackwell card; latency per pair is dominated by image decode, not the model forward pass. No CUDA-version friction — all three support torch ≥2.0.

### License + cost notes
- DreamSim: MIT.
- LPIPS: BSD-2.
- DINOv2: Apache 2.0.

All three commercially safe.

### Maturity
DreamSim is the de-facto reference comparison metric for image generation eval in 2025–2026. LPIPS has been stable since 2018. Both are production-grade.

### Honest comparison vs current scoring
The current 12-metric CV stack (alpha/contrast/edge/colorfulness/motion/flicker/etc.) is **not redundant** — it captures shader-specific properties (motion, flicker, alpha coverage) that DreamSim cannot. The right design is **two-stage scoring**:

- **Stage A — current CV metrics + role gates**, used for cheap rejection (this is what `shader_batch_review.py` already does).
- **Stage B — DreamSim + LPIPS against reference set**, run only on candidates that passed Stage A, used for final ordering and diversity filter.

This costs ~20 ms per surviving candidate and replaces the current edge-MSE-only reference scoring in `shader_reference_score.py`. **Yes, this beats the current scoring** — the current approach was always documented as a placeholder.

---

## Q3. Shader template libraries (Godot 4.x compatible)

### Top recommendations

1. **godotshaders.com.** Community library of 2000+ Godot shaders, browseable and one-click installable from inside the editor. Coverage of every category the brief lists (ground_glow, weapon_trail, status_halo, water, etc.) is broad but uneven in quality. **Licenses vary per shader** — most are MIT or CC0 but must be tracked individually. https://godotshaders.com/
2. **gdquest-demos/godot-shaders.** Curated open-source collection with playable demos. Smaller and higher quality than godotshaders.com. License: MIT for code. https://github.com/gdquest-demos/godot-shaders
3. **Hollow Pixel — Godot 4 Essential 2D Effects (Free Pack).** Six curated `canvas_item` shaders: `outline_2d`, `dissolve_burn_2d`, `heat_distortion_2d`, `drop_shadow_2d`, `flash_tint_2d`, `radial_wipe_2d`. Free for personal + commercial use. Best fit for the missing-category list — `flash_tint_2d` ≈ `hit_flash`, `radial_wipe_2d` ≈ `AOE_indicator`, `heat_distortion_2d` ≈ adjacent to `dash_blur`. https://hollow-pixel.itch.io/godot-4-essential-2d-effects-free-shader-pack
4. **Godot Shader Library Addon (Asset Library asset 4890, April 2026).** Editor addon that filters Godot Asset Library shaders by type with one-click install — useful as a discovery surface, not a code source. https://godotengine.org/asset-library/asset/4890
5. **Material Maker 1.6 (April 2026).** Godot-based procedural texture/node-graph authoring with a CLI for batch export (reinstated in 1.5, 2026-01-26). Outputs PBR maps + Godot ShaderMaterial-ready resources. Useful for the **ground_glow / terrain overlay / water surface** category specifically — those are mostly material/texture problems, not animated-effect problems. https://github.com/RodZill4/material-maker

### Hardware/install fit
All four are CPU-trivial; Material Maker uses Godot's renderer (your existing GPU is overkill).

### License + cost notes
godotshaders.com licenses are per-shader; **do not bulk-import without a per-shader license-tracking sidecar.** Hollow Pixel pack is permissive. Material Maker is MIT.

### Maturity
godotshaders.com, gdquest-demos, and Material Maker are mature multi-year projects. Hollow Pixel pack is a curated 2025-era release; small but reliable.

### Honest comparison vs hand-writing more templates
Hand-writing one template takes ~half a day of careful authoring. Importing a vetted external one with a sidecar `template.json` (role, parameter ranges, license, source URL, attribution, intended use) takes ~15 min. **At 6 templates today and a target of 10+ new families, importing wins.** Recommended priority order based on the brief's missing-category list:

| Missing category | Source | Approach |
|---|---|---|
| `hit_flash` | Hollow Pixel `flash_tint_2d` | Wrap, tag, integrate |
| `AOE_indicator` | Hollow Pixel `radial_wipe_2d` + author tweaks | Wrap, mutate ring_field as fallback |
| `dash_blur` | Hollow Pixel `heat_distortion_2d` | Wrap |
| `ground_glow` | godotshaders.com (pick top-rated; ~5 candidates) | Curate 1, sidecar license |
| `projectile_trail` | gdquest-demos (trail demo) | Wrap |
| `weapon_trail` | godotshaders.com (multiple) | Curate 1 |
| `charge_pulse` | Author from scratch — variant of ring_field | Hand-write |
| `status_halo` | Mutate ring_field_2d with new parameter ranges | Parameter sidecar only |
| `water surface` | Material Maker procedural | Out-of-band, separate batch |
| `energy_weapon` | Mutate beam_lightning_2d | Parameter sidecar only |

This expands template coverage from 6 → ~14 in 2–3 days of integration work, ~1 day of which is license-sidecar plumbing.

---

## Q4. Genetic / evolutionary shader optimization (real GA with crossover + ML fitness)

### Top recommendations

1. **AI Co-Artist (same as Q1).** The 2025 paper that comes closest to "real" genetic shader optimization with LLM-driven crossover and mutation, ML fitness via user-guided aesthetic selection. **No public open-source release as of 2026-05-07** — must be reproduced from paper. https://arxiv.org/abs/2512.08951
2. **CodeEvolve (arXiv 2510.14150, Oct 2025).** Open evolutionary coding framework with island-based GA, weighted LLM ensemble, and three operators: inspiration crossover, meta-prompting, depth-targeted refinement. **Not shader-specific** but the cleanest open framework to wrap a shader fitness function around. https://arxiv.org/html/2510.14150v4
3. **AlphaEvolve (DeepMind, 2025).** Closed; relevant only as evidence that the LLM-driven evolutionary approach is the 2025 frontier. Don't try to use directly.
4. **Your existing `shader_evolve.py` + DreamSim fitness.** Adding DreamSim as the selection-pressure signal turns the current parameter-mutation script into a real ML-fitness genetic optimizer. This is the highest-leverage change in the whole brief.

### Hardware/install fit
CodeEvolve runs on whatever your LLM call runs on. DreamSim fits comfortably on the 5090.

### License + cost notes
CodeEvolve: open, Apache-style. AlphaEvolve: closed.

### Maturity
CodeEvolve is research-grade but actively developed. AI Co-Artist's framework is a paper-only target. Your `shader_evolve.py` is the only one in this list that *actually runs locally and produces Godot-ready outputs today.*

### Honest comparison vs current `shader_evolve.py`
**Your existing approach beats every public 2026 alternative for the specific goal of producing Godot-ready evolved shader candidates** — because none of them target Godot, none of them avoid compile failures, and none of them have ML-judged fitness against curated reference sets. The single missing piece is the fitness function. Today: edge-MSE against reference. After upgrade: DreamSim + LPIPS + your role-gates.

The crossover-vs-mutation gap is real (you only do mutation today, no crossover), but for *parameter* evolution against fixed templates, mutation alone is fine — crossover only matters if you also evolve template structure or shader source. That's a Phase 2 project.

---

## Q5. LLM-shader-loop workflows (agent that writes/iterates shader code with metric feedback)

### Top recommendations

1. **Your existing `llm_review_packet.json` + `shader_batch_review.py` loop.** This *is* a 2026-standard LLM-shader-loop workflow. The packet design (compact JSON, no screenshots, explicit metrics, role gates) anticipates what AI Co-Artist and ShadAR both do — but constrains the LLM to a manageable action space (parameters + template choice) instead of free GLSL.
2. **Godot MCP Pro (April 2026, Asset Library 4961).** 162 MCP tools for Godot 4 including shader operations, scene authoring, runtime analysis, particles, and testing. Connects Cursor/Claude/Windsurf/Cline directly to a Godot 4.5 editor. Cost: $15 one-time. https://godotengine.org/asset-library/asset/4961
3. **Godot AI (Asset Library 5050, 2026).** Multi-step task execution agent inside the Godot editor; supports Gemini, Ollama, OpenRouter as backends. Useful for editor-side iteration after a candidate is promoted, not for batch generation.
4. **ShaderToy-MCP (Q1).** Treat as a retrieval source for the LLM-shader loop, not as the generator.

### Hardware/install fit
All four work over the LLM API and a small editor footprint; nothing GPU-bound on your side.

### License + cost notes
Godot MCP Pro is paid ($15 one-time). Godot AI Suite is free addon. ShaderToy-MCP is MIT.

### Maturity
Godot MCP Pro is brand-new (April 2026); the surface area is large but quality of individual tools varies. Worth piloting on `shader_godot_render.py` first to confirm it can drive headless Godot rendering reliably before adopting deeper.

### Honest comparison vs current LLM workflow
**Your `llm_review_packet.json` is the right primitive.** The 2026 MCP-based agents (Godot MCP Pro, Godot AI) provide a *richer surface* — the LLM can directly drive the editor — but for **batch shader generation** you don't want the LLM driving the editor; you want batch artifacts. MCP fits a *manual review and refinement* loop after promotion, not the broad-batch loop.

**Recommendation:** Keep the packet-based loop as the backbone; pilot Godot MCP Pro for the **promotion → editor refinement → final QA** stage. This is genuinely lateral with the current design.

---

## Q6. Shader-from-video

### Honest answer
**No reliable open 2026 method exists for "reference video → working Godot shader."**

Closest 2025–2026 work:

1. **Multi-texture Neural Cellular Automata (Nature Sci. Reports 2025).** NCA + Local Pattern Producing Network can target a still image or texture and synthesize an evolving 2D pattern in real time. Works for *texture-class* targets (lava, sand, wood-grain), not for *effect-class* targets (a fireball, a dissolve). https://www.nature.com/articles/s41598-025-23997-7
2. **Diffusion Renderer (Liang et al., CVPR 2025).** Neural inverse and forward rendering via video diffusion; can decompose a video into geometry + shading. Heavy, NeRF-class hardware footprint, output is not a `.gdshader` — it's a neural network you'd have to bake into a shader. https://openaccess.thecvf.com/content/CVPR2025/papers/Liang_Diffusion_Renderer_Neural_Inverse_and_Forward_Rendering_with_Video_Diffusion_CVPR_2025_paper.pdf
3. **Mesh Neural Cellular Automata (TOG 2024).** Same lineage as #1, on meshes. Same scope limit.
4. **Manual reference-frame extraction → DreamSim-against-frames as evolution target.** You can mostly *simulate* video targeting today by frame-extracting a reference video and treating each frame as a reference image in a `reference_set/`. Score evolved candidates against multiple frames; pick winners that match the temporal envelope. **This is the practical 2026 answer.**

### Honest comparison
**There is no shortcut here in 2026.** Treating reference video as a multi-frame reference set in your existing pipeline is the realistic move; everything else is research-grade and doesn't output Godot.

---

## Q7. Production shader management

### Honest answer
**No 2026 industry convention exists for "game shader production package" beyond Godot's existing addon mechanism.** Roll a small custom convention.

### Recommendation

Add a fourth tier under [art_lab/shaders/](../../../art_lab/shaders/):

```
art_lab/shaders/
  templates/        # first-party authoring shaders (existing)
  batches/          # iterations (existing)
  review_queues/    # promoted shortlists (existing)
  library/          # NEW: production-graded promoted shaders
    <category>/<name>/
      <name>.gdshader
      <name>.tres                  # ShaderMaterial preset
      preview.png                  # 256x256 hero frame
      flipbook.png                 # animation strip
      manifest.json                # see below
      LICENSE.md                   # if external
```

`manifest.json` schema (the simplest thing that works):

```json
{
  "name": "ground_glow_v1",
  "version": "1.0.0",
  "category": "ground_glow",
  "shader_type": "canvas_item",
  "origin": "evolved",
  "source_batch": "ground_glow_storm_001",
  "source_candidate": "ground_glow_storm_001_ring_field_2d_017",
  "promoted_from_queue": "storm_projectile_review_002",
  "godot_version": "4.5",
  "parameters": { "...": "..." },
  "reference_set": "storm_projectile",
  "scores": { "dreamsim": 0.78, "lpips": 0.21, "edge_mse": 0.034 },
  "license": "MIT",
  "attribution": null,
  "performance_tier": "low",
  "created": "2026-05-09",
  "tags": ["spell", "storm", "ground", "AOE"]
}
```

This gives you:

- A clear winners list separated from in-flight iteration.
- Provenance (which batch, which candidate, which queue produced it).
- Reproducibility (parameters + template version → can re-render).
- License tracking (matters once you import from godotshaders.com / Hollow Pixel / ShaderToy-MCP).
- Searchability for the LLM operator (categories, tags).

**No external 2026 tool does this for you.** The Godot Asset Library is a distribution surface, not a project-internal catalog. Material Maker 1.6 has its own `.ptex` format which is irrelevant here. Shader-Slang's neural shading SIGGRAPH 2025 course has versioning conventions for neural appearance models, not for live VFX shaders.

This is two days of plumbing — `shader_promote.py` already writes a `manifest.json`; extend it to copy promoted candidates into `library/<category>/` with the schema above and update the dashboard.

---

## Synthesis — The three concrete decisions the brief asked for

### Decision 1: Is the LLM-mutation framework the right path or should it be replaced?

**Keep it. It is the right path.**

Both the academic SOTA papers (AI Co-Artist Nov 2025; ShadAR Feb 2026 ISMAR) implement the same loop you built, with weaker guardrails and worse compile reliability. None of the 2026 open releases produce production-ready Godot `.gdshader` output. The framework's real bottlenecks are:

- Reference scoring is too primitive (fix: DreamSim + LPIPS, see Q2).
- Template vocabulary is too narrow (fix: Hollow Pixel + gdquest + curated godotshaders.com imports, see Q3).
- Has never been aimed at a real production target (fix: pick one, see Decision 3).

Add an *optional* free-form LLM lane (AI Co-Artist style) gated behind a Godot CLI compile check, but do not let it replace the bounded path.

### Decision 2: Identify 2-3 missing template categories to add first

Pick by best ratio of "how often will spell/VFX content need this" × "low integration cost":

1. **`hit_flash_2d`** — universal for any combat impact. Source: Hollow Pixel `flash_tint_2d`. Wrap, sidecar `template.json`, parameter ranges. ~1 hour.
2. **`projectile_trail_2d`** — every projectile needs one; ring_field/beam don't substitute well. Source: gdquest-demos trail demo (or write from scratch — small shader). ~3 hours.
3. **`ground_glow_2d`** — AOE indicators, telegraphs, status circles all need this. Source: best-rated godotshaders.com result + sidecar license. ~2 hours.

If a fourth is added: **`charge_pulse_2d`** (parameter-evolved variant of `ring_field_2d` with different envelope; sidecar metadata only, no new shader). ~30 minutes.

### Decision 3: Pick the right reference-set + template combo for the first real (non-smoke) batch

The brief lists `storm_projectile`, `occult_portal`, `holy_shield` as candidate reference sets. Of those, **`occult_portal`** is the highest-confidence first real run because:

- The existing reference is a **portal** (`smoke_portal_ref/ref_001.png`) — it's the only set with even one curated reference image today.
- The existing `portal_swirl_2d` template is a tight match for the role.
- It is the only target where you can *immediately* run end-to-end without first curating ~5–10 reference images.

Recommended first real run:

```powershell
# 1. Curate 5-10 occult_portal reference images
#    (handpicked from existing screenshots + image search; track licenses)
mkdir art_lab\shaders\reference_sets\occult_portal
# ...add ref_001.png ... ref_010.png

# 2. Run evolution against the new reference set
python art_lab\tools\shader_evolve.py `
  --reference art_lab\shaders\reference_sets\occult_portal `
  --batch-id occult_portal_evolve_001 `
  --template portal_swirl_2d `
  --template ring_field_2d `
  --population 48 `
  --generations 6 `
  --elites 8 `
  --frames 16 `
  --size 256

# 3. Promote with diversity filter
python art_lab\tools\shader_promote.py `
  --batch occult_portal_evolve_001 `
  --queue occult_portal_review_001 `
  --top 12

# 4. Render through Godot (after Godot binary path is set up — currently blocking)
python art_lab\tools\shader_godot_render.py `
  --queue occult_portal_review_001
```

After that loop completes once **with real Godot rendering** (not just CPU proxy), you'll have validated the entire pipeline against an authentic target for the first time. Then aim a second batch at `storm_projectile` using the new `projectile_trail_2d` template (Decision 2) and `beam_lightning_2d`.

---

## Files to update

Per the brief's "After response returns" instructions:

- [docs/pipeline_reviews/07_vfx_shaders.md](../../../docs/pipeline_reviews/07_vfx_shaders.md) — record the keep-the-framework decision, link this response, list the three template imports as actionable items, list the DreamSim/LPIPS scoring upgrade as the highest-leverage operational change.
- [art_lab/SHADER_WORKFLOW_STATUS.md](../../../art_lab/SHADER_WORKFLOW_STATUS.md) — append a new section ("2026-05-07 Research Update") summarizing: (a) framework validated by AI Co-Artist + ShadAR, (b) DreamSim/LPIPS upgrade plan for `shader_reference_score.py`, (c) library/ tier added, (d) `occult_portal` chosen as first real production target, (e) Godot CLI render path is the remaining blocker for end-to-end validation.

---

## Sources

- [AI Co-Artist: A LLM-Powered Framework for Interactive GLSL Shader Animation Evolution (arXiv 2512.08951, Nov 2025)](https://arxiv.org/abs/2512.08951)
- [ShadAR: LLM-driven shader generation to transform visual perception in Augmented Reality (arXiv 2602.17481, Feb 2026 ISMAR)](https://arxiv.org/abs/2602.17481)
- [DreamSim (NeurIPS 2023; updated NeurIPS 2024)](https://github.com/ssundaram21/dreamsim)
- [LPIPS — richzhang/PerceptualSimilarity](https://github.com/richzhang/PerceptualSimilarity)
- [Foundation Models Boost Low-Level Perceptual Similarity Metrics (ICASSP 2025, arXiv 2409.07650)](https://arxiv.org/html/2409.07650)
- [godotshaders.com — community shader library](https://godotshaders.com/)
- [gdquest-demos/godot-shaders](https://github.com/gdquest-demos/godot-shaders)
- [Hollow Pixel — Godot 4 Essential 2D Effects (Free Pack)](https://hollow-pixel.itch.io/godot-4-essential-2d-effects-free-shader-pack)
- [Godot Shader Library Addon (Asset Library 4890)](https://godotengine.org/asset-library/asset/4890)
- [Material Maker 1.5 — CLI batch export reinstated (Jan 2026)](https://digitalproduction.com/2026/01/26/material-maker-1-5-adds-dds-fbx-cli-10-new-nodes/)
- [Material Maker 1.6 (Apr 2026)](https://digitalproduction.com/2026/04/24/material-maker-1-6-tunes-graphs-and-exports/)
- [Material Maker source — RodZill4/material-maker](https://github.com/RodZill4/material-maker)
- [CodeEvolve — open evolutionary coding framework (arXiv 2510.14150, Oct 2025)](https://arxiv.org/html/2510.14150v4)
- [ShaderToy-MCP — wilsonchenghy](https://github.com/wilsonchenghy/ShaderToy-MCP)
- [AIShader — keijiro (Unity)](https://github.com/keijiro/AIShader)
- [Godot MCP Pro (Asset Library 4961, April 2026)](https://godotengine.org/asset-library/asset/4961)
- [Godot AI Suite (Asset Library 5050, 2026)](https://godotengine.org/asset-library/asset/5050)
- [VLMaterial — Procedural Material Generation with Large Vision-Language Models (ICLR 2025)](https://arxiv.org/html/2501.18623)
- [MultiMat — Multimodal Program Synthesis for Procedural Materials (ICCV/arXiv 2509.22151)](https://arxiv.org/abs/2509.22151)
- [Multi-texture synthesis through signal responsive neural cellular automata (Nature Sci. Reports 2025)](https://www.nature.com/articles/s41598-025-23997-7)
- [Diffusion Renderer — Neural Inverse and Forward Rendering with Video Diffusion (CVPR 2025)](https://openaccess.thecvf.com/content/CVPR2025/papers/Liang_Diffusion_Renderer_Neural_Inverse_and_Forward_Rendering_with_Video_Diffusion_CVPR_2025_paper.pdf)
- [shader-slang/neural-shading-s25 — SIGGRAPH 2025 Neural Shading Course](https://github.com/shader-slang/neural-shading-s25)
- [Shaders21k — Procedural Image Programs for Representation Learning (NeurIPS 2022; still active reference corpus)](https://github.com/mbaradad/shaders21k)
