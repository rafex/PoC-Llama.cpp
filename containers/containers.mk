# =============================================================================
# containers.mk — gestión de contenedores por aplicativo
# Incluible desde el Makefile raíz si se requieren targets de containers.
#
# Convención de variables por app:
#   APP_NAME   — nombre del aplicativo (ej: llama-server)
#   APP_IMAGE  — imagen docker resultante
#   APP_TAG    — tag de la imagen
# =============================================================================

.PHONY: containers-help

COMPOSE := docker compose

## Muestra ayuda de containers
containers-help:
	@printf "Targets de containers (requiere incluir containers/containers.mk):\n"
	@printf "  containers-help  — este mensaje\n"
	@printf "\n  Agrega targets por aplicativo según se desarrollen.\n"
