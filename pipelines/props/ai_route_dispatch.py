"""AI-route dispatcher for the props pipeline.

Given a concept image + render_class hint (and optional flags), return:
  - which AI route to use (trellis2 / hunyuan3d / meshy)
  - the right per-route settings to hit the target quality/cost

**TRELLIS2 IS THE DEFAULT (2026-05-06).** Phase 11A sweep showed Trellis2
beats HY3D-2.1 on visual quality at every config — even Trellis2's lowest
setting (49k faces, 4s) looks better than HY3D's most expensive (100k faces,
677s). HY3D is kept around as a fallback only when caller has integration
constraints (e.g. ComfyUI batch authoring infrastructure already wired).

Decision matrix is informed by the Phase 11A sweep:

  HY3D-2.1 sweep (Egyptian obelisk concept):
    baseline    40k f / 1024² /  90s / 1.6 MB
    hi_geo     100k f / 1024² /  74s / 3.0 MB   (HY3D sweet spot, but still < t2_low)
    hi_paint    40k f / 2048² / 387s / 3.1 MB
    hero_max   100k f / 2048² / 677s / 5.4 MB

  Trellis2 sweep (same concept, mesh gen ~23s + postprocess):
    low        49k f / 1024² /  4s / 4.0 MB    ← scatter-grade, beats HY3D hero_max
    mid       194k f / 2048² /  8s / 13.8 MB   ← default
    hi        485k f / 2048² / 18s / 23.1 MB   ← max-quality hero
    hi_tex    194k f / 4096² / 20s / 32.1 MB   ← when texture detail dominates

See `world/props/ai_routes/AB_hy3d_vs_trellis2_2026_05_06.md` for full A/B doc.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


RenderClass = Literal["hero_prop", "scene_prop", "scatter_multimesh"]
Route = Literal["hunyuan3d", "trellis2", "meshy"]


@dataclass
class RouteDecision:
    route: Route
    settings: dict
    reason: str


# Per-route preset libraries. Keep separate so callers can build their own
# bespoke configs without re-implementing the dispatcher.
HY3D_PRESETS = {
    # 40k cap, 1024² tex, 90s. Cheap baseline; OK for scatter/scene where
    # detail isn't visible at distance.
    "scatter":  dict(octree=384, max_facenum=40000,  view_size=512, texture_size=1024, paint_steps=10),
    # 100k cap, 1024² tex, 74s. Sweet spot: more geometry detail at slightly
    # lower wall-clock than baseline (sweep confirmed).
    "balanced": dict(octree=512, max_facenum=100000, view_size=512, texture_size=1024, paint_steps=10),
    # Avoid: 387-677s for marginal gains over `balanced`. Documented for
    # completeness; dispatcher should not pick these by default.
    "hi_paint": dict(octree=384, max_facenum=40000,  view_size=1024, texture_size=2048, paint_steps=20),
    "hero_max": dict(octree=512, max_facenum=100000, view_size=1024, texture_size=2048, paint_steps=30),
}

TRELLIS2_PRESETS = {
    # 49k cap, 1024² tex, 4s postprocess (+ 23s one-time mesh gen).
    "scatter":  dict(decimation_target=50000,  texture_size=1024),
    # 194k cap, 2048² tex, 8s postprocess. Trellis2 default; beats every HY3D
    # config on visual detail per the sweep.
    "balanced": dict(decimation_target=200000, texture_size=2048),
    # 485k cap, 2048² tex, 18s. Use for true hero shots where polycount budget
    # exists. May need decimation downstream for in-engine use.
    "hero":     dict(decimation_target=500000, texture_size=2048),
    # 194k cap, 4096² tex, 20s. Use when texture detail (carved hieroglyphs,
    # weathering, fine relief) matters more than mesh density.
    "hi_tex":   dict(decimation_target=200000, texture_size=4096),
}

# Cloud route (placeholder shape; actual settings depend on Meshy API contract).
MESHY_PRESETS = {
    "balanced": dict(art_style="realistic", target_polycount=50000, texture_richness="high"),
}


def pick_route(
    render_class: RenderClass,
    *,
    has_fine_relief: bool = False,
    prefer_route: Route | None = None,
    hero_polycount_budget_ok: bool = False,
    cloud_spend_authorized: bool = False,
    use_hy3d_for_comfy_integration: bool = False,
) -> RouteDecision:
    """Pick (route, settings) for a prop.

    Default route is Trellis2 because the Phase 11A sweep showed it dominates
    HY3D-2.1 visually at every config. HY3D is selected only when the caller
    explicitly asks (via prefer_route='hunyuan3d' or use_hy3d_for_comfy_integration).

    Args:
        render_class: 'hero_prop' (close camera), 'scene_prop' (mid distance),
            or 'scatter_multimesh' (biome scatter, far distance).
        has_fine_relief: Concept image has carved relief / hieroglyphs / fine
            engraved detail. Bumps the Trellis2 preset to `hero` if budget_ok.
        prefer_route: Force a specific route regardless of heuristics.
        hero_polycount_budget_ok: Caller commits the scene can afford a 485k+
            face mesh without LOD-decimation upstream. Default False — most
            scenes need decimation downstream anyway.
        cloud_spend_authorized: Caller has authorized Meshy cloud spend for
            this prop. Required for the `meshy` route.
        use_hy3d_for_comfy_integration: Caller has ComfyUI batch authoring
            infrastructure wired and prefers HY3D's workflow. Falls back to
            HY3D presets matching the render_class.

    Returns:
        RouteDecision(route, settings, reason).
    """
    if prefer_route is not None:
        if prefer_route == "trellis2":
            preset = "hero" if (hero_polycount_budget_ok and render_class == "hero_prop") else "balanced"
            return RouteDecision("trellis2", TRELLIS2_PRESETS[preset],
                                 f"explicit prefer_route='trellis2' ({preset})")
        if prefer_route == "hunyuan3d":
            preset = "scatter" if render_class == "scatter_multimesh" else "balanced"
            return RouteDecision("hunyuan3d", HY3D_PRESETS[preset],
                                 f"explicit prefer_route='hunyuan3d' ({preset})")
        if prefer_route == "meshy":
            if cloud_spend_authorized:
                return RouteDecision("meshy", MESHY_PRESETS["balanced"],
                                     "explicit prefer_route='meshy' + cloud_spend_authorized")
            # Fall through to local default if cloud not authorized.

    if use_hy3d_for_comfy_integration:
        if render_class == "scatter_multimesh":
            return RouteDecision("hunyuan3d", HY3D_PRESETS["scatter"],
                                 "use_hy3d_for_comfy_integration + scatter")
        return RouteDecision("hunyuan3d", HY3D_PRESETS["balanced"],
                             f"use_hy3d_for_comfy_integration + {render_class}")

    # Default Trellis2-first dispatch.
    if render_class == "scatter_multimesh":
        # Biome scatter — far distance, low polycount budget per instance.
        # `low` keeps GLB at ~4 MB and 49k faces.
        return RouteDecision("trellis2", TRELLIS2_PRESETS["scatter"],
                             "scatter_multimesh: Trellis2 low (49k/1024²/4s + 23s mesh gen)")

    if render_class == "hero_prop" and has_fine_relief and hero_polycount_budget_ok:
        return RouteDecision("trellis2", TRELLIS2_PRESETS["hero"],
                             "hero_prop + fine_relief + budget_ok: Trellis2 hero (485k/2048²/18s)")

    # Default for hero_prop and scene_prop: Trellis2 balanced. Beats HY3D
    # hero_max visually for ~100x less wall-clock and 1/8 the GLB size.
    return RouteDecision("trellis2", TRELLIS2_PRESETS["balanced"],
                         f"{render_class}: Trellis2 balanced (194k/2048²/8s + 23s mesh gen)")


def cli_demo() -> None:
    cases = [
        # prop_id, render_class, has_fine_relief, budget_ok, use_hy3d_comfy
        ("ruined_obelisk_a", "hero_prop", True,  False, False),
        ("rock_small_a01",   "scatter_multimesh", False, False, False),
        ("crate_wood",       "scene_prop", False, False, False),
        ("statue_warrior",   "hero_prop", True,  True,  False),
        ("simple_lantern",   "hero_prop", False, False, False),
        ("biome_scatter_hy3d", "scatter_multimesh", False, False, True),
    ]
    print(f"{'prop':<22} {'class':<20} {'relief':<6} {'budget':<6} {'comfy':<6} -> route + preset")
    print("-" * 130)
    for prop, rc, relief, budget, comfy in cases:
        d = pick_route(rc, has_fine_relief=relief, hero_polycount_budget_ok=budget,
                       use_hy3d_for_comfy_integration=comfy)
        print(f"{prop:<22} {rc:<20} {str(relief):<6} {str(budget):<6} {str(comfy):<6} {d.route} | {d.reason}")


if __name__ == "__main__":
    cli_demo()
