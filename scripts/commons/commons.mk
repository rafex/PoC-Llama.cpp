# =============================================================================
# commons.mk — variables compartidas y utilidades base
# Incluido por el Makefile raíz. No contiene targets ejecutables.
# =============================================================================

# --- Detección de plataforma --------------------------------------------------
OS          := $(shell uname -s)
ARCH        := $(shell uname -m)
CPU_FLAGS   := $(shell grep -m1 flags /proc/cpuinfo 2>/dev/null || sysctl -n machdep.cpu.features 2>/dev/null | tr '[:upper:]' '[:lower:]' || echo "unknown")

# --- Versión de build ---------------------------------------------------------
BUILD_DATE  := $(shell date +%Y.%m.%d)
GIT_HASH    := $(shell git rev-parse --short HEAD 2>/dev/null || echo "nogit")

# --- Paths de instalación -----------------------------------------------------
INSTALL_BASE    := /opt/llama.cpp
INSTALL_VERSION := $(BUILD_DATE)-$(ARCH)
INSTALL_DIR     := $(INSTALL_BASE)/versions/$(INSTALL_VERSION)
INSTALL_CURRENT := $(INSTALL_BASE)/current
MODELS_DIR      := /srv/models
SYMLINK_BIN     := /usr/local/bin

# --- Repositorio llama.cpp ---------------------------------------------------
LLAMA_REPO_URL  := https://github.com/ggerganov/llama.cpp.git
LLAMA_SRC_DIR   := $(CURDIR)/build/llama.cpp
LLAMA_BUILD_DIR := $(LLAMA_SRC_DIR)/build-out

# --- Detección de capacidades CPU y GPU ---------------------------------------
CMAKE_COMMON_FLAGS := $(shell python3 scripts/build/detect-profile.py --flags 2>/dev/null || echo "-DCMAKE_BUILD_TYPE=Release") -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=ON


# --- Colores para output ------------------------------------------------------
# Secuencias ANSI reales (via shell para que $(info ...) las interprete)
RESET  := $(shell printf '\033[0m')
BOLD   := $(shell printf '\033[1m')
GREEN  := $(shell printf '\033[32m')
YELLOW := $(shell printf '\033[33m')
CYAN   := $(shell printf '\033[36m')
RED    := $(shell printf '\033[31m')

# $(info ...) es un built-in de make: no necesita @ y funciona dentro de define/call
define log_info
$(info $(CYAN)[INFO]$(RESET)  $(1))
endef

define log_ok
$(info $(GREEN)[OK]$(RESET)    $(1))
endef

define log_warn
$(info $(YELLOW)[WARN]$(RESET)  $(1))
endef

define log_error
$(info $(RED)[ERROR]$(RESET) $(1))
endef
