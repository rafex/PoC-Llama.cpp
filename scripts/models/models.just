# =============================================================================
# models.just — descarga y gestión de modelos GGUF
# =============================================================================

# Lista el catálogo completo de modelos disponibles
model-list:
    python3 scripts/models/model-download.py --list

# Menú interactivo para elegir y descargar un modelo
model-download:
    python3 scripts/models/model-download.py

# Filtra el catálogo por tipo y muestra menú (ej: just model-download-type chat)
model-download-type type:
    python3 scripts/models/model-download.py --type {{type}}

# Descarga directamente por ID sin menú (ej: just model-download-id qwen2.5-1.5b-chat-q4)
model-download-id id:
    python3 scripts/models/model-download.py --id {{id}}
