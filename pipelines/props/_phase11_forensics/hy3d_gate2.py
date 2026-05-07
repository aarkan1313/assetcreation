"""Gate-2: Hunyuan3D-2.1 PBR-textured smoke run via visualbruno chain.

This is the WHOLE point of the install — image -> mesh + albedo + metallic-roughness textures.
"""
import sys, json, time
from pathlib import Path
sys.path.insert(0, r"D:\assets")
from pipelines._meta.comfy_runner import ComfyRunner, load_workflow

CONCEPT = Path(r"D:\assets\world\props\concepts\ruined_obelisk_a\source.png")
WF = Path(r"D:\assets\pipelines\_meta\comfy_workflows\hunyuan3d_21_image_to_glb_pbr.json")
OUT_DIR = Path(r"D:\assets\world\props\ai_routes\hunyuan3d\ruined_obelisk_a_gate2_real")
OUT_DIR.mkdir(parents=True, exist_ok=True)

r = ComfyRunner("http://127.0.0.1:8189")
wf_full = load_workflow(WF)
wf = {k: v for k, v in wf_full.items() if not k.startswith("_")}
print(f"[gate2] workflow has {len(wf)} nodes")

comfy_name = r.upload_image(CONCEPT, name="ruined_obelisk_a_source.png", overwrite=True)
print(f"[gate2] uploaded {comfy_name}")
wf["1"]["inputs"]["image"] = comfy_name

missing = r.missing_node_types(wf)
if missing:
    print(f"[gate2] FATAL missing nodes: {missing}", file=sys.stderr)
    raise SystemExit(2)

t0 = time.time()
prompt_id = r.submit(wf)
print(f"[gate2] submitted prompt_id={prompt_id}")
print(f"[gate2] expected wall-clock: ~3-6 min (DiT + multiview paint + bake + inpaint)")

history = r.wait_for_history(prompt_id, timeout_s=1800.0, poll_s=5.0)
elapsed = time.time() - t0
print(f"[gate2] history received after {elapsed:.1f}s")

(OUT_DIR / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")

outputs = history.get(prompt_id, {}).get("outputs", {})
print(f"[gate2] output nodes with results: {sorted(outputs.keys())}")
for nid, payload in outputs.items():
    print(f"  node {nid}: keys={list(payload.keys())}")
    for k, v in payload.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            for entry in v[:3]:
                print(f"    {k} -> {entry}")
print(f"[gate2] DONE in {elapsed:.1f}s")
