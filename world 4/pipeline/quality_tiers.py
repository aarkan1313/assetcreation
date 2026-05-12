"""Quality-tier resolver (Python side).

Loads `the world 4/config/quality_tiers.json` (inside the Godot
project so the shipped game can read it via `res://config/...`),
returns a typed dict for any of the named tiers, and is the
authoritative source consumed by pipeline tools (asset baking, splat
sizing, etc).

Architecture note: consumers read named keys (cfg["ring_grid_n"]),
never the tier string. This keeps the consumer code Phase-2-ready
(custom overrides land later as a one-file extension here).

CLI usage:
    python pipeline/quality_tiers.py --tier high
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


class QualityTiersError(RuntimeError):
    """Raised for unknown tier / malformed config."""


# Keys every tier dict must define. Add to this list when introducing
# a new tier knob (and update the JSON simultaneously — the test
# `test_every_tier_has_every_known_key` is the safety net).
KNOWN_KEYS = (
    "ring_count",
    "ring_grid_n",
    "ring_grid_step_base_m",
    "heightmap_format_inner",
    "heightmap_format_outer",
    "collision_rings",
    "splat_texture_array_size",
    "splat_resolution_per_ring_m",
    "shadow_quality",
    "update_interval_s",
)


def get_config_path() -> Path:
    """Return the absolute path to quality_tiers.json.

    Resolves relative to this file:
        pipeline/quality_tiers.py
        → world 4/pipeline → world 4 → world 4/the world 4/config/quality_tiers.json
    Works regardless of CWD.
    """
    here = Path(__file__).resolve()
    w4_root = here.parent.parent
    return w4_root / "the world 4" / "config" / "quality_tiers.json"


def load_config() -> dict:
    """Read and parse the JSON config. Raises QualityTiersError on
    missing file or malformed JSON."""
    path = get_config_path()
    if not path.exists():
        raise QualityTiersError(f"config not found at {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise QualityTiersError(f"config malformed: {e}") from e


def resolve(tier: str | None = None) -> dict:
    """Resolve a tier name to its config dict.

    If `tier` is None, uses `default_tier` from the JSON.
    Result is a fresh dict copy with `_tier` set to the resolved name
    so consumers can log / display it.
    """
    cfg = load_config()
    if tier is None:
        tier = cfg.get("default_tier", "high")
    tiers = cfg.get("tiers", {})
    if tier not in tiers:
        raise QualityTiersError(
            f"unknown tier {tier!r}; known: {sorted(tiers.keys())!r}")
    out = dict(tiers[tier])
    out["_tier"] = tier
    return out


def _cli() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default=None,
                    help="Tier name (low/medium/high/ultra). Default: high.")
    args = ap.parse_args()
    cfg = resolve(args.tier)
    print(json.dumps(cfg, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
