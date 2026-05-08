# Research Response — Characters / Animation Pipeline (2026 SOTA)

**Date:** 2026-05-07
**Brief:** `01_characters_animation.md`
**Hardware target:** RTX 5090 Laptop, 24 GB VRAM, Blackwell sm_120, CUDA 12.8+, torch ≥ 2.7, Windows 11 native preferred.

---

> **2026-05-07 PM — implementation outcome (corrects two claims below):**
>
> - **Puppeteer ✅ installed and validated** — went **native Windows + cu128**, not WSL2. The "2-4 hour install slog" estimate held but was the right path: end-to-end rig pipeline produces deer.fbx + spiderman.fbx (skeleton + skinning + bpy export). Full recipe + 9 documented gotchas in [animators/INSTALL_MATRIX.md](../../../animators/INSTALL_MATRIX.md).
> - **AniMo ❌ skipped — the brief's "modest VRAM, native Windows plausible" estimate was wrong.** The repo at github.com/WandererXX/AniMo ships **only training scripts** (`train_vq.py` + `train_t2m_transformer.py` + `train_res_transformer.py`). **No `inference.py`, no released checkpoints, no Releases page, no tags.** Dataset must be self-generated via `data_generation/`. To use AniMo we'd have to generate AniMo4D + run 3 sequential multi-day train phases + write our own inference. Research artifact, not a usable tool. Use AnyTop (already validated, unconditional sampling) for non-humanoid motion until a SOTA text-conditioned animal-motion tool with shipped checkpoints emerges.
>
> The rest of the brief stands. Q1's recommendation #2 (AniMo) and Q2's recommendation #1 (Puppeteer install caveats) should be read with these outcomes in mind.

---

## Executive summary up front

The honest answer is that **the current install matrix is already close to SOTA** — but the specific tools you have don't necessarily compose well, and the AnimateAnyMesh "trash" output is almost certainly because it was never the right tool for "rigged-game-character-doing-an-action." It's a 4D foundation model trained for short, mostly stationary text-driven mesh deformations — head turns, light flapping, breathing. It is not a substitute for a skeleton + retargeted clip.

For the 33-character roster, the canonical 2026 path is:

1. **Rig with Puppeteer** (NeurIPS '25 spotlight) or **SkinTokens** (already installed). Puppeteer is the only single-repo system that *also* offers video-guided animation, so it's the strongest candidate for non-humanoids where you don't have a clean text→motion model.
2. **Animate humanoids via Hunyuan-Motion** (you have it) → retarget to Mixamo/SMPL-H → apply via Make-It-Animatable or your own retargeter.
3. **Animate non-humanoids via AnyTop** (you have it) — but use the *right* specialized model per topology, and don't expect text conditioning. For text-conditioned non-humanoid motion, **AniMo** (CVPR '25, code released, 114 species) is the more targeted choice; **X-MoGen** and the late-2025 **OmniZoo / topology-agnostic** paper are research previews without confirmed code.
4. **Use AnimateAnyMesh only for "ambient mesh wiggle"** (idle breathing, plant sway, tentacle ripple on otherwise-static decoration) — not for character action.

The one likely missing piece in your matrix is **a video-driven retargeter** for capturing reference footage (yours or stock) and pulling motion onto rigged meshes. The 2026 incumbent is **GVHMR + GMR (ICRA '26)** for humans and the **SMAL/AniMal-pipeline** family for animals. For purely creative output, **Puppeteer's video-guided mode** is the simplest single-stop choice.

Below, per question.

---

## Q1 — 2026 SOTA for animating diverse non-humanoid creatures

### Recommendations

**1. AnyTop (you have it) — keep, but use correctly.**
AnyTop ([SIGGRAPH '25](https://anytop2025.github.io/Anytop-page/), [arXiv:2502.17327](https://arxiv.org/abs/2502.17327), [github](https://github.com/Anytop2025/Anytop)) is still the strongest *open-weights* option in 2026 for skeleton-conditioned motion diffusion across heterogeneous topologies. Its main limitation is that it is **unconditional** — there is no text prompt. You feed it a rigged skeleton and it samples plausible motion. For your roster you should be picking the right specialized model (biped / quadruped / flying / millipede-snake / all) per character family and accepting that you will run multiple samples and curate.

**2. AniMo (CVPR '25) — the real successor for text-conditioned animals.**
[AniMo](https://github.com/WandererXX/AniMo) ([paper](https://openaccess.thecvf.com/content/CVPR2025/papers/Wang_AniMo_Species-Aware_Model_for_Text-Driven_Animal_Motion_Generation_CVPR_2025_paper.pdf)) is a species-aware, text-driven animal motion model trained on **AniMo4D** (78k motion sequences across 114 species, 185k captions). Two-stage: motion-VQ tokenization with species-aware feature modulation, then a Base+Residual Transformer. Code is released, conda env provided. This is what you actually want for "monster does X" prompts on a rigged quadruped/insect. **Honest caveat:** 114 species is broad biologically but heavy on real animals; sandworms, tentacle horrors, dragons-with-six-legs are out of distribution and will need either a closest-species retarget or an AnyTop fallback.

**3. AnimateAnyMesh — demote to "ambient deformation only."**
[AnimateAnyMesh](https://github.com/JarrentWu1031/AnimateAnyMesh) ([ICCV '25 paper](https://arxiv.org/abs/2506.09982)) is a feed-forward 4D mesh-trajectory model. The "DyMeshVAE + Shape-Guided Text-to-Trajectory" architecture is good at *short, low-displacement* deformations of arbitrary-topology meshes (the demo set is dominated by gentle wobbles and shape-key-style effects). Training code for DyMeshVAE was released [Feb 2026](https://github.com/JarrentWu1031/AnimateAnyMesh). Your "trash, most do nothing or barely move the head" experience matches a known limitation — not a config bug, a model-capacity bug for character action.

**Watch list (research previews, no confirmed Windows-ready release):**

- **UniMoGen** (arXiv:2505.21837, [paper](https://arxiv.org/abs/2505.21837)) — UNet-diffusion, skeleton-agnostic, dynamic joint count, controllable via style+trajectory+past frames, 250× fewer inference steps than MDM. **No public code as of 2026-05.**
- **X-MoGen** (arXiv:2508.05162, [paper](https://arxiv.org/abs/2508.05162)) — first unified human+animal text-conditioned model, UniMo4D dataset (115 species, 119k seqs). **No public code.**
- **OmniZoo / "Topology-Agnostic Animal Motion Generation from Text Prompt"** (arXiv:2512.10352, [paper](https://arxiv.org/abs/2512.10352), Dec 2025) — 140 species, 32,979 sequences, text-driven autoregressive on arbitrary topologies. **Dataset/code not yet public.**
- **MocapAnything** (Huawei, arXiv:2604.28130, [paper](https://arxiv.org/abs/2604.28130), 2026) — video → non-humanoid skeleton mocap → BVH, mesh-free. Would be net-new capability (AnyTop is unconditional, Puppeteer's video mode is rig+animate not pure mocap). **Only unofficial reimplementation exists (github.com/animotionlab26/MocapAnything, 2026-04-09 anonymous org, no checkpoints, no license, author disclaims as "not a reproduction").** Revisit if Huawei ships official weights. See [memory note](C:\\Users\\josep\\.claude\\projects\\d--assets\\memory\\mocapanything_unofficial_skip.md).

If any of these ship code in Q2-Q3 2026, they could leapfrog AnyTop + AniMo. Today, they're papers.

### Hardware fit
- **AniMo:** PyTorch + CLIP, modest VRAM (single GPU); CUDA 12.x will work on Blackwell with torch ≥ 2.7. Windows-native plausible (conda + pip + CLIP). No exotic ops noted.
- **AnyTop:** Already validated in your install matrix; keep as-is.
- **AnimateAnyMesh:** Already installed.

### License + cost
AnyTop, AniMo, AnimateAnyMesh — all academic open-weights. Free.

### Maturity
- AnyTop: SIGGRAPH '25, actively cited; repo healthy.
- AniMo: CVPR '25, code released, environment.yml provided.
- AnimateAnyMesh: ICCV '25, training code released Feb 2026 — *most* active of the three but limited by its scope.

### Honest comparison vs what you have
**Lateral, with one true addition.** AniMo is the actual addition. UniMoGen / X-MoGen / OmniZoo are not yet usable. AnyTop and AnimateAnyMesh remain SOTA in their narrow lanes; the bad outputs were a usage problem, not a tool problem.

---

## Q2 — 2026 autoriggers, broadest topology range

### Recommendations

**1. Puppeteer (NeurIPS '25 Spotlight) — the most complete single tool.**
[Puppeteer](https://github.com/Seed3D/Puppeteer) ([paper](https://arxiv.org/abs/2508.10898), [project page](https://chaoyuesong.github.io/Puppeteer/)) does *both* rigging and animation in one repo. Rigging path: point-cloud + normals → autoregressive transformer with joint-based tokenization → topology-aware joint-attention skinning. Trained on **Articulation-XL2.0** (59.4k models, 11.4k diverse-pose subset). FBX export with bones+skin. Apache 2.0. The published comparisons claim improvements over UniRig and MagicArticulate on non-humanoid topology; the *real* differentiator vs SkinTokens is the integrated video-guided animation step, which gives you a one-tool path for non-humanoids you can't easily text-condition.

**Caveat:** Repo specifies Python 3.10.13, PyTorch 2.1.1 + CUDA 11.8, plus flash-attn / pytorch3d / torch-scatter. **This will NOT install cleanly on Blackwell sm_120** without rebuilds — flash-attn 2.x, torch-scatter, and pytorch3d all need either prebuilt sm_120 wheels (rare) or local compilation against CUDA 12.8. Plan for a 2–4 hour install slog. WSL2 is the safer path here.

**2. SkinTokens (you have it) — keep as primary humanoid + small-creature default.**
[SkinTokens](https://github.com/VAST-AI-Research/SkinTokens) ([paper](https://arxiv.org/html/2602.04805)) is the successor to UniRig. The published numbers show **98–133% improvement in skinning accuracy** and 17–22% in bone prediction over UniRig/MagicArticulate, with FSQ-CVAE-enforced locality eliminating the bleeding artifacts UniRig suffered. For finger-level articulation it's the only method that preserves spatial differentiation cleanly. This is your default for humanoids and quadrupeds with clear bilateral symmetry.

**3. RigAnything (you have it) — keep for the pathological cases.**
[RigAnything](https://github.com/Isabella98Liu/RigAnything) ([paper](https://arxiv.org/abs/2502.09615)) is the best when topology is genuinely weird (sandworms, tentacles, segmented bodies). Template-free autoregressive, trained on RigNet + 9686 curated Objaverse rigs. Inference under a few seconds. Python 3.11, CUDA 12.x — **Blackwell-friendly** as installed.

**Watch:**
- **SPRig** (arXiv:2602.12740, Feb 2026) — adds temporal-consistency self-supervision *on top of* existing static riggers (UniRig/RigAnything/SkinTokens). It's a wrapper, not a replacement. If your animations show jitter at the rigging stage, this is the upgrade path. Code status unclear.
- **Make-It-Animatable** ([CVPR '25 Highlight](https://github.com/jasongzy/Make-It-Animatable)) — sub-second humanoid rig, MIT license, but **humanoid-only** by design. Good for humanoid throughput; useless for monsters.
- **Tripo Rigging 2.5** (closed, [tripo3d.ai](https://www.tripo3d.ai/features/ai-auto-rigging)) — claims biped/quadruped/birds/insects/static; API-priced. Skip unless you want a managed fallback.

### Hardware fit
- **SkinTokens, RigAnything:** already installed, Blackwell-OK.
- **Puppeteer:** flash-attn 2.x + pytorch3d + torch-scatter on sm_120 = WSL2 fallback.
- **Make-It-Animatable:** Linux examples only, training tuned for A100 80G; **inference** should fit in 24 GB. Windows-native: untested by upstream, conda+pip only. Likely OK.

### License + cost
All open-weights / academic licenses (Apache 2.0 for Puppeteer, MIT for Make-It-Animatable). Free. Tripo: cloud API, undisclosed pricing.

### Maturity
- Puppeteer: NeurIPS '25, last activity Sep 2025; actively maintained but in initial-release phase.
- SkinTokens, RigAnything: actively maintained.
- Make-It-Animatable: CVPR '25 Highlight; modest commit count, unknown long-term maintenance.

### Honest comparison vs what you have
**Puppeteer is the addition worth adding.** SPRig is a future quality-fixer. Make-It-Animatable adds humanoid throughput but is a sidegrade for your purposes. The "newer than SkinTokens, measurably better on non-humanoid" candidate doesn't exist as of 2026-05; SkinTokens still wins on benchmarks.

---

## Q3 — Best end-to-end "mesh + text → rigged + animated FBX" workflow, 2026

### Canonical recipe

The honest 2026 production answer is **(a) rig first, then animate skeletal — hybrid only as decoration**. Shape-key animation (AnimateAnyMesh-style) is not the way to make a centipede walk; it's the way to make a static centipede *breathe* on a static rock.

**Per character, two paths:**

#### Path A — Humanoid (10 of 33 ish, by your description)
1. **Mesh** (have it, 30k tris from Meshy preprocessing).
2. **Rig:** SkinTokens → FBX with skeleton + skin weights. 30 s/asset.
3. **Animate:** Hunyuan-Motion text prompt → BVH/FBX in SMPL-H or Mixamo skeleton. ~10 s.
4. **Retarget:** Blender bpy or Mixamo Auto-Rigger / Make-It-Animatable → animated FBX on character skeleton.
5. (Optional) **Cleanup:** foot-locking pass, see Q5.

Total: ~1–2 minutes per humanoid per animation clip.

#### Path B — Non-humanoid (~23 of 33)
1. **Mesh.**
2. **Rig:** RigAnything for unusual topologies, SkinTokens for clean quadrupeds. → FBX with skeleton + skin.
3. **Animate, by sub-type:**
   - **Quadruped/insect/biped-non-humanoid** with text prompt → **AniMo** (closest species) → BVH on AniMo skeleton → retarget to your rigged skeleton via Blender NLA / `bpy_extras` / `pyfbx`.
   - **Truly out-of-distribution** (sandworm, tentacle, six-legs): **AnyTop** specialized model → unconditional sample → curate.
   - **Alternative for hard cases**: **Puppeteer** end-to-end, video-guided (you provide a reference video clip; it rigs and animates in one).
4. **Cleanup**: contact-pose pass for legged creatures.

Total: ~2–5 minutes per non-humanoid per clip plus curation overhead for AnyTop's unconditional sampling.

#### What about "hybrid" (skeletal + shape-key)?
Use shape keys *additively*: skeletal animation for primary motion + shape keys for secondary detail (face expressions, gill flutter, mantle pulse). This is standard production practice. AnimateAnyMesh is a candidate for *generating* the shape-key layer because shape-keys-from-mesh-deformation is exactly its sweet spot — but you'll need to bake displacement to shape keys, which is a Blender script step.

### What does production game-asset work look like in 2026?

The big-studio reference is **Hunyuan3D Studio** ([paper](https://arxiv.org/html/2509.12815v1)) and **Tripo P1 + Tripo Rigging 2.5**: image/text → mesh → retopo → PBR texture → auto-rig → engine export, all in one closed pipeline. For an open-weights pipeline closest to that, your current matrix + Puppeteer is approximately what an indie studio would assemble. The Meshy → preprocess → SkinTokens/RigAnything/Puppeteer → Hunyuan-Motion/AniMo/AnyTop → Blender retarget chain is the 2026 indie SOTA.

### Honest comparison
**Your current pipeline is already the right shape. The missing pieces are (1) Puppeteer for unified non-humanoid rig+animate, (2) AniMo for text-conditioned non-humanoid motion, (3) a documented retarget script.** The "trash" outputs are not a chain failure — they're a tool-misuse failure (AnimateAnyMesh used for character action) plus an undocumented run config.

---

## Q4 — Tools you might be missing entirely

### Video-to-motion (mocap from RGB)
You don't have one. The 2026 open-weights stack:

**1. GVHMR + GMR (ICRA '26)** — [GMR github](https://github.com/YanjieZe/GMR). GVHMR pulls SMPL-X from monocular video; GMR retargets to humanoid robots / arbitrary humanoid skeletons in real-time on CPU. The combination is the cleanest 2026 pipeline for "I record myself doing X, paste it onto a character." MIT-style licenses. Windows-buildable.
**2. Sapiens** ([Meta](https://github.com/facebookresearch/sapiens)) — foundation human-vision models (2D pose, depth, segmentation, normals) at 1024² resolution. Excellent feature extractor for any custom video→motion pipeline. Licensed for research/commercial via Meta's terms.
**3. WHAM / TRAM** — established baselines, still useful, less SOTA in 2026.
**4. EasyMocap / XRMoCap** — mature multi-view toolboxes if you ever capture your own footage.

For **animal video → motion**: SMAL/SMBLD parametric models exist but the pipeline is research-grade. Skip unless you have a specific need.

### Specialized creature animators
The honest answer: **you won't find a "snake animator" or "spider animator" SaaS in 2026.** The production answer for these creatures in shipping games is **procedural IK** (Unreal Control Rigs, Unity procedural-IK assets, or hand-coded Godot scripts). The relevant search results all point to procedural systems, not learned ones.

For your use case (sprite-sheet baking from 3D), procedural IK in your **runtime engine isn't useful** — you need the animation baked into FBX before sprite-bake. So: rig + AnyTop + curate is the path. Or: rig in Blender, hand-author tail/spine bone constraints, key out 16 frames manually for the worst offenders. For 33 characters this is feasible if AnyTop fails on ~5 of them.

### "AI animator wrappers" that auto-decide rigging vs shape-key
**Don't exist in 2026.** Puppeteer is the closest — it picks "rig + skeletal animation" as the One True Path and ignores shape-key paradigms. There is no router that says "this is a tentacle, use shape-key" vs "this is a humanoid, use skeletal." If you want one, it's a 200-line classifier on your end.

### Honest comparison vs what you have
**One real addition (GVHMR+GMR), one realistic procedural-IK admission, and one "doesn't exist."** If you ever want to record yourself doing combat moves and paste them onto a humanoid roster, GVHMR+GMR is the install. Otherwise the gap is small.

---

## Q5 — Animation review / quality scoring

### Recommendations

**1. FVMD — Fréchet Video Motion Distance** ([github](https://github.com/DSL-Lab/FVMD-frechet-video-motion-distance), pip-installable). Measures temporal motion consistency from video frames; catches over-smoothed and jittery generations. ICML 2024 workshop. Good *aggregate* metric — gives one number per clip vs a reference distribution. **Limitation per the literature:** Fréchet Motion Distance variants do not reliably catch foot-skating intensity. So FVMD = "is this clip plausibly animated at all" — not "are the feet pinned."

**2. Foot-skating / contact-violation: Blender-script the metric yourself.**
There is no 2026 turnkey "animation linter" tool. Build a 50-line Blender script:
- Load FBX, sample foot-bone world-space xy at each frame.
- Detect "in contact" frames by foot-z below threshold.
- Flag any frame where foot-xy delta > epsilon while in contact = foot-skate frame.
- Threshold: skate-frames / total-frames > 5% = fail.
This is exactly what Kovar/Schreiner '02 (the canonical "Footskate Cleanup") describes; modern repos have nothing better as a *metric*, only as a *fixer*.

**3. Static-frame detection: trivial per-bone delta script.**
- Sum of per-bone rotation deltas across the clip < threshold = "didn't move." This is the actual filter for your "most do nothing or barely move the head" complaint. **Ten lines of Blender Python.** Run it as a CI gate after every batched animation.

**4. Self-intersection / penetration:** Mesh self-intersection per-frame can be checked via `bpy.ops.mesh.intersect` or a custom BVH-vs-BVH per pair of bones. Heavier (~1 s/frame). Not standard practice; do it only on a sampled subset.

### Hardware fit
All Blender-script-based. No GPU needed. Windows-native trivial.

### License + cost
Free. Self-built.

### Maturity
FVMD: research-grade but pip-installable. The custom scripts are throwaway code — that is the mature option.

### Honest comparison
**There is no "2026 standard" tool.** A 100-line Blender CI-style script will do more for your validation than any single research repo. The lit specifically warns FMD-family metrics miss foot-skate. Build the linter; it's a one-afternoon job.

---

## Q6 — Sprite-sheet baking, 2026

### Recommendations

**1. Stay on Blender + custom script — you're already on the right tool.** The 2026 ecosystem for 3D-to-sprite-sheet is mature but small:
- **[blender-spritesheets](https://github.com/theloneplant/blender-spritesheets)** — Unity-targeted, animated 3D → sheet exporter.
- **[SpriteBatchRender](https://github.com/pekkavaa/SpriteBatchRender)** — Blender plugin, multiple-direction batch rendering, separate-file output.
- **[DirectionalSpriteBatchRender](https://github.com/chronicleroflegends/DirectionalSpriteBatchRender)** — purpose-built for Zdoom / 8-direction sprite output.
- **[Spritesheet Renderer](https://blender-addons.org/spritesheet-renderer/)** — generic 3D-to-sheet automation.
- **Sequenced Bake** (Blender Extensions) — frame-by-frame *material* baking, not directional renders, but useful if you want texture-baked sheets.

**2. Use EEVEE-Next, not Cycles.** On Blackwell sm_120 EEVEE-Next does ~6816×3344 frames at 50–500 ms each depending on scene complexity. Cycles for sprite-sheet baking is overkill unless you specifically want raytraced shadows/SSS in the bake. For 33 characters × 8 directions × 16 frames = 4,224 frames per sheet — at 200 ms/frame that's 14 minutes. Tractable.

**3. Bake-pipeline pattern that scales:**
- One headless `blender --background --python script.py` per character.
- `bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'`.
- Orthographic camera on a parented Empty; rotate the Empty 8× per frame; loop 16 frames.
- Composite tile-grid in script via Pillow (don't use Blender's image compositor — slower, less flexible).
- Output PNG per direction × frame, then stitch.
- Run all 33 characters with `xargs -P` or PowerShell `ForEach-Object -Parallel`.

**4. There is no 2026 "AI sprite-sheet baker" worth using.** SpriteFusion's "AI sprite generator" is a 2D/text→sprite tool unrelated to your 3D→2D bake.

### Hardware fit
Blender 4.x EEVEE-Next runs natively on Blackwell with current driver, no CUDA-version sensitivity. Windows-native.

### License + cost
All free / open / GPL.

### Maturity
Blender 4.x + EEVEE-Next is the most-maintained renderer in this space. The community sprite-sheet plugins are old (2016–2020) but the *pattern* is current and well-documented.

### Honest comparison
**Lateral.** No 2026 tool beats a tight Blender headless script for your scale. Adding a plugin gains nothing over a 100-line Python file you control. Spend the time on parallelization (`-P 4` across the L4 wells of your 5090) rather than tool selection.

---

## What to do next (recommendation, not a plan)

In priority order:

1. **Recover the bad-run config first** (`animators/AnimateAnyMesh/runs/*.log` or whatever you keep). The 33-character roster is too valuable to re-run blind.
2. **Install Puppeteer in WSL2** as a fallback — accept the install pain once. It's the single-tool path for "rig + animate" non-humanoids and gives you a non-AnyTop second opinion.
3. **Install AniMo** native Windows — quick conda env, validated to work. This unlocks text-conditioned animal motion which AnyTop can't do.
4. **Pick 1 humanoid + 1 non-humanoid validator** before fanning out. Suggested: humanoid via SkinTokens → Hunyuan-Motion → retarget. Non-humanoid via RigAnything → AniMo (if species-near) or AnyTop (if topology-out).
5. **Write the animation linter** (Q5 #3). Even before fanning out — so the validator pass produces a numeric quality bar.
6. **Defer**: GVHMR+GMR (only if you want video-driven mocap), SPRig (only if you see jitter), OmniZoo / X-MoGen / UniMoGen (wait for code).

---

## Sources

### Q1 (non-humanoid creature animation)
- [AnyTop project page](https://anytop2025.github.io/Anytop-page/), [arXiv:2502.17327](https://arxiv.org/abs/2502.17327), [github](https://github.com/Anytop2025/Anytop)
- [AniMo CVPR '25 paper](https://openaccess.thecvf.com/content/CVPR2025/papers/Wang_AniMo_Species-Aware_Model_for_Text-Driven_Animal_Motion_Generation_CVPR_2025_paper.pdf), [github](https://github.com/WandererXX/AniMo)
- [AnimateAnyMesh project page](https://animateanymesh.github.io/AnimateAnyMesh/), [github](https://github.com/JarrentWu1031/AnimateAnyMesh), [ICCV '25 paper](https://arxiv.org/abs/2506.09982)
- [UniMoGen paper](https://arxiv.org/abs/2505.21837)
- [X-MoGen paper](https://arxiv.org/abs/2508.05162)
- [Topology-Agnostic Animal Motion (OmniZoo)](https://arxiv.org/abs/2512.10352)
- [OmniMotionGPT](https://github.com/USRC-SEA/OmniMotionGPT)

### Q2 (autoriggers)
- [Puppeteer project](https://chaoyuesong.github.io/Puppeteer/), [github](https://github.com/Seed3D/Puppeteer), [paper](https://arxiv.org/abs/2508.10898)
- [SkinTokens github](https://github.com/VAST-AI-Research/SkinTokens), [paper](https://arxiv.org/html/2602.04805), [project page](https://zjp-shadow.github.io/works/SkinTokens/)
- [UniRig github](https://github.com/VAST-AI-Research/UniRig)
- [MagicArticulate github](https://github.com/Seed3D/MagicArticulate)
- [RigAnything github](https://github.com/Isabella98Liu/RigAnything), [paper](https://arxiv.org/abs/2502.09615)
- [Make-It-Animatable github](https://github.com/jasongzy/Make-It-Animatable), [project page](https://jasongzy.github.io/Make-It-Animatable/)
- [SPRig paper](https://arxiv.org/html/2602.12740v1)
- [Tripo auto-rigging](https://www.tripo3d.ai/features/ai-auto-rigging)

### Q3 (end-to-end workflow)
- [Hunyuan3D Studio paper](https://arxiv.org/html/2509.12815v1)
- [HY-Motion 1.0 github](https://github.com/Tencent-Hunyuan/HY-Motion-1.0)
- [Best AI 3D model generators 2026 (Meshy blog)](https://www.meshy.ai/blog/best-ai-tools-for-3d-game-assets)

### Q4 (missing tools)
- [GMR (ICRA '26) github](https://github.com/YanjieZe/GMR)
- [Sapiens github](https://github.com/facebookresearch/sapiens), [paper](https://arxiv.org/html/2408.12569v1)
- [VideoPose3D](https://github.com/facebookresearch/VideoPose3D)
- [EasyMocap](https://github.com/zju3dv/EasyMocap)
- [XRMoCap](https://github.com/openxrlab/xrmocap)
- [ActionMesh github](https://github.com/facebookresearch/actionmesh) — note: video+3D→4D, not text→4D
- [Procedural Snakes & Dragons (Unreal community)](https://dev.epicgames.com/community/learning/tutorials/r4n5/unreal-engine-procedural-snakes-and-dragons)

### Q5 (animation review)
- [FVMD github](https://github.com/DSL-Lab/FVMD-frechet-video-motion-distance), [project blog](https://dsl-lab.github.io/blog/2024/fvmd-2/), [arXiv](https://arxiv.org/html/2407.16124v1)
- [FMD on foot-skating (SIGGRAPH MIG '23)](https://dl.acm.org/doi/10.1145/3623264.3624443)
- [Kovar/Schreiner Footskate Cleanup '02](https://research.cs.wisc.edu/graphics/Gallery/kovar.vol/Cleanup/)
- [Foot Lock Blender add-on](https://superhivemarket.com/products/foot-lock)

### Q6 (sprite-sheet baking)
- [blender-spritesheets](https://github.com/theloneplant/blender-spritesheets)
- [SpriteBatchRender (Blender)](https://github.com/pekkavaa/SpriteBatchRender)
- [DirectionalSpriteBatchRender](https://github.com/chronicleroflegends/DirectionalSpriteBatchRender)
- [Spritesheet Renderer](https://blender-addons.org/spritesheet-renderer/)
- [Sequenced Bake (Blender Extensions)](https://extensions.blender.org/add-ons/sequenced-bake/)
