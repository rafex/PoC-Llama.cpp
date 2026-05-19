# =============================================================================
# justfile — task manager y punto de entrada para el desarrollador
#
# Responsabilidades: orquestar flujos, llamar scripts, invocar make.
# PROHIBIDO: duplicar lógica de Makefile o reimplementar compilación/builds.
#
# Uso:
#   just           — muestra ayuda
#   just setup     — flujo completo: clone → compile → install → post-install
#   just run <model.gguf>  — inicia llama-server con el modelo dado
# =============================================================================

set shell := ["bash", "-euo", "pipefail", "-c"]
set dotenv-load := false

import "scripts/commons/commons.just"
import "scripts/build/build.just"
import "scripts/install/install.just"
import "scripts/post-install/post-install.just"
import "scripts/debug/debug.just"
import "scripts/uninstall/uninstall.just"

# Muestra ayuda por defecto
default:
    @just --list --unsorted

# =============================================================================
# Flujos de alto nivel
# =============================================================================

# Flujo completo de primera instalación
setup: check-deps clone compile install post-install
    @echo ""
    @echo "[OK] Setup completo. Versión instalada:"
    @just install-list

# Flujo de actualización a nueva versión
upgrade: clone compile install post-install install-symlinks
    @echo ""
    @echo "[OK] Upgrade completado."
    @just install-list

# =============================================================================
# Runtime
# =============================================================================

# Inicia llama-server con el modelo especificado
run model port="8080":
    @echo "[INFO] Iniciando llama-server con {{model}} en puerto {{port}} ..."
    llama-server \
      -m "{{model}}" \
      --host 0.0.0.0 \
      --port {{port}} \
      -c 4096 \
      -t "$(nproc 2>/dev/null || sysctl -n hw.logicalcpu)"

# Inicia llama-cli en modo interactivo con el modelo especificado
chat model:
    @echo "[INFO] Iniciando llama-cli con {{model}} ..."
    llama-cli \
      -m "{{model}}" \
      --interactive \
      -c 4096

# Ejecuta benchmark sobre el modelo especificado
bench model:
    llama-bench -m "{{model}}"

# =============================================================================
# Utilidades
# =============================================================================

# Lista modelos .gguf disponibles en /srv/models
models:
    @find /srv/models -name "*.gguf" 2>/dev/null | sort || echo "(sin modelos en /srv/models)"

# Cambia la versión activa de llama.cpp (uso: just switch-version 2026.05.18-x86_64)
switch-version version:
    @echo "[INFO] Cambiando versión activa a {{version}} ..."
    sudo ln -sfn "/opt/llama.cpp/versions/{{version}}" /opt/llama.cpp/current
    @just install-symlinks
    @echo "[OK] Versión activa: $(readlink /opt/llama.cpp/current)"
