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

# Binarios a verificar en el test suite
# Núcleo + multimodal: se testean con --version
TEST_BINARIES := llama-cli llama-server llama-bench llama-embedding llama-mtmd-cli
# Herramientas GGUF y diagnóstico: solo se verifica que existan y sean ejecutables
TEST_BINARIES_TOOLS := llama-quantize llama-gguf llama-gguf-split llama-gguf-hash \
                       llama-tokenize llama-imatrix

## Suite completa de pruebas
test: test-binaries test-versions
	@printf "$(GREEN)[OK]$(RESET)    Todas las pruebas pasaron.\n"

## Verifica que los binarios están instalados y son ejecutables
test-binaries:
	$(call log_info,=== Prueba: binarios instalados ===)
	@failed=0; \
	for bin in $(TEST_BINARIES) $(TEST_BINARIES_TOOLS); do \
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
	  printf "$(YELLOW)[SKIP]$(RESET)  Sin modelos en $(MODELS_DIR)/gguf — descarga uno con 'just model-download-smart'\n"; \
	  exit 0; \
	fi; \
	printf "$(CYAN)[INFO]$(RESET)  Usando modelo: $$model\n"; \
	printf "$(CYAN)[INFO]$(RESET)  Generando 16 tokens de prueba...\n"; \
	tmpout=$$(mktemp); \
	llama-cli \
	  -m "$$model" \
	  -n 16 \
	  -p "Hello" \
	  --log-disable \
	  > "$$tmpout" 2>&1; \
	rc=$$?; \
	if [ $$rc -eq 0 ]; then \
	  output=$$(grep -v '^\[' "$$tmpout" | grep -v '^$$' | head -3); \
	  rm -f "$$tmpout"; \
	  printf "$(GREEN)[PASS]$(RESET)  Inferencia exitosa:\n"; \
	  if [ -n "$$output" ]; then \
	    echo "$$output" | sed 's/^/         /'; \
	  fi; \
	else \
	  printf "$(RED)[FAIL]$(RESET)  llama-cli falló (rc=$$rc). Salida:\n"; \
	  head -20 "$$tmpout" | sed 's/^/         /'; \
	  rm -f "$$tmpout"; \
	  exit 1; \
	fi
