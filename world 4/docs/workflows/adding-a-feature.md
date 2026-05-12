# Workflow — adding a feature

> The W4 way to ship anything non-trivial. Skips for one-line bug fixes
> or doc edits. For everything else, this is the spec → plan → execute
> loop.

## The flow

```
brainstorming skill        →  superpowers/specs/YYYY-MM-DD-<topic>-design.md
        ↓
writing-plans skill        →  superpowers/plans/YYYY-MM-DD-<topic>.md
        ↓
executing-plans skill      →  task-by-task commits
        ↓
build-note + STATE update  →  build-notes/<TOPIC>_BUILD_NOTES_YYYY_MM_DD.md
                              + edit STATE.md "Active work" → "Worlds" + tests
```

## Step-by-step

### 1. Brainstorm (always)

Invoke the `superpowers:brainstorming` skill. The agent will:
- check project context (recent commits, existing docs)
- ask clarifying questions one at a time
- propose 2-3 approaches with trade-offs
- write the spec to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
- ask you to review the spec before continuing

**Don't skip brainstorming, even for "simple" features.** It's where unstated assumptions get caught. See `quality-tiers` (2026-05-12) — the brainstorm revealed that the source-of-truth choice (JSON vs GDScript) had implications for asset-pipeline tooling that wouldn't have surfaced if I'd just started typing.

### 2. Plan (after spec approved)

The brainstorming skill auto-invokes `superpowers:writing-plans`. The plan:
- maps each spec requirement to a task
- breaks each task into bite-sized steps (write failing test → code → pass → commit)
- shows exact code, exact commands, exact expected output
- saves to `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`

Review the plan before executing. Catch issues like wrong file paths, missing tests, contradictions between tasks.

### 3. Execute

Two execution modes (the writing-plans skill will offer the choice):

- **Subagent-driven** (recommended for independent tasks): one fresh subagent per task, review between tasks. Best when tasks are mostly independent.
- **Inline** (recommended for tight sequences): execute in this session. Best when each task builds directly on the previous one.

Either way, follow the plan literally. If you discover a plan bug mid-execution, fix it and document the deviation in the commit message.

### 4. Build-note

After all tasks land and tests pass, write a build-note at
`docs/build-notes/<TOPIC>_BUILD_NOTES_YYYY_MM_DD.md`. Cover:

- What shipped (one paragraph)
- Test status (X/Y passing, what changed)
- Plan deviations and why
- Lessons learned (new pitfall entries? new tooling?)
- Captures, if visual

The build-note is "what was shipped, lessons" — different from the spec (which is "what we will build, why") and the plan (which is "how, step by step").

### 5. STATE.md refresh

Update `docs/STATE.md`:
- Move the work from "Active work" to "Worlds" or "Code inventory" as appropriate.
- Update test count in "Test inventory".
- Add new pitfalls to the count in "Known pitfalls".

This is the cheap-but-easy-to-forget step. It's part of the workflow specifically because skipping it makes the next fresh-Claude take longer to orient.

## When to skip the flow

- **Pure doc edits** — just commit.
- **One-line bug fixes** with a unit test — just commit with a tight message.
- **Reverting a bad commit** — `git revert`, write a build-note if the bad commit had a build-note.

For everything else: spec → plan → execute. The cost of the flow is one extra brainstorm turn, which is small compared to the cost of building the wrong thing.

## Common failure modes

- **Skipping brainstorming "because the feature is simple"**: the feature is rarely as simple as it looks. The brainstorm catches the part you didn't see.
- **Plan with "TODO" placeholders**: the writing-plans skill has a self-review step that catches these. If you see one slip through, it's a plan bug — fix the plan before executing.
- **Inline execution drift**: tasks getting bigger than 2-5 minutes. Stop and re-task. Bite-sized is the whole point.
- **Forgetting the build-note**: future-you will not know what shipped. Always write the build-note.

## Cross-references

- Skill: `superpowers:brainstorming` (lives in `~/.claude/plugins/.../brainstorming/`)
- Skill: `superpowers:writing-plans`
- Skill: `superpowers:executing-plans`
- Skill: `superpowers:subagent-driven-development`
- Example spec: `docs/superpowers/specs/2026-05-12-quality-tiers-design.md`
- Example plan: `docs/superpowers/plans/2026-05-12-quality-tiers.md`
- Example build-note: `docs/build-notes/AXIS6_BUILD_NOTES_2026_05_12.md`
