# Handoff — Character Animation Install + Validate Pass (2026-05-07 PM → next session)

> **⚠ 2026-05-07 EVENING — superseded.** This handoff captures the state at 14:45. Since then: Puppeteer installed natively on Win cu128 (NOT WSL2 as this doc predicted); AniMo proven to be training-only research code with no checkpoints (skipped, NOT installed); and **all 8 SOTA briefs (#01-#08) have been returned, sifted, and integrated into the pipeline reviews + ROADMAP.** The "33 character validation" goal of this handoff was reframed by the user as content-authoring (not pipeline work) and is **deferred**. Real pipeline gap surfaced: per-instance mesh albedo inpainting for faction insignia / damage states / variants — to be researched as brief #09 or designed from existing knowledge.
>
> **Read this instead:**
> - **[../plans/NEXT_STEPS_2026_05_07.md](../plans/NEXT_STEPS_2026_05_07.md)** — cross-cutting state after the brief sift (what installed, what's queued, what NOT to do)
> - **[../plans/ROADMAP.md](../plans/ROADMAP.md)** §"Research-calibrated findings" — per-brief outcomes
> - **[../pipeline_reviews/](../pipeline_reviews/)** — every review now has a research-calibrated section
>
> Sections below kept as historical reference for the install slog that produced the validated Puppeteer recipe in [animators/INSTALL_MATRIX.md](../../animators/INSTALL_MATRIX.md).

---

You are picking up a multi-day asset-pipeline project mid-flow. **Don't restart from scratch — read the references and continue the existing plan.**

## What this session is for

Execute the action plan from research brief #01 (characters / animation). Specifically:

1. **Forensics** — recover the bad-run config that produced "trash" character animations
2. **Install AniMo** (native Windows; CVPR '25 text-conditioned animal motion, 114 species)
3. **Install Puppeteer** (WSL2; NeurIPS '25 single-repo rig+animate)
4. **Validate the canonical animation chain** on 3 characters: 1 humanoid (goblin), 1 clean quadruped, 1 OOD creature (sandworm or tentacle_horror)
5. **Build the Blender CI linter** (~100 lines) for static-frame + foot-skating detection
6. **Continue dispatching SOTA research briefs** as we go (briefs 02-08 are pre-written and ready)
7. **Update all relevant docs** as findings come in

The 33-character roster is **likely production content** (not throwaway like every other lane). The user wants this lane done right.

## Critical context (read these first, in order)

1. **[`docs/audits/AUDIT_2026_05_07_post_nuke.md`](../audits/AUDIT_2026_05_07_post_nuke.md)** — full project state as of 2026-05-07
2. **[`docs/pipeline_reviews/README.md`](../pipeline_reviews/README.md)** — index of 7 manual reviews + the canonical reframe ("pipelines real, content placeholder")
3. **[`docs/pipeline_reviews/06_characters.md`](../pipeline_reviews/06_characters.md)** — full character lane review with research-calibrated chain
4. **[`docs/research_briefs/2026_05_07_sota_survey/01_characters_animation.response.md`](../research_briefs/2026_05_07_sota_survey/01_characters_animation.response.md)** — the research findings driving this work
5. **[`animators/INSTALL_MATRIX.md`](../../animators/INSTALL_MATRIX.md)** — install recipes for all 13 animator tools (12 validated + 2 planned: Puppeteer, AniMo)
6. **[`WORKFLOWS.md` §1](../../WORKFLOWS.md)** — canonical Character chain with Path A (humanoid) + Path B (non-humanoid)
7. **[`docs/plans/ROADMAP.md`](../plans/ROADMAP.md)** — current focus + research-calibrated findings + action items

## Hardware target (don't deviate)

- **GPU:** RTX 5090 Laptop, 24 GB VRAM, Blackwell sm_120 — needs CUDA 12.8+ / torch ≥ 2.7 for native CUDA
- **OS:** Windows 11; default to native Windows venvs at Python 3.11 or 3.12
- **WSL2:** acceptable when forced (Linux-only deps); already used for AnimateAnyMesh in some prior workflows
- **Disk:** D:\ drive has ~344 GB free; budget per new venv is ~3-5 GB (torch+cu128 alone is 3.3 GB)

## Established patterns to follow (don't relitigate)

These were decided over the last 24h. Don't second-guess unless you find evidence otherwise:

1. **Always research before installing.** Read README + GitHub issues + check for prebuilt wheels matching `(torch_version, cuda_version, python_version, OS)`. The kaolin install was thought to need 1-3h source-build until I found prebuilt Blackwell wheels — was actually 30 min.
2. **Override stale README pins** when they predate Blackwell. `torch==2.7.0+cu128` is the floor for sm_120 support; many repos pin `torch==2.4.x` or `cu118` which won't work on this hardware.
3. **Native Windows install path strongly preferred.** WSL2 only when forced.
4. **`bpy` 4.4.0** for Python 3.11/3.12 (5.0+ broke `Action.fcurves` legacy API used by AnimateAnyMesh / Anytop).
5. **For DLL load order:** import torch *before* bpy on Windows (bpy needs torch's MSVC runtime DLLs preloaded).
6. **Validation bar:** "does the README quickstart produce a real artifact?" Not just "do imports work." Run the demo end-to-end against actual model weights.

## Memory file you should already have loaded

The user-memory at `C:\Users\josep\.claude\projects\d--assets\memory\MEMORY.md` includes:
- Research before installing (saved 2026-05-07 from this session)
- D: drive space constraint
- Quality over coverage
- Write tool encoding gotcha (UTF-16 on Windows, use Python helper for JSON/UTF-8)
- Regional DEM STAC unlock

## Background workers — don't disturb

Other chat sessions are running concurrently:

- **Worldgen worker** in `world3/` — rebuilding scene-composition pipeline. Don't poke `world3/`.
- **Texture worker** in `pipelines/textures/` + `world/textures/library/` — improving tileable texture quality. Don't poke either path.

If you see broken markdown links in `world3/docs/*` or `pipelines/textures/*.md`, **leave them** — those are worker-managed.

## Action plan (in priority order)

### A. Forensics — recover bad-run config

Read `D:/assets/meshy/batch_logs/` to figure out what command + prompt + source mesh produced each of the 5 baked animations:

- `goblin_attack`, `goblin_walk_left`, `goblin_walk_right`
- `witch_chant`
- `bone_construct_attack`

Specifically need to know:
- Was the source mesh **rigged before** AnimateAnyMesh ran, or raw preprocessed mesh?
- What was the exact `--prompt`?
- What `--seed` and `--num_traj`?
- Confirms the hypothesis that "wrong tool" + "thin prompt" is the failure, not pipeline broken.

Save findings to `docs/pipeline_reviews/06_characters.md` under a new "Forensic recovery" section.

### B. Install AniMo (native Windows, ~30 min)

Source: [github.com/WandererXX/AniMo](https://github.com/WandererXX/AniMo) — CVPR '25, text-conditioned animal motion, 114 species, AniMo4D dataset.

```powershell
cd D:\assets\animators
git clone https://github.com/WandererXX/AniMo.git
cd AniMo
# Read README first; their conda env is upstream-recommended but py3.11 venv may work too
& "C:\Program Files\Python311\python.exe" -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
# Install upstream requirements (read carefully for torch pin; override to 2.7.0+cu128 if needed)
.\venv\Scripts\python.exe -m pip install -r requirements.txt
# If torch pin is stale:
.\venv\Scripts\python.exe -m pip install torch==2.7.0 torchvision --index-url https://download.pytorch.org/whl/cu128
# Download model checkpoints per upstream README
```

Smoke test: pick a quadruped concept (cat? dog? horse?) and run inference with a text prompt like `"a cat stalking, low to ground"`. Confirm BVH/FBX output.

Update `animators/INSTALL_MATRIX.md` AniMo section from ⏳ to ✅ when validated.

### C. Install Puppeteer (WSL2, 2-4h compile pain budget)

Source: [github.com/Seed3D/Puppeteer](https://github.com/Seed3D/Puppeteer) — NeurIPS '25 spotlight, single-repo rig+animate with video-guided mode.

**Defer until A and B done.** Upstream pins:
- Python 3.10.13
- PyTorch 2.1.1 + CUDA 11.8
- flash-attn 2.x + pytorch3d + torch-scatter

Native Windows on Blackwell sm_120 = 2-4h compile pain. **WSL2 with upstream conda env is the safer path.**

```bash
# In WSL2
conda env create -f environment.yml
conda activate puppeteer
# Their CUDA 11.8 wheels work as-is in WSL
# Smoke test: rig + animate a sample mesh
```

Update `animators/INSTALL_MATRIX.md` Puppeteer section.

### D. Validate canonical chain on 3 characters

Per `WORKFLOWS.md §1`. Pick:
- **Goblin** (humanoid) — Path A: SkinTokens → Hunyuan-Motion → retarget
- **Hellhound** or **giant_spider** (clean quadruped) — Path B with AniMo
- **Sandworm** or **tentacle_horror** (OOD) — Path B with AnyTop

For each:
1. Rig
2. Animate (3 actions per character: idle, walk, attack)
3. Blender retarget if rigger ≠ animator skeleton
4. Sprite-bake (8 angles × 16 frames)
5. **Visual verification** — open the resulting MP4 turnaround in a video player. **Don't claim success without seeing the animation move.**

Save outputs to `meshy/output/<char>/animations/<action>.fbx` + `meshy/sprites/<char>/<action>/sheet.png`.

### E. Build Blender CI linter (~100 lines)

Per research brief #01 Q5. Create `meshy/animation_linter.py`:

```python
# 1. Static-frame detection (~10 lines)
#    Sum per-bone rotation deltas across clip. < threshold = "didn't move" → fail.
# 2. Foot-skate detection (~50 lines, Kovar/Schreiner '02)
#    Sample foot-bone world xy each frame.
#    Detect "in contact" frames (foot-z below threshold).
#    Flag frames where xy delta > epsilon while in-contact.
#    > 5% skate-frames = fail.
# 3. (Optional) FVMD aggregate via pip install
#    Note: lit warns FMD-family does NOT reliably catch foot-skate
#    so it's a complement, not a replacement, for #2.
```

Run as a CI gate after every batched animation. Failing FBXs go to a quarantine dir for manual review.

### F. Continue dispatching SOTA briefs

Briefs 02-08 are pre-written at `docs/research_briefs/2026_05_07_sota_survey/`. The user dispatches them one at a time to a research agent. When responses come back, you update the relevant docs the same way you did for #01:

- Pipeline review (`docs/pipeline_reviews/0N_<lane>.md`)
- INSTALL_MATRIX (if new tools)
- Per-lane README in the relevant subdir
- WORKFLOWS.md if the canonical recipe changes
- ROADMAP "Research-calibrated findings" section
- pipeline_reviews/README.md index

Suggested order (per index):
- **02 Textures** — newly active; covers tileable + mesh-driven hero terrain (MaterialAnything retrofit)
- **03 Props** — image-to-3D 2026 SOTA beyond Trellis2
- **04 VFX 3D bake** — GPU plan refresh
- **05 VFX shaders** — better than LLM-mutation framework?
- **06 Audio** — re-bake path after archive
- **07 UI / Icons** — faction LoRA + hero icons
- **08 Game Data** — ML-driven balance tooling

User dispatch prompt template:
```
Read D:/assets/docs/research_briefs/2026_05_07_sota_survey/<NN>_<topic>.md and complete the research it requests. Save your response as <NN>_<topic>.response.md in the same folder.
```

## Tool inventory shortcut

13 animator tools, 12 install-validated end-to-end on RTX 5090 / Win11 as of 2026-05-07:

✅ ComfyUI, ComfyUI_HY3D, Trellis2, hy-motion-fbx-exporter, SkinTokens, AnimateAnyMesh (demoted to ambient-only), Anytop (Windows-ported), RigAnything, MagicArticulate, mesa-repo, MaterialAnything, mesh2motion-app, mesa-env

⏳ Puppeteer, AniMo (this session installs them)

For exact recipes per tool: [`animators/INSTALL_MATRIX.md`](../../animators/INSTALL_MATRIX.md).

## What NOT to do

- **Don't fan out to all 33 characters until canonical chain is validated on 3.** Producing 33 trash FBXs is the failure mode we're explicitly avoiding.
- **Don't reinstall the 12 working tools.** They're validated and stable.
- **Don't archive AnimateAnyMesh outputs.** They're forensic evidence for understanding what went wrong.
- **Don't touch worker-managed dirs** (`world3/`, `pipelines/textures/`, `world/textures/library/`).
- **Don't trust requirements.txt torch pins blindly** — most repos pin pre-Blackwell torch. Override to 2.7.0+cu128 unless the README specifically mentions Blackwell.
- **Don't add new pipelines.** This session is install + validate + linter, not "build new things."
- **Don't claim animation success without playing the MP4.** "Imports work" ≠ "animation looks right."

## Project framing (the canonical reframe — internalize this)

> "Honestly nothing was hand-authored, all just kind of made without review. We proved it works, we will want to make sure it works well on our next pass. Honestly this is most likely the direction every pipeline and workflow will go." — user, 2026-05-07

Across 7 reviewed pipelines, the pattern is identical: pipeline plumbing real, first-pass content throwaway. **The character lane is the exception** — those 33 will likely be production content. So getting the animation step right matters here in a way it doesn't elsewhere.

## Doc state checkpoint

Last updated 2026-05-07 PM:
- 6 root pillar docs (README, DOCS_INDEX, PIPELINE_DIRECTORY, PIPELINE_GUIDE, TOOLS_INDEX, WORKFLOWS) — current
- `docs/pipeline_reviews/01-07_*.md` — 7 of 8 done; #02 textures deferred (worker active) but research brief is now active
- `docs/research_briefs/2026_05_07_sota_survey/` — 8 briefs written; #01 returned + integrated; #02-08 pending dispatch
- `animators/INSTALL_MATRIX.md` — 13 tools, 12 validated, 2 planned (Puppeteer, AniMo)
- 0 broken links in our docs (5 in worker-managed files, ignore those)

## First action when you start

```
Read D:/assets/docs/handoffs/HANDOFF_2026_05_07_pm_characters_animation_install.md (this file)
Then read the 7 references in "Critical context" above
Then start with action A (forensics)
```

## What success looks like at the end of this session

- AniMo installed, validated, and producing real animal motion output on a quadruped
- Puppeteer installed in WSL2 (or path documented if blocked)
- 3 characters validated through the canonical chain with playable MP4 turnarounds
- Blender CI linter built and committed
- Bad-run forensics documented (so we know *why* the first pass failed)
- 1-2 more SOTA briefs dispatched + integrated as user has time
- All docs updated to reflect what was done

The 33-character animation fanout is **not** a goal of this session — that comes after validation.

---

**Hardware:** RTX 5090 Laptop, 24 GB VRAM, Blackwell sm_120, Windows 11.
**Project root:** `D:\assets\`
**Today's date:** Whatever it is when you start; today's notes are dated 2026-05-07.
