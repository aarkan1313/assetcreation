"""W4 biome-kit ComfyUI batch driver.

Generates the ComfyUI PBR slots for the 4 new W4 biomes (alpine, desert,
rocky, wetland) via aaa_texture.py with klein-9B FP8 + qwen_3_8b.

Output: world/textures/library/<id>/ first, then mirrored into
world 4/the world 4/materials/biome_<name>/<slot>/{albedo,normal,roughness,ao}.png.

Prompts come straight from plans/AXIS6_TEXTURE_VARIETY_2026_05_11.md.

Skips slots that already have output in world 4/.../materials/biome_<name>/<slot>/.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PY = r"C:\Program Files\Python312\python.exe"
AAA = r"D:\assets\pipelines\textures\aaa_texture.py"
LIBRARY = Path(r"D:\assets\world\textures\library")
DEST_ROOT = Path(r"D:\assets\world 4\the world 4\materials")

UNET = "flux-2-klein-9b-fp8.safetensors"
CLIP = "qwen_3_8b_fp8mixed.safetensors"

# (biome, slot, category, prompt)
SLOTS = [
    ("alpine", "mid", "Snow",
     "tileable seamless texture, mixed terrain - patchy lichen-spotted rock peeking through thin snow cover, cool grey-blue palette, overhead perspective, weathered"),
    ("desert", "ground", "Sand",
     "tileable seamless texture, fine warm desert sand, slight ripples, soft yellow-tan tones, overhead perspective, no debris"),
    ("desert", "mid", "Ground",
     "tileable seamless texture, dry desert ground with sparse dead scrub, sand-and-rock-fragment mix, warm orange-tan palette, overhead perspective"),
    ("rocky", "mid", "Foliage",
     "tileable seamless texture, patchy moss and lichen on grey rock, mid-grey palette with sparse green accents, overhead perspective, weathered"),
    ("wetland", "ground", "Ground",
     "tileable seamless texture, dark wet peat soil with sparse green moss patches, muted dark-brown palette, overhead perspective, slight wetness"),
    ("wetland", "mid", "Foliage",
     "tileable seamless texture, marsh ground with tall reed grass tufts, muted green and brown palette, overhead perspective, soft"),
    ("wetland", "rock", "Rock",
     "tileable seamless texture, waterworn dark rounded rocks with moss cover, wet-rock palette of dark greys and greens, overhead perspective"),
    # Rock slots originally planned as real-ortho via W3 _soft_composite, but
    # that pipeline needs orthophoto+DTM stack pairs we don't have for alpine
    # and desert regions. Generated via ComfyUI klein-9B as a session-1
    # tactical deviation; backfilling with real-ortho is a follow-up.
    ("alpine", "rock", "Rock",
     "tileable seamless texture, weathered dark slate rock, cracked alpine bedrock, cool dark grey palette with subtle blue undertones, overhead perspective, sharp angular fractures"),
    ("desert", "rock", "Rock",
     "tileable seamless texture, weathered brown sandstone outcrop, warm dry palette of tans and rusty browns, eroded layers and pitting, overhead perspective"),
    ("rocky", "ground", "Rock",
     "tileable seamless texture, loose scree slope of mid-grey rock fragments, talus debris field, cool dust-grey palette, overhead perspective, sharp angular pieces of varied sizes"),
]


def already_have(biome: str, slot: str) -> bool:
    d = DEST_ROOT / f"biome_{biome}" / slot
    return all((d / m).exists() for m in ("albedo.png", "normal.png",
                                          "roughness.png", "ao.png"))


def install_to_w4(slot_id: str, biome: str, slot: str) -> None:
    src = LIBRARY / slot_id
    dst = DEST_ROOT / f"biome_{biome}" / slot
    dst.mkdir(parents=True, exist_ok=True)
    pairs = {
        f"{slot_id}_albedo.png": "albedo.png",
        f"{slot_id}_normal.png": "normal.png",
        f"{slot_id}_roughness.png": "roughness.png",
        f"{slot_id}_ao.png": "ao.png",
    }
    for s, d in pairs.items():
        sp = src / s
        if not sp.exists():
            raise FileNotFoundError(f"missing generated map: {sp}")
        shutil.copy2(sp, dst / d)
    print(f"  installed -> {dst}")


def run_slot(biome: str, slot: str, category: str, prompt: str,
             skip_existing: bool = True) -> None:
    if skip_existing and already_have(biome, slot):
        print(f"[skip] biome_{biome}/{slot} already has 4 maps")
        return

    slot_id = f"w4_biome_{biome}_{slot}"
    print(f"\n========== {slot_id} ==========")
    print(f"  prompt: {prompt}")
    cmd = [
        PY, AAA,
        "--prompt", prompt,
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
        raise RuntimeError(f"aaa_texture.py failed for {slot_id}")
    install_to_w4(slot_id, biome, slot)


def main():
    args = sys.argv[1:]
    if args and args[0] == "--only":
        wanted = set(args[1:])
        targets = [t for t in SLOTS if f"{t[0]}_{t[1]}" in wanted]
    else:
        targets = SLOTS

    print(f"running {len(targets)} slot(s) with klein-9b fp8 + qwen_3_8b")
    for biome, slot, category, prompt in targets:
        run_slot(biome, slot, category, prompt)

    print("\n========== batch done ==========")
    for biome, slot, _, _ in SLOTS:
        ok = already_have(biome, slot)
        print(f"  biome_{biome}/{slot}: {'OK' if ok else 'MISSING'}")


if __name__ == "__main__":
    main()
