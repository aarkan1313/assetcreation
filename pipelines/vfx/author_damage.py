"""Author damage / impact catalogue.

Per `EXPANSION_PLAN.md` Phase 5: hit reactions, blood, sparks, dust puffs,
debris. Each is a small particle/fracture preset that any ability can
reference as a secondary impact effect (Ability.impact_vfx_id).

These are deliberately *physical* - no element tint, no bloom on most.
They composite over the elemental-impact effects authored by author_grid.py.

12 effects, 4 categories:
  blood:    blood_spray_small, blood_spray_large, blood_drip
  sparks:   spark_metal, spark_stone, spark_arcane
  dust:     dust_puff_small, dust_puff_large, dust_drift
  debris:   debris_wood, debris_stone, debris_chitin
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _common_visual(palette: list[str], blend: str = "alpha", bloom: bool = False) -> dict:
    return {"palette": palette, "blend": blend,
            "background": "#00000000", "bloom": bloom}


def _particle_burst(eid: str, palette: list[str], *,
                    count: int, speed: float, spread: float, drag: float,
                    gravity: float, size: float, dur: float,
                    blend: str = "alpha", bloom: bool = False,
                    direction_deg: float = 90.0,
                    cues: list[dict] | None = None,
                    kind: str = "spell",
                    phenomenon: str = "particle",
                    archetype: str = "impact",
                    tags: list[str] | None = None,
                    export_target: str = "decal") -> dict:
    return {
        "id": eid,
        "kind": kind,
        "phenomenon": phenomenon,
        "backend": "particle_cpu",
        "duration_s": dur,
        "fps": 30,
        "bounds_px": [256, 256],
        "visual": _common_visual(palette, blend, bloom),
        "visual3d": {"billboard_mode": "y_axis", "world_size_m": 1.4},
        "backend_params": {
            "emitter": "burst",
            "count": count,
            "seed": hash(eid) & 0xFFFF,
            "initial_speed": speed,
            "speed_jitter": speed * 0.5,
            "direction_deg": direction_deg,
            "spread_deg": spread,
            "gravity": [0.0, gravity],
            "drag": drag,
            "size_px": size,
            "size_jitter": size * 0.4,
            "fade": 1.0,
            "emission_pos": [128, 160],
            "_audio_cues": cues or [{"t": 0.0, "name": "impact"}],
        },
        "gameplay": {"shape": "point", "damage_tags": [], "collision": "first_hit"},
        "element": "physical",
        "archetype": archetype,
        "tags": tags or [],
        "export_target": export_target,
        "notes": f"Damage/impact: {eid}",
    }


CATALOGUE: dict[str, list[dict]] = {
    "blood": [
        _particle_burst(
            "blood_spray_small",
            palette=["#c83a2a", "#8a1f15", "#3a0a05"],
            count=60, speed=120.0, spread=110.0, drag=0.8, gravity=240.0,
            size=4.0, dur=0.45,
            cues=[{"t": 0.0, "name": "hit"}, {"t": 0.18, "name": "settle"}],
            tags=["blood", "physical", "hit_reaction"],
        ),
        _particle_burst(
            "blood_spray_large",
            palette=["#e84a3a", "#9a1f15", "#2a0805"],
            count=140, speed=160.0, spread=140.0, drag=0.7, gravity=240.0,
            size=6.0, dur=0.6,
            cues=[{"t": 0.0, "name": "hit"}, {"t": 0.2, "name": "spray"},
                  {"t": 0.45, "name": "settle"}],
            tags=["blood", "physical", "hit_reaction", "critical"],
        ),
        _particle_burst(
            "blood_drip",
            palette=["#a02a20", "#6a1510", "#2a0606"],
            count=20, speed=10.0, spread=30.0, drag=0.4, gravity=180.0,
            size=3.0, dur=1.2,
            direction_deg=270.0,  # downward
            cues=[{"t": 0.0, "name": "drip_start"}],
            tags=["blood", "physical", "ambient"],
            export_target="3d_billboard",
        ),
    ],
    "sparks": [
        _particle_burst(
            "spark_metal",
            palette=["#fff8c2", "#ffce4a", "#a06010", "#1a0e02"],
            count=40, speed=180.0, spread=160.0, drag=1.2, gravity=80.0,
            size=2.5, dur=0.35,
            blend="additive", bloom=True,
            cues=[{"t": 0.0, "name": "clang"}, {"t": 0.1, "name": "shower"}],
            tags=["sparks", "physical", "metal"],
        ),
        _particle_burst(
            "spark_stone",
            palette=["#e6d6b8", "#b89870", "#604530", "#1a1208"],
            count=30, speed=140.0, spread=150.0, drag=1.4, gravity=120.0,
            size=2.8, dur=0.4,
            blend="additive", bloom=False,
            cues=[{"t": 0.0, "name": "thud"}, {"t": 0.18, "name": "shower"}],
            tags=["sparks", "physical", "stone"],
        ),
        _particle_burst(
            "spark_arcane",
            palette=["#e8d8ff", "#a878ff", "#5a30c0", "#1a0a3a"],
            count=50, speed=160.0, spread=360.0, drag=1.0, gravity=-30.0,
            size=3.0, dur=0.5,
            blend="additive", bloom=True,
            cues=[{"t": 0.0, "name": "chime"}, {"t": 0.25, "name": "fade"}],
            tags=["sparks", "arcane", "magical"],
        ),
    ],
    "dust": [
        _particle_burst(
            "dust_puff_small",
            palette=["#d8c89a", "#8a7250", "#3a2e1a"],
            count=45, speed=40.0, spread=160.0, drag=2.4, gravity=-15.0,
            size=12.0, dur=0.7,
            blend="alpha", bloom=False,
            cues=[{"t": 0.0, "name": "step"}, {"t": 0.5, "name": "settle"}],
            tags=["dust", "physical", "footstep"],
        ),
        _particle_burst(
            "dust_puff_large",
            palette=["#c8b890", "#7a6448", "#2a2010"],
            count=85, speed=80.0, spread=180.0, drag=2.0, gravity=-25.0,
            size=18.0, dur=1.0,
            blend="alpha", bloom=False,
            cues=[{"t": 0.0, "name": "thud"}, {"t": 0.4, "name": "billow"},
                  {"t": 0.85, "name": "settle"}],
            tags=["dust", "physical", "impact", "landing"],
            archetype="impact",
        ),
        _particle_burst(
            "dust_drift",
            palette=["#e8d8b8", "#a89070", "#382a18"],
            count=25, speed=8.0, spread=40.0, drag=1.5, gravity=-3.0,
            size=14.0, dur=2.0,
            blend="alpha", bloom=False,
            cues=[{"t": 0.0, "name": "drift_in"}],
            tags=["dust", "physical", "ambient"],
            archetype="ambient",
            kind="ambient",
            export_target="3d_billboard",
        ),
    ],
    "debris": [
        # Wood splinters: yellow-brown shards from fracture2d
        {
            "id": "debris_wood",
            "kind": "destruction",
            "phenomenon": "shatter",
            "backend": "fracture2d",
            "duration_s": 0.9,
            "fps": 24,
            "bounds_px": [256, 256],
            "visual": _common_visual(["#c89668", "#7a4828", "#2a1808"]),
            "visual3d": {"billboard_mode": "y_axis", "world_size_m": 1.3},
            "backend_params": {
                "source_shape": "ngon",
                "source_radius_px": 70.0,
                "source_n_sides": 10,
                "shard_count": 12,
                "impact_center": [128, 128],
                "gravity": [0.0, 220.0],
                "drag": 0.6,
                "burst_speed": 90.0,
                "burst_jitter": 30.0,
                "spin_max": 9.0,
                "base_color": "#a07040",
                "outline_color": "#1a1006",
                "seed": 11,
                "_audio_cues": [{"t": 0.0, "name": "crack"},
                                 {"t": 0.45, "name": "tumble"}],
            },
            "gameplay": {"shape": "point", "damage_tags": [], "collision": "first_hit"},
            "element": "physical", "archetype": "impact",
            "tags": ["debris", "physical", "wood", "destruction"],
            "export_target": "3d_billboard",
            "notes": "Wood splinter burst from a chest/door/crate hit.",
        },
        {
            "id": "debris_stone",
            "kind": "destruction",
            "phenomenon": "shatter",
            "backend": "fracture2d",
            "duration_s": 1.0,
            "fps": 24,
            "bounds_px": [256, 256],
            "visual": _common_visual(["#aaa090", "#605040", "#202018"]),
            "visual3d": {"billboard_mode": "y_axis", "world_size_m": 1.6},
            "backend_params": {
                "source_shape": "ngon",
                "source_radius_px": 80.0,
                "source_n_sides": 8,
                "shard_count": 10,
                "impact_center": [128, 128],
                "gravity": [0.0, 260.0],
                "drag": 0.45,
                "burst_speed": 70.0,
                "burst_jitter": 25.0,
                "spin_max": 6.0,
                "base_color": "#857560",
                "outline_color": "#100806",
                "seed": 13,
                "_audio_cues": [{"t": 0.0, "name": "smash"},
                                 {"t": 0.5, "name": "tumble"}],
            },
            "gameplay": {"shape": "point", "damage_tags": [], "collision": "first_hit"},
            "element": "physical", "archetype": "impact",
            "tags": ["debris", "physical", "stone", "destruction"],
            "export_target": "3d_billboard",
            "notes": "Stone chunk burst from a wall/statue/rock hit.",
        },
        {
            "id": "debris_chitin",
            "kind": "destruction",
            "phenomenon": "shatter",
            "backend": "fracture2d",
            "duration_s": 0.7,
            "fps": 24,
            "bounds_px": [256, 256],
            "visual": _common_visual(["#5a3820", "#2a1808", "#10080a"]),
            "visual3d": {"billboard_mode": "y_axis", "world_size_m": 1.1},
            "backend_params": {
                "source_shape": "ngon",
                "source_radius_px": 50.0,
                "source_n_sides": 12,
                "shard_count": 14,
                "impact_center": [128, 128],
                "gravity": [0.0, 180.0],
                "drag": 0.7,
                "burst_speed": 110.0,
                "burst_jitter": 40.0,
                "spin_max": 12.0,
                "base_color": "#3a2010",
                "outline_color": "#080404",
                "seed": 17,
                "_audio_cues": [{"t": 0.0, "name": "crunch"},
                                 {"t": 0.3, "name": "shower"}],
            },
            "gameplay": {"shape": "point", "damage_tags": [], "collision": "first_hit"},
            "element": "physical", "archetype": "impact",
            "tags": ["debris", "physical", "chitin", "creature", "destruction"],
            "export_target": "3d_billboard",
            "notes": "Chitin/shell shard burst from a creature kill.",
        },
    ],
}


KIND_DIR = {
    "spell": "spells",
    "destruction": "destruction",
    "ambient": "environment",
    "projectile": "projectiles",
}


def write_catalogue(catalog_root: Path, force: bool = False) -> tuple[int, int]:
    written = 0
    skipped = 0
    for category, effects in CATALOGUE.items():
        for eff in effects:
            kind_dir = KIND_DIR.get(eff["kind"], "spells")
            out_dir = catalog_root / kind_dir / eff["id"]
            out_dir.mkdir(parents=True, exist_ok=True)
            out = out_dir / "effect.json"
            if out.exists() and not force:
                skipped += 1
                continue
            out.write_text(json.dumps(eff, indent=2))
            written += 1
    return written, skipped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", type=Path,
                    default=Path(r"D:\assets\vfx\catalog"))
    ap.add_argument("--force", action="store_true",
                    help="Overwrite existing effect.json files.")
    args = ap.parse_args()
    written, skipped = write_catalogue(args.catalog, args.force)
    print(f"[author_damage] wrote {written} effect.json, skipped {skipped} existing "
          f"(use --force to overwrite). target: {args.catalog}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
