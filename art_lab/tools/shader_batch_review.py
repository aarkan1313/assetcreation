"""Batch shader explorer and non-OCR review harness.

This is the second layer above shader_compile_preview.py:

1. Generate many parameter variants from a first-party Godot shader template.
2. Emit the same shippable files as the single-shader compiler.
3. Render CPU fallback previews for the current first-party templates when a
   Godot binary is not available.
4. Score outputs from pixels, not OCR: coverage, contrast, colorfulness,
   edge energy, center balance, motion, flicker, clipping, and role fit.
5. Write an HTML gallery plus JSON review packets for an LLM to iterate on.

The CPU renderer is intentionally a review proxy, not the source of truth.
When Godot preview rendering is available, use Godot-produced PNG/flipbooks
for final acceptance. The CPU path still lets the LLM explore broad parameter
space without depending on visual OCR.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import random
import re
import shutil
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

LAB_ROOT = Path(r"D:\assets\art_lab")
TEMPLATES_DIR = LAB_ROOT / "shaders" / "templates"
GENERATED_DIR = LAB_ROOT / "shaders" / "generated"
BATCHES_DIR = LAB_ROOT / "shaders" / "batches"

sys.path.append(str(Path(__file__).resolve().parent))
from shader_compile_preview import GD_PROJECT, build_scene_with_params  # noqa: E402


PALETTES: dict[str, list[list[float]]] = {
    "arcane": [[0.26, 0.86, 1.0], [0.62, 0.34, 1.0], [1.0, 0.98, 0.88], [0.06, 0.03, 0.12]],
    "storm": [[0.88, 0.96, 1.0], [0.36, 0.63, 1.0], [0.16, 0.28, 0.86], [0.02, 0.02, 0.08]],
    "fire": [[1.0, 0.36, 0.08], [1.0, 0.75, 0.18], [0.42, 0.06, 0.02], [0.08, 0.02, 0.0]],
    "frost": [[0.56, 0.92, 1.0], [0.15, 0.42, 0.95], [0.95, 1.0, 1.0], [0.02, 0.05, 0.10]],
    "necrotic": [[0.40, 1.0, 0.48], [0.12, 0.45, 0.18], [0.78, 0.94, 0.55], [0.01, 0.04, 0.02]],
    "shadow": [[0.42, 0.22, 0.76], [0.07, 0.04, 0.13], [0.84, 0.70, 1.0], [0.01, 0.00, 0.03]],
    "blood": [[0.92, 0.04, 0.07], [0.30, 0.0, 0.03], [1.0, 0.42, 0.35], [0.06, 0.0, 0.0]],
    "radiant": [[1.0, 0.92, 0.48], [1.0, 0.52, 0.18], [1.0, 1.0, 0.90], [0.08, 0.05, 0.00]],
    "earth": [[0.74, 0.55, 0.30], [0.25, 0.16, 0.09], [0.80, 0.95, 0.52], [0.04, 0.03, 0.02]],
    "void": [[0.20, 0.04, 0.40], [0.02, 0.00, 0.05], [0.70, 0.36, 1.0], [0.0, 0.0, 0.0]],
}

ROLE_RUBRICS: dict[str, dict[str, Any]] = {
    "aura": {
        "coverage": [0.08, 0.58], "motion": [0.005, 0.22], "center_max": 0.24,
        "colorfulness_min": 0.10, "edge": [0.010, 0.18], "contrast_min": 0.04,
        "weights": {"coverage": 1.3, "motion": 1.0, "center": 1.1, "color": 1.0, "edge": 0.8, "contrast": 0.8},
    },
    "aoe": {
        "coverage": [0.12, 0.70], "motion": [0.004, 0.18], "center_max": 0.25,
        "colorfulness_min": 0.08, "edge": [0.008, 0.16], "contrast_min": 0.035,
        "weights": {"coverage": 1.4, "motion": 0.8, "center": 1.0, "color": 0.8, "edge": 0.8, "contrast": 0.9},
    },
    "projectile": {
        "coverage": [0.015, 0.26], "motion": [0.008, 0.28], "center_max": 0.32,
        "colorfulness_min": 0.10, "edge": [0.012, 0.26], "contrast_min": 0.05,
        "aspect_min": 1.30,
        "weights": {"coverage": 1.4, "motion": 1.1, "center": 0.7, "color": 0.8, "edge": 1.0, "contrast": 0.8, "aspect": 1.0},
    },
    "beam": {
        "coverage": [0.010, 0.24], "motion": [0.006, 0.25], "center_max": 0.36,
        "colorfulness_min": 0.08, "edge": [0.015, 0.28], "contrast_min": 0.06,
        "aspect_min": 2.00,
        "weights": {"coverage": 1.3, "motion": 0.8, "center": 0.5, "color": 0.7, "edge": 1.1, "contrast": 0.9, "aspect": 1.5},
    },
    "shield": {
        "coverage": [0.10, 0.65], "motion": [0.004, 0.16], "center_max": 0.22,
        "colorfulness_min": 0.08, "edge": [0.012, 0.22], "contrast_min": 0.04,
        "weights": {"coverage": 1.3, "motion": 0.8, "center": 1.1, "color": 0.7, "edge": 1.1, "contrast": 0.8},
    },
    "portal": {
        "coverage": [0.10, 0.62], "motion": [0.010, 0.28], "center_max": 0.20,
        "colorfulness_min": 0.10, "edge": [0.008, 0.20], "contrast_min": 0.05,
        "weights": {"coverage": 1.2, "motion": 1.2, "center": 1.2, "color": 1.0, "edge": 0.8, "contrast": 0.9},
    },
    "dissolve": {
        "coverage": [0.08, 0.82], "motion": [0.008, 0.24], "center_max": 0.34,
        "colorfulness_min": 0.09, "edge": [0.018, 0.30], "contrast_min": 0.06,
        "weights": {"coverage": 1.0, "motion": 1.0, "center": 0.5, "color": 0.8, "edge": 1.5, "contrast": 1.0},
    },
    "ground": {
        "coverage": [0.70, 1.0], "motion": [0.0, 0.10], "center_max": 0.55,
        "colorfulness_min": 0.04, "edge": [0.004, 0.20], "contrast_min": 0.025,
        "weights": {"coverage": 1.5, "motion": 0.4, "center": 0.2, "color": 0.6, "edge": 0.8, "contrast": 0.9},
    },
    "ui": {
        "coverage": [0.04, 0.70], "motion": [0.0, 0.06], "center_max": 0.24,
        "colorfulness_min": 0.04, "edge": [0.010, 0.30], "contrast_min": 0.05,
        "weights": {"coverage": 1.2, "motion": 0.3, "center": 1.2, "color": 0.5, "edge": 1.2, "contrast": 1.0},
    },
}

TEMPLATE_ROLE = {
    "ring_field_2d": "aura",
    "beam_lightning_2d": "beam",
    "dissolve_fire_2d": "dissolve",
    "shield_ripple_2d": "shield",
    "portal_swirl_2d": "portal",
}


@dataclass
class Uniform:
    type: str
    name: str
    hint: str
    default: str
    min_value: float | None = None
    max_value: float | None = None


def fract(x: np.ndarray | float) -> np.ndarray | float:
    return x - np.floor(x)


def smoothstep(edge0: float, edge1: float, x: np.ndarray) -> np.ndarray:
    denom = max(1e-8, edge1 - edge0)
    t = np.clip((x - edge0) / denom, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def hash21(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    px = fract(x * 123.34)
    py = fract(y * 456.21)
    dot = px * (px + 45.32) + py * (py + 45.32)
    px = px + dot
    py = py + dot
    return fract(px * py)


def vnoise(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    ix = np.floor(x)
    iy = np.floor(y)
    fx = fract(x)
    fy = fract(y)
    a = hash21(ix, iy)
    b = hash21(ix + 1.0, iy)
    c = hash21(ix, iy + 1.0)
    d = hash21(ix + 1.0, iy + 1.0)
    ux = fx * fx * (3.0 - 2.0 * fx)
    uy = fy * fy * (3.0 - 2.0 * fy)
    return (a * (1.0 - ux) + b * ux) * (1.0 - uy) + (c * (1.0 - ux) + d * ux) * uy


def fbm(x: np.ndarray, y: np.ndarray, octaves: int = 4) -> np.ndarray:
    v = np.zeros_like(x, dtype=np.float32)
    amp = 0.5
    for _ in range(octaves):
        v += amp * vnoise(x, y)
        x *= 2.0
        y *= 2.0
        amp *= 0.5
    return v


def parse_uniforms(shader_text: str) -> list[Uniform]:
    pattern = re.compile(
        r"uniform\s+(\w+)\s+(\w+)(\s*:\s*(?:hint_range\([^)]+\)|source_color))?\s*(?:=\s*([^;]+))?;"
    )
    uniforms: list[Uniform] = []
    for line in shader_text.splitlines():
        match = pattern.search(line)
        if not match:
            continue
        typ, name, hint, default = match.groups()
        uni = Uniform(typ, name, (hint or "").strip(), (default or "").strip())
        hint_match = re.search(r"hint_range\(([-0-9.]+),\s*([-0-9.]+)", uni.hint)
        if hint_match:
            uni.min_value = float(hint_match.group(1))
            uni.max_value = float(hint_match.group(2))
        uniforms.append(uni)
    return uniforms


def parse_default(uni: Uniform) -> Any:
    if not uni.default:
        if uni.type == "vec2":
            return [0.5, 0.5]
        if uni.type == "vec3":
            return [1.0, 1.0, 1.0]
        if uni.type == "vec4":
            return [1.0, 1.0, 1.0, 1.0]
        return 0.0
    if uni.type in {"float", "int"}:
        try:
            return float(uni.default)
        except ValueError:
            return 0.0
    if uni.type.startswith("vec"):
        vals = re.findall(r"[-+]?[0-9]*\.?[0-9]+", uni.default)
        return [float(v) for v in vals]
    return uni.default


def choose_palette(intent: str, rng: random.Random) -> tuple[str, list[list[float]]]:
    text = intent.lower()
    keywords = [
        ("fire", ["fire", "flame", "burn", "inferno", "lava", "ember"]),
        ("frost", ["ice", "frost", "cold", "snow", "winter"]),
        ("storm", ["storm", "lightning", "electric", "thunder"]),
        ("necrotic", ["poison", "toxic", "acid", "venom", "nature", "green"]),
        ("shadow", ["shadow", "dark", "void", "curse", "night"]),
        ("blood", ["blood", "crimson", "flesh"]),
        ("radiant", ["holy", "radiant", "sun", "gold", "paladin"]),
        ("earth", ["earth", "stone", "moss", "ground", "root"]),
        ("void", ["void", "abyss", "black hole", "portal"]),
        ("arcane", ["arcane", "magic", "rune", "spell"]),
    ]
    for key, words in keywords:
        if any(word in text for word in words):
            return key, PALETTES[key]
    key = rng.choice(list(PALETTES))
    return key, PALETTES[key]


def jitter_color(color: list[float], rng: random.Random, amount: float = 0.10) -> list[float]:
    return [float(np.clip(c + rng.uniform(-amount, amount), 0.0, 1.0)) for c in color]


def sample_float(uni: Uniform, rng: random.Random, role: str) -> float:
    default = float(parse_default(uni) or 0.0)
    lo = uni.min_value if uni.min_value is not None else default - abs(default) - 1.0
    hi = uni.max_value if uni.max_value is not None else default + abs(default) + 1.0
    name = uni.name.lower()

    if "opacity" in name:
        return round(rng.uniform(0.72, 1.0), 4)
    if "radius" in name:
        return round(rng.uniform(max(lo, 0.18), min(hi, 0.49)), 4)
    if "edge_width" in name or "thickness" == name:
        return round(rng.uniform(max(lo, 0.012), min(hi, 0.11)), 4)
    if "core_thickness" in name:
        return round(rng.uniform(max(lo, 0.18), min(hi, 0.58)), 4)
    if "speed" in name:
        return round(rng.uniform(max(lo, -3.8), min(hi, 5.5)), 4)
    if "noise_scale" in name or "frequency" in name or "ripple_freq" in name:
        return round(rng.uniform(max(lo, 5.0), min(hi, 36.0)), 4)
    if "strength" in name:
        return round(rng.uniform(max(lo, 0.18), min(hi, 1.25)), 4)
    if "distortion" in name or "warp" in name or "jaggedness" in name:
        return round(rng.uniform(max(lo, 0.05), min(hi, 0.82)), 4)
    if "rune_count" in name:
        return round(rng.choice([0, 6, 8, 10, 12, 16, 18, 24]), 4)
    if "arms" == name:
        return round(rng.choice([3, 4, 5, 6, 7, 8, 10]), 4)
    if "threshold" in name:
        return round(rng.uniform(max(lo, 0.25), min(hi, 0.70)), 4)
    if "arc" == name and role in {"beam", "projectile"}:
        return round(rng.uniform(max(lo, -0.22), min(hi, 0.22)), 4)
    if "hit_age" in name:
        return round(rng.uniform(max(lo, 0.25), min(hi, 2.8)), 4)

    # Broad but not endpoint-heavy.
    center = np.clip(default, lo, hi)
    span = hi - lo
    if span <= 0:
        return round(center, 4)
    v = rng.gauss(center, span * 0.22)
    if rng.random() < 0.35:
        v = rng.uniform(lo, hi)
    return round(float(np.clip(v, lo, hi)), 4)


def sample_params(template: str, uniforms: list[Uniform], intent: str, role: str, rng: random.Random) -> dict[str, Any]:
    palette_name, palette = choose_palette(intent, rng)
    params: dict[str, Any] = {}

    color_slots = {
        "inner": 0, "core": 0, "burn": 0, "hit": 2,
        "outer": 1, "edge": 1, "shield": 0, "mid": 1,
        "glow": 2, "ember": 2, "void": 3, "ash": 3,
    }
    for uni in uniforms:
        name = uni.name.lower()
        if uni.type == "vec3":
            slot = 0
            for key, idx in color_slots.items():
                if key in name:
                    slot = idx
                    break
            params[uni.name] = jitter_color(palette[slot], rng, 0.08)
        elif uni.type == "vec2":
            if "hit_position" in name:
                params[uni.name] = [round(rng.uniform(0.34, 0.66), 4), round(rng.uniform(0.34, 0.66), 4)]
            else:
                params[uni.name] = parse_default(uni)
        elif uni.type in {"float", "int"}:
            value = sample_float(uni, rng, role)
            params[uni.name] = int(value) if uni.type == "int" else value
        else:
            params[uni.name] = parse_default(uni)

    # Template-specific guardrails so random exploration does not flood review
    # with obvious garbage.
    if template == "beam_lightning_2d":
        params["thickness"] = min(params.get("thickness", 0.05), 0.085)
        params["frequency"] = max(params.get("frequency", 14.0), 8.0)
    if template == "ring_field_2d":
        params["edge_width"] = min(params.get("edge_width", 0.04), 0.075)
    if template == "portal_swirl_2d" and palette_name == "void":
        params["color_void"] = [0.0, 0.0, 0.0]
    return params


def mutate_params(parent: dict[str, Any], uniforms: list[Uniform], rng: random.Random, strength: float) -> dict[str, Any]:
    """Make a local mutation around an existing winning request."""
    strength = float(np.clip(strength, 0.01, 1.0))
    mutated: dict[str, Any] = {}
    uniform_by_name = {u.name: u for u in uniforms}
    for name, value in parent.items():
        uni = uniform_by_name.get(name)
        if not uni:
            mutated[name] = value
            continue
        if uni.type == "vec3":
            amount = 0.22 * strength
            mutated[name] = jitter_color(list(value), rng, amount)
        elif uni.type == "vec2":
            vec = list(value)
            mutated[name] = [
                round(float(np.clip(vec[0] + rng.gauss(0.0, 0.12 * strength), 0.0, 1.0)), 4),
                round(float(np.clip(vec[1] + rng.gauss(0.0, 0.12 * strength), 0.0, 1.0)), 4),
            ]
        elif uni.type in {"float", "int"}:
            base = float(value)
            lo = uni.min_value if uni.min_value is not None else base - abs(base) - 1.0
            hi = uni.max_value if uni.max_value is not None else base + abs(base) + 1.0
            span = max(hi - lo, 1e-6)
            if name.lower() in {"rune_count", "arms"} and rng.random() < 0.35:
                mutated[name] = sample_float(uni, rng, "aura")
            else:
                v = base + rng.gauss(0.0, span * 0.16 * strength)
                v = float(np.clip(v, lo, hi))
                mutated[name] = int(round(v)) if uni.type == "int" else round(v, 4)
        else:
            mutated[name] = value
    return mutated


def preview_config_for(template: str, role: str, size: int, frames: int) -> dict[str, Any]:
    if template == "beam_lightning_2d" or role == "beam":
        return {"size": [size * 2, size], "frames": frames, "duration_s": 1.5, "background": [0.015, 0.015, 0.035, 1.0]}
    return {"size": [size, size], "frames": frames, "duration_s": 1.8, "background": [0.035, 0.035, 0.055, 1.0]}


def emit_candidate(batch_dir: Path, shader_id: str, template: str, shader_text: str,
                   params: dict[str, Any], preview: dict[str, Any], intent: str, role: str) -> Path:
    out_dir = batch_dir / shader_id
    out_dir.mkdir(parents=True, exist_ok=True)
    shader_out = out_dir / f"{shader_id}.gdshader"
    shader_out.write_text(
        f"// Generated {datetime.now(timezone.utc).isoformat()} from template {template}\n"
        + shader_text,
        encoding="utf-8",
    )
    size = tuple(preview.get("size", [512, 512]))
    background = preview.get("background", [0.05, 0.05, 0.08, 1.0])
    scene = build_scene_with_params(shader_id, shader_text, params, size, background)
    (out_dir / f"{shader_id}.tscn").write_text(scene, encoding="utf-8")
    (out_dir / "project.godot").write_text(GD_PROJECT, encoding="utf-8")
    record = {
        "id": shader_id,
        "intent": intent,
        "role": role,
        "template": template,
        "params": params,
        "preview": preview,
        "created": datetime.now(timezone.utc).isoformat(),
        "review": {"status": "pending"},
    }
    (out_dir / "request.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return out_dir


def uv_grid(width: int, height: int) -> tuple[np.ndarray, np.ndarray]:
    xs = np.linspace(0.0, 1.0, width, endpoint=False, dtype=np.float32) + 0.5 / width
    ys = np.linspace(0.0, 1.0, height, endpoint=False, dtype=np.float32) + 0.5 / height
    return np.meshgrid(xs, ys)


def as_arr3(v: list[float]) -> np.ndarray:
    return np.array(v[:3], dtype=np.float32)


def rgba(rgb: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    alpha = np.clip(alpha, 0.0, 1.0).astype(np.float32)
    return np.dstack((np.clip(rgb, 0.0, 1.0), alpha))


def render_ring(params: dict[str, Any], w: int, h: int, t: float) -> np.ndarray:
    x, y = uv_grid(w, h)
    ux = x - 0.5
    uy = y - 0.5
    noise_scale = float(params.get("noise_scale", 11.0))
    warp_x = fbm(ux * noise_scale + t * 0.3, uy * noise_scale) - 0.5
    warp_y = fbm(ux * noise_scale, uy * noise_scale + t * 0.3) - 0.5
    ux = ux + warp_x * float(params.get("distortion", 0.12))
    uy = uy + warp_y * float(params.get("distortion", 0.12))
    rr = np.sqrt(ux * ux + uy * uy)
    ang = np.arctan2(uy, ux)
    radius = float(params.get("radius", 0.42))
    edge_width = float(params.get("edge_width", 0.04))
    ring = 1.0 - smoothstep(0.0, edge_width, np.abs(rr - radius))
    pulse = 0.5 + 0.5 * math.sin(t * float(params.get("pulse_speed", 1.8)))
    ring *= 0.6 + 0.4 * pulse
    rune_count = float(params.get("rune_count", 12.0))
    if rune_count > 0.0:
        a = ang * rune_count / (math.pi * 2.0)
        rune_mask = (np.abs(fract(a) - 0.5) * 2.0 >= 0.55).astype(np.float32)
        rune_band = smoothstep(radius - edge_width * 1.5, radius + edge_width * 1.5, rr)
        rune_band *= 1.0 - smoothstep(radius + edge_width * 1.5, radius + edge_width * 5.0, rr)
        ring += rune_mask * rune_band * float(params.get("rune_strength", 0.7))
    glow = np.exp(-np.power((rr - radius) / max(edge_width * 4.0, 1e-5), 2.0)) * 0.5
    inner = as_arr3(params.get("color_inner", [0.33, 0.84, 1.0]))
    outer = as_arr3(params.get("color_outer", [0.65, 0.42, 1.0]))
    glow_color = as_arr3(params.get("color_glow", [1.0, 1.0, 1.0]))
    mixv = np.clip(ring, 0.0, 1.0)[..., None]
    rgb = outer * (1.0 - mixv) + inner * mixv
    rgb += glow[..., None] * glow_color * pulse
    alpha = np.clip(ring + glow, 0.0, 1.0) * float(params.get("opacity", 1.0))
    return rgba(rgb, alpha)


def render_beam(params: dict[str, Any], w: int, h: int, t: float) -> np.ndarray:
    x, y = uv_grid(w, h)
    mid_y = 0.5 + float(params.get("arc", 0.0)) * np.sin(x * math.pi)
    freq = float(params.get("frequency", 14.0))
    speed = float(params.get("speed", 4.0))
    n1 = vnoise(x * freq, np.full_like(x, t * speed))
    n2 = vnoise(x * freq * 2.3, np.full_like(x, t * speed * 1.7))
    jaggle = (n1 - 0.5) * float(params.get("jaggedness", 0.55)) + (n2 - 0.5) * float(params.get("jaggedness", 0.55)) * 0.5
    line_y = mid_y + jaggle * 0.25
    dist = np.abs(y - line_y)
    thickness = float(params.get("thickness", 0.05))
    core = 1.0 - smoothstep(0.0, thickness * float(params.get("core_thickness", 0.35)), dist)
    band = 1.0 - smoothstep(0.0, thickness, dist)
    glow = 1.0 - smoothstep(0.0, thickness * 4.0, dist)
    fork = np.zeros_like(x)
    fork_strength = float(params.get("fork_strength", 0.4))
    for i in range(3):
        fork_y = mid_y + (vnoise(x * freq * 0.7 + i * 11.0, np.full_like(x, t * speed * 0.6)) - 0.5) * 0.4
        fdist = np.abs(y - fork_y) + np.abs(x - (0.4 + 0.2 * i)) * 0.5
        fork += (1.0 - smoothstep(0.0, thickness * 0.7, fdist)) * fork_strength
    band = np.clip(band + fork, 0.0, 1.4)
    core_c = as_arr3(params.get("color_core", [1.0, 1.0, 1.0]))
    edge_c = as_arr3(params.get("color_edge", [0.55, 0.78, 1.0]))
    glow_c = as_arr3(params.get("color_glow", [0.30, 0.55, 1.0]))
    bandv = np.clip(band, 0.0, 1.0)[..., None]
    corev = np.clip(core, 0.0, 1.0)[..., None]
    rgb = glow_c * (1.0 - bandv) + edge_c * bandv
    rgb = rgb * (1.0 - corev) + core_c * corev
    alpha = np.clip(band + glow * 0.5 + core, 0.0, 1.0) * float(params.get("opacity", 1.0))
    return rgba(rgb, alpha)


def render_portal(params: dict[str, Any], w: int, h: int, t: float) -> np.ndarray:
    x, y = uv_grid(w, h)
    ux = x - 0.5
    uy = y - 0.5
    rr = np.sqrt(ux * ux + uy * uy) * 2.0
    ang = np.arctan2(uy, ux)
    radius = float(params.get("radius", 0.42))
    swirl_amount = float(params.get("swirl", 6.0)) / np.maximum(rr, 0.01)
    a = ang + swirl_amount + t * float(params.get("spin_speed", 1.4))
    arm_pattern = 0.5 + 0.5 * np.sin(a * float(params.get("arms", 5.0)))
    arm_pattern = np.power(arm_pattern, 2.5) * float(params.get("arm_strength", 0.6))
    spiral_x = np.cos(a) * rr * 4.0
    spiral_y = np.sin(a) * rr * 4.0
    n = vnoise(spiral_x + t * 0.4, spiral_y)
    pulse = 0.5 + 0.5 * math.sin(t * 1.7)
    depth = smoothstep(0.0, radius, rr) * (1.0 - float(params.get("depth_pulse", 0.35)) * pulse)
    void = as_arr3(params.get("color_void", [0.05, 0.0, 0.10]))
    outer = as_arr3(params.get("color_outer", [0.30, 0.10, 0.50]))
    mid = as_arr3(params.get("color_mid", [0.70, 0.45, 0.95]))
    inner = as_arr3(params.get("color_inner", [1.0, 1.0, 1.0]))
    s1 = smoothstep(0.0, radius * 0.4, rr)[..., None]
    s2 = (smoothstep(radius * 0.4, radius * 0.85, rr) * (0.6 + arm_pattern) * (0.7 + n * 0.3))[..., None]
    s3 = (arm_pattern * (1.0 - smoothstep(radius * 0.6, radius, rr)) * (1.0 - depth * 0.4))[..., None]
    rgb = void * (1.0 - s1) + outer * s1
    rgb = rgb * (1.0 - np.clip(s2, 0.0, 1.0)) + mid * np.clip(s2, 0.0, 1.0)
    rgb = rgb * (1.0 - np.clip(s3, 0.0, 1.0)) + inner * np.clip(s3, 0.0, 1.0)
    edge = 1.0 - smoothstep(radius, radius + 0.05, rr)
    alpha = edge * float(params.get("opacity", 1.0))
    return rgba(rgb, alpha)


def render_shield(params: dict[str, Any], w: int, h: int, t: float) -> np.ndarray:
    x, y = uv_grid(w, h)
    ux = x - 0.5
    uy = y - 0.5
    scale = float(params.get("hex_scale", 18.0))
    # Cheap hex-like lattice proxy: crossing triangular waves.
    gx = np.abs(fract((ux * scale) + 0.5) - 0.5)
    gy = np.abs(fract((uy * scale * 1.732) + 0.5) - 0.5)
    gd = np.abs(fract(((ux + uy * 0.577) * scale) + 0.5) - 0.5)
    hex_edge = (1.0 - smoothstep(0.015, 0.045, np.minimum.reduce([gx, gy, gd]))) * float(params.get("hex_strength", 0.45))
    rr = np.sqrt(ux * ux + uy * uy) * 2.0
    fres = np.power(np.clip(rr, 0.0, 1.0), float(params.get("fresnel_power", 2.5)))
    ripple = np.sin(rr * float(params.get("ripple_freq", 18.0)) - t * float(params.get("ripple_speed", 3.0))) * 0.5 + 0.5
    ripple = np.power(ripple, 4.0) * float(params.get("ripple_strength", 0.7))
    hit_age = float(params.get("hit_age", 0.0))
    hit = np.zeros_like(rr)
    if 0.0 < hit_age < 4.0:
        hp = params.get("hit_position", [0.5, 0.5])
        hd = np.sqrt((ux - (hp[0] - 0.5)) ** 2 + (uy - (hp[1] - 0.5)) ** 2)
        hit_radius = hit_age * 0.6
        ring = np.exp(-np.power((hd - hit_radius) * 6.0, 2.0))
        fade = 1.0 - smoothstep(0.0, 4.0, np.full_like(rr, hit_age))
        hit = ring * fade
    shield_c = as_arr3(params.get("color_shield", [0.40, 0.78, 1.0]))
    hit_c = as_arr3(params.get("color_hit", [1.0, 0.95, 0.55]))
    value = 0.4 + ripple + fres * 0.6 + hex_edge * 0.8
    rgb = shield_c * value[..., None]
    hitv = np.clip(hit, 0.0, 1.0)[..., None]
    rgb = rgb * (1.0 - hitv) + hit_c * hitv
    alpha = (fres * 0.7 + hex_edge + ripple * 0.3 + hit) * float(params.get("opacity", 1.0))
    # Round shield silhouette; keeps previews honest for spell use.
    alpha *= 1.0 - smoothstep(0.92, 1.08, rr)
    return rgba(rgb, alpha)


def render_dissolve(params: dict[str, Any], w: int, h: int, t: float) -> np.ndarray:
    x, y = uv_grid(w, h)
    scale = float(params.get("noise_scale", 8.0))
    scroll = float(params.get("scroll_speed", 0.7))
    warp_strength = float(params.get("warp_strength", 0.3))
    tt = t * scroll
    warp_x = fbm(x * scale + tt, y * scale, 5) - 0.5
    warp_y = fbm(x * scale, y * scale + tt * 0.7, 5) - 0.5
    sx = x + warp_x * warp_strength
    sy = y + warp_y * warp_strength
    n = fbm(sx * scale, sy * scale + tt, 5)
    bias = 1.0 - y
    n = n * 0.6 + bias * 0.4
    threshold = float(params.get("threshold", 0.45))
    edge_width = float(params.get("edge_width", 0.10))
    burnt = smoothstep(threshold - edge_width, threshold, n)
    edge = smoothstep(threshold, threshold + edge_width, n) - burnt
    visible = 1.0 - smoothstep(threshold + edge_width, threshold + edge_width * 1.5, n)
    # Synthetic base sprite silhouette for review.
    rect = (smoothstep(0.10, 0.18, x) * (1.0 - smoothstep(0.82, 0.90, x))
            * smoothstep(0.10, 0.18, y) * (1.0 - smoothstep(0.82, 0.90, y)))
    circle = 1.0 - smoothstep(0.35, 0.48, np.sqrt((x - 0.5) ** 2 + (y - 0.5) ** 2))
    base_alpha = np.maximum(rect * 0.75, circle)
    base = np.dstack([np.full_like(x, 0.42), np.full_like(x, 0.42), np.full_like(x, 0.46)])
    burn = as_arr3(params.get("color_burn", [1.0, 0.55, 0.10]))
    ash = as_arr3(params.get("color_ash", [0.18, 0.10, 0.07]))
    ember = as_arr3(params.get("color_ember", [1.0, 0.85, 0.30]))
    pulse = 0.7 + 0.3 * np.sin(t * 6.0 + n * 8.0)
    rgb = base.copy()
    edgev = np.clip(edge * 0.95, 0.0, 1.0)[..., None]
    rgb = rgb * (1.0 - edgev) + burn * edgev
    rgb += ember * edge[..., None] * pulse[..., None]
    burntv = np.clip(burnt, 0.0, 1.0)[..., None]
    rgb = rgb * (1.0 - burntv) + ash * burntv
    alpha = (base_alpha * visible + edge * 0.85) * float(params.get("opacity", 1.0))
    return rgba(rgb, alpha)


def render_cpu_frame(template: str, params: dict[str, Any], width: int, height: int, t: float) -> np.ndarray:
    if template == "ring_field_2d":
        return render_ring(params, width, height, t)
    if template == "beam_lightning_2d":
        return render_beam(params, width, height, t)
    if template == "portal_swirl_2d":
        return render_portal(params, width, height, t)
    if template == "shield_ripple_2d":
        return render_shield(params, width, height, t)
    if template == "dissolve_fire_2d":
        return render_dissolve(params, width, height, t)
    raise ValueError(f"no CPU preview renderer for template {template}")


def arr_to_image(frame: np.ndarray, background: list[float] | None = None) -> Image.Image:
    frame = np.clip(frame, 0.0, 1.0)
    if background is not None:
        bg = np.array(background[:3], dtype=np.float32)
        rgb = frame[..., :3] * frame[..., 3:4] + bg * (1.0 - frame[..., 3:4])
        out = np.dstack([rgb, np.ones(frame.shape[:2], dtype=np.float32)])
    else:
        out = frame
    return Image.fromarray((out * 255.0 + 0.5).astype(np.uint8), "RGBA")


def make_flipbook(images: list[Image.Image], columns: int = 8) -> Image.Image:
    if not images:
        raise ValueError("no images")
    w, h = images[0].size
    cols = min(columns, len(images))
    rows = math.ceil(len(images) / cols)
    sheet = Image.new("RGBA", (w * cols, h * rows), (0, 0, 0, 0))
    for i, img in enumerate(images):
        sheet.paste(img, ((i % cols) * w, (i // cols) * h))
    return sheet


def render_cpu_preview(out_dir: Path, template: str, params: dict[str, Any], preview: dict[str, Any]) -> list[Path]:
    width, height = preview.get("size", [256, 256])
    frames = int(preview.get("frames", 1))
    frames = max(1, min(frames, 32))
    duration = float(preview.get("duration_s", 1.8))
    background = preview.get("background", [0.035, 0.035, 0.055, 1.0])
    frame_dir = out_dir / "frames"
    frame_dir.mkdir(exist_ok=True)
    frame_paths: list[Path] = []
    images: list[Image.Image] = []
    for i in range(frames):
        t = (i / max(1, frames - 1)) * duration
        frame = render_cpu_frame(template, params, width, height, t)
        transparent = arr_to_image(frame)
        composited = arr_to_image(frame, background)
        frame_path = frame_dir / f"frame_{i:03d}.png"
        transparent.save(frame_path)
        frame_paths.append(frame_path)
        images.append(composited)
    images[0].save(out_dir / "preview.png")
    if len(images) > 1:
        make_flipbook(images).save(out_dir / "flipbook.png")
    else:
        shutil.copy2(out_dir / "preview.png", out_dir / "flipbook.png")
    return frame_paths


def colorfulness(rgb: np.ndarray) -> float:
    if rgb.size == 0:
        return 0.0
    rg = rgb[..., 0] - rgb[..., 1]
    yb = 0.5 * (rgb[..., 0] + rgb[..., 1]) - rgb[..., 2]
    std_rg = float(np.std(rg))
    std_yb = float(np.std(yb))
    mean_rg = float(np.mean(rg))
    mean_yb = float(np.mean(yb))
    return math.sqrt(std_rg * std_rg + std_yb * std_yb) + 0.3 * math.sqrt(mean_rg * mean_rg + mean_yb * mean_yb)


def edge_energy(gray: np.ndarray) -> float:
    if gray.size == 0:
        return 0.0
    gx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
    gy = np.abs(np.diff(gray, axis=0, prepend=gray[:1, :]))
    return float(np.mean(np.sqrt(gx * gx + gy * gy)))


def bbox_aspect(mask: np.ndarray) -> float:
    ys, xs = np.where(mask)
    if len(xs) < 4:
        return 0.0
    bw = max(1, int(xs.max() - xs.min() + 1))
    bh = max(1, int(ys.max() - ys.min() + 1))
    a = bw / bh
    return float(max(a, 1.0 / max(a, 1e-6)))


def image_metrics(image_paths: list[Path]) -> dict[str, float]:
    per_frame = []
    arrays = []
    for path in image_paths:
        img = Image.open(path).convert("RGBA")
        arr = np.asarray(img).astype(np.float32) / 255.0
        arrays.append(arr)
        alpha = arr[..., 3]
        mask = alpha > 0.04
        rgb = arr[..., :3]
        premul_luma = (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]) * np.maximum(alpha, 0.2)
        coverage = float(np.mean(mask))
        if np.any(mask):
            yy, xx = np.indices(alpha.shape)
            weights = alpha * mask
            denom = max(float(weights.sum()), 1e-6)
            cx = float((xx * weights).sum() / denom) / max(1, alpha.shape[1] - 1)
            cy = float((yy * weights).sum() / denom) / max(1, alpha.shape[0] - 1)
            center_distance = math.hypot(cx - 0.5, cy - 0.5)
            active_rgb = rgb[mask]
            active_luma = premul_luma[mask]
        else:
            center_distance = 0.75
            active_rgb = rgb.reshape(-1, 3)
            active_luma = premul_luma.reshape(-1)
        per_frame.append({
            "coverage": coverage,
            "mean_alpha": float(np.mean(alpha)),
            "luma_mean": float(np.mean(active_luma)) if active_luma.size else 0.0,
            "contrast": float(np.std(active_luma)) if active_luma.size else 0.0,
            "colorfulness": colorfulness(active_rgb),
            "edge_energy": edge_energy(premul_luma),
            "center_distance": center_distance,
            "clip_high": float(np.mean((rgb > 0.985) & (alpha[..., None] > 0.08))),
            "clip_low": float(np.mean((rgb < 0.010) & (alpha[..., None] > 0.08))),
            "aspect": bbox_aspect(mask),
        })

    motions = []
    for prev, cur in zip(arrays, arrays[1:]):
        motions.append(float(np.mean(np.abs(cur - prev))))

    def mean_key(key: str) -> float:
        return float(statistics.fmean([m[key] for m in per_frame]))

    metrics = {key: mean_key(key) for key in per_frame[0]}
    metrics["motion"] = float(statistics.fmean(motions)) if motions else 0.0
    metrics["flicker"] = float(np.std([m["coverage"] for m in per_frame])) if len(per_frame) > 1 else 0.0
    metrics["frames"] = float(len(image_paths))
    return metrics


def score_range(value: float, lo: float, hi: float) -> float:
    if lo <= value <= hi:
        return 1.0
    span = max(hi - lo, 1e-6)
    if value < lo:
        return max(0.0, 1.0 - (lo - value) / span)
    return max(0.0, 1.0 - (value - hi) / span)


def score_min(value: float, lo: float, target: float | None = None) -> float:
    target = target if target is not None else max(lo * 2.0, lo + 0.05)
    if value >= target:
        return 1.0
    if value <= 0:
        return 0.0
    return max(0.0, min(1.0, (value - lo * 0.25) / max(target - lo * 0.25, 1e-6)))


def review_metrics(metrics: dict[str, float], role: str) -> dict[str, Any]:
    rubric = ROLE_RUBRICS.get(role, ROLE_RUBRICS["aura"])
    weights = rubric["weights"]
    component_scores: dict[str, float] = {}
    component_scores["coverage"] = score_range(metrics["coverage"], *rubric["coverage"])
    component_scores["motion"] = score_range(metrics["motion"], *rubric["motion"])
    component_scores["center"] = score_range(metrics["center_distance"], 0.0, rubric["center_max"])
    component_scores["color"] = score_min(metrics["colorfulness"], rubric["colorfulness_min"])
    component_scores["edge"] = score_range(metrics["edge_energy"], *rubric["edge"])
    component_scores["contrast"] = score_min(metrics["contrast"], rubric["contrast_min"])
    if "aspect_min" in rubric:
        component_scores["aspect"] = score_min(metrics["aspect"], rubric["aspect_min"], rubric["aspect_min"] * 1.5)

    total_weight = 0.0
    weighted = 0.0
    for key, value in component_scores.items():
        weight = float(weights.get(key, 0.0))
        weighted += value * weight
        total_weight += weight

    score = 100.0 * weighted / max(total_weight, 1e-6)
    # Hard penalties that tend to indicate poor review value.
    if metrics["coverage"] < 0.006 or metrics["coverage"] > 0.96:
        score -= 24.0
    if metrics["clip_high"] > 0.14:
        score -= min(14.0, metrics["clip_high"] * 70.0)
    if metrics["flicker"] > 0.20:
        score -= min(12.0, metrics["flicker"] * 60.0)
    score = float(np.clip(score, 0.0, 100.0))

    gate_issues: list[str] = []
    gate_warnings: list[str] = []
    cov_lo, cov_hi = rubric["coverage"]
    if metrics["coverage"] < 0.006:
        gate_issues.append("near-empty alpha coverage")
    elif metrics["coverage"] < cov_lo * 0.45:
        gate_warnings.append("role coverage far below target")
    if metrics["coverage"] > 0.96:
        gate_issues.append("nearly full-screen alpha coverage")
    elif metrics["coverage"] > min(0.94, cov_hi * 1.35):
        gate_warnings.append("role coverage far above target")
    if metrics["contrast"] < rubric["contrast_min"] * 0.70:
        gate_warnings.append("weak contrast")
    if metrics["clip_high"] > 0.20:
        gate_warnings.append("highlight clipping")
    if metrics["flicker"] > 0.20:
        gate_warnings.append("strong frame-to-frame flicker")
    if role not in {"ground", "ui"} and metrics["frames"] > 1 and metrics["motion"] < rubric["motion"][0] * 0.65:
        gate_warnings.append("motion below role target")
    if role in {"beam", "projectile"} and metrics["aspect"] < ROLE_RUBRICS[role].get("aspect_min", 1.0):
        gate_warnings.append("silhouette aspect below role target")

    if gate_issues:
        grade = "reject"
    elif score >= 88 and not gate_warnings:
        grade = "keep"
    elif score >= 76:
        grade = "review"
    elif score >= 60:
        grade = "maybe"
    else:
        grade = "reject"
    return {
        "score": round(score, 2),
        "grade": grade,
        "components": {k: round(v, 3) for k, v in component_scores.items()},
        "gate_issues": gate_issues,
        "gate_warnings": gate_warnings,
    }


def mutation_hints(metrics: dict[str, float], role: str, params: dict[str, Any]) -> list[str]:
    rubric = ROLE_RUBRICS.get(role, ROLE_RUBRICS["aura"])
    hints: list[str] = []
    cov_lo, cov_hi = rubric["coverage"]
    if metrics["coverage"] < cov_lo:
        hints.append("coverage low: increase radius/thickness/edge_width/opacity, or reduce dissolve threshold")
    elif metrics["coverage"] > cov_hi:
        hints.append("coverage high: reduce radius/thickness/glow/opacity, or increase dissolve threshold")
    if metrics["contrast"] < rubric["contrast_min"]:
        hints.append("contrast low: widen color separation, add hotter core/edge, or reduce background-like colors")
    if metrics["colorfulness"] < rubric["colorfulness_min"]:
        hints.append("color weak: switch palette or push core/edge/glow colors farther apart")
    if metrics["edge_energy"] < rubric["edge"][0]:
        hints.append("too smooth: increase frequency/noise/rune/hex/jaggedness or sharpen edge_width")
    elif metrics["edge_energy"] > rubric["edge"][1]:
        hints.append("too noisy: lower frequency/noise/jaggedness or widen edge_width")
    if metrics["motion"] < rubric["motion"][0] and metrics["frames"] > 1:
        hints.append("motion low: increase speed/pulse/spin/scroll parameters")
    if metrics["center_distance"] > rubric["center_max"]:
        hints.append("off center: adjust hit_position/arc or rebalance template geometry")
    if role in {"beam", "projectile"} and metrics["aspect"] < ROLE_RUBRICS[role].get("aspect_min", 1.0):
        hints.append("beam silhouette weak: increase lengthwise structure and reduce vertical thickness")
    if not hints:
        hints.append("good candidate: mutate locally around these params with smaller jitter")
    return hints


def candidate_review(out_dir: Path, role: str, params: dict[str, Any]) -> dict[str, Any]:
    frame_paths = sorted((out_dir / "frames").glob("frame_*.png"))
    if not frame_paths and (out_dir / "preview.png").exists():
        frame_paths = [out_dir / "preview.png"]
    metrics = image_metrics(frame_paths)
    review = review_metrics(metrics, role)
    review["metrics"] = {k: round(v, 5) for k, v in metrics.items()}
    review["hints"] = mutation_hints(metrics, role, params)
    return review


def update_request_review(out_dir: Path, review: dict[str, Any]) -> None:
    path = out_dir / "request.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["review"] = review
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_gallery(batch_dir: Path, rows: list[dict[str, Any]]) -> None:
    rows = sorted(rows, key=lambda r: r["review"]["score"], reverse=True)
    cards = []
    for row in rows:
        rel = row["id"]
        review = row["review"]
        metrics = review["metrics"]
        img_src = f"{rel}/flipbook.png" if (batch_dir / rel / "flipbook.png").exists() else f"{rel}/preview.png"
        params_html = html.escape(json.dumps(row["params"], indent=2))
        hints = "".join(f"<li>{html.escape(h)}</li>" for h in review.get("hints", []))
        gates = "".join(
            f"<li>{html.escape(g)}</li>"
            for g in [*review.get("gate_issues", []), *review.get("gate_warnings", [])]
        )
        gate_block = f"<div class=\"gates\"><strong>gates</strong><ul>{gates}</ul></div>" if gates else ""
        cards.append(f"""
        <article class="card {review['grade']}">
          <div class="thumb"><img src="{html.escape(img_src)}" loading="lazy" alt="{html.escape(row['id'])}"></div>
          <div class="body">
            <h2>{html.escape(row['id'])}</h2>
            <div class="meta">
              <span>{html.escape(row['template'])}</span>
              <span>{html.escape(row['role'])}</span>
              <strong>{review['score']:.2f}</strong>
              <span>{html.escape(review['grade'])}</span>
            </div>
            <div class="metrics">
              cov {metrics['coverage']:.3f} | motion {metrics['motion']:.3f} | contrast {metrics['contrast']:.3f} |
              color {metrics['colorfulness']:.3f} | edge {metrics['edge_energy']:.3f} | center {metrics['center_distance']:.3f}
            </div>
            {gate_block}
            <ul>{hints}</ul>
            <details><summary>params</summary><pre>{params_html}</pre></details>
          </div>
        </article>
        """)
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Shader Batch Review</title>
  <style>
    :root {{ color-scheme: dark; font-family: Segoe UI, system-ui, sans-serif; background:#0b0d12; color:#e6edf7; }}
    body {{ margin:0; padding:24px; }}
    header {{ display:flex; align-items:end; justify-content:space-between; gap:20px; margin-bottom:18px; }}
    h1 {{ margin:0; font-size:24px; }}
    .sub {{ color:#94a3b8; font-size:13px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(330px, 1fr)); gap:14px; }}
    .card {{ background:#111722; border:1px solid #263246; border-radius:8px; overflow:hidden; }}
    .card.keep {{ border-color:#63e6be; }}
    .card.review {{ border-color:#ffd166; }}
    .card.maybe {{ border-color:#748ffc; }}
    .card.reject {{ opacity:.72; }}
    .thumb {{ background:#05070a; min-height:180px; display:flex; align-items:center; justify-content:center; }}
    img {{ max-width:100%; display:block; image-rendering:auto; }}
    .body {{ padding:12px; }}
    h2 {{ margin:0 0 8px; font-size:16px; }}
    .meta {{ display:flex; flex-wrap:wrap; gap:6px; align-items:center; }}
    .meta span, .meta strong {{ background:#1c2635; border-radius:999px; padding:3px 8px; font-size:12px; }}
    .meta strong {{ color:#111722; background:#e6edf7; }}
    .metrics {{ color:#b6c2d2; font-size:12px; margin-top:8px; line-height:1.5; }}
    .gates {{ color:#ffd166; font-size:12px; margin-top:8px; }}
    .gates strong {{ text-transform:uppercase; letter-spacing:.08em; font-size:10px; }}
    .gates ul {{ margin-top:4px; }}
    ul {{ color:#cbd5e1; font-size:12px; padding-left:18px; }}
    details {{ margin-top:8px; }}
    summary {{ cursor:pointer; color:#9ab7ff; }}
    pre {{ overflow:auto; white-space:pre-wrap; font-size:11px; color:#d8dee9; background:#080b10; padding:8px; border-radius:6px; }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Shader Batch Review</h1>
      <div class="sub">Sorted by non-OCR review score. Keep/review candidates are the ones to inspect visually.</div>
    </div>
    <div class="sub">{html.escape(batch_dir.name)} | {len(rows)} candidates</div>
  </header>
  <section class="grid">
    {''.join(cards)}
  </section>
</body>
</html>
"""
    (batch_dir / "gallery.html").write_text(html_text, encoding="utf-8")


def write_llm_packet(batch_dir: Path, rows: list[dict[str, Any]], keep_top: int) -> None:
    rows = sorted(rows, key=lambda r: r["review"]["score"], reverse=True)
    top = rows[:keep_top]
    packet = {
        "batch": batch_dir.name,
        "created": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(rows),
        "recommended_for_user_review": [
            {
                "id": r["id"],
                "score": r["review"]["score"],
                "grade": r["review"]["grade"],
                "template": r["template"],
                "role": r["role"],
                "preview": str((batch_dir / r["id"] / "flipbook.png").relative_to(batch_dir)),
                "metrics": r["review"]["metrics"],
                "hints": r["review"]["hints"],
                "gate_issues": r["review"].get("gate_issues", []),
                "gate_warnings": r["review"].get("gate_warnings", []),
                "params": r["params"],
            }
            for r in top
            if r["review"]["grade"] in {"keep", "review", "maybe"}
        ],
        "low_score_summary": [
            {"id": r["id"], "score": r["review"]["score"], "hints": r["review"]["hints"][:2]}
            for r in rows[-min(8, len(rows)):]
        ],
        "next_iteration_policy": [
            "Preserve top candidate params and make local mutations around them.",
            "Do not ask the LLM to OCR the image; use metrics plus gallery thumbnails.",
            "Use Godot-rendered previews for final acceptance when the Godot binary is available.",
            "Escalate only keep/review candidates to human review.",
        ],
    }
    (batch_dir / "llm_review_packet.json").write_text(json.dumps(packet, indent=2), encoding="utf-8")

    md_lines = [
        f"# Shader Batch Review - {batch_dir.name}",
        "",
        "Use this as the LLM handoff. Scores are computed from image data, not screenshot OCR.",
        "",
        "## Top candidates",
        "",
    ]
    for r in top:
        review = r["review"]
        md_lines.extend([
            f"### {r['id']} - {review['score']:.2f} ({review['grade']})",
            "",
            f"- Template: `{r['template']}`",
            f"- Role: `{r['role']}`",
            f"- Preview: `{r['id']}/flipbook.png`",
            f"- Metrics: coverage `{review['metrics']['coverage']:.3f}`, motion `{review['metrics']['motion']:.3f}`, contrast `{review['metrics']['contrast']:.3f}`, color `{review['metrics']['colorfulness']:.3f}`, edge `{review['metrics']['edge_energy']:.3f}`",
            f"- Gates: {('; '.join([*review.get('gate_issues', []), *review.get('gate_warnings', [])]) or 'none')}",
            f"- Hints: {'; '.join(review['hints'])}",
            "",
        ])
    md_lines.extend([
        "## Next iteration",
        "",
        "Mutate locally around the top `keep` and `review` candidates. Reject low-coverage, full-screen, low-contrast, or over-noisy outputs automatically before human review.",
    ])
    (batch_dir / "llm_review.md").write_text("\n".join(md_lines), encoding="utf-8")


def run_batch(args: argparse.Namespace) -> Path:
    rng = random.Random(args.seed)
    parent_requests = []
    for path in args.parent_request or []:
        parent_requests.append(json.loads(path.read_text(encoding="utf-8")))
    template_names = args.template or sorted({p["template"] for p in parent_requests}) or list(TEMPLATE_ROLE.keys())
    batch_id = args.batch_id or datetime.now().strftime("shader_batch_%Y%m%d_%H%M%S")
    batch_dir = BATCHES_DIR / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    generated = 0
    # Round-robin across templates so small exploratory batches still cover
    # every requested effect family instead of exhausting one template at a
    # time and starving later templates.
    template_cycle = list(template_names)
    template_cache: dict[str, tuple[str, list[Uniform], str]] = {}
    while generated < args.count:
        parent = parent_requests[generated % len(parent_requests)] if parent_requests else None
        template = parent["template"] if parent else template_cycle[generated % len(template_cycle)]
        template_path = TEMPLATES_DIR / f"{template}.gdshader"
        if not template_path.exists():
            raise SystemExit(f"template not found: {template_path}")
        if template not in template_cache:
            shader_text = template_path.read_text(encoding="utf-8")
            uniforms = parse_uniforms(shader_text)
            role = args.role if args.role != "auto" else (parent or {}).get("role") or TEMPLATE_ROLE.get(template, "aura")
            template_cache[template] = (shader_text, uniforms, role)
        shader_text, uniforms, role = template_cache[template]
        generated += 1
        shader_id = f"{batch_id}_{template}_{generated:03d}"
        if parent:
            params = mutate_params(parent.get("params", {}), uniforms, rng, args.mutation_strength)
            intent = args.intent or parent.get("intent", "local mutation")
        else:
            params = sample_params(template, uniforms, args.intent, role, rng)
            intent = args.intent
        preview = preview_config_for(template, role, args.size, args.frames)
        out_dir = emit_candidate(batch_dir, shader_id, template, shader_text, params, preview, intent, role)
        frame_paths = render_cpu_preview(out_dir, template, params, preview)
        review = candidate_review(out_dir, role, params)
        review["render_source"] = "cpu_proxy"
        update_request_review(out_dir, review)
        rows.append({
            "id": shader_id,
            "template": template,
            "role": role,
            "params": params,
            "preview": preview,
            "frames": [str(p.relative_to(out_dir)) for p in frame_paths],
            "review": review,
        })

    rows = sorted(rows, key=lambda r: r["review"]["score"], reverse=True)
    (batch_dir / "batch_summary.json").write_text(json.dumps({
        "batch": batch_id,
        "intent": args.intent,
        "seed": args.seed,
        "parent_requests": [str(p) for p in (args.parent_request or [])],
        "count": len(rows),
        "created": datetime.now(timezone.utc).isoformat(),
        "rows": rows,
    }, indent=2), encoding="utf-8")
    write_gallery(batch_dir, rows)
    write_llm_packet(batch_dir, rows, args.keep_top)
    return batch_dir


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--intent", default="arcane spell effects for Godot", help="Natural-language intent used for palette/range hints")
    ap.add_argument("--template", action="append", choices=sorted(TEMPLATE_ROLE), help="Template to explore. Repeat for multiple. Omit for all.")
    ap.add_argument("--role", default="auto", choices=["auto", *sorted(ROLE_RUBRICS)], help="Review role/rubric")
    ap.add_argument("--count", type=int, default=24, help="Total candidates to generate")
    ap.add_argument("--frames", type=int, default=8, help="CPU proxy frames per candidate")
    ap.add_argument("--size", type=int, default=256, help="Preview square size; beam uses 2x width")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--batch-id", help="Output batch id")
    ap.add_argument("--keep-top", type=int, default=8)
    ap.add_argument("--parent-request", action="append", type=Path,
                    help="Existing request.json to mutate around. Repeat for multiple parents.")
    ap.add_argument("--mutation-strength", type=float, default=0.22,
                    help="Local mutation size when --parent-request is used")
    args = ap.parse_args()
    batch_dir = run_batch(args)
    print(f"wrote {batch_dir}")
    print(f"gallery: {batch_dir / 'gallery.html'}")
    print(f"llm packet: {batch_dir / 'llm_review_packet.json'}")


if __name__ == "__main__":
    main()
