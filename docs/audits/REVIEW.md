# Character Pipeline Review — 2026-05-05 (updated end-of-day)

Comprehensive review of the **character pipeline** (`meshy/`, `animators/`) after end-to-end verification on goblin, witch, and bone_construct. Reviews each script, finds bugs, surveys 2026 alternatives, and prioritizes next steps.

**Scope:** this doc is character-pipeline-specific. For status of all other pipelines (terrain, textures, world maps, shaders, biomes, VFX, etc.) see [PIPELINE_DIRECTORY.md](../../PIPELINE_DIRECTORY.md). For their walkthroughs see [PIPELINE_GUIDE.md](../../PIPELINE_GUIDE.md). For roadmap see [../plans/ROADMAP.md](../plans/ROADMAP.md).

## 🟢 Update — 2026-05-05 evening: all 3 bugs fixed + Mesh2Motion installed + 30 assets batch-preprocessed

Subsequent work delivered:
- **`pack_sheet.py` jitter** — fixed via union-bbox-per-angle. Re-baked goblin verifies frames stay centered across walk cycle.
- **`pixel_art.py` shimmer** — fixed via shared-palette across frames. Goblin v2 pixel-art shows consistent green hues across all 16 frames.
- **`bake_sprites.py` camera** — `position_camera` now uses both `radius_xy` and `radius_z`, no more no-op ternary.
- **Mesh2Motion** — installed at `D:\assets\animators\mesh2motion-app\`, launcher script at `start.ps1`. Boots in 207ms, runs on http://localhost:5173. Honest finding: same UI-driven workflow as Mixamo, just self-hosted. Wins are quadruped/bird/dragon support and no Adobe dependency. **Does not save the manual upload step**.
- **`batch_preprocess.py`** — written and ran successfully: **30/30 assets succeeded in 406 seconds (~13.5s/asset average), zero failures**. All 33 Meshy outputs now have preprocessed `_p.glb` companions in `../../meshy/preprocessed/`. Originals at `output/<name>/model.glb` are untouched. Summary at `../../meshy/preprocessed/_batch_summary.json`.

For navigation: [TOOLS_INDEX.md](../../TOOLS_INDEX.md) | [PIPELINE_GUIDE.md](../../PIPELINE_GUIDE.md) | [../plans/ROADMAP.md](../plans/ROADMAP.md)

---

## 1. Pipeline state — what's verified and where

| Stage | Tool | Status | Lines | Notes |
|---|---|---|---|---|
| Image → 3D | Meshy API | ✅ verified, 33 models cached | 103 + 59 wrappers | Plaintext API key, no retry on transient failures |
| Image → 3D backup | Trellis2 | ⚠️ imports OK, inference untested | n/a | Must run from project dir |
| Mesh preprocess | Blender script | ✅ verified on goblin/witch/bone_construct | 367 | Now includes topology checks |
| Auto-rig (humanoid) | Mixamo (web) | ✅ FBX prep verified | n/a | Manual web upload step |
| Auto-rig (any) | RigAnything | ✅ goblin/witch | n/a | Fastest (~5s) |
| Auto-rig (best skin) | SkinTokens | ✅ goblin/witch | n/a | 2026 SOTA |
| Auto-rig (skel only) | MagicArticulate | ✅ goblin/witch | n/a | No skinning |
| Animate (text→mesh) | AnimateAnyMesh | ✅ verified | n/a | Subtle motions |
| Animate (text→motion) | hy-motion | ⚠️ CLI works, needs Mixamo input | n/a | Untested with real model |
| Sprite bake | Blender script | ✅ verified | 264 + 65 | One no-op ternary |
| Atlas pack | Pillow script | ✅ verified | 136 | Frame jitter bug w/ --crop |
| Pixel-art filter | Pillow script | ✅ verified | 104 | Per-frame palette = temporal jitter |
| Batch animate | wrapper | ✅ verified | 112 | Now writes LF |
| Batch full pipeline | wrapper | ✅ verified | 136 | Animate + bake + pack + pixel-art |

---

## 2. Bugs found this session

### ✅ Confirmed real bugs (all fixed 2026-05-05)

| Severity | File | Bug | Fix applied |
|---|---|---|---|
| ✅ HIGH | `pack_sheet.py` | With `--crop`, each frame independently centered → animation jitter | Now groups frames by angle and uses union bbox for that angle group |
| ✅ HIGH | `pixel_art.py` | Per-frame palette quantization → colors shift across animation frames | Two-pass: builds shared palette from sample frames, applies to all via `quantize_with_shared_palette()` |
| ✅ LOW | `bake_sprites.py` | No-op ternary on camera distance calc | Distance now correctly differs by camera type (2.0× ortho vs 2.75× perspective) |
| ✅ LOW | `bake_sprites.py` | `position_camera` ignored `radius_z` | Now uses `effective_radius = max(radius_xy, radius_z * 0.6)` |
| ⏸️ LOW | `meshy_image_to_3d.py` | No retry on Meshy 5xx errors | Deferred — Meshy hasn't actually returned 5xx during our usage |

### 🟡 Already fixed earlier
- `preprocess.py` collapsed every Meshy `model.glb` to single `model_p.glb` — fixed (uses parent dir name)
- `glb_to_fbx.py` carried `_p` suffix into output — fixed (strips it)
- `batch_animate.py` wrote CRLF — fixed (LF newlines)

---

## 3. Tool survey — what's new in 2026

I researched the SOTA in each category to spot what we should adopt or substitute.

### Image-to-3D
- **What we have**: Meshy (cloud, ~30 credits), Trellis2 (local, untested)
- **2026 alternatives**:
  - [Hunyuan3D-2.1](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1) — Tencent, open-source, image-to-PBR-mesh. Strong contender. Already in `~/.cache/huggingface/`.
  - [Stable Fast 3D](https://stability.ai/news/introducing-stable-fast-3d) — Stability AI, very fast (<1s).
- **Recommendation**: When Meshy credits run out, validate Trellis2 first (already installed). If Trellis2 has issues, Hunyuan3D-2.1 is a strong open-source backup.

### Auto-rigging — Mixamo alternatives
This is the big finding. Mixamo's development has been stalled for years and Adobe may eventually shut it down.
- **[Mesh2Motion](https://github.com/scriptsengineer/mesh2motion)** — open-source Mixamo alternative. Web-based, free, **supports humanoid + quadruped + bird**. Worth evaluating since it could solve the "Mixamo doesn't do quadrupeds" gap with no manual upload step.
- **[AccuRIG 2](https://magazine.reallusion.com/2025/07/30/accurig-2-vs-mixamo-smarter-auto-rigging-for-3d-animators/)** (Reallusion) — free, AI-driven, identifies hands and fingers. Desktop tool, not API.
- **[Tripo3D Auto-Rig](https://www.tripo3d.ai/)** — same company that made UniRig/SkinTokens. Cloud-based, possibly the same engine we have running locally already.
- **Recommendation**: Try Mesh2Motion (~30 min). If it can rig a quadruped and bake to FBX, it replaces both the Mixamo manual step AND fills the quadruped gap. Big leverage.

### Mesh retopology
- **What we have**: Blender Decimate (collapse mode) + optional voxel remesh
- **2026 alternatives**:
  - [Hunyuan Polygen 1.5](https://help.scenario.com/en/articles/hunyuan-polygen-the-essentials/) — Tencent's neural retopology model. **Not yet open-sourced** as of 2026-05.
  - [Instant Meshes](https://github.com/wjakob/instant-meshes) — open-source field-aligned quad remesher. Standalone executable.
  - [AutoRemesher](https://github.com/huxingyi/autoremesher) — open-source, libQEx + CoMISo solver.
  - [QRemeshify](https://github.com/ksami/QRemeshify) — Blender extension wrapping good quad topology.
- **Recommendation**: Defer. Our current decimate+collapse is good enough for sprite work. Only investigate retopology if we hit visible quality issues.

### Sprite generation pipeline  
- **What we have**: Custom Blender scripts (full control, free).
- **2026 commercial tools that do similar**:
  - [PixelLab](https://www.pixellab.ai/) — paid, Aseprite plugin, AI-driven directly.
  - [Ludo.ai](https://ludo.ai/features/sprite-generator) — text-to-sprite-sheet, paid.
  - [SEELE AI](https://www.seeles.ai/features/tools/sprite) — free tier, in-browser.
  - [PixelVibe](https://lab.rosebud.ai/blog/ai-game-assets-generator-pixelvibe) — Rosebud Lab, panoramas + sprites.
- **Recommendation**: None. Our 3D-to-2D pipeline gives you turnaround consistency that AI text-to-sprite tools struggle with (different angles never quite match). Stick with what we have.

### Pixel-art post-processing
- **What we have**: median-cut quantization with optional dithering, per-frame
- **2026 advances**:
  - [SD-πXL: differentiable palette quantization](https://arxiv.org/html/2410.06236v1) — 2024 research, gradient-based, much better quality
  - [PixDiff-PIG](https://www.researchgate.net/publication/398825200_PixDiff-PIG_Palette-Informed_Diffusion_for_Pixel_Art_Generation) — palette-aware diffusion model
  - **OKLab color space** — perceptually uniform, better quantization than RGB
- **Recommendation**: Implement the **shared-palette fix** (high priority, 30 lines). Then optionally migrate to OKLab quantization (~50 lines). Skip the diffusion-based ones — overkill.

### Game-engine integration  
- **What we have**: PNG atlas + JSON metadata (engine-agnostic)
- **What's missing**: Engine-specific exporters
  - Godot 4 `SpriteFrames` (TRES file) — ~30 lines
  - Unity `SpriteAtlas` + meta files — ~40 lines, more boilerplate
  - Aseprite JSON tag format (works with Phaser, LDtk, RPG Maker) — ~20 lines
- **Recommendation**: Pick the engine you actually use and write that one.

---

## 4. Prioritized next steps

By time-to-value (highest first):

### Tier 1 — fix what's broken (1-2 hours)
1. **Fix pack_sheet.py crop bug** (30 min). Compute union bbox per angle, crop all frames to same bbox, then center the entire angle group. Eliminates animation jitter.
2. **Fix pixel_art.py temporal coherence** (30 min). Two-pass: build palette from union of frames, apply to each. Eliminates color shimmer.
3. **Fix bake_sprites.py camera math** (15 min). Use both `radius_xy` and `radius_z` for proper framing of tall meshes.

### Tier 2 — fill a real gap (2-3 hours)
4. **Try Mesh2Motion** as Mixamo replacement (1 hour). Could solve quadruped rigging AND eliminate the manual upload step. Highest leverage potential.
5. **Validate Trellis2 inference** end-to-end (30 min). Confirm the backup is ready before Meshy credits run out.
6. **Batch-preprocess all 33 Meshy assets** (15 min). Just write a loop. Unblocks everything else.

### Tier 3 — engine integration (1 hour each)
7. **Pick a target engine** (Godot/Unity/Phaser/etc.) and write the atlas exporter. Single highest win for shipping the pipeline.

### Tier 4 — quality of life (deferred)
8. Test SkinTokens on a creature that Mixamo can't handle (hellhound, eye_horror) to validate the non-humanoid path.
9. Set up Anytop env (deferred — wait until we know we need it).
10. Implement Mixamo-skeleton retargeting for our other riggers' outputs.

### Tier 5 — quality polish (optional)
11. OKLab pixel-art quantization for higher-quality retro output.
12. Multi-animation packing — combine walk+attack+idle into a single sheet with named frame ranges.

---

## 5. Rough effort estimates

If you wanted to push this to "production-ready for shipping a game," here's the realistic time:

| Goal | Hours |
|---|---|
| Fix all 3 confirmed bugs | 1.5 |
| Validate Trellis2 + Mesh2Motion | 1.5 |
| Batch-preprocess all 33 assets | 0.5 |
| Generate full library: 33 chars × 4 animations (idle/walk/attack/death) = 132 sprites | 2-3 (mostly compute) |
| Write Godot/Unity exporter | 1-2 |
| Total | **6-9 hours** |

That's one focused day. The pipeline is genuinely close to "ready."

---

## 6. Things to NOT do

A few things that look tempting but aren't worth the cost:

- ❌ **Mixamo upload automation** (Selenium/Playwright). Mixamo's UI is JS-heavy and breaks with Adobe redesigns. Maintenance burden. Stick with manual or use Mesh2Motion.
- ❌ **Hunyuan Polygen for retopology**. Not open-sourced; only available on paid hosted services. Our Decimate + Collapse is good enough.
- ❌ **AI text-to-sprite tools** (PixelLab/Ludo/etc.). They generate single sprites well but struggle with multi-angle consistency. Our 3D-to-2D pipeline beats them on coherence.
- ❌ **Full retraining of AnimateAnyMesh** for directional motion. The model's design ignores direction modifiers; this isn't a bug we can fix without re-architecting their training.
- ❌ **Adopting flash_attn 4** in MagicArticulate. We just sourcebuilt FA2 and it works. Don't break it for marginal speed gain.

---

## 7. The "shipping-ready" definition

If you wanted to define "done" for this pipeline, here's what I think it means:

- ✅ Image-to-mesh works on multiple input styles
- ✅ Preprocessing is automated and detects bad geometry
- ✅ At least one rigging path (Mixamo) works for humanoids
- ⏸️ At least one rigging path works for quadrupeds (TBD — depends on Mesh2Motion test; FBX prepped at `mixamo_ready/hellhound.fbx`)
- ⏸️ Animation library exists for common verbs (walk/run/attack/idle) — only 5 character-prompt combos baked so far (goblin x4, witch x1, bone_construct x1)
- ✅ Sprite bake produces atlas + metadata
- ⏸️ Engine integration: at least one target engine has a one-command import path — Godot 4.5 confirmed, exporter not yet written
- ✅ All 33 existing Meshy models are processed and ready (batch_preprocess 30/30 succeeded 2026-05-05 evening)

The 3 ⏸️ items are the gap to "shippable" for characters specifically. ROADMAP scope expanded beyond shipping characters — full asset factory across categories is the new aim.

---

## Phase 11 Props Deep-Dive — 8 patches found and fixed (2026-05-06 PM)

Phase 11 took the props pipeline through the same investigation discipline the character pipeline got. Both AI routes (HY3D-2.1 + Trellis2 4B) ran end-to-end on RTX 5090 / cu130 / Win11, but neither worked first-try. Six install/runtime patches surfaced — all documented here so re-runs after venv rebuilds are easy.

### Hunyuan3D-2.1 (visualbruno fork) — 3 patches

#### 1. `multiview_utils.py:45` — `trust_remote_code` not passed to `from_pretrained`

**Symptom:** `ValueError: ... contains custom code in modules.py which must be executed to correctly load the model. Pass trust_remote_code=True to allow loading remote code modules.` after 135s of successful geometry generation, killed mid-paint-pipeline-load.

**Root cause:** Tencent's `hunyuan3d-paintpbr-v2-1` HF repo ships custom Python module code in the `unet/` subfolder. Modern `diffusers` defaults to `trust_remote_code=False` and rejects loading it.

**Fix:** Added `trust_remote_code=True` to the `HunyuanPaintPipeline.from_pretrained(...)` call.

#### 2. `convert_utils.py:138` — Chinese-character print crashes Windows cp1252 console

**Symptom:** `UnicodeEncodeError: 'charmap' codec can't encode characters in position 7-11` masked an *otherwise successful* GLB save. The PBR GLB was actually written to disk successfully, but a Chinese log message after `gltf.save()` crashed the print, which propagated as an exception that obscured the success.

**Root cause:** `print(f"PBR GLB文件已保存: {output_path}")` on line 138. Windows cp1252 console can't encode the Chinese characters.

**Fix:** Replaced with ASCII `print(f"[hy3dpaint] PBR GLB saved: {output_path}")`. This is an idempotent fix — even if Tencent updates the file upstream, our patch survives because the surrounding logic is unchanged.

#### 3. NVIDIA driver upgrade 592.01 → 596.36 (cu130 PTX support)

**Symptom:** `torch.AcceleratorError: CUDA error: the provided PTX was compiled with an unsupported toolchain. Search for cudaErrorUnsupportedPtxVersion`. Hit at the rasterizer step inside `custom_rasterizer-0.1.0+torch2100.cuda130-cp312-cp312-win_amd64.whl`.

**Root cause:** kijai's prebuilt rasterizer wheel was compiled against a CUDA 13.x toolkit. Driver 592.01 (Aug 2025) advertised CUDA runtime 13.1 but couldn't JIT-compile the wheel's PTX down to sm_120.

**Fix:** Upgraded NVIDIA driver to 596.36. After upgrade + wheel reinstall, rasterizer ran clean. **Lesson:** Blackwell (sm_120) cu130 wheels need a fairly recent driver; check `nvidia-smi` driver version against the wheel's build toolkit.

#### Patch 1 + 2 + 3 result

End-to-end gate-2 PBR run: **87 seconds on real Egyptian-obelisk concept** (DiT geometry → multi-view paint → bake → inpaint → 1.6 MB PBR-textured GLB).

### Trellis2 4B (microsoft/TRELLIS.2-4B) — 3 patches

#### 4. `flex_gemm/kernels/__init__.py` — `cuda.pyd` DLL load failure

**Symptom:** `ImportError: DLL load failed while importing cuda` at `from . import cuda`. The shipped `cuda.cp311-win_amd64.pyd` couldn't load its torch + CUDA dependencies on cu128.

**Root cause:** The wheel was compiled against torch 2.5/cu124. Our Trellis2 venv has torch 2.8/cu128. Windows since Python 3.8 requires explicit `os.add_dll_directory()` calls to find DLLs outside the standard search path.

**Fix:** Patched `flex_gemm/kernels/__init__.py` to call `os.add_dll_directory()` for CUDA 13.0 / 12.8 / 12.1 toolkit dirs + the torch lib dir before importing the cuda submodule. The cu124-built .pyd actually works fine on cu128 once the right DLL paths are searchable — the binary ABI is compatible enough at the python-extension level.

#### 5. Missing `flex_gemm.kernels.triton` submodule — write a pure-torch fallback

**Symptom:** `AttributeError: module 'flex_gemm.kernels' has no attribute 'triton'` at the rasterization stage of `o_voxel.postprocess.to_glb()`. The flex_gemm package's `__init__.py` does `try: from . import triton; except ImportError: pass` — and the triton subpackage was never installed in our venv.

**Root cause:** Trellis2's vendored `flex_gemm` package shipped only the `cuda.pyd` backend; the upstream `triton` Python submodule (which provides `indice_weighed_sum_fwd/bwd_input` for sparse weighted gathers) was never bundled.

**Fix:** Wrote a pure-torch fallback at `flex_gemm/kernels/triton/__init__.py`. The op semantics are simple — `out[m] = sum_k weight[m,k] * feats[indices[m,k]]` — which is just an indexed gather + weighted sum. Vanilla torch primitives (`feats[indices]` → `(gathered * weight).sum(dim=1)`) handle it.

#### 6. Sentinel index handling + dtype preservation in the fallback

**Symptom:** First triton fallback iteration: `CUDA error: device-side assert triggered. IndexKernel.cu:113: Assertion -sizes[i] <= index && index < sizes[i] && "index out of bounds" failed.` Second iteration: `RuntimeError: Index put requires the source and destination dtypes match, got Half for the destination and Float for the source.`

**Root cause:** `indices` may contain `-1` sentinels (Trellis2's neighbor-map "no neighbor / outside grid" marker). Vanilla torch indexing rejects them. Also, `feats` is fp16 but vanilla torch operations defaulted the output to fp32, which downstream `index_put` rejected.

**Fix:** Added `valid = (indices >= 0) & (indices < N)` mask + `safe_idx = torch.where(valid, indices, 0)` clamp before the gather; multiplied invalid contributions by zero via `(weight * valid.to(weight.dtype))`. For dtype: cast all intermediates to `feats.dtype` and `.to(feats.dtype)` on the final return. Both fwd and bwd_input variants got the same treatment.

#### Patches 4 + 5 + 6 result

End-to-end Trellis2 run: **86 seconds on real Egyptian-obelisk concept** (mesh generation 23s + o_voxel postprocess 8s for `mid` preset = 1,076,420 verts → 128k verts / 194k faces / 2048² PBR / 13.9 MB GLB).

### Patch 7 + 8: postprocess orchestrator (`../../pipelines/props/postprocess_ai_route.py`)

Built a one-command orchestrator that walks an AI-route GLB through 7 stages (preprocess → lod_chain → collision → billboard → pbr_bind → validate → export) to produce a Godot-importable prop. Smoke-tested end-to-end on the Trellis2 obelisk → `obelisk_egyptian_a04`, all stages green.

Two bugs found during orchestrator bring-up:

#### 7. `validate_props.py` doesn't have a `--id` flag

**Symptom:** `validate_props.py: error: unrecognized arguments: --id obelisk_egyptian_a02`. Orchestrator stage 6 failed.

**Root cause:** `validate_props.py` is a full-library validator (no per-prop flag). I assumed it had per-id selection.

**Fix:** Orchestrator invokes it without `--id`. Validator's pass/fail signal still covers the new prop because it's now in the library. Broken neighbors would be pre-existing factory bugs, not orchestrator-caused.

#### 8. Bootstrap prop.json wrote `triangles: 0` → all LODs reported tris=8

**Symptom:** After full pipeline run, prop.json showed `triangles: 8` for every LOD0/1/2/3. Cosmetic but wrong (real numbers should be ~194k/126k/68k/29k for a hero_prop ladder on a 194k mesh).

**Root cause:** `lod_chain.update_prop_json()` (line 117 of lod_chain.py) computes `approx_tris = max(8, int(round(base_hint * r_ratio)))` where `base_hint` reads from the existing prop.json. My orchestrator's bootstrap wrote `triangles: 0` for the LOD0 entry → `0 × 0.65 = 0` → `max(8, 0) = 8`.

**Fix:** Orchestrator now imports trimesh, reads `len(mesh.faces)` from the source GLB, and writes that into the bootstrap prop.json's LOD0 `triangles` field. Cleanly populates the ladder downstream.

### Phase 11 forensics conclusion

All 8 patches documented + reapply notes in `../../pipelines/props/TRELLIS2_PATCHES.md` (Trellis2) and inline in the visualbruno fork at `D:\assets\animators\ComfyUI_HY3D\custom_nodes\ComfyUI-Hunyuan3d-2-1\` (HY3D). Authoritative A/B + sweep + dispatch matrix lives at `../../world/props/ai_routes/AB_hy3d_vs_trellis2_2026_05_06.md`. Postprocess orchestrator at `../../pipelines/props/postprocess_ai_route.py`.

---

## Phase 12 Audio Deep-Dive — Stable Audio Open 1.0 GPU bake (2026-05-06 PM)

Phase 12 took the audio pipeline through the same investigation discipline as props. The plumbing was already there from Audio v3 (build chat A2) — `local_audio_open.py` adapter, `biome_ambience.py` runner, 4-layer recipe for all 10 biomes — but every output was dry-run silence. Phase 12 flipped that to real audio. Two patches surfaced; both fixes documented for reapply.

### Patch 9: `local_audio_open.py` — prefer local path over gated HF API at runtime

**Symptom:** After `huggingface-cli download stabilityai/stable-audio-open-1.0` succeeded with `HF_TOKEN` set + license accepted, the first `StableAudioPipeline.from_pretrained(model_id, ...)` call still hit the gated HF API and crashed with `GatedRepoError: 401 Client Error. Cannot access gated repo`.

**Root cause:** Diffusers' `from_pretrained` with a repo ID re-validates the gated-repo license at runtime via `hf_hub_download`. Even with the local cache fully populated, that path doesn't always pick up `HF_TOKEN` from env (depends on python session env inheritance). Different code path than the bulk download.

**Fix:** Patched `local_audio_open.py:_load_pipe()` to check for `models/diffusers/<repo_name>/model_index.json`. If present, pass that local directory path to `from_pretrained` directly — bypasses the HF API entirely. Falls back to the repo ID (which then needs HF auth) only if the local copy is missing.

This is a **reusable pattern** for any future gated-repo diffusers model: download once via the explicit `hf download` CLI (which handles auth cleanly), then load by path at runtime.

### Patch 10: `biome_ambience_large_only.json` — avoid the small-model gated repo

**Symptom:** `GatedRepoError` on `stabilityai/stable-audio-open-small` mid-bake. The recipe used `"model": "small"` for short wildlife/distant_event clips (1-2s) where the small model's 11s ceiling is sufficient. But the small model is **a separate gated repo from the large model** — accepting one license doesn't auto-grant the other.

**Root cause:** Stability AI splits Stable Audio Open into two gated repos (small vs 1.0). Each has its own license click-through. Our deployment had only accepted the large one.

**Fix:** Created `recipes/biome_ambience_large_only.json` (mirror of `biome_ambience.json` with all 22 `"model": "small"` entries → `"model": "large"`). All 50 model refs now use large. The 1.21B model is fast enough on a 5090 (~5-10s per short clip) that this isn't a real cost. Original recipe preserved at `recipes/biome_ambience.json` for forensics.

**Lesson:** Always check **all** gated repos a recipe will touch, not just the headline one. One license click is per-repo.

### Phase 12 result

Real Stable Audio Open 1.0 bake on all 10 biomes:
- **142 WAVs / 56 MB** at 44.1 kHz mono, LUFS-normalized (-28 dBFS bed_drone, -30 dBFS bed_air, -22 dBFS wildlife peak, -20 dBFS distant_event peak)
- **740.6 seconds wall-clock** for all 10 biomes (12 min) — single pipeline-load, then ~12 stems × 10 biomes amortized
- 4-layer pattern per biome: looped bed_drone + looped bed_air + Poisson wildlife oneshots + Poisson distant_event
- Loop-seam scores: most under 0.05 (tight). Outliers (lava 0.25, mana 0.26, grassland 0.41, underwater 0.15) flagged for re-bake or post-process loop-fix on follow-up

10 biomes × 4 layers + 142 individual stems = full ambience pack ready for `ambience_pack.py` → Godot export. Phase 12 closes the audio pipeline at A-grade.

The "deep-dive" bar this hit:
- 2 AI routes proven, 1 picked as default with documented rationale
- 4×4 quality sweep on the same concept → settings sweet spots known
- 6 install patches found, fixed, documented for reapply
- Workflow infra (dispatcher + batch runner + route adapter) wired so future props don't repeat the manual gate-1/gate-2 dance
- Findings worth remembering: concept-quality is the bottleneck, not model choice; geometry knobs are cheaper than texture knobs on HY3D; Trellis2 mesh gen is amortizable across N concepts
