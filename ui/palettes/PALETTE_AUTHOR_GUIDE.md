# Faction Palette Author Guide

How to add or edit a faction palette. Every palette JSON in this directory is
consumed by:

- `pipelines/ui/frame_compose.py` — reskins 9-slice frames per faction.
- `pipelines/ui/hud_mockup.py` — paints the HUD preview tints.
- (planned) `pipelines/ui/recraft_icons.py` — passes `accent` and `metal`
  hints when generating set-style cloud icons.

The palette file is the **single source of truth** for a faction's visual
identity. Edit here, re-run `frame_compose.py --sweep` and `hud_mockup.py
--fixtures`, and every downstream artifact updates consistently.

---

## Schema

Every palette JSON has exactly these eight keys:

```json
{
  "id":         "verdant_court",
  "metal":      "#9caf6a",
  "metal_dark": "#4d5a2c",
  "ink":        "#10180a",
  "accent":     "#d2b85a",
  "wood":       "#3b2c18",
  "bg":         "#16241aee",
  "highlight":  "#ffffff44"
}
```

| Slot | Use | Contrast target | Constraint |
|---|---|---|---|
| `id` | Filename + cross-pipeline ref. snake_case | — | Must match filename stem |
| `metal` | Frame border, slot rims, button outline | 4.5:1 vs `bg` | Mid-saturation, faction-tinted |
| `metal_dark` | Frame inner borders, slot fills | 7:1 vs `bg` | Darker sibling of `metal` |
| `ink` | Solid panel back, modal back | 14:1 vs text white | Near-black with faction hue |
| `accent` | Highlight, "active" tint, banner fill, dialog speaker tag | 6:1 vs `ink` | High saturation, distinct from `metal` |
| `wood` | Button body, frame base | 4.5:1 vs `metal` | Earth tone tied to faction story |
| `bg` | Panel back, semi-transparent. **8-char hex (RGBA)** | 14:1 vs text white once composited | Includes alpha (`ee` ≈ 93%) |
| `highlight` | Sheen line on buttons. **8-char hex (RGBA)** | — | Always `#ffffff??`, alpha 0x33–0x55 |

`bg` and `highlight` MUST be 8-char hex (RGBA). Everything else is 6-char
hex (RGB, alpha implied 0xff).

The `frame_compose.py::palette_rgba()` parser will raise on any other shape.

---

## Per-faction design philosophy

The shipped 4 palettes anchor the cardinal-direction model: `metal` ↔ `wood`
defines the structural mood; `accent` defines the magic/danger signal.

### Verdant Court — `#9caf6a` over `#3b2c18`
**Story tag:** druids, river-vow knights, longbow scouts. Camp fires + reed
pavilions; emblem shapes lean leaf, vine, antler.

| `metal`        | mossy bronze  `#9caf6a` |
| `metal_dark`   | deep olive    `#4d5a2c` |
| `ink`          | forest near-black `#10180a` |
| `accent`       | candle-honey  `#d2b85a` (low saturation; doesn't read as gold) |
| `wood`         | walnut beam   `#3b2c18` |
| `bg`           | mid forest    `#16241aee` |

Why these choices:
- **Olive over yellow-green** keeps the faction from reading "elf cliché";
  Verdant Court is grounded, not whimsical.
- **Honey accent** instead of pure gold so spell highlights look like
  candle-fire, not high-magic glow.
- The structural pair (`metal_dark`, `wood`) is brown-on-brown deliberately:
  hand-crafted, lashed-together, not forged.

### Ember Legion — `#c46a3a` over `#3a1c10`
**Story tag:** mining-state militia, foundry knights, lava-line cartographers.

| `metal`        | hammered copper  `#c46a3a` |
| `metal_dark`   | ferrous brick    `#5a2810` |
| `ink`          | charcoal blood   `#180c08` |
| `accent`       | molten gold      `#f7d04a` (saturated; combat readiness) |
| `wood`         | charred oak      `#3a1c10` |
| `bg`           | blood-clay       `#241612ee` |

Why:
- **Copper over orange.** Saturated orange reads as cartoony; copper carries
  industrial weight.
- **Saturated gold accent** — the faction's combat signaling is loud. UI
  banners (`combat_active`, `low_hp`) will pop hard against this.
- The whole stack is warm: deliberately no cool secondary so it's
  unmistakably *not* the Tide-Bound palette even in grayscale.

### Tide-Bound — `#7ac1d6` over `#1d2c3a`
**Story tag:** sea-warden navy, salt-priests, weather-witch order.

| `metal`        | corroded brass-blue  `#7ac1d6` |
| `metal_dark`   | deep tide            `#234a5e` |
| `ink`          | abyssal              `#0a1822` |
| `accent`       | foam-pale            `#cdebff` (cool highlight, not gold) |
| `wood`         | drift-plank          `#1d2c3a` (also blue-tinted) |
| `bg`           | undertow             `#101e2cee` |
| `highlight`    | brighter than others `#ffffff55` (water gleam) |

Why:
- **Cool everything.** Even `wood` is blue-tinted; this faction has no
  warm-color element. Important for tonal contrast against Ember Legion
  scenes.
- **Pale accent** instead of saturated cyan keeps the palette readable in
  bright HUD states (`level_up`, `full_hp`) — saturated cyan would crush
  detail.
- `highlight` lifted to `0x55` alpha because the Tide-Bound metal already
  carries less specularity than the warm metals; needs a brighter sheen.

### Ashen Pact — `#a59ea6` over `#241820`
**Story tag:** void-cult, exiled necromancers, broken-oath wraiths.

| `metal`        | bone ash       `#a59ea6` |
| `metal_dark`   | tomb shale     `#3a3236` |
| `ink`          | obsidian       `#100c10` |
| `accent`       | rune violet    `#a25cff` (saturated; the only chromatic note) |
| `wood`         | rotted oak     `#241820` |
| `bg`           | crypt          `#171318ee` |

Why:
- **Desaturated grays** for everything except accent. The faction's whole
  visual hook is "ash on ash, until the magic shows." The single saturated
  accent (rune violet) carries 100% of the chromatic load.
- **No green or yellow tints.** Avoid edging into "swamp" or "decay" —
  Ashen Pact is austere, not gross.
- Combat banners on this palette read as **purple-on-gray**, which is
  strikingly readable; verify by checking
  `ui/hud_preview_ashen_pact_combat_active.png`.

---

## How to add a new faction palette

1. **Pick the structural pair** first: `metal` and `wood`. These set the
   faction's "feel" before any chromatic note. Do this on a B&W reference
   image — squint and verify the two colors are clearly distinguishable
   when desaturated.
2. **Derive `metal_dark` and `ink`** by darkening `metal` and `wood`
   respectively to ~30% luminance. They'll be on top of the structural
   colors and need to read as "shadow."
3. **Pick `accent`** *last*. It's the only color the player parses
   semantically (active state, low HP warning, etc.). It must be (a)
   distinct from every other faction's `accent`, (b) high contrast vs
   `ink`, (c) NOT confusable with HP red or Mana blue (those are reserved
   in `hud_mockup.py::render_preview` and aren't in the palette).
4. **Pick `bg` and `highlight`** for compositing fidelity. `bg` should be
   2-3% lighter than `ink` so panel layers read in stack. `highlight`
   defaults to `#ffffff44` and only needs editing if the metal is very
   pale (Tide-Bound).
5. **Verify against the 6 fixtures.**
   ```powershell
   python pipelines/ui/frame_compose.py --base panel --palette ui/palettes/<new>.json --corner filigree --edge ridge --id panel_<new> --out ui/9slice/panel_<new>.png
   python pipelines/ui/frame_compose.py --sweep
   python pipelines/ui/hud_mockup.py --faction <new> --fixtures
   ```
   Open the 6 PNGs in `ui/hud_preview_<new>_*.png` and check:
   - **`combat_active`** banner is legible against `accent`
   - **`low_hp`** danger banner doesn't clash with `metal`
   - **`dialog_open`** speaker text contrast is readable
   - **`inventory_full`** modal back doesn't drown out the slot grid
6. **Add a stanza to this guide** with the same shape as the four above:
   story tag + table + "why these choices" bullets. The "why" is the
   most important part — future palette additions look coherent only when
   their logic is articulated, not just their hex codes.

## Cross-faction guardrails

- No two faction `accent` colors should sit within 30° of each other on the
  HSL wheel. The four shipped palettes use ~50° (Verdant honey), ~45°
  (Ember gold), ~200° (Tide foam-pale), ~265° (Ashen violet) — well-spaced.
- `metal` and `accent` must never be near-complementary; that produces
  vibration on small UI elements (action-bar slots).
- The full palette set is grayscale-distinct. Run
  `python pipelines/ui/preview_grid.py --grayscale` (planned) to verify.

## Tools that consume palettes

| Tool | Read | Write |
|---|---|---|
| `frame_compose.py` | every key | nothing |
| `hud_mockup.py` | `metal`, `metal_dark`, `ink`, `accent`, `wood`, `bg` | nothing |
| `recraft_icons.py` *(planned)* | `accent`, `metal` (as prompt hints) | nothing |
| `lint_icons.py` | `id` (cross-checks faction name) | nothing |
| `frame_compose.py --write-default-palettes` | nothing | overwrites the four shipped palettes |

The shipped 4 palettes are never overwritten by ordinary runs; only
`--write-default-palettes` does, and it's an explicit subcommand.

---

*Last edited: 2026-05-06 (UI v3 handoff). Owned by `pipelines/ui/`.*
