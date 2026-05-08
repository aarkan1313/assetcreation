# Characters — Manual Review (2026-05-07)

`meshy/` lane (orchestrator) + `animators/` (rigging/animation tools). **The lane the user has actually engaged with.** Different review character: this lane has been hand-iterated on, multiple times. Real verdict already exists in `docs/audits/REVIEW.md` from 2026-05-05.

## Inventory (truth from disk)

### Raw outputs (`meshy/output/`)

**33 character GLBs** (~14-26 MB each, 350k-740k tris) from Meshy image-to-3D:

```
assassin, bog_corpse, bone_construct, bone_priest, centipede, crab,
crystal_cluster, dark_knight, eye_horror, gargoyle, ghoul, giant_spider,
goblin, hellhound, imp, moth_horror, mummy, mummy_classic, myconid,
necromancer, ogre, pirate_ghost, reaper, red_priest, sandworm,
screaming_corpse, skeleton, tar_lich, tattooed_warrior, tentacle_horror,
viking, wendigo, witch
```

Each `<char>/` has `model.glb` (the raw Meshy output) + `task.json` (Meshy API response with prompt + URL + provenance).

### Preprocessed (`meshy/preprocessed/`)

**33 GLBs** with `_p` suffix, decimated to **~30k tris each**:

| Character | Raw | Preprocessed | Reduction |
|---|---|---|---|
| goblin | 360,782 tris | 29,998 | **8.3%** |
| witch | 743,934 tris | 30,000 | **4.0%** |
| reaper | 658,519 tris | 29,999 | **4.6%** |
| dark_knight | 526,508 tris | 29,997 | **5.7%** |

**Batch summary:** 30 successes, 0 failures, **406 seconds total** for the preprocess pass. The decimation pipeline is reproducible and fast.

This solves the real Meshy problem: you ask for 30k tris, Meshy gives you 350k+. `preprocess.py` brings it down to spec while preserving silhouette + UVs.

### Animations baked (`animators/AnimateAnyMesh/output_videos/`)

**5 named animations** as FBX + MP4:

- `bone_construct_attack`
- `goblin_attack`
- `goblin_walk_left`
- `goblin_walk_right`
- `witch_chant`

Plus `dragon` (the Anytop install validation from earlier).

This proves the AnimateAnyMesh integration end-to-end — text prompt → mesh deformation → exported FBX with shape-key animation.

### Sprite sheets (`meshy/sprites/`)

**11 sprite sheet bakes** from the animation FBXs:

- `bone_construct_attack` (+ `_pix` pixel-art variant)
- `goblin` (base + animations: `goblin_attack`, `goblin_walk_left`, `goblin_walk_right`)
- `goblin_v2` (rebaked)
- `witch_chant`
- All have a `_pix` pixel-art variant alongside

**Goblin sheet stats:** 6816×3344 RGBA, 128 frames (8 angles × 16 frames). That's a real production-quality sprite sheet.

Each sprite dir has:
- `sheet.png` (full sheet) + `sheet_pix.png` (pixel art variant)
- `sheet.json` (frame metadata)
- `manifest.json`
- `angle_000/`, `angle_045/`, ..., `angle_315/` (8-angle source frames)

### Rigging (sample runs)

`animators/RigAnything/outputs/` has 3 rigged GLBs from real runs:

- `model_p_simplified_rig.glb`
- `witch_p_simplified_rig.glb`
- `spyro_the_dragon_simplified_rig.glb` (from yesterday's install validation)

These use the preprocessed `_p` versions as input.

### Mixamo ready (`meshy/mixamo_ready/`)

**3 FBXs** ready for Mixamo upload: `goblin.fbx`, `witch.fbx`, `hellhound.fbx`. Format conversion verified.

### Animator venv readiness (from yesterday's install pass)

All 13 animator tools install-validated 2026-05-07 (see `animators/INSTALL_MATRIX.md`):

- ✅ Pre-existing & proven: ComfyUI, ComfyUI_HY3D, Trellis2, SkinTokens, MaterialAnything, hy-motion-fbx-exporter, mesh2motion-app
- ✅ Hand-validated yesterday: AnimateAnyMesh, Anytop, RigAnything, MagicArticulate, mesa-repo
- All pass smoke test producing real artifacts

## What works

- ✅ **Full pipeline end-to-end on multiple characters.** This is the only lane where the chain `concept → 3D → preprocess → rig → animate → export` has been completed for real assets.
- ✅ **Preprocess pipeline solves a real problem.** Meshy ignores polycount config; preprocess brings 350k-740k tris down to ~30k consistently. **30/30 preprocess success rate, 406s wall-clock total.**
- ✅ **Sprite sheet bake is production-quality.** 8 angles × 16 frames = 128 frame sprite sheets with pixel-art variants. The `meshy/sprites/goblin/` output is a real game asset.
- ✅ **Animation pipeline proven** on 5 named animations (3 different actions + walk_left/right variants).
- ✅ **Multiple rigging routes validated.** RigAnything has 3 rigged GLB outputs on disk, MagicArticulate has 6 example skeletons, SkinTokens pre-existing, Mesh2Motion build verified, Mixamo path proven (3 FBXs ready).
- ✅ **Format conversion works.** GLB → FBX → Mixamo upload is real.
- ✅ **Quality discipline already established.** [REVIEW.md](../audits/REVIEW.md) from 2026-05-05 documents bugs found, fixes applied, tool comparison. **The depth standard for the rest of the project.**
- ✅ **Provenance per character.** `task.json` has the Meshy API task ID, prompt, timestamps, URL, status. Reproducible.

## What's open / weak

1. **Most of the 33 characters haven't been animated.** Only ~5 have animations baked: goblin (3 actions), witch (chant), bone_construct (attack). The other 28 are static GLBs + preprocessed but not put through the animation pipeline.
2. **Most haven't been rigged.** Only 3 have rigged outputs (goblin's preprocessed version, witch's preprocessed, dragon test). 30/33 characters are untouched by the rigger lane.
3. **Sprite sheets exist for ~3 characters.** Same gap — animation + sprite bake is per-character work that hasn't been fanned out.
4. **No unified "render this character into Godot" recipe** — preprocess outputs are flat at `meshy/preprocessed/<name>_p.glb`, not in a Godot project drop-in shape. The path to Godot is implicit (drag the GLB in), but no `meshy/godot/` analog to `world/props/godot/`.
5. **Variation testing limited.** Only goblin has multiple animations (attack + walk_left + walk_right). Witch has one (chant). Bone_construct has one (attack). **The sprite system can produce 8-angle × 16-frame walk + idle + attack + chant per character — we haven't actually fanned that out.**
6. **No batch-animate run on the full 33-character roster.** The infrastructure is ready (`batch_animate.py` exists). It just hasn't been pointed at "give me walk + idle + attack for all 33 characters."

## User verdict (2026-05-07)

1. **Roster:** "this was a test like everything else. **HOWEVER, these will most likely be production content.**" Different from every other pipeline — characters are the one lane where the throwaway-content reframe might not apply. The 33 will likely survive into the actual game.
2. **Goblin status:** "**I haven't gotten to view any animations/sprite sheets of anyone, do we have fully viewable animations for any that I can play in Blender?**" — goblin is NOT proven to user yet. Will answer below.
3. **Default rigger:** "need to review them all most likely" — defer the rigger-selection question; we have tools, no default chosen yet, multiple options need head-to-head per character type.
4. **Sprite atlas size:** "not sure" — sprite-sheet quality for production is unconfirmed.

**Critical implication of #2:** all the work the pipeline produced (5 animations, 11 sprite sheets, 3 rigged GLBs) **has not actually been validated by the user.** That's a real gap — every other pipeline was at least sampled (audio listened to, props eyeballed, icons opened). Characters is the most-built lane and the *least viewed*.

## Playable animations on disk (answer to user Q2)

**8 binary FBXs** in `animators/AnimateAnyMesh/output_videos/rf_model/`, ~10-11 MB each, valid `Kaydara FBX Binary` format — these import directly into Blender:

| File | Size | What |
|---|---|---|
| `goblin.fbx` | 10.4 MB | base goblin (no animation, just mesh) |
| `goblin_attack.fbx` | 10.3 MB | goblin attacking |
| `goblin_walk_left.fbx` | 10.2 MB | goblin walking left |
| `goblin_walk_right.fbx` | 10.2 MB | goblin walking right |
| `witch_chant.fbx` | 9.9 MB | witch chanting |
| `bone_construct_attack.fbx` | 10.9 MB | bone_construct attacking |
| `dragon.fbx` | 3.7 MB | dragon flying (Anytop install validation) |
| `examples/dragon.fbx` | 3.7 MB | duplicate dragon (path bug from AnimateAnyMesh's render.py) |

**7 MP4 turnaround previews** alongside, 200-420 KB each — playable in any video player without Blender.

**1 BVH** at `animators/Anytop/save/flying_model_dataset_truebones_bs_16_latentdim_128/samples_*/Bat_rep_0_#0.bvh` (Bat skeleton motion from the Anytop install validation).

**11 sprite sheets** in `meshy/sprites/` — static PNGs. The bigger ones:

| Sheet | Size | Notes |
|---|---|---|
| `goblin/sheet.png` | 8.8 MB, 6816×3344 | 8 angles × 16 frames, full base goblin |
| `goblin_v2/sheet.png` | 8.8 MB | rebake |
| `bone_construct_attack/sheet.png` | 6.4 MB | attack animation 8 angles |
| `goblin_pix/sheet.png` | 0.8 MB | pixel-art variant |
| `witch_chant/sheet.png` | 0.6 MB | witch chant 8 angles |

### Recommended viewing order

**Fastest path** (no Blender needed): play these MP4s in any video player (Windows Media Player, VLC, browser):
- `output_videos/rf_model/goblin_attack_azi0_ele0.mp4` (340 KB)
- `output_videos/rf_model/witch_chant_azi0_ele0.mp4` (260 KB)
- `output_videos/rf_model/bone_construct_attack_azi0_ele0.mp4` (420 KB)

**For real validation** (Blender):
- File → Import → FBX → `output_videos/rf_model/goblin_attack.fbx`
- Should load with shape-key animation. Press play in the timeline.

**For sprite sheet check** (any image viewer):
- Open `meshy/sprites/goblin/sheet.png` (8.8 MB, 6816×3344). Should see 8 rows of 16 frames each, character at different angles.

## User animation verdict (2026-05-07)

After playing the MP4s:

> "from what I can tell those animations are trash, most do nothing or are like slightly moving their head. BUT that doesn't mean we should try again, we don't know run conditions, how the skeleton/rigging was, if it needed rigging, how the prompting was, settings etc"

**Key distinction:** this is "trash but inconclusive," not "trash so archive it." The animations are bad; whether the *pipeline* is bad is unknown. We have no answer to:

1. **Was the input mesh rigged before AnimateAnyMesh ran?** (Looking at the goblin FBXs, AnimateAnyMesh uses shape-keys not bone rigs — but if the source mesh wasn't rigged, the model has nothing to deform around. The chain `meshy → preprocess → AnimateAnyMesh` may have skipped a required `meshy → preprocess → SkinTokens/RigAnything → AnimateAnyMesh` step.)
2. **What was the prompt?** AnimateAnyMesh demos use `--prompt "The object is flying"`. If our prompts were generic ("attack", "chant") that's much weaker than what the model needs.
3. **Were settings tuned?** Defaults (`--seed 666`, `--num_traj` default) vs the README's "try 3 prompt/seed combos per example" guidance.
4. **Was AnimateAnyMesh the right tool?** Maybe these characters needed `hy-motion-fbx-exporter` (text → motion → retarget to Mixamo skeleton — different abstraction) or Mixamo direct.
5. **Was the source mesh prepared correctly?** Static-mesh-only is required; if there were vertex issues from Meshy → preprocess, the trajectories had nothing clean to act on.

**Pipeline test status:** **inconclusive.** We have a known-broken output from an unknown configuration. **The pipeline isn't proven OR disproven.**

This is different from every other pipeline review. The audio bake was conclusively bad output from a documented run. The character animations are bad output from a *partially-documented* run, and the documentation gap is exactly the missing piece needed to know if it's a pipeline problem or a configuration problem.

## Action items from this verdict

1. **Don't archive the bad FBXs yet.** They're forensic evidence. Need to know: were these from rigged or unrigged source meshes? Were skeleton tools (SkinTokens/RigAnything) run first or skipped?
2. **Document the actual run config used for each animation.** `meshy/batch_logs/` has `goblin_attack.log` etc — read those to recover the actual command + settings + source mesh.
3. **Decide on the canonical pipeline path** for character animation. Right now there are 3 valid paths:
   - **Shape-key only** (AnimateAnyMesh on a static mesh — what we did, gave us bad output)
   - **Skeletal animation** (SkinTokens/RigAnything to rig → hy-motion-fbx-exporter or Mixamo to animate)
   - **Manual** (Mesh2Motion app browser UI, applies pre-built rigs to the mesh)
4. **The character roster is going to be production content** — meaning getting this pipeline right is **critical**, not "nice to have." This deserves a focused proper-run pass, ideally with one character (probably goblin since it has the most artifacts already) tested through all 3 paths to compare.
5. **No batch animation across 33 characters until the canonical path is proven** — would just produce 33 trash FBXs.

## Research-calibrated 2026-05-07 PM (SOTA brief #01 response)

Full response: [`docs/research_briefs/2026_05_07_sota_survey/01_characters_animation.response.md`](../research_briefs/2026_05_07_sota_survey/01_characters_animation.response.md). Headline findings:

### AnimateAnyMesh is reclassified, not "broken"

It's a 4D mesh-deformation foundation model trained on **short, low-displacement deformations** — head turns, breathing, fabric ripples. It's not a substitute for skeletal animation. **Our "trash" output is tool-misuse**, not a model bug. **Demote to "ambient mesh wiggle"** — idle breathing, plant sway, tentacle ripple on otherwise-static decoration. Layer additively as secondary motion on top of a real skeletal animation.

### Canonical 2026 indie chain (decided)

**Rig-first → skeletal animation by topology → Blender retarget. Shape-keys only as decoration.**

#### Path A — Humanoid (~10 of 33)
1. Mesh (already preprocessed to 30k tris)
2. **Rig:** SkinTokens (we have it) → FBX with skeleton + skin weights, ~30s
3. **Animate:** Hunyuan-Motion text prompt (we have it) → BVH/FBX in SMPL-H or Mixamo skeleton, ~10s
4. **Retarget:** Blender bpy / Mixamo Auto-Rigger / Make-It-Animatable → animated FBX
5. Optional foot-locking pass

Total ~1-2 min/humanoid/clip.

#### Path B — Non-humanoid (~23 of 33)
1. Mesh
2. **Rig:** RigAnything for unusual topologies, SkinTokens for clean quadrupeds → FBX with skeleton + skin
3. **Animate, by sub-type:**
   - **Quadruped/insect/biped-non-humanoid** (text-conditioned) → **AniMo** (CVPR '25, 114 species, code released, conda env provided) → BVH on AniMo skeleton → retarget
   - **Out-of-distribution** (sandworm, tentacle, six-legs) → **AnyTop** specialized model, unconditional sample, curate
   - **Hard cases / video-driven** → **Puppeteer** (NeurIPS '25 spotlight, end-to-end rig+animate with video-guided mode)
4. Cleanup pass for legged creatures

Total ~2-5 min/non-humanoid/clip plus AnyTop curation overhead.

### Two real new installs to add

| Tool | Status today | Why install |
|---|---|---|
| **Puppeteer** ([github](https://github.com/Seed3D/Puppeteer)) | Not installed | NeurIPS '25 spotlight; single-repo rig-and-animate with video-guided mode. **WSL2 expected install** — flash-attn 2.x + pytorch3d + torch-scatter on Blackwell sm_120 = 2-4 hours of compile pain natively. |
| **AniMo** ([github](https://github.com/WandererXX/AniMo)) | Not installed | CVPR '25, text-conditioned animal motion, 114 species, AniMo4D dataset (78k seqs, 185k captions). Conda env released. Native Windows plausible. **Closes the AnyTop text-conditioning gap.** |

### Watch list (no usable code yet — defer)

- **UniMoGen** (arXiv:2505.21837) — UNet-diffusion, skeleton-agnostic, 250× fewer inference steps than MDM. No public code 2026-05.
- **X-MoGen** (arXiv:2508.05162) — first unified human+animal text-conditioned model, UniMo4D dataset. No public code.
- **OmniZoo / "Topology-Agnostic Animal Motion"** (arXiv:2512.10352, Dec 2025) — 140 species, autoregressive on arbitrary topologies. Code/dataset not yet public.
- **SPRig** (arXiv:2602.12740) — temporal-consistency self-supervision wrapper on top of UniRig/RigAnything/SkinTokens. Install only if jitter shows up at the rigging stage.

### Tools we can stop investing in

- **AnimateAnyMesh** for character action — wrong tool. Keep installed for ambient-deformation use case only.
- "Specialized creature animator" SaaS — doesn't exist in 2026 for snakes/spiders/dragons. Production answer is **procedural IK in the runtime engine**, which doesn't apply to our sprite-bake pipeline.
- "AI animator wrapper" that auto-decides rigging vs shape-key — doesn't exist. Puppeteer is the closest but commits to "rig + skeletal" as the One True Path.

### Animation review tooling

**No 2026 turnkey exists.** Build a 100-line Blender CI linter:

1. **Static-frame detection** (10 lines): sum of per-bone rotation deltas across clip < threshold = "didn't move." Catches the exact "barely moves their head" failure mode.
2. **Foot-skating** (50 lines, per Kovar/Schreiner '02): sample foot-bone world-space xy each frame; flag frames where xy delta > epsilon while foot-z below threshold; > 5% skate-frames = fail.
3. **FVMD** ([pip-installable](https://github.com/DSL-Lab/FVMD-frechet-video-motion-distance)) for over-smoothing detection. **Lit warns FMD-family does NOT reliably catch foot-skate intensity** — that's why we still need the manual linter for foot-skate.

This is a one-afternoon job and turns into a CI gate after every batched animation.

### Sprite-sheet baking

**Lateral.** Stay on Blender headless EEVEE-Next; no 2026 tool beats it for our scale. Gains are in **parallelization** (`-P 4` across the 5090's wells), not tooling. Pattern: one `blender --background --python script.py` per character; parallel via PowerShell `ForEach-Object -Parallel`. 33 chars × 8 dirs × 16 frames = 4,224 frames; at ~200ms/frame = 14 min/character.

### Video-to-motion (only if you want it)

**Not required**, but if mocap-from-video ever becomes useful: **GVHMR + GMR (ICRA '26)** is the 2026 stack. SMPL-X from monocular video → real-time retarget to humanoid skeleton. MIT-style licenses, Windows-buildable. Skip until there's a specific use case.

## Updated pipeline-level read (2026-05-07 PM)

- **State:** mesh ingestion + preprocess + sprite-bake **proven**. Animation step had **wrong tool selected** — AnimateAnyMesh isn't a skeletal animator. Pipeline is not broken; the recipe was wrong.
- **Strongest part still:** preprocess + sprite-bake chain. 30/30 success, 13.5s/character avg, scales linearly with parallelization.
- **Weakest part:** animation tooling **gap is identified, fillable** — install Puppeteer (WSL2) + AniMo (Win), build the linter, validate on 1 humanoid + 1 non-humanoid before fanout.
- **What "shipping quality" requires (refined):**
  - Recover bad-run config from `meshy/batch_logs/` (forensics)
  - Install Puppeteer + AniMo
  - Validate Path A on goblin (humanoid → SkinTokens → Hunyuan-Motion → retarget)
  - Validate Path B on a quadruped (RigAnything → AniMo) and an OOD creature (RigAnything → AnyTop)
  - Build the Blender linter
  - Then fan out to all 33 characters with confidence

## Concrete next moves (research-calibrated)

In priority order (from the research response):

1. **Recover bad-run config first** — read `meshy/batch_logs/*.log` and `animators/AnimateAnyMesh/output_videos/`. ~15 min. Forensics.
2. **Install AniMo** native Windows — quick conda env, validated. Unblocks text-conditioned animal motion. ~30 min.
3. **Install Puppeteer** in WSL2 — accept install pain once. Single-tool rig+animate fallback. ~2-4 hours including Linux sm_120 build pain.
4. **Pick validators**: 1 humanoid (goblin) + 1 quadruped (hellhound?) + 1 OOD (sandworm? tentacle_horror?). Run all 3 paths.
5. **Write the animation linter** (Q5 from response). Even before fanout — gives us a numeric quality bar.
6. **Defer**: GVHMR+GMR (only if video mocap), SPRig (only if jitter), OmniZoo/X-MoGen/UniMoGen (wait for code).

## Pipeline-level read

- **State:** **most-built pipeline, most-uncertain animation step.** Mesh ingestion + preprocess + sprite-sheet bake all work cleanly. Animation step produced bad output from undocumented config.
- **Strongest part:** **the preprocess + sprite bake chain.** 30k-tri decimation is reproducible across 30 characters at 13.5s/character. Sprite bake produces real 8-angle × 16-frame sheets.
- **Weakest part:** **animation step is uncalibrated.** Bad output, unknown if pipeline issue, configuration issue, or wrong-tool-choice. Cannot iterate without recovering run config.
- **What "shipping quality" would require:**
  - Recover the run configurations from `meshy/batch_logs/`
  - Decide canonical animation path (shape-key vs skeletal vs manual rig)
  - Single-character validation through that canonical path before fanout
  - Then: per-character animation set (idle/walk/attack/hurt/death for melee, etc.)
  - Sprite-bake the results
  - Sprite size budget reality check (6816×3344 × 33 ≈ 7.5 GB — likely needs pixel-art-only for memory)

## Concrete next moves

1. **CRITICAL: read `meshy/batch_logs/*.log` and recover the animation run config.** What command, what prompts, what source mesh, was it rigged. Without this we can't iterate the animation pipeline.
2. **Once config is known, decide the canonical animation path.** Three options on disk: AnimateAnyMesh shape-keys (what was tried, may be wrong tool), SkinTokens-then-animate (skeletal), Mixamo-via-Mesh2Motion (manual rig + library).
3. **Single-character validation through the chosen path** before any batch run. Probably goblin since it's the most-iterated already.
4. **NO batch animation across 33 characters** until the canonical path is validated. Would just produce 33 trash FBXs.
5. **Documentation gap:** no `meshy/README.md`. The most complete + most uncertain lane is also the least documented. Fix this when the canonical path lands.

**Reframe:** the user's first read ("31 out of 33 are basically untouched") becomes more nuanced once we recognize the animation step itself is unproven. The right move is *not* "fan out the existing pipeline" but "fix the animation step first." Mesh ingestion + sprite sheet bake — those parts can scale. Animation needs a real validation before it scales.
