#!/usr/bin/env bash
# generate-wrappers.sh — crea wrappers semánticos en el directorio de la versión
# Uso: sudo bash scripts/post-install/generate-wrappers.sh <install_dir> <install_current>
set -euo pipefail

INSTALL_DIR="${1:?Falta INSTALL_DIR}"
INSTALL_CURRENT="${2:?Falta INSTALL_CURRENT}"
WRAPPERS_DIR="$INSTALL_DIR/scripts"

mkdir -p "$WRAPPERS_DIR"

# --- start-server.sh ----------------------------------------------------------
cat > "$WRAPPERS_DIR/start-server.sh" << 'WRAPPER'
#!/usr/bin/env bash
# Inicia llama-server con el modelo indicado.
# Uso: start-server.sh <ruta-al-modelo.gguf> [puerto] [args-extra...]
set -euo pipefail
MODEL="${1:?Especifica la ruta al modelo .gguf}"
PORT="${2:-8080}"
shift || true
shift || true
THREADS="$(nproc 2>/dev/null || sysctl -n hw.logicalcpu)"

if pgrep -x llama-server >/dev/null 2>&1; then
  echo "[INFO] Deteniendo llama-server activo ..."
  pkill -TERM -x llama-server
  for _ in {1..20}; do
    pgrep -x llama-server >/dev/null 2>&1 || break
    sleep 0.25
  done
  if pgrep -x llama-server >/dev/null 2>&1; then
    echo "[WARN] llama-server no terminó con SIGTERM; enviando SIGKILL ..."
    pkill -KILL -x llama-server
  fi
fi

exec "/opt/llama.cpp/current/bin/llama-server" \
  -m "$MODEL" \
  --host 0.0.0.0 \
  --port "$PORT" \
  --jinja \
  --ctx-size 4096 \
  -n 1024 \
  -t "$THREADS" \
  "$@"
WRAPPER
chmod 755 "$WRAPPERS_DIR/start-server.sh"

# --- bench.sh -----------------------------------------------------------------
cat > "$WRAPPERS_DIR/bench.sh" << 'WRAPPER'
#!/usr/bin/env bash
# Benchmark rápido del modelo indicado.
# Uso: bench.sh <ruta-al-modelo.gguf>
set -euo pipefail
MODEL="${1:?Especifica la ruta al modelo .gguf}"
exec "/opt/llama.cpp/current/bin/llama-bench" -m "$MODEL"
WRAPPER
chmod 755 "$WRAPPERS_DIR/bench.sh"

echo "Wrappers generados en $WRAPPERS_DIR"
