# [TEMPLATE] Handoff: <topic> → OpenTopo worker (<date>)

Use this template when the orchestrator (world3 main chat) hands off
a scoped task to the OpenTopo worker chat. Copy this file to
`docs/handoffs/HANDOFF_to_opentopo_<topic>_<date>.md` and fill it in.

Drop the worker's response either inline at "Worker reply" below, or
as a follow-up commit referenced by hash. Mark status DONE when the
orchestrator integrates + accepts; DROPPED if cancelled; REVISIONS
if more work needed.

---

## Status

`OPEN` | `IN PROGRESS` | `REVISIONS REQUESTED` | `DONE` | `DROPPED`

## Task

One paragraph. What needs to be built and why. Reference the
relevant section of `world3/docs/WORLD3_STATE_2026_05_08.md` (e.g.
"M2 transition prototype").

## Inputs

What the worker needs to read or use as starting material. List
exact paths. Examples:

- Catalog spec: `world3/materials/CATALOG.md`
- Existing review scene: `world3/toporeview/biome_tile_transition_review.tscn`
- Worker's existing tool: `world3/pipeline/build_opentopo_tileable_texture.py`
- Material pairs to handle (table or list)

## Deliverables

Exact list. The worker should be able to check off each one. Examples:

- [ ] Tool: `pipelines/textures/build_transition_strip.py`
- [ ] Output materials: `world3/textures/wgv3/transitions/<a>_to_<b>/{albedo,normal,roughness}.png`
- [ ] Captures: drop into `biome_tile_transition_review.tscn` and
      add a screenshot of each transition rendered against hard cuts
      at `world3/docs/captures/transitions/<a>_to_<b>.png`
- [ ] Docs update: append a section to
      `world3/docs/OPENTOPO_BIOME_TILE_TRANSITION_REVIEW.md`
      describing the new transitions

## Accept criteria

How the orchestrator decides "done." Be specific. Examples:

- All deliverables committed.
- At least 3 transitions read better than hard cuts in the review
  scene (visual review by user).
- Tool runs end-to-end on the listed material pairs without manual
  steps.
- No regressions in existing review scenes.

## Out of scope

What the worker should NOT do, even if tempting. Examples:

- DO NOT modify `terrain_blend.gdshader` — runtime shader changes
  are orchestrator-owned (M4).
- DO NOT redesign the catalog format — use it as given.
- DO NOT add new material classes; only generate transitions
  between existing ones.

## Deadline

Optional. "By session N" or absolute date.

## Pointers for the worker

Anything the orchestrator knows that would help the worker:
gotchas, prior failed approaches, references to similar work,
who/what to ask if blocked.

---

## Worker reply

[Worker fills in when responding]

### What landed

- (commit hash) — short description
- (commit hash) — short description

### Surprises / deviations

What didn't go to plan, or things the orchestrator should know.

### Things I couldn't do

If any deliverables aren't met, list why. Don't silently drop them.

### Next-step suggestions

Optional. If you saw an obvious follow-up, name it.

---

## Orchestrator review (after worker reply)

[Orchestrator fills in]

### Verdict

`ACCEPTED` | `REVISIONS REQUESTED` | `DONE`

### Notes

What was integrated, what was deferred, what surprised the orchestrator.

### Integration commit

(orchestrator's integration commit hash)
