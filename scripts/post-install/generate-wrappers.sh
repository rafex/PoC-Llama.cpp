#!/usr/bin/env bash
# generate-wrappers.sh — crea wrappers semánticos en el directorio de la versión
# Uso: sudo bash scripts/post-install/generate-wrappers.sh <install_dir> <install_current>
set -euo pipefail

INSTALL_DIR="${1:?Falta INSTALL_DIR}"
INSTALL_CURRENT="${2:?Falta INSTALL_CURRENT}"
WRAPPERS_DIR="$INSTALL_DIR/scripts"
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

mkdir -p "$WRAPPERS_DIR"

# ── Detectar soporte GPU para incluir -ngl en los wrappers ──────────────────
GPU_NGL_LINE=""
if [ -f "$REPO_DIR/scripts/commons/detect_gpu.py" ] && \
   python3 "$REPO_DIR/scripts/commons/detect_gpu.py" --has-gpu-sdk 2>/dev/null; then
    GPU_NGL_LINE='  -ngl "${NGL:-99}" \\'
    echo "[INFO] GPU backend detectado — los wrappers usarán -ngl 99 por defecto"
else
    echo "[INFO] Sin GPU backend — los wrappers no incluirán -ngl"
fi

# --- start-server.sh ----------------------------------------------------------
cat > "$WRAPPERS_DIR/start-server.sh" << 'WRAPPER'
#!/usr/bin/env bash
# Inicia llama-server con el modelo indicado.
# Uso: start-server.sh <ruta-al-modelo.gguf> [puerto] [args-extra...]
# Para desactivar GPU: NGL=0 start-server.sh ...
set -euo pipefail
MODEL="${1:?Especifica la ruta al modelo .gguf}"
PORT="${2:-43110}"
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
#__GPU_NGL_PLACEHOLDER__
  --jinja \
  --ctx-size 4096 \
  -n 1024 \
  -t "$THREADS" \
  "$@"
WRAPPER

# ── Inyectar -ngl si GPU detectada ──────────────────────────────────────────
if [ -n "$GPU_NGL_LINE" ]; then
    sed -i "s|#__GPU_NGL_PLACEHOLDER__|${GPU_NGL_LINE}|" "$WRAPPERS_DIR/start-server.sh"
else
    sed -i '/#__GPU_NGL_PLACEHOLDER__/d' "$WRAPPERS_DIR/start-server.sh"
fi
chmod 755 "$WRAPPERS_DIR/start-server.sh"

# --- bench.sh -----------------------------------------------------------------
cat > "$WRAPPERS_DIR/bench.sh" << 'WRAPPER'
#!/usr/bin/env bash
# Benchmark rápido del modelo indicado.
# Uso: bench.sh <ruta-al-modelo.gguf>
set -euo pipefail
MODEL="${1:?Especifica la ruta al modelo .gguf}"
exec "/opt/llama.cpp/current/bin/llama-bench" \
  -m "$MODEL" \
#__GPU_NGL_PLACEHOLDER__
  "$@"
WRAPPER

# ── Inyectar -ngl si GPU detectada ──────────────────────────────────────────
if [ -n "$GPU_NGL_LINE" ]; then
    sed -i "s|#__GPU_NGL_PLACEHOLDER__|${GPU_NGL_LINE}|" "$WRAPPERS_DIR/bench.sh"
else
    sed -i '/#__GPU_NGL_PLACEHOLDER__/d' "$WRAPPERS_DIR/bench.sh"
fi
chmod 755 "$WRAPPERS_DIR/bench.sh"

# --- start-server-embedding.sh -------------------------------------------------
cat > "$WRAPPERS_DIR/start-server-embedding.sh" << 'WRAPPER'
#!/usr/bin/env bash
# Inicia llama-server en modo exclusivo embeddings.
# Uso: start-server-embedding.sh <ruta-modelo.gguf> [puerto] [args-extra...]
#   POOLING=last start-server-embedding.sh ...  → cambia pooling (default: mean)
#   NGL=0 start-server-embedding.sh ...         → desactiva GPU
set -euo pipefail
MODEL="${1:?Especifica la ruta al modelo .gguf}"
PORT="${2:-43111}"
shift || true; shift || true
THREADS="$(nproc 2>/dev/null || sysctl -n hw.logicalcpu)"
exec "/opt/llama.cpp/current/bin/llama-server" \
  -m "$MODEL" \
  --host 0.0.0.0 \
  --port "$PORT" \
#__GPU_NGL_PLACEHOLDER__
  --embeddings \
  --pooling "${POOLING:-mean}" \
  -t "$THREADS" \
  "$@"
WRAPPER

# ── Inyectar -ngl si GPU detectada ──────────────────────────────────────────
if [ -n "$GPU_NGL_LINE" ]; then
    sed -i "s|#__GPU_NGL_PLACEHOLDER__|${GPU_NGL_LINE}|" "$WRAPPERS_DIR/start-server-embedding.sh"
else
    sed -i '/#__GPU_NGL_PLACEHOLDER__/d' "$WRAPPERS_DIR/start-server-embedding.sh"
fi
chmod 755 "$WRAPPERS_DIR/start-server-embedding.sh"

echo "Wrappers generados en $WRAPPERS_DIR"
