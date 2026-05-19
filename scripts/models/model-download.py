#!/usr/bin/env python3
"""
model-download.py — Catálogo interactivo de modelos GGUF para llama.cpp

Muestra el catálogo en build/models/catalog.toml, permite filtrar por tipo
y descarga el modelo elegido usando llama-cli --hf-repo (nativo de llama.cpp)
con fallback a wget/curl.

Uso:
  python3 scripts/models/model-download.py
  python3 scripts/models/model-download.py --type chat
  python3 scripts/models/model-download.py --list
  python3 scripts/models/model-download.py --id qwen2.5-1.5b-chat-q4
"""

import sys
import os
import argparse
import subprocess
import shutil
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        sys.exit("[ERROR] Se requiere Python 3.11+ o: pip install tomli")

CATALOG_PATH = Path(__file__).parent.parent.parent / "build/models/catalog.toml"
MODELS_BASE  = Path("/srv/models")
HF_BASE_URL  = "https://huggingface.co/{repo}/resolve/main/{file}"

COLORS = {
    "reset":  "\033[0m",
    "bold":   "\033[1m",
    "green":  "\033[32m",
    "yellow": "\033[33m",
    "cyan":   "\033[36m",
    "red":    "\033[31m",
    "dim":    "\033[2m",
}

TYPE_LABELS = {
    "chat":      "💬 Chat",
    "coding":    "💻 Código",
    "embedding": "🔢 Embedding",
    "multimodal":"🖼  Multimodal",
}


def c(color: str, text: str) -> str:
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def load_catalog(model_type: Optional[str] = None) -> list[dict]:
    with open(CATALOG_PATH, "rb") as f:
        data = tomllib.load(f)
    models = data.get("models", [])
    if model_type:
        models = [m for m in models if m["type"] == model_type]
    return models


def print_catalog(models: list[dict]) -> None:
    if not models:
        print(c("yellow", "  Sin modelos para ese filtro."))
        return

    current_type = None
    for i, m in enumerate(models, 1):
        if m["type"] != current_type:
            current_type = m["type"]
            label = TYPE_LABELS.get(current_type, current_type)
            print(f"\n  {c('bold', label)}")
            print(f"  {'─' * 60}")

        ram   = f"{m['ram_gb']} GB RAM"
        size  = f"~{m['size_gb']} GB"
        mid = m["id"]
        print(
            f"  {c('cyan', f'[{i:2d}]')} {c('bold', m['name'])}\n"
            f"       {c('dim', m['description'])}\n"
            f"       {c('dim', f'{size}  ·  {ram}  ·  id: {mid}')}",
        )


def already_downloaded(model: dict) -> Optional[Path]:
    dest = MODELS_BASE / model["dest_dir"] / model["hf_file"]
    return dest if dest.exists() else None


def download_with_llama_cli(model: dict, dest: Path) -> bool:
    """Descarga usando el downloader nativo de llama.cpp."""
    if not shutil.which("llama-cli"):
        return False
    # llama-cli puede descargar el modelo si se compila con CURL
    # Usamos --no-warmup y -n 0 para descargar sin inferir
    cmd = [
        "llama-cli",
        "--hf-repo", model["hf_repo"],
        "--hf-file", model["hf_file"],
        "--no-warmup",
        "-n", "0",
        "--model", str(dest),
        "--log-disable",
    ]
    print(c("cyan", f"[INFO] Descargando con llama-cli: {' '.join(cmd[:4])} ..."))
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0 and dest.exists():
        return True
    # llama-cli no soporta --hf-repo en esta build o falló
    return False


def download_with_http(model: dict, dest: Path) -> bool:
    """Descarga directa desde HuggingFace via wget o curl."""
    url = HF_BASE_URL.format(repo=model["hf_repo"], file=model["hf_file"])
    print(c("cyan", f"[INFO] URL: {url}"))

    if shutil.which("wget"):
        cmd = ["wget", "--progress=bar:force", "-O", str(dest), url]
    elif shutil.which("curl"):
        cmd = ["curl", "-L", "--progress-bar", "-o", str(dest), url]
    else:
        print(c("red", "[ERROR] Se necesita wget o curl para descargar."))
        return False

    result = subprocess.run(cmd)
    return result.returncode == 0 and dest.exists()


def download_model(model: dict) -> None:
    dest_dir = MODELS_BASE / model["dest_dir"]
    dest     = dest_dir / model["hf_file"]

    existing = already_downloaded(model)
    if existing:
        print(c("yellow", f"[SKIP]  El modelo ya existe: {existing}"))
        return

    print(c("bold", f"\n[INFO] Descargando: {model['name']}"))
    print(c("dim",  f"       Destino: {dest}"))

    # Necesita sudo para crear /srv/models si no existe
    if not dest_dir.exists():
        print(c("cyan", f"[INFO] Creando directorio: {dest_dir}"))
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            subprocess.run(["sudo", "mkdir", "-p", str(dest_dir)], check=True)
            subprocess.run(["sudo", "chmod", "777", str(dest_dir)], check=True)

    # Intentar con llama-cli primero, luego fallback HTTP
    success = download_with_llama_cli(model, dest) or download_with_http(model, dest)

    if success:
        print(c("green", f"\n[OK]   Modelo descargado: {dest}"))
        size_mb = dest.stat().st_size / (1024 * 1024)
        print(c("dim",   f"       Tamaño: {size_mb:.0f} MB"))
    else:
        print(c("red", f"\n[ERROR] Falló la descarga de {model['hf_file']}"))
        if dest.exists():
            dest.unlink()
        sys.exit(1)


def interactive_menu(models: list[dict]) -> dict:
    print(c("bold", "\n  PoC-Llama.cpp — Catálogo de modelos"))
    print_catalog(models)
    print(f"\n  {c('dim', '─' * 60)}")
    print(f"  Modelos instalados en {MODELS_BASE}")

    # Marcar los ya descargados
    for m in models:
        if already_downloaded(m):
            print(c("green", f"  [✓] {m['id']}"))

    print()
    while True:
        try:
            raw = input(c("bold", "  Número a descargar (q para salir): ")).strip()
        except (KeyboardInterrupt, EOFError):
            print()
            sys.exit(0)
        if raw.lower() in ("q", "exit", "quit"):
            sys.exit(0)
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(models):
                return models[idx]
            print(c("yellow", f"  Número inválido. Elige entre 1 y {len(models)}."))
        except ValueError:
            print(c("yellow", "  Ingresa un número o 'q' para salir."))


def main() -> None:
    parser = argparse.ArgumentParser(description="Descarga modelos GGUF para llama.cpp.")
    parser.add_argument("--type",  choices=["chat", "coding", "embedding", "multimodal"],
                        help="Filtrar por tipo de modelo")
    parser.add_argument("--list",  action="store_true", help="Solo listar, no descargar")
    parser.add_argument("--id",    help="Descargar directamente por ID sin menú interactivo")
    args = parser.parse_args()

    models = load_catalog(args.type)

    if not models:
        print(c("yellow", "[WARN] No hay modelos en el catálogo con ese filtro."))
        sys.exit(0)

    if args.list:
        print_catalog(models)
        sys.exit(0)

    if args.id:
        match = [m for m in models if m["id"] == args.id]
        if not match:
            print(c("red", f"[ERROR] ID '{args.id}' no encontrado en el catálogo."))
            sys.exit(1)
        download_model(match[0])
        return

    model = interactive_menu(models)
    download_model(model)


if __name__ == "__main__":
    main()
