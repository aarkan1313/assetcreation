"""Author the 24-cell element x archetype effect grid.

Per `EXPANSION_PLAN.md` Phase 5: hand-author `effect.json` entries covering
arcane/elemental schools (fire/ice/lightning/earth/arcane/shadow x
projectile/burst/aura/impact = 24 cells). Wires `Effect.id` into
`Ability.vfx_id` so game_data abilities have real referenced VFX.

This is a *generator*, not a baker. It writes 24 (or N filtered) effect.json
files that the existing bakers (particle_cpu, smoke_field) can consume.

Idempotency: if `vfx/catalog/<kind>/<id>/effect.json` already exists, the
generator skips it (use `--force` to overwrite). Audio cues are added to
`backend_params._audio_cues` (consumed by the baker via the manifest's
extras pipeline below) so AudioCueBus has work to do at runtime.

Element palettes are tuned for the AAA/painterly aesthetic the asset
factory targets - all four palette stops are pre-baked through the lifecycle
(bright -> medium -> dark -> ash). Archetype params follow these contracts:

  projectile: omni-burst, additive, ~0.6s, 100-140 particles, drag~1.4
  burst:      directional explosion, ~0.5s, 160-200 particles, no gravity
  aura:       smoke_field, slow rise, ~1.6s, persistent low-emission
  impact:     short downward cone, ~0.35s, 80-120 particles, gravity, settles
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# --- element palettes (4-stop life-cycle: bright -> medium -> dark -> ash) ---

ELEMENTS: dict[str, dict] = {
    "fire": {
        "palette": ["#fff7c2", "#ffae3b", "#c83a2a", "#3a0a06"],
        "blend": "additive", "bloom": True, "tag": "fire",
        "size_mult": 1.0, "speed_mult": 1.0,
    },
    "ice": {
        "palette": ["#e8faff", "#9ad6ff", "#3a8fcd", "#0d2a4a"],
        "blend": "additive", "bloom": True, "tag": "frost",
        "size_mult": 0.85, "speed_mult": 1.1,
    },
    "lightning": {
        "palette": ["#fcfcff", "#bce8ff", "#7a4fdb", "#1a0a3a"],
        "blend": "additive", "bloom": True, "tag": "shock",
        "size_mult": 0.7, "speed_mult": 1.6,
    },
    "earth": {
        "palette": ["#d8c79a", "#a07a4a", "#553820", "#1a120a"],
        "blend": "alpha", "bloom": False, "tag": "physical",
        "size_mult": 1.2, "speed_mult": 0.7,
    },
    "arcane": {
        "palette": ["#f5e8ff", "#d8a8ff", "#7a4fdb", "#2a0a4a"],
        "blend": "additive", "bloom": True, "tag": "arcane",
        "size_mult": 1.0, "speed_mult": 1.0,
    },
    "shadow": {
        "palette": ["#9b4ad0", "#5a2a90", "#2a0a40", "#0a0010"],
        "blend": "alpha", "bloom": True, "tag": "necrotic",
        "size_mult": 1.1, "speed_mult": 0.85,
    },
}


# --- archetype templates ---

def _projectile(elem_key: str, elem: dict) -> dict:
    return {
        "kind": "projectile",
        "phenomenon": {
            "fire": "fire", "ice": "particle", "lightning": "lightning",
            "earth": "particle", "arcane": "particle", "shadow": "smoke",
        }[elem_key],
        "backend": "particle_cpu",
        "duration_s": 0.6,
        "fps": 24,
        "bounds_px": [256, 256],
        "visual": {
            "palette": elem["palette"], "blend": elem["blend"],
            "background": "#00000000", "bloom": elem["bloom"],
        },
        "visual3d": {"billboard_mode": "y_axis", "world_size_m": 1.5},
        "backend_params": {
            "emitter": "burst",
            "count": 110,
            "seed": hash(f"{elem_key}_projectile") & 0xFFFF,
            "initial_speed": 25.0 * elem["speed_mult"],
            "speed_jitter": 55.0 * elem["speed_mult"],
            "direction_deg": 90.0,
            "spread_deg": 360.0,
            "gravity": [0.0, -8.0],
            "drag": 1.4,
            "size_px": 8.0 * elem["size_mult"],
            "size_jitter": 3.5,
            "fade": 1.0,
            "emission_pos": [128, 128],
            "_audio_cues": [
                {"t": 0.0, "name": "spawn"},
                {"t": 0.35, "name": "tail"},
            ],
        },
        "gameplay": {
            "shape": "projectile",
            "damage_tags": [elem["tag"]],
            "collision": "first_hit",
        },
        "element": elem_key, "archetype": "projectile",
        "tags": [elem_key, "projectile", elem["tag"]],
        "export_target": "3d_billboard",
    }


def _burst(elem_key: str, elem: dict) -> dict:
    return {
        "kind": "spell",
        "phenomenon": {
            "fire": "fire", "ice": "shatter", "lightning": "lightning",
            "earth": "particle", "arcane": "particle", "shadow": "smoke",
        }[elem_key],
        "backend": "particle_cpu",
        "duration_s": 0.5,
        "fps": 30,
        "bounds_px": [320, 320],
        "visual": {
            "palette": elem["palette"], "blend": elem["blend"],
            "background": "#00000000", "bloom": elem["bloom"],
        },
        "visual3d": {"billboard_mode": "enabled", "world_size_m": 2.5},
        "backend_params": {
            "emitter": "burst",
            "count": 180,
            "seed": hash(f"{elem_key}_burst") & 0xFFFF,
            "initial_speed": 80.0 * elem["speed_mult"],
            "speed_jitter": 80.0 * elem["speed_mult"],
            "direction_deg": 90.0,
            "spread_deg": 360.0,
            "gravity": [0.0, 0.0],
            "drag": 1.6,
            "size_px": 7.0 * elem["size_mult"],
            "size_jitter": 4.0,
            "fade": 1.0,
            "emission_pos": [160, 160],
            "_audio_cues": [
                {"t": 0.0, "name": "burst"},
                {"t": 0.30, "name": "settle"},
            ],
        },
        "gameplay": {
            "shape": "aura",
            "damage_tags": [elem["tag"]],
            "collision": "pierce",
        },
        "element": elem_key, "archetype": "burst",
        "tags": [elem_key, "burst", "aoe", elem["tag"]],
        "export_target": "3d_billboard",
    }


def _aura(elem_key: str, elem: dict) -> dict:
    return {
        "kind": "ambient",
        "phenomenon": "smoke" if elem_key in ("shadow", "earth") else "field",
        "backend": "smoke_field",
        "duration_s": 1.6,
        "fps": 18,
        "bounds_px": [192, 192],
        "visual": {
            "palette": elem["palette"][:3],
            "blend": elem["blend"],
            "background": "#00000000",
            "bloom": elem["bloom"],
        },
        "visual3d": {"billboard_mode": "y_axis", "world_size_m": 3.0},
        "backend_params": {
            "grid_size": 64,
            "seed": hash(f"{elem_key}_aura") & 0xFFFF,
            "emit_pos": [0.5, 0.85],
            "emit_radius": 4.0,
            "emit_density": 4.5,
            "buoyancy": -7.0 if elem_key != "shadow" else 4.0,
            "dissipation": 0.5,
            "viscosity": 0.45,
            "_audio_cues": [
                {"t": 0.0, "name": "loop_in"},
                {"t": 1.2, "name": "loop_out"},
            ],
        },
        "gameplay": {"shape": "aura", "damage_tags": [elem["tag"]], "collision": "none"},
        "element": elem_key, "archetype": "aura",
        "tags": [elem_key, "aura", "buff", elem["tag"]],
        "export_target": "decal",
    }


def _impact(elem_key: str, elem: dict) -> dict:
    return {
        "kind": "destruction" if elem_key == "earth" else "spell",
        "phenomenon": {
            "fire": "fire", "ice": "shatter", "lightning": "lightning",
            "earth": "rubble", "arcane": "particle", "shadow": "smoke",
        }[elem_key],
        "backend": "particle_cpu",
        "duration_s": 0.4,
        "fps": 30,
        "bounds_px": [256, 256],
        "visual": {
            "palette": elem["palette"],
            "blend": elem["blend"],
            "background": "#00000000",
            "bloom": elem["bloom"],
        },
        "visual3d": {"billboard_mode": "y_axis", "world_size_m": 1.8},
        "backend_params": {
            "emitter": "burst",
            "count": 95,
            "seed": hash(f"{elem_key}_impact") & 0xFFFF,
            "initial_speed": 70.0 * elem["speed_mult"],
            "speed_jitter": 35.0,
            "direction_deg": 90.0,    # spawn pointed up; gravity pulls down
            "spread_deg": 90.0,
            "gravity": [0.0, 110.0],
            "drag": 1.0,
            "size_px": 6.5 * elem["size_mult"],
            "size_jitter": 2.5,
            "fade": 1.0,
            "emission_pos": [128, 200],   # ground line near bottom
            "_audio_cues": [
                {"t": 0.0, "name": "impact"},
                {"t": 0.18, "name": "shower"},
                {"t": 0.32, "name": "settle"},
            ],
        },
        "gameplay": {
            "shape": "point",
            "damage_tags": [elem["tag"]],
            "collision": "first_hit",
        },
        "element": elem_key, "archetype": "impact",
        "tags": [elem_key, "impact", elem["tag"]],
        "export_target": "decal",
    }


ARCHETYPES = {
    "projectile": _projectile,
    "burst": _burst,
    "aura": _aura,
    "impact": _impact,
}


def kind_for_archetype(arch: str) -> str:
    """Maps the catalog folder kind for each archetype."""
    return {
        "projectile": "projectiles",
        "burst": "spells",
        "aura": "spells",
        "impact": "spells",
    }[arch]


def build_one(elem_key: str, arch: str) -> tuple[str, str, dict]:
    elem = ELEMENTS[elem_key]
    eff = ARCHETYPES[arch](elem_key, elem)
    eid = f"{elem_key}_{arch}"
    eff["id"] = eid
    eff.setdefault("notes",
                   f"Auto-authored {elem_key} {arch} from element-archetype grid.")
    return kind_for_archetype(arch), eid, eff


def write_grid(catalog_root: Path, force: bool = False,
               only_elements: list[str] | None = None,
               only_archetypes: list[str] | None = None) -> tuple[int, int]:
    written = 0
    skipped = 0
    elements = only_elements or list(ELEMENTS.keys())
    archetypes = only_archetypes or list(ARCHETYPES.keys())
    for ek in elements:
        for ak in archetypes:
            kind_dir, eid, eff = build_one(ek, ak)
            out_dir = catalog_root / kind_dir / eid
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
    ap.add_argument("--elements", nargs="+",
                    help="Limit to specific elements (default: all 6).")
    ap.add_argument("--archetypes", nargs="+",
                    help="Limit to specific archetypes (default: all 4).")
    args = ap.parse_args()
    written, skipped = write_grid(
        args.catalog, args.force,
        only_elements=args.elements,
        only_archetypes=args.archetypes,
    )
    print(f"[author_grid] wrote {written} effect.json, skipped {skipped} existing "
          f"(use --force to overwrite). target: {args.catalog}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
