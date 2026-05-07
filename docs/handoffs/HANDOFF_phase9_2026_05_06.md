# Phase 9 Handoff - Open-Weights / ComfyUI / HF Integration

Date: 2026-05-06
Scope: Research K top-5 plus Tier-2 dry-run adapters.
Runtime rule followed: no GPU, no cloud spend, no ComfyUI server call. Everything real-run capable is gated.

## Built

- K-rec #1: `../../pipelines/_meta/comfy_runner.py`
  - Dry-run by default; `--run` is required to call ComfyUI.
  - Supports dotted overrides such as `7.inputs.seed=42`.
  - POSTs `/prompt`, polls `/history/<prompt_id>`, downloads `/view` outputs.
  - Optional `/object_info` node-class validation.
  - Generic input upload helper uses ComfyUI upload API instead of writing into `../../animators/ComfyUI/input`.

- Starter workflows in `../../pipelines/_meta/comfy_workflows/`
  - `simple_flux_schnell_512.json` - 7 nodes, output node `7`.
  - `simple_image_upscale.json` - 4 nodes, output node `4`.
  - `simple_audio_gen.json` - 2 nodes, output node `2`.

- Downstream Comfy workflow stubs
  - `hunyuan3d_25_image_to_glb.json` - 3 nodes.
  - `flux_schnell_ipadapter_iconset.json` - 9 nodes.
  - `f5tts_voice_clone.json` - 3 nodes.
  - `wan_t2v_5s_720p.json` - 3 nodes.
  - `birefnet_remove_bg.json` - 3 nodes.
  - `depthanything_v2_normal.json` - 5 nodes.

- K-rec #2: `../../pipelines/props/hunyuan3d_route.py`
  - Dry-run writes `prop_asset.v1` + QA under `../../world/props/ai_routes/hunyuan3d/<id>/`.
  - Real run is `--device cuda --run-model` only.

- K-rec #3: `pipelines/ui/local_diffusion_icons.py --backend comfy`
  - Adds FLUX-schnell + IP-Adapter/InstantStyle Comfy plan/run lane.
  - Keeps FLUX-dev / Krea-dev non-commercial hard-stop.

- K-rec #4 and #12: `../../pipelines/audio/local_tts_f5.py`
  - `--engine f5`: dry-run WAV + cue; real Comfy F5 path gated.
  - `--engine kokoro`: Kokoro-82M placeholder/mass-bark lane; real command path gated by `KOKORO_TTS_CMD`.

- K-rec #5: `../../pipelines/video/comfy_video.py` and `../../pipelines/video/flipbook_extract.py`
  - Wan video plan/run wrapper, dry-run by default.
  - CPU image-sequence flipbook extractor.

- K-rec #6: `../../pipelines/game_data/local_llm_backend.py`
  - Default model changed to `Qwen/Qwen2.5-Coder-32B-Instruct-AWQ`.
  - Dry-run now emits exact vLLM request preview with `guided_json` and `guided_decoding_backend=xgrammar`.
  - Real local server call remains behind `--device cuda --run-model`.

- K-rec #7-#11 helpers
  - `../../pipelines/_meta/hf_surveyor.py` with commercial-license accept/reject filter.
  - `../../pipelines/_meta/matting.py` for BiRefNet Comfy planning.
  - `../../pipelines/_meta/depth_normal.py` for DepthAnything-V2 + GeoWizard Comfy planning.
  - `../../pipelines/_meta/upscale.py` as HAT-L Comfy upscale microtool. I did not edit `../../pipelines/textures/flux_upscale.py` because this chat's owned scope excludes texture pipeline code.
  - `../../pipelines/audio/local_music_yue.py` YuE music pilot. MusicGen/AudioCraft/AudioGen are intentionally unsupported.

## Verified

- `python -m py_compile ...` over 12 Phase 9 scripts: clean.
- Workflow JSON parse/node-count check:
  - starter: 7 / 4 / 2 nodes.
  - downstream: 3 / 9 / 3 / 3 / 3 / 5 nodes.
- `curl.exe --version`: curl 8.18.0 available. I did not curl ComfyUI endpoints.

Dry-run smoke artifacts:

- `../../pipelines/_meta/reports/phase9_comfy_runner_smoke.json`
  - `dry_run=true`, `node_count=7`, `output_node_ids=["7"]`.
- `../../pipelines/_meta/reports/phase9_comfy_audio_workflow_smoke.json`
  - `node_count=2`, output node `2`.
- `../../pipelines/_meta/reports/phase9_comfy_upscale_workflow_smoke.json`
  - `node_count=4`, output node `4`.
- `../../world/props/ai_routes/hunyuan3d/phase9_hunyuan_smoke/prop.json`
  - `prop_asset.v1`, status `dry_run`; `qa.json` also written.
- `../../ui/diffusion_plans/phase9_comfy_icons.plan.json`
  - 6 icon prompts planned, FLUX-schnell Apache-2.0, output node `9`.
- `../../audio/voice/phase9_f5_smoke.wav`
  - 2.39s placeholder, 114,764 bytes, cue written.
- `../../audio/voice/phase9_kokoro_smoke.wav`
  - 2.73s placeholder, 131,084 bytes, cue written.
- `../../video/runs/phase9_wan_smoke/video_plan.json`
  - 24 frames planned at 12 fps, 512x288.
- `../../video/runs/phase9_wan_smoke/flipbook_manifest.json`
  - dry-run, frame count 0.
- `../../game_data/reports/phase9_local_llm_dryrun_item.json`
  - `parser_ok=true`, includes vLLM `guided_json` + xgrammar preview.
- `../../research/_surveyor/phase9_hf_surveyor_smoke.md`
  - 3 dry-run rows with accept/reject license filtering.
- `../../pipelines/_meta/reports/phase9_witch_matte.matting_plan.json`
  - BiRefNet workflow dry-run, 3 nodes.
- `../../pipelines/_meta/reports/phase9_depth_witch/depth_normal_plan.json`
  - depth/normal workflow dry-run, 5 nodes.
- `../../pipelines/_meta/reports/phase9_witch_upscaled.upscale_plan.json`
  - HAT-L upscale workflow dry-run, 4 nodes.
- `../../audio/music/phase9_yue_smoke.wav`
  - 4.00s placeholder, 705,644 bytes, `.music.json` written.

## Stubbed / Blocked

- ComfyUI install check: `../../animators/ComfyUI/custom_nodes/` currently contains only `example_node.py.example` and `websocket_image_save.py`.
- Therefore Hunyuan3D, IP-Adapter/InstantStyle, F5-TTS, Wan, BiRefNet, and DepthAnything workflows are workflow-contract stubs until their custom node packs are installed.
- GPU-bound verification is intentionally deferred because the 5090 is reserved.
- HAT-L texture retrofit is only the `_meta/upscale.py` microtool in this pass; texture-lane integration should be a separate owner-approved edit.

## Real-Run Verify Commands When GPU / Nodes Are Free

```powershell
curl.exe http://127.0.0.1:8188/object_info

python pipelines\props\hunyuan3d_route.py images\archived\witch.png --id witch_hunyuan_real --device cuda --run-model
python pipelines\ui\local_diffusion_icons.py --prompts ui\prompts.json --backend comfy --style-image images\archived\witch.png --run
python pipelines\audio\local_tts_f5.py --text "The old gate opens at dusk." --ref-audio <voice.wav> --ref-text "<transcript>" --out audio\voice\f5_real.wav --device cuda --run-model
python pipelines\video\comfy_video.py --id portal_real --prompt "looping glowing portal UI stinger" --device cuda --run-model
python pipelines\game_data\local_llm_backend.py item --backend vllm --device cuda --run-model --max-records 10
python pipelines\_meta\hf_surveyor.py --pipelines text-to-image,image-to-3d,text-to-speech --out research\_surveyor\manual_run.md
```

## Docs Updated

- `../plans/EXPANSION_PLAN.md` Phase 9 status.
- `../../PIPELINE_DIRECTORY.md` ComfyUI role and Phase 9 lane note.
- `../../TOOLS_INDEX.md` new tools and updated adapter descriptions.
- `../reference/CLOUD_KEYS.md` local-only replacement paths and new runtime command gates.
