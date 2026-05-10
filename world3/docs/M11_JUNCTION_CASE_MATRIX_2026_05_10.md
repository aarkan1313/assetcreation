# M11 Junction Case Matrix - 2026-05-10

## Status

M11 has accepted workflow evidence for:

- Three-way/Y junction: `M11_JUNCTION_LAYER_PROOF_2026_05_10.md`.
- Four-way/corner junction: `M11_FOURWAY_CORNER_PROOF_2026_05_10.md`.

This matrix defines the cases that can actually appear once chunks are generated
from biome/material ownership fields. It prevents M11 from expanding into random
corner art.

## Strategy

Junctions are generated from continuous ownership fields, then projected into:

- shared height output;
- runtime RGBA splat weights;
- source macro guidance and valid masks;
- feature/scatter sidecar masks.

They are not painted RGB corner strips, and they are not procedural expansion
outside available source data. Source data boundaries remain explicit finite
footprints until a real adjacent stack exists.

## Case Matrix

| Case | Runtime shape | Current evidence | Status | Notes |
|------|---------------|------------------|--------|-------|
| Pairwise band | Two domains across a broad seam/ecotone | M10 seam/ecotone proofs | Accepted workflow | Owned by M10, but feeds M11 edges. |
| Three-way/Y | Three domains meet with one junction core | M11 source/grassland/canyon proof | Accepted workflow | Uses small soil/triple-core support, not a muddy strip. |
| Four-way/corner | Four explicit RGBA domains meet in one warped corner | M11 photoreal/grassland/fantasy/canyon proof | Accepted workflow | Uses all splat channels directly. |
| T-junction | One pairwise band terminates into a third domain | Derived from Y contract | Planned variant | Should reuse Y fields with one suppressed branch. |
| L-corner | Two pairwise bands bend around a dominant domain | Derived from four-way contract | Planned variant | Should reuse four-way fields with two low-weight domains. |
| Island/enclave | Small domain nested inside a dominant source field | Not yet generated | Deferred | Wait until biome solver can produce real islands. |
| Data edge | Source footprint ends with no adjacent data | Source valid-area policy | Not a junction | Must clip/show edge or use real adjacent stack, not fabricate terrain. |

## Closure Rule

For the current roadmap, M11 is complete enough to move to M12 when:

- at least one Y junction and one four-way corner render cleanly in topdown, iso,
  medium, and close review;
- both use the domain-field/splat/macro/mask contract;
- known limitations are recorded as asset-quality or future generator work, not
  hidden as accepted production art.

That bar is now met. The remaining T/L/island variants are useful next cases but
do not block M12 view-mode parity.
