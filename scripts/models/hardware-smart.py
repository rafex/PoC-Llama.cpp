#!/usr/bin/env python3
"""
hardware-smart.py — Detecta hardware y clasifica modelos del catálogo por capacidad

Lee /proc/meminfo y /proc/cpuinfo (sin dependencias externas) para el análisis
básico. Ofrece instalar dmidecode para enriquecer la info de RAM.

Clasificación:
  ✅ Eficiente  — RAM total >= ram_gb * 2  (corre cómodamente, con holgura)
  ⚠️  Suficiente — RAM total >= ram_gb      (corre ajustado, puede ser lento)
  ❌ Excede     — RAM total < ram_gb        (supera al hardware, no recomendado)

Uso:
  python3 scripts/models/hardware-smart.py                  # listar clasificados
  python3 scripts/models/hardware-smart.py --download       # listar + menú de descarga
  python3 scripts/models/hardware-smart.py --type chat      # filtrar por tipo
  python3 scripts/models/hardware-smart.py --no-install     # omitir prompt de deps
"""

import sys
import os
import re
import subprocess
import shutil
import argparse
from pathlib import Path
from typing import Optional, List

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        sys.exit("[ERROR] Se requiere Python 3.11+ o: pip install tomli")

CATALOG_PATH = Path(__file__).parent.parent.parent / "build/models/catalog.toml"

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

TYPE_LABELS = {
    "chat":       "💬 Chat",
    "coding":     "💻 Código",
    "embedding":  "🔢 Embedding",
    "multimodal": "🖼  Multimodal",
}

TIER_CONFIG = {
    "eficiente":  ("✅", "green",  "Eficiente  — corre cómodamente (RAM con holgura)"),
    "suficiente": ("⚠️ ", "yellow", "Suficiente — corre ajustado (puede ser lento)"),
    "excede":     ("❌", "red",    "Excede     — supera al hardware (no recomendado)"),
}

# Herramientas opcionales que enriquecen la detección de hardware
OPTIONAL_TOOLS: List[dict] = [
    {
        "cmd":           "dmidecode",
        "pkg":           "dmidecode",
        "desc":          "tipo de memoria RAM (DDR4/DDR3), velocidad en MHz y slots físicos",
        "requires_sudo": True,
    },
]


# =============================================================================
# Utilidades de color
# =============================================================================

def c(color: str, text: str) -> str:
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


# =============================================================================
# Detección de hardware básica (sin dependencias externas)
# =============================================================================

def get_total_ram_gb() -> float:
    """Lee MemTotal de /proc/meminfo."""
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return round(kb / (1024 * 1024), 1)
    except (FileNotFoundError, ValueError, IndexError):
        pass
    return 0.0


def get_available_ram_gb() -> float:
    """Lee MemAvailable de /proc/meminfo."""
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    kb = int(line.split()[1])
                    return round(kb / (1024 * 1024), 1)
    except (FileNotFoundError, ValueError, IndexError):
        pass
    return 0.0


def get_cpu_info() -> dict:
    """Extrae modelo, núcleos físicos e hilos de /proc/cpuinfo."""
    info = {"model": "desconocido", "cores": 0, "threads": 0}
    try:
        with open("/proc/cpuinfo") as f:
            content = f.read()

        m = re.search(r"model name\s*:\s*(.+)", content)
        if m:
            # Normalizar espacios extra frecuentes en el campo
            info["model"] = re.sub(r"\s+", " ", m.group(1).strip())

        info["threads"] = content.count("processor\t:")

        cores_match = re.findall(r"cpu cores\s*:\s*(\d+)", content)
        info["cores"] = int(cores_match[0]) if cores_match else info["threads"]

    except (FileNotFoundError, ValueError):
        pass
    return info


def get_disk_free_gb() -> Optional[float]:
    """Espacio libre en /srv/models, o en / como fallback."""
    for path in ["/srv/models", "/srv", "/"]:
        try:
            usage = shutil.disk_usage(path)
            return round(usage.free / (1024 ** 3), 1)
        except (FileNotFoundError, PermissionError):
            continue
    return None


# =============================================================================
# Detección enriquecida (herramientas opcionales)
# =============================================================================

def get_ram_type_dmidecode() -> Optional[str]:
    """Devuelve tipo y velocidad de RAM via dmidecode (ej: 'DDR4 2400 MT/s')."""
    if not shutil.which("dmidecode"):
        return None
    try:
        result = subprocess.run(
            ["sudo", "dmidecode", "-t", "memory"],
            capture_output=True, text=True, timeout=8,
        )
        if result.returncode != 0:
            return None

        # Filtrar entradas vacías (sin módulo instalado)
        types  = re.findall(r"Type:\s+(\w+)",                result.stdout)
        speeds = re.findall(r"Speed:\s+([\d]+ (?:MT/s|MHz))", result.stdout)

        types  = [t for t in types  if t  not in ("Unknown", "Other", "None", "DDR")]
        speeds = [s for s in speeds if "Unknown" not in s]

        if types and speeds:
            return f"{types[0]} {speeds[0]}"
        if types:
            return types[0]
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
        pass
    return None


def detect_gpu() -> Optional[str]:
    """Detecta GPU NVIDIA (nvidia-smi) o mediante lspci como fallback."""
    # ── NVIDIA ─────────────────────────────────────────────────────────────
    if shutil.which("nvidia-smi"):
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0 and r.stdout.strip():
                gpus = [ln.strip() for ln in r.stdout.strip().splitlines() if ln.strip()]
                return "NVIDIA: " + "; ".join(gpus)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # ── lspci (pciutils, suele estar instalado) ─────────────────────────
    if shutil.which("lspci"):
        try:
            r = subprocess.run(["lspci"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                for line in r.stdout.splitlines():
                    upper = line.upper()
                    if any(k in upper for k in ("VGA", "3D CONTROLLER", "DISPLAY")):
                        m = re.search(r":\s+(.+)", line)
                        if m:
                            return m.group(1).strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    return None


# =============================================================================
# Gestión de dependencias opcionales
# =============================================================================

def missing_optional_tools() -> List[dict]:
    return [t for t in OPTIONAL_TOOLS if not shutil.which(t["cmd"])]


def prompt_install(missing: List[dict]) -> bool:
    """Muestra las herramientas que faltan y pregunta si instalarlas."""
    print(c("yellow", "\n  Herramientas opcionales no encontradas:"))
    print()
    for t in missing:
        sudo_note = "  (requiere sudo)" if t.get("requires_sudo") else ""
        print(f"    • {c('bold', t['cmd'])}  (apt: {t['pkg']}){sudo_note}")
        print(f"      {c('dim', t['desc'])}")
    print()
    print(c("dim", "  Sin estas herramientas el análisis continúa con información básica."))
    print()
    try:
        ans = input(c("bold", "  ¿Instalar ahora? [s/N]: ")).strip().lower()
        print()
    except (KeyboardInterrupt, EOFError):
        print()
        return False
    return ans in ("s", "si", "sí", "y", "yes")


def install_tools(tools: List[dict]) -> None:
    pkgs = [t["pkg"] for t in tools]
    print(c("cyan", f"  [INFO] Instalando: {' '.join(pkgs)} ..."))
    try:
        subprocess.run(
            ["sudo", "apt-get", "install", "-y"] + pkgs,
            check=True,
        )
        print(c("green", "  [OK]  Instalación completada.\n"))
    except subprocess.CalledProcessError:
        print(c("red", "  [WARN] Falló la instalación. Continuando sin ellas.\n"))


# =============================================================================
# Clasificación y presentación
# =============================================================================

def classify(model: dict, total_ram_gb: float) -> str:
    needed = model.get("ram_gb", 0)
    if needed == 0:
        return "eficiente"
    if total_ram_gb >= needed * 2:
        return "eficiente"
    if total_ram_gb >= needed:
        return "suficiente"
    return "excede"


def print_hardware_summary(
    total_ram: float,
    avail_ram: float,
    cpu: dict,
    disk_free: Optional[float],
    ram_type: Optional[str],
    gpu: Optional[str],
) -> None:
    print(c("bold", "\n  PoC-Llama.cpp — Análisis de hardware"))
    print(f"  {'─' * 65}")

    ram_str = f"{total_ram} GB total  ·  {avail_ram} GB disponibles"
    if ram_type:
        ram_str += f"  ({ram_type})"
    print(f"  {c('cyan', 'RAM   ')}  {ram_str}")
    print(f"  {c('cyan', 'CPU   ')}  {cpu['model']}")
    print(f"  {c('cyan', '      ')}  {cpu['cores']} núcleos físicos  /  {cpu['threads']} hilos lógicos")

    if disk_free is not None:
        print(f"  {c('cyan', 'Disco ')}  {disk_free} GB libres en /srv/models")

    if gpu:
        print(f"  {c('cyan', 'GPU   ')}  {gpu}")
    else:
        print(f"  {c('cyan', 'GPU   ')}  {c('dim', 'No detectada — inferencia en CPU')}")


def print_smart_catalog(models: List[dict], total_ram_gb: float) -> None:
    buckets: dict = {"eficiente": [], "suficiente": [], "excede": []}
    for m in models:
        buckets[classify(m, total_ram_gb)].append(m)

    for tier in ("eficiente", "suficiente", "excede"):
        tier_models = buckets[tier]
        if not tier_models:
            continue

        icon, color, label = TIER_CONFIG[tier]
        print(f"\n  {c(color, f'{icon}  {label}')}")
        print(f"  {'─' * 65}")

        current_type = None
        for m in tier_models:
            if m["type"] != current_type:
                current_type = m["type"]
                print(f"\n    {c('dim', TYPE_LABELS.get(current_type, current_type))}")

            mid  = m["id"]
            ram  = f"{m['ram_gb']} GB RAM"
            size = f"~{m['size_gb']} GB"
            print(
                f"    {c('bold', m['name'])}\n"
                f"      {c('dim', m['description'])}\n"
                f"      {c('dim', f'{size}  ·  {ram}  ·  id: {mid}')}",
            )


def print_numbered_catalog(models: List[dict], total_ram_gb: float) -> dict:
    """Imprime el catálogo numerado agrupado por tier. Devuelve {n: (model, tier)}."""
    buckets: dict = {"eficiente": [], "suficiente": [], "excede": []}
    for m in models:
        buckets[classify(m, total_ram_gb)].append(m)

    index: dict = {}
    n = 1

    for tier in ("eficiente", "suficiente", "excede"):
        tier_models = buckets[tier]
        if not tier_models:
            continue

        icon, color, label = TIER_CONFIG[tier]
        print(f"\n  {c(color, f'{icon}  {label}')}")
        print(f"  {'─' * 65}")

        current_type = None
        for m in tier_models:
            if m["type"] != current_type:
                current_type = m["type"]
                print(f"\n    {c('dim', TYPE_LABELS.get(current_type, current_type))}")

            num_color = "red" if tier == "excede" else "cyan"
            ram  = f"{m['ram_gb']} GB RAM"
            size = f"~{m['size_gb']} GB"
            print(
                f"    {c(num_color, f'[{n:2d}]')} {c('bold', m['name'])}\n"
                f"           {c('dim', m['description'])}\n"
                f"           {c('dim', f'{size}  ·  {ram}')}",
            )
            index[n] = (m, tier)
            n += 1

    return index


def interactive_download_menu(models: List[dict], total_ram_gb: float) -> None:
    """Muestra catálogo numerado por tier y ejecuta la descarga del modelo elegido."""
    print(c("bold", f"\n  Modelos disponibles para {total_ram_gb} GB de RAM"))
    index = print_numbered_catalog(models, total_ram_gb)

    total = len(index)
    print(f"\n  {c('dim', '─' * 65)}")
    print(c("dim", "  Los modelos ❌ superan el hardware — se pueden descargar con confirmación."))
    print()

    while True:
        try:
            raw = input(c("bold", f"  Número a descargar [1-{total}] (q para salir): ")).strip()
        except (KeyboardInterrupt, EOFError):
            print()
            sys.exit(0)

        if raw.lower() in ("q", "exit", "quit"):
            sys.exit(0)

        try:
            idx = int(raw)
        except ValueError:
            print(c("yellow", "  Ingresa un número o 'q' para salir."))
            continue

        if idx not in index:
            print(c("yellow", f"  Número inválido. Elige entre 1 y {total}."))
            continue

        model, tier = index[idx]

        if tier == "excede":
            needed = model.get("ram_gb", 0)
            print(c("yellow",
                    f"\n  ⚠️  Este modelo requiere {needed} GB de RAM "
                    f"y el equipo tiene {total_ram_gb} GB."))
            try:
                confirm = input(c("bold", "  ¿Descargar de todas formas? [s/N]: ")).strip().lower()
                print()
            except (KeyboardInterrupt, EOFError):
                print()
                sys.exit(0)
            if confirm not in ("s", "si", "sí", "y", "yes"):
                continue

        launch_download(model)
        return


def launch_download(model: dict) -> None:
    """Delega la descarga a model-download.py --id <id> (reutiliza toda su lógica)."""
    script = Path(__file__).parent / "model-download.py"
    result = subprocess.run([sys.executable, str(script), "--id", model["id"]])
    sys.exit(result.returncode)


def print_summary(models: List[dict], total_ram_gb: float, disk_free: Optional[float]) -> None:
    counts: dict = {"eficiente": 0, "suficiente": 0, "excede": 0}
    for m in models:
        counts[classify(m, total_ram_gb)] += 1

    print(f"\n  {'─' * 65}")
    print(
        f"  {c('green',  str(counts['eficiente']))} eficientes   "
        f"{c('yellow', str(counts['suficiente']))} suficientes   "
        f"{c('red',    str(counts['excede']))} exceden al hardware"
    )

    eficientes = [m for m in models if classify(m, total_ram_gb) == "eficiente"]
    if eficientes:
        total_size = sum(m.get("size_gb", 0) for m in eficientes)
        disk_info  = f"  (libre: {disk_free} GB)" if disk_free is not None else ""
        print(f"  Tamaño total modelos eficientes: ~{total_size:.1f} GB{disk_info}")

    print()
    print(c("dim", "  Descargar con menú inteligente:  just model-download-smart"))
    print(c("dim", "  Descargar por ID directamente:   just model-download-id <id>"))
    print()


# =============================================================================
# main
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detecta hardware y clasifica modelos GGUF según capacidad del equipo."
    )
    parser.add_argument(
        "--type", choices=["chat", "coding", "embedding", "multimodal"],
        help="Filtrar por tipo de modelo",
    )
    parser.add_argument(
        "--download", action="store_true",
        help="Mostrar menú interactivo para elegir y descargar un modelo",
    )
    parser.add_argument(
        "--no-install", action="store_true",
        help="No preguntar por instalación de dependencias opcionales",
    )
    args = parser.parse_args()

    # 1. Dependencias opcionales ────────────────────────────────────────────
    if not args.no_install:
        missing = missing_optional_tools()
        if missing and prompt_install(missing):
            install_tools(missing)

    # 2. Detección de hardware ──────────────────────────────────────────────
    total_ram = get_total_ram_gb()
    avail_ram = get_available_ram_gb()
    cpu       = get_cpu_info()
    disk_free = get_disk_free_gb()
    ram_type  = get_ram_type_dmidecode()
    gpu       = detect_gpu()

    # 3. Resumen de hardware ────────────────────────────────────────────────
    print_hardware_summary(total_ram, avail_ram, cpu, disk_free, ram_type, gpu)

    # 4. Cargar catálogo ────────────────────────────────────────────────────
    try:
        with open(CATALOG_PATH, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        sys.exit(c("red", f"\n  [ERROR] Catálogo no encontrado: {CATALOG_PATH}"))

    models = data.get("models", [])
    if args.type:
        models = [m for m in models if m["type"] == args.type]

    if not models:
        print(c("yellow", "\n  Sin modelos para ese filtro."))
        sys.exit(0)

    # 5a. Modo descarga — menú numerado interactivo ────────────────────────
    if args.download:
        interactive_download_menu(models, total_ram)
        return

    # 5b. Modo lista — catálogo clasificado sin números ────────────────────
    type_label = f" [{args.type}]" if args.type else ""
    print(c("bold", f"\n  Modelos clasificados para {total_ram} GB de RAM{type_label}"))
    print_smart_catalog(models, total_ram)

    # 6. Resumen final ──────────────────────────────────────────────────────
    print_summary(models, total_ram, disk_free)


if __name__ == "__main__":
    main()
