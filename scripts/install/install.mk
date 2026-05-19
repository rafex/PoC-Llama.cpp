# =============================================================================
# install.mk — instalación versionada en /opt/llama.cpp y symlinks
# Incluido por el Makefile raíz.
# =============================================================================

.PHONY: install install-binaries install-models-dir install-symlinks install-check

LLAMA_BINARIES := llama-cli llama-server llama-bench llama-embedding llama-run

## Instala binarios compilados en la versión activa
install: compile install-binaries install-models-dir install-symlinks install-check
	$(call log_ok,Instalación completa: $(INSTALL_DIR))

install-binaries: compile
	$(call log_info,Instalando binarios en $(INSTALL_DIR)/bin ...)
	@cmake --install $(LLAMA_BUILD_DIR) --prefix $(INSTALL_DIR)
	$(call log_ok,Binarios instalados.)

install-models-dir:
	$(call log_info,Creando estructura de modelos en $(MODELS_DIR) ...)
	@mkdir -p $(MODELS_DIR)/{gguf,embeddings,rerankers,multimodal}
	@if [ ! -e "$(INSTALL_DIR)/models" ]; then \
	  ln -s $(MODELS_DIR) $(INSTALL_DIR)/models; \
	fi
	$(call log_ok,Directorio de modelos listo.)

## Apunta current a la versión recién instalada y actualiza symlinks en /usr/local/bin
install-symlinks:
	$(call log_info,Actualizando symlink current -> $(INSTALL_VERSION) ...)
	@sudo ln -sfn $(INSTALL_DIR) $(INSTALL_CURRENT)
	$(call log_info,Creando symlinks en $(SYMLINK_BIN) ...)
	@for bin in $(LLAMA_BINARIES); do \
	  bin_path="$(INSTALL_DIR)/bin/$$bin"; \
	  if [ -f "$$bin_path" ]; then \
	    sudo ln -sfn "$$bin_path" "$(SYMLINK_BIN)/$$bin"; \
	    printf "$(GREEN)[OK]$(RESET)    symlink: $(SYMLINK_BIN)/$$bin -> $$bin_path\n"; \
	  fi; \
	done

## Verifica que los binarios sean alcanzables desde PATH
install-check:
	$(call log_info,Verificando binarios instalados ...)
	@for bin in $(LLAMA_BINARIES); do \
	  if command -v "$$bin" >/dev/null 2>&1; then \
	    printf "$(GREEN)[OK]$(RESET)    $$bin encontrado en $$(command -v $$bin)\n"; \
	  else \
	    printf "$(YELLOW)[WARN]$(RESET)  $$bin no encontrado en PATH (puede requerir nueva sesión de shell)\n"; \
	  fi; \
	done

## Lista las versiones instaladas
install-list:
	$(call log_info,Versiones instaladas en $(INSTALL_BASE)/versions :)
	@ls -1 $(INSTALL_BASE)/versions 2>/dev/null || echo "  (ninguna)"
	@echo ""
	$(call log_info,Versión activa (current):)
	@readlink $(INSTALL_CURRENT) 2>/dev/null || echo "  (no configurada)"
