# W4 — project guidelines

## Ethos (binding, ordered by priority)

1. **Quality ≥ Performance/Optimization**
2. **Everything else**
3. *(far behind)* time-to-ship — no deadlines on this project

When choosing between approaches, pick the architecturally-correct one even if it costs more sessions now. Do not propose effort-saving shortcuts unless the user explicitly asks for one. Throwaway intermediates are the actual waste.

## Concrete implications

- **Performance is a feature**, not a polish pass. Build for non-flagship hardware from day one (quality-tier system, bulk operations over per-element, async over blocking). Don't write code that only runs at 60fps on a 5090.
- **Tests, types, parse-checks, headless captures, editor verification, cross-impl gates** are non-negotiable. They stay even when "the change is small."
- **Editor verification is mandatory** for any visual change. Print the launch command for the user — never background-launch Godot from the harness. (See `editor_launch_workflow.md` memory.)
- **One change at a time** during visual debugging. Headless + editor captures both per significant change.
- **Skirts use `VERTEX.y += h`**, not `=`. Heightmap displacement must preserve mesh-local Y offsets. (Discovered Stage 2 of Axis 1 Path 2.)

## Process

- Follow the active plan literally (currently `docs/plans/AXIS1_PATH2_PLAN_2026_05_12.md`). Each task: write failing test → run fail → write code → run pass → commit.
- Commits reference task numbers (e.g. `axis1: 1.4 …`).
- Methodological hard rules in `COMPACTION_HANDOFF.md` still apply.

## File encoding (Windows)

The Write tool produces UTF-16 LE on Windows. For JSON / .tscn / .tres / .gdshader, use the Python helper pattern:
```
"C:/Program Files/Python312/python.exe" -c "open('path', 'w', encoding='utf-8', newline='\\n').write('...')"
```
