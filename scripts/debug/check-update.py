#!/usr/bin/env python3
"""
check-update.py — Compara la versión local de llama.cpp con la última release en GitHub.

Uso:
  python3 scripts/debug/check-update.py [--src-dir <path>]
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from typing import Optional, Tuple

GH_API = "https://api.github.com/repos/ggerganov/llama.cpp/releases/latest"
COLORS = {
    "green":  "\033[32m",
    "yellow": "\033[33m",
    "cyan":   "\033[36m",
    "bold":   "\033[1m",
    "reset":  "\033[0m",
}


def c(color: str, text: str) -> str:
    return f"{COLORS[color]}{text}{COLORS['reset']}"


def build_num(tag: str) -> int:
    stripped = tag.lstrip("b")
    return int(stripped) if stripped.isdigit() else 0


def local_version(src_dir: str) -> Tuple[Optional[str], Optional[str]]:
    """Devuelve (tag, commit) del repo clonado, o (None, None) si no existe."""
    if not os.path.isdir(os.path.join(src_dir, ".git")):
        return None, None

    try:
        tag = subprocess.check_output(
            ["git", "-C", src_dir, "describe", "--tags", "--abbrev=0"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except subprocess.CalledProcessError:
        tag = None

    try:
        commit = subprocess.check_output(
            ["git", "-C", src_dir, "log", "--oneline", "-1"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except subprocess.CalledProcessError:
        commit = None

    return tag, commit


def installed_version() -> Optional[str]:
    """Devuelve la línea de versión de llama-cli --version, o None."""
    try:
        out = subprocess.check_output(
            ["llama-cli", "--version"],
            stderr=subprocess.STDOUT, text=True,
        ).strip().splitlines()
        return next((l for l in out if "version" in l.lower()), out[0] if out else None)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def latest_release() -> Tuple[str, str]:
    """Devuelve (tag, fecha) de la última release en GitHub."""
    req = urllib.request.Request(GH_API, headers={"User-Agent": "PoC-Llama.cpp"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    return data["tag_name"], data["published_at"][:10]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--src-dir",
        default="build/llama.cpp/src",
        help="Ruta al repo clonado de llama.cpp (default: build/llama.cpp/src)",
    )
    args = parser.parse_args()

    print()

    # --- Versión local ---
    tag, commit = local_version(args.src_dir)
    if tag is None and commit is None:
        print("  {}  llama.cpp no está clonado en {}".format(c("yellow", "[WARN]"), args.src_dir))
        print("         Ejecuta: make clone")
        sys.exit(0)

    if tag:
        print("  Local clonado : {}  ({})".format(c("bold", tag), commit))
    else:
        print("  Local clonado : {}  {}".format(c("yellow", "(sin tag)"), commit))

    # --- Versión instalada ---
    ver = installed_version()
    if ver:
        print("  Instalado     : {}".format(c("cyan", ver)))
    else:
        print("  Instalado     : {}".format(c("yellow", "(llama-cli no encontrado en PATH)")))

    # --- Última release ---
    try:
        latest_tag, latest_date = latest_release()
        print("  Última release: {}  ({})".format(c("bold", latest_tag), latest_date))
    except Exception as e:
        print("  {}  No se pudo consultar GitHub: {}".format(c("yellow", "[WARN]"), e))
        sys.exit(0)

    # --- Comparar ---
    print()
    local_n  = build_num(tag or "")
    latest_n = build_num(latest_tag)

    if local_n == 0:
        print("  {}  No se puede comparar — tag local no reconocido.".format(c("yellow", "[?]")))
    elif local_n >= latest_n:
        print("  {}  Estás en la última versión ({}).".format(c("green", "[OK]"), latest_tag))
    else:
        diff = latest_n - local_n
        print("  {}  Hay una versión más reciente disponible.".format(c("yellow", "[UPDATE]")))
        print("           Local     : {}".format(tag))
        print("           Disponible: {}  ({} builds de diferencia)".format(latest_tag, diff))
        print()
        print("  Para actualizar:")
        print("    make build-purge")
        print("    just setup-profile <tu-perfil>")
    print()


if __name__ == "__main__":
    main()
