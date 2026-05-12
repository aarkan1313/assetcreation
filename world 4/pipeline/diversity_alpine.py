"""W4 alpine biome diversity batch.

Generates ~50 ComfyUI PBR materials for the alpine biome across a wide
prompt space (3 slots x many stylistic variants). The point is not to
ship them all — it's to give us a candidate pool we then pick the best
3 from (one per slot) to replace the current biome_alpine kit, and to
build intuition for which prompt knobs actually matter.

Settings match generate_biome_kits.py: klein-9B FP8 + qwen_3_8b, 1024px,
--quality default (4 variants, SM PBR backend, seam-B+ gate, --no-gate
so failures still ship for review).

Output:
  D:/assets/world/textures/library/w4_alpine_div_<NN>_<slot>_<tag>/
    -> _albedo.png, _normal.png, _roughness.png, _ao.png, qa/

Review workflow after batch completes:
  - eyeball qa/ thumbnails for each material
  - pick the 3 winners (one per slot)
  - copy into materials/biome_alpine/<slot>/ to replace current kit
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PY = r"C:\Program Files\Python312\python.exe"
AAA = r"D:\assets\pipelines\textures\aaa_texture.py"
LIBRARY = Path(r"D:\assets\world\textures\library")

UNET = "flux-2-klein-9b-fp8.safetensors"
CLIP = "qwen_3_8b_fp8mixed.safetensors"

PROMPT_PREFIX = "tileable seamless texture, "
OVERHEAD = ", overhead perspective"

# (slot, tag, category, prompt_body) — final prompt is
#   PROMPT_PREFIX + prompt_body + OVERHEAD
#
# Slot distribution:
#   ground: 16 — snow / wind-pack / firn / hoar / drift
#   mid:    20 — patchy snow on lichen-rock (the richest space)
#   rock:   14 — alpine bedrock / slate / shattered scree
SLOTS = [
    # ----- GROUND (snow) -----
    ("ground", "fresh_powder", "Snow",
     "fresh powder snow, soft undisturbed surface, bright cold white with subtle blue shadow tones"),
    ("ground", "windpack", "Snow",
     "wind-packed snow with sastrugi ridges, sharp wind-carved striations, bright white"),
    ("ground", "firn_dense", "Snow",
     "dense firn snow, compacted granular surface, off-white with grey crystalline texture"),
    ("ground", "hoar_crystals", "Snow",
     "surface hoar frost crystals on packed snow, sparkly cold-white with faint blue undertones"),
    ("ground", "old_drift", "Snow",
     "old wind-drifted snow with subtle dune shape, bright cold white, smooth and slightly rippled"),
    ("ground", "icy_crust", "Snow",
     "icy crust over snow, hard glassy surface with reflective crystalline patches, cold blue-white"),
    ("ground", "shallow_powder_dirt", "Snow",
     "shallow powder snow over dark earth, mottled white-and-brown patches, melting interface"),
    ("ground", "boot_compacted", "Snow",
     "boot-compacted snow path texture, ridged compressed snow with grain detail, cold white"),
    ("ground", "wind_swept_thin", "Snow",
     "thin wind-swept snow over rocky substrate, scattered ice patches and grey stone, cold palette"),
    ("ground", "granular_glacier", "Snow",
     "glacial granular firn, near-ice density, faint blue-white with crystal facets"),
    ("ground", "fresh_blanket", "Snow",
     "fresh untouched snow blanket, soft uniform white, subtle drifts, pristine"),
    ("ground", "melting_patchy", "Snow",
     "melting patchy snow with exposed dark wet earth and frosted edges, half-cold-half-warm mix"),
    ("ground", "deep_crystals", "Snow",
     "deep snow with prominent ice crystal sparkle, cold white with violet shadow tones"),
    ("ground", "windrim_sastrugi", "Snow",
     "sharp sastrugi wind-ridges in hard snow, alternating bright crest and shadow trough"),
    ("ground", "compact_blue", "Snow",
     "compact glacial blue-white snow, dense smooth surface with subtle blue ice undertones"),
    ("ground", "dusty_old_snow", "Snow",
     "old snow with thin dust film, faintly tan-grey white, weathered alpine surface"),
    # ----- MID (lichen + rock + snow mix) -----
    ("mid", "lichen_thin_snow", "Snow",
     "thin snow patches over lichen-spotted dark rock, cool grey-blue palette, mixed alpine surface"),
    ("mid", "moss_grey_rock", "Snow",
     "patchy moss on grey alpine rock with snow remnants, muted cool palette, weathered"),
    ("mid", "exposed_bedrock_ice", "Snow",
     "exposed dark bedrock fringed with ice and snow crusts, sharp grey-and-white contrast"),
    ("mid", "lichen_yellow_rock", "Snow",
     "yellow-green lichen splotches on weathered grey rock with snow dust, alpine high-altitude"),
    ("mid", "frosted_lichen", "Snow",
     "frosted lichen on cold-grey alpine rock, frost-rim accents, mostly grey with faint green-blue"),
    ("mid", "mixed_scree_snow", "Snow",
     "loose scree fragments mixed with crusty snow, mid-grey rock and bright snow patches"),
    ("mid", "mossy_wet_slate", "Snow",
     "wet dark slate with dense moss carpet, cool damp palette of dark green and slate grey"),
    ("mid", "alpine_grass_snow", "Snow",
     "tufts of brown alpine grass poking through thin snow, muted earth-brown and cold white"),
    ("mid", "lichen_orange_blue", "Snow",
     "vivid orange lichen and grey-blue lichen mosaic on alpine rock with snow trim"),
    ("mid", "shattered_rock_snow", "Snow",
     "shattered rock fragments with snow filling cracks, sharp dark edges against bright snow"),
    ("mid", "moss_meltwater", "Snow",
     "moss-covered rock with meltwater pooling, wet dark-green moss and grey rock, subtle highlights"),
    ("mid", "lichen_dense_carpet", "Snow",
     "dense pale lichen carpet on dark alpine rock, faded mint and grey palette, weathered"),
    ("mid", "permafrost_polygon", "Snow",
     "polygonal permafrost terrain with frost cracks and small stones, muted ochre and grey"),
    ("mid", "scree_with_lichen", "Snow",
     "scree slope with sparse lichen growth, mid-grey rock fragments and pale green spots"),
    ("mid", "snowmelt_mineral", "Snow",
     "snowmelt rivulets over mineral-stained alpine rock, rusty streaks and grey base"),
    ("mid", "boulder_snow_caps", "Snow",
     "scattered alpine boulders with snow caps and lichen flanks, dark rock and bright snow"),
    ("mid", "tundra_dwarf", "Snow",
     "alpine tundra with dwarf shrubs and crusty snow patches, brown vegetation and cold white"),
    ("mid", "frost_heaved", "Snow",
     "frost-heaved soil with stone polygons, cracked alpine ground, muted browns and greys"),
    ("mid", "wet_lichen_quartz", "Snow",
     "wet lichen on quartz-veined rock, dark surface with bright white veins and green patches"),
    ("mid", "windscoured_ice", "Snow",
     "wind-scoured ice over rock fragments, glassy clear ice with embedded grey stones"),
    ("mid", "spring_thaw", "Snow",
     "spring thaw transition: patchy snow, wet rock, emerging moss, mixed cold-and-warm tones"),
    # ----- ROCK (alpine bedrock / slate) -----
    ("rock", "dark_slate", "Rock",
     "weathered dark slate rock with sharp cleavage planes, cool grey palette, alpine bedrock"),
    ("rock", "shattered_granite", "Rock",
     "shattered alpine granite with angular fractures, mid-grey with subtle pink-feldspar grain"),
    ("rock", "quartz_veined", "Rock",
     "dark alpine rock with bright white quartz veins running through, cool grey with high contrast"),
    ("rock", "weathered_basalt", "Rock",
     "weathered dark basalt outcrop with frost-shattered surface, cool grey-blue palette"),
    ("rock", "lichen_streaked", "Rock",
     "alpine rock heavily streaked with yellow and grey lichen, cool grey base with dappled accents"),
    ("rock", "frost_shattered", "Rock",
     "frost-shattered alpine bedrock, sharp angular fragments, mid-grey palette, weathered"),
    ("rock", "mossy_dark_slate", "Rock",
     "dark slate with patchy moss in cracks, near-black rock with bright green crack-fill"),
    ("rock", "glacial_polished", "Rock",
     "glacially polished alpine rock, smooth grey surface with faint striations, cool palette"),
    ("rock", "talus_face", "Rock",
     "tightly packed talus rock face, angular fragments of dark grey alpine stone"),
    ("rock", "iron_stained", "Rock",
     "iron-stained alpine rock with rusty streaks over grey bedrock, weathered alpine surface"),
    ("rock", "schist_layered", "Rock",
     "layered schist rock with shimmering mica flecks, mid-grey foliation with subtle sparkle"),
    ("rock", "cracked_bedrock", "Rock",
     "cracked alpine bedrock with deep frost-cracks and lichen in fissures, cool grey palette"),
    ("rock", "snow_dusted_rock", "Rock",
     "alpine rock lightly dusted with snow in surface depressions, dark grey with bright accents"),
    ("rock", "verglas_glaze", "Rock",
     "verglas ice glaze over dark alpine rock, glassy reflective surface with subtle grey base"),
]


def already_have(slot_id: str) -> bool:
    d = LIBRARY / slot_id
    return all((d / f"{slot_id}_{m}.png").exists()
               for m in ("albedo", "normal", "roughness", "ao"))


def run_slot(slot: str, tag: str, category: str, body: str, idx: int,
             skip_existing: bool = True) -> bool:
    """Returns True if ran (or was skipped), False on failure."""
    slot_id = f"w4_alpine_div_{idx:02d}_{slot}_{tag}"
    if skip_existing and already_have(slot_id):
        print(f"[skip] {slot_id} already has 4 maps")
        return True

    full_prompt = PROMPT_PREFIX + body + OVERHEAD
    print(f"\n========== [{idx:02d}/{len(SLOTS)}] {slot_id} ==========")
    print(f"  prompt: {full_prompt}")
    cmd = [
        PY, AAA,
        "--prompt", full_prompt,
        "--id", slot_id,
        "--category", category,
        "--quality", "default",
        "--size", "1024",
        "--unet", UNET,
        "--clip", CLIP,
        "--no-gate",
    ]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"  !! FAILED rc={result.returncode}")
        return False
    return True


def main():
    args = sys.argv[1:]
    if args and args[0] == "--only":
        wanted = set(args[1:])
        targets = [(s, t, c, b) for (s, t, c, b) in SLOTS if f"{s}_{t}" in wanted]
    else:
        targets = SLOTS

    print(f"alpine diversity batch: {len(targets)} materials, klein-9b fp8")
    failures = []
    for i, (slot, tag, category, body) in enumerate(targets, start=1):
        ok = run_slot(slot, tag, category, body, i)
        if not ok:
            failures.append(f"{slot}_{tag}")

    print("\n========== batch done ==========")
    print(f"  total:    {len(targets)}")
    print(f"  failures: {len(failures)}")
    for f in failures:
        print(f"    - {f}")
    print("\nreview qa/ thumbnails under:")
    print(f"  {LIBRARY}")
    print("then pick 3 winners (one per slot) to replace biome_alpine.")


if __name__ == "__main__":
    main()
