# Docs Guide — for Future-Us

We have ~24 markdown files. That's a lot. This page explains *why* —
each doc has a distinct role, write-rule, and lifetime — so we can
tell at a glance "where does this new finding go?" without losing
track or duplicating.

If you're trying to *find* something, [README.md](README.md) is the
question→doc index. **This** doc explains the *system*, not the
contents.

## Doc roles, by lifetime

There are four lifetime classes. Knowing which a doc belongs to tells
you how to write to it without breaking the system.

### 1. Living runbooks — *update when behavior changes*

Truth-of-the-moment about how something works. When the code or
process changes, update the doc. Older versions don't matter.

| Doc                                          | Topic                                                                |
|----------------------------------------------|----------------------------------------------------------------------|
| [WORKFLOW.md](WORKFLOW.md)                   | End-to-end "how do I run world3 from a fresh checkout" + Godot specifics |
| [pipelines/textures/RECIPES.md](../../pipelines/textures/RECIPES.md) | Canonical commands per use case (operator's guide) |
| [pipelines/textures/PIPELINE.md](../../pipelines/textures/PIPELINE.md) | Texture pipeline mechanics (stages, presets, gate logic, output, world3 staging) |
| [pipelines/textures/TOOLS.md](../../pipelines/textures/TOOLS.md) | Inventory of every tool script + when to reach for each              |
| [OPENTOPO_GUIDE.md](OPENTOPO_GUIDE.md)       | OpenTopo data acquisition runbook                                    |
| [OPENTOPO_DATA_TYPES.md](OPENTOPO_DATA_TYPES.md) | What each OT dataset contains + when to use it                   |
| [OPENTOPO_MOSAIC_FUSION_WORKFLOWS.md](OPENTOPO_MOSAIC_FUSION_WORKFLOWS.md) | Tile-stitching and layer-fusion runbook            |
| [opentopo/STATUS.md](../opentopo/STATUS.md)  | Current state of the OpenTopo data we have                           |

**Write-rule**: edit in place. Replace stale sections.
**When in doubt**: prefer adding a new section over rewriting; it's
easier to undo.

### 2. Append-only logs — *never edit history, add new entries*

A timeline of decisions/lessons/experiments. Past entries stay even
when overridden — they're how we remember *why* we did something.

| Doc                                          | Topic                                                                |
|----------------------------------------------|----------------------------------------------------------------------|
| [DECISIONS.md](DECISIONS.md)                 | Architectural decisions + alternatives we considered                 |
| [pipelines/textures/LESSONS.md](../../pipelines/textures/LESSONS.md) | Surprises, gotchas, "the obvious thing was wrong"      |
| [pipelines/textures/TEXTURE_RND.md](../../pipelines/textures/TEXTURE_RND.md) | Part 1: experiments/sweeps. Part 2: prompt cookbook.    |

**Write-rule**: new entries get added with a date. Old entries stay
verbatim. If a finding is *reversed*, add a new entry that says so —
don't edit the original.

**When in doubt**: append. Nobody has ever regretted that an old
DECISIONS entry was kept. Plenty have regretted that they were
edited.

### 3. Snapshots — *frozen at moment of writing*

A point-in-time record. Doesn't update. Reading these in a year
should still make sense.

| Doc                                          | Topic                                                                |
|----------------------------------------------|----------------------------------------------------------------------|
| [TEXTURE_PIPELINE_FIX_PLAN.md](TEXTURE_PIPELINE_FIX_PLAN.md) | The 2026-05-07 audit + 5 fixes (now closed)            |
| [ROADMAP_v1_archived.md](ROADMAP_v1_archived.md) | Original roadmap before the v2 reframe                            |
| [OPENTOPO_PILOT1_*_AUDIT.md](OPENTOPO_PILOT1_GRAND_CANYON_USGS10M_AUDIT.md) | Pilot 1 audit                                |
| [OPENTOPO_PILOT2_*_AUDIT.md](OPENTOPO_PILOT2_GUADALUPE_CYPRESS_FUSION_AUDIT.md) | Pilot 2 audit                            |
| [OPENTOPO_PHASE2_HD_REVIEW.md](OPENTOPO_PHASE2_HD_REVIEW.md) | Phase 2 HD-tile review pass (4096/8192/16K stress test)        |
| [OPENTOPO_PHASE2_MAX_REVIEW.md](OPENTOPO_PHASE2_MAX_REVIEW.md) | Phase 2 max-resolution review pass                          |
| [pipelines/textures/EXTERNAL_TECHNIQUES.md](../../pipelines/textures/EXTERNAL_TECHNIQUES.md) | Survey of external tileable-PBR techniques (2026-05-07 snapshot) |

**Write-rule**: don't edit unless fixing typos. New audits = new
files. New roadmap version = archive the old + write a new one. New
external-techniques survey = new dated file (e.g.
`EXTERNAL_TECHNIQUES_2026Q3.md`).

### 4. Iteration plans — *rewritten each iteration*

Current scope. Replaced when we move to the next iteration.

| Doc                                          | Topic                                                                |
|----------------------------------------------|----------------------------------------------------------------------|
| [ROADMAP.md](ROADMAP.md)                     | Phased plan toward the long-term vision (rewrite when reframing)     |
| [PLAN.md](PLAN.md)                           | Current iteration scope (rewrite each iteration)                     |
| [OPENTOPO_LARGE_4CALL_PLAN.md](OPENTOPO_LARGE_4CALL_PLAN.md) | Active scoped plan for the next 4-call OpenTopo USGS1m fetch (the OpenTopo branch's PLAN.md analogue) |
| [OPENTOPO_TEXTURE_SCENE_ROADMAP.md](OPENTOPO_TEXTURE_SCENE_ROADMAP.md) | Active scoped roadmap for the OpenTopo texture+scene+HD branch (the OpenTopo branch's ROADMAP.md analogue) |

**Write-rule**: the *current* version is the source of truth. When
you replace it, archive the old as `<NAME>_v<N>_archived.md` so
history is preserved. The OpenTopo branch follows the same rule for
its own pair of plan/roadmap docs.

### 5. Session handoff — *fully replaced each session*

A copy/paste opener for a fresh chat session. Writes the minimum
context needed to pick up where the last session left off, without
re-reading the whole doc set. Replaced wholesale at the end of each
session.

| Doc                                          | Topic                                                                |
|----------------------------------------------|----------------------------------------------------------------------|
| [NEXT_SESSION_PROMPT.md](NEXT_SESSION_PROMPT.md) | The opener for the next session — points at the right docs and current state. |

**Write-rule**: rewrite the whole file at the end of each session.
This file is *for future-you's first 30 seconds of context-loading*,
not for posterity. If you want the past version, look in git history.
Don't append.

## Index docs

| Doc                                          | Role                                                                 |
|----------------------------------------------|----------------------------------------------------------------------|
| [README.md](README.md)                       | "Question → doc" index. Anyone landing here finds where to look.    |
| **DOCS_GUIDE.md** (this file)                | "How the docs system works." Why we have what we have.              |

## Writing decisions: where does this new piece of information go?

A flowchart for "I just learned something — where does it land?":

```
Did the *code* or *behavior* change?
├── yes → update the relevant runbook (group 1)
│         AND if the change is architecturally meaningful,
│         add a DECISIONS.md entry explaining why.
│
Was this a "I expected X but got Y" surprise?
├── yes → LESSONS.md (group 2)
│
Did I run an experiment / sweep / A/B / form a prompt opinion?
├── yes → TEXTURE_RND.md (group 2)
│         Part 1 for sweeps, Part 2 for cookbook entries.
│
Is this an operational quirk (Godot path, env var, GPU thing)?
├── yes → the relevant runbook (group 1)
│
Is this a snapshot of "what did we do today" (audit, pilot, etc)?
├── yes → new file, group 3 (snapshots). Don't reuse an existing one.
│
Did we change scope or strategy at the iteration level?
├── yes → PLAN.md (rewrite). If big enough to change phase order:
│         archive ROADMAP.md as v_N and rewrite (group 4).
│
Otherwise → DECISIONS.md is the safe default. Append-only and
            broad scope means nothing's lost.
```

## What we're guarding against

The two failure modes for documentation systems are:

**A. Losing things**: a finding gets mentioned in a chat or a commit
message but never makes it to a permanent doc. A year later we
re-discover the same lesson the hard way.
- Defense: append-only logs (LESSONS, EXPERIMENTS, COOKBOOK,
  DECISIONS). When in doubt, append.

**B. Drowning in things**: 50 markdown files, contradictory
information, nobody knows what's current. Future-us can't tell what
to trust.
- Defense: distinct role per doc + write-rule per doc + an index
  (README) + this guide.

The current ~24-file count is fine because each doc has a clear
role. The problem would be **overlap**, not count. Watch for:
- Two docs explaining the same thing → consolidate or cross-link
- A doc whose role is unclear after 2 weeks → rename or merge into
  the closest existing doc
- A doc that hasn't been touched in 6 months but is in group 1
  (living runbook) → either it's stable (good) or stale (bad). Read
  it, decide.

## Sanity checks (run periodically)

1. **Every doc fits in exactly one group above.** If not, the role
   isn't clear; clarify it in the doc's own preamble.
2. **README.md's question→doc table covers every doc.** New docs
   should be linked there.
3. **No two docs claim to be the source of truth on the same topic.**
   When new info contradicts old, the new doc should say "supersedes
   X" and the old should say "see X for current info."
4. **Group 2 docs grow over time; group 1 docs don't necessarily.**
   If a runbook keeps growing it's becoming a pile-of-everything;
   split it.
