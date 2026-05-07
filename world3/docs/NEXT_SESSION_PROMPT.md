# Next-Session Prompt

Copy/paste this as the opening message in a fresh session. It contains
the minimum context to pick up Phase A.3 without re-reading
everything. Past-session, you wrote it to yourself.

---

## Session opener (copy from here)

We're picking up world3/Phase A.3 (texture pipeline R&D).

**Project state**: world3 is a real-DEM-driven terrain generator at
`D:/assets/world3/`. Phases 0-2.5 done (MVP loop, shader stack,
biome kits, region gallery). Currently in Phase A (texture quality
+ prompt R&D).

**Read these first, in order, ~10 min total**:
1. [`world3/docs/README.md`](world3/docs/README.md) — docs index. Get oriented.
2. [`world3/docs/PLAN.md`](world3/docs/PLAN.md) — Phase A scope, A.3 task spec.
3. [`pipelines/textures/TEXTURE_RND.md`](pipelines/textures/TEXTURE_RND.md) — Part 1 (A.2 sweep findings) is the trigger for A.3.
4. [`world3/docs/DOCS_GUIDE.md`](world3/docs/DOCS_GUIDE.md) — where new findings go (most stuff goes to TEXTURE_RND or LESSONS).

**Where we left off**:
- Phase A.1 done: `pipelines/textures/experiment.py` is the sweep
  harness. Ready to use.
- Phase A.2 done: 5 materials × 3 seeds. Findings in TEXTURE_RND
  Part 1. Two clear weak materials surfaced: **snow** and
  **leaf_litter**.
- Phase A.3 *not started*: rewrite snow + leaf_litter prompts.

**A.3 plan**:
- 4 prompt variants × 3 seeds for **snow** (12 runs, ~30 min compute)
- 4 prompt variants × 3 seeds for **leaf_litter** (12 runs, ~30 min)
- Use `experiment.py --mode prompts --prompts-file <file>` for both
- Identify winning prompt patterns; update TEXTURE_RND Part 2
  (cookbook) with what works
- If a winner is dramatically better than current, regenerate the
  shipping wgv3_snow / wgv3_forest_floor textures (forest_floor is
  what plays the leaf_litter slot in our world3 textures dir)

**Snow prompt variants to test** (from TEXTURE_RND Part 2's "candidate
rewrites" notes):
1. Drop "subtle compacted ridges" cue — likely the lace generator
2. "Powder snow surface, fine crystalline detail, top-down photo"
3. "Aerial photograph of fresh snow field, even overcast lighting"
4. "Compacted snow with footprint impressions and small ice flakes,
   top-down photo, photoreal"

**Leaf litter prompt variants** (no prior notes, design fresh):
1. Current cookbook (control) — already in TEXTURE_RND
2. More minimal: "forest floor with mixed leaves and twigs, top-down
   photo"
3. Specific leaves: "fallen oak leaves and pine needles on dark soil,
   top-down photo"
4. Different lead: "ground-level photograph of autumn leaf litter,
   damp dark soil visible underneath, no plants growing, top-down view"

**Avoid seed 300** (cookbook — produced lattice failures on 4/5
materials in A.2).

**Operational**:
- ComfyUI may or may not be running on `127.0.0.1:8188`. Test:
  `curl -fsS http://127.0.0.1:8188/system_stats`. If down:
  `& "D:\assets\animators\ComfyUI\venv\Scripts\python.exe" "D:\assets\animators\ComfyUI\main.py" --listen 127.0.0.1 --port 8188`
- Experiment outputs: `D:/tmp/world3_experiments/<name>/` (contact
  sheet + manifest)
- Always set `$env:PYTHONIOENCODING="utf-8"` in PowerShell.

**Output expectations**:
- Two contact sheets (one per material) in
  `D:/tmp/world3_experiments/A3_snow_prompts/` and
  `D:/tmp/world3_experiments/A3_leaf_litter_prompts/`
- An A.3 entry in `pipelines/textures/TEXTURE_RND.md` Part 1
  documenting findings (use the A.2 entry as a template)
- Updated cookbook entries in TEXTURE_RND Part 2 if any prompt won
  decisively
- If shipping textures got regenerated: a fresh region-gallery
  capture to confirm visible improvement, archived to
  `world3/docs/captures/phase_a/<material>_after/`

**The two failure modes to avoid**:
- Don't ship a "smooth A" texture (LESSONS L16) — visually
  featureless materials pass the metric but look blank in-world.
  Eyeball the contact sheet, don't trust grade alone.
- Don't grow the doc set — A.3 findings go in existing files
  (TEXTURE_RND, LESSONS, DECISIONS for big choices). No new .md
  unless a *new lifetime class* would justify it.

**Doc-system reminder** (if you're tempted to write something new):
- Code/behavior change → update the relevant runbook + DECISIONS
  entry if architecturally meaningful
- Surprise / "the obvious thing was wrong" → LESSONS
- Sweep / experiment / prompt opinion → TEXTURE_RND
- Otherwise: DECISIONS is the safe default (append-only, broad scope)

**After A.3**:
- A.4 (settings sweep — heal_strength on lattice-prone materials)
- A.5 (external research — Reddit, ComfyUI workflows, HF spaces)
- A.6 (apply learnings; consider building a "richness" QA check from
  LESSONS L16)
- Phase A exits when first-pass success rate is qualitatively higher
  and at least one external technique has been adopted.

**Long-term direction (don't lose sight)**:
- ROADMAP v2 has phases A-F. A is texture R&D, F is multi-tile.
  Continuous/infinite world is the long-term goal; kernels and
  procedural generation deferred until basic quality is locked in.

Ask me if anything's unclear before generating. The docs system is
careful but I'd rather you ask than guess about doc placement.
