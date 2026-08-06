#!/usr/bin/env python3
"""
detect-gpu.py — Detección automática de GPU y backends de aceleración para llama.cpp

Detecta la presencia de GPUs integradas (Intel HD Graphics / Iris / Arc), GPUs discretas
(NVIDIA, AMD) y soporte de drivers para Vulkan, CUDA, ROCm y Metal.

Uso:
  python3 scripts/commons/detect-gpu.py
  python3 scripts/commons/detect-gpu.py --json
  python3 scripts/commons/detect-gpu.py --toml
"""

import sys
import os
import platform
import subprocess
import shutil
import json
from typing import Dict, Any, List

def run_command(cmd: List[str]) -> str:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return ""

def detect_macos_gpu() -> Dict[str, Any]:
    gpu_info = {
        "vendor": "Apple",
        "model": "Apple Integrated / Discrete GPU",
        "vulkan_supported": False,
        "cuda_supported": False,
        "rocm_supported": False,
        "metal_supported": True,
        "backend_recommended": "GGML_METAL",
        "vram_gb": 0.0
    }
    system_profiler = run_command(["system_profiler", "SPDisplaysDataType"])
    if system_profiler:
        for line in system_profiler.splitlines():
            if "Chipset Model:" in line or "Modelo de chip:" in line:
                gpu_info["model"] = line.split(":", 1)[1].strip()
                break
    return gpu_info

def detect_linux_gpu() -> Dict[str, Any]:
    gpus: List[str] = []
    gpu_info = {
        "vendor": "unknown",
        "model": "unknown",
        "vulkan_supported": False,
        "cuda_supported": False,
        "rocm_supported": False,
        "metal_supported": False,
        "backend_recommended": "CPU",
        "vram_gb": 0.0
    }

    # 1. Detección vía lspci
    lspci_out = run_command(["lspci"])
    if lspci_out:
        for line in lspci_out.splitlines():
            if any(term in line.lower() for term in ["vga compatible controller", "3d controller", "display controller"]):
                gpus.append(line.split(":", 2)[-1].strip())

    # 1b. Detección vía lsgpu (si lspci no está instalado o para más detalle)
    if not gpus and shutil.which("lsgpu"):
        lsgpu_out = run_command(["lsgpu"])
        if lsgpu_out:
            for line in lsgpu_out.splitlines():
                if "drm:" in line or "card" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        gpus.append(" ".join(parts[1:-1]).strip() or parts[0])

    # 1c. Comprobar aceleración DRM (/dev/dri/renderD128)
    drm_available = os.path.exists("/dev/dri/renderD128") or os.path.exists("/dev/dri/card0")

    # 2. Check NVIDIA (CUDA)
    has_nvidia = False
    if shutil.which("nvidia-smi"):
        smi_out = run_command(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
        if smi_out:
            parts = smi_out.splitlines()[0].split(",")
            gpu_info["vendor"] = "NVIDIA"
            gpu_info["model"] = parts[0].strip()
            try:
                gpu_info["vram_gb"] = round(float(parts[1].strip()) / 1024.0, 1)
            except Exception:
                pass
            gpu_info["cuda_supported"] = True
            gpu_info["backend_recommended"] = "GGML_CUDA"
            has_nvidia = True

    # 3. Check Vulkan (Universal para Intel HD / Iris / Arc / AMD / NVIDIA)
    vulkan_ok = False
    if shutil.which("vulkaninfo"):
        vinfo = run_command(["vulkaninfo", "--summary"])
        if "GPU" in vinfo or "Vulkan Instance Version" in vinfo:
            vulkan_ok = True
    elif os.path.exists("/usr/lib/x86_64-linux-gnu/libvulkan.so.1") or os.path.exists("/usr/lib64/libvulkan.so.1") or drm_available:
        vulkan_ok = True

    if vulkan_ok:
        gpu_info["vulkan_supported"] = True

    # 4. Intel / AMD detection via lspci/lsgpu if not NVIDIA
    if not has_nvidia and gpus:
        first_gpu = gpus[0]
        gpu_info["model"] = first_gpu
        if "intel" in first_gpu.lower() or "ivybridge" in first_gpu.lower():
            gpu_info["vendor"] = "Intel"
            if vulkan_ok:
                gpu_info["backend_recommended"] = "GGML_VULKAN"
            else:
                gpu_info["backend_recommended"] = "CPU"
        elif "amd" in first_gpu.lower() or "radeon" in first_gpu.lower():
            gpu_info["vendor"] = "AMD"
            if shutil.which("rocm-smi") or shutil.which("hipconfig"):
                gpu_info["rocm_supported"] = True
                gpu_info["backend_recommended"] = "GGML_HIPBLAS"
            elif vulkan_ok:
                gpu_info["backend_recommended"] = "GGML_VULKAN"
        else:
            if vulkan_ok:
                gpu_info["backend_recommended"] = "GGML_VULKAN"


    return gpu_info

def get_gpu_info() -> Dict[str, Any]:
    os_type = platform.system().lower()
    if os_type == "darwin":
        return detect_macos_gpu()
    elif os_type == "linux":
        return detect_linux_gpu()
    else:
        return {
            "vendor": "unknown",
            "model": "unknown",
            "vulkan_supported": False,
            "cuda_supported": False,
            "rocm_supported": False,
            "metal_supported": False,
            "backend_recommended": "CPU",
            "vram_gb": 0.0
        }

def main():
    info = get_gpu_info()

    if "--json" in sys.argv:
        print(json.dumps(info, indent=2))
        return

    if "--toml" in sys.argv:
        print("[gpu]")
        print(f'vendor              = "{info["vendor"]}"')
        print(f'model               = "{info["model"]}"')
        print(f'vulkan_supported    = {str(info["vulkan_supported"]).lower()}')
        print(f'cuda_supported      = {str(info["cuda_supported"]).lower()}')
        print(f'rocm_supported      = {str(info["rocm_supported"]).lower()}')
        print(f'metal_supported     = {str(info["metal_supported"]).lower()}')
        print(f'backend_recommended = "{info["backend_recommended"]}"')
        print(f'vram_gb             = {info["vram_gb"]}')
        return

    # Salida por defecto formateada para consola
    reset = "\033[0m"
    bold = "\033[1m"
    cyan = "\033[36m"
    green = "\033[32m"
    yellow = "\033[33m"

    print(f"{bold}PoC-Llama.cpp — Diagnóstico de GPU{reset}\n")
    print(f"  {bold}Fabricante / Modelo:{reset}  {info['vendor']} — {info['model']}")
    print(f"  {bold}VRAM Estimada:{reset}        {info['vram_gb']} GB")
    print(f"  {bold}Soporte Vulkan:{reset}       {green + 'SÍ' + reset if info['vulkan_supported'] else yellow + 'NO (requiere mesa-vulkan-drivers / vulkan-tools)' + reset}")
    print(f"  {bold}Soporte CUDA:{reset}         {green + 'SÍ' + reset if info['cuda_supported'] else 'NO'}")
    print(f"  {bold}Soporte ROCm:{reset}         {green + 'SÍ' + reset if info['rocm_supported'] else 'NO'}")
    print(f"  {bold}Soporte Metal:{reset}        {green + 'SÍ' + reset if info['metal_supported'] else 'NO'}")
    print(f"  {bold}Backend Sugerido:{reset}     {cyan}{info['backend_recommended']}{reset}")

if __name__ == "__main__":
    main()
