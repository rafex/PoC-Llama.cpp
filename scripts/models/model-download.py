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
    "chat":       "💬 Chat",
    "coding":     "💻 Código",
    "embedding":  "🔢 Embedding",
    "multimodal": "🖼  Multimodal",
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


def extra_files(model: dict) -> list[str]:
    return model.get("hf_extra_files", [])


def download_file(repo: str, filename: str, dest: Path) -> bool:
    """Descarga un archivo individual: llama-cli primero, luego HTTP."""
    if dest.exists():
        print(c("yellow", f"[SKIP]  Ya existe: {dest.name}"))
        return True

    # Intentar con llama-cli (si tiene soporte HuggingFace compilado)
    if shutil.which("llama-cli"):
        cmd = [
            "llama-cli",
            "--hf-repo", repo,
            "--hf-file", filename,
            "--no-warmup", "-n", "0",
            "--model", str(dest),
            "--log-disable",
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0 and dest.exists():
            return True

    # Fallback: descarga HTTP directa desde HuggingFace
    url = HF_BASE_URL.format(repo=repo, file=filename)
    print(c("cyan", f"[INFO] {filename}  ←  {url}"))
    if shutil.which("wget"):
        cmd = ["wget", "--progress=bar:force", "-O", str(dest), url]
    elif shutil.which("curl"):
        cmd = ["curl", "-L", "--progress-bar", "-o", str(dest), url]
    else:
        print(c("red", "[ERROR] Se necesita wget o curl para descargar."))
        return False

    result = subprocess.run(cmd)
    return result.returncode == 0 and dest.exists()


def ensure_dest_dir(dest_dir: Path) -> None:
    if not dest_dir.exists():
        print(c("cyan", f"[INFO] Creando directorio: {dest_dir}"))
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            subprocess.run(["sudo", "mkdir", "-p", str(dest_dir)], check=True)
            subprocess.run(["sudo", "chmod", "777", str(dest_dir)], check=True)

    # El directorio existe pero el usuario actual no tiene permisos de escritura
    if not os.access(dest_dir, os.W_OK):
        print(c("cyan", f"[INFO] Ajustando permisos de escritura: {dest_dir}"))
        subprocess.run(["sudo", "chmod", "777", str(dest_dir)], check=True)


def download_model(model: dict) -> None:
    dest_dir = MODELS_BASE / model["dest_dir"]
    ensure_dest_dir(dest_dir)

    # Archivo principal
    existing = already_downloaded(model)
    if existing:
        print(c("yellow", f"[SKIP]  Modelo principal ya existe: {existing}"))
    else:
        print(c("bold", f"\n[INFO] Descargando: {model['name']}"))
        dest = dest_dir / model["hf_file"]
        if not download_file(model["hf_repo"], model["hf_file"], dest):
            print(c("red", f"[ERROR] Falló la descarga de {model['hf_file']}"))
            if dest.exists():
                dest.unlink()
            sys.exit(1)
        size_mb = dest.stat().st_size / (1024 * 1024)
        print(c("green", f"[OK]   {dest.name}  ({size_mb:.0f} MB)"))

    # Archivos extra (ej: mmproj para multimodal)
    for extra in extra_files(model):
        dest_extra = dest_dir / extra
        print(c("bold", f"\n[INFO] Archivo extra requerido: {extra}"))
        if not download_file(model["hf_repo"], extra, dest_extra):
            print(c("red", f"[ERROR] Falló la descarga de {extra}"))
            if dest_extra.exists():
                dest_extra.unlink()
            sys.exit(1)
        size_mb = dest_extra.stat().st_size / (1024 * 1024)
        print(c("green", f"[OK]   {dest_extra.name}  ({size_mb:.0f} MB)"))

    print(c("green", f"\n[OK]   Descarga completa en {dest_dir}"))


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
