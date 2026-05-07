"""Pydantic schemas for VFX effects.

Per `research/I_vfx_lab_local_audit_and_migration_plan.md`'s recommended
content-first contract:

  effect.json -> bake -> manifest.json + frames + (particles|field|fragments) ->
  pack flipbook -> Godot export

The `Effect` model is the canonical authoring artifact. Backends accept it
and produce the same `BakeManifest` shape so they're swappable.

v2 (2026-05-06): adds `export_target` for 3D Godot scene shapes,
`EffectVisual3D` for billboard/depth/world-size hints, and new backends
(volumetric_fog, runtime_trail, decal_flipbook, vat, plus deferred GPU
backends from GPU_BACKENDS_PLAN.md). Existing v1 effects stay valid: every
new field has a default that mirrors the old 2D behavior.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

EffectKind = Literal["spell", "environment", "projectile", "destruction", "ambient"]
Phenomenon = Literal["liquid", "fire", "smoke", "lightning", "swarm", "swirl",
                     "shatter", "rubble", "aura", "field", "particle"]
# v1 CPU backends + v2 round-2 additions. New literal values are additive;
# extra="forbid" only blocks unknown *fields*, not unknown literal values.
Backend = Literal[
    # v1 (implemented):
    "particle_cpu", "fracture2d", "smoke_field", "external",
    # v2 round-2 additions:
    "volumetric_fog",   # bakes Texture3D density volume (CPU numpy noise)
    "runtime_trail",    # no bake; runtime mesh trail (RibbonTrail/Tube)
    "decal_flipbook",   # underlying flipbook baker + Decal export wrapper
    "vat",              # deferred stub
    # GPU bakers from GPU_BACKENDS_PLAN.md (deferred until 5090 free):
    "taichi_particle", "taichi_smoke", "warp", "phiflow", "liquidfun",
]
ExportTarget = Literal["2d", "3d_billboard", "decal", "fog_volume", "mesh_trail"]


class EffectVisual(BaseModel):
    model_config = ConfigDict(extra="forbid")

    palette: list[Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]] = Field(
        default_factory=lambda: ["#ffffff"], min_length=1, max_length=6,
    )
    blend: Literal["alpha", "additive"] = "alpha"
    background: Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")] = "#00000000"
    bloom: bool = False


class EffectVisual3D(BaseModel):
    """3D-specific render hints. Only consulted when `export_target != '2d'`.

    Defaults are tuned for 2.5D iso scenes (camera-faced billboards, no shadows,
    additive-friendly depth).
    """
    model_config = ConfigDict(extra="forbid")

    billboard_mode: Literal["off", "enabled", "y_axis", "particles"] = "enabled"
    cast_shadow: bool = False
    receive_shadow: bool = False
    depth_test: Literal["enabled", "disabled", "less"] = "enabled"
    # World size in metres for 3d_billboard QuadMesh / decal extents / fog AABB.
    # If None, the exporter falls back to bounds_px / 100.
    world_size_m: float | None = Field(default=None, ge=0.1, le=64.0)


class GameplayHooks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shape: Literal["projectile", "self", "aura", "cone", "line", "point", "touch"] = "point"
    damage_tags: list[str] = Field(default_factory=list, max_length=8)
    collision: Literal["first_hit", "pierce", "none"] = "none"


class Effect(BaseModel):
    """The spell.json / effect.json contract."""
    model_config = ConfigDict(extra="forbid")

    id: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")]
    kind: EffectKind = "spell"
    phenomenon: Phenomenon
    backend: Backend
    duration_s: Annotated[float, Field(gt=0.0, le=60.0)] = 1.0
    fps: Annotated[int, Field(ge=8, le=60)] = 24
    bounds_px: tuple[Annotated[int, Field(ge=64, le=2048)],
                     Annotated[int, Field(ge=64, le=2048)]] = (256, 256)
    visual: EffectVisual = Field(default_factory=EffectVisual)
    visual3d: EffectVisual3D = Field(default_factory=EffectVisual3D)
    backend_params: dict = Field(default_factory=dict)
    gameplay: GameplayHooks = Field(default_factory=GameplayHooks)
    # Optional taxonomy used by the gallery + game_data wiring.
    # `element` and `archetype` are conventions the v2 catalogue follows
    # (fire/ice/lightning/earth/arcane/shadow/physical x projectile/burst/aura/impact).
    element: Literal["fire", "ice", "lightning", "earth", "arcane",
                     "shadow", "physical", "neutral"] = "neutral"
    archetype: Literal["projectile", "burst", "aura", "impact", "ambient",
                       "destruction", "trail"] = "burst"
    tags: list[str] = Field(default_factory=list, max_length=12)
    # 3D-aware export hint. Legacy effects default to 2D AnimatedSprite2D.
    export_target: ExportTarget = "2d"
    notes: str = ""

    @property
    def n_frames(self) -> int:
        return max(int(round(self.duration_s * self.fps)), 1)


class BakeManifest(BaseModel):
    """Returned by every backend baker. Stable across backends."""
    model_config = ConfigDict(extra="forbid")

    effect_id: str
    backend: Backend
    n_frames: int
    fps: int
    bounds_px: tuple[int, int]
    flipbook: str  # path to flipbook.png (atlased) - "" for non-frame backends (fog)
    frames_dir: str  # path to frames/ - "" for non-frame backends
    extras: dict = Field(default_factory=dict)  # particles.json, fragments.json, audio_cues, density_volume, etc.
    metrics: dict = Field(default_factory=dict)
    timestamp: str = ""
