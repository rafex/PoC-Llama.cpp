# =============================================================================
# uninstall.mk — desinstalación limpia de binarios y symlinks
# Incluido por el Makefile raíz. Requiere confirmación explícita.
# =============================================================================

.PHONY: uninstall uninstall-version uninstall-symlinks uninstall-all

LLAMA_BINARIES_UNINSTALL := llama-cli llama-server llama-bench llama-embedding llama-run

## Desinstala la versión activa (current) y actualiza symlinks
uninstall:
	$(call log_warn,Desinstalando versión actual: $$(readlink $(INSTALL_CURRENT) 2>/dev/null || echo "ninguna") ...)
	$(MAKE) uninstall-symlinks
	@if [ -L "$(INSTALL_CURRENT)" ]; then \
	  TARGET=$$(readlink $(INSTALL_CURRENT)); \
	  sudo rm -f $(INSTALL_CURRENT); \
	  sudo rm -rf "$$TARGET"; \
	  printf "$(GREEN)[OK]$(RESET)    Versión eliminada: $$TARGET\n"; \
	fi

## Elimina los symlinks en /usr/local/bin
uninstall-symlinks:
	$(call log_info,Eliminando symlinks de $(SYMLINK_BIN) ...)
	@for bin in $(LLAMA_BINARIES_UNINSTALL); do \
	  if [ -L "$(SYMLINK_BIN)/$$bin" ]; then \
	    sudo rm -f "$(SYMLINK_BIN)/$$bin"; \
	    printf "$(GREEN)[OK]$(RESET)    Eliminado: $(SYMLINK_BIN)/$$bin\n"; \
	  fi; \
	done

## Desinstala una versión específica (uso: make uninstall-version VERSION=2026.05.18-x86_64)
uninstall-version:
ifndef VERSION
	$(error Especifica VERSION=<fecha-arch>, ej: make uninstall-version VERSION=2026.05.18-x86_64)
endif
	$(call log_warn,Desinstalando versión $(INSTALL_BASE)/versions/$(VERSION) ...)
	@sudo rm -rf "$(INSTALL_BASE)/versions/$(VERSION)"
	$(call log_ok,Versión $(VERSION) eliminada.)

## Elimina TODO /opt/llama.cpp — DESTRUCTIVO
uninstall-all:
	$(call log_warn,ATENCIÓN: esto elimina TODO $(INSTALL_BASE))
	@read -p "¿Confirmas? [s/N] " ans && [ "$$ans" = "s" ] || exit 1
	$(MAKE) uninstall-symlinks
	@sudo rm -rf $(INSTALL_BASE)
	$(call log_ok,$(INSTALL_BASE) eliminado completamente.)
