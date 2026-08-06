#!/usr/bin/env python3
"""
detect_gpu.py — Detección automática de GPU y backends de aceleración para llama.cpp

Detecta la presencia de GPUs integradas (Intel HD Graphics / Iris / Arc), GPUs discretas
(NVIDIA, AMD) y soporte de drivers para Vulkan, CUDA, ROCm y Metal.

Uso:
  python3 scripts/commons/detect_gpu.py
  python3 scripts/commons/detect_gpu.py --json
  python3 scripts/commons/detect_gpu.py --toml
  python3 scripts/commons/detect_gpu.py --has-vulkan-sdk   # exit 0/1
  python3 scripts/commons/detect_gpu.py --has-opencl-sdk   # exit 0/1
  python3 scripts/commons/detect_gpu.py --has-gpu-sdk      # exit 0 si hay GPU (Vulkan/Metal/CUDA/ROCm/OpenCL)
  python3 scripts/commons/detect_gpu.py --vulkan-override   # emite -DGGML_VULKAN=ON o vacío
  python3 scripts/commons/detect_gpu.py --opencl-override   # emite -DGGML_OPENCL=ON o vacío
  python3 scripts/commons/detect_gpu.py --missing           # lista paquetes Vulkan faltantes
  python3 scripts/commons/detect_gpu.py --opencl-missing    # lista paquetes OpenCL faltantes
"""

import sys
import os
import platform
import subprocess
import shutil
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

# Paquetes Debian necesarios para compilación Vulkan de llama.cpp
# Orden: requeridos para compilar, luego opcionales
_VULKAN_DEBIAN_PKGS: List[Dict[str, str]] = [
    {"pkg": "libvulkan-dev",       "role": "headers + loader (compilación)"},
    {"pkg": "glslang-tools",       "role": "herramientas glslang (compilación)"},
    {"pkg": "glslc",               "role": "compilador glslc (Debian 13+)"},
    {"pkg": "spirv-headers",       "role": "headers SPIR-V (compilación shaders)"},
    {"pkg": "mesa-vulkan-drivers", "role": "driver Intel/AMD (runtime)"},
    {"pkg": "vulkan-tools",        "role": "vulkaninfo (diagnóstico, opcional)"},
]

# Paquetes debian requeridos para compilación. Se marcan como faltantes
# si ninguno de los dos (glslang-tools o glslc) provee el binario.
_VULKAN_COMPILER_PKGS = {"glslang-tools", "glslc"}

_OPENCL_DEBIAN_PKGS: List[Dict[str, str]] = [
    {"pkg": "ocl-icd-opencl-dev", "role": "headers + loader OpenCL (compilación)"},
    {"pkg": "clinfo",             "role": "info dispositivos (diagnóstico)"},
    {"pkg": "mesa-opencl-icd",    "role": "driver Intel/AMD (runtime)"},
]


def run_command(cmd: List[str]) -> str:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return ""


def _check_debian_pkg(pkg: str) -> bool:
    result = run_command(["dpkg-query", "-W", "-f=${Status}", pkg])
    return "install ok installed" in result


def _detect_vulkan_packages() -> Dict[str, Any]:
    pkgs_status = {}
    missing = []

    for entry in _VULKAN_DEBIAN_PKGS:
        pkg = entry["pkg"]
        installed = _check_debian_pkg(pkg)
        pkgs_status[pkg] = {
            "installed": installed,
            "role": entry["role"],
        }
        if not installed:
            missing.append(pkg)

    libdev_ok = pkgs_status.get("libvulkan-dev", {}).get("installed", False)
    compiler_ok = (
        pkgs_status.get("glslang-tools", {}).get("installed", False) or
        pkgs_status.get("glslc", {}).get("installed", False)
    )
    spirv_ok = pkgs_status.get("spirv-headers", {}).get("installed", False)

    missing_required = []
    if not libdev_ok:
        missing_required.append("libvulkan-dev")
    if not compiler_ok:
        missing_required.append("glslc")
    if not spirv_ok:
        missing_required.append("spirv-headers")

    return {
        "packages": pkgs_status,
        "missing": missing,
        "missing_required": missing_required,
        "all_required_installed": len(missing_required) == 0,
    }

# GPUs Intel anteriores a Gen8 (Broadwell) no soportan fp16 storage,
# requerido por el backend Vulkan de llama.cpp. Marcar como no compatibles.
_INTEL_GPU_TOO_OLD = {
    "2nd generation", "2nd gen",
    "3rd generation", "3rd gen",
    "4th generation", "4th gen",
    "sandybridge", "ivybridge", "haswell",
    "bay trail", "cherry trail",
}

def _intel_gen_too_old(gpu_desc: str) -> bool:
    for keyword in _INTEL_GPU_TOO_OLD:
        if keyword.lower() in gpu_desc.lower():
            return True
    return False

def _check_opencl() -> Dict[str, Any]:
    has_clinfo = shutil.which("clinfo") is not None
    has_headers = os.path.exists("/usr/include/CL/cl.h") or os.path.exists("/usr/include/CL/opencl.h")
    has_lib = os.path.exists("/usr/lib/x86_64-linux-gnu/libOpenCL.so") or os.path.exists("/usr/lib64/libOpenCL.so")

    packages = {}
    missing = []
    for entry in _OPENCL_DEBIAN_PKGS:
        pkg = entry["pkg"]
        installed = _check_debian_pkg(pkg)
        packages[pkg] = {"installed": installed, "role": entry["role"]}
        if not installed:
            missing.append(pkg)

    gpu_count = 0
    if has_clinfo:
        out = run_command(["clinfo", "--list"])
        for line in out.splitlines():
            if "GPU" in line:
                gpu_count += 1

    return {
        "opencl_supported": (has_clinfo or has_lib) and has_headers,
        "opencl_packages": packages,
        "opencl_missing": missing,
        "opencl_gpu_count": gpu_count,
    }

def detect_macos_gpu() -> Dict[str, Any]:
    gpu_info = {
        "vendor": "Apple",
        "model": "Apple Integrated / Discrete GPU",
        "vulkan_supported": False,
        "vulkan_packages": {},
        "vulkan_missing": [],
        "opencl_supported": False,
        "opencl_packages": {},
        "opencl_missing": [],
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
        "vulkan_packages": {},
        "vulkan_missing": [],
        "opencl_supported": False,
        "opencl_packages": {},
        "opencl_missing": [],
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

    # 1b. Detección vía lsgpu (complementa lspci con info de chipset)
    if shutil.which("lsgpu"):
        lsgpu_out = run_command(["lsgpu"])
        if lsgpu_out:
            for line in lsgpu_out.splitlines():
                if "drm:" in line or "card" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        ls_name = " ".join(parts[1:-1]).strip() if parts[-1].startswith("drm:") else " ".join(parts[1:]).strip() if len(parts) >= 3 else parts[0]
                        if ls_name and ls_name not in gpus:
                            gpus.append(ls_name)

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
    #    Fuente de verdad: binario glslc + headers vulkan.h (no dpkg-query).
    #    dpkg-query es solo informativo para mostrar qué instalar.
    vulkan_pkg_info = _detect_vulkan_packages()
    gpu_info["vulkan_packages"] = vulkan_pkg_info["packages"]
    gpu_info["vulkan_missing"] = vulkan_pkg_info["missing"]

    has_glslc = shutil.which("glslc") is not None
    has_headers = os.path.exists("/usr/include/vulkan/vulkan.h")
    has_spirv = os.path.exists("/usr/include/spirv/unified1/spirv.h")
    if not has_spirv:
        has_spirv = any(Path("/usr").glob("**/SPIRV-HeadersConfig.cmake"))
    vulkan_sdk_ok = has_glslc and has_headers and has_spirv

    vulkan_ok = False
    if vulkan_sdk_ok:
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
            if _intel_gen_too_old(first_gpu):
                gpu_info["vulkan_supported"] = False
                gpu_info["backend_recommended"] = "CPU"
            elif vulkan_ok:
                gpu_info["backend_recommended"] = "GGML_VULKAN"
            else:
                gpu_info["backend_recommended"] = "CPU"
        elif "amd" in first_gpu.lower() or "radeon" in first_gpu.lower():
            gpu_info["vendor"] = "AMD"
            if shutil.which("rocm-smi") or shutil.which("hipconfig"):
                gpu_info["rocm_supported"] = True
                gpu_info["backend_recommended"] = "GGML_HIP"
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
            "vulkan_packages": {},
            "vulkan_missing": [],
            "opencl_supported": False,
            "opencl_packages": {},
            "opencl_missing": [],
            "cuda_supported": False,
            "rocm_supported": False,
            "metal_supported": False,
            "backend_recommended": "CPU",
            "vram_gb": 0.0
        }

def main():
    info = get_gpu_info()

    # ── Modos especiales de salida (sin formato consola) ──────────────────
    if "--has-vulkan-sdk" in sys.argv:
        if info["vulkan_supported"]:
            sys.exit(0)
        else:
            sys.exit(1)

    if "--has-opencl-sdk" in sys.argv:
        if info["opencl_supported"]:
            sys.exit(0)
        else:
            sys.exit(1)

    if "--has-gpu-sdk" in sys.argv:
        if (info["vulkan_supported"] or info["cuda_supported"] or
                info["metal_supported"] or info.get("rocm_supported", False) or
                info.get("opencl_supported", False)):
            sys.exit(0)
        else:
            sys.exit(1)

    if "--vulkan-override" in sys.argv:
        if info["vulkan_supported"]:
            glslc_path = shutil.which("glslc")
            if glslc_path:
                print(f"-DGGML_VULKAN=ON -DVulkan_GLSLC_EXECUTABLE={glslc_path}")
            else:
                print("-DGGML_VULKAN=ON")
        sys.exit(0)

    if "--opencl-override" in sys.argv:
        if info["opencl_supported"]:
            print("-DGGML_OPENCL=ON")
        sys.exit(0)

    if "--missing" in sys.argv:
        missing = info.get("vulkan_missing", [])
        if missing:
            print(f"sudo apt-get install -y {' '.join(missing)}")
        sys.exit(0)

    if "--opencl-missing" in sys.argv:
        missing = info.get("opencl_missing", [])
        if missing:
            print(f"sudo apt-get install -y {' '.join(missing)}")
        sys.exit(0)

    if "--json" in sys.argv:
        print(json.dumps(info, indent=2, ensure_ascii=False))
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

    # ── Salida por defecto formateada para consola ────────────────────────
    reset = "\033[0m"
    bold = "\033[1m"
    cyan = "\033[36m"
    green = "\033[32m"
    yellow = "\033[33m"
    red = "\033[31m"
    dim = "\033[2m"

    print(f"{bold}PoC-Llama.cpp — Diagnóstico de GPU{reset}\n")
    print(f"  {bold}Fabricante / Modelo:{reset}  {info['vendor']} — {info['model']}")
    print(f"  {bold}VRAM Estimada:{reset}        {info['vram_gb']} GB")

    # Vulkan: mostrar paquetes individuales si están disponibles
    vulkan_pkg_info = info.get("vulkan_packages", {})
    if info['vulkan_supported']:
        print(f"  {bold}Soporte Vulkan:{reset}       {green}SÍ{reset}")
    elif vulkan_pkg_info:
        print(f"  {bold}Soporte Vulkan:{reset}       {yellow}NO — paquetes faltantes:{reset}")
        for pkg_name, pkg_data in sorted(vulkan_pkg_info.items()):
            icon = f"{green}✓{reset}" if pkg_data["installed"] else f"{red}✗{reset}"
            print(f"      {icon} {pkg_name:<24} {dim}({pkg_data['role']}){reset}")
        missing = info.get("vulkan_missing", [])
        if missing:
            print(f"  {bold}Instalar con:{reset}          {cyan}sudo apt-get install -y {' '.join(missing)}{reset}")
    else:
        print(f"  {bold}Soporte Vulkan:{reset}       {yellow}NO (requiere libvulkan-dev + glslc){reset}")

    print(f"  {bold}Soporte CUDA:{reset}         {green + 'SÍ' + reset if info['cuda_supported'] else 'NO'}")
    print(f"  {bold}Soporte ROCm:{reset}         {green + 'SÍ' + reset if info['rocm_supported'] else 'NO'}")
    print(f"  {bold}Soporte OpenCL:{reset}       {green + 'SÍ' + reset if info.get('opencl_supported') else yellow + 'NO' + reset}")
    print(f"  {bold}Soporte Metal:{reset}        {green + 'SÍ' + reset if info['metal_supported'] else 'NO'}")
    print(f"  {bold}Backend Sugerido:{reset}     {cyan}{info['backend_recommended']}{reset}")

if __name__ == "__main__":
    main()
