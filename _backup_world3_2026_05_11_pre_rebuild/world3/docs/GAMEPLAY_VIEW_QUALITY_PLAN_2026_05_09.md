# Gameplay View Quality Plan - 2026-05-09

## Purpose

world3 visual quality must be judged at the camera distances the game will
actually use. Debug captures, orbit tours, and topdown sheets remain useful, but
they are not enough to close visual milestones by themselves.

This plan adds a gameplay zoom contract to the M7-M12 roadmap. It does not
replace the existing 70 percent OpenTopo reference target. It makes that target
camera-aware.

## Quality Principle

The terrain stack should split responsibilities by scale:

- Source macro imagery: landform color, broad material shifts, source truth, and
  terrain identity.
- Procedural or generated PBR detail: close-range ground grain, rock/sand/soil
  texture, and repeatable high-frequency detail.
- Masks and seam integration: height, normals, valid coverage, macro color, and
  material weights must solve together.
- Future scatter/features: vegetation clumps, stones, deadfall, buildings, roads,
  and POIs should become explicit feature layers instead of accidental source
  photo artifacts.

Source macro imagery alone should not be expected to hold up under close
first-person inspection. Close gameplay quality needs layered detail materials
and, eventually, scatter.

## Gameplay Camera Bands

### Close Play Band

Target use: character-scale movement, inspection, combat/action moments.

- Camera: roughly 1.5-8 m above ground or 4-18 m from the focus point.
- Terrain demand: no obvious texture boxes, no source-photo pixel mush, no harsh
  seam line within the near field.
- Required support: procedural/detail PBR overlays, sane normal/roughness energy,
  and source macro reduced to low-frequency contribution.
- Review status today: partially proven as workflow. Not production-closed until
  M8 texture cleanup and M12 view parity make close/mid captures repeatable.

### Medium Play Band

Target use: default exploration camera, vehicle/party travel, tactical movement.

- Camera: roughly 10-45 m from the focus point.
- Terrain demand: landforms, color families, and seams must read as intentional
  terrain, not chunk joins.
- Required support: M10 seam integration, valid-mask clipping, low-strength
  detail material, and consistent lighting/exposure.
- Review status today: the accepted M10 Gloss-Guadalupe proofs are promising in
  this band.

### Iso / Tactical Band

Target use: isometric planning, party command, editor-like overview.

- Camera: roughly 45-160 m from focus, orthographic or shallow perspective.
- Terrain demand: seam bands must disappear into plausible terrain variation;
  material regions should remain legible without noisy close-detail clutter.
- Required support: shared source/material contract across walk and iso modes.
- Review status today: M10 iso captures are valid evidence, but M12 still needs
  parity work.

### Topdown / Map Band

Target use: map, strategy layer, region review, data QA.

- Camera: roughly 120 m to full source footprint.
- Terrain demand: no fake infinite terrain, no invalid fallback plateaus, no
  obvious source rectangles unless intentionally shown as dataset boundaries.
- Required support: source valid masks, finite-footprint clipping, and explicit
  dataset-boundary policy.
- Review status today: source-boundary policy is in place; use topdown as a
  QA tool and visual screen, not as the only acceptance view.

## Acceptance Matrix

Every future visual promotion should record at least:

| Band | Required capture | Failure examples |
|------|------------------|------------------|
| Close | near 3D traverse | pixel mush, noisy grass/leaves, box patches, harsh normals |
| Medium | moving 3D traverse | height wall, color block, ghost seam, fake plateau |
| Iso | orthographic/isometric sweep | style break, repeated chunk pattern, unreadable material regions |
| Topdown | footprint or band capture | invalid data hidden as terrain, obvious source rectangle, landmark contamination |

Promotion is allowed only when the asset/workflow is clear about which bands it
passes. A workflow can be accepted while an asset remains sidecar-only.

## Immediate Roadmap Impact

1. M10 now has a first real-to-procedural workflow proof. It can move to live
   review, then unlike-biome blending if the topdown/iso/medium bands hold up.
2. M8 remains necessary for close play quality because bad generated organic
   textures still contaminate near-field reads.
3. M12 should formalize view-mode parity using this camera-band matrix.
4. Future review scenes should use named camera bands rather than ad hoc tour
   stops, so accepted quality means the same thing across walk, iso, and
   topdown.
