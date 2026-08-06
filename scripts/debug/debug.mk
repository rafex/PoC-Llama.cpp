# =============================================================================
# debug.mk — diagnóstico del entorno, binarios y runtime
# Incluido por el Makefile raíz.
# =============================================================================

.PHONY: debug debug-env debug-cpu debug-gpu debug-binaries debug-models check-update

## Muestra diagnóstico completo
debug: debug-env debug-cpu debug-gpu debug-binaries debug-models


## Variables de entorno y paths relevantes
debug-env:
	$(call log_info,=== Entorno ===)
	@echo "  OS              = $(OS)"
	@echo "  ARCH            = $(ARCH)"
	@echo "  BUILD_DATE      = $(BUILD_DATE)"
	@echo "  INSTALL_VERSION = $(INSTALL_VERSION)"
	@echo "  INSTALL_DIR     = $(INSTALL_DIR)"
	@echo "  INSTALL_CURRENT = $(INSTALL_CURRENT)"
	@echo "  MODELS_DIR      = $(MODELS_DIR)"
	@echo "  LLAMA_SRC_DIR   = $(LLAMA_SRC_DIR)"
	@echo "  CMAKE_FLAGS     = $(CMAKE_COMMON_FLAGS)"

## Capacidades de CPU detectadas
debug-cpu:
	$(call log_info,=== CPU ===)
ifeq ($(OS),Darwin)
	@sysctl -n machdep.cpu.brand_string 2>/dev/null || true
	@sysctl -n machdep.cpu.features 2>/dev/null | tr ' ' '\n' | grep -iE 'avx|sse|neon|fma|bmi' | sort || true
else
	@grep -m1 "model name" /proc/cpuinfo || true
	@grep -m1 "flags"      /proc/cpuinfo | tr ' ' '\n' | grep -iE 'avx|sse|neon|fma|bmi' | sort || true
endif

## Diagnóstico de GPU
debug-gpu:
	$(call log_info,=== GPU ===)
	@python3 scripts/commons/detect_gpu.py


## Estado de binarios instalados
debug-binaries:
	$(call log_info,=== Binarios en $(INSTALL_CURRENT)/bin ===)
	@if [ -d "$(INSTALL_CURRENT)/bin" ]; then \
	  ls -lh $(INSTALL_CURRENT)/bin/; \
	else \
	  echo "  (directorio no encontrado)"; \
	fi
	$(call log_info,=== Symlinks en $(SYMLINK_BIN) ===)
	@ls -lh $(SYMLINK_BIN)/llama-* 2>/dev/null || echo "  (ninguno)"

## Compara la versión local de llama.cpp con la última release en GitHub
check-update:
	$(call log_info,=== Versión de llama.cpp ===)
	@python3 scripts/debug/check-update.py --src-dir $(LLAMA_SRC_DIR)

## Estado del directorio de modelos
debug-models:
	$(call log_info,=== Modelos en $(MODELS_DIR) ===)
	@if [ -d "$(MODELS_DIR)" ]; then \
	  find $(MODELS_DIR) -name "*.gguf" -exec ls -lh {} \; 2>/dev/null || echo "  (sin modelos .gguf)"; \
	else \
	  echo "  (directorio $(MODELS_DIR) no existe)"; \
	fi
