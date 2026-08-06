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
#   just run-id <id>       — inicia llama-server con un modelo del catálogo
# =============================================================================

set shell := ["bash", "-euo", "pipefail", "-c"]
set dotenv-load := false

import "scripts/commons/commons.just"
import "scripts/build/build.just"
import "scripts/install/install.just"
import "scripts/post-install/post-install.just"
import "scripts/test/test.just"
import "scripts/models/models.just"
import "scripts/debug/debug.just"
import "scripts/uninstall/uninstall.just"

# Muestra ayuda por defecto
default:
    @just --list --unsorted

# =============================================================================
# Flujos de alto nivel
# =============================================================================

# Flujo completo de primera instalación (detección automática de plataforma)
setup: check-deps clone compile install post-install
    @echo ""
    @echo "[OK] Setup completo. Versión instalada:"
    @just install-list

# Flujo completo con perfil explícito (uso: just setup-profile apple/macmini6.2)
# Si los binarios ya existen en build-out, omite la compilación.
setup-profile profile:
    just check-deps {{profile}}
    just clone
    just _compile-if-needed {{profile}}
    make install PROFILE={{profile}}
    make post-install
    make test
    @echo ""
    @echo "[OK] Setup con perfil {{profile}} completado."
    @just install-list

# Flujo de actualización a nueva versión (detección automática)
upgrade: clone compile install post-install install-symlinks
    @echo ""
    @echo "[OK] Upgrade completado."
    @just install-list

# Upgrade con perfil explícito — siempre recompila para obtener código nuevo
upgrade-profile profile:
    just check-deps {{profile}}
    just clone
    make compile PROFILE={{profile}}
    make install PROFILE={{profile}}
    make post-install
    make install-symlinks
    @echo ""
    @echo "[OK] Upgrade con perfil {{profile}} completado."
    @just install-list

# Compila solo si los binarios no existen en build-out (evita recompilar si ya terminó)
[private]
_compile-if-needed profile:
    #!/usr/bin/env bash
    set -euo pipefail
    build_bin="{{llama_build_dir}}/bin"
    if [[ -f "$build_bin/llama-cli" || -f "$build_bin/llama-server" ]]; then
        echo "[INFO] Binarios ya compilados en $build_bin — saltando compilación."
        echo "[INFO] Usa 'just upgrade-profile {{profile}}' para forzar recompilación."
    else
        make compile PROFILE={{profile}}
    fi

# =============================================================================
# Runtime
# =============================================================================

# Detiene cualquier llama-server activo
stop-server:
    #!/usr/bin/env bash
    set -euo pipefail
    if pgrep -x llama-server >/dev/null 2>&1; then
        echo "[INFO] Deteniendo llama-server activo ..."
        pkill -TERM -x llama-server
        for _ in {1..20}; do
            pgrep -x llama-server >/dev/null 2>&1 || exit 0
            sleep 0.25
        done
        echo "[WARN] llama-server no terminó con SIGTERM; enviando SIGKILL ..."
        pkill -KILL -x llama-server
    else
        echo "[INFO] No hay llama-server activo."
    fi

# Inicia llama-server con el modelo especificado y número opcional de capas GPU (ngl="99")
run model port="8080" ngl="99":
    just stop-server
    @echo "[INFO] Iniciando llama-server con {{model}} en puerto {{port}} (capas GPU ngl={{ngl}}) ..."
    llama-server \
      -m "{{model}}" \
      --host 0.0.0.0 \
      --port {{port}} \
      -ngl {{ngl}} \
      --jinja \
      --ctx-size 4096 \
      -n 1024 \
      -t "$(nproc 2>/dev/null || sysctl -n hw.logicalcpu)"

# Inicia llama-server con un modelo del catálogo por ID
run-id id port="8080" ngl="99":
    #!/usr/bin/env bash
    set -euo pipefail
    model="$(python3 scripts/models/model-download.py --path "{{id}}")"
    just run "$model" "{{port}}" "{{ngl}}"

# Inicia llama-cli en modo interactivo con el modelo especificado y capas GPU
chat model ngl="99":
    @echo "[INFO] Iniciando llama-cli con {{model}} (ngl={{ngl}}) ..."
    llama-cli \
      -m "{{model}}" \
      -ngl {{ngl}} \
      --interactive \
      -c 4096

# Diagnóstico de GPU y backends de aceleración soportados
gpu-info:
    @python3 scripts/commons/detect-gpu.py


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
