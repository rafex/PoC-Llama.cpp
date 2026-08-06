#!/usr/bin/env python3
"""
quantize.py — Wrapper interactivo para cuantización de modelos con llama-quantize

Soporta cuantizar modelos en /srv/models a tipos como Q4_K_M, Q5_K_M, Q8_0, IQ4_NL, etc.

Uso:
  python3 scripts/models/quantize.py
  python3 scripts/models/quantize.py <input.gguf> <output.gguf> <type>
"""

import sys
import os
import subprocess
import shutil
from pathlib import Path

MODELS_BASE = Path("/srv/models")

TYPES = ["Q4_K_M", "Q5_K_M", "Q8_0", "Q4_0", "Q4_1", "IQ4_NL", "IQ4_XS"]

def find_gguf_files() -> list[Path]:
    if not MODELS_BASE.exists():
        return []
    return sorted(list(MODELS_BASE.rglob("*.gguf")))

def main():
    if len(sys.argv) == 4:
        input_path = Path(sys.argv[1])
        output_path = Path(sys.argv[2])
        qtype = sys.argv[3]
    else:
        print("\033[1mPoC-Llama.cpp — Cuantización Local de Modelos\033[0m\n")
        files = find_gguf_files()
        if not files:
            print("\033[33m[WARN] No hay archivos .gguf en /srv/models\033[0m")
            sys.exit(0)

        print("Modelos disponibles:")
        for idx, f in enumerate(files, 1):
            size_mb = f.stat().st_size / (1024 * 1024)
            print(f"  [{idx}] {f.name} ({size_mb:.0f} MB)")

        try:
            choice = input("\nSelecciona el número de modelo a cuantizar (q para salir): ").strip()
            if choice.lower() in ("q", "quit", "exit"):
                sys.exit(0)
            idx = int(choice) - 1
            input_path = files[idx]
        except Exception:
            print("Selección inválida.")
            sys.exit(1)

        print("\nTipos de cuantización soportados:")
        for idx, t in enumerate(TYPES, 1):
            print(f"  [{idx}] {t}")

        try:
            choice_t = input("\nSelecciona el tipo de cuantización (default 1 = Q4_K_M): ").strip() or "1"
            qtype = TYPES[int(choice_t) - 1]
        except Exception:
            qtype = "Q4_K_M"

        suffix = f"_{qtype.lower()}.gguf"
        output_name = input_path.stem + suffix
        output_path = input_path.parent / output_name

    print(f"\n\033[36m[INFO] Cuantizando {input_path.name} → {output_path.name} ({qtype})...\033[0m")

    # Verificar binario llama-quantize
    quantize_bin = shutil.which("llama-quantize") or "/opt/llama.cpp/current/bin/llama-quantize"
    if not os.path.exists(str(quantize_bin)) and not shutil.which(str(quantize_bin)):
        print("\033[31m[ERROR] No se encontró el binario llama-quantize en PATH o /opt/llama.cpp/current/bin/\033[0m")
        sys.exit(1)

    cmd = [str(quantize_bin), str(input_path), str(output_path), qtype]
    res = subprocess.run(cmd)

    if res.returncode == 0 and output_path.exists():
        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"\033[32m[OK] Cuantización exitosa: {output_path} ({size_mb:.0f} MB)\033[0m")
    else:
        print(f"\033[31m[ERROR] Falló la cuantización con código {res.returncode}\033[0m")
        sys.exit(res.returncode)

if __name__ == "__main__":
    main()
