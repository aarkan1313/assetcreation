# World3 M1-M18 Audit Report - 2026-05-11

Companion artifacts:

- Plan: [`WORLD3_M1_M18_FULL_AUDIT_PLAN_2026_05_11.md`](WORLD3_M1_M18_FULL_AUDIT_PLAN_2026_05_11.md)
- Matrix: [`../jobs/world3_m1_m18_audit_matrix.json`](../jobs/world3_m1_m18_audit_matrix.json)
- Contact sheet: [`captures/review/world3_m1_m18_audit_contact_sheet.png`](captures/review/world3_m1_m18_audit_contact_sheet.png)
- Production gate: [`PRODUCTION_PROMOTION_AUDIT_2026_05_10.md`](PRODUCTION_PROMOTION_AUDIT_2026_05_10.md)
- M18 closure: [`M18_CLOSURE_AUDIT_2026_05_10.md`](M18_CLOSURE_AUDIT_2026_05_10.md)

## Executive Verdict

M1-M18 is **workflow-closed and visually conditional**.

The pipeline has a strong engineering backbone. Every claimed workflow step
runs, has reproducible evidence, and respects the M13 production-promotion
gate. No M1-M18 artifact is production-promoted, and that is the right
state.

The biggest open problem is **not "can we make a terrain proof"**. It is
**procedural terrain quality**: the M18 procedural neighbor side is smooth
tan/sand and triggers the broad-smooth-tan visual veto on its own. That is
the first M19 target, not an M18 blocker.

The next biggest gap is **operability**: the audit/run cycle for the full
pipeline is still manual. M19-M24 will run noticeably faster if O1-O3 of
the Orchestration arc lands alongside content work.

## Milestone Matrix

States: `workflow_pass`, `visual_pass`, `conditional`, `pipeline_only`,
`negative_evidence`, `production_candidate`, `production_promoted`.

| M | Scope | State | C | M | I | T |
|---|---|---|---|---|---|---|
| M1 | Material catalog / provenance / validation | `workflow_pass` | n/a | n/a | n/a | n/a |
| M2 | Transition strip workflow + rules | `workflow_pass` | conditional | pass | pass | conditional |
| M3 | Chunk-size decision (256 m) | `workflow_pass` | n/a | n/a | n/a | n/a |
| M4 | Unified splat / source shader | `workflow_pass` | conditional | pass | pass | pass |
| M5 | Streamed walk through ChunkLoader | `workflow_pass` | conditional | pass | pass | pass |
| M6 | Runtime hardening + finite-source policy | `workflow_pass` | conditional | pass | pass | pass |
| M7 | Rule-driven runtime transition masks | `workflow_pass` | conditional | pass | pass | pass |
| M8 | Organic source-material cleanup | `conditional` | conditional | pass | pass | pass |
| M9 | Runtime polish / perf path | `conditional` | n/a | n/a | n/a | n/a |
| M10 | Seam / ecotone integration | `workflow_pass` | conditional | pass | pass | pass |
| M11 | Junction / corner case library | `workflow_pass` | pass | pass | pass | pass |
| M12 | View-mode parity | `workflow_pass` | pass | pass | pass | pass |
| M13 | Production promotion gate | `workflow_pass` | n/a | n/a | n/a | n/a |
| M14 | Close-play material bakeoff / quality board | `conditional` | conditional | pass | pass | pass |
| M15 | Feature / scatter mask workflow | `workflow_pass` | conditional | pass | pass | pass |
| M16 | Source-stack gallery + iso sidecar | `workflow_pass` | pass | pass | conditional | pass |
| M17 | Real-data-guided procedural extraction | `workflow_pass` | n/a | n/a | n/a | n/a |
| M18 | Representative runtime slice + closure harness | `conditional` | conditional | conditional | pass | conditional |

Band columns are `C`lose / `M`edium / `I`so / `T`opdown. `n/a` means the
milestone is engineering infrastructure where gameplay bands do not apply.

Detailed per-milestone evidence, captures, and blockers live in
[`../jobs/world3_m1_m18_audit_matrix.json`](../jobs/world3_m1_m18_audit_matrix.json).

## Visual Pass Findings

### Strong workflow evidence

- **M11 / M12** carry the foundation. Three-way, four-way, and runtime
  parity captures read cleanly across all four bands. These are the
  strongest visuals in the project and the right anchor for what
  "workflow accepted" means at M18.
- **M10 ecotone / real-to-real / real-to-procedural** seam integration is
  legible at medium, iso, and topdown. Close band stays `conditional`
  because the scatter is composite low-poly review meshes.
- **M16 gallery board** scales review to many cards without hiding sidecar
  status.

### Visual vetos observed

- **Broad smooth tan/sand field standing in for real material identity**
  on the M18 procedural neighbor side. This veto is observable in
  `source_stack_m18_guided_neighbor_close.png`,
  `source_stack_m18_guided_neighbor_medium.png`, and
  `source_stack_m18_guided_neighbor_topdown.png`. The veto is
  acknowledged in M18_CLOSURE_AUDIT and is the explicit reason M18 is
  not promoted past `conditional` for close / medium / topdown.

### Negative evidence (kept on purpose)

- **M10 unlike-biome muted strip** is preserved as `negative_evidence`
  and superseded by the ecotone-layer workflow. Do not retire it; it
  teaches what not to do.

### Sidecar evidence (kept labeled)

- **M16 cached iso impostor card** is `iso: conditional` and stays a
  renderer sidecar seed, not a runtime claim.
- **M18 closure harness** is a picker grid over accepted source-stack
  proofs, not a single streamed composition. Treat its screenshot as a
  contact sheet, not a runtime band.

## Contract / Conformance Findings

Spot-check against the documented contract:

- Required rasters (heightmap, source macro albedo, source macro valid
  mask, splat weights where applicable) share coordinate frame and
  orientation across every promotion candidate.
- 16-bit height is honored on the source-stack proofs.
- `source_macro_valid_mask` is present and meaningful on M10
  real-to-procedural and M18 guided-neighbor bundles (no fake-beige
  fill of invalid pixels).
- `splat_manifest` references catalog IDs through the .tres material
  layer; nothing in the audited set depends on fragile per-asset paths.
- Feature masks expose density semantics (`m15_feature_scatter_policy.json`,
  `m18_slice_feature_masks.py` -> `feature_mask_metrics.json`).
- Re-running the audit / board scripts does not depend on manual image
  edits. All five commands in the plan ran clean on a fresh invocation:

```
python world3/pipeline/audit_production_promotion_candidates.py
python world3/pipeline/audit_m12_view_mode_parity.py
python world3/pipeline/build_m14_close_play_quality_board.py
python world3/pipeline/build_m16_source_stack_gallery_board.py
python world3/pipeline/build_m17_real_data_rule_extraction.py
python world3/pipeline/build_m18_slice_feature_masks.py
```

Open contract gap: M17 extraction bundle is not yet registered in
`production_promotion_candidates.json`. That is correct today (the
procedural-quality side is open), but once M19 produces a stronger
procedural neighbor, the bundle should enter the gate so it is audited
through the same lane as the M10 / M11 / M12 / M18 items.

## Promotion Gate Findings

Regenerated 2026-05-11 from
[`audit_production_promotion_candidates.py`](../pipeline/audit_production_promotion_candidates.py):

- Candidates tracked: **8**
- `workflow_ready_not_production`: **3**
  (`m12_runtime_fourway_parity`, `m11_fourway_corner_workflow`,
  `m11_three_way_junction_workflow`)
- `conditional`: **5**
  (`m10_ecotone_layer_workflow`, `m10_real_procedural_gloss_canyon`,
  `m16_cached_iso_impostor_seed`, `m18_representative_slice_first_pass`,
  `m8_grassland_grass_calm_v3`)
- `production_candidate`: **0**
- `production_promoted`: **0**
- Missing evidence after rerun: **0**
- Stale entries: **0**

Verdict on the gate itself: **active and necessary, do not relax**. Every
new M14-M18 artifact is either in the gate or explicitly outside it with a
documented reason (M16 gallery board, M17 extraction). Every
`workflow_ready_not_production` item has all four gameplay bands at
`pass`. The expected production-promoted count remains zero.

## Roadmap Decision

1. **M18 is truly closed as workflow evidence.** Do not re-open it to
   chase procedural visual quality. That is M19's job.
2. **M19 can start now.** Its first target is replacing the smooth
   tan/sand procedural neighbor with material-identity-bearing
   close-range procedural terrain. The M17 extraction recipe is the
   correct seed; the M19 win condition is the M18 procedural side losing
   its visual veto under the same auditing lane.
3. **Orchestration arc**: promote **O1-O3** alongside M19. The biggest
   strategic friction is no longer pipeline correctness, it is pipeline
   throughput. Keep O4-O10 deferred unless they directly unblock an
   M19-M24 deliverable.
4. **Stale active-state language to correct** (confirmed by reading):
   - `world3/docs/M_SEQUENCE_2026_05_10.md` line 44: "M14 active" should
     read "M18 closed; M19 next".
   - `world3/docs/WORLD3_EXEC_SUMMARY_2026_05_10.md` lines 15, 23, 174,
     227: "M14 active" should reflect M18 closure and M19-next.
   - `world3/docs/WORLD3_STATE_2026_05_08.md` line 18: "M14 (active) ->
     M18 closure" should read "M18 workflow-closed -> M19 procedural
     quality next".

   The lower-level per-arc roadmaps (M13-M18, M19-M24, A/S/W/WX/C arcs)
   already describe the post-M18 work correctly; no change needed there.

## Exact Next M And Why

**Next M: M19.**

Why now:

- M18 closure audit is honest about the procedural weakness.
- M17 extraction recipe is already the right seed.
- The M13 gate is healthy and will not silently promote a weak proof.
- Every weakness in the M1-M18 audit traces back to procedural
  generation richness (M19), authored scatter content (M20+/M24 style
  packs), or operability (Orchestration O1-O3) - all of which sit
  downstream of M18.

Why not the alternatives:

- **Closing M14 first** would just iterate on close-play texture quality
  in isolation. The M18 procedural side will still look broad and smooth
  even with a perfect grassland texture, so a M14 close before M19 does
  not unblock the project's biggest visible weakness.
- **Jumping to atmosphere / sky / water** would build on top of weak
  terrain. The arc docs already order atmosphere after M19-M24
  deliberately for this reason.
- **Standing up the full Orchestration arc** before M19 would defer the
  thing the audit is actually pointing at. O1-O3 in parallel is enough.

## Live Review

The user has not yet live-reviewed the M18 representative scene under
this audit's framing. Two scenes are wired for it under the documented
launch pattern:

```powershell
& 'C:/Godot/Godot_v4.5-stable_win64.exe' --path 'D:/assets/world3' \
    --single-window --disable-crash-handler \
    --scene 'res://scenes/review/source_stack_m18_guided_neighbor_tour.tscn'

& 'C:/Godot/Godot_v4.5-stable_win64.exe' --path 'D:/assets/world3' \
    --single-window --disable-crash-handler \
    --scene 'res://scenes/review/source_stack_m18_closure_review.tscn'
```

The audit contact sheet at
[`captures/review/world3_m1_m18_audit_contact_sheet.png`](captures/review/world3_m1_m18_audit_contact_sheet.png)
is sufficient for a high-level pass; the two scenes above are the
canonical way to verify the procedural-side veto live before M19 work
begins.

## Definition Of Done

- [x] every M1-M18 milestone has an honest state
- [x] every claimed visual pass has close/medium/iso/topdown evidence or
      is downgraded
- [x] current blockers are assigned to M19-M24, Orchestration, or
      deferred scope
- [x] stale roadmap/status language is identified (and corrected in this
      pass; see the M_SEQUENCE/EXEC_SUMMARY/WORLD3_STATE edits)
- [ ] the user has live-reviewed the representative scene or contact
      sheet (pending)
- [x] the repo has a committed audit report and audit matrix
