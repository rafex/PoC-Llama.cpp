# =============================================================================
# models.mk — descarga y gestión de modelos GGUF
# Incluido por el Makefile raíz.
# =============================================================================

.PHONY: model-list model-list-smart model-download model-download-smart model-download-id model-quantize


MODEL_DOWNLOAD    := scripts/models/model-download.py
HARDWARE_SMART    := scripts/models/hardware-smart.py

## Lista el catálogo completo de modelos disponibles
model-list:
	@python3 $(MODEL_DOWNLOAD) --list

## Detecta hardware y clasifica modelos (Eficiente / Suficiente / Excede)
model-list-smart:
	@python3 $(HARDWARE_SMART)

## Filtra por tipo según capacidad: make model-list-smart-type TYPE=chat
model-list-smart-type:
ifndef TYPE
	$(error Especifica TYPE=chat|coding|embedding|multimodal)
endif
	@python3 $(HARDWARE_SMART) --type $(TYPE)

## Detecta hardware, clasifica y descarga el modelo elegido (menú inteligente)
model-download-smart:
	@python3 $(HARDWARE_SMART) --download

## Filtra por tipo y descarga: make model-download-smart-type TYPE=chat
model-download-smart-type:
ifndef TYPE
	$(error Especifica TYPE=chat|coding|embedding|multimodal)
endif
	@python3 $(HARDWARE_SMART) --download --type $(TYPE)

## Menú interactivo simple (sin clasificación de hardware)
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

## Cuantización local de modelos descargados
model-quantize:
	@python3 scripts/models/quantize.py

