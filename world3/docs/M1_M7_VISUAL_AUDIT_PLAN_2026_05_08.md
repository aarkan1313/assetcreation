# M1-M7 Visual Audit Plan

Date: 2026-05-08

## Purpose

Run this audit after M7 and before starting M8.

The goal is to separate two different questions:

- Does the workflow/pipeline contract work?
- Does the visible output meet the AAA-quality target for the relevant camera
  range?

M7 exposed why this split matters: automatic boundary placement works, but some
source materials still make the final read weaker than the workflow.

## Scope

Review the current terrain stack from M1 through M7:

- M1 material catalog and kit bindings.
- M2 transition strip generation and hard-cut comparisons.
- M3 chunk-size/stitch evidence.
- M4 unified splat shader and OpenTopo compatibility.
- M5 walk streaming and chunk-crossing captures.
- M6 runtime cache/collision hardening plus source-material noise audit.
- M7 automatic transition-mask runtime placement.

## Audit Matrix

| Area | Evidence | Pass Question |
|------|----------|---------------|
| Catalog + provenance | `materials/catalog.json`, `CATALOG.md` | Are source, scale, maps, and validation states believable and complete? |
| Source material quality | M6 noise audit, source sheets, close captures | Which materials are production candidates vs pipeline-only? |
| Transition assets | M2 hard-cut vs transition sheets | Do strips improve hard adjacency without creating a new artifact? |
| Runtime placement | M7 captures and metrics | Are generated masks placed correctly and stable across chunk edges? |
| Chunk seams | M3/M5/M6 captures | Are geometry/material seams absent at chunk boundaries? |
| Walk view | M5-M7 walk captures | Does close/mid terrain read naturally enough for continued runtime work? |
| Iso/topdown parity | Phase C/E/gallery captures | Which older whole-kit views must migrate or retune in M12? |

## Output

Create an audit doc with:

- `PASS`: acceptable for the current workflow quality bar.
- `PIPELINE_ONLY`: useful to validate contracts, but not production-quality
  content.
- `REWORK`: blocks the next milestone unless fixed.
- `DEFER`: known issue that belongs to M9-M12 or a later deferred system.

The audit should explicitly decide whether M8 starts with organic material
cleanup only, or whether M7 needs a second visual-targeted boundary pass first.
