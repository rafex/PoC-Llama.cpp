# =============================================================================
# post-install.mk — configuración post-instalación: wrappers, permisos, etc.
# Incluido por el Makefile raíz.
# =============================================================================

.PHONY: post-install post-install-wrappers post-install-perms

WRAPPERS_DIR := $(INSTALL_DIR)/scripts

## Ejecuta todos los pasos de post-instalación
post-install: post-install-wrappers post-install-perms
	$(call log_ok,Post-instalación completada.)

## Genera wrappers semánticos en el directorio de la versión activa
post-install-wrappers:
	$(call log_info,Generando wrappers en $(WRAPPERS_DIR) ...)
	@mkdir -p $(WRAPPERS_DIR)
	@cat > $(WRAPPERS_DIR)/start-server.sh << 'EOF'
	#!/usr/bin/env bash
	# Inicia llama-server con el modelo especificado como argumento
	# Uso: start-server.sh <ruta-al-modelo.gguf> [puerto]
	set -euo pipefail
	MODEL="${1:?Especifica la ruta al modelo .gguf}"
	PORT="${2:-8080}"
	exec "$(INSTALL_CURRENT)/bin/llama-server" \
	  -m "$$MODEL" \
	  --host 0.0.0.0 \
	  --port "$$PORT" \
	  -c 4096 \
	  -t "$$(nproc 2>/dev/null || sysctl -n hw.logicalcpu)"
	EOF
	@chmod +x $(WRAPPERS_DIR)/start-server.sh
	@cat > $(WRAPPERS_DIR)/bench.sh << 'EOF'
	#!/usr/bin/env bash
	# Benchmark rápido del modelo especificado
	set -euo pipefail
	MODEL="${1:?Especifica la ruta al modelo .gguf}"
	exec "$(INSTALL_CURRENT)/bin/llama-bench" -m "$$MODEL"
	EOF
	@chmod +x $(WRAPPERS_DIR)/bench.sh
	$(call log_ok,Wrappers generados en $(WRAPPERS_DIR).)

## Ajusta permisos en el directorio de instalación
post-install-perms:
	$(call log_info,Ajustando permisos en $(INSTALL_DIR) ...)
	@chmod -R 755 $(INSTALL_DIR)/bin 2>/dev/null || true
	@chmod -R 755 $(INSTALL_DIR)/scripts 2>/dev/null || true
	$(call log_ok,Permisos ajustados.)
