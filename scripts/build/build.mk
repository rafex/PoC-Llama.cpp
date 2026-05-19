# =============================================================================
# build.mk — clonación, configuración y compilación de llama.cpp
# Incluido por el Makefile raíz.
# =============================================================================

.PHONY: clone configure compile build-clean

## Clona el repositorio de llama.cpp en build/llama.cpp
clone:
	$(call log_info,Clonando llama.cpp en $(LLAMA_SRC_DIR)...)
	@if [ -d "$(LLAMA_SRC_DIR)/.git" ]; then \
	  printf "$(YELLOW)[WARN]$(RESET)  El repositorio ya existe. Ejecuta 'make build-clean' primero si quieres re-clonar.\n"; \
	else \
	  git clone --depth=1 $(LLAMA_REPO_URL) $(LLAMA_SRC_DIR); \
	  $(call log_ok,Repositorio clonado.); \
	fi

## Configura cmake con flags de la plataforma detectada
configure: clone
	$(call log_info,Configurando cmake en $(LLAMA_BUILD_DIR)...)
	@cmake -S $(LLAMA_SRC_DIR) -B $(LLAMA_BUILD_DIR) \
	  $(CMAKE_COMMON_FLAGS) \
	  -DCMAKE_INSTALL_PREFIX=$(INSTALL_DIR)
	$(call log_ok,Configuración cmake completada.)

## Compila llama.cpp (requiere configure previo)
compile: configure
	$(call log_info,Compilando llama.cpp con $(shell nproc 2>/dev/null || sysctl -n hw.logicalcpu) núcleos...)
	@cmake --build $(LLAMA_BUILD_DIR) \
	  --config Release \
	  --parallel $(shell nproc 2>/dev/null || sysctl -n hw.logicalcpu)
	$(call log_ok,Compilación completada.)

## Elimina la carpeta build para empezar desde cero
build-clean:
	$(call log_warn,Eliminando $(LLAMA_BUILD_DIR)...)
	@rm -rf $(LLAMA_BUILD_DIR)
	$(call log_ok,Limpieza completada.)

## Elimina también el repo clonado
build-purge:
	$(call log_warn,Eliminando $(LLAMA_SRC_DIR) completo...)
	@rm -rf $(LLAMA_SRC_DIR)
	$(call log_ok,Purga completada.)
