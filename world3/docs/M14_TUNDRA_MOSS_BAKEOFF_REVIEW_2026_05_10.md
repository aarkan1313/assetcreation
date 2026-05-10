# M14 Tundra Moss Bakeoff Review - 2026-05-10

## Purpose

Review the first M14 bakeoff attempts for `tundra_moss`, whose blocker is
high-frequency moss speckle and object-like colored clusters at close gameplay
scale.

The corrected target is a low tundra peat/moss substrate. Tundra identity
should come from M15 feature layers: cushion islands, lichen patches, tiny
plants, stones, and sparse scatter. M14 should not bake those readable objects
into a repeating flat texture.

## Evidence

| Attempt | Grid | Summary |
|---------|------|---------|
| v1 | `world3/docs/captures/m14/m14_tundra_moss_substrate_v1_grid_final.png` | `world3/docs/captures/m14/m14_tundra_moss_substrate_v1_summary.json` |
| v2 | `world3/docs/captures/m14/m14_tundra_moss_substrate_v2_grid_final.png` | `world3/docs/captures/m14/m14_tundra_moss_substrate_v2_summary.json` |
| v3 | `world3/docs/captures/m14/m14_tundra_moss_peatfelt_v3_grid_final.png` | `world3/docs/captures/m14/m14_tundra_moss_peatfelt_v3_summary.json` |
| FLUX-only 10x | `world3/docs/captures/m14/m14_tundra_moss_flux10_contact_sheet_final.png` | `world3/docs/captures/m14/m14_tundra_moss_flux10_summary.json` |
| FLUX shortlist | `world3/docs/captures/m14/m14_tundra_moss_flux10_candidates_single_2x2.png` | `world3/docs/captures/m14/m14_tundra_moss_flux10_candidates_summary.json` |
| FLUX-only 50x | `world3/docs/captures/m14/m14_tundra_moss_flux50_contact_sheet_final.png` | `world3/docs/captures/m14/m14_tundra_moss_flux50_summary.json` |
| FLUX 50 shortlist | `world3/docs/captures/m14/m14_tundra_moss_flux50_shortlist6_single_2x2.png` | `world3/docs/captures/m14/m14_tundra_moss_flux50_shortlist6_summary.json` |

## Attempt v1

Prompt direction: low tundra moss and organic peat substrate with muted olive
brown cushion texture.

Visual result:

- FLUX produced repeated moss/cushion plant objects. Useful as scatter
  reference, rejected as a tiling material.
- AuraFlow produced a very dark continuous organic substrate with the best seam
  score, but it risked black crush and under-reading as moss.
- SD 3.5 produced large moss/stone object blobs. Reject.

## Attempt v2

Prompt direction: lighter sage/olive-brown moss nap and peaty mineral soil.

Visual result:

- FLUX retained repeated cushion/tuft patterning. Reject as material.
- AuraFlow became lighter but introduced small plant clumps and object
  landmarks. Reject relative to v3.
- SD 3.5 again produced large moss/stone object blobs. Reject.

## Attempt v3

Prompt direction: subarctic peat felt substrate with diffuse olive-brown moss
staining, fine organic fibers, and no cushions/clumps.

Visual result:

- AuraFlow has a dark continuous peat/felt substrate with subtle fiber texture
  and excellent seam score, but live visual review rejected it as effectively
  black for the target.
- FLUX is more visibly plant-like and still repeats small moss objects. Keep as
  scatter/reference direction, not material.
- SD 3.5 is still large object blobs and is rejected.

## FLUX-Only 10x Review

User correction: the AuraFlow v3 route is too black. The workflow was adjusted
to run FLUX only, which cuts the active bakeoff from three models to one model.
After initial warmup, healed FLUX candidates ran at about 10 seconds each.

Prompt direction: weathered subarctic peat soil with faint olive moss film,
medium value, no black crush, no cushions/clumps/tufts.

Visual shortlist:

- `m14_tundra_moss_flux10_202605192`: safest substrate candidate. Muted, low
  object risk, good seam score (`0.0069`).
- `m14_tundra_moss_flux10_202605191`: more fine organic variation, slightly
  busier, good seam score (`0.0074`).
- `m14_tundra_moss_flux10_202605194`: strongest moss-patch read, but highest
  risk of visible moss objects/repetition among the three, good seam score
  (`0.0070`).

Rejected from shortlist:

- `m14_tundra_moss_flux10_202605198`: initially promising in single-tile view
  but shows visible repeat/cross structure in the 2x2 review.

## FLUX-Only 50x Review

User correction: production should not accept the first plausible texture. The
workflow was expanded from a 10-candidate FLUX check to a 50-candidate FLUX
family sweep. This keeps the fast lane fast while testing prompt families
instead of betting on one phrasing.

Prompt families:

- A: original medium-value subarctic peat soil with faint olive moss film.
- B: pale sage peat-loam substrate, low object count, not black.
- C: cold mineral soil with moss stain.
- D: pressed organic felt with stronger moss read.
- E: damp peat and moss film, not black.

Visual result:

- Family B is the strongest substrate direction. It is pale and may read more
  like tundra mineral/lichen ground than full moss, but it avoids the black
  failure and has the lowest object-repeat risk.
- Family A remains useful as a more moss-colored fallback, but its patch shapes
  are more readable as repeated flat moss islands.
- Family C has a visible 2x2 repeat/cross risk and more circular moss objects.
- Family D reads more mossy, but the pattern becomes an obvious repeating
  network at terrain scale.
- Family E trends darker and patchier; keep only as a damp-peat reference.

Current orchestrator shortlist for live user review:

1. `m14_tundra_moss_flux50_b_202605207` (`b8`): cleanest pale substrate,
   seam score `0.0074`.
2. `m14_tundra_moss_flux50_b_202605203` (`b4`): pale low-object substrate,
   seam score `0.0086`.
3. `m14_tundra_moss_flux50_b_202605204` (`b5`): similar pale low-object
   substrate, but slightly stronger repeated wisps, seam score `0.0086`.

Fallbacks:

- `m14_tundra_moss_flux10_202605192` (`a3`): more moss-colored, safer than
  early attempts, but patchier than the B-family candidates.
- `m14_tundra_moss_flux50_c_202605212` (`c3`) and
  `m14_tundra_moss_flux50_d_202605229` (`d10`) are useful references but not
  preferred sidecar candidates because the 2x2 review exposes repetition.

## Decision

Do not promote the black AuraFlow v3 candidate. Do not treat the first FLUX
winner as sufficient. Use the FLUX-only 50-candidate shortlist as the active
candidate pool for `tundra_moss` sidecar testing.

The current preferred order is:

1. `m14_tundra_moss_flux50_b_202605207`
2. `m14_tundra_moss_flux50_b_202605203`
3. `m14_tundra_moss_flux50_b_202605204`

None of these are production-promoted. They are brighter, more reviewable
substrate/material candidates. M15 should still carry readable moss cushions,
lichen islands, small stones, and sparse tundra vegetation.

Workflow note: for organic blockers, use broad curation. Start with a small
multi-model bakeoff to identify the viable lane, then run 10-50 same-model
prompt-family samples and reject by 2x2 visual review before spending time on
PBR derivation or runtime staging.

## Next Action

The B-family direction was accepted for sidecar staging. Runtime evidence is
recorded in `world3/docs/M14_TUNDRA_MOSS_RUNTIME_SIDECAR_REVIEW_2026_05_10.md`.
`m14_tundra_moss_flux50_b_202605207` has a conditional smoke pass in a Gloss
real-source context, but remains sidecar-only. Before M13 promotion, validate:

- close view: moss detail without black crush or object-repeat clumps
- medium/iso/topdown: no repeated dark striping or object islands
- tundra source context: substrate supports, rather than replaces, authored
  moss/lichen scatter
