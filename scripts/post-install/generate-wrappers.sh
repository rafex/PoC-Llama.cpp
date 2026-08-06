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
# start-server.sh — Inicia llama-server con detección dinámica de parámetros
# Uso: start-server.sh <ruta-modelo.gguf> [puerto] [args-extra...]
#
# Variables de entorno para override:
#   LLAMA_CTX_SIZE    — tamaño de contexto (default: auto-detectado)
#   LLAMA_N_PREDICT   — tokens máximos a generar (default: 512)
#   LLAMA_NGL         — capas GPU (default: 99 si GPU disponible)
#   LLAMA_THREADS     — número de hilos (default: todos los núcleos)
#   LLAMA_VERBOSE     — =1 muestra información de detección
set -euo pipefail

# ── Funciones auxiliares ──────────────────────────────────────────────────
_llama_log()   { echo "[INFO] $*"; }
_llama_warn()  { echo "[WARN] $*" >&2; }

_get_model_ctx() {
    local model="$1" ctx=0
    if command -v llama-gguf >/dev/null 2>&1; then
        ctx=$(llama-gguf info "$model" 2>/dev/null | grep -i "context_length" | head -1 | awk '{print $NF}')
    fi
    if [ -z "$ctx" ] || [ "$ctx" -le 0 ]; then
        local sd; sd="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        [ -x "$sd/llama-gguf" ] && ctx=$("$sd/llama-gguf" info "$model" 2>/dev/null | grep -i "context_length" | head -1 | awk '{print $NF}')
    fi
    echo "${ctx:-0}"
}

_get_total_mem_mb() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        awk '/MemTotal/ {printf "%.0f", $2/1024}' /proc/meminfo
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        sysctl -n hw.memsize 2>/dev/null | awk '{printf "%.0f", $1/1024/1024}'
    else
        echo 4096
    fi
}

_get_free_mem_mb() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        awk '/MemAvailable/ {printf "%.0f", $2/1024}' /proc/meminfo
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        vm_stat 2>/dev/null | awk '/free/ {f=$3} /inactive/ {i=$3} END {printf "%.0f", (f+i)*4096/1024/1024}'
    else
        echo 1024
    fi
}

_calc_safe_ctx() {
    local model_ctx="$1" total_mem="$2" free_mem="$3"
    local model_size_mb=0 kv_per_1k=15 mbytes=15
    [ -f "$MODEL" ] && model_size_mb=$(du -m "$MODEL" 2>/dev/null | cut -f1)
    [ -z "$model_size_mb" ] && model_size_mb=0

    # Modelo cargado ≈ archivo + 20%
    local model_load_mb=$(( model_size_mb * 12 / 10 ))
    # Aproximación de KV cache: ~15 bytes por token (conservador para Q4)
    # = 15 MB / 1000 tokens
    local avail_mb=$(( free_mem - 256 - model_load_mb ))
    [ "$avail_mb" -lt 0 ] && avail_mb=0
    local max_ctx_by_mem=$(( avail_mb * 1000 / mbytes ))
    [ "$max_ctx_by_mem" -lt 512 ] && max_ctx_by_mem=512

    local safe=$max_ctx_by_mem
    [ "$model_ctx" -gt 0 ] && [ "$model_ctx" -lt "$safe" ] && safe=$model_ctx

    # Redondear a múltiplos de 1024 (>2048) o 256 (<=2048)
    if [ "$safe" -gt 2048 ]; then
        safe=$(( (safe + 1023) / 1024 * 1024 ))
    else
        safe=$(( (safe + 255) / 256 * 256 ))
    fi
    [ "$safe" -gt 8192 ] && safe=8192
    echo "$safe"
}

# ── Argumentos ────────────────────────────────────────────────────────────
MODEL="${1:?Especifica la ruta al modelo .gguf}"
PORT="${2:-43110}"
shift || true; shift || true

# ── Detección dinámica ────────────────────────────────────────────────────
MODEL_CTX=$(_get_model_ctx "$MODEL")
[ "$MODEL_CTX" -le 0 ] && { _llama_warn "No se pudo leer context_length del modelo; usando 4096"; MODEL_CTX=4096; }

TOTAL_MEM=$(_get_total_mem_mb)
FREE_MEM=$(_get_free_mem_mb)
[ "${LLAMA_VERBOSE:-0}" = "1" ] && _llama_log "RAM total: ${TOTAL_MEM}MB, libre: ${FREE_MEM}MB"

CTX_SIZE="${LLAMA_CTX_SIZE:-$(_calc_safe_ctx "$MODEL_CTX" "$TOTAL_MEM" "$FREE_MEM")}"
N_PREDICT="${LLAMA_N_PREDICT:-512}"
THREADS="${LLAMA_THREADS:-$(nproc 2>/dev/null || sysctl -n hw.logicalcpu 2>/dev/null || echo 4)}"

_llama_log "Configuración:"
_llama_log "  Modelo:     $MODEL"
_llama_log "  Puerto:     $PORT"
_llama_log "  Contexto:   $CTX_SIZE (máx modelo: $MODEL_CTX)"
_llama_log "  Generación: $N_PREDICT tokens"
_llama_log "  Hilos:      $THREADS"
[ "${LLAMA_VERBOSE:-0}" = "1" ] && _llama_log "  RAM total: ${TOTAL_MEM}MB  libre: ${FREE_MEM}MB"
[ $# -gt 0 ] && _llama_log "  Args extra: $*"

# ── Detener instancia previa ──────────────────────────────────────────────
if pgrep -x llama-server >/dev/null 2>&1; then
    _llama_log "Deteniendo llama-server activo ..."
    pkill -TERM -x llama-server
    for _ in {1..20}; do
        pgrep -x llama-server >/dev/null 2>&1 || break
        sleep 0.25
    done
    if pgrep -x llama-server >/dev/null 2>&1; then
        _llama_warn "No terminó con SIGTERM; enviando SIGKILL ..."
        pkill -KILL -x llama-server
    fi
fi

# ── Lanzar ────────────────────────────────────────────────────────────────
exec "/opt/llama.cpp/current/bin/llama-server" \
  -m "$MODEL" \
  --host 0.0.0.0 \
  --port "$PORT" \
#__GPU_NGL_PLACEHOLDER__
  --jinja \
  --ctx-size "$CTX_SIZE" \
  -n "$N_PREDICT" \
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
# start-server-embedding.sh — Inicia llama-server en modo embeddings con detección dinámica
# Uso: start-server-embedding.sh <ruta-modelo.gguf> [puerto] [args-extra...]
#
# Variables de entorno para override:
#   LLAMA_CTX_SIZE    — tamaño de contexto (default: auto-detectado)
#   LLAMA_NGL         — capas GPU (default: 99 si GPU disponible)
#   LLAMA_THREADS     — número de hilos (default: todos los núcleos)
#   LLAMA_VERBOSE     — =1 muestra información de detección
#   POOLING           — método de pooling: mean|cls|last|none|rank (default: mean)
set -euo pipefail

# ── Funciones auxiliares ──────────────────────────────────────────────────
_llama_log()   { echo "[INFO] $*"; }
_llama_warn()  { echo "[WARN] $*" >&2; }

_get_model_ctx() {
    local model="$1" ctx=0
    if command -v llama-gguf >/dev/null 2>&1; then
        ctx=$(llama-gguf info "$model" 2>/dev/null | grep -i "context_length" | head -1 | awk '{print $NF}')
    fi
    if [ -z "$ctx" ] || [ "$ctx" -le 0 ]; then
        local sd; sd="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        [ -x "$sd/llama-gguf" ] && ctx=$("$sd/llama-gguf" info "$model" 2>/dev/null | grep -i "context_length" | head -1 | awk '{print $NF}')
    fi
    echo "${ctx:-0}"
}

_get_total_mem_mb() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        awk '/MemTotal/ {printf "%.0f", $2/1024}' /proc/meminfo
    else
        echo 4096
    fi
}

_get_free_mem_mb() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        awk '/MemAvailable/ {printf "%.0f", $2/1024}' /proc/meminfo
    else
        echo 1024
    fi
}

_calc_safe_ctx() {
    local model_ctx="$1" total_mem="$2" free_mem="$3"
    local model_size_mb=0 mbytes=15
    [ -f "$MODEL" ] && model_size_mb=$(du -m "$MODEL" 2>/dev/null | cut -f1)
    [ -z "$model_size_mb" ] && model_size_mb=0

    local model_load_mb=$(( model_size_mb * 12 / 10 ))
    local avail_mb=$(( free_mem - 256 - model_load_mb ))
    [ "$avail_mb" -lt 0 ] && avail_mb=0
    local max_ctx_by_mem=$(( avail_mb * 1000 / mbytes ))
    [ "$max_ctx_by_mem" -lt 512 ] && max_ctx_by_mem=512

    local safe=$max_ctx_by_mem
    [ "$model_ctx" -gt 0 ] && [ "$model_ctx" -lt "$safe" ] && safe=$model_ctx

    if [ "$safe" -gt 2048 ]; then
        safe=$(( (safe + 1023) / 1024 * 1024 ))
    else
        safe=$(( (safe + 255) / 256 * 256 ))
    fi
    [ "$safe" -gt 8192 ] && safe=8192
    echo "$safe"
}

# ── Argumentos ────────────────────────────────────────────────────────────
MODEL="${1:?Especifica la ruta al modelo .gguf}"
PORT="${2:-43111}"
shift || true; shift || true

# ── Detección dinámica ────────────────────────────────────────────────────
MODEL_CTX=$(_get_model_ctx "$MODEL")
[ "$MODEL_CTX" -le 0 ] && { _llama_warn "No se pudo leer context_length del modelo; usando 4096"; MODEL_CTX=4096; }

TOTAL_MEM=$(_get_total_mem_mb)
FREE_MEM=$(_get_free_mem_mb)
[ "${LLAMA_VERBOSE:-0}" = "1" ] && _llama_log "RAM total: ${TOTAL_MEM}MB, libre: ${FREE_MEM}MB"

CTX_SIZE="${LLAMA_CTX_SIZE:-$(_calc_safe_ctx "$MODEL_CTX" "$TOTAL_MEM" "$FREE_MEM")}"
THREADS="${LLAMA_THREADS:-$(nproc 2>/dev/null || sysctl -n hw.logicalcpu 2>/dev/null || echo 4)}"

_llama_log "Configuración:"
_llama_log "  Modelo:     $MODEL"
_llama_log "  Puerto:     $PORT"
_llama_log "  Contexto:   $CTX_SIZE (máx modelo: $MODEL_CTX)"
_llama_log "  Pooling:    ${POOLING:-mean}"
_llama_log "  Hilos:      $THREADS"
[ $# -gt 0 ] && _llama_log "  Args extra: $*"

# ── Lanzar ────────────────────────────────────────────────────────────────
exec "/opt/llama.cpp/current/bin/llama-server" \
  -m "$MODEL" \
  --host 0.0.0.0 \
  --port "$PORT" \
#__GPU_NGL_PLACEHOLDER__
  --embeddings \
  --pooling "${POOLING:-mean}" \
  --ctx-size "$CTX_SIZE" \
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
