#!/usr/bin/env python3
"""
fetch-latest-tag.py — Imprime el tag de la última release de llama.cpp en GitHub.

Uso:
  python3 scripts/build/fetch-latest-tag.py
  # → b9852

Salida: solo el tag (sin newline extra), para uso en shell:
  tag=$(python3 scripts/build/fetch-latest-tag.py)
"""

import json
import sys
import urllib.request

GH_API = "https://api.github.com/repos/ggerganov/llama.cpp/releases/latest"


def main() -> None:
    req = urllib.request.Request(GH_API, headers={"User-Agent": "PoC-Llama.cpp"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        print(data["tag_name"])
    except Exception as e:
        sys.exit(f"[ERROR] No se pudo obtener el último tag de llama.cpp: {e}")


if __name__ == "__main__":
    main()
