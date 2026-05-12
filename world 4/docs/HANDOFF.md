# W4 — Fresh-Session Handoff

> Drop this into a new chat to pick up W4 work. Self-contained — the
> agent should be able to start from this alone, then drive next steps
> off the live ROADMAP.

---PROMPT START---

I'm continuing a project called World 4 (W4). It's a Godot 4.5 + Python
world-generation system. Working directory: `D:\assets\world 4\`.

## Read these docs in order before doing anything

These are the live sources of truth. Anything older / dated / archived is
not authoritative.

1. **`docs/ROADMAP.md`** — what's done, what's next, ranked. Single
   source for "what to work on now."
2. **`docs/strategy/AXES.md`** — the 6 axes of expansion and what state
   each axis is currently in.
3. **`docs/strategy/ANCHOR.md`** — the regression baseline. Anything we
   build must not break the anchor demo.
4. **`docs/reference/PITFALLS.md`** — the 4 known terrain artifact
   classes with root causes + working fixes. Check this whenever a
   visual artifact appears.
5. **`docs/reference/TOOLS.md`** — index of every pipeline script,
   shader, and runtime component, plus when to run each.
6. **`docs/reference/ORCHESTRATOR_GUIDE.md`** — how to actually run the
   pipeline end-to-end (commands + file layout + common failure modes).

If a specific axis is the focus, also read its build-note in
`docs/build-notes/`:
- `ANCHOR_BUILD_NOTES.md` — 256m anchor demo
- `SCALE_BUILD_NOTES.md` — Axis 1 scale_demo (1024m, 16 tiles, paging)
- `BIOME_KITS_BUILD_NOTES_2026_05_12.md` — Axis 2 texture kits

## How to work

- **Drive next steps from `ROADMAP.md`'s ranked candidates.** The list
  is current; trust it. If the rank feels stale, talk it through and
  rerank before starting work.
- **One change at a time** during visual debugging. Headless captures
  hide some bugs the editor shows (Pitfall #3). Trust live editor
  screenshots as ground truth.
- **Don't change the anchor.** `materials/anchor_v2/`,
  `terrain_anchor_v2.gdshader`, `AnchorTerrain.gd`, and the
  `worlds/anchor/` bundle are the locked regression baseline.
- **Run `--headless --import`** after editing any shader, texture, or
  imported asset from outside Godot, or "nothing changes in the
  editor."
- **Quality > Performance > Organization.** Per AXES.md. KISS / YAGNI
  serve these, they don't outrank them.

## Operator mode (from `handoffs/COMPACTION_HANDOFF.md`)

The user drives strategy; I drive tactics. Ask before:
- destructive operations (deleting files, dropping branches, force-pushes)
- anchor-breaking changes (anything touching `worlds/anchor/` or the v2
  anchor shader)
- W3 changes (W3 is parts depot, not a build target — see memory entry
  `w4_kickoff_decision.md`)

Otherwise: pick the next ranked roadmap item, implement, capture, report.

## What I'm picking up right now

Read `ROADMAP.md` and pick the top-ranked candidate. If unclear, ask;
otherwise propose your concrete first step before coding.

---PROMPT END---

## Update protocol for this doc

- The PROMPT block above should age slowly — it's about *how to take
  over*, not *what's currently next*.
- Specific session takeovers (e.g. "this session's job: generate 48
  texture maps") get their own dated handoff doc at the docs root
  (`HANDOFF_YYYY_MM_DD_<topic>.md`), not edits here.
- When the roadmap structure changes (new axis added, doc layout
  reorganized), update the doc list above to match.
