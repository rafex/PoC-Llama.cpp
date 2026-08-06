#!/usr/bin/env python3
"""
service-generator.py — Generador y gestor de servicios daemon (systemd / launchd) para llama-server

Soporta Linux (systemd) y macOS (launchd).

Uso:
  python3 scripts/post-install/service-generator.py --install <model_path_or_id> [--port 8080] [--ngl 99]
  python3 scripts/post-install/service-generator.py --status
  python3 scripts/post-install/service-generator.py --stop
  python3 scripts/post-install/service-generator.py --uninstall
"""

import sys
import os
import platform
import subprocess
import shutil
import argparse
import pwd
from pathlib import Path

SYSTEMD_PATH = Path("/etc/systemd/system/llama-server.service")
LAUNCHD_DIR = Path.home() / "Library/LaunchAgents"
LAUNCHD_PLIST = LAUNCHD_DIR / "com.llama.server.plist"

def get_current_user() -> str:
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        return sudo_user
    return pwd.getpwuid(os.getuid()).pw_name

def resolve_model_path(model_input: str) -> str:
    path = Path(model_input)
    if path.exists():
        return str(path.resolve())
    
    # Intentar resolver vía catalog o /srv/models
    srv_path = Path("/srv/models/gguf") / model_input
    if srv_path.exists():
        return str(srv_path.resolve())
    
    # Probar script de modelos si es un ID
    try:
        res = subprocess.run(
            ["python3", "scripts/models/model-download.py", "--path", model_input],
            capture_output=True, text=True
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    
    return model_input

def install_systemd(model_path: str, port: str, ngl: str):
    user = get_current_user()
    bin_path = shutil.which("llama-server") or "/usr/local/bin/llama-server"
    
    service_content = f"""[Unit]
Description=llama.cpp Server Daemon
After=network.target

[Service]
Type=simple
User={user}
ExecStart={bin_path} -m "{model_path}" --host 0.0.0.0 --port {port} -ngl {ngl} --jinja --ctx-size 4096 -n 1024
Restart=always
RestartSec=3
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
"""
    tmp_file = Path("/tmp/llama-server.service")
    tmp_file.write_text(service_content)
    
    print(f"\033[36m[INFO] Instalando servicio systemd en {SYSTEMD_PATH}...\033[0m")
    subprocess.run(["sudo", "cp", str(tmp_file), str(SYSTEMD_PATH)], check=True)
    subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
    subprocess.run(["sudo", "systemctl", "enable", "--now", "llama-server.service"], check=True)
    print("\033[32m[OK] Servicio systemd llama-server.service instalado y activado.\033[0m")

def install_launchd(model_path: str, port: str, ngl: str):
    LAUNCHD_DIR.mkdir(parents=True, exist_ok=True)
    bin_path = shutil.which("llama-server") or "/usr/local/bin/llama-server"
    
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.llama.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>{bin_path}</string>
        <string>-m</string>
        <string>{model_path}</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>{port}</string>
        <string>-ngl</string>
        <string>{ngl}</string>
        <string>--jinja</string>
        <string>--ctx-size</string>
        <string>4096</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/llama-server.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/llama-server.err</string>
</dict>
</plist>
"""
    LAUNCHD_PLIST.write_text(plist_content)
    print(f"\033[36m[INFO] Instalando servicio launchd en {LAUNCHD_PLIST}...\033[0m")
    subprocess.run(["launchctl", "unload", str(LAUNCHD_PLIST)], capture_output=True)
    subprocess.run(["launchctl", "load", "-w", str(LAUNCHD_PLIST)], check=True)
    print("\033[32m[OK] Agente launchd com.llama.server cargado exitosamente.\033[0m")

def check_status():
    system = platform.system().lower()
    if system == "linux":
        subprocess.run(["sudo", "systemctl", "status", "llama-server.service"])
    elif system == "darwin":
        res = subprocess.run(["launchctl", "list", "com.llama.server"], capture_output=True, text=True)
        if res.returncode == 0:
            print("\033[32m[RUNNING] Agente launchd com.llama.server activo:\033[0m")
            print(res.stdout)
        else:
            print("\033[33m[INACTIVE] Agente launchd com.llama.server no está cargado.\033[0m")

def stop_service():
    system = platform.system().lower()
    if system == "linux":
        subprocess.run(["sudo", "systemctl", "stop", "llama-server.service"])
        print("\033[32m[OK] Servicio systemd detenido.\033[0m")
    elif system == "darwin":
        subprocess.run(["launchctl", "unload", str(LAUNCHD_PLIST)])
        print("\033[32m[OK] Agente launchd detenido.\033[0m")

def uninstall_service():
    system = platform.system().lower()
    if system == "linux":
        subprocess.run(["sudo", "systemctl", "disable", "--now", "llama-server.service"], capture_output=True)
        if SYSTEMD_PATH.exists():
            subprocess.run(["sudo", "rm", "-f", str(SYSTEMD_PATH)])
            subprocess.run(["sudo", "systemctl", "daemon-reload"])
        print("\033[32m[OK] Servicio systemd desinstalado.\033[0m")
    elif system == "darwin":
        if LAUNCHD_PLIST.exists():
            subprocess.run(["launchctl", "unload", str(LAUNCHD_PLIST)], capture_output=True)
            LAUNCHD_PLIST.unlink()
        print("\033[32m[OK] Agente launchd desinstalado.\033[0m")

def main():
    parser = argparse.ArgumentParser(description="Gestor de servicios daemon para llama-server")
    parser.add_argument("--install", help="Ruta o ID del modelo a ejecutar")
    parser.add_argument("--port", default="8080", help="Puerto HTTP (default: 8080)")
    parser.add_argument("--ngl", default="99", help="Número de capas GPU (default: 99)")
    parser.add_argument("--status", action="store_true", help="Estado del servicio")
    parser.add_argument("--stop", action="store_true", help="Detener el servicio")
    parser.add_argument("--uninstall", action="store_true", help="Desinstalar el servicio")

    args = parser.parse_args()
    system = platform.system().lower()

    if args.install:
        model_path = resolve_model_path(args.install)
        if system == "linux":
            install_systemd(model_path, args.port, args.ngl)
        elif system == "darwin":
            install_launchd(model_path, args.port, args.ngl)
        else:
            print("\033[31m[ERROR] Sistema operativo no soportado para servicios daemon.\033[0m")
            sys.exit(1)
    elif args.status:
        check_status()
    elif args.stop:
        stop_service()
    elif args.uninstall:
        uninstall_service()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
