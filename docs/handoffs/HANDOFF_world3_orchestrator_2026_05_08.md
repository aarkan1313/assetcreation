# Orchestrator Handoff: world3 — 2026-05-08

You are the new orchestrator for **world3**, the real-DEM-driven
terrain generator at `D:/assets/world3/`. The previous orchestrator
ran a single-stream operating model with the OpenTopo chat as worker.
This doc is your single entry point: read this, you're caught up.

If you only have time for one file, this is it. If you have 15
minutes, also read `world3/docs/WORLD3_STATE_2026_05_08.md` (state
doc) and `world3/docs/PLAN.md` (M1–M5 sequence).

---

## What you own

- The world3 unified roadmap + sequencing (M1–M5).
- All cross-cutting decisions (taxonomy, chunk size, shader stack,
  material catalog format).
- Most of the work: runtime, scene wiring, shader stack, kit
  definitions, chunk streaming, procedural texture generation
  pipeline, integration of worker output.
- Direction-setting docs: `WORLD3_STATE_2026_05_08.md`, `PLAN.md`,
  `ROADMAP.md`, `DECISIONS.md`.

## What the worker (OpenTopo chat) owns

- Real-data sourcing: DEM/orthophoto/NIR/LAZ fetch + processing.
- Master-stack assembly (real-place review scenes).
- Real-source material extraction (variant atlases →
  soft-composite path → `finish_opentopo_soft_materials.py`).
- Transition tile authoring (their QA infra is already built).
- Provenance metadata authoring.
- Their `world3/docs/OPENTOPO_*.md` set is their runbook.

## What flows between you

Handoffs. Template at `docs/handoffs/HANDOFF_TEMPLATE_to_worker.md`.
You write a small spec; worker executes and replies inline; you
review + integrate + mark DONE. Keep handoffs SMALL — one bounded
task per handoff is easier to integrate.

The worker has acknowledged this model (2026-05-08 reply). They are
on standby until you send them M2.

---

## Operating-model recap (90 seconds)

**Until 2026-05-08**: two parallel chats (world3 main + OpenTopo)
both made architectural decisions. Started converging on the same
problems (chunks, transitions, taxonomy) without a shared contract.

**Switched 2026-05-08**: single-stream orchestrator + worker. One
source of truth for direction. Worker takes scoped handoffs in
their domain. No more competing roadmaps.

**Why**: the user wanted to see how performance + quality scale
across chunk sizes under streaming load (an evidence-backed
decision, not back-of-envelope). Plus material taxonomy + transitions
+ splat shader + chunk size are interlocked — sequential phases
don't fit. M1–M5 is the real sequence; Phase F got absorbed.

**The user is the source of truth on direction.** When in doubt
about scope or sequencing, ask. They've made several mid-iteration
calls that reshaped the plan correctly (e.g. "chunk size needs
evidence"; "we're not doing two pipelines anymore").

---

## What's been built (very-short version)

Phases A through E + F.1/F.3 are DONE. Long version is in section
2A of `WORLD3_STATE_2026_05_08.md`. Highlights:

- **5 biome kits** with bound `terrain_blend_<kit>.tres` materials
  (Phase D) + per-mode variants for walk/iso/topdown (Phase E).
- **Anchor-mode framing** on iso/topdown cameras (Phase C). Lets
  cameras frame around a `PlayerAnchor` at a configurable diameter
  (40m ARPG / 300m strategy / 50m game-tile / 10km minimap).
- **Region gallery** captures all 7 sample regions × iso + topdown
  showing all 5 kits — `world3/docs/captures/phase_e_gallery/`.
- **2x2 stitch test** (Phase F.3) confirmed basic geometric
  stitching works; surfaced a per-chunk normal-seam issue at
  borders (one-sided finite differences) that M3 fixes.
- **6 OpenTopo finished material classes** (worker side):
  `bare_soil`, `bright_rock`, `dry_wash`, `rocky_slope`,
  `scrub_dense`, `scrub_sparse`. Bound to
  `terrain_hex_detail.gdshader` (NOT the same shader as the
  procedural kits — see "Known sharp edges" below).
- **Master stacks** (worker side): Gloss Mountain (textured
  0.6×1.1km) + Zion (4-call USGS10m 36×37km no-color).
  Production-FACING review scenes, not final production assets.

---

## The current iteration: M1–M5

| ID | What | Owner | Blocks | Blocked by |
|----|------|-------|--------|------------|
| **M1** | Material catalog: single source of truth aligning kit slots + OpenTopo material classes. | You draft spec; worker handoff for migrating their 6 materials. | M2, M4 | — |
| **M2** | Transition material prototype: 4–6 transitions across kit/class/source pairs. | Worker handoff (they have the QA infra). | M4 | M1 |
| **M3** | Chunk-size sweep: parameterized streaming harness + sweep at 256/512/1024 m. | You. | M5 | — (parallel with M1/M2) |
| **M4** | Splat-shader prototype + shader unification (terrain_blend + terrain_hex_detail → one). | You. | M5 | M1, M2 |
| **M5** | Wire streaming + splat into `walk.tscn`. | You. | — | M3, M4 |

**Parallelism**: M1+M3 can start simultaneously. M2 starts as soon
as M1's catalog spec is drafted.

Full M1–M5 detail is in `world3/docs/PLAN.md`.

---

## YOUR FIRST MOVE

You walk in with three legitimate options. Pick based on what the
user asks for, default if not asked is **option A**.

### Option A — Start M1 (material catalog) now (default)

Draft `world3/materials/CATALOG.md` (or `catalog.json`) with the
schema specified in `PLAN.md` § M1. Required fields per material:

- `id` (canonical name)
- `source` (real / procedural / fantasy)
- `provenance` (DEM/orthophoto crop ref OR generation prompt)
- `scale_m_per_repeat`
- `color_family`
- `pbr_maps` (paths)
- `shader_binding` (`terrain_blend` or `terrain_hex_detail` —
  records the current reality; M4 unifies)
- `validated_views` (close/mid/far ok-or-not)

Migrate the 25 kit-slot textures (5 kits × 5 slots) yourself.
Once draft + your migration is in, write the **M2-prep handoff**
to the worker: "use this catalog format to migrate your 6 finished
OpenTopo material classes; reply with the catalog entries committed."

That M2-prep handoff is BEFORE M2 (transition prototype) itself —
the catalog has to settle first because M2 takes catalog ids as
input.

### Option B — Start M3 (chunk-size sweep) in parallel with M1

Doesn't depend on M1, can start anytime. Build
`world3/scripts/ChunkLoader.gd` parameterized on `chunk_size_m`.
Synthetic infinite world (single Tetons heightmap tiled across
arbitrary grid). Sweep at 256/512/1024 m. Capture per-size: GPU
memory, frame time mean/p95/p99, peak chunk count, worst-case
load latency, seam quality screenshot.

Outcome doc: `world3/docs/PHASE_F_CHUNK_SIZE_SWEEP.md`. Lock chunk
size in DECISIONS.md.

This is good if the user wants to unblock M5 sooner, or wants
evidence before committing to M4 design.

### Option C — Pause for the night

Tell the user "M1–M5 is queued, where do you want to start," and
wait. The state is fully captured — there's no time pressure on
picking up.

---

## How to write a good worker handoff

The worker has acknowledged the operating model. They're cooperative
and provided three useful corrections to the state doc on first
contact (see change log in `WORLD3_STATE_2026_05_08.md`). They will
push back factually, won't push back architecturally. Treat them as
a domain specialist, not a peer.

**Use the template at `docs/handoffs/HANDOFF_TEMPLATE_to_worker.md`.**
Fill all sections. Specifically:

- **Inputs**: list exact paths. Worker won't guess. If you reference
  the catalog, say "see catalog entries `desert_sand`, `dry_wash`,
  etc."
- **Deliverables**: checkbox list. Worker checks them off in their
  reply.
- **Accept criteria**: how you decide DONE. Be specific, ideally
  visual ("transitions read better than hard cuts in
  `biome_tile_transition_review.tscn`") OR mechanical ("tool runs
  end-to-end on the listed pairs without manual steps").
- **Out of scope**: things they should NOT do. The worker offered
  to act as orchestrator earlier; the user declined. Don't let them
  extend scope into runtime/shader work — that's yours.

When they reply DONE, integrate their commits into your runtime,
update `WORLD3_STATE_2026_05_08.md` change log, mark the handoff
DONE, and move to the next.

---

## Known sharp edges

These will bite if you don't know about them.

### 1. Two shaders, not one (until M4)

Orchestrator-side scenes use `terrain_blend.gdshader` (bound by all
`terrain_blend_<kit>_<mode>.tres` files). Worker's 6 finished
OpenTopo materials use `terrain_hex_detail.gdshader` (bound by
`material_hex_detail_finished.tres` files). The `.tres` files are
NOT interchangeable across shaders. M4 unifies; until then, both
coexist and the catalog must record `shader_binding` per entry.

### 2. Captures hang in `--headless` mode

The SceneTree-script runner pattern (`screenshot_scenes.py`,
`_codex_render_runner.gd`) hangs in `--headless` because
`process_frame` awaits don't resume reliably. Run captures WITHOUT
`--headless` — real window mode is fast (~2s/scene) and produces
correct output. Documented in
`world3/docs/captures/phase_c/README.md`.

### 3. Material/scene changes need a Godot import pass

After deploying or regenerating any `.tres` or PNG that goes into
`world3/textures/wgv3/`:

```powershell
& "C:/Godot/Godot_v4.5-stable_win64.exe" --path world3 --quiet --headless --editor --import
```

Without this, captures error with "No loader found for resource"
because the new files have no `.import` metadata.

### 4. Per-chunk normal seam at chunk borders

Phase F.3 surfaced this: each chunk's `Terrain.gd._build_mesh`
computes normals via finite differences from its own height grid.
At chunk borders, normals are computed one-sided → faint shading
seam visible under directional light. M3 fixes by sampling 1-2
pixel overlap from the source heightmap when building each chunk's
hgrid.

### 5. `Write` tool encoding gotcha

Windows `Write-Output` and Python `print()` crash on cp1252 stdout
when emitting Unicode arrows (`→`) etc. Use plain ASCII (`->`).

### 6. D: drive space pressure

Was at 100% on 2026-05-06. Currently OK but check `df -h /d` before
bulk pulls / multi-tile aaa_texture runs / chunk-streaming sweeps.

### 7. Worker may have parallel uncommitted changes

The worker has been editing files in parallel during the operating-
model switch (mostly their `OPENTOPO_*.md` docs and their pipelines).
These will land via their commits, not yours. Don't blow away their
work — `git status` before staging anything broad. Use surgical
`git add <path>` rather than `git add -A` when uncertain.

### 8. Grassland kit looks uniform — by design

Tibet + Serengeti read as near-uniform tall_grass at iso/topdown.
DECISIONS-locked 2026-05-07. Real Serengeti and Tibetan plateau ARE
biologically uniform; tightening the bands made it worse not
better (all 5 grassland slots share a yellow color family; tighter
bands triggered more layers but they all looked yellow). If a
specific region needs visible rocky variation, the right fix is a
region-specific kit override OR regenerating
`wgv3_gl_grass_rock` + `wgv3_gl_weathered_stone` with darker prompts
— NOT widening the kit's bands.

---

## What's parked (don't plan, just know)

- **Props pipeline**: meshes + textures + collision + placement
  metadata. Partially exists in `pipelines/props/` +
  `world/props/library/`. Per-chunk placement masks once chunks
  exist.
- **Decoration pipeline**: vegetation scatter, ground decals.
- **Buildings + POIs**: separate pipeline (procedural + generated +
  handcrafted).
- **Fantasy biomes** as a Source-axis value.
- **Per-game knob presets** (each game picks a point in the 5-axis
  knob-space).

These start when chunk + biome + tile + transition is ~80% solved
(per user 2026-05-08). NOT in scope for current iteration.

## Post-M5 option registers (for when the user asks "what next")

Two forward-looking docs that survey post-M5 directions. Don't plan
work from them now — they exist so the next "what's next?"
conversation has concrete options on the table.

- [`world3/docs/FUTURE_WORLD_SOURCES_2026_05_08.md`](../../world3/docs/FUTURE_WORLD_SOURCES_2026_05_08.md)
  — Track A (alternative heightmap/world sources: NLCD land-cover,
  bathymetry, planetary DEMs, sketch-to-heightmap, fantasy world
  generators, photo+depth) and Track B (explorable interiors —
  castles, dungeons, building insides). Highest-leverage Track A
  item is **NLCD land-cover** (free per-pixel biome ground truth;
  pairs with M4 splat shader).

- [`world3/docs/FUTURE_PROCEDURAL_STRUCTURES_2026_05_08.md`](../../world3/docs/FUTURE_PROCEDURAL_STRUCTURES_2026_05_08.md)
  — Track C (procedural structure generators: 11 families covering
  trees, grass, crystals, voronoi, fractals, scree, layered rock,
  cellular, lattices, etc). Highest-leverage Track C item is
  **G1 trees + G7 grass + G5 scree** as a Tier 1 starter group;
  vegetation transforms "terrain" into "place."

The single most powerful post-M5 pairing called out across the docs:
**NLCD biome masks (Track A #1) + tree scatter at biome-class
density (Track C G1)** — a ~2-3 session arc to a demo that looks
like a real game world for the first time.

Both docs are also linked from `world3/docs/ROADMAP.md` "Far-end
direction (post-M1–M5 option registers)" section.

---

## Open polish items (parked)

Pick up between M-tasks if you have spare cycles:

- **Non-alpine per-mode visual review.** Phase E's emit tool covers
  all 5 kits but only alpine has dedicated capture scenes.
- **Walk-mode shared-anchor decision.** Phase C deferred whether
  walk shares a `PlayerAnchor` with iso/topdown.
- **Region gallery walk shot.** Gallery only does iso + topdown.
- **Corner textures (3-way junctions).** Defer until M2 pairwise
  transitions land and we know which corners actually appear in
  game content.

---

## Doc-system map

Where new findings go:

- Code / behavior change → relevant runbook (`PIPELINE.md`,
  `TOOLS.md`, `RECIPES.md`) + `DECISIONS.md` entry if architectural.
- "I expected X but got Y" surprise → `LESSONS.md`.
- Sweep / experiment / prompt opinion → `TEXTURE_RND.md`.
- New canonical command for a use case → `RECIPES.md`.
- Phase / iteration wrap-up → handoff doc under `docs/handoffs/`.
- Worker handoff: `docs/handoffs/HANDOFF_to_opentopo_*.md`.
- Updates to direction → `WORLD3_STATE_2026_05_08.md` change log
  AT MINIMUM. Plus `PLAN.md` if iteration scope changed; plus
  `ROADMAP.md` if phase order changed.
- Otherwise: `DECISIONS.md` is the safe default (append-only).

---

## Reading list (when you have time)

1. **This doc** — orchestrator handoff (you're here).
2. `world3/docs/WORLD3_STATE_2026_05_08.md` — full state doc with
   knob-space, inventory, gaps, M1–M5 detail, owner/worker boundary,
   handoff protocol, change log.
3. `world3/docs/PLAN.md` — current iteration: M1–M5 with sequence +
   ownership.
4. `world3/docs/ROADMAP.md` — phase history (A–E done) + 2026-05-08
   update note up top.
5. `docs/handoffs/HANDOFF_TEMPLATE_to_worker.md` — handoff template.
6. `world3/docs/captures/phase_e_gallery/README.md` — visual
   evidence of what the system looks like today.
7. Worker runbook (read for orientation only, no action):
   `world3/docs/OPENTOPO_TEXTURE_SCENE_ROADMAP.md`,
   `world3/docs/OPENTOPO_BIOME_TILE_TRANSITION_REVIEW.md`,
   `world3/docs/OPENTOPO_MASTER_STACKS_AUDIT.md`.

---

## What the user wants from you (likely)

Best guess based on the recent conversation:

- **Visual sign-off** is pending — they want to look at the
  captures (phase_e_gallery, phase_e, phase_c, phase_f) and check
  quality before more work lands. This sign-off is async; don't
  block on it.
- **M1 is the first concrete deliverable** they're asking for.
  Default to drafting that unless they redirect.
- They are willing to course-correct mid-iteration; they don't
  expect you to nail the first plan. When they push back ("we
  need evidence on chunk sizes"; "we're not doing two pipelines
  anymore"), that reshapes the plan immediately. Don't fight
  course corrections.
- They prefer concise responses with concrete next moves. Don't
  pad. Don't restate the question. State the action and offer a
  small set of options if there's a real fork.

---

## Last commits before handoff (for context)

```
e494d82 state doc: apply worker corrections to 2B/2C; M4 absorbs shader unification
c0b5178 operating model: switch to single-stream orchestrator/worker
92202cc state doc: world3 + OpenTopo convergence inventory + alignment
f3e374b phase F.2 deferred behind sweep — chunk size needs evidence
f76fde1 phase F.1 + F.3: research findings + 2x2 stitch test passes
d9a231c phase F kickoff: grassland decision-locked + Phase F plan
```

---

## Acknowledgement to send when you start

Reply to user with something like:

> Read the handoff. Caught up on M1–M5, the orchestrator/worker
> split, and the worker's three corrections. Ready to start M1
> (material catalog) — that's the gating piece for M2 and M4. Want
> me to draft the catalog format now or are you going to pick a
> different first move?

Then wait for their reply before drafting.
