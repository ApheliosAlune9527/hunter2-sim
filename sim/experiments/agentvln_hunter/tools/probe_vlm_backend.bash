#!/usr/bin/env bash
# Probe the local WSL inference backends available for a small VLM.
source /mnt/d/rob-memory/sim/experiments/lab_nav_fix_20261106/lab_nav_fix_env.bash >/dev/null 2>&1 || true
echo "== display devices"
lspci 2>/dev/null | grep -Ei 'vga|3d|display' || true
echo "== rocm"
command -v rocminfo && (rocminfo 2>&1 | head -25) || echo no_rocminfo
command -v rocm-smi && (rocm-smi 2>&1 | head -30) || echo no_rocm_smi
echo "== vulkan"
command -v vulkaninfo && (vulkaninfo --summary 2>&1 | head -40) || echo no_vulkaninfo
echo "== nvidia"
command -v nvidia-smi && nvidia-smi || echo no_nvidia
echo "== python modules"
python3 - <<'PY'
import importlib.util
for m in ['torch','transformers','accelerate','bitsandbytes','llama_cpp','ollama','cv2','PIL','qwen_vl_utils']:
    print(m, bool(importlib.util.find_spec(m)))
try:
    import torch
    print('torch_version', torch.__version__)
    print('cuda_available', torch.cuda.is_available())
    print('cuda_device_count', torch.cuda.device_count())
except Exception as exc:
    print('torch_import_error', repr(exc))
PY
echo "== huggingface cache"
du -sh "$HOME/.cache/huggingface" 2>/dev/null || true
find "$HOME/.cache/huggingface" -maxdepth 3 -type d 2>/dev/null | head -30 || true
echo "== ollama"
command -v ollama && ollama list 2>&1 || echo no_ollama
echo "== llama.cpp binaries"
command -v llama-cli || true
command -v llama-server || true
command -v llava-cli || true
