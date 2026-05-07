# Next-Session Prompt

Copy/paste this as the opening message in a fresh session. It contains
the minimum context to pick up where the last session left off,
without re-reading everything. Past-session, you wrote it to yourself.

---

## Session opener (copy from here)

We just finished **Phase A** (texture quality + prompt R&D) on world3.
The next iteration hasn't been picked yet — `PLAN.md` lists 4 candidate
options, ranked by scope. I want to pick one and start.

**Project state**: world3 is a real-DEM-driven terrain generator at
`D:/assets/world3/`. Phases 0-2.5 done (MVP loop, shader stack,
biome kits, region gallery). Phase A just closed:
- Reproducible experiment harness in `pipelines/textures/experiment.py`
- 4 weak shipping textures regenerated to grade A (snow,
  forest_floor, tundra_ice, desert_canyon_rock)
- The directional-cue rule documented across 3 materials (anatomy
  rule promoted from anti-pattern)
- `pipelines/textures/EXTERNAL_TECHNIQUES.md` survey of the open-
  source state of the art
- 5 LESSONS entries (L17 algorithm canonical, L18 klein cfg=1
  negatives, L19 concurrent-runs race)

**Read these first, in order, ~10 min total**:
1. [`world3/docs/README.md`](world3/docs/README.md) — docs index. Get oriented.
2. [`world3/docs/PLAN.md`](world3/docs/PLAN.md) — current iteration is "between iterations"; lists 4 options.
3. [`world3/docs/ROADMAP.md`](world3/docs/ROADMAP.md) — Phase A is DONE; Phase B (upscaling) is NEXT per the roadmap.
4. [`world3/docs/PLAN_phaseA_archived.md`](world3/docs/PLAN_phaseA_archived.md) — what we just finished, with the OpenTopo addendum at the bottom.
5. [`world3/docs/DOCS_GUIDE.md`](world3/docs/DOCS_GUIDE.md) — where new findings go.

**Open candidate options** (full details in PLAN.md):
1. **Phase A.7** — build "richness" QA metric (small, half-session,
   addresses confirmed smooth-A failures)
2. **Phase B** — upscaling research (medium, what ROADMAP says next)
3. **OpenTopo branch** — HD review + 4-call USGS1m fetch (medium-
   large, planning docs already exist)
4. **Variation-and-stitch tool** — `variant_blend.py` (small-medium,
   from EXTERNAL_TECHNIQUES #5)

**Decision needed first**: which option are we doing this session?
The user picks; PLAN.md gets rewritten with the chosen iteration's
full task list.

**Operational**:
- ComfyUI may or may not be running on `127.0.0.1:8188`. Test:
  `curl -fsS http://127.0.0.1:8188/system_stats`. If down:
  `& "D:\assets\animators\ComfyUI\venv\Scripts\python.exe" "D:\assets\animators\ComfyUI\main.py" --listen 127.0.0.1 --port 8188`
- Always set `$env:PYTHONIOENCODING="utf-8"` in PowerShell.
- Sweep outputs: `D:/tmp/world3_experiments/<name>/`
- Most of `world3/textures/` and `world3/.godot/` are now gitignored
  (committed this session). Generated content is reproducible from
  cookbook prompts.

**Doc-system reminder** (where to write new findings):
- Code/behavior change → relevant runbook + DECISIONS entry if architecturally meaningful
- "I expected X but got Y" surprise → LESSONS
- Sweep / experiment / prompt opinion → TEXTURE_RND
- New external-tech survey → new dated `EXTERNAL_TECHNIQUES_<date>.md`
  (snapshot, don't append to existing)
- Otherwise: DECISIONS.md is the safe default (append-only, broad
  scope)

**The two doc-system failure modes to avoid** (per DOCS_GUIDE):
- Losing things: a finding mentioned in chat but not in a doc
- Drowning in things: 50 markdown files with overlapping scope

**The two technical failure modes to avoid** (per LESSONS):
- "Smooth A" — featureless texture that grades A on metrics but looks
  blank in-world. Always eyeball the contact sheet.
- Concurrent `experiment.py` runs with the same `--name` race on
  shared library paths and corrupt each other. One at a time.

Ask me which option to commit to before doing anything else. The doc
system is careful and I'd rather you ask than guess about iteration
scope.
