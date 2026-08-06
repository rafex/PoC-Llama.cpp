#!/usr/bin/env python3
"""
compile-auto-test.py — Dry-run de detección de hardware para compile-auto.

Ejecuta detect-profile.py y detect_gpu.py mostrando el hardware detectado,
el match de perfil TOML, y los flags cmake que se usarían. Sin compilar.

Uso:
  python3 scripts/build/compile-auto-test.py
  python3 scripts/build/compile-auto-test.py --profile apple/macmini6.2
"""

import sys
import json
import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent
DETECT_PROFILE = SCRIPTS_DIR / "build" / "detect-profile.py"
DETECT_GPU = SCRIPTS_DIR / "commons" / "detect_gpu.py"
TOML_READER = SCRIPTS_DIR / "commons" / "toml-reader.py"
TEMPLATES_DIR = Path("build/templates")

BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
DIM = "\033[2m"
RESET = "\033[0m"


def run(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    except Exception:
        return ""


def section(title: str) -> None:
    print(f"\n{CYAN}[INFO]{RESET}  {BOLD}=== {title} ==={RESET}")


def hardware_section() -> None:
    section("Detección de hardware")
    raw = run([sys.executable, str(DETECT_PROFILE), "--info"])
    if not raw:
        print("  (no disponible)")
        return

    d = json.loads(raw)
    print(f"  OS:         {d.get('os', '?')}  |  Arch: {d.get('arch', '?')}")
    print(f"  CPU:        {d.get('cpu_model', '?')}")
    print(f"  Cores:      {d.get('logical_cpus', '?')}")
    p = d.get("product", "") or "(no detectado)"
    print(f"  Product:    {p}")
    a = d.get("cpu_arch", "") or "(no inferido)"
    print(f"  cpu_arch:   {a}")

    exts = []
    if d.get("has_avx"):
        exts.append("AVX")
    if d.get("has_avx2"):
        exts.append("AVX2")
    if d.get("has_neon"):
        exts.append("NEON")
    if d.get("has_sve"):
        exts.append("SVE")
    if exts:
        print(f"  Extensiones: {' '.join(exts)}")


def gpu_section() -> None:
    section("Detección de GPU")
    result = subprocess.run(
        [sys.executable, str(DETECT_GPU)],
        capture_output=True, text=True,
    )
    lines = result.stdout.splitlines()
    for line in lines:
        print(f"  {line}" if line.strip() else "")


def vulkan_instructions_section() -> None:
    section("Instrucciones para habilitar GPU (Vulkan)")

    raw = run([sys.executable, str(DETECT_GPU), "--json"])
    if not raw:
        print("  (información no disponible)")
        return

    info = json.loads(raw)

    # macOS: no aplica
    if info.get("metal_supported"):
        print(f"  {GREEN}✓{RESET}  Metal disponible en macOS — no requiere Vulkan")
        return

    vulkan_packages = info.get("vulkan_packages", {})
    if not vulkan_packages:
        # Sin dpkg — usar chequeo binario
        missing_cmd = run([sys.executable, str(DETECT_GPU), "--missing"])
        if missing_cmd:
            print(f"  {YELLOW}Paquetes faltantes:{RESET}")
            print(f"  {BOLD}Instalar con:{RESET}  {CYAN}{missing_cmd}{RESET}")
        elif not info.get("vulkan_supported"):
            print(f"  {YELLOW}(no se detectaron paquetes Vulkan — instala libvulkan-dev glslang-tools){RESET}")
        else:
            print(f"  {GREEN}✓ SDK Vulkan completo{RESET}")
        return

    # dpkg disponible — mostrar detalle por paquete
    all_ok = True
    for pkg_name in sorted(vulkan_packages.keys()):
        pkg_data = vulkan_packages[pkg_name]
        if pkg_data["installed"]:
            print(f"  {GREEN}✓{RESET} {pkg_name:<24} {DIM}({pkg_data['role']}){RESET}")
        else:
            print(f"  {RED}✗{RESET} {pkg_name:<24} {DIM}({pkg_data['role']}){RESET}")
            all_ok = False

    if all_ok:
        print(f"\n  {GREEN}✓ SDK Vulkan completo — GGML_VULKAN=ON se añadirá automáticamente{RESET}")
    else:
        missing_cmd = run([sys.executable, str(DETECT_GPU), "--missing"])
        print(f"\n  {BOLD}Para habilitar aceleración GPU:{RESET}")
        if missing_cmd:
            print(f"  {CYAN}{missing_cmd}{RESET}")
        print(f"\n  Luego ejecuta  {CYAN}make compile-auto{RESET}  (se añadirá -DGGML_VULKAN=ON automáticamente)")

    # OpenCL para GPUs Intel antiguas (Gen7-)
    ocl_info = info.get("opencl_packages", {})
    if ocl_info:
        print(f"\n  {BOLD}OpenCL (alternativa para GPU Intel Gen7-):{RESET}")
        ocl_all = True
        for pkg_name in sorted(ocl_info.keys()):
            pd = ocl_info[pkg_name]
            if pd["installed"]:
                print(f"  {GREEN}✓{RESET} {pkg_name:<24} {DIM}({pd['role']}){RESET}")
            else:
                print(f"  {RED}✗{RESET} {pkg_name:<24} {DIM}({pd['role']}){RESET}")
                ocl_all = False
        if ocl_all:
            print(f"  {GREEN}✓ OpenCL disponible — GGML_OPENCL=ON se añadirá automáticamente{RESET}")
        else:
            ocl_cmd = run([sys.executable, str(DETECT_GPU), "--opencl-missing"])
            if ocl_cmd:
                print(f"  {CYAN}{ocl_cmd}{RESET}")


def profile_section(forced_profile: str = "") -> None:
    section("Match de perfil TOML")

    if forced_profile:
        toml_file = TEMPLATES_DIR / forced_profile / "build.toml"
        if toml_file.is_file():
            print(f"{GREEN}[OK]{RESET}    Perfil TOML: {forced_profile}")
            print(f"{CYAN}[INFO]{RESET}  Flags cmake del perfil:")
            flags = run([sys.executable, str(TOML_READER), str(toml_file), "--format", "cmake"])
            _print_cmake_flags(flags)
            return
        else:
            print(f"{RED}[ERROR]{RESET} Perfil no encontrado: {forced_profile}")
            print()
            print(f"{CYAN}[INFO]{RESET}  Perfiles disponibles:")
            for tf in sorted(TEMPLATES_DIR.rglob("build.toml")):
                name = "/".join(tf.relative_to(TEMPLATES_DIR).parts[:-1])
                print(f"  {name}")
            return

    detected = run([sys.executable, str(DETECT_PROFILE), "--match"])
    if detected:
        print(f"{GREEN}[OK]{RESET}    Perfil TOML: {detected}")
        toml_file = TEMPLATES_DIR / detected / "build.toml"
        if toml_file.is_file():
            print(f"{CYAN}[INFO]{RESET}  Flags cmake del perfil:")
            flags = run([sys.executable, str(TOML_READER), str(toml_file), "--format", "cmake"])
            _print_cmake_flags(flags)
    else:
        print(f"{YELLOW}[WARN]{RESET}  Sin perfil TOML — usando detección automática genérica")


def _print_cmake_flags(flags: str, indent: str = "         ") -> None:
    import shlex
    try:
        parts = shlex.split(flags)
    except ValueError:
        parts = flags.split()
    for f in parts:
        print(f"{indent}{f}")


def flags_section() -> None:
    section("Flags cmake finales (detección automática)")
    flags = run([sys.executable, str(DETECT_PROFILE), "--flags"])
    _print_cmake_flags(flags, indent="  ")


def main() -> None:
    forced_profile = ""
    if "--profile" in sys.argv:
        idx = sys.argv.index("--profile")
        if idx + 1 < len(sys.argv):
            forced_profile = sys.argv[idx + 1]

    print(f"\n{BOLD}PoC-Llama.cpp — compile-auto-test (dry-run){RESET}")
    hardware_section()
    gpu_section()
    vulkan_instructions_section()
    profile_section(forced_profile)
    flags_section()

    if forced_profile:
        print(f"\n{CYAN}[INFO]{RESET}  Con PROFILE={forced_profile}, los flags del perfil TOML tienen precedencia.")


if __name__ == "__main__":
    main()
