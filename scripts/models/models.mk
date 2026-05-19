# =============================================================================
# models.mk — descarga y gestión de modelos GGUF
# Incluido por el Makefile raíz.
# =============================================================================

.PHONY: model-list model-download model-download-id

MODEL_DOWNLOAD := scripts/models/model-download.py

## Lista el catálogo completo de modelos disponibles
model-list:
	@python3 $(MODEL_DOWNLOAD) --list

## Menú interactivo para descargar un modelo
model-download:
	@python3 $(MODEL_DOWNLOAD)

## Descarga por tipo: make model-download-type TYPE=chat
model-download-type:
ifndef TYPE
	$(error Especifica TYPE=chat|coding|embedding)
endif
	@python3 $(MODEL_DOWNLOAD) --type $(TYPE)

## Descarga directa por ID: make model-download-id ID=qwen2.5-1.5b-chat-q4
model-download-id:
ifndef ID
	$(error Especifica ID=<id-del-modelo>. Ver 'make model-list')
endif
	@python3 $(MODEL_DOWNLOAD) --id $(ID)
