"""Audit whether a finite height source is safe for wrapped runtime repetition."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HEIGHTMAP = ROOT / "toporeview" / "gloss_mountain_textured_master" / "heightmap.png"
DEFAULT_META = ROOT / "toporeview" / "gloss_mountain_textured_master" / "meta.json"
DEFAULT_JSON = ROOT / "docs" / "captures" / "review" / "source_repeat_safety_gloss_mountain.json"
DEFAULT_MD = ROOT / "docs" / "SOURCE_REPEAT_POLICY_2026_05_09.md"

MEAN_WARN_M = 1.0
P95_WARN_M = 3.0
MAX_WARN_M = 8.0


def load_height_norm(path: Path) -> np.ndarray:
    img = Image.open(path)
    arr = np.asarray(img)
    if arr.ndim == 3:
        arr = arr[:, :, 0]
    arr_f = arr.astype(np.float32)
    if np.issubdtype(arr.dtype, np.integer):
        # PIL exposes 16-bit PNG mode "I" as int32. The data is still 0..65535.
        max_value = 65535.0 if int(arr.max()) <= 65535 else float(np.iinfo(arr.dtype).max)
    else:
        max_value = 1.0
    if max_value <= 0.0:
        max_value = 1.0
    return np.clip(arr_f / max_value, 0.0, 1.0)


def edge_stats(delta_m: np.ndarray) -> dict[str, float]:
    return {
        "mean_m": float(np.mean(delta_m)),
        "median_m": float(np.median(delta_m)),
        "p95_m": float(np.percentile(delta_m, 95)),
        "max_m": float(np.max(delta_m)),
    }


def edge_pass(stats: dict[str, float]) -> bool:
    return (
        stats["mean_m"] <= MEAN_WARN_M
        and stats["p95_m"] <= P95_WARN_M
        and stats["max_m"] <= MAX_WARN_M
    )


def audit(heightmap: Path, meta_path: Path) -> dict[str, Any]:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    height = load_height_norm(heightmap)
    elev_range_m = float(meta.get("elevation_range_m", 1.0))

    x_edge = np.abs(height[:, 0] - height[:, -1]) * elev_range_m
    z_edge = np.abs(height[0, :] - height[-1, :]) * elev_range_m
    x_stats = edge_stats(x_edge)
    z_stats = edge_stats(z_edge)
    x_pass = edge_pass(x_stats)
    z_pass = edge_pass(z_stats)
    wrap_safe = x_pass and z_pass

    return {
        "heightmap": str(heightmap),
        "meta": str(meta_path),
        "source_name": meta.get("name", heightmap.parent.name),
        "heightmap_size_px": [int(height.shape[1]), int(height.shape[0])],
        "world_size_m": {
            "x": float(meta.get("world_size_x_m", meta.get("world_size_m", 0.0))),
            "z": float(meta.get("world_size_z_m", meta.get("world_size_m", 0.0))),
        },
        "elevation_range_m": elev_range_m,
        "thresholds_m": {
            "mean": MEAN_WARN_M,
            "p95": P95_WARN_M,
            "max": MAX_WARN_M,
        },
        "edge_delta_m": {
            "x_wrap_left_vs_right": x_stats,
            "z_wrap_top_vs_bottom": z_stats,
        },
        "wrap_safe": wrap_safe,
        "recommended_repeat_mode": "wrap" if wrap_safe else "mirror",
        "policy_note": (
            "Use wrap only when opposite source edges are elevation-compatible. "
            "Use mirror for finite OpenTopo crops to avoid runtime height walls; "
            "use clamp only for explicit finite-footprint diagnostics."
        ),
    }


def write_markdown(path: Path, result: dict[str, Any]) -> None:
    x = result["edge_delta_m"]["x_wrap_left_vs_right"]
    z = result["edge_delta_m"]["z_wrap_top_vs_bottom"]
    status = "PASS" if result["wrap_safe"] else "FAIL"
    path.write_text(
        "\n".join(
            [
                "# Source Repeat Policy",
                "",
                "Date: 2026-05-09",
                "",
                "## Finding",
                "",
                f"- Source: `{result['source_name']}`",
                f"- Wrap-safety audit: **{status}**",
                f"- Recommended `ChunkLoader.source_repeat_mode`: "
                f"`{result['recommended_repeat_mode']}`",
                "",
                "The wall/box artifact in the source-stack auto review scene came from "
                "wrapping a finite OpenTopo height source as if its opposite edges were "
                "toroidal. They are not. When the runtime connected unrelated opposite "
                "edges, it produced a large height discontinuity.",
                "",
                "## Edge Delta Audit",
                "",
                "| Edge pair | mean m | median m | p95 m | max m |",
                "| --- | ---: | ---: | ---: | ---: |",
                f"| left/right | {x['mean_m']:.3f} | {x['median_m']:.3f} | "
                f"{x['p95_m']:.3f} | {x['max_m']:.3f} |",
                f"| top/bottom | {z['mean_m']:.3f} | {z['median_m']:.3f} | "
                f"{z['p95_m']:.3f} | {z['max_m']:.3f} |",
                "",
                "Thresholds for wrap-safe terrain are mean <= 1 m, p95 <= 3 m, "
                "and max <= 8 m on both edge pairs.",
                "",
                "## Runtime Policy",
                "",
                "- `mirror`: default for finite real-source terrain. Prevents hard "
                "source-edge height jumps while preserving local landform continuity.",
                "- `wrap`: only for sources explicitly audited as toroidal/seam-safe.",
                "- `clamp`: diagnostics only, for exposing finite-footprint boundaries.",
                "",
                "For review scenes with a source macro valid mask, invalid mask areas "
                "should be clipped or hidden, not rendered as fallback terrain. A "
                "flat material fill reads as a fake plateau and obscures the actual "
                "data boundary.",
                "",
                "## Repeated-Source Blend Mode",
                "",
                "A 2x2 or 3x3 repeated-source review is still valid as a workflow "
                "tool if it has an explicit boundary blend band. The blend has to "
                "operate on both geometry and appearance:",
                "",
                "- height samples from tile A and tile B blend over the same "
                "world-space band;",
                "- source macro albedo/orthophoto samples blend over that band;",
                "- source valid masks blend or clip consistently;",
                "- tileable detail material continues over the band so the join is "
                "not a flat blur.",
                "",
                "This is similar in spirit to material transitions, but stricter: if "
                "the height blend and texture blend disagree, the seam becomes "
                "visible as either a cliff, a smear, or a photo/geometry mismatch.",
                "",
                "## Quality Direction",
                "",
                "Mirroring is a mitigation, not the final world-generation answer. "
                "Repeated-source blend mode is useful for review and stress testing, "
                "but the production-quality path is to extract landform/material "
                "rules from OpenTopo, stream or mosaic compatible neighboring "
                "sources, and use generated procedural terrain for extension instead "
                "of repeating one identifiable real crop forever.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--heightmap", type=Path, default=DEFAULT_HEIGHTMAP)
    ap.add_argument("--meta", type=Path, default=DEFAULT_META)
    ap.add_argument("--out-json", type=Path, default=DEFAULT_JSON)
    ap.add_argument("--out-md", type=Path, default=DEFAULT_MD)
    args = ap.parse_args()

    result = audit(args.heightmap, args.meta)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_markdown(args.out_md, result)
    print(json.dumps(result["edge_delta_m"], indent=2))
    print(f"wrap_safe={result['wrap_safe']} recommended={result['recommended_repeat_mode']}")
    print(f"wrote {args.out_json}")
    print(f"wrote {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
