# Next-Session Prompt

Copy/paste this as the opening message in a fresh session. It contains
the minimum context to pick up where the last session left off,
without re-reading everything. Past-session, you wrote it to yourself.

---

## Session opener (copy from here)

We just switched world3 to a **single-stream orchestrator/worker
operating model (2026-05-08)**. The world3 main chat (this one) is
the orchestrator — owns roadmap, sequencing, most work, all
cross-cutting decisions. The OpenTopo chat is a worker that takes
scoped task handoffs in their domain (real-data sourcing, master-
stack assembly, real-source material extraction, transition tile
authoring).

**The current iteration is M1–M5**, replacing the original "Phase F
end-to-end" plan because material taxonomy + transitions + splat
shader + chunk size are interlocked and need to be sequenced
together.

**Phases done**: A, A polish, B, C, D, E, F.1, F.3. **All work
committed.**

**Read these first, in order, ~15 min total**:

1. [`world3/docs/WORLD3_STATE_2026_05_08.md`](world3/docs/WORLD3_STATE_2026_05_08.md)
   — orchestrator state doc + knob-space + worker infra inventory +
   M1–M5 plan + handoff protocol. **Read first.**
2. [`world3/docs/PLAN.md`](world3/docs/PLAN.md) — current iteration:
   M1–M5 with sequence + ownership.
3. [`world3/docs/ROADMAP.md`](world3/docs/ROADMAP.md) — phase
   history (A–E done) + 2026-05-08 update note up top.
4. [`docs/handoffs/HANDOFF_TEMPLATE_to_worker.md`](docs/handoffs/HANDOFF_TEMPLATE_to_worker.md)
   — handoff template format.
5. Captures for visual sign-off (no action; just review):
   - `world3/docs/captures/phase_e_gallery/` — 7 regions × 5 kits.
   - `world3/docs/captures/phase_e/` — alpine walk/iso/topdown.
   - `world3/docs/captures/phase_c/` — anchor zoom levels.
   - `world3/docs/captures/phase_f/` — F.3 2x2 stitch test.

## What's next: M1 (material catalog)

M1 is the gating step — it defines the contract that M2 (transitions)
and M4 (splat shader) need.

**Concrete first move:**

1. Draft `world3/materials/CATALOG.md` (or `catalog.json` — decide
   during drafting). Schema for each material entry: id, source
   (real/procedural/fantasy), provenance, scale, color family,
   current PBR maps path, validated views (close/mid/far ok or not).
2. Migrate the 25 kit-slot textures (5 kits × 5 slots) into the
   catalog. Re-derive `biome_kits.json` so kit slots reference
   catalog ids.
3. Write a handoff for the worker covering migration of their 6
   OpenTopo finished materials into the same catalog format. Use
   the handoff template at `docs/handoffs/HANDOFF_TEMPLATE_to_worker.md`.

**Exit for M1**: every material in the system has one canonical id
+ one catalog entry. `biome_kits.json` references catalog ids.
Existing runtime scenes still build + render.

**Parallel work possible**: M3 (chunk-size sweep) doesn't depend on
M1. If M1's drafting is paused waiting on user feedback or worker
response, start M3 in parallel.

## Operating reminders

- **Godot binary**: `C:/Godot/Godot_v4.5-stable_win64.exe`.
- **Always run captures WITHOUT `--headless`.** SceneTree-script
  runner pattern hangs in headless. Real-window mode is fast (~2s/
  scene) and produces correct output. Documented in
  `world3/docs/captures/phase_c/README.md`.
- **After deploying / regenerating any .tres**, run
  `Godot --headless --editor --import` once before capturing.
- **D: drive**: was 100% on 2026-05-06. Check `df -h /d` before bulk
  pulls / multi-tile runs.
- ComfyUI: test with `curl -fsS http://127.0.0.1:8188/system_stats`.
  If down: see `pipelines/textures/RECIPES.md` "Prerequisites".
- Always set `$env:PYTHONIOENCODING="utf-8"` in PowerShell.
- **PowerShell `Write-Output` for unicode** crashes on Windows
  cp1252. Use plain ASCII (`->` not `→`) in print statements + use
  the `Write` tool only for UTF-8 docs.

## Worker handoff protocol

Orchestrator writes a small spec at
`docs/handoffs/HANDOFF_to_opentopo_<topic>_<date>.md`. Worker
executes, commits, replies inline. Orchestrator reviews + integrates
+ marks status DONE.

When in doubt: keep handoffs SMALL (one bounded task). Easier to
review + integrate + course-correct than a big multi-feature
handoff.

## Acknowledged future scope (NOT planned now)

Props, decorations, buildings, POIs, fantasy biomes. All exist as
known future pipelines. Kick in once chunk + biome + tile +
transition is ~80% solved. Listed in WORLD3_STATE section 6 so we
don't accidentally architect ourselves out of them.

## Doc-system reminder

- Code/behavior change → relevant runbook (PIPELINE/TOOLS/RECIPES) +
  DECISIONS entry if architecturally meaningful.
- "I expected X but got Y" surprise → LESSONS.
- Sweep / experiment / prompt opinion → TEXTURE_RND.
- New canonical command for a use case → RECIPES.
- Phase / iteration wrap-up → handoff doc under `docs/handoffs/`.
- Worker handoff: `docs/handoffs/HANDOFF_to_opentopo_*.md`.
- Otherwise: DECISIONS.md is the safe default (append-only).
