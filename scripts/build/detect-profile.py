#!/usr/bin/env python3
"""
detect-profile.py — Detección inteligente de hardware para compile-auto.

Detecta OS, arquitectura, modelo de CPU, microarquitectura y extensiones
relevantes para llama.cpp (AVX, AVX2, NEON, SVE, Metal, etc.).

Modos de salida:
  --info   → JSON con toda la detección
  --flags  → flags cmake listos para pasar a cmake
  --match  → nombre de perfil TOML si hay coincidencia (vacío si no)

Uso:
  python3 scripts/build/detect-profile.py --info
  python3 scripts/build/detect-profile.py --flags
  python3 scripts/build/detect-profile.py --match
"""

import json
import argparse
import platform
import subprocess
import sys
from pathlib import Path

TEMPLATES_DIR = Path("build/templates")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str]) -> str:
    """Ejecuta un comando y devuelve stdout o '' si falla."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return ""


def _read_file(path: str) -> str:
    """Lee un archivo de texto o devuelve '' si no existe."""
    try:
        return Path(path).read_text().strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Detección por plataforma
# ---------------------------------------------------------------------------

def detect_linux_x86() -> dict:
    """Detecta CPU en Linux x86_64."""
    cpuinfo = _read_file("/proc/cpuinfo")
    model_name = ""
    flags_list: list[str] = []

    for line in cpuinfo.splitlines():
        line = line.strip()
        if not line:
            continue
        key, sep, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if key == "model name" and not model_name:
            model_name = val
        if key == "flags":
            flags_list.extend(val.split())

    cores = len([l for l in cpuinfo.splitlines() if l.startswith("processor")])
    if cores == 0:
        cores = int(_run(["nproc"]) or "1")

    flags_set = set(flags_list)

    return {
        "cpu_model": model_name,
        "logical_cpus": cores,
        "has_avx": "avx" in flags_set,
        "has_avx2": "avx2" in flags_set,
        "has_avx512": "avx512f" in flags_set,
        "has_fma": "fma" in flags_set,
        "has_f16c": "f16c" in flags_set,
        "has_sse3": "pni" in flags_set,
        "has_ssse3": "ssse3" in flags_set,
        "has_sse41": "sse4_1" in flags_set,
        "has_sse42": "sse4_2" in flags_set,
        "has_bmi2": "bmi2" in flags_set,
        "has_metal": False,
    }


def detect_linux_arm() -> dict:
    """Detecta CPU en Linux aarch64."""
    cpuinfo = _read_file("/proc/cpuinfo")
    model_name = ""
    cpu_part = ""
    features = set()

    for line in cpuinfo.splitlines():
        line = line.strip()
        if not line:
            continue
        key, sep, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if key == "Model" and not model_name:
            model_name = val
        if key == "CPU part":
            cpu_part = val
        if key == "Features":
            features = set(val.split())

    # Producto (ej: Raspberry Pi)
    product = ""
    dt_model = _read_file("/proc/device-tree/model")
    if dt_model:
        product = dt_model.rstrip("\x00")

    cores = len([l for l in cpuinfo.splitlines() if l.startswith("processor")])
    if cores == 0:
        cores = int(_run(["nproc"]) or "1")

    has_neon = "asimd" in features
    has_sve = "sve" in features
    has_fp16 = "fphp" in features and "asimdhp" in features

    return {
        "cpu_model": model_name,
        "cpu_part": cpu_part,
        "product": product,
        "logical_cpus": cores,
        "has_neon": has_neon,
        "has_sve": has_sve,
        "has_fp16_compute": has_fp16,
        "has_metal": False,
    }


def detect_macos_x86() -> dict:
    """Detecta CPU en macOS x86_64."""
    brand = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
    cores = int(_run(["sysctl", "-n", "hw.logicalcpu"]) or "1")
    features_raw = _run(["sysctl", "-n", "machdep.cpu.features"])
    features_set = set(features_raw.lower().split())

    return {
        "cpu_model": brand,
        "logical_cpus": cores,
        "has_avx": "avx1.0" in features_raw or "avx" in features_set,
        "has_avx2": "avx2.0" in features_raw or "avx2" in features_set,
        "has_avx512": "avx512f" in features_set,
        "has_fma": "fma" in features_set,
        "has_f16c": "f16c" in features_set,
        "has_bmi2": "bmi2" in features_set,
        "has_metal": False,
    }


def detect_macos_arm() -> dict:
    """Detecta CPU en macOS ARM64 (Apple Silicon)."""
    brand = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
    if not brand:
        brand = "Apple Silicon"
    cores_p = int(_run(["sysctl", "-n", "hw.perflevel0.physicalcpu"]) or "0")
    cores_e = int(_run(["sysctl", "-n", "hw.perflevel1.physicalcpu"]) or "0")
    total = int(_run(["sysctl", "-n", "hw.logicalcpu"]) or "1")

    # Capacidades ARM vía hw.optional
    neon = _run(["sysctl", "-n", "hw.optional.neon"])
    sve = _run(["sysctl", "-n", "hw.optional.arm.FEAT_SVE"])
    fp16 = _run(["sysctl", "-n", "hw.optional.arm.FEAT_FP16"])

    return {
        "cpu_model": brand,
        "logical_cpus": total,
        "perf_cores": cores_p,
        "efficiency_cores": cores_e,
        "has_neon": neon == "1",
        "has_sve": sve == "1",
        "has_fp16_compute": fp16 == "1",
        "has_metal": True,  # Metal siempre disponible en Apple Silicon
    }


# ---------------------------------------------------------------------------
# Orquestador de detección
# ---------------------------------------------------------------------------

def detect() -> dict:
    """Detecta hardware de forma unificada."""
    os_name = platform.system()
    arch = platform.machine()

    base = {"os": os_name, "arch": arch}

    if os_name == "Linux" and arch == "x86_64":
        base.update(detect_linux_x86())
    elif os_name == "Linux" and arch == "aarch64":
        base.update(detect_linux_arm())
    elif os_name == "Darwin" and arch == "x86_64":
        base.update(detect_macos_x86())
    elif os_name == "Darwin" and arch in ("arm64", "aarch64"):
        base.update(detect_macos_arm())
    else:
        base.update({"cpu_model": "unknown", "logical_cpus": 1})

    return base


# ---------------------------------------------------------------------------
# Generación de flags cmake
# ---------------------------------------------------------------------------

def cmake_flags_from_detection(det: dict) -> str:
    """Genera flags cmake a partir de la detección de hardware de CPU y GPU."""
    flags = ["-DCMAKE_BUILD_TYPE=Release"]
    os_name = det.get("os", "")
    arch = det.get("arch", "")

    # Detección de GPU
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "commons"))
        from detect_gpu import get_gpu_info
        gpu_info = get_gpu_info()
        rec_backend = gpu_info.get("backend_recommended", "CPU")
        if rec_backend == "GGML_VULKAN":
            flags.append("-DGGML_VULKAN=ON")
        elif rec_backend == "GGML_CUDA":
            flags.append("-DGGML_CUDA=ON")
        elif rec_backend == "GGML_HIP":
            flags.append("-DGGML_HIP=ON")
    except Exception:
        pass

    if os_name == "Darwin" and det.get("has_metal"):
        flags.append("-DGGML_METAL=ON")
        flags.append("-DGGML_BLAS=OFF")
    elif det.get("has_avx2"):
        flags.extend([
            "-DGGML_AVX2=ON",
            "-DGGML_AVX=ON",
            "-DGGML_F16C=ON",
            "-DGGML_FMA=ON",
        ])
    elif det.get("has_avx"):
        flags.extend([
            "-DGGML_AVX=ON",
            "-DGGML_AVX2=OFF",
        ])
    elif det.get("has_neon"):
        flags.extend([
            "-DGGML_NEON=ON",
            "-DGGML_NATIVE=OFF",
        ])
        if det.get("has_sve"):
            flags.append("-DGGML_SVE=ON")
    else:
        # Fallback: delegar a cmake la detección de -march=native
        flags.append("-DGGML_NATIVE=ON")

    return " ".join(flags)



# ---------------------------------------------------------------------------
# Match de perfiles TOML
# ---------------------------------------------------------------------------

def _load_toml_profile(toml_path: Path) -> dict:
    """Carga un build.toml y devuelve la sección [hardware]."""
    try:
        import tomllib
    except ModuleNotFoundError:
        try:
            import tomli as tomllib
        except ModuleNotFoundError:
            return {}

    try:
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return {}

    # Si tiene herencia, cargar el perfil base para obtener hardware completo
    inherits = data.pop("inherits", None)
    if inherits:
        templates_root = toml_path.parents[2]
        base_path = templates_root / f"{inherits}.toml"
        if base_path.exists():
            try:
                with open(base_path, "rb") as f:
                    base = tomllib.load(f)
                # Fusionar hardware (base + override)
                base_hw = base.get("hardware", {})
                data_hw = data.get("hardware", {})
                return {**base_hw, **data_hw}
            except Exception:
                pass

    return data.get("hardware", {})


def match_profile(det: dict) -> str:
    """Busca un perfil TOML que coincida con el hardware detectado.

    Devuelve el nombre de perfil (ej: 'raspi/4b') o cadena vacía si no hay match.
    Estrategia:
      1. Match exacto de product (ej: "Raspberry Pi 4 Model B")
      2. Match parcial de cpu_model + arch
    """
    if not TEMPLATES_DIR.is_dir():
        return ""

    candidates: list[tuple[str, dict]] = []
    for toml_file in sorted(TEMPLATES_DIR.rglob("build.toml")):
        rel = toml_file.relative_to(TEMPLATES_DIR)
        profile_name = str(rel.parent).replace("/", "/")
        # Ya es relativo tipo "raspi/4b"
        profile_name = "/".join(rel.parts[:-1])  # sin "build.toml"
        hw = _load_toml_profile(toml_file)
        if hw:
            candidates.append((profile_name, hw))

    detected_product = det.get("product", "")
    detected_model = det.get("cpu_model", "")
    detected_arch = det.get("arch", "")

    # Fase 1: match exacto por product
    for name, hw in candidates:
        if hw.get("product") and detected_product:
            if hw["product"].lower() in detected_product.lower() or detected_product.lower() in hw["product"].lower():
                return name

    # Fase 2: match por cpu_model + arch
    for name, hw in candidates:
        hw_arch = hw.get("cpu_arch", "")
        hw_model = hw.get("cpu_model", "")
        if hw_arch and detected_arch and hw_arch == detected_arch:
            if hw_model and detected_model:
                if hw_model.lower() in detected_model.lower() or detected_model.lower() in hw_model.lower():
                    return name

    return ""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detección inteligente de hardware para compile-auto"
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Emitir detección como JSON",
    )
    parser.add_argument(
        "--flags",
        action="store_true",
        help="Emitir flags cmake para el hardware actual",
    )
    parser.add_argument(
        "--match",
        action="store_true",
        help="Emitir nombre de perfil TOML si hay coincidencia",
    )
    parser.add_argument(
        "--jobs",
        action="store_true",
        help="Emitir número de jobs recomendado",
    )
    args = parser.parse_args()

    det = detect()

    if args.info:
        print(json.dumps(det, indent=2, ensure_ascii=False))
    elif args.flags:
        print(cmake_flags_from_detection(det))
    elif args.match:
        matched = match_profile(det)
        if matched:
            print(matched)
    elif args.jobs:
        jobs = det.get("logical_cpus", 1)
        print(jobs)
    else:
        # Sin flag → --info por defecto
        print(json.dumps(det, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
