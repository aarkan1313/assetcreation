#!/usr/bin/env bash
# LoRA train — run id v3_smoke
# Base model: black-forest-labs/FLUX.1-schnell
# Auto-written by pipelines/ui/lora_train.py at 2026-05-06T20:47:27+00:00
#
# Pre-reqs (run once on the 5090 host):
#   conda create -n lora python=3.11 -y && conda activate lora
#   pip install torch==2.7.0 --index-url https://download.pytorch.org/whl/cu128
#   git clone --branch v0.9.0 https://github.com/kohya-ss/sd-scripts.git
#   cd sd-scripts && pip install -e .
#
# Real run (this script):
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p output logs
accelerate launch --num_cpu_threads_per_process 4 \
  $(python -c "import sd_scripts; print(sd_scripts.__path__[0])")/sdxl_train_network.py \
  --config_file 'D:/assets/ui/lora/v3_smoke/train_lora.toml'
