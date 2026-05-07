# Next-Session Prompt

Copy/paste this as the opening message in a fresh session. It contains
the minimum context to pick up where the last session left off,
without re-reading everything. Past-session, you wrote it to yourself.

---

## Session opener (copy from here)

We just finished **Phase A polish** on world3 (richness QA, CHORD
opt-in PBR, variant_blend rescue tool, reference-anchor mode,
CHORD+SM-roughness hybrid). The texture pipeline now has a solid
foundation: 4 PBR backends, an advisory richness gate that catches
"smooth A" failures, a rescue tool for lattice-prone materials, and
optional reference-photo anchoring. **All work is committed.**

**The texture pipeline is paused. Next up is Phase B: upscaling +
multi-resolution pipeline** — currently 512 throughout; close-walk
and hero-material use cases need 1K-2K. Phase A polish left several
foundations Phase B will consume (sharper CHORD geometry pairs well
with SR; richness gate validates upscaled outputs; reference anchor
could anchor upscaled albedos).

**Project state**: world3 is a real-DEM-driven terrain generator at
`D:/assets/world3/`. Phases 0-2.5 done (MVP loop, shader stack,
biome kits, region gallery). Phase A done (texture quality + prompt
R&D). Phase A polish just finished (this session arc):

- A.7  richness QA metric (advisory)               — `b551203`
- A.8  CHORD opt-in PBR backend                    — `ee73ccd`
- A.9  variant_blend.py rescue tool                — `530db77`
- A.10 reference-image anchor mode                 — `a486363`
- A.11 CHORD + SM-roughness hybrid backend         — `0b38aab`
- (doc full-pass)                                  — pending commit

**Read these first, in order, ~15 min total**:

1. [`world3/docs/README.md`](world3/docs/README.md) — docs index. Get oriented.
2. [`world3/docs/PLAN.md`](world3/docs/PLAN.md) — Phase A polish status table; Phase B is NEXT.
3. [`world3/docs/ROADMAP.md`](world3/docs/ROADMAP.md) — Phase B scope is laid out under "Phase B — Upscaling + multi-resolution pipeline (NEXT after polish)".
4. [`pipelines/textures/RECIPES.md`](pipelines/textures/RECIPES.md) — **NEW THIS SESSION** — canonical commands per use case. The operator's guide.
5. [`pipelines/textures/EXTERNAL_TECHNIQUES.md`](pipelines/textures/EXTERNAL_TECHNIQUES.md) — A.5 survey; many entries are upscaling-adjacent and worth a re-skim before starting Phase B.
6. [`world3/docs/DOCS_GUIDE.md`](world3/docs/DOCS_GUIDE.md) — where new findings go.

## Phase B scope (from ROADMAP.md)

The texture pipeline currently outputs at 512×512. Phase B's goal:

- Audit `pipelines/textures/flux_upscale.py` (already exists; review what works).
- Research alternatives: **Real-ESRGAN, SwinIR, BSRGAN** (general-purpose
  super-resolution); ComfyUI's upscaler ecosystem (UltimateSDUpscale,
  ESRGAN, custom workflows); tileable-aware SR strategies.
- Pick a 512→1K and a 512→2K path. Decision point: 4× SR followed by
  tiling repair, vs. integrated tile-aware SR, vs. SR via FLUX img2img
  at higher res.
- Build/extend an upscaler that handles **all 5 PBR maps**, not just
  albedo. Normal needs special handling (don't blur — bicubic or
  normal-aware SR; see TEXTURE_RND if anything was logged).
- Per-tier QA using the **post-A.7 gate** (richness advisory included
  so smooth-A failures get caught at every resolution tier).
- Pick a flagship texture (probably wgv3_rock_dark with the new
  CHORD geometry from A.8/A.11) and produce the full 512→1K→2K
  ladder.

**Exit**: pipeline command `512 → 1K|2K` with all maps preserved
and tiling intact. Documented policy: which textures get which tier.

## Foundations Phase B consumes

- **A.7 richness gate** catches smooth-A at every resolution tier.
- **A.8 CHORD backend** operates at 1024 native — naturally pairs with
  upscaling research (we already have a 1K-class backend).
- **A.10 reference-anchor** — the heal-pass `BasicScheduler` swap we
  did for anchor mode is also relevant infrastructure for Phase B
  if we end up using img2img-style upscaling (i.e. SR via partial
  denoise).
- **A.11 hybrid (chord_sm_rough)** — this is probably the
  starting-point backend for the flagship rock_dark upscale ladder
  (sharp normals + correct roughness at 1024 → can be cleanly
  upscaled).

## Open candidates (parked, in ROADMAP "Open / parked candidates")

These are queued behind Phase B but worth keeping in mind as the
upscaling work surfaces specific needs:

- **Auto-rescue mode** in orchestrator (detect "all variants share
  lattice", fall through to `variant_blend`).
- **Promote richness from advisory to hard-gate** (wait until we have
  more data on whether new generations score consistently).
- **Hero-mesh lane** (Hunyuan3D-Paint 2.1) — separate workflow for
  UV-baked bespoke terrain. User said "we'll see"; deferred.
- **klein-9B Edit** — stronger native reference handling than
  klein-4B. Revisit if A.10's anchor isn't enough for some use case.
- **Honest partial-denoise heal pass audit** (LESSONS issue surfaced
  by A.10c) — `Flux2Scheduler` silently drops `denoise`. Switching
  the heal pass to `BasicScheduler` at honest 0.5 might improve
  content preservation. Requires A/B against shipping set.
- **Curated reference-photo set** under `world/textures/references/`
  for A.10 anchor mode.

## Operational

- ComfyUI: test with `curl -fsS http://127.0.0.1:8188/system_stats`.
  If down: see RECIPES.md "Prerequisites".
- Always set `$env:PYTHONIOENCODING="utf-8"` in PowerShell.
- Sweep outputs go to `D:/tmp/world3_experiments/<name>/`.
- HF token is configured at `~/.cache/huggingface/token` (rotate the
  one that was pasted in chat — pls verify it's been replaced with
  a fresh one).
- D: drive: was 100% on 2026-05-06; verified 74% during this session.
  Check `df -h /d` before bulk pulls / multi-tile runs.

## Things to know before generating

- **The directional-cue rule** is project-wide (TEXTURE_RND Part 2
  anatomy): if the desired material doesn't *naturally* have a
  visible directional structure at 1m² scale, don't put a directional
  word in the prompt (`ridges`, `striations`, `wind ridges`, `bands`).
  Confirmed across 3 materials and 3 directional words; periodic
  failures up to 1269 if violated.
- **Avoid seed 300** — A.2 found it produces lattice on 4/5
  representative materials. Use 100/200/400 by default.
- **Two `experiment.py` runs with the same `--name` race-condition
  each other** through shared library paths (LESSONS L19). One at a
  time, or use distinct `--name` values.
- **The richness metric is currently advisory** (computed + printed
  but not part of the A/B/C/D grade). LESSONS L16 still applies —
  always eyeball the contact sheet, the metric isn't a substitute
  for visual review.

## Doc-system reminder (where to write new findings)

- Code/behavior change → relevant runbook (PIPELINE/TOOLS/RECIPES) +
  DECISIONS entry if architecturally meaningful
- "I expected X but got Y" surprise → LESSONS
- Sweep / experiment / prompt opinion → TEXTURE_RND
- New external-tech survey → new dated `EXTERNAL_TECHNIQUES_<date>.md`
- New canonical command for a use case → RECIPES (the new doc!)
- Otherwise: DECISIONS.md is the safe default (append-only)

## The two failure modes I keep getting bitten by

- **"Smooth A"** — featureless texture that grades A on metrics but
  looks blank in-world. The richness check now flags it (advisory
  for now). Always eyeball.
- **Concurrent experiment.py runs corrupt each other** — see L19.
  One at a time.

## What I'd ask before doing anything

The user might prefer to **not start Phase B immediately** and instead
take one of the parked items (e.g. honest partial-denoise heal audit
is small and could surface real wins). Worth asking:

> "Phase B (upscaling research) is the next ROADMAP item, but several
> Phase A parked candidates are also small enough to land in a single
> session. Want to start Phase B, or pick up one of the parked items
> first? Options visible in ROADMAP under 'Open / parked candidates'."

If they say go, start Phase B with the audit of `flux_upscale.py`
and a research pass on Real-ESRGAN / SwinIR / BSRGAN compatibility
with our pipeline. Don't install anything until the research
clarifies which approach is right (per memory rule:
"Research before installing").
