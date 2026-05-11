"""Phase F.5a — derive catalog demand from a world plan.

Computes "which materials does this plan need that we don't have at
acceptable gate state," and prioritizes remediation using F.4
transition audit verdicts when present.

Output: world3/jobs/catalog_demand/<plan_id>.json with three buckets:

- have:    materials referenced by the plan that exist AND passed_gate=true
- need:    materials referenced by the plan that don't exist in the catalog
- below_promotion_bar: materials that exist but passed_gate=false

Plus a prioritized work_queue with per-material recommended_action drawn
from F.4 audit results (if a transition audit for this plan exists).

Usage:
    python world3/pipeline/derive_catalog_demand.py world3/jobs/examples/world_plan_starter_5biome_procedural.json
    python world3/pipeline/derive_catalog_demand.py <plan> --json

Exit codes: 0 ok / 2 plan unreadable
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORLD3 = Path(__file__).resolve().parents[1]
CATALOG_PATH = WORLD3 / "materials" / "catalog.json"
WGV3_DIR = WORLD3 / "textures" / "wgv3"
TRANSITION_AUDITS_DIR = WORLD3 / "jobs" / "transition_audits"
DEMAND_OUT_DIR = WORLD3 / "jobs" / "catalog_demand"

# Action priority: palette_lock is cheapest (cross-material variant),
# regenerate is heaviest (rebuild material), shader_blend_band is runtime
# (not catalog work).
ACTION_PRIORITY = {
    "palette_lock": 0,
    "regenerate": 1,
    "shader_blend_band": 2,
    "none": 3,
    "fix_catalog": -1,   # missing material — highest priority (precedes everything)
}


def load_catalog() -> dict[str, dict]:
    """Return {material_id: {...}} keyed for fast lookup."""
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(f"catalog not found at {CATALOG_PATH}")
    cat = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    out = {}
    for m in cat.get("materials", []):
        out[m["id"]] = m
    return out


def passed_gate(mat: dict) -> bool:
    return bool(mat.get("provenance", {}).get("passed_gate", False))


def material_on_disk(material_id: str) -> bool:
    return (WGV3_DIR / material_id / "albedo.png").exists()


def load_transition_audit(plan_id: str) -> dict | None:
    path = TRANSITION_AUDITS_DIR / f"{plan_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def collect_plan_materials(plan: dict) -> list[dict]:
    """Walk plan.biomes and (per-tile source_overrides) to collect every
    material_id referenced. Returns a list of {material_id, biome_id, role}."""
    seen: dict[tuple[str, str], dict] = {}

    for biome in plan["biomes"]:
        bid = biome["id"]
        prim = biome.get("primary_material_id")
        if prim:
            seen[(prim, bid)] = {"material_id": prim, "biome_id": bid, "role": "primary"}
        src = biome.get("source", {})
        if src.get("type") == "procedural":
            mid = src.get("material_id")
            if mid:
                seen[(mid, bid)] = {"material_id": mid, "biome_id": bid, "role": "source"}
        elif src.get("type") == "hybrid":
            proc = src.get("procedural", {})
            mid = proc.get("material_id")
            if mid:
                seen[(mid, bid)] = {"material_id": mid, "biome_id": bid, "role": "source"}

    # Per-tile source_overrides
    for entry in plan.get("biome_layout", []):
        ovr = entry.get("source_override")
        if not ovr:
            continue
        if ovr.get("type") == "procedural":
            mid = ovr.get("material_id")
            if mid:
                seen[(mid, entry["biome"])] = {"material_id": mid, "biome_id": entry["biome"], "role": "tile_override"}
        elif ovr.get("type") == "hybrid":
            proc = ovr.get("procedural", {})
            mid = proc.get("material_id")
            if mid:
                seen[(mid, entry["biome"])] = {"material_id": mid, "biome_id": entry["biome"], "role": "tile_override"}

    return list(seen.values())


def derive_work_queue(have: list[dict], need: list[dict], below: list[dict],
                       audit: dict | None) -> list[dict]:
    """Per-material remediation work, prioritized."""
    work: list[dict] = []

    # Missing materials: highest priority — must be generated before plan works
    for entry in need:
        work.append({
            "material_id": entry["material_id"],
            "biome_id": entry["biome_id"],
            "action": "fix_catalog",
            "priority": ACTION_PRIORITY["fix_catalog"],
            "reason": f"material '{entry['material_id']}' referenced by plan but not in catalog",
            "driver_hint": "pipelines/textures/aaa_texture.py",
        })

    # Materials below gate: regenerate or finish their gate work
    for entry in below:
        work.append({
            "material_id": entry["material_id"],
            "biome_id": entry["biome_id"],
            "action": "regenerate",
            "priority": ACTION_PRIORITY["regenerate"],
            "reason": "material exists but passed_gate=false (catalog rejection or not yet graded)",
            "driver_hint": "pipelines/textures/aaa_texture.py (regenerate); or finish M13 gate review",
        })

    # Audit-driven: failing pairs surface per-material work
    if audit:
        for pair in audit.get("pairs", []):
            if pair["verdict"] not in ("warn", "fail"):
                continue
            action = pair.get("recommended_action", "none")
            if action == "shader_blend_band":
                # Runtime work, NOT catalog work — surface but don't queue
                continue
            for mat_key in ("material_a", "material_b"):
                mid = pair[mat_key]
                bid = pair["biome_a"] if mat_key == "material_a" else pair["biome_b"]
                work.append({
                    "material_id": mid,
                    "biome_id": bid,
                    "action": action,
                    "priority": ACTION_PRIORITY.get(action, 9),
                    "reason": f"transition audit {pair['verdict']}: pair ({pair['biome_a']} <-> {pair['biome_b']}) — {', '.join(pair.get('notes', []))}",
                    "driver_hint": {
                        "palette_lock": "pipelines/textures/palette_lock.py",
                        "regenerate": "pipelines/textures/aaa_texture.py",
                    }.get(action, ""),
                    "transition_pair": [pair["biome_a"], pair["biome_b"]],
                })

    # Dedupe: keep the highest-priority work per (material_id, action)
    dedup: dict[tuple[str, str], dict] = {}
    for w in work:
        key = (w["material_id"], w["action"])
        if key not in dedup or w["priority"] < dedup[key]["priority"]:
            dedup[key] = w

    return sorted(dedup.values(), key=lambda w: (w["priority"], w["material_id"]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("plan", type=Path)
    ap.add_argument("--json", action="store_true",
                    help="Emit demand JSON to stdout in addition to writing it.")
    args = ap.parse_args()

    if not args.plan.exists():
        print(f"ERROR: plan not found at {args.plan}", file=sys.stderr)
        return 2

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    plan_id = plan.get("id", "unknown")

    catalog = load_catalog()
    referenced = collect_plan_materials(plan)

    have: list[dict] = []
    need: list[dict] = []
    below: list[dict] = []
    for ref in referenced:
        mid = ref["material_id"]
        if mid not in catalog:
            # Even if catalog entry missing, maybe albedo is on disk
            if material_on_disk(mid):
                below.append({**ref, "reason": "albedo on disk but no catalog entry"})
            else:
                need.append(ref)
            continue
        if passed_gate(catalog[mid]):
            have.append({**ref, "passed_gate": True})
        else:
            below.append({**ref, "passed_gate": False, "reason": "catalog entry exists but passed_gate=false"})

    audit = load_transition_audit(plan_id)
    work_queue = derive_work_queue(have, need, below, audit)

    print(f"=== derive_catalog_demand ===")
    print(f"Plan: {plan_id}")
    print(f"Catalog: {len(catalog)} materials total")
    print(f"Plan references: {len({r['material_id'] for r in referenced})} unique materials across {len(referenced)} biome bindings")
    print()
    print(f"--- Buckets ---")
    print(f"  have  ({len({h['material_id'] for h in have})}): {sorted({h['material_id'] for h in have})}")
    print(f"  need  ({len({n['material_id'] for n in need})}): {sorted({n['material_id'] for n in need})}")
    print(f"  below ({len({b['material_id'] for b in below})}): {sorted({b['material_id'] for b in below})}")
    print()
    print(f"--- Work queue ({len(work_queue)} items) ---")
    for w in work_queue:
        pair_note = ""
        if "transition_pair" in w:
            pair_note = f"  [pair {w['transition_pair']}]"
        print(f"  [{w['action']:<18}] {w['material_id']:<25}  {pair_note}")
        print(f"                       reason: {w['reason']}")
        if w.get("driver_hint"):
            print(f"                       run:    {w['driver_hint']}")

    audit_summary = None
    if audit:
        audit_summary = {
            "audit_path": str(TRANSITION_AUDITS_DIR.relative_to(ROOT) / f"{plan_id}.json").replace("\\", "/"),
            "pass": audit.get("pass_count", 0),
            "warn": audit.get("warn_count", 0),
            "fail": audit.get("fail_count", 0),
            "error": audit.get("error_count", 0),
        }

    DEMAND_OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DEMAND_OUT_DIR / f"{plan_id}.json"
    doc = {
        "schema_version": 1,
        "plan_id": plan_id,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "have": have,
        "need": need,
        "below_promotion_bar": below,
        "transition_audit": audit_summary,
        "work_queue": work_queue,
    }
    out_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    print()
    print(f"--- Summary ---")
    print(f"  written: {out_path.relative_to(ROOT)}")
    if audit_summary:
        print(f"  transition audit: pass={audit_summary['pass']} warn={audit_summary['warn']} fail={audit_summary['fail']}")
    else:
        print(f"  transition audit: NOT FOUND — run audit_transition_pairs.py first to prioritize remediation")
    print()
    print(f"=== derive_catalog_demand DONE ===")

    if args.json:
        print()
        print(json.dumps(doc, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
