"""Plain-language effect description → seeded effect.json (brief #04, 2026-05-07).

Addresses the "18 of 24 palette-swap recolors" problem identified in
docs/pipeline_reviews/02_vfx_3d_bake.md by moving the authoring layer up:
designers describe the *intent* of an effect ("a red wave of fire that
ripples outward when a giant slams the ground"), and the LLM emits a seeded
`effect.json` whose phenomenon, palette, backend, gameplay shape, and
backend_params reflect that intent — instead of cloning an existing effect
and only swapping the palette.

This is the "LLM authoring tool comes BEFORE GPU port" priority that brief
#04 identified. See `docs/plans/ROADMAP.md` Brief #04 section.

Usage
-----

  # Dry-run (no LLM): build the prompt + JSON Schema preview + a synthetic
  # placeholder effect.json so you can see what the LLM would be asked.
  python pipelines/vfx/effect_from_description.py \\
      --description "fire wave that ripples outward from giant ground slam" \\
      --id giant_fire_slam_wave \\
      --out vfx/catalog/spells/giant_fire_slam_wave/effect.json

  # Real LLM run (requires a local vLLM server with guided_json/xgrammar):
  python pipelines/vfx/effect_from_description.py \\
      --description "fire wave that ripples outward from giant ground slam" \\
      --id giant_fire_slam_wave \\
      --backend vllm \\
      --server http://127.0.0.1:8000/v1 \\
      --model Qwen/Qwen2.5-Coder-32B-Instruct-AWQ \\
      --out vfx/catalog/spells/giant_fire_slam_wave/effect.json

The LLM-generated effect.json is *seeded* — the bake step still owns final
sim parameters; this tool's job is to get the high-level shape right
(phenomenon, backend, palette intent, archetype, gameplay hooks) so a
subsequent baker run produces a non-palette-swap effect.

Output is validated against the canonical `Effect` Pydantic model from
pipelines/vfx/schemas.py before being written; invalid LLM output is rejected
loudly with the validation error and the raw LLM response for debugging.

Dependencies (when --backend vllm): only stdlib + pydantic (vLLM is queried
over HTTP). When --backend dry-run: stdlib + pydantic only.

Pattern mirrors pipelines/game_data/local_llm_backend.py — same vLLM HTTP
shape, same guided_json + xgrammar grammar enforcement, same fallback to a
synthetic dry-run on CPU. Cloud backends (Claude, DeepSeek) are deliberately
NOT wired here per the "cloud parked" user direction; if cloud comes back,
add a sibling --backend claude using the existing Anthropic SDK pattern.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from schemas import Effect  # noqa: E402


SYSTEM_PROMPT = (
    "You are a senior VFX technical artist authoring effect.json files for a "
    "2.5D fantasy ARPG. The effect.json contract drives downstream bakers "
    "(particle_cpu, fracture2d, smoke_field, volumetric_fog, runtime_trail, "
    "decal_flipbook). Your job is to translate a designer's plain-language "
    "description into a single seeded effect.json that will produce a "
    "*distinctively-shaped* effect, not a palette-swap of an existing one.\n\n"
    "Rules:\n"
    "1. Pick a phenomenon, backend, archetype, and gameplay shape that match "
    "the description's physics — don't default to 'particle' for everything.\n"
    "2. Palette must be 1-6 hex colors (#RRGGBB) that reflect the described "
    "elemental/material intent.\n"
    "3. Choose `kind`, `archetype`, and `element` consistently with the "
    "description (e.g. a healing aura is kind=spell + archetype=aura + "
    "element=arcane).\n"
    "4. Set `gameplay.shape` based on the spatial pattern (projectile, aura, "
    "cone, line, point, touch, self).\n"
    "5. Pick a `backend` whose physics matches: particle_cpu for sprays/bursts, "
    "fracture2d for shatter/destruction, smoke_field for fire/smoke/cloud "
    "fields, volumetric_fog for ambient bioma haze, runtime_trail for "
    "projectile tails, decal_flipbook for ground impacts.\n"
    "6. Backend-specific `backend_params` should seed reasonable starting values "
    "(emitter type, particle count, gravity, drag, spread, density curves) — "
    "the baker will refine, but bad seeds make for bad effects.\n"
    "7. Use lowercase snake_case for `id`. Match the user-supplied id exactly.\n"
    "8. `notes` should briefly explain the design intent in one sentence.\n"
    "9. Return strictly one JSON object matching the schema; no markdown fences."
)


def build_prompt(description: str, effect_id: str, hints: dict[str, Any]) -> str:
    """Compose the user-prompt half of the LLM request."""
    parts = [
        f"Designer description:\n{description.strip()}",
        f"\nDesired effect id: {effect_id}",
    ]
    if hints:
        parts.append("\nDesign hints:")
        for k, v in hints.items():
            parts.append(f"  - {k}: {v}")
    parts.append(
        "\nReturn one JSON object matching the Effect schema. "
        "Pay special attention to backend selection, palette, archetype, and "
        "gameplay.shape — those are the levers that make this not a "
        "palette-swap."
    )
    return "\n".join(parts)


def effect_schema() -> dict[str, Any]:
    """Pydantic-derived JSON Schema for the canonical Effect model."""
    return Effect.model_json_schema()


def build_vllm_request(
    description: str,
    effect_id: str,
    *,
    hints: dict[str, Any],
    model: str,
    guided_backend: str,
    max_tokens: int,
) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_prompt(description, effect_id, hints)},
        ],
        "temperature": 0.3,
        "max_tokens": max_tokens,
        "guided_json": effect_schema(),
        "guided_decoding_backend": guided_backend,
    }


def _post_json(url: str, payload: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urlopen(req, timeout=timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"vLLM request failed: HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"vLLM request failed: {exc}") from exc


def run_vllm(
    description: str,
    effect_id: str,
    *,
    hints: dict[str, Any],
    server: str,
    model: str,
    guided_backend: str,
    max_tokens: int,
    timeout_s: float,
) -> dict[str, Any]:
    base = server.rstrip("/")
    payload = build_vllm_request(
        description,
        effect_id,
        hints=hints,
        model=model,
        guided_backend=guided_backend,
        max_tokens=max_tokens,
    )
    result = _post_json(f"{base}/chat/completions", payload, timeout_s)
    try:
        content = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"unexpected vLLM response shape: {result!r}") from exc
    parsed = json.loads(content)
    return parsed


def synthetic_seed(description: str, effect_id: str, hints: dict[str, Any]) -> dict[str, Any]:
    """No-LLM placeholder used by --backend dry-run.

    Produces a schema-valid effect.json with a deliberately-bland default shape
    so the user sees the *structure* the LLM would emit, plus the prompt that
    would be sent. This is the brief #04 "sub-day scaffold" — it does NOT
    attempt to interpret the description, only to round-trip the contract.
    """
    palette_hint = hints.get("palette") or ["#ffffff", "#888888"]
    backend_hint = hints.get("backend") or "particle_cpu"
    archetype_hint = hints.get("archetype") or "burst"
    return {
        "id": effect_id,
        "kind": hints.get("kind") or "spell",
        "phenomenon": hints.get("phenomenon") or "particle",
        "backend": backend_hint,
        "duration_s": 1.0,
        "fps": 24,
        "bounds_px": [256, 256],
        "visual": {
            "palette": palette_hint,
            "blend": "alpha",
            "background": "#00000000",
            "bloom": False,
        },
        "visual3d": {
            "billboard_mode": "enabled",
            "cast_shadow": False,
            "receive_shadow": False,
            "depth_test": "enabled",
            "world_size_m": None,
        },
        "backend_params": {},
        "gameplay": {
            "shape": hints.get("shape") or "point",
            "damage_tags": [],
            "collision": "none",
        },
        "element": hints.get("element") or "neutral",
        "archetype": archetype_hint,
        "tags": [],
        "export_target": "2d",
        "notes": (
            f"DRY-RUN PLACEHOLDER (--backend dry-run). LLM would interpret: "
            f"{description.strip()[:200]}"
        ),
    }


def author_effect(
    description: str,
    effect_id: str,
    *,
    hints: dict[str, Any],
    backend: str,
    server: str,
    model: str,
    guided_backend: str,
    max_tokens: int,
    timeout_s: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Returns (validated_effect_json, debug_info)."""
    debug: dict[str, Any] = {
        "backend": backend,
        "model": model if backend != "dry-run" else None,
        "prompt_user": build_prompt(description, effect_id, hints),
        "prompt_system": SYSTEM_PROMPT,
        "schema_keys": sorted(effect_schema().get("properties", {}).keys()),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    if backend == "dry-run":
        raw = synthetic_seed(description, effect_id, hints)
    elif backend == "vllm":
        raw = run_vllm(
            description,
            effect_id,
            hints=hints,
            server=server,
            model=model,
            guided_backend=guided_backend,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
        )
    else:
        raise ValueError(f"unknown backend {backend!r} (use dry-run or vllm)")

    debug["raw_payload"] = raw

    try:
        validated = Effect.model_validate(raw).model_dump()
    except Exception as exc:
        raise RuntimeError(
            f"LLM returned a payload that does NOT validate against the Effect "
            f"schema. raw={raw!r}\n\nValidation error: {exc}"
        ) from exc

    if validated.get("id") != effect_id:
        validated["id"] = effect_id

    return validated, debug


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Author a seeded effect.json from a plain-language description.",
    )
    ap.add_argument("--description", required=True,
                    help="Plain-language description of the effect's intent.")
    ap.add_argument("--id", dest="effect_id", required=True,
                    help="Effect id (lowercase snake_case, length 2-40).")
    ap.add_argument("--out", type=Path, required=True,
                    help="Output path for the seeded effect.json.")
    ap.add_argument("--backend", choices=("dry-run", "vllm"), default="dry-run",
                    help="dry-run = no LLM, schema-valid placeholder. "
                         "vllm = POST to a local OpenAI-compatible vLLM server.")
    ap.add_argument("--server", default="http://127.0.0.1:8000/v1",
                    help="vLLM base URL when --backend vllm.")
    ap.add_argument("--model", default="Qwen/Qwen2.5-Coder-32B-Instruct-AWQ",
                    help="Model name passed to vLLM.")
    ap.add_argument("--guided-backend", default="xgrammar",
                    choices=("xgrammar", "outlines", "lm-format-enforcer"))
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--timeout", type=float, default=120.0,
                    help="vLLM HTTP timeout (seconds).")
    ap.add_argument("--hint", action="append", default=[],
                    metavar="KEY=VALUE",
                    help="Optional design hint(s), e.g. "
                         "--hint backend=particle_cpu --hint archetype=projectile. "
                         "May be passed multiple times.")
    ap.add_argument("--debug", action="store_true",
                    help="Also write a sibling .debug.json with prompt + raw LLM payload.")
    args = ap.parse_args()

    hints: dict[str, Any] = {}
    for h in args.hint:
        if "=" not in h:
            print(f"[effect_from_description] WARNING: ignoring malformed hint {h!r} (need KEY=VALUE)",
                  file=sys.stderr)
            continue
        k, _, v = h.partition("=")
        hints[k.strip()] = v.strip()

    validated, debug = author_effect(
        args.description,
        args.effect_id,
        hints=hints,
        backend=args.backend,
        server=args.server,
        model=args.model,
        guided_backend=args.guided_backend,
        max_tokens=args.max_tokens,
        timeout_s=args.timeout,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(validated, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[effect_from_description] backend={args.backend} -> {args.out}")
    print(f"  id={validated['id']} backend={validated['backend']} "
          f"phenomenon={validated['phenomenon']} archetype={validated['archetype']}")

    if args.debug:
        debug_path = args.out.with_suffix(args.out.suffix + ".debug.json")
        debug_path.write_text(json.dumps(debug, indent=2, ensure_ascii=False, default=str),
                              encoding="utf-8")
        print(f"  debug -> {debug_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
