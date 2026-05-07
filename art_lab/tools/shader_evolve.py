"""Evolutionary shader search against reference images.

This is the "breed the best results" path. It uses the existing template
library and CPU proxy renderer, but selection pressure comes from a reference
image or reference set instead of only role rubrics.

Use this for target-driven exploration:

  - "make this portal closer to these references"
  - "evolve a projectile silhouette toward this concept image"
  - "find parameter neighborhoods that match this UI glow"
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

LAB_ROOT = Path(r"D:\assets\art_lab")
TOOLS_DIR = LAB_ROOT / "tools"

sys.path.append(str(TOOLS_DIR))
from shader_batch_review import (  # noqa: E402
    BATCHES_DIR,
    TEMPLATE_ROLE,
    TEMPLATES_DIR,
    candidate_review,
    emit_candidate,
    mutate_params,
    parse_uniforms,
    preview_config_for,
    render_cpu_preview,
    sample_params,
    update_request_review,
    write_gallery,
    write_llm_packet,
)
from shader_reference_score import feature, image_paths  # noqa: E402


def resolve_references(paths: list[Path]) -> list[tuple[Path, np.ndarray]]:
    refs: list[Path] = []
    for path in paths:
        if path.is_dir():
            refs.extend(image_paths(path))
        elif path.exists():
            refs.append(path)
    if not refs:
        raise SystemExit("no reference images found")
    return [(p, feature(p)) for p in sorted(refs)]


def ref_similarity(preview_path: Path, references: list[tuple[Path, np.ndarray]]) -> tuple[float, Path, float]:
    cand = feature(preview_path)
    best_path = references[0][0]
    best_dist = math.inf
    for path, ref in references:
        dist = float(np.linalg.norm(cand - ref))
        if dist < best_dist:
            best_dist = dist
            best_path = path
    return round(100.0 * math.exp(-best_dist * 2.2), 2), best_path, round(best_dist, 5)


def load_template(template: str) -> tuple[str, list[Any], str]:
    path = TEMPLATES_DIR / f"{template}.gdshader"
    if not path.exists():
        raise SystemExit(f"template not found: {path}")
    text = path.read_text(encoding="utf-8")
    return text, parse_uniforms(text), TEMPLATE_ROLE.get(template, "aura")


def grade_from_combined(combined: float, base: float, gate_issues: list[str]) -> str:
    if gate_issues or base < 45:
        return "reject"
    if combined >= 88 and base >= 70:
        return "keep"
    if combined >= 75 and base >= 58:
        return "review"
    if combined >= 58:
        return "maybe"
    return "reject"


def evaluate_candidate(
    batch_dir: Path,
    shader_id: str,
    template: str,
    shader_text: str,
    params: dict[str, Any],
    preview: dict[str, Any],
    intent: str,
    role: str,
    references: list[tuple[Path, np.ndarray]],
    reference_weight: float,
) -> dict[str, Any]:
    out_dir = emit_candidate(batch_dir, shader_id, template, shader_text, params, preview, intent, role)
    frame_paths = render_cpu_preview(out_dir, template, params, preview)
    review = candidate_review(out_dir, role, params)
    base_score = float(review["score"])
    ref_score, nearest, distance = ref_similarity(out_dir / "preview.png", references)
    combined = round((1.0 - reference_weight) * base_score + reference_weight * ref_score, 2)
    review["base_score"] = base_score
    review["reference_score"] = ref_score
    review["reference_distance"] = distance
    review["nearest_reference"] = str(nearest)
    review["score"] = combined
    review["grade"] = grade_from_combined(combined, base_score, review.get("gate_issues", []))
    review["render_source"] = "cpu_proxy"
    review["selection_score"] = combined
    update_request_review(out_dir, review)
    return {
        "id": shader_id,
        "template": template,
        "role": role,
        "params": params,
        "preview": preview,
        "frames": [str(p.relative_to(out_dir)) for p in frame_paths],
        "review": review,
    }


def unique_elites(rows: list[dict[str, Any]], elite_count: int) -> list[dict[str, Any]]:
    rows = sorted(rows, key=lambda r: float(r["review"].get("selection_score", r["review"].get("score", 0.0))), reverse=True)
    elites: list[dict[str, Any]] = []
    seen_templates: set[str] = set()
    for row in rows:
        if row["template"] not in seen_templates:
            elites.append(row)
            seen_templates.add(row["template"])
        if len(elites) >= elite_count:
            return elites
    for row in rows:
        if row not in elites:
            elites.append(row)
        if len(elites) >= elite_count:
            break
    return elites


def run(args: argparse.Namespace) -> Path:
    rng = random.Random(args.seed)
    references = resolve_references(args.reference)
    templates = args.template or list(TEMPLATE_ROLE.keys())
    template_cache = {template: load_template(template) for template in templates}
    batch_id = args.batch_id or datetime.now().strftime("shader_evolve_%Y%m%d_%H%M%S")
    batch_dir = BATCHES_DIR / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, Any]] = []
    generation_summaries: list[dict[str, Any]] = []
    parents: list[dict[str, Any]] = []
    reference_weight = float(np.clip(args.reference_weight, 0.0, 1.0))

    for generation in range(args.generations):
        generation_rows: list[dict[str, Any]] = []
        for i in range(args.population):
            if generation == 0 or not parents:
                template = templates[i % len(templates)]
                shader_text, uniforms, role = template_cache[template]
                params = sample_params(template, uniforms, args.intent, role, rng)
            else:
                parent = parents[i % len(parents)]
                template = parent["template"]
                shader_text, uniforms, role = template_cache[template]
                strength = args.mutation_strength * (0.80 ** max(0, generation - 1))
                params = mutate_params(parent["params"], uniforms, rng, strength)
            preview = preview_config_for(template, role, args.size, args.frames)
            shader_id = f"{batch_id}_g{generation:02d}_{template}_{i + 1:03d}"
            row = evaluate_candidate(
                batch_dir,
                shader_id,
                template,
                shader_text,
                params,
                preview,
                args.intent,
                role,
                references,
                reference_weight,
            )
            row["generation"] = generation
            generation_rows.append(row)
            all_rows.append(row)

        parents = unique_elites(generation_rows + parents, args.elites)
        generation_summaries.append({
            "generation": generation,
            "best": [
                {
                    "id": row["id"],
                    "template": row["template"],
                    "score": row["review"]["score"],
                    "base_score": row["review"].get("base_score"),
                    "reference_score": row["review"].get("reference_score"),
                    "grade": row["review"]["grade"],
                }
                for row in unique_elites(generation_rows, min(args.elites, len(generation_rows)))
            ],
        })

    all_rows = sorted(all_rows, key=lambda r: float(r["review"].get("selection_score", r["review"].get("score", 0.0))), reverse=True)
    summary = {
        "batch": batch_id,
        "created": datetime.now(timezone.utc).isoformat(),
        "intent": args.intent,
        "seed": args.seed,
        "templates": templates,
        "references": [str(p) for p, _ in references],
        "population": args.population,
        "generations": args.generations,
        "elites": args.elites,
        "reference_weight": reference_weight,
        "generation_summaries": generation_summaries,
        "count": len(all_rows),
        "rows": all_rows,
    }
    (batch_dir / "batch_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (batch_dir / "evolution_summary.json").write_text(json.dumps({
        k: v for k, v in summary.items() if k != "rows"
    }, indent=2), encoding="utf-8")
    write_gallery(batch_dir, all_rows)
    write_llm_packet(batch_dir, all_rows, args.keep_top)
    return batch_dir


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", action="append", type=Path, required=True,
                    help="Reference image or directory. Repeat for multiple.")
    ap.add_argument("--template", action="append", choices=sorted(TEMPLATE_ROLE),
                    help="Template family to evolve. Repeat for multiple.")
    ap.add_argument("--intent", default="target-driven shader evolution")
    ap.add_argument("--batch-id")
    ap.add_argument("--population", type=int, default=24)
    ap.add_argument("--generations", type=int, default=4)
    ap.add_argument("--elites", type=int, default=6)
    ap.add_argument("--frames", type=int, default=4)
    ap.add_argument("--size", type=int, default=192)
    ap.add_argument("--seed", type=int, default=9)
    ap.add_argument("--mutation-strength", type=float, default=0.20)
    ap.add_argument("--reference-weight", type=float, default=0.65)
    ap.add_argument("--keep-top", type=int, default=12)
    args = ap.parse_args()

    args.population = max(2, args.population)
    args.generations = max(1, args.generations)
    args.elites = max(1, min(args.elites, args.population))
    batch_dir = run(args)
    print(f"wrote {batch_dir}")
    print(f"gallery: {batch_dir / 'gallery.html'}")
    print(f"evolution: {batch_dir / 'evolution_summary.json'}")


if __name__ == "__main__":
    main()
