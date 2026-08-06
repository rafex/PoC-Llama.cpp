#!/usr/bin/env python3
"""
status.py — Dashboard de estado y monitoreo CLI para PoC-Llama.cpp

Muestra información consolidada del sistema:
- Versión activa de llama.cpp en /opt/llama.cpp/current
- Modelos instalados en /srv/models y espacio en disco
- Diagnóstico rápido de GPU y backend
- Estado de cualquier servidor llama-server activo (PID, Puerto, Memoria, CPU)

Uso:
  python3 scripts/commons/status.py
  python3 scripts/commons/status.py --watch
"""

import sys
import os
import time
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, List

MODELS_BASE = Path("/srv/models")
CURRENT_LINK = Path("/opt/llama.cpp/current")

def get_active_version() -> str:
    if CURRENT_LINK.exists() and CURRENT_LINK.is_symlink():
        target = CURRENT_LINK.readlink()
        return target.name
    elif CURRENT_LINK.exists():
        return "Instalado (sin versionado)"
    return "No instalado en /opt/llama.cpp/current"

def get_models_info() -> Dict[str, Any]:
    info = {"count": 0, "total_size_mb": 0.0, "total_size_gb": 0.0, "categories": {}}
    if not MODELS_BASE.exists():
        return info


    for category in ["gguf", "embeddings", "rerankers", "multimodal"]:
        cat_dir = MODELS_BASE / category
        if cat_dir.exists():
            files = list(cat_dir.glob("*.gguf"))
            cat_size = sum(f.stat().st_size for f in files) / (1024 * 1024)
            info["categories"][category] = {
                "count": len(files),
                "size_mb": round(cat_size, 1),
                "files": [f.name for f in files]
            }
            info["count"] += len(files)
            info["total_size_mb"] += cat_size

    info["total_size_gb"] = round(info["total_size_mb"] / 1024.0, 2)
    return info

def get_running_server() -> Dict[str, Any]:
    server_info = {"running": False, "pid": None, "cmd": None, "port": "8080", "mem_mb": 0.0}
    try:
        res = subprocess.run(["pgrep", "-f", "llama-server"], capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            pids = res.stdout.strip().splitlines()
            pid = int(pids[0])
            server_info["running"] = True
            server_info["pid"] = pid

            # Obtener cmdline
            ps_out = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True)
            if ps_out.returncode == 0:
                cmd = ps_out.stdout.strip()
                server_info["cmd"] = cmd
                # Buscar puerto
                parts = cmd.split()
                if "--port" in parts:
                    idx = parts.index("--port")
                    if idx + 1 < len(parts):
                        server_info["port"] = parts[idx + 1]

            # Obtener uso de memoria (RSS)
            mem_out = subprocess.run(["ps", "-p", str(pid), "-o", "rss="], capture_output=True, text=True)
            if mem_out.returncode == 0 and mem_out.stdout.strip():
                try:
                    server_info["mem_mb"] = round(float(mem_out.stdout.strip()) / 1024.0, 1)
                except Exception:
                    pass
    except Exception:
        pass
    return server_info

def render_dashboard():
    # Estilos ANSI
    bold = "\033[1m"
    cyan = "\033[36m"
    green = "\033[32m"
    yellow = "\033[33m"
    red = "\033[31m"
    dim = "\033[2m"
    reset = "\033[0m"

    version = get_active_version()
    models = get_models_info()
    server = get_running_server()

    # Intentar cargar GPU info
    gpu_desc = "Desconocida"
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from detect_gpu import get_gpu_info
        gpu_data = get_gpu_info()
        gpu_desc = f"{gpu_data.get('vendor')} {gpu_data.get('model')} ({gpu_data.get('backend_recommended')})"
    except Exception:
        pass

    print(f"\n{bold}PoC-Llama.cpp — Estado y Monitoreo del Sistema{reset}\n")
    print(f"  {bold}Versión Activa:{reset}       {green if '20' in version else yellow}{version}{reset}")
    print(f"  {bold}Hardware GPU:{reset}         {cyan}{gpu_desc}{reset}")
    print(f"  {bold}Directorio Modelos:{reset}   {MODELS_BASE} ({models['count']} modelos, {models['total_size_gb']} GB)")

    for cat, data in models["categories"].items():
        if data["count"] > 0:
            print(f"    └─ {cat:12s}: {data['count']} archivo(s)  ({data['size_mb']} MB)")

    print(f"\n  {bold}Estado de llama-server:{reset}")
    if server["running"]:
        print(f"    Status:     {green}● RUNNING{reset} (PID: {server['pid']})")
        print(f"    Puerto:     {cyan}http://localhost:{server['port']}{reset}")
        print(f"    Memoria:    {server['mem_mb']} MB RAM")
        if server["cmd"]:
            print(f"    Comando:    {dim}{server['cmd'][:80]}...{reset}")
    else:
        print(f"    Status:     {yellow}○ INACTIVO{reset} (Iniciar con 'just run <modelo>')")
    print()

def main():
    if "--watch" in sys.argv:
        try:
            while True:
                # Limpiar pantalla
                os.system("cls" if os.name == "nt" else "clear")
                render_dashboard()
                print("\033[2mPresiona Ctrl+C para salir del monitoreo...\033[0m")
                time.sleep(2)
        except KeyboardInterrupt:
            print("\nMonitoreo finalizado.")
            sys.exit(0)
    else:
        render_dashboard()

if __name__ == "__main__":
    main()
