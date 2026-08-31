# =============================================================================
# runtime.mk — benchmark y ejecución adaptativa de llama.cpp
# Incluido por el Makefile raíz.
# =============================================================================

.PHONY: benchmark-best run-best test-runtime

RUNTIME_SCRIPT := scripts/runtime/runtime.py

## Mide BLAS/Vulkan y guarda el mejor perfil local por modelo
## Uso: make benchmark-best MODEL=/srv/models/gguf/model.gguf [OBJECTIVE=tg|pp]
benchmark-best:
ifndef MODEL
	$(error Especifica MODEL=<ruta.gguf o id del catálogo>)
endif
	@python3 $(RUNTIME_SCRIPT) benchmark "$(MODEL)" \
		--repo-root "$(CURDIR)" \
		--objective "$(or $(OBJECTIVE),tg)"

## Ejecuta llama-server usando el perfil medido para el objetivo indicado
## Uso: make run-best MODEL=/srv/models/gguf/model.gguf [OBJECTIVE=tg|pp]
run-best:
ifndef MODEL
	$(error Especifica MODEL=<ruta.gguf o id del catálogo>)
endif
	@python3 $(RUNTIME_SCRIPT) serve "$(MODEL)" \
		--repo-root "$(CURDIR)" \
		--objective "$(or $(OBJECTIVE),tg)" \
		--port "$(or $(PORT),43110)" \
		--ctx-size "$(or $(CTX_SIZE),4096)" \
		--n-predict "$(or $(N_PREDICT),512)" \
		--threads "$(or $(THREADS),$(shell nproc 2>/dev/null || sysctl -n hw.logicalcpu 2>/dev/null || echo 4))" \
		--batch "$(or $(BATCH),256)"

## Pruebas unitarias del selector y parser de benchmarks
test-runtime:
	@python3 -m unittest discover -s scripts/runtime -p 'test_*.py' -v
