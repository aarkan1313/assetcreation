"""Gate-1: Hunyuan3D-2.1 geometry-only smoke run.

Sends concept PNG -> kijai chain -> GLB. Output lands in
ComfyUI_HY3D/output/props/ and we'll publish from there.
"""
import sys, json, time
from pathlib import Path
sys.path.insert(0, r"D:\assets")
from pipelines._meta.comfy_runner import ComfyRunner, load_workflow

CONCEPT = Path(r"D:\assets\world\props\concepts\ruined_obelisk_a\source.png")
WF = Path(r"D:\assets\pipelines\_meta\comfy_workflows\hunyuan3d_21_image_to_glb_geo.json")
OUT_DIR = Path(r"D:\assets\world\props\ai_routes\hunyuan3d\ruined_obelisk_a_gate1")
OUT_DIR.mkdir(parents=True, exist_ok=True)

r = ComfyRunner("http://127.0.0.1:8189")
wf_full = load_workflow(WF)
# Strip top-level _doc / _required_models / _node_packs / _owner comment keys
wf = {k: v for k, v in wf_full.items() if not k.startswith("_")}
print(f"[gate1] workflow has {len(wf)} nodes")

# Upload the concept image to ComfyUI's input/
comfy_name = r.upload_image(CONCEPT, name="ruined_obelisk_a_source.png", overwrite=True)
print(f"[gate1] uploaded {comfy_name}")

# Override LoadImage to use the uploaded name + bump seed if you want
wf["1"]["inputs"]["image"] = comfy_name
wf["3"]["inputs"]["seed"] = 42  # already 42; explicit

# Validate node availability (we already did this, but be paranoid)
missing = r.missing_node_types(wf)
if missing:
    print(f"[gate1] FATAL missing nodes: {missing}", file=sys.stderr)
    raise SystemExit(2)

t0 = time.time()
prompt_id = r.submit(wf)
print(f"[gate1] submitted prompt_id={prompt_id}")

history = r.wait_for_history(prompt_id, timeout_s=1800.0, poll_s=3.0)
elapsed = time.time() - t0
print(f"[gate1] history received after {elapsed:.1f}s")

# Save raw history for forensics
(OUT_DIR / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")

# Output node 6 is Hy3DExportMesh -> writes GLB into output/props/
outputs = history.get(prompt_id, {}).get("outputs", {})
print(f"[gate1] output nodes with results: {sorted(outputs.keys())}")
for nid, payload in outputs.items():
    print(f"  node {nid}: keys={list(payload.keys())}")
    for k, v in payload.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            for entry in v[:3]:
                print(f"    {k} -> {entry}")
print(f"[gate1] DONE in {elapsed:.1f}s")
