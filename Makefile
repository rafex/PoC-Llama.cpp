# =============================================================================
# Makefile — orquestador de builds y construcción de binarios
#
# Responsabilidades: compilar, construir, instalar binarios.
# PROHIBIDO: llamar a justfile o duplicar lógica de just.
#
# Uso:
#   make help          — lista de targets disponibles
#   make compile       — compila llama.cpp
#   make install       — compila + instala en /opt/llama.cpp/versions/<fecha-arch>
#   make debug         — diagnóstico del entorno
#   make uninstall     — desinstala la versión activa
# =============================================================================

# Forzar bash para heredocs y features modernas
SHELL := /usr/bin/env bash

.DEFAULT_GOAL := help

# --- Includes -----------------------------------------------------------------
include scripts/commons/commons.mk
include scripts/build/build.mk
include scripts/install/install.mk
include scripts/post-install/post-install.mk
include scripts/test/test.mk
include scripts/models/models.mk
include scripts/debug/debug.mk
include scripts/uninstall/uninstall.mk

# --- Help ---------------------------------------------------------------------
.PHONY: help

## Muestra este mensaje de ayuda
help:
	@printf "\n$(BOLD)PoC-Llama.cpp — Makefile$(RESET)\n\n"
	@printf "$(CYAN)Build y construcción$(RESET)\n"
	@printf "  %-28s %s\n" "clone"            "Clona repositorio llama.cpp en build/"
	@printf "  %-28s %s\n" "configure"        "Configura cmake con flags de plataforma"
	@printf "  %-28s %s\n" "compile"          "Compila llama.cpp"
	@printf "  %-28s %s\n" "build-clean"      "Limpia artefactos cmake (mantiene repo)"
	@printf "  %-28s %s\n" "build-purge"      "Elimina también el repo clonado"
	@printf "\n$(CYAN)Instalación$(RESET)\n"
	@printf "  %-28s %s\n" "install"          "compile + instala en /opt/llama.cpp/versions/..."
	@printf "  %-28s %s\n" "install-symlinks" "Actualiza symlinks en /usr/local/bin"
	@printf "  %-28s %s\n" "install-check"    "Verifica binarios en PATH"
	@printf "  %-28s %s\n" "install-list"     "Lista versiones instaladas"
	@printf "\n$(CYAN)Post-instalación$(RESET)\n"
	@printf "  %-28s %s\n" "post-install"     "Genera wrappers y ajusta permisos"
	@printf "\n$(CYAN)Debug$(RESET)\n"
	@printf "  %-28s %s\n" "debug"            "Diagnóstico completo"
	@printf "  %-28s %s\n" "debug-env"        "Muestra variables de entorno"
	@printf "  %-28s %s\n" "debug-cpu"        "Capacidades CPU detectadas"
	@printf "  %-28s %s\n" "debug-binaries"   "Estado de binarios instalados"
	@printf "  %-28s %s\n" "debug-models"     "Modelos disponibles en /srv/models"
	@printf "\n$(CYAN)Desinstalación$(RESET)\n"
	@printf "  %-28s %s\n" "uninstall"        "Desinstala versión activa + symlinks"
	@printf "  %-28s %s\n" "uninstall-version VERSION=<v>" "Desinstala versión específica"
	@printf "  %-28s %s\n" "uninstall-all"    "DESTRUCTIVO: elimina todo /opt/llama.cpp"
	@printf "\n"
