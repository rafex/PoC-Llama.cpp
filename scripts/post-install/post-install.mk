# =============================================================================
# post-install.mk — configuración post-instalación: wrappers, permisos, etc.
# Incluido por el Makefile raíz.
# =============================================================================

.PHONY: post-install post-install-wrappers post-install-perms

WRAPPERS_DIR    := $(INSTALL_DIR)/scripts
WRAPPER_SCRIPT  := scripts/post-install/generate-wrappers.sh

## Ejecuta todos los pasos de post-instalación
post-install: post-install-wrappers post-install-perms
	@printf "$(GREEN)[OK]$(RESET)    Post-instalación completada.\n"

## Genera wrappers semánticos en el directorio de la versión activa
post-install-wrappers:
	$(call log_info,Generando wrappers en $(WRAPPERS_DIR) ...)
	@sudo bash $(WRAPPER_SCRIPT) "$(INSTALL_DIR)" "$(INSTALL_CURRENT)"
	@printf "$(GREEN)[OK]$(RESET)    Wrappers listos: $(WRAPPERS_DIR)\n"

## Ajusta permisos en el directorio de instalación
post-install-perms:
	$(call log_info,Ajustando permisos en $(INSTALL_DIR) ...)
	@sudo chmod -R 755 $(INSTALL_DIR)/bin 2>/dev/null || true
	@sudo chmod -R 755 $(INSTALL_DIR)/scripts 2>/dev/null || true
	@printf "$(GREEN)[OK]$(RESET)    Permisos ajustados.\n"
