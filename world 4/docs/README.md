# W4 docs — index

> Start here. This page tells you where to find everything else and
> what each doc is for.

## If you are...

- **A fresh Claude session** → read `HANDOFF.md` first.
- **Asking "what's the current state of W4?"** → read `STATE.md`.
- **Asking "what should I work on next?"** → read `ROADMAP.md`.
- **About to do a specific kind of task** → read `workflows/`.
- **Looking up a CLI tool, shader, or class** → read `reference/TOOLS.md`.
- **Debugging a visual artifact** → read `reference/PITFALLS.md`.
- **Trying to understand a long-term design choice** → read `strategy/`.

## Folder map

| Folder | Purpose | When it changes |
|---|---|---|
| `(root)` | The entry points: `README.md` (this), `STATE.md`, `ROADMAP.md`, `HANDOFF.md` | Whenever the project state advances |
| `workflows/` | "How to do X." End-to-end recipes for recurring tasks | When a new recurring task pattern emerges |
| `reference/` | Authoritative reference: `TOOLS.md`, `PITFALLS.md`, `ORCHESTRATOR_GUIDE.md` | When tools / pitfalls / orchestration change |
| `strategy/` | Long-form design: `AXES.md`, `ANCHOR.md`, `BIOMES.md`, `WISHLIST.md` | When the architecture or roadmap shape shifts |
| `plans/` | Per-axis design docs + implementation plans | One pair per axis cycle |
| `superpowers/` | Plans + specs managed by the brainstorming / writing-plans skills | One per skill-driven feature |
| `build-notes/` | "What was just shipped" per axis cycle | Once per shipped axis |
| `handoffs/` | Big-bang takeover prompts (`HANDOFF_YYYY_MM_DD_*`) | Each compaction or pickup point |
| `historical/` | Closed bugs / audit trails that future you should remember | Rare — once-per-debugging-saga |
| `features/` | Per-feature docs (e.g. view-modes, world-pipeline) | When a feature reaches "shipped + documented" |

## Update protocol

- The **top four** (`README`, `STATE`, `ROADMAP`, `HANDOFF`) are the layer that ages fast. Touch them whenever they go stale.
- `reference/TOOLS.md` is the index of *every* CLI tool, shader, and runtime class. Add an entry when you add a tool. Don't let it drift — `git grep` for a script that's not in TOOLS.md is a signal.
- `reference/PITFALLS.md` grows by one entry per real bug-class. Update when you find or fix one.
- Everything else is append-only or rarely-touched.

## Doc lifecycle

```
spec (superpowers/specs/)            ← brainstorming output
   ↓
plan (superpowers/plans/)             ← writing-plans output
   ↓
implementation (commits)
   ↓
build-note (build-notes/)             ← "what was shipped, lessons"
   ↓
state update (STATE.md)               ← "what we now have"
```

Older non-skill plans live in `plans/` directly (e.g. `AXIS6_TRANSITIONS_PLAN_2026_05_12.md`) and follow the same lifecycle without the superpowers/ subfolder.
