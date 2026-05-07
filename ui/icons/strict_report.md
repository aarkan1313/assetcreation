# UI strict-icons report

- **strict mode:** False
- **total_icons:** 135
- **base validator OK:** True
- **strict OK:** False

## unused_icons

- **unused_count:** `131`
- **total_icons:** `135`
- **unused_fraction:** `0.9704`
- **threshold:** `0.95`
- **passes:** `False`
- **unused_ids_sample** (20):
  - `ico_arcane_orb`
  - `ico_axe`
  - `ico_barrier`
  - `ico_bow`
  - `ico_coin`
  - `ico_dagger`
  - `ico_elixir`
  - `ico_eye`
  - `ico_fireball`
  - `ico_flame_rune`
  - … and 10 more

## mismatched_icons

- **min_score:** `0.4`
- **margin:** `0.2`
- **mismatches** (6):
  - `{'kind': 'items', 'record_id': 'iron_mace_0', 'display_name': 'Iron Mace', 'current_icon_id': 'ico_sword', 'current_score': 0.0, 'suggested_icon_id': 'ico_mace', 'suggested_score': 0.5, 'delta': 0.5}`
  - `{'kind': 'items', 'record_id': 'frost_spear_0', 'display_name': 'Frost Spear', 'current_icon_id': 'ico_sword', 'current_score': 0.0, 'suggested_icon_id': 'ico_arcane_orb', 'suggested_score': 0.8536, 'delta': 0.8536}`
  - `{'kind': 'items', 'record_id': 'uncommon_fire_blade_45', 'display_name': 'Uncommon Training Blade', 'current_icon_id': 'ico_sword', 'current_score': 0.0, 'suggested_icon_id': 'ico_gi_fire', 'suggested_score': 0.7041, 'delta': 0.7041}`
  - `{'kind': 'abilities', 'record_id': 'shadow_aura_t1_42', 'display_name': 'Shadow Aura T1', 'current_icon_id': 'ico_scroll', 'current_score': 0.0, 'suggested_icon_id': 'ico_shadow_bolt', 'suggested_score': 0.8162, 'delta': 0.8162}`
  - `{'kind': 'abilities', 'record_id': 'arcane_self_t2_43', 'display_name': 'Arcane Self T2', 'current_icon_id': 'ico_gem_blue', 'current_score': 0.0, 'suggested_icon_id': 'ico_arcane_orb', 'suggested_score': 0.8162, 'delta': 0.8162}`
  - `{'kind': 'abilities', 'record_id': 'nature_self_t3_44', 'display_name': 'Nature Self T3', 'current_icon_id': 'ico_potion_blue', 'current_score': 0.0, 'suggested_icon_id': 'ico_nature_thorn', 'suggested_score': 0.7887, 'delta': 0.7887}`
- **passes:** `False`

## missing_tags

- **missing_count:** `37`
- **total:** `135`
- **missing_ids_sample** (30):
  - `ico_arcane_orb`
  - `ico_axe`
  - `ico_barrier`
  - `ico_bow`
  - `ico_coin`
  - `ico_dagger`
  - `ico_elixir`
  - `ico_eye`
  - `ico_fireball`
  - `ico_footprint`
  - … and 20 more
- **passes:** `True`
- **informational:** `True`
