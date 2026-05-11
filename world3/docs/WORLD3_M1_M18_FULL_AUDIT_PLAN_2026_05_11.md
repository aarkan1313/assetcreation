# World3 M1-M18 Full Audit Plan - 2026-05-11

## Purpose

This plan defines the audit we should run after M18 before treating the
world3 terrain workflow as a stable foundation for M19-M24.

The audit answers one question:

> What should world3 have proven by M18, what did it actually prove, and what
> remains workflow-only, visually conditional, or blocked?

This is not a content-promotion pass. It is a truth-maintenance pass across
workflow, visuals, contract conformance, docs, and roadmap sequencing.

## Audit Rules

- Workflow acceptance and production quality are separate states.
- Every visual claim must be tied to close, medium, iso, and topdown evidence.
- A scene can prove a pipeline while failing the AAA visual bar.
- Generated/procedural materials are sidecar candidates until terrain-context
  review and M13 promotion say otherwise.
- Real OpenTopo/source-stack areas are reference and validation anchors; they
  are not something to stretch into fake infinite terrain.
- The M18 sand/procedural side is a known quality failure and must stay labeled
  as such.
- If evidence is missing, mark it missing. Do not infer a pass from adjacent
  work.

## Quality States

Use these states consistently in the final audit:

| State | Meaning |
|---|---|
| `workflow_pass` | The pipeline path works, is reproducible, and has enough evidence for future work. |
| `visual_pass` | The artifact meets the current visual bar for its intended view bands. |
| `conditional` | Useful evidence exists, but quality, scope, or completeness blocks promotion. |
| `pipeline_only` | Engineering proof only; screenshots are diagnostics, not art approval. |
| `negative_evidence` | A failed attempt that teaches the workflow what not to do. |
| `production_candidate` | M13 gate says all required bands and blockers are satisfied. |
| `production_promoted` | Explicitly promoted through M13. Current expected count: zero. |

## What Should Be Proven By M18

By this point, world3 should have proven:

1. **Material catalog truth**: materials have IDs, provenance, view validation,
   and honest blocker labels.
2. **Texture generation workflow**: ComfyUI/FLUX/Aura/SD candidates can be
   generated, curated, PBR-staged, and reviewed without silent promotion.
3. **Transition workflow**: same-source, unlike-biome, real-to-real, and
   real-to-procedural transitions have a repeatable seam/ecotone method.
4. **Junction workflow**: three-way and four-way/corner cases have accepted
   representative workflow evidence.
5. **Runtime source-stack contract**: height, macro color, valid masks, splat
   weights, feature masks, and metadata stay aligned.
6. **Finite-source boundary policy**: missing data does not render as fake
   beige terrain or invisible fallbacks.
7. **Chunked runtime path**: 256 m chunks, collision, material binding, and
   runtime caches work well enough for review scenes.
8. **View-mode parity**: the same terrain contract can be inspected at close,
   medium, iso, and topdown bands.
9. **Scatter/feature workflow**: masks can drive feature placement; assets are
   still placeholders unless separately promoted.
10. **Gallery/sidecar workflow**: bulk cards and cached iso experiments can be
    reviewed without confusing sidecars for runtime closure.
11. **Real-data procedural extraction**: accepted source-stack data can produce
    procedural rule targets and a compatible neighbor bundle.
12. **Representative runtime slice**: procedural neighbor output can re-enter
    the runtime path and be audited through M13.
13. **Promotion governance**: no workflow proof becomes production content
    without explicit M13 state.
14. **Roadmap readiness**: M19-M24 can start only with current weaknesses
    documented as targets, not as solved problems.

## Milestone Audit Matrix

The final audit should classify each milestone like this:

| M | Expected Proof | Required Evidence | Known Starting Read |
|---|---|---|---|
| M1 | Catalog/provenance/validation schema works. | `materials/catalog.json`, M1/M6 noise audits, validation labels. | Workflow pass; visual labels need strict truth checks. |
| M2 | Transition strips and rules can be generated. | transition assets, rules JSON, strip sheets, terrain-context shots. | Workflow pass; mixed visuals. |
| M3 | Chunk size decision is justified. | chunk sweep docs, budget notes, 256 m decision. | Workflow pass; visuals diagnostic only. |
| M4 | Unified splat/source shader path works. | shader files, splat captures, source-stack rerenders. | Workflow pass; early beauty shots are not quality evidence. |
| M5 | Streamed walk scene works. | `ChunkLoader`, walk review, collision/cache evidence. | Workflow pass; close visuals conditional. |
| M6 | Runtime hardening and finite-source policy work. | runtime cache docs, valid-mask policy, source-material noise audit. | Workflow pass; source material blockers remain. |
| M7 | Rule-driven runtime transition masks work. | boundary integration docs, mask metrics, source-stack review. | Workflow pass; visual conditional. |
| M8 | Organic material cleanup lane exists. | regen queue, Comfy inventory, terrain-context reviews. | Partial; sidecar candidates only. |
| M9 | Runtime polish/perf has a measurable path. | M5/M6 metrics, M18 smoke, hitch notes. | Partial; needs dedicated post-M18 perf pass. |
| M10 | Seam/ecotone integration works for core cases. | seam metrics, source-stack bundles, visual sheets. | Workflow accepted; unlike-biome quality remains conditional. |
| M11 | Junction/corner ownership is represented. | three-way/four-way docs, case matrix, captures. | Representative workflow accepted; not exhaustive. |
| M12 | Same contract works across close/medium/iso/topdown. | parity audit, runtime parity proof, captures. | Workflow accepted. |
| M13 | Promotion gate prevents silent over-claiming. | candidates JSON, audit report, status counts. | Active and necessary; zero production promotions expected. |
| M14 | Close-play material bakeoff/selection lane works. | quality board, bakeoff docs, sidecar staging. | Workflow useful; content not final. |
| M15 | Feature/scatter masks feed runtime review. | policy JSON, masks, scatter scene, captures. | Workflow pass; authored assets missing. |
| M16 | Source-stack gallery and iso sidecar are reviewable. | gallery manifest/board, review scene, iso card. | Workflow pass; sidecar not runtime replacement. |
| M17 | Real data can seed procedural rules. | extraction JSON/MD, guided neighbor bundle, board. | Workflow pass; procedural quality limited. |
| M18 | Full representative slice can be reviewed. | runtime slice, closure harness, M18 audit, perf smoke. | Workflow-closed / visually conditional. |

## Visual Audit Plan

### Canonical Visual Sets

Review these in order:

1. M1-M7 original diagnostic captures and source-stack remediation captures.
2. M10 same-source, real-to-real, real-to-procedural, and unlike-biome proofs.
3. M11 three-way and four-way/corner junction sheets.
4. M12 runtime parity close/medium/iso/topdown evidence.
5. M14 material bakeoff sheets and terrain-context candidates.
6. M15 feature/scatter overlay across all four bands.
7. M16 gallery cards plus cached iso sidecar.
8. M17 extraction board and procedural neighbor bundle.
9. M18 guided-neighbor tour, closure harness, and contact sheet.

### Band Checklist

Each candidate gets four independent grades:

| Band | What To Check |
|---|---|
| Close | Ground detail, scatter scale, texture noise, object repeats, seams, lighting. |
| Medium | Landform readability, material transitions, cliffs/slopes, feature density. |
| Iso | Tactical readability, silhouettes, material identity, no visual clutter. |
| Topdown | Biome shape, transition fields, map readability, no straight fake strips. |

### Visual Vetoes

Any of these prevents visual pass:

- hard source-data wall presented as terrain
- broad smooth tan/sand field standing in for real material identity
- straight muted transition strip with no ecological/ecotone structure
- visible square/box seams, 2x2 paneling, or center-cross artifacts
- repeated object-like grass/leaves/lichen that reads as stamps
- overbright lighting, white background glare, or bloom masking quality
- low-resolution smear in a close/medium gameplay band
- scatter objects that float, clip badly, or break iso/topdown readability
- hidden sidecar/prototype renderer presented as runtime parity

## Contract And Pipeline Audit

Check the output contract against the current artifacts:

- Required rasters share coordinate frame and orientation.
- Height encodings are 16-bit where claimed and normalized correctly.
- `source_macro_valid_mask` accurately marks invalid source coverage.
- `splat_manifest` references catalog IDs, not fragile paths.
- Feature masks and scatter manifests use documented density semantics.
- Chunk metadata is derivable from the parent bundle.
- Generator/provenance metadata identifies source, script, and git ref where
  available.
- Re-running a pipeline step does not depend on manual image edits.

Minimum command checks for the audit run:

```powershell
python world3/pipeline/audit_production_promotion_candidates.py
python world3/pipeline/audit_m12_view_mode_parity.py
python world3/pipeline/build_m14_close_play_quality_board.py
python world3/pipeline/build_m16_source_stack_gallery_board.py
python world3/pipeline/build_m17_real_data_rule_extraction.py
python world3/pipeline/build_m18_slice_feature_masks.py
```

Use explicit Godot `--scene` launches for visual review. Do not use hidden
window launches for scenes that need real viewport validation.

```powershell
& 'C:/Godot/Godot_v4.5-stable_win64.exe' --path 'D:/assets/world3' --single-window --disable-crash-handler --scene 'res://scenes/review/source_stack_m18_guided_neighbor_tour.tscn'
& 'C:/Godot/Godot_v4.5-stable_win64.exe' --path 'D:/assets/world3' --single-window --disable-crash-handler --scene 'res://scenes/review/source_stack_m18_closure_review.tscn'
```

## Promotion Gate Audit

The M13 audit must answer:

- How many candidates exist?
- Which are `workflow_ready_not_production`, `conditional`, or rejected?
- Are any accidentally stale or missing evidence?
- Does every new M14-M18 artifact have a candidate entry or an explicit reason
  it is not tracked?
- Are all four gameplay bands present for any item that claims promotion?
- Is production-promoted count still zero unless we made an explicit decision?

Expected current answer: no production-promoted terrain content.

## Roadmap And Scope Audit

The final audit must decide:

1. Whether M18 is truly closed as workflow evidence.
2. Whether M19-M24 can start with M18 sand/procedural weakness as the first
   target.
3. Whether the Orchestration arc should promote now, partially promote, or stay
   deferred.
4. Whether `M_SEQUENCE_2026_05_10.md` still has stale "M14 active" language
   after M18 closure.
5. Whether `ROADMAP.md`, `WORKFLOW.md`, and the executive summary point to the
   same current state.

Recommendation going into the audit:

- Start M19 only after the audit report exists.
- Promote at least O1-O3 as near-term operability work if the audit confirms
  manual workflow friction is now slowing quality iteration.
- Keep O4-O10 deferred unless they directly unblock M19-M24.

## Final Audit Deliverables

Produce these artifacts:

- `world3/docs/WORLD3_M1_M18_AUDIT_REPORT_2026_05_11.md`
- `world3/jobs/world3_m1_m18_audit_matrix.json`
- `world3/docs/captures/review/world3_m1_m18_audit_contact_sheet.png`
- Updated `PRODUCTION_PROMOTION_AUDIT_2026_05_10.md`
- Updated roadmap/status docs with one current active pointer

The report should contain:

- executive verdict
- milestone matrix
- visual pass findings
- contract/conformance findings
- promotion gate findings
- roadmap decision
- exact next M and why

## Definition Of Done

The M1-M18 audit is complete when:

- every M1-M18 milestone has an honest state
- every claimed visual pass has close/medium/iso/topdown evidence or is
  downgraded
- current blockers are assigned to M19-M24, Orchestration, or deferred scope
- all stale roadmap/status language is corrected
- the user has live-reviewed the representative scene or contact sheet
- the repo has a committed audit report and audit matrix

## Known Findings Before Running

These are not final findings, but they are known enough to seed the audit:

- The source-stack workflow is the project backbone and should be preserved.
- M10/M11/M12 are strong workflow evidence.
- M13 is essential; do not relax it.
- M14/M15 are workflow-useful but content-light.
- M16 is useful for review scale and iso research, but sidecar evidence must
  stay labeled sidecar.
- M17/M18 prove procedural re-entry, not procedural quality.
- M18 sand/procedural terrain is visually weak and should drive M19 rather than
  block M19 entirely.
- The biggest strategic gap is no longer "can we make a terrain proof"; it is
  "can we run and audit the whole pipeline quickly and repeatedly."
