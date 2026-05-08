extends RefCounted
class_name CamFraming

# Phase C zoom-level presets. Visible diameter on the longer screen axis (16:9
# horizontal) in world meters. Reference points only — capture scenes set the
# camera's `visible_diameter_m` directly to one of these values.

# Iso ARPG (Diablo, Path of Exile): tight, single-screen combat framing.
const ISO_ARPG_DIAMETER_M: float = 40.0

# Iso strategy (Civ, RTS): mid-zoom unit + city overview.
const ISO_STRATEGY_DIAMETER_M: float = 300.0

# Topdown game-tile (Stardew-ish): per-screen play area.
const TOPDOWN_GAME_TILE_DIAMETER_M: float = 50.0

# Topdown minimap: whole region or large radius for navigation.
const TOPDOWN_MINIMAP_DIAMETER_M: float = 10000.0
