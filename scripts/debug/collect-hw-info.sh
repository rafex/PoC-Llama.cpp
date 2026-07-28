#!/usr/bin/env bash
# =============================================================================
# collect-hw-info.sh — Detecta hardware en Linux y genera TOML para PoC-Llama.cpp
#
# Genera la información mínima del equipo en formato TOML lista para compartir
# con el mantenedor del proyecto. No requiere dependencias externas.
#
# Uso:
#   bash scripts/debug/collect-hw-info.sh
#   bash scripts/debug/collect-hw-info.sh > mi-equipo.toml
# =============================================================================
set -euo pipefail

RED='\033[31m'
GREEN='\033[32m'
YELLOW='\033[33m'
CYAN='\033[36m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

header()  { printf "\n${BOLD}%s${RESET}\n" "$1"; }
info()    { printf "${DIM}# %s${RESET}\n" "$1"; }
warn()    { printf "${YELLOW}[!] %s${RESET}\n" "$1" >&2; }

# ─────────────────────────────────────────────────────────────────────────────
# Detección de hardware
# ─────────────────────────────────────────────────────────────────────────────

# Fabricante / Modelo (requiere dmidecode con sudo)
manufacturer="unknown"
product="unknown"
if command -v dmidecode &>/dev/null; then
    manufacturer=$(sudo dmidecode -s system-manufacturer 2>/dev/null || echo "unknown")
    product=$(sudo dmidecode -s system-product-name 2>/dev/null || echo "unknown")
else
    warn "dmidecode no instalado — fabricante/modelo en 'unknown'"
    info "Instálalo: sudo apt-get install -y dmidecode  (y ejecuta sudo dmidecode -s system-manufacturer)"
fi

# CPU model
cpu_model="unknown"
if [ -f /proc/cpuinfo ]; then
    cpu_model=$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | sed 's/^[[:space:]]*//' 2>/dev/null || echo "unknown")
fi

# CPU cores
logical_cpus=$(nproc 2>/dev/null || echo 1)
physical_cores=$(grep -m1 'cpu cores' /proc/cpuinfo 2>/dev/null | awk '{print $NF}' || echo "$logical_cpus")

# Vendor
cpu_vendor="unknown"
if [ -f /proc/cpuinfo ]; then
    vendor_raw=$(grep -m1 vendor_id /proc/cpuinfo 2>/dev/null | awk '{print $NF}' || echo "")
    case "$vendor_raw" in
        GenuineIntel) cpu_vendor="intel" ;;
        AuthenticAMD) cpu_vendor="amd"   ;;
        *)           cpu_vendor="unknown" ;;
    esac
fi

# Flags SIMD (x86)
flags=""
if [ -f /proc/cpuinfo ]; then
    flags=$(grep -m1 flags /proc/cpuinfo 2>/dev/null | cut -d: -f2 || echo "")
fi

has_flag() { echo "$flags" | grep -qw "$1" && echo "true" || echo "false"; }

# ─────────────────────────────────────────────────────────────────────────────
# Salida TOML
# ─────────────────────────────────────────────────────────────────────────────

cat <<EOF
# =============================================================================
# Perfil de hardware — generado automáticamente por collect-hw-info.sh
# Proyecto: PoC-Llama.cpp
# Fecha:     $(date +%Y-%m-%d)
# Hostname:  $(hostname)
# =============================================================================

[hardware]
manufacturer   = "${manufacturer}"
product        = "${product}"
cpu_model      = "${cpu_model}"
logical_cpus   = ${logical_cpus}
physical_cores = ${physical_cores}
os             = "linux"

[build]
jobs      = ${logical_cpus}
type      = "Release"

[cpu]
vendor = "${cpu_vendor}"

[cpu.simd]
sse41  = $(has_flag sse4_1)
sse42  = $(has_flag sse4_2)
avx    = $(has_flag 'avx ')
avx2   = $(has_flag avx2)
f16c   = $(has_flag f16c)
fma    = $(has_flag fma)
bmi1   = $(has_flag bmi1)
bmi2   = $(has_flag bmi2)
avx512 = $(has_flag avx512f)
neon   = $(has_flag neon)
sve    = $(has_flag sve)
crc32  = $(has_flag crc32)

[dependencies]
commands     = ["git", "cmake", "gcc", "g++", "pkg-config"]
pkg_config   = ["openblas", "openssl"]
apt_packages = ["build-essential", "cmake", "git", "libopenblas-dev", "libssl-dev", "pkg-config"]
EOF

# ─────────────────────────────────────────────────────────────────────────────
# Instrucciones para el usuario
# ─────────────────────────────────────────────────────────────────────────────
echo ""
header "Comparte esta información con el mantenedor del proyecto"
echo ""
echo "  Opción 1 — Guardar en archivo:"
echo "    ${GREEN}bash scripts/debug/collect-hw-info.sh > mi-equipo.toml${RESET}"
echo ""
echo "  Opción 2 — Copiar y pegar:"
echo "    Copia el bloque TOML de arriba y compártelo"
echo ""
echo "  Opción 3 — Usar el template manual:"
echo "    Rellena ${GREEN}build/templates/TEMPLATE.toml${RESET} y compártelo"
echo ""
