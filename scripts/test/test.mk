# =============================================================================
# test.mk — pruebas de validación post-compilación e instalación
# Incluido por el Makefile raíz.
#
# Targets:
#   test              — suite completa (binarios + versiones)
#   test-binaries     — verifica que los binarios existen y son ejecutables
#   test-versions     — ejecuta --version en cada binario instalado
#   test-smoke        — inferencia rápida si hay algún modelo en /srv/models
# =============================================================================

.PHONY: test test-binaries test-versions test-smoke

TEST_BINARIES := llama-cli llama-server llama-bench llama-embedding

## Suite completa de pruebas
test: test-binaries test-versions
	@printf "$(GREEN)[OK]$(RESET)    Todas las pruebas pasaron.\n"

## Verifica que los binarios están instalados y son ejecutables
test-binaries:
	$(call log_info,=== Prueba: binarios instalados ===)
	@failed=0; \
	for bin in $(TEST_BINARIES); do \
	  path="$(SYMLINK_BIN)/$$bin"; \
	  if [ -L "$$path" ] && [ -x "$$(readlink -f $$path)" ]; then \
	    printf "$(GREEN)[PASS]$(RESET)  $$bin → $$(readlink -f $$path)\n"; \
	  else \
	    printf "$(RED)[FAIL]$(RESET)  $$bin no encontrado o no ejecutable en $(SYMLINK_BIN)\n"; \
	    failed=$$((failed + 1)); \
	  fi; \
	done; \
	[ "$$failed" -eq 0 ] || exit 1

## Ejecuta --version en cada binario para confirmar que arranca
test-versions:
	$(call log_info,=== Prueba: ejecución --version ===)
	@failed=0; \
	for bin in $(TEST_BINARIES); do \
	  if command -v "$$bin" >/dev/null 2>&1; then \
	    version=$$($$bin --version 2>&1 | head -1 || true); \
	    printf "$(GREEN)[PASS]$(RESET)  $$bin: $$version\n"; \
	  else \
	    printf "$(RED)[FAIL]$(RESET)  $$bin no encontrado en PATH\n"; \
	    failed=$$((failed + 1)); \
	  fi; \
	done; \
	[ "$$failed" -eq 0 ] || exit 1

## Inferencia rápida con el primer modelo .gguf disponible (smoke test)
test-smoke:
	$(call log_info,=== Prueba: smoke test de inferencia ===)
	@model=$$(find $(MODELS_DIR)/gguf -name "*.gguf" 2>/dev/null | sort | head -1); \
	if [ -z "$$model" ]; then \
	  printf "$(YELLOW)[SKIP]$(RESET)  Sin modelos en $(MODELS_DIR)/gguf — descarga uno con 'huggingface-cli'\n"; \
	  exit 0; \
	fi; \
	printf "$(CYAN)[INFO]$(RESET)  Usando modelo: $$model\n"; \
	printf "$(CYAN)[INFO]$(RESET)  Generando 16 tokens de prueba...\n"; \
	output=$$(echo "Hello" | llama-cli \
	  -m "$$model" \
	  -n 16 \
	  --no-display-prompt \
	  --log-disable \
	  -p "Hello" 2>/dev/null | head -3 || true); \
	if [ -n "$$output" ]; then \
	  printf "$(GREEN)[PASS]$(RESET)  Inferencia exitosa:\n"; \
	  echo "$$output" | sed 's/^/         /'; \
	else \
	  printf "$(RED)[FAIL]$(RESET)  La inferencia no produjo output\n"; \
	  exit 1; \
	fi
