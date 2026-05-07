"""HUD mockup generator (Godot 4.5 .tscn + PIL preview PNG).

Per research D §6: closes v1's dogfooding gap by emitting a real assembled
HUD scene that imports the Theme + atlas + faction-themed 9-slice frames.

Outputs per --faction:

  ui/godot/hud_<faction>.tscn        Godot 4.5 Control-tree scene
  ui/hud_preview_<faction>.png       PIL render mirroring the .tscn layout

Layout (1920x1080 design viewport, scales via Control anchors):

  +--------------------------------------------------+
  | [QUEST TITLE PANEL]                              |
  |                                                  |
  | [ACTION BAR: 8 slots]              [MINIMAP]    |
  |                                                  |
  |                                                  |
  |                       [TOOLTIP]                  |
  |                                                  |
  |                                                  |
  | [HP BAR]                              [INVENTORY]|
  | [MANA BAR]                                       |
  +--------------------------------------------------+

Asset wiring:
  - theme           -> ui/godot/theme.tres
  - icon slots      -> ui/godot/<icon_id>_atlas.tres (loaded as Texture2D)
  - panel/frame bg  -> ui/godot/<element>_<faction>_stylebox.tres if available,
                       else ui/godot/<element>_stylebox.tres

Per-faction action-bar icons are picked deterministically from manifest.json
(top 8 with prefix `ico_` -- includes the 8 v1 synth icons + any later additions).

CLI:
  python hud_mockup.py                              # all factions, default layout
  python hud_mockup.py --faction ember_legion       # single faction
  python hud_mockup.py --action-icons ico_sword,ico_shield,ico_potion_red,...
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(r"D:\assets")
ICONS_DIR = ASSETS / "ui" / "icons"
SLICE_DIR = ASSETS / "ui" / "9slice"
ATLAS_DIR = ASSETS / "ui" / "atlas"
PALETTE_DIR = ASSETS / "ui" / "palettes"
GODOT_OUT = ASSETS / "ui" / "godot"
PREVIEW_OUT = ASSETS / "ui"

DESIGN_W, DESIGN_H = 1920, 1080


# ---------- Layout (single source of truth, used for both .tscn + PIL) -----

# ---------- Scenarios (gameplay states the HUD should be auditable in) ----

# Six fixtures per faction. Tweaks layout fills + tooltip text + a banner
# overlay so the v3 reviewer can spot-check faction palettes against
# realistic UI states. Adding a new scenario is one entry here.

SCENARIOS = {
    "default":         {"hp": 0.72, "mana": 0.45, "tooltip_visible": True,
                        "banner": None, "modal": None},
    "full_hp":         {"hp": 1.00, "mana": 1.00, "tooltip_visible": False,
                        "banner": "Full Restore",
                        "modal": None},
    "low_hp":          {"hp": 0.12, "mana": 0.04, "tooltip_visible": False,
                        "banner": "DANGER",
                        "modal": None},
    "combat_active":   {"hp": 0.55, "mana": 0.30, "tooltip_visible": True,
                        "banner": "COMBAT",
                        "modal": None,
                        "tooltip_override": ("Frostbrand Strike",
                                              "Cooldown: 4.2s")},
    "inventory_full":  {"hp": 0.85, "mana": 0.60, "tooltip_visible": False,
                        "banner": "Inventory Full",
                        "modal": "inventory"},
    "dialog_open":     {"hp": 0.85, "mana": 0.60, "tooltip_visible": False,
                        "banner": None,
                        "modal": "dialog",
                        "dialog_text": ("Halloran",
                                        "The crown was sundered. We need it.")},
    "level_up":        {"hp": 1.00, "mana": 1.00, "tooltip_visible": False,
                        "banner": "LEVEL UP",
                        "modal": "levelup",
                        "level_up_text": ("LEVEL 12",
                                          "+1 ability point  +HP  +Mana")},
}


def hud_layout(action_icon_ids: list[str], faction: str,
               scenario: str = "default") -> dict:
    bar_slot = 80
    bar_pad = 8
    n_slots = min(8, len(action_icon_ids))
    bar_w = n_slots * (bar_slot + bar_pad) + bar_pad
    sc = SCENARIOS.get(scenario, SCENARIOS["default"])
    tt_title = "Frostbrand Strike"
    tt_body = "+18 cold damage. Applies CHILLED for 4s."
    tt_override = sc.get("tooltip_override")
    if tt_override:
        tt_title, tt_body = tt_override
    layout = {
        "design_size": [DESIGN_W, DESIGN_H],
        "faction": faction,
        "scenario": scenario,
        "quest_panel": {"rect": [60, 24, 1100, 80],
                        "label": "QUEST: Recover the Sundered Crown"},
        "action_bar": {"rect": [60, 920, bar_w, 100],
                       "slot_size": bar_slot, "slot_padding": bar_pad,
                       "icons": action_icon_ids[:n_slots]},
        "minimap": {"rect": [DESIGN_W - 280 - 30, 30, 280, 280],
                    "label": "MAP"},
        "hp_bar":   {"rect": [60, 880, 360, 28], "label": "HP",
                      "fill": sc["hp"]},
        "mana_bar": {"rect": [60, 856, 360, 22], "label": "MP",
                      "fill": sc["mana"]},
        "tooltip":  {"rect": [DESIGN_W // 2 - 220, DESIGN_H // 2 - 80, 440, 160],
                     "title": tt_title, "body": tt_body,
                     "visible": sc.get("tooltip_visible", True)},
        "inventory_btn": {"rect": [DESIGN_W - 200 - 30, DESIGN_H - 90, 200, 60],
                          "label": "INVENTORY"},
    }
    if sc.get("banner"):
        layout["banner"] = {
            "rect": [DESIGN_W // 2 - 200, 110, 400, 60],
            "label": sc["banner"],
        }
    if sc.get("modal") == "inventory":
        layout["modal_inventory"] = {
            "rect": [DESIGN_W // 2 - 360, DESIGN_H // 2 - 240, 720, 480],
            "title": "INVENTORY (full)",
        }
    elif sc.get("modal") == "dialog":
        speaker, line = sc.get("dialog_text", ("?", "..."))
        layout["modal_dialog"] = {
            "rect": [DESIGN_W // 2 - 480, DESIGN_H - 280, 960, 200],
            "speaker": speaker, "line": line,
        }
    elif sc.get("modal") == "levelup":
        title, line = sc.get("level_up_text", ("LEVEL UP", ""))
        layout["modal_levelup"] = {
            "rect": [DESIGN_W // 2 - 280, DESIGN_H // 2 - 120, 560, 240],
            "title": title, "line": line,
        }
    return layout


# ---------- Asset resolver -------------------------------------------------

def _exists(p: Path) -> bool:
    return p.exists() and p.is_file()


def resolve_panel_stylebox(faction: str) -> str:
    cand = GODOT_OUT / f"panel_{faction}_stylebox.tres"
    if _exists(cand):
        return f"ui/panel_{faction}_stylebox.tres"
    return "ui/panel_stylebox.tres"


def resolve_frame_stylebox(faction: str) -> str:
    cand = GODOT_OUT / f"frame_{faction}_stylebox.tres"
    if _exists(cand):
        return f"ui/frame_{faction}_stylebox.tres"
    return "ui/frame_stylebox.tres"


def resolve_button_stylebox(faction: str) -> str:
    cand = GODOT_OUT / f"button_{faction}_stylebox.tres"
    if _exists(cand):
        return f"ui/button_{faction}_stylebox.tres"
    return "ui/button_stylebox.tres"


def resolve_healthbar_stylebox(faction: str) -> str:
    cand = GODOT_OUT / f"healthbar_{faction}_stylebox.tres"
    if _exists(cand):
        return f"ui/healthbar_{faction}_stylebox.tres"
    return "ui/healthbar_stylebox.tres"


def resolve_icon_atlas(icon_id: str) -> str | None:
    cand = GODOT_OUT / f"{icon_id}_atlas.tres"
    if _exists(cand):
        return f"ui/{icon_id}_atlas.tres"
    return None


# ---------- .tscn emitter --------------------------------------------------

def make_tscn(layout: dict, faction: str, theme_path: str = "ui/theme.tres") -> str:
    """Build a Godot 4.5 .tscn string. Uses Control anchors so the scene
    scales cleanly at any window size; design coords are in 1920x1080 space.
    """
    ext: list[tuple[str, str, str]] = []
    eid_by_path: dict[str, int] = {}

    def reg(godot_path: str, type_hint: str = "Resource") -> int:
        if godot_path in eid_by_path:
            return eid_by_path[godot_path]
        eid = len(ext) + 1
        ext.append((godot_path, type_hint, str(eid)))
        eid_by_path[godot_path] = eid
        return eid

    theme_eid = reg(theme_path, "Theme")
    panel_sb_eid = reg(resolve_panel_stylebox(faction), "StyleBoxTexture")
    frame_sb_eid = reg(resolve_frame_stylebox(faction), "StyleBoxTexture")
    button_sb_eid = reg(resolve_button_stylebox(faction), "StyleBoxTexture")
    hpbar_sb_eid = reg(resolve_healthbar_stylebox(faction), "StyleBoxTexture")
    slot_icon_eids: dict[str, int] = {}
    for icon_id in layout["action_bar"]["icons"]:
        gp = resolve_icon_atlas(icon_id)
        if gp is not None:
            slot_icon_eids[icon_id] = reg(gp, "Texture2D")

    load_steps = len(ext) + 1

    L = []
    L.append(f'[gd_scene load_steps={load_steps} format=3]')
    L.append("")
    for path, type_hint, eid in ext:
        L.append(f'[ext_resource type="{type_hint}" path="res://{path}" id="{eid}"]')
    L.append("")
    # Root Control
    L.append('[node name="HUD" type="Control"]')
    L.append('layout_mode = 3')
    L.append('anchors_preset = 15')
    L.append('anchor_right = 1.0')
    L.append('anchor_bottom = 1.0')
    L.append(f'theme = ExtResource("{theme_eid}")')
    L.append('mouse_filter = 2')
    L.append("")

    def add_panelcontainer(name: str, rect: list[int],
                           sb_eid: int, parent: str = ".") -> None:
        x, y, w, h = rect
        L.append(f'[node name="{name}" type="PanelContainer" parent="{parent}"]')
        L.append('layout_mode = 0')
        L.append(f'offset_left = {x}.0')
        L.append(f'offset_top = {y}.0')
        L.append(f'offset_right = {x + w}.0')
        L.append(f'offset_bottom = {y + h}.0')
        L.append(f'theme_override_styles/panel = ExtResource("{sb_eid}")')
        L.append("")

    def add_label(name: str, parent: str, text: str,
                  rect: list[int] | None = None,
                  align: str = "left") -> None:
        L.append(f'[node name="{name}" type="Label" parent="{parent}"]')
        if rect:
            x, y, w, h = rect
            L.append('layout_mode = 0')
            L.append(f'offset_left = {x}.0')
            L.append(f'offset_top = {y}.0')
            L.append(f'offset_right = {x + w}.0')
            L.append(f'offset_bottom = {y + h}.0')
        else:
            L.append('layout_mode = 2')
        L.append(f'text = "{text}"')
        if align == "center":
            L.append('horizontal_alignment = 1')
            L.append('vertical_alignment = 1')
        L.append("")

    def add_textureprogress(name: str, parent: str, rect: list[int],
                            value: float, sb_eid: int) -> None:
        x, y, w, h = rect
        L.append(f'[node name="{name}" type="ProgressBar" parent="{parent}"]')
        L.append('layout_mode = 0')
        L.append(f'offset_left = {x}.0')
        L.append(f'offset_top = {y}.0')
        L.append(f'offset_right = {x + w}.0')
        L.append(f'offset_bottom = {y + h}.0')
        L.append(f'value = {round(value * 100)}.0')
        L.append('show_percentage = false')
        L.append(f'theme_override_styles/background = ExtResource("{sb_eid}")')
        L.append("")

    def add_button(name: str, parent: str, rect: list[int], text: str,
                   sb_eid: int) -> None:
        x, y, w, h = rect
        L.append(f'[node name="{name}" type="Button" parent="{parent}"]')
        L.append('layout_mode = 0')
        L.append(f'offset_left = {x}.0')
        L.append(f'offset_top = {y}.0')
        L.append(f'offset_right = {x + w}.0')
        L.append(f'offset_bottom = {y + h}.0')
        L.append(f'text = "{text}"')
        L.append(f'theme_override_styles/normal = ExtResource("{sb_eid}")')
        L.append(f'theme_override_styles/hover = ExtResource("{sb_eid}")')
        L.append(f'theme_override_styles/pressed = ExtResource("{sb_eid}")')
        L.append("")

    def add_texturerect(name: str, parent: str, rect: list[int],
                        texture_eid: int) -> None:
        x, y, w, h = rect
        L.append(f'[node name="{name}" type="TextureRect" parent="{parent}"]')
        L.append('layout_mode = 0')
        L.append(f'offset_left = {x}.0')
        L.append(f'offset_top = {y}.0')
        L.append(f'offset_right = {x + w}.0')
        L.append(f'offset_bottom = {y + h}.0')
        L.append(f'texture = ExtResource("{texture_eid}")')
        L.append('expand_mode = 1')
        L.append('stretch_mode = 5')
        L.append("")

    # Quest panel
    qp = layout["quest_panel"]
    add_panelcontainer("QuestPanel", qp["rect"], panel_sb_eid)
    add_label("Title", "QuestPanel", qp["label"])

    # Minimap (panel placeholder)
    mm = layout["minimap"]
    add_panelcontainer("Minimap", mm["rect"], panel_sb_eid)
    add_label("MapLabel", "Minimap", mm["label"])

    # Action bar
    ab = layout["action_bar"]
    abx, aby, abw, abh = ab["rect"]
    add_panelcontainer("ActionBar", ab["rect"], panel_sb_eid)
    sx = ab["slot_padding"]
    sy = ab["slot_padding"]
    for i, icon_id in enumerate(ab["icons"]):
        slot_rect = [sx, sy, ab["slot_size"], ab["slot_size"]]
        # Slot frame
        if frame_sb_eid:
            L.append(f'[node name="Slot{i}" type="PanelContainer" parent="ActionBar"]')
            L.append('layout_mode = 0')
            L.append(f'offset_left = {slot_rect[0]}.0')
            L.append(f'offset_top = {slot_rect[1]}.0')
            L.append(f'offset_right = {slot_rect[0] + slot_rect[2]}.0')
            L.append(f'offset_bottom = {slot_rect[1] + slot_rect[3]}.0')
            L.append(f'theme_override_styles/panel = ExtResource("{frame_sb_eid}")')
            L.append("")
        # Icon TextureRect (only if its atlas exists)
        ico_eid = slot_icon_eids.get(icon_id)
        if ico_eid is not None:
            inner = slot_rect[2] - 16
            L.append(f'[node name="Icon" type="TextureRect" parent="ActionBar/Slot{i}"]')
            L.append('layout_mode = 0')
            L.append(f'offset_left = 8.0')
            L.append(f'offset_top = 8.0')
            L.append(f'offset_right = {8 + inner}.0')
            L.append(f'offset_bottom = {8 + inner}.0')
            L.append(f'texture = ExtResource("{ico_eid}")')
            L.append('expand_mode = 1')
            L.append('stretch_mode = 5')
            L.append("")
        sx += ab["slot_size"] + ab["slot_padding"]

    # Bars
    add_textureprogress("HpBar", ".", layout["hp_bar"]["rect"],
                        layout["hp_bar"]["fill"], hpbar_sb_eid)
    add_textureprogress("ManaBar", ".", layout["mana_bar"]["rect"],
                        layout["mana_bar"]["fill"], hpbar_sb_eid)

    # Tooltip
    tt = layout["tooltip"]
    add_panelcontainer("Tooltip", tt["rect"], frame_sb_eid)
    add_label("TipTitle", "Tooltip", tt["title"])
    add_label("TipBody", "Tooltip", tt["body"])

    # Inventory button
    inv = layout["inventory_btn"]
    add_button("InventoryButton", ".", inv["rect"], inv["label"], button_sb_eid)

    return "\n".join(L) + "\n"


# ---------- PIL preview ----------------------------------------------------

def _palette_for(faction: str) -> dict:
    p = PALETTE_DIR / f"{faction}.json"
    if not p.exists():
        return {
            "metal": "#a89060", "metal_dark": "#5a4a30", "ink": "#1a160c",
            "accent": "#7cb342", "wood": "#5b3a1c",
            "bg": "#1c2418ee", "highlight": "#ffffff44",
        }
    return json.loads(p.read_text(encoding="utf-8"))


def _hex(c: str) -> tuple[int, int, int, int]:
    c = c.lstrip("#")
    if len(c) == 6:
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255)
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), int(c[6:8], 16))


def render_preview(layout: dict, faction: str, scale: float = 0.45) -> Image.Image:
    pal = _palette_for(faction)
    metal = _hex(pal["metal"])
    ink = _hex(pal["ink"])
    bg = _hex(pal["bg"])
    accent = _hex(pal["accent"])
    metal_dark = _hex(pal["metal_dark"])

    W, H = int(DESIGN_W * scale), int(DESIGN_H * scale)
    img = Image.new("RGBA", (W, H), (12, 14, 18, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", max(10, int(16 * scale)))
        font_small = ImageFont.truetype("arial.ttf", max(8, int(11 * scale)))
    except OSError:
        font = ImageFont.load_default()
        font_small = ImageFont.load_default()

    def s(rect):
        x, y, w, h = rect
        return [int(x * scale), int(y * scale),
                int((x + w) * scale), int((y + h) * scale)]

    def panel(rect, color_fill=bg, color_border=metal, label=None):
        r = s(rect)
        draw.rounded_rectangle(r, radius=int(8 * scale),
                               fill=color_fill, outline=color_border, width=max(1, int(3 * scale)))
        if label:
            draw.text((r[0] + int(10 * scale), r[1] + int(6 * scale)),
                      label, fill=metal, font=font)

    # Quest
    panel(layout["quest_panel"]["rect"], label=layout["quest_panel"]["label"])
    # Minimap
    panel(layout["minimap"]["rect"], label=layout["minimap"]["label"])
    # Action bar
    ab = layout["action_bar"]
    panel(ab["rect"])
    abx, aby, abw, abh = ab["rect"]
    sx = abx + ab["slot_padding"]
    sy = aby + ab["slot_padding"]
    for icon_id in ab["icons"]:
        slot_rect = [sx, sy, ab["slot_size"], ab["slot_size"]]
        panel(slot_rect, color_fill=ink, color_border=metal_dark)
        # Try to draw the actual icon
        ipath = ICONS_DIR / f"{icon_id}.png"
        if ipath.exists():
            with Image.open(ipath) as ico:
                ico = ico.convert("RGBA")
                inner = int((ab["slot_size"] - 16) * scale)
                ico = ico.resize((inner, inner), Image.LANCZOS)
                # If silhouette (mostly black), tint to accent for visibility on dark slot
                if _looks_silhouette(ico):
                    ico = _tint(ico, accent)
                img.alpha_composite(ico, (int((sx + 8) * scale), int((sy + 8) * scale)))
        sx += ab["slot_size"] + ab["slot_padding"]
    # Bars
    for key, color in (("hp_bar", _hex("#c0382bff")), ("mana_bar", _hex("#3aa0e0ff"))):
        b = layout[key]
        rect = b["rect"]
        panel(rect, color_fill=ink, color_border=metal_dark)
        # fill
        r = s(rect)
        fill_w = int((r[2] - r[0]) * b["fill"])
        if fill_w > 2:
            draw.rectangle([r[0] + 2, r[1] + 2, r[0] + fill_w - 2, r[3] - 2],
                           fill=color)
        draw.text((r[0] + int(8 * scale), r[1] + int(2 * scale)),
                  f"{b['label']} {int(b['fill'] * 100)}%",
                  fill=(240, 240, 240, 255), font=font_small)
    # Tooltip
    tt = layout["tooltip"]
    if tt.get("visible", True):
        panel(tt["rect"])
        rt = s(tt["rect"])
        draw.text((rt[0] + int(14 * scale), rt[1] + int(10 * scale)),
                  tt["title"], fill=accent, font=font)
        draw.text((rt[0] + int(14 * scale), rt[1] + int(36 * scale)),
                  tt["body"], fill=(220, 220, 220, 255), font=font_small)

    # Inventory button
    inv = layout["inventory_btn"]
    panel(inv["rect"], color_fill=metal_dark, color_border=metal,
          label=inv["label"])

    # Scenario overlays (banners + modals)
    if "banner" in layout:
        b = layout["banner"]
        panel(b["rect"], color_fill=accent, color_border=metal_dark)
        r = s(b["rect"])
        # Title centered
        try:
            tw = font.getlength(b["label"])
        except AttributeError:
            tw = len(b["label"]) * 8
        draw.text((r[0] + (r[2] - r[0] - tw) // 2,
                   r[1] + int(18 * scale)),
                  b["label"], fill=ink, font=font)
    if "modal_inventory" in layout:
        m = layout["modal_inventory"]
        panel(m["rect"], color_fill=ink, color_border=metal)
        r = s(m["rect"])
        draw.text((r[0] + int(20 * scale), r[1] + int(14 * scale)),
                  m["title"], fill=accent, font=font)
        # 5x4 cells of "filled" item slots
        cw = (r[2] - r[0] - int(40 * scale)) // 5
        ch = (r[3] - r[1] - int(60 * scale)) // 4
        for row in range(4):
            for col in range(5):
                x = r[0] + int(20 * scale) + col * cw
                y = r[1] + int(50 * scale) + row * ch
                draw.rectangle([x, y, x + cw - int(4 * scale),
                                y + ch - int(4 * scale)],
                               fill=metal_dark, outline=metal, width=1)
    if "modal_dialog" in layout:
        m = layout["modal_dialog"]
        panel(m["rect"], color_fill=ink, color_border=accent)
        r = s(m["rect"])
        draw.text((r[0] + int(20 * scale), r[1] + int(14 * scale)),
                  m["speaker"], fill=accent, font=font)
        draw.text((r[0] + int(20 * scale), r[1] + int(46 * scale)),
                  m["line"], fill=(220, 220, 220, 255), font=font_small)
    if "modal_levelup" in layout:
        m = layout["modal_levelup"]
        panel(m["rect"], color_fill=metal_dark, color_border=accent)
        r = s(m["rect"])
        draw.text((r[0] + int(20 * scale), r[1] + int(14 * scale)),
                  m["title"], fill=accent, font=font)
        draw.text((r[0] + int(20 * scale), r[1] + int(60 * scale)),
                  m["line"], fill=(240, 240, 240, 255), font=font_small)

    # Faction + scenario caption
    sc_label = layout.get("scenario", "default")
    draw.text((10, H - int(20 * scale) - 4),
              f"HUD mockup -- {faction} -- {sc_label}",
              fill=(180, 180, 180, 255), font=font_small)
    return img


def _looks_silhouette(img: Image.Image) -> bool:
    """Heuristic: treat icons whose RGB mean is below 30 (mostly black) as
    silhouettes that should be tinted to read on a dark slot."""
    px = img.load()
    if px is None:
        return False
    w, h = img.size
    samples = 0
    dark = 0
    for y in range(0, h, max(1, h // 16)):
        for x in range(0, w, max(1, w // 16)):
            r, g, b, a = px[x, y]
            if a < 50:
                continue
            samples += 1
            if (r + g + b) / 3 < 30:
                dark += 1
    return samples > 0 and dark / samples > 0.7


def _tint(img: Image.Image, color: tuple[int, int, int, int]) -> Image.Image:
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    px_in = img.load()
    px_out = out.load()
    cr, cg, cb, _ = color
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b, a = px_in[x, y]
            if a == 0:
                continue
            # Map alpha-modulated source to tint
            l = (r + g + b) / 3 / 255.0
            px_out[x, y] = (
                int(cr * (1 - l) + 255 * l),
                int(cg * (1 - l) + 255 * l),
                int(cb * (1 - l) + 255 * l),
                a,
            )
    return out


# ---------- Asset discovery -----------------------------------------------

def default_action_icons(manifest_path: Path = ICONS_DIR / "manifest.json") -> list[str]:
    """Pick 8 deterministic icon IDs for the action bar.

    Priority: classic ability slots if present (sword/shield/potions/scroll/key/coin/skull),
    then fall back to the first 8 manifest entries that have a corresponding
    `<id>_atlas.tres` in ui/godot/.
    """
    PREFERRED = [
        "ico_sword", "ico_shield", "ico_potion_red", "ico_potion_blue",
        "ico_gem_blue", "ico_scroll", "ico_key", "ico_coin",
    ]
    if not manifest_path.exists():
        return PREFERRED
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in data.get("icons", [])}
    out = [iid for iid in PREFERRED if iid in by_id]
    for entry in data.get("icons", []):
        if len(out) >= 8:
            break
        if entry["id"] not in out:
            out.append(entry["id"])
    return out[:8]


def known_factions(palette_dir: Path = PALETTE_DIR) -> list[str]:
    if not palette_dir.exists():
        return ["default"]
    return [p.stem for p in sorted(palette_dir.glob("*.json"))]


# ---------- Main ----------------------------------------------------------

def export_one(faction: str, action_icons: list[str],
               theme_path: str = "ui/theme.tres",
               scenario: str = "default",
               *,
               write_tscn: bool = True) -> dict:
    layout = hud_layout(action_icons, faction, scenario=scenario)
    GODOT_OUT.mkdir(parents=True, exist_ok=True)
    PREVIEW_OUT.mkdir(parents=True, exist_ok=True)
    suffix = "" if scenario == "default" else f"_{scenario}"
    tscn_path = GODOT_OUT / f"hud_{faction}{suffix}.tscn"
    if write_tscn:
        tscn = make_tscn(layout, faction, theme_path)
        tscn_path.write_text(tscn, encoding="utf-8")
    preview = render_preview(layout, faction)
    preview_path = PREVIEW_OUT / f"hud_preview_{faction}{suffix}.png"
    preview.save(preview_path)
    print(f"[hud_mockup] {faction:14s} {scenario:16s} -> "
          f"{preview_path.name}" + (f" + {tscn_path.name}" if write_tscn else ""))
    return {
        "faction": faction,
        "scenario": scenario,
        "tscn": str(tscn_path.relative_to(ASSETS).as_posix()) if write_tscn else None,
        "preview": str(preview_path.relative_to(ASSETS).as_posix()),
        "action_icons": action_icons,
        "layout": layout,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--faction", default=None,
                    help="One faction name (no extension). Default: all known.")
    ap.add_argument("--factions", default=None,
                    help="Comma-separated list (overrides --faction).")
    ap.add_argument("--action-icons", default=None,
                    help="Comma-separated icon IDs (max 8). "
                         "Default: smart pick from manifest.")
    ap.add_argument("--theme", default="ui/theme.tres",
                    help="Godot path to the Theme.tres (relative to res://).")
    ap.add_argument("--manifest-out", type=Path,
                    default=ASSETS / "ui" / "godot" / "hud_manifest.json")
    ap.add_argument("--scenario", default="default",
                    choices=sorted(SCENARIOS.keys()),
                    help="Gameplay state to render. Default: 'default' (the "
                         "v2-shipped neutral state).")
    ap.add_argument("--fixtures", action="store_true",
                    help="Generate the full 4 factions x 6 scenarios "
                         "fixture grid (24 PNGs total). Skips .tscn for "
                         "non-default scenarios -- they're preview fixtures, "
                         "not authored Godot scenes.")
    ap.add_argument("--fixtures-scenarios", default=None,
                    help="Comma-separated subset of scenario names for "
                         "--fixtures (default: all 6).")
    args = ap.parse_args()

    if args.factions:
        factions = [f.strip() for f in args.factions.split(",") if f.strip()]
    elif args.faction:
        factions = [args.faction]
    else:
        factions = known_factions() or ["default"]

    if args.action_icons:
        action_icons = [s.strip() for s in args.action_icons.split(",") if s.strip()]
    else:
        action_icons = default_action_icons()

    out: list[dict] = []
    if args.fixtures:
        scenarios = (
            [s.strip() for s in args.fixtures_scenarios.split(",") if s.strip()]
            if args.fixtures_scenarios
            else ["full_hp", "low_hp", "combat_active",
                  "inventory_full", "dialog_open", "level_up"]
        )
        for f in factions:
            for sc in scenarios:
                # Only the 'default' scenario writes a .tscn -- non-default
                # are preview fixtures, not scenes the runtime should load.
                out.append(export_one(f, action_icons, args.theme,
                                      scenario=sc, write_tscn=False))
    else:
        for f in factions:
            out.append(export_one(f, action_icons, args.theme,
                                  scenario=args.scenario))

    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(json.dumps({"huds": out}, indent=2),
                                 encoding="utf-8")
    print(f"[hud_mockup] {len(out)} variants -> {args.manifest_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
