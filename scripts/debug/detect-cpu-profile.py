#!/usr/bin/env python3
"""
detect-cpu-profile.py — Detecta CPU en Linux y genera perfiles build.toml

Analiza /proc/cpuinfo, /proc/meminfo y genera:
  1. Perfil base de CPU   — cpu/<vendor>/<arch>.toml  (flags SIMD + compilador)
  2. Perfil de hardware   — <vendor>/<device>/build.toml (hereda del perfil CPU)

Funciona sin dependencias externas (solo stdlib de Python).

Uso:
  python3 scripts/debug/detect-cpu-profile.py
  python3 scripts/debug/detect-cpu-profile.py --device "Dell Optiplex 7010"
  python3 scripts/debug/detect-cpu-profile.py --vendor dell --product "optiplex-7010"
  python3 scripts/debug/detect-cpu-profile.py --cpu-only
  python3 scripts/debug/detect-cpu-profile.py --json
  python3 scripts/debug/detect-cpu-profile.py --from-template TEMPLATE.toml
  python3 scripts/debug/detect-cpu-profile.py --from-template mi-equipo.toml --output-dir build/templates
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple, Dict, List

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        sys.exit("[ERROR] Se requiere Python 3.11+ o: pip install tomli")

COLORS = {
    "reset":  "\033[0m",
    "bold":   "\033[1m",
    "green":  "\033[32m",
    "yellow": "\033[33m",
    "cyan":   "\033[36m",
    "red":    "\033[31m",
    "dim":    "\033[2m",
    "blue":   "\033[34m",
}

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "build" / "templates"

# ==============================================================================
# Utilidades
# ==============================================================================

def c(color: str, text: str) -> str:
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def read_file(path: str) -> str:
    try:
        with open(path) as f:
            return f.read()
    except (FileNotFoundError, PermissionError):
        return ""


def run_cmd(cmd: list[str], timeout: int = 10) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
        return ""


# ==============================================================================
# Detección de CPU
# ==============================================================================

def detect_vendor(cpuinfo: str) -> str:
    m = re.search(r"vendor_id\s*:\s*(.+)", cpuinfo)
    if m:
        vid = m.group(1).strip()
        if "GenuineIntel" in vid:
            return "intel"
        if "AuthenticAMD" in vid:
            return "amd"
        return vid.lower()
    # ARM: /proc/cpuinfo no tiene vendor_id, usamos CPU implementer
    m = re.search(r"CPU implementer\s*:\s*(0x[0-9a-fA-F]+)", cpuinfo)
    if m:
        return "arm"
    return "unknown"


def detect_model_name(cpuinfo: str) -> str:
    m = re.search(r"model name\s*:\s*(.+)", cpuinfo)
    if m:
        return re.sub(r"\s+", " ", m.group(1).strip())
    return "unknown"


def detect_architecture() -> str:
    return os.uname().machine


def detect_cores(cpuinfo: str) -> Tuple[int, int]:
    threads = len(re.findall(r"^processor\s*:", cpuinfo, re.MULTILINE))
    cores_match = re.findall(r"cpu cores\s*:\s*(\d+)", cpuinfo)
    physical = int(cores_match[0]) if cores_match else max(threads, 1)
    return physical, threads


def get_cpu_flags(cpuinfo: str) -> str:
    m = re.search(r"^flags\s*:\s*(.+)", cpuinfo, re.MULTILINE)
    if m:
        return m.group(1).strip()
    # ARM: usa Features en lugar de flags
    m = re.search(r"^Features\s*:\s*(.+)", cpuinfo, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return ""


def detect_os() -> str:
    return "darwin" if sys.platform == "darwin" else "linux"


# ==============================================================================
# ARM — decodificador de CPU part
# ==============================================================================

ARM_PARTS: Dict[str, str] = {
    "0xd03": "Cortex-A53",  "0xd04": "Cortex-A35",
    "0xd05": "Cortex-A55",  "0xd07": "Cortex-A57",
    "0xd08": "Cortex-A72",  "0xd09": "Cortex-A73",
    "0xd0a": "Cortex-A75",  "0xd0b": "Cortex-A76",
    "0xd0c": "Neoverse N1", "0xd0d": "Cortex-A77",
    "0xd0e": "Cortex-A78",  "0xd41": "Cortex-A78",
    "0xd44": "Cortex-X1",   "0xd46": "Cortex-A510",
    "0xd47": "Cortex-A715", "0xd48": "Cortex-X2",
    "0xd49": "Neoverse N2", "0xd4c": "Cortex-X3",
    "0xd4d": "Cortex-A720", "0xd4e": "Cortex-X4",
    "0xd0f": "Cortex-A710",
}

ARM_IMPLEMENTERS: Dict[str, str] = {
    "0x41": "ARM Ltd.",
    "0x42": "Broadcom",
    "0x43": "Cavium",
    "0x48": "HiSilicon",
    "0x4e": "NVIDIA",
    "0x50": "Applied Micro",
    "0x51": "Qualcomm",
    "0x53": "Samsung",
    "0x56": "Marvell",
    "0x61": "Apple",
    "0x69": "Intel",
    "0xc0": "Ampere",
}


def decode_arm_cpu(cpuinfo: str) -> str:
    """Devuelve nombre legible del core ARM, o 'unknown'."""
    m_impl = re.search(r"CPU implementer\s*:\s*(0x[0-9a-fA-F]+)", cpuinfo)
    m_part = re.search(r"CPU part\s*:\s*(0x[0-9a-fA-F]+)", cpuinfo)
    if m_part:
        part = m_part.group(1).lower()
        if part in ARM_PARTS:
            return ARM_PARTS[part]
    return "unknown"


def get_arm_implementer_name(cpuinfo: str) -> Optional[str]:
    m = re.search(r"CPU implementer\s*:\s*(0x[0-9a-fA-F]+)", cpuinfo)
    if m:
        return ARM_IMPLEMENTERS.get(m.group(1).lower())
    return None


# ==============================================================================
# Mapeo de flags → GGML cmake options
# ==============================================================================

FLAG_TO_GGML: Dict[str, str] = {
    "avx":     "GGML_AVX",
    "avx2":    "GGML_AVX2",
    "f16c":    "GGML_F16C",
    "fma":     "GGML_FMA",
    "bmi2":    "GGML_BMI2",
}

ARM_FEAT_TO_GGML: Dict[str, str] = {
    "asimd": "GGML_NEON",
    "neon":  "GGML_NEON",
    "sve":   "GGML_SVE",
}

# ==============================================================================
# Detección de march/mtune vía gcc
# ==============================================================================

def gcc_detect_march() -> Optional[str]:
    """Usa gcc -march=native para detectar la microarquitectura."""
    if not shutil.which("gcc"):
        return None
    out = run_cmd(["gcc", "-march=native", "-Q", "--help=target"], timeout=15)
    m = re.search(r"^\s*-march=\s+(\S+)", out, re.MULTILINE)
    return m.group(1) if m else None


def gcc_version() -> Optional[str]:
    if not shutil.which("gcc"):
        return None
    out = run_cmd(["gcc", "--version"], timeout=5)
    m = re.search(r"(\d+\.\d+\.\d+)", out)
    return m.group(1) if m else None


# ==============================================================================
# Heurísticas de microarquitectura (fallback sin gcc)
# ==============================================================================

def guess_march_intel(flags_set: set[str], model: str) -> Tuple[str, str, str]:
    """
    A partir de flags y modelo, devuelve (march, mtune, generation_label).
    Usa las microarquitecturas soportadas por GCC 12+.
    """
    march = "x86-64"
    label = "x86-64 baseline"

    # Detección por número de modelo Intel (iX-Nxxx)
    model_gen = [
        (r"i[3579]-14\d{3}", "raptorlake",    "Raptor Lake Refresh (14th gen)"),
        (r"i[3579]-13\d{3}", "raptorlake",    "Raptor Lake (13th gen)"),
        (r"i[3579]-12\d{3}", "alderlake",     "Alder Lake (12th gen)"),
        (r"i[3579]-11\d{2}", "tigerlake",     "Tiger Lake / Rocket Lake (11th gen)"),
        (r"i[3579]-10\d{2}", "icelake-client","Ice Lake / Comet Lake (10th gen)"),
        (r"i[3579]-9\d{2}",  "skylake",       "Coffee Lake Refresh (9th gen)"),
        (r"i[3579]-8\d{3}",  "skylake",       "Coffee Lake (8th gen)"),
        (r"i[3579]-7\d{3}",  "skylake",       "Kaby Lake (7th gen)"),
        (r"i[3579]-6\d{3}",  "skylake",       "Skylake (6th gen)"),
        (r"i[3579]-5\d{3}",  "broadwell",     "Broadwell (5th gen)"),
        (r"i[3579]-4\d{3}",  "haswell",       "Haswell (4th gen)"),
        (r"i[3579]-3\d{3}",  "ivybridge",     "Ivy Bridge (3rd gen)"),
        (r"i[3579]-2\d{3}",  "sandybridge",   "Sandy Bridge (2nd gen)"),
    ]
    for pattern, gcc_march, gen_label in model_gen:
        if re.search(pattern, model, re.IGNORECASE):
            march = gcc_march
            label = gen_label
            break
    else:
        # Fallback: detectar por flags
        arch_order = [
            ("avx512f",   "sapphirerapids",   "Sapphire Rapids+"),
            ("avx512f",   "skylake-avx512",   "Skylake-X/SP"),
            ("avx2",      "haswell",          "Haswell/Broadwell"),
            ("avx",       "ivybridge",        "Ivy Bridge / Sandy Bridge"),
            ("sse4_2",    "nehalem",          "Nehalem/Westmere"),
            ("sse4_1",    "core2",            "Core 2/Penryn"),
        ]
        for flag, gcc_march, gen_label in arch_order:
            if flag in flags_set:
                march = gcc_march
                label = gen_label
                break

    # Refinar con keywords textuales para CPUs sin número en el modelo
    text_hints = [
        (r"13th|14th|raptor\s*lake",            "raptorlake",    "Raptor Lake"),
        (r"12th|alder\s*lake",                  "alderlake",     "Alder Lake"),
        (r"11th|tiger\s*lake|rocket\s*lake",    "tigerlake",     "Tiger Lake / Rocket Lake"),
        (r"10th|ice\s*lake|comet\s*lake",       "icelake-client","Ice Lake / Comet Lake"),
        (r"coffee\s*lake",                      "skylake",       "Coffee Lake"),
        (r"kaby\s*lake",                        "skylake",       "Kaby Lake"),
        (r"skylake",                            "skylake",       "Skylake"),
        (r"broadwell",                          "broadwell",     "Broadwell"),
        (r"haswell",                            "haswell",       "Haswell"),
        (r"ivy\s*bridge",                       "ivybridge",     "Ivy Bridge"),
        (r"sandy\s*bridge",                     "sandybridge",   "Sandy Bridge"),
        (r"silvermont|bay\s*trail|braswell",    "silvermont",    "Silvermont / Atom"),
        (r"goldmont",                           "goldmont",      "Goldmont / Atom"),
    ]
    for pattern, gcc_march, gen_label in text_hints:
        if re.search(pattern, model, re.IGNORECASE) and label == "x86-64 baseline":
            march = gcc_march
            label = gen_label
            break

    return march, march, label


def guess_march_amd(flags_set: set[str], model: str) -> Tuple[str, str, str]:
    if "avx512f" in flags_set:
        return "znver4", "znver4", "Zen 4 / Zen 5"
    if "avx2" in flags_set:
        if "bmi2" in flags_set:
            return "znver3", "znver3", "Zen 3"
        return "znver2", "znver2", "Zen 2"
    if "avx" in flags_set:
        return "znver1", "znver1", "Zen 1"
    return "btver2", "btver2", "Bulldozer/Piledriver"


def guess_march_arm(flags_set: set[str], cpu_part_name: str, arch: str) -> Tuple[str, str, str]:
    isa = "armv8-a"
    march = "armv8-a"
    label = "ARMv8-A"

    if "sve" in flags_set:
        isa = "armv8.2-a"
        march = "armv8.2-a"
        label = "ARMv8.2-A+ (SVE)"

    core_isa_map = {
        "Cortex-A55": ("armv8.2-a", "ARMv8.2-A"),
        "Cortex-A75": ("armv8.2-a", "ARMv8.2-A"),
        "Cortex-A76": ("armv8.2-a", "ARMv8.2-A"),
        "Cortex-A77": ("armv8.2-a", "ARMv8.2-A"),
        "Cortex-A78": ("armv8.2-a", "ARMv8.2-A"),
        "Cortex-X1":  ("armv8.2-a", "ARMv8.2-A"),
        "Cortex-A710": ("armv9-a",   "ARMv9-A"),
        "Cortex-A715": ("armv9-a",   "ARMv9-A"),
        "Cortex-X2":   ("armv9-a",   "ARMv9-A"),
        "Cortex-X3":   ("armv9-a",   "ARMv9-A"),
        "Cortex-X4":   ("armv9.2-a", "ARMv9.2-A"),
        "Cortex-A510": ("armv9-a",   "ARMv9-A"),
        "Cortex-A720": ("armv9-a",   "ARMv9-A"),
        "Neoverse N1": ("armv8.2-a", "ARMv8.2-A"),
        "Neoverse N2": ("armv9-a",   "ARMv9-A"),
    }

    if cpu_part_name in core_isa_map:
        isa, label = core_isa_map[cpu_part_name]
        march = isa

    # Añadir crc si disponible
    if "crc32" in flags_set and "crc" not in march:
        march += "+crc"

    return march, cpu_part_name.lower().replace(" ", "-"), label


# ==============================================================================
# Detección de RAM
# ==============================================================================

def detect_ram_gb() -> float:
    content = read_file("/proc/meminfo")
    m = re.search(r"MemTotal:\s+(\d+)", content)
    if m:
        return round(int(m.group(1)) / (1024 * 1024), 1)
    return 0.0


# ==============================================================================
# Detección de GPU (informativo)
# ==============================================================================

def detect_gpu() -> Optional[str]:
    if shutil.which("nvidia-smi"):
        out = run_cmd(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], timeout=5)
        if out:
            return f"NVIDIA {out.splitlines()[0].strip()}"
    if shutil.which("lspci"):
        out = run_cmd(["lspci"], timeout=5)
        for line in out.splitlines():
            if any(k in line.upper() for k in ("VGA", "3D CONTROLLER", "DISPLAY")):
                m = re.search(r":\s+(.+)", line)
                if m:
                    return m.group(1).strip()
    return None


# ==============================================================================
# Generación de TOML
# ==============================================================================

def gen_cflags(flags_set: set[str], vendor: str) -> str:
    """Genera los cflags apropiados según las extensiones detectadas."""
    base = "-O3 -ffast-math -fno-finite-math-only"

    if vendor in ("intel", "amd"):
        # Si tiene AVX pero no FMA ni BMI2 → defensa en profundidad (ADR-005)
        if "avx" in flags_set and "fma" not in flags_set and "bmi2" not in flags_set:
            return base + " -mno-avx -mno-avx2 -mno-fma -mno-f16c -mno-bmi -mno-bmi2"
        if "avx" in flags_set and "bmi2" not in flags_set:
            return base + " -mno-bmi -mno-bmi2"

    return base


def gen_simd_section(vendor: str, flags_set: set[str]) -> str:
    """Genera la sección [cpu] con extensiones SIMD booleanas."""
    if vendor in ("intel", "amd"):
        # Mapeo flag cpuinfo → nombre interno
        flag_map = {
            "sse41":  ("sse4_1",  "SSE4.1"),
            "sse42":  ("sse4_2",  "SSE4.2"),
            "avx":    ("avx",     "AVX"),
            "avx2":   ("avx2",    "AVX2"),
            "f16c":   ("f16c",    "F16C"),
            "fma3":   ("fma",     "FMA3"),
            "bmi1":   ("bmi1",    "BMI1"),
            "bmi2":   ("bmi2",    "BMI2"),
            "avx512": ("avx512f", "AVX-512"),
        }
        lines = []
        for key, (cpu_flag, name) in flag_map.items():
            has = cpu_flag in flags_set
            lines.append(f"{key:<7} = {str(has).lower():<5}  # {name}")
        return "\n".join(lines)

    elif vendor == "arm":
        return (
            f"asimd        = {str('asimd' in flags_set or 'neon' in flags_set).lower():<5}  # NEON / Advanced SIMD\n"
            f"crc32        = {str('crc32' in flags_set).lower():<5}  # CRC32 por hardware\n"
            f"fp32         = true   # FP32 escalar (ARMv8-A baseline)\n"
            f"fp64         = true   # FP64 escalar\n"
            f"sve          = {str('sve' in flags_set).lower():<5}  # Scalable Vector Extension\n"
            f"fp16_compute = {str('asimdhp' in flags_set).lower():<5}  # FP16 vectorial (fphp+asimdhp)"
        )

    return ""


def gen_ggml_flags(vendor: str, flags_set: set[str], march: str) -> str:
    """Genera flags GGML cmake según las extensiones detectadas."""
    flags = {}

    if vendor in ("intel", "amd"):
        flag_pairs = [
            ("avx",    "GGML_AVX"),
            ("avx2",   "GGML_AVX2"),
            ("f16c",   "GGML_F16C"),
            ("fma",    "GGML_FMA"),
            ("bmi2",   "GGML_BMI2"),
        ]
        for cpu_flag, ggml_flag in flag_pairs:
            present = cpu_flag in flags_set
            # ivybridge-like: tiene avx pero no fma/bmi2
            if cpu_flag == "avx" and present and "fma" not in flags_set:
                # Caso especial: AVX sin FMA/BMI2 (ADR-005)
                pass  # se maneja con GGML_AVX=OFF y -mno-*
            flags[ggml_flag] = "ON" if present else "OFF"

        # Si AVX está presente pero sin FMA ni BMI2, forzar OFF
        if flags.get("GGML_AVX") == "ON" and flags.get("GGML_FMA") == "OFF":
            flags["GGML_AVX"] = "OFF"

    elif vendor == "arm":
        flags["GGML_NEON"] = "ON" if ("asimd" in flags_set or "neon" in flags_set) else "OFF"
        flags["GGML_SVE"]  = "ON" if ("sve" in flags_set) else "OFF"

    flags["GGML_NATIVE"] = "OFF"

    lines = []
    for key in sorted(flags.keys()):
        lines.append(f'{key:<18} = "{flags[key]}"')

    return "\n".join(lines)


def gen_cpu_profile(
    vendor: str, arch_name: str, model_name: str,
    flags_set: set[str], march: str, mtune: str, gen_label: str,
    cpu_part_name: str = "",
) -> str:
    """Genera el contenido de un perfil CPU (cpu/<vendor>/<arch>.toml)."""
    cflags_str = gen_cflags(flags_set, vendor)
    simd_block = gen_simd_section(vendor, flags_set)
    ggml_block = gen_ggml_flags(vendor, flags_set, march)

    name = f"{vendor.capitalize()} {gen_label}"
    if vendor == "arm" and cpu_part_name:
        name = f"ARM {cpu_part_name}"

    # Solo flags SIMD y extensiones relevantes (no flags de sistema como fpu, vme, etc.)
    simd_relevant = {
        "mmx", "sse", "sse2", "sse3", "ssse3", "sse4_1", "sse4_2",
        "avx", "avx2", "avx512f", "avx512bw", "avx512cd", "avx512vl", "avx512dq",
        "f16c", "fma", "bmi1", "bmi2", "aes", "pclmulqdq", "rdrand", "rdseed",
        "neon", "asimd", "sve", "crc32", "asimdhp", "fphp",
    }
    ext_str = ", ".join(sorted(f for f in flags_set if f in simd_relevant))

    return f"""\
# =============================================================================
# Perfil de CPU: {name}
# Generado automáticamente por detect-cpu-profile.py
#
# CPU detectada:  {model_name}
# Arquitectura:   {march}
# Extensiones:     {ext_str}

# =============================================================================
# =============================================================================

[cpu]
name    = "{name}"
vendor  = "{vendor}"
arch    = "{arch_name}"
{f'gen     = ""' if vendor in ('intel','amd') else ''}
# Extensiones SIMD soportadas
{simd_block}

# Extensiones NO soportadas — verificar con /proc/cpuinfo antes de activar
# (añadir aquí las que faltan respecto a generaciones posteriores)

# =============================================================================
# Configuración del compilador
# =============================================================================

[compiler]
march  = "{march}"
mtune  = "{mtune}"
cflags = "{cflags_str}"

# =============================================================================
# Flags cmake de extensiones CPU para ggml
# =============================================================================

[cmake.flags]
# Las opciones GGML_* controlan qué código SIMD compila ggml.
# ggml usa target_compile_options() que pisa CMAKE_C_FLAGS.
# Ver docs/architecture/decisions.md ADR-005.
{ggml_block}
""".replace("gen     = \"\"\n", "")


def gen_hw_profile(
    vendor: str, arch_name: str, cpu_model: str,
    device_vendor: str, device_product: str,
    physical_cores: int, logical_cpus: int,
    os_name: str, ram_gb: float,
    gpu_info: Optional[str],
    inherits_path: str,
) -> str:
    """Genera el contenido de un perfil de hardware (<vendor>/<device>/build.toml)."""
    jobs = max(logical_cpus, 1)

    ram_note = ""
    if ram_gb > 0:
        ram_note = f"\n# RAM detectada:  {ram_gb} GB"
        if ram_gb < 4:
            ram_note += "\n#   → Considerar jobs=2 para evitar OOM durante compilación"
        if ram_gb < 2:
            ram_note += "\n#   → jobs=1 y añadir swap (sudo dphys-swapfile)"

    gpu_note = f"\n# GPU detectada:   {gpu_info}" if gpu_info else ""
    metal_line = "" if os_name == "darwin" else '\nGGML_METAL           = "OFF"   # Solo disponible en Apple Silicon / macOS'

    return f"""\
# =============================================================================
# Perfil de compilación: {device_vendor} {device_product}
# Generado automáticamente por detect-cpu-profile.py
#
# Hardware identificado con:
{f'#   uname -a    → {os.uname().sysname} {os.uname().release} {os.uname().machine}'}
{f'#   /proc/cpuinfo → {cpu_model}'}
{f'#   lscpu / nproc  → {physical_cores} núcleos físicos, {logical_cpus} hilos lógicos'}
{ram_note}{gpu_note}
#
# La configuración del procesador (march, mtune, cflags, GGML_*) se hereda de:
#   build/templates/{inherits_path}.toml
#
# Este archivo solo contiene lo específico del equipo:
#   hardware, jobs, dependencias y flags de hardware (BLAS, CUDA, METAL...).
# =============================================================================

inherits = "{inherits_path}"

[hardware]
manufacturer   = "{device_vendor}"
product        = "{device_product}"
cpu_model      = "{cpu_model}"
cpu_arch       = "{arch_name}"
logical_cpus   = {logical_cpus}
physical_cores = {physical_cores}
os             = "{os_name}"

[build]
jobs      = {jobs}
type      = "Release"
generator = "Unix Makefiles"

[dependencies]
# Binarios verificados con `command -v`
commands = ["git", "cmake", "gcc", "g++", "pkg-config"]
# Librerías verificadas con `pkg-config --exists`
pkg_config = ["openblas", "openssl"]
# Paquetes sugeridos para instalar (solo referencia, no se instalan automáticamente)
apt_packages = [
  "build-essential",
  "cmake",
  "git",
  "libopenblas-dev",
  "libssl-dev",
  "pkg-config",
]

# Flags cmake específicos del hardware.
# Los flags de CPU (GGML_AVX, GGML_NEON, compiler.*) vienen del perfil CPU.
[cmake.flags]
BUILD_SHARED_LIBS    = "OFF"
GGML_BLAS            = "ON"
GGML_BLAS_VENDOR     = "OpenBLAS"{metal_line}
LLAMA_BUILD_TESTS    = "OFF"
LLAMA_BUILD_EXAMPLES = "ON"
"""


def sanitize_filename(s: str) -> str:
    return re.sub(r"[^a-z0-9\-_.]", "-", s.lower().strip()).strip("-")


# ==============================================================================
# Salida JSON para consumo por scripts
# ==============================================================================

def json_output(
    vendor: str, arch_name: str, model_name: str,
    flags_set: set[str], march: str, mtune: str, gen_label: str,
    physical_cores: int, logical_cpus: int, ram_gb: float,
    gpu: Optional[str], os_name: str,
    cpu_part_name: str = "",
) -> None:
    import json
    data = {
        "vendor": vendor,
        "model_name": model_name,
        "architecture": march,
        "generation": gen_label,
        "cores": {"physical": physical_cores, "logical": logical_cpus},
        "ram_gb": ram_gb,
        "os": os_name,
        "gpu": gpu,
        "flags": sorted(flags_set),
        "cpu_part": cpu_part_name or None,
        "ggml_options": {},
        "march": march,
        "mtune": mtune,
    }

    if vendor in ("intel", "amd"):
        for f, g in FLAG_TO_GGML.items():
            data["ggml_options"][g] = f in flags_set
    elif vendor == "arm":
        for g, check_flags in [("GGML_NEON", ("asimd", "neon")), ("GGML_SVE", ("sve",))]:
            data["ggml_options"][g] = any(f in flags_set for f in check_flags)

    data["ggml_options"]["GGML_NATIVE"] = False
    print(json.dumps(data, indent=2))


# ==============================================================================
# Presentación en terminal
# ==============================================================================

def print_hardware_summary(
    vendor: str, gen_label: str, model_name: str, cpu_part_name: str,
    march: str, mtune: str,
    physical_cores: int, logical_cpus: int, ram_gb: float,
    gpu: Optional[str], flags_set: set[str],
    gcc_ver: Optional[str],
) -> None:
    print(c("bold", "\n  PoC-Llama.cpp — Detección de CPU y generación de perfil"))
    print(f"  {'─' * 65}")

    print(f"  {c('cyan', 'CPU   ')}  {model_name}")
    if cpu_part_name != "unknown" and cpu_part_name:
        print(f"  {c('cyan', 'Core  ')}  {cpu_part_name}")

    print(f"  {c('cyan', 'Gen   ')}  {gen_label}")
    print(f"  {c('cyan', '      ')}  {physical_cores} núcleos físicos  /  {logical_cpus} hilos lógicos")

    if gcc_ver:
        print(f"  {c('cyan', 'march ')}  {march}  (mtune={mtune})  detectado por gcc {gcc_ver}")
    else:
        print(f"  {c('cyan', 'march ')}  {march}  (mtune={mtune})  estimado (gcc no encontrado)")

    if ram_gb > 0:
        print(f"  {c('cyan', 'RAM   ')}  {ram_gb} GB")

    if gpu:
        print(f"  {c('cyan', 'GPU   ')}  {gpu}")

    # Extensiones relevantes
    relevant = sorted(f for f in flags_set if f in (
        "sse4_1", "sse4_2", "avx", "avx2", "f16c", "fma", "bmi1", "bmi2",
        "avx512f", "avx512bw", "avx512cd", "avx512vl", "avx512dq",
        "asimd", "neon", "sve", "crc32", "asimdhp", "fphp",
    ))
    if relevant:
        flags_str = " ".join(relevant)
        print(f"  {c('cyan', 'Flags ')}  {c('dim', flags_str)}")

    print()


def print_ggml_table(vendor: str, flags_set: set[str], march: str) -> None:
    print(c("bold", "  Flags GGML sugeridos para cmake:"))
    print(f"  {'─' * 45}")

    if vendor in ("intel", "amd"):
        for cpu_flag, ggml_flag in sorted(FLAG_TO_GGML.items()):
            present = cpu_flag in flags_set
            status = c("green", f"ON ") if present else c("dim", f"OFF")
            print(f"  {ggml_flag:<18} = {status}")
        print(f"  {'GGML_NATIVE':<18} = {c('dim', 'OFF')}")
    elif vendor == "arm":
        for ggml_flag, check_flags in [("GGML_NEON", ("asimd", "neon")), ("GGML_SVE", ("sve",))]:
            present = any(f in flags_set for f in check_flags)
            status = c("green", f"ON ") if present else c("dim", f"OFF")
            print(f"  {ggml_flag:<18} = {status}")
        print(f"  {'GGML_NATIVE':<18} = {c('dim', 'OFF')}")


def print_adr005_warning(flags_set: set[str]) -> None:
    """Si es Ivy Bridge-like, mostrar advertencia."""
    if "avx" in flags_set and "fma" not in flags_set and "bmi2" not in flags_set:
        print()
        print(c("yellow",
            "  ⚠️  ADR-005: Esta CPU tiene AVX pero NO tiene FMA3 ni BMI2."))
        print(c("yellow",
            "     Es necesario desactivar GGML_AVX=OFF, GGML_BMI2=OFF, GGML_FMA=OFF"))
        print(c("yellow",
            "     y añadir -mno-avx -mno-bmi -mno-bmi2 en cflags."))
        print(c("dim",
            "     Ver docs/architecture/decisions.md ADR-005 para más detalles."))


def find_existing_cpu_profile(cpu_arch: str, vendor: str) -> Optional[Path]:
    """Busca si ya existe un perfil CPU con el mismo arch."""
    if vendor in ("intel", "amd"):
        cpu_dir = TEMPLATES_DIR / "cpu" / (vendor if vendor == "intel" else "amd")
    else:
        cpu_dir = TEMPLATES_DIR / "cpu" / vendor
    if cpu_dir.exists():
        for f in cpu_dir.glob("*.toml"):
            return f
    return None


# ==============================================================================
# Modo interactivo
# ==============================================================================

def prompt(prompt_text: str, default: str = "") -> str:
    try:
        val = input(f"  {c('bold', prompt_text)}").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)
    return val if val else default


def interactive_device_info(cpu_model: str, vendor: str) -> Tuple[str, str]:
    """Pregunta al usuario los datos del dispositivo."""
    print(c("bold", f"\n  Datos del equipo — necesarios para el perfil de hardware"))
    print(f"  {'─' * 55}")

    # Sugerir fabricante a partir del vendor de CPU
    vendor_hints = {
        "intel": "Ej: Dell Inc., Lenovo, HP, Apple Inc., ASUS, Gigabyte",
        "amd":   "Ej: Dell Inc., Lenovo, HP, ASUS, Gigabyte, Framework",
        "arm":   "Ej: Raspberry Pi Foundation, Orange Pi, Rockchip, NVIDIA",
    }
    hint = vendor_hints.get(vendor, "Ej: Dell Inc., Lenovo, Raspberry Pi Foundation")

    print(f"  {c('dim', hint)}")
    manufacturer = prompt("Fabricante (manufacturer): ")
    if not manufacturer:
        manufacturer = "Unknown"

    print(f"\n  {c('dim', f'Ej: Optiplex 7010, ThinkPad T480, Macmini6.2, Raspberry Pi 4 Model B')}")
    product = prompt("Modelo (product): ")
    if not product:
        product = "unknown-device"

    return manufacturer, product


# ==============================================================================
# Main
# ==============================================================================

def load_template_toml(path: str) -> dict:
    """Carga y valida un archivo TEMPLATE.toml rellenado por el usuario."""
    p = Path(path)
    if not p.exists():
        print(c("red", f"[ERROR] Archivo no encontrado: {path}"))
        sys.exit(1)
    with open(p, "rb") as f:
        return tomllib.load(f)


def template_flags_to_set(template: dict) -> Tuple[set[str], str]:
    """
    Convierte la sección [cpu.simd] del template a un flags_set.
    Devuelve (flags_set, cpu_vendor).
    """
    cpu_vendor = template.get("cpu", {}).get("vendor", "").strip()
    simd = template.get("cpu", {}).get("simd", {})

    flags: set[str] = set()
    simd_map = {
        "sse41":  "sse4_1",  "sse42":  "sse4_2",
        "avx":    "avx",     "avx2":   "avx2",
        "f16c":   "f16c",    "fma":    "fma",
        "bmi1":   "bmi1",    "bmi2":   "bmi2",
        "avx512": "avx512f",
    }

    # x86: mapear las claves del template a nombres de flag de /proc/cpuinfo
    for tkey, fkey in simd_map.items():
        val = simd.get(tkey)
        if val is True or (isinstance(val, str) and val.lower() == "true"):
            flags.add(fkey)

    # ARM: neon → asimd (el nombre real en /proc/cpuinfo Features)
    arm_map = {
        "neon":  "asimd",
        "sve":   "sve",
        "crc32": "crc32",
    }
    if cpu_vendor == "arm":
        for tkey, fkey in arm_map.items():
            val = simd.get(tkey)
            if val is True or (isinstance(val, str) and val.lower() == "true"):
                flags.add(fkey)

    # Si neon está activo, añadir también "neon" para compatibilidad
    if "asimd" in flags:
        flags.add("neon")

    return flags, cpu_vendor


def template_to_cpu_arch(template: dict, flags_set: set[str], cpu_vendor: str, model_name: str) -> Tuple[str, str, str, str]:
    """
    Determina march, mtune, gen_label, arch_name desde el template.
    Prioriza cpu_arch si el usuario lo proporcionó.
    """
    user_arch = template.get("cpu", {}).get("arch", "").strip()

    if cpu_vendor in ("intel", "amd"):
        if cpu_vendor == "intel":
            march, mtune, gen_label = guess_march_intel(flags_set, model_name)
        else:
            march, mtune, gen_label = guess_march_amd(flags_set, model_name)
        arch_name = user_arch if user_arch else march
    elif cpu_vendor == "arm":
        march, mtune, gen_label = guess_march_arm(flags_set, "", "")
        arch_name = user_arch if user_arch else (
            model_name.lower().replace(" ", "-").replace("arm-", "")
        )
    else:
        march = mtune = gen_label = "unknown"
        arch_name = user_arch or "unknown"

    return march, mtune, gen_label, arch_name


def template_to_hardware(template: dict) -> dict:
    """Extrae los datos de hardware del template, con valores por defecto."""
    hw = template.get("hardware", {})
    build = template.get("build", {})
    return {
        "manufacturer":   hw.get("manufacturer", "unknown").strip() or "unknown",
        "product":        hw.get("product", "unknown-device").strip() or "unknown-device",
        "cpu_model":      hw.get("cpu_model", "unknown").strip() or "unknown",
        "logical_cpus":   int(hw.get("logical_cpus", 1) or 1),
        "physical_cores": int(hw.get("physical_cores", 1) or 1),
        "os":             hw.get("os", "linux").strip() or "linux",
        "jobs":           int(build.get("jobs", 1) or 1),
        "ram_gb":         float(template.get("ram_gb", 0) or 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detecta CPU en Linux y genera perfiles build.toml para llama.cpp."
    )
    parser.add_argument(
        "--device", help="Nombre del dispositivo (ej: 'Dell Optiplex 7010')",
    )
    parser.add_argument(
        "--vendor", help="Fabricante del equipo (ej: dell, lenovo, apple)",
    )
    parser.add_argument(
        "--product", help="Modelo del equipo (ej: optiplex-7010, thinkpad-t480)",
    )
    parser.add_argument(
        "--cpu-only", action="store_true",
        help="Generar solo perfil de CPU (sin perfil de hardware)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Salida JSON para consumo por scripts",
    )
    parser.add_argument(
        "--from-template", metavar="TEMPLATE.toml",
        help="Leer un TEMPLATE.toml rellenado y generar perfiles completos (no requiere /proc/cpuinfo)",
    )
    parser.add_argument(
        "--output-dir", help="Directorio donde escribir los archivos TOML (default: stdout)",
    )
    args = parser.parse_args()

    # ── Modo --from-template ──────────────────────────────────────────────
    if args.from_template:
        template = load_template_toml(args.from_template)
        flags_set, cpu_vendor = template_flags_to_set(template)
        hw              = template_to_hardware(template)
        model_name      = hw["cpu_model"]
        vendor          = cpu_vendor
        vendor_dir      = vendor
        phys            = hw["physical_cores"]
        logi            = hw["logical_cpus"]
        ram_gb          = hw["ram_gb"]
        os_name         = hw["os"]
        gpu             = None
        cpu_part_name   = ""
        gcc_ver         = None
        device_vendor   = hw["manufacturer"]
        device_product  = hw["product"]
        march, mtune, gen_label, arch_name = template_to_cpu_arch(
            template, flags_set, cpu_vendor, model_name,
        )

        # Si el template viene sin cores, usar valores razonables
        if logi < 1:
            logi = 4
        if phys < 1:
            phys = logi

        # El usuario no proporcionó vendor → saltar modo interactivo
        if args.vendor:
            device_vendor = args.vendor
        if args.product:
            device_product = args.product

    else:
        # ── Modo detección normal (requiere /proc/cpuinfo) ────────────────
        cpuinfo = read_file("/proc/cpuinfo")
        if not cpuinfo:
            print(c("red", "[ERROR] No se pudo leer /proc/cpuinfo. ¿Es un sistema Linux?"))
            print(c("dim",  "[INFO] Usa --from-template TEMPLATE.toml para generar perfiles sin acceso al equipo."))
            sys.exit(1)

        # 2. Detectar todo
        vendor        = detect_vendor(cpuinfo)
        model_name    = detect_model_name(cpuinfo)
        arch          = detect_architecture()
        phys, logi    = detect_cores(cpuinfo)
        flags_raw     = get_cpu_flags(cpuinfo)
        flags_set     = set(flags_raw.split())
        ram_gb        = detect_ram_gb()
        gpu           = detect_gpu()
        os_name       = detect_os()
        gcc_ver       = gcc_version()
        cpu_part_name = ""
        implementer   = ""

        # ARM específico
        if vendor == "arm":
            cpu_part_name = decode_arm_cpu(cpuinfo)
            implementer   = get_arm_implementer_name(cpuinfo) or ""
            if cpu_part_name != "unknown":
                model_name = f"ARM {cpu_part_name}"

        # 3. Determinar march/mtune
        gcc_march = gcc_detect_march()

        if vendor in ("intel", "amd"):
            if vendor == "intel":
                march, mtune, gen_label = guess_march_intel(flags_set, model_name)
            else:
                march, mtune, gen_label = guess_march_amd(flags_set, model_name)
            if gcc_march and gcc_march not in ("native", "x86-64"):
                march = gcc_march
                mtune = gcc_march
            arch_name = march
        elif vendor == "arm":
            march, mtune, gen_label = guess_march_arm(flags_set, cpu_part_name, arch)
            arch_name = cpu_part_name.lower().replace(" ", "-") if cpu_part_name != "unknown" else march
        else:
            march, mtune, gen_label = arch, arch, arch
            arch_name = "unknown"

        # Determinar vendor para path de templates
        if vendor == "arm":
            vendor_dir = vendor
        elif vendor == "amd":
            vendor_dir = vendor
        else:
            vendor_dir = vendor

        # Información del dispositivo
        device_vendor = args.vendor or ""
        device_product = args.product or ""

        if args.device:
            parts = args.device.split(" ", 1)
            if len(parts) == 2:
                device_vendor = device_vendor or parts[0]
                device_product = device_product or parts[1]

        if not args.cpu_only and (not device_vendor or not device_product):
            device_vendor, device_product = interactive_device_info(model_name, vendor)

    # 4. Salida JSON
    if args.json:
        json_output(vendor, arch_name, model_name, flags_set, march, mtune,
                     gen_label, phys, logi, ram_gb, gpu, os_name, cpu_part_name)
        return

    # 5. Mostrar resumen
    print_hardware_summary(
        vendor, gen_label, model_name, cpu_part_name,
        march, mtune, phys, logi, ram_gb, gpu, flags_set, gcc_ver,
    )
    print_ggml_table(vendor, flags_set, march)
    print_adr005_warning(flags_set)

    # 7. Generar perfil CPU
    cpu_profile = gen_cpu_profile(
        vendor, arch_name, model_name, flags_set, march, mtune, gen_label,
        cpu_part_name,
    )

    inherits_path = f"cpu/{vendor_dir}/{arch_name}"
    hw_profile: str = ""

    # Mostrar / guardar
    print(c("bold", "\n  ── Perfil de CPU ───────────────────────────────────────────────"))
    print()
    print(cpu_profile)

    if not args.cpu_only:
        hw_profile = gen_hw_profile(
            vendor_dir, arch_name, model_name,
            device_vendor, device_product,
            phys, logi, os_name, ram_gb, gpu,
            inherits_path,
        )

        print(c("bold", "\n  ── Perfil de Hardware ──────────────────────────────────────────"))
        print()
        print(hw_profile)

    # 8. Guardar a disco si --output-dir
    if args.output_dir:
        out = Path(args.output_dir)
        out.mkdir(parents=True, exist_ok=True)

        cpu_filename = f"{arch_name}.toml"
        cpu_dir = out / "cpu" / vendor_dir
        cpu_dir.mkdir(parents=True, exist_ok=True)
        cpu_path = cpu_dir / cpu_filename
        cpu_path.write_text(cpu_profile)
        print(c("green", f"\n  [OK] Perfil CPU guardado:     {cpu_path}"))

        if not args.cpu_only:
            hw_dir = out / sanitize_filename(device_vendor) / sanitize_filename(device_product)
            hw_dir.mkdir(parents=True, exist_ok=True)
            hw_path = hw_dir / "build.toml"
            hw_path.write_text(hw_profile)
            print(c("green", f"  [OK] Perfil hardware guardado: {hw_path}"))

    # 9. Instrucciones finales
    print(c("bold", f"\n  {'─' * 65}"))
    print(c("cyan",  "  Próximos pasos:"))
    print(f"  {c('dim', '1.')} Revisa los flags GGML generados: ¿coinciden con tu CPU?")
    print(f"  {c('dim', '2.')} Coloca el perfil de CPU en:    build/templates/cpu/{vendor_dir}/{arch_name}.toml")
    if not args.cpu_only:
        print(f"  {c('dim', '3.')} Coloca el perfil de hardware en:  build/templates/{sanitize_filename(device_vendor)}/{sanitize_filename(device_product)}/build.toml")
        print(f"  {c('dim', '4.')} Prueba la compilación:")
        print(f"         {c('green', f'just setup-profile {sanitize_filename(device_vendor)}/{sanitize_filename(device_product)}')}")
    else:
        print(f"  {c('dim', '3.')} Prueba la compilación con el perfil:")
        print(f"         {c('green', 'make compile PROFILE=<vendor>/<device>')}")

    print(f"  {c('dim',    '5.')} Verifica los binarios con:  make debug-cpu  &&  make test")
    print()


if __name__ == "__main__":
    main()
