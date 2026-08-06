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
GPU_NGL_DEFAULT=0
if [ -f "$REPO_DIR/scripts/commons/detect_gpu.py" ] && \
   python3 "$REPO_DIR/scripts/commons/detect_gpu.py" --has-gpu-sdk 2>/dev/null; then
    GPU_NGL_DEFAULT=99
    echo "[INFO] GPU backend detectado — los wrappers usarán -ngl 99 por defecto"
else
    echo "[INFO] Sin GPU backend — los wrappers no incluirán -ngl"
fi

# --- start-server.sh ----------------------------------------------------------
cat > "$WRAPPERS_DIR/start-server.sh" << 'WRAPPER'
#!/usr/bin/env bash
# start-server.sh — Inicia llama-server con detección dinámica de parámetros
# Uso:
#   start-server.sh --model <modelo.gguf> [--port 43110] [--ctx-size 4096] [...]
#   start-server.sh <modelo.gguf> [puerto] [args-extra...]  (posicional legacy)
#
# Flags soportados:
#   -m, --model <path>      Ruta al modelo (requerido)
#   -p, --port <puerto>     Puerto (default: 43110)
#   --ctx-size <n>          Tamaño de contexto (default: auto-detectado)
#   -n, --n-predict <n>     Tokens a generar (default: 512)
#   --ngl <n>               Capas GPU (default: detectado en compilación)
#   -t, --threads <n>       Hilos (default: todos los núcleos)
#   -b, --batch-size <n>     Tamaño de lote 256|512|... (default: auto)
#   --prompt-cache <path>    Cache de prompt (default: /tmp/llama-cache-*.cache)
#   --no-cache               Desactiva el cache de prompt
#   -v, --verbose            Muestra información de detección
#   --                       Todo lo posterior pasa a llama-server
#
# Variables de entorno para override:
#   LLAMA_CTX_SIZE, LLAMA_N_PREDICT, LLAMA_NGL, LLAMA_THREADS, LLAMA_VERBOSE
set -euo pipefail

DEFAULT_PORT=43110
DEFAULT_NGL=__DEFAULT_NGL__
DEFAULT_N_PREDICT=512
PIDFILE="/tmp/llama-server-${PORT:-43110}.pid"

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

_check_intel_old_gpu() {
    local gpu_info=""
    if command -v lspci >/dev/null 2>&1; then
        gpu_info=$(lspci -d::0300 2>/dev/null || echo "")
    fi
    if [ -z "$gpu_info" ] && command -v lsgpu >/dev/null 2>&1; then
        gpu_info=$(lsgpu 2>/dev/null || echo "")
    fi
    for kw in "3rd Gen" "2nd Gen" "Ivybridge" "Sandybridge" "Haswell" "Bay Trail" "Cherry Trail"; do
        if echo "$gpu_info" | grep -qi "$kw"; then return 0; fi
    done
    return 1
}

_detect_batch_size() {
    if [ "$NGL" -gt 0 ]; then echo 512
    elif [ "$THREADS" -ge 8 ]; then echo 512
    else echo 256
    fi
}

# ── Parseo de flags (+ retrocompatibilidad posicional) ────────────────────
MODEL=""
PORT=""
NGL=""
CTX_SIZE_ARG=""
N_PREDICT_ARG=""
THREADS_ARG=""
BATCH_ARG=""
CACHE_ARG=""
VERBOSE=0
PASSTHROUGH=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        -m|--model)    MODEL="$2"; shift 2 ;;
        -p|--port)     PORT="$2"; shift 2 ;;
        --ctx-size)    CTX_SIZE_ARG="$2"; shift 2 ;;
        -n|--n-predict) N_PREDICT_ARG="$2"; shift 2 ;;
        --ngl)         NGL="$2"; shift 2 ;;
        -t|--threads)  THREADS_ARG="$2"; shift 2 ;;
        -b|--batch-size) BATCH_ARG="$2"; shift 2 ;;
        --prompt-cache) CACHE_ARG="$2"; shift 2 ;;
        --no-cache)    CACHE_ARG="none"; shift ;;
        -v|--verbose)  VERBOSE=1; shift ;;
        --)            shift; PASSTHROUGH=("$@"); break ;;
        -*)
            _llama_warn "Flag desconocido: $1"
            shift ;;
        *)
            if [ -z "$MODEL" ]; then
                MODEL="$1"
            elif [ -z "$PORT" ] && [[ "$1" =~ ^[0-9]+$ ]]; then
                PORT="$1"
            else
                PASSTHROUGH+=("$1")
            fi
            shift ;;
    esac
done

[ -z "$MODEL" ] && { _llama_warn "Especifica --model <ruta.gguf>"; exit 1; }
PORT="${PORT:-$DEFAULT_PORT}"
NGL="${LLAMA_NGL:-${NGL:-$DEFAULT_NGL}}"

# ── Runtime GPU validation: Intel Gen7- → force NGL=0 ────────────────────
if [ "$NGL" -gt 0 ] && _check_intel_old_gpu; then
    _llama_warn "GPU Intel Gen7- detectada — sin backend GPU compatible (Vulkan/OpenCL)"
    _llama_warn "Forzando NGL=0 (solo CPU)"
    NGL=0
fi

# ── Detección dinámica ────────────────────────────────────────────────────
MODEL_CTX=$(_get_model_ctx "$MODEL")
[ "$MODEL_CTX" -le 0 ] && { _llama_warn "No se pudo leer context_length del modelo; usando 4096"; MODEL_CTX=4096; }

TOTAL_MEM=$(_get_total_mem_mb)
FREE_MEM=$(_get_free_mem_mb)
[ "$VERBOSE" = "1" ] && _llama_log "RAM total: ${TOTAL_MEM}MB, libre: ${FREE_MEM}MB"

CTX_SIZE="${LLAMA_CTX_SIZE:-${CTX_SIZE_ARG:-$(_calc_safe_ctx "$MODEL_CTX" "$TOTAL_MEM" "$FREE_MEM")}}"
N_PREDICT="${LLAMA_N_PREDICT:-${N_PREDICT_ARG:-$DEFAULT_N_PREDICT}}"
THREADS="${LLAMA_THREADS:-${THREADS_ARG:-$(nproc 2>/dev/null || sysctl -n hw.logicalcpu 2>/dev/null || echo 4)}}"
BATCH="${LLAMA_BATCH_SIZE:-${BATCH_ARG:-$(_detect_batch_size)}}"
# Prompt cache: reutiliza KV cache entre sesiones (acelera cargas repetidas)
if [ "${CACHE_ARG:-}" = "none" ] || [ "${LLAMA_NO_CACHE:-0}" = "1" ]; then
    CACHE=""
else
    CACHE="${CACHE_ARG:-/tmp/llama-cache-$(basename "$MODEL" .gguf | tr '/' '_').cache}"
fi

_llama_log "Configuración:"
_llama_log "  Modelo:     $MODEL"
_llama_log "  Puerto:     $PORT"
_llama_log "  Contexto:   $CTX_SIZE (máx modelo: $MODEL_CTX)"
_llama_log "  Generación: $N_PREDICT tokens"
_llama_log "  Capas GPU:  $NGL"
_llama_log "  Hilos:      $THREADS"
_llama_log "  Batch:      $BATCH"
[ -n "$CACHE" ] && _llama_log "  Cache:      $CACHE"
[ "$VERBOSE" = "1" ] && _llama_log "  RAM total: ${TOTAL_MEM}MB  libre: ${FREE_MEM}MB"
[ "${#PASSTHROUGH[@]}" -gt 0 ] && _llama_log "  Args extra: ${PASSTHROUGH[*]}"

# ── PID y trap ─────────────────────────────────────────────────────────
# Re-definir PIDFILE con el puerto final después del parseo de flags
PIDFILE="/tmp/llama-server-${PORT}.pid"
trap "rm -f $PIDFILE" EXIT

# ── Detener instancia previa vía PID ────────────────────────────────────
if [ -f "$PIDFILE" ]; then
    old=$(cat "$PIDFILE" 2>/dev/null || echo "")
    if [ -n "$old" ] && kill -0 "$old" 2>/dev/null; then
        _llama_log "Deteniendo instancia previa (PID $old) ..."
        kill -TERM "$old"
        for _ in {1..20}; do
            kill -0 "$old" 2>/dev/null || break
            sleep 0.25
        done
        if kill -0 "$old" 2>/dev/null; then
            _llama_warn "No terminó con SIGTERM; enviando SIGKILL ..."
            kill -KILL "$old"
        fi
        rm -f "$PIDFILE"
    fi
fi

# ── Guardar PID para stop-server.sh ─────────────────────────────────────
echo $$ > "$PIDFILE"

# ── Lanzar ────────────────────────────────────────────────────────────────
exec "/opt/llama.cpp/current/bin/llama-server" \
  -m "$MODEL" \
  --host 0.0.0.0 \
  --port "$PORT" \
  -ngl "$NGL" \
  --jinja \
  --ctx-size "$CTX_SIZE" \
  -n "$N_PREDICT" \
  -tb "$BATCH" \
  -t "$THREADS" \
  $( [ -n "$CACHE" ] && echo "--prompt-cache $CACHE" ) \
  "${PASSTHROUGH[@]}"
WRAPPER

# ── Inyectar default NGL según GPU detectada ──────────────────────────────
sed -i "s|__DEFAULT_NGL__|${GPU_NGL_DEFAULT}|" "$WRAPPERS_DIR/start-server.sh"
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
  -ngl "${NGL:-__DEFAULT_NGL__}" \
  "$@"
WRAPPER

sed -i "s|__DEFAULT_NGL__|${GPU_NGL_DEFAULT}|" "$WRAPPERS_DIR/bench.sh"
chmod 755 "$WRAPPERS_DIR/bench.sh"

# --- start-server-embedding.sh -------------------------------------------------
cat > "$WRAPPERS_DIR/start-server-embedding.sh" << 'WRAPPER'
#!/usr/bin/env bash
# start-server-embedding.sh — Inicia llama-server en modo embeddings con detección dinámica
# Uso:
#   start-server-embedding.sh --model <modelo.gguf> [--pooling mean] [...]
#   start-server-embedding.sh <modelo.gguf> [puerto] [args-extra...]  (posicional legacy)
#
# Flags soportados:
#   -m, --model <path>      Ruta al modelo (requerido)
#   -p, --port <puerto>     Puerto (default: 43111)
#   --pooling <m>           Método: mean|cls|last|none|rank (default: mean)
#   --ctx-size <n>          Tamaño de contexto (default: auto-detectado)
#   --ngl <n>               Capas GPU (default: detectado en compilación)
#   -t, --threads <n>       Hilos (default: todos los núcleos)
#   -b, --batch-size <n>     Tamaño de lote 256|512|... (default: auto)
#   --prompt-cache <path>    Cache de prompt (default: /tmp/llama-cache-*.cache)
#   --no-cache               Desactiva el cache de prompt
#   -v, --verbose            Muestra información de detección
#   --                       Todo lo posterior pasa a llama-server
#
# Variables de entorno para override:
#   LLAMA_CTX_SIZE, LLAMA_NGL, LLAMA_THREADS, LLAMA_VERBOSE, POOLING
set -euo pipefail

DEFAULT_PORT=43111
DEFAULT_NGL=__DEFAULT_NGL__
DEFAULT_POOLING="mean"
PIDFILE="/tmp/llama-server-${PORT:-43111}.pid"

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

_check_intel_old_gpu() {
    local gpu_info=""
    if command -v lspci >/dev/null 2>&1; then
        gpu_info=$(lspci -d::0300 2>/dev/null || echo "")
    fi
    if [ -z "$gpu_info" ] && command -v lsgpu >/dev/null 2>&1; then
        gpu_info=$(lsgpu 2>/dev/null || echo "")
    fi
    for kw in "3rd Gen" "2nd Gen" "Ivybridge" "Sandybridge" "Haswell" "Bay Trail" "Cherry Trail"; do
        if echo "$gpu_info" | grep -qi "$kw"; then return 0; fi
    done
    return 1
}

_detect_batch_size() {
    if [ "$NGL" -gt 0 ]; then echo 512
    elif [ "$THREADS" -ge 8 ]; then echo 512
    else echo 256
    fi
}

# ── Parseo de flags (+ retrocompatibilidad posicional) ────────────────────
MODEL=""
PORT=""
NGL=""
POOLING=""
CTX_SIZE_ARG=""
THREADS_ARG=""
BATCH_ARG=""
CACHE_ARG=""
VERBOSE=0
PASSTHROUGH=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        -m|--model)    MODEL="$2"; shift 2 ;;
        -p|--port)     PORT="$2"; shift 2 ;;
        --pooling)     POOLING="$2"; shift 2 ;;
        --ctx-size)    CTX_SIZE_ARG="$2"; shift 2 ;;
        --ngl)         NGL="$2"; shift 2 ;;
        -t|--threads)  THREADS_ARG="$2"; shift 2 ;;
        -b|--batch-size) BATCH_ARG="$2"; shift 2 ;;
        --prompt-cache) CACHE_ARG="$2"; shift 2 ;;
        --no-cache)    CACHE_ARG="none"; shift ;;
        -v|--verbose)  VERBOSE=1; shift ;;
        --)            shift; PASSTHROUGH=("$@"); break ;;
        -*)
            _llama_warn "Flag desconocido: $1"
            shift ;;
        *)
            if [ -z "$MODEL" ]; then
                MODEL="$1"
            elif [ -z "$PORT" ] && [[ "$1" =~ ^[0-9]+$ ]]; then
                PORT="$1"
            else
                PASSTHROUGH+=("$1")
            fi
            shift ;;
    esac
done

[ -z "$MODEL" ] && { _llama_warn "Especifica --model <ruta.gguf>"; exit 1; }
PORT="${PORT:-$DEFAULT_PORT}"
NGL="${LLAMA_NGL:-${NGL:-$DEFAULT_NGL}}"
POOLING="${POOLING:-$DEFAULT_POOLING}"

# ── Runtime GPU validation: Intel Gen7- → force NGL=0 ────────────────────
if [ "$NGL" -gt 0 ] && _check_intel_old_gpu; then
    _llama_warn "GPU Intel Gen7- detectada — sin backend GPU compatible (Vulkan/OpenCL)"
    _llama_warn "Forzando NGL=0 (solo CPU)"
    NGL=0
fi

# ── Detección dinámica ────────────────────────────────────────────────────
MODEL_CTX=$(_get_model_ctx "$MODEL")
[ "$MODEL_CTX" -le 0 ] && { _llama_warn "No se pudo leer context_length del modelo; usando 4096"; MODEL_CTX=4096; }

TOTAL_MEM=$(_get_total_mem_mb)
FREE_MEM=$(_get_free_mem_mb)
[ "$VERBOSE" = "1" ] && _llama_log "RAM total: ${TOTAL_MEM}MB, libre: ${FREE_MEM}MB"

CTX_SIZE="${LLAMA_CTX_SIZE:-${CTX_SIZE_ARG:-$(_calc_safe_ctx "$MODEL_CTX" "$TOTAL_MEM" "$FREE_MEM")}}"
THREADS="${LLAMA_THREADS:-${THREADS_ARG:-$(nproc 2>/dev/null || sysctl -n hw.logicalcpu 2>/dev/null || echo 4)}}"
BATCH="${LLAMA_BATCH_SIZE:-${BATCH_ARG:-$(_detect_batch_size)}}"
if [ "${CACHE_ARG:-}" = "none" ] || [ "${LLAMA_NO_CACHE:-0}" = "1" ]; then
    CACHE=""
else
    CACHE="${CACHE_ARG:-/tmp/llama-cache-$(basename "$MODEL" .gguf | tr '/' '_').cache}"
fi

_llama_log "Configuración:"
_llama_log "  Modelo:     $MODEL"
_llama_log "  Puerto:     $PORT"
_llama_log "  Contexto:   $CTX_SIZE (máx modelo: $MODEL_CTX)"
_llama_log "  Pooling:    $POOLING"
_llama_log "  Capas GPU:  $NGL"
_llama_log "  Hilos:      $THREADS"
_llama_log "  Batch:      $BATCH"
[ -n "$CACHE" ] && _llama_log "  Cache:      $CACHE"
[ "$VERBOSE" = "1" ] && _llama_log "  RAM total: ${TOTAL_MEM}MB  libre: ${FREE_MEM}MB"
[ "${#PASSTHROUGH[@]}" -gt 0 ] && _llama_log "  Args extra: ${PASSTHROUGH[*]}"

# ── PID y trap ─────────────────────────────────────────────────────────
PIDFILE="/tmp/llama-server-${PORT}.pid"
trap "rm -f $PIDFILE" EXIT
echo $$ > "$PIDFILE"

# ── Lanzar ────────────────────────────────────────────────────────────────
exec "/opt/llama.cpp/current/bin/llama-server" \
  -m "$MODEL" \
  --host 0.0.0.0 \
  --port "$PORT" \
  -ngl "$NGL" \
  --embeddings \
  --pooling "$POOLING" \
  --ctx-size "$CTX_SIZE" \
  -tb "$BATCH" \
  -t "$THREADS" \
  $( [ -n "$CACHE" ] && echo "--prompt-cache $CACHE" ) \
  "${PASSTHROUGH[@]}"
WRAPPER

sed -i "s|__DEFAULT_NGL__|${GPU_NGL_DEFAULT}|" "$WRAPPERS_DIR/start-server-embedding.sh"
chmod 755 "$WRAPPERS_DIR/start-server-embedding.sh"

# --- stop-server.sh ------------------------------------------------------------
cat > "$WRAPPERS_DIR/stop-server.sh" << 'WRAPPER'
#!/usr/bin/env bash
# stop-server.sh — Detiene instancias de llama.cpp vía PID o por nombre
# Uso:
#   stop-server.sh                    → PIDs de /tmp/llama-server-*.pid
#   stop-server.sh --port 43110       → PID del puerto específico
#   stop-server.sh --pid /path/file   → PID file explícito
#   stop-server.sh --all --force      → todos los procesos + SIGKILL
set -euo pipefail

FORCE=0 ALL=0 PIDFILE="" killed=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --force) FORCE=1; shift ;;
        --all)   ALL=1; shift ;;
        --port)  PIDFILE="/tmp/llama-server-$2.pid"; shift 2 ;;
        --pid)   PIDFILE="$2"; shift 2 ;;
        -h|--help)
            echo "Uso: stop-server.sh [--force] [--port N] [--pid FILE] [--all]"
            exit 0 ;;
        *) shift ;;
    esac
done

_stop_pid() {
    local p="$1" f="$2"
    if [ -n "$p" ] && kill -0 "$p" 2>/dev/null; then
        echo "[INFO] Deteniendo PID $p ..."
        kill -TERM "$p"
        killed=1
    fi
    rm -f "$f"
}

# PID específico o por puerto
if [ -n "$PIDFILE" ]; then
    [ -f "$PIDFILE" ] && _stop_pid "$(cat "$PIDFILE")" "$PIDFILE"
elif [ "$ALL" -ne 1 ]; then
    for pf in /tmp/llama-server-*.pid; do
        [ -f "$pf" ] || continue
        _stop_pid "$(cat "$pf")" "$pf"
    done
fi

# Limpieza por nombre si --all o si no se encontraron PIDs
if [ "$ALL" -eq 1 ] || [ "$killed" -eq 0 ]; then
    for proc in llama-server llama-cli llama-bench; do
        if pgrep -x "$proc" >/dev/null 2>&1; then
            [ "$ALL" -ne 1 ] && echo "[INFO] Limpiando $proc huérfano ..."
            pkill -TERM -x "$proc"
            killed=1
        fi
    done
fi

[ "$killed" -eq 0 ] && { echo "[INFO] No hay procesos llama.cpp activos."; exit 0; }

for _ in {1..20}; do
    pgrep -f "llama-" >/dev/null 2>&1 || { echo "[OK] Detenido."; exit 0; }
    sleep 0.25
done

if [ "$FORCE" -eq 1 ]; then
    echo "[WARN] SIGKILL a procesos restantes ..."
    pkill -KILL -f "llama-"
else
    echo "[WARN] Algunos procesos no terminaron. Usa --force."
    exit 1
fi
WRAPPER
chmod 755 "$WRAPPERS_DIR/stop-server.sh"

echo "Wrappers generados en $WRAPPERS_DIR"
