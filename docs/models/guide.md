# Guía de modelos

## Estructura de directorios

```
/srv/models/
├── gguf/         — modelos de lenguaje (llama-cli, llama-server)
├── embeddings/   — modelos de embeddings (llama-embedding)
├── rerankers/    — modelos de reranking para RAG
└── multimodal/   — modelos con capacidades de visión
```

## Catálogo curado

El proyecto incluye un catálogo en `build/models/catalog.toml` con modelos
probados y recomendados, agrupados por tipo:

| Tipo        | Descripción                              |
|-------------|------------------------------------------|
| `chat`      | Modelos de conversación general          |
| `coding`    | Especializados en generación de código   |
| `embedding` | Representación vectorial para RAG        |
| `multimodal`| Visión + lenguaje (análisis de imágenes) |

## Descargar modelos

```bash
# Menú interactivo (recomienda y descarga)
just model-download

# Filtrar por tipo antes del menú
just model-download-type chat
just model-download-type coding
just model-download-type embedding
just model-download-type multimodal

# Descargar directamente por ID (sin menú)
just model-download-id qwen2.5-1.5b-chat-q4

# Solo listar el catálogo sin descargar
just model-list
```

## Modelos del catálogo

### Chat — conversación general

| ID | Modelo | Tamaño | RAM mín. |
|----|--------|--------|----------|
| `qwen2.5-0.5b-chat-q4`             | Qwen 2.5 0.5B Q4_K_M          | ~0.4 GB | 1 GB  |
| `qwen2.5-1.5b-chat-q4`             | Qwen 2.5 1.5B Q4_K_M          | ~1.0 GB | 2 GB  |
| `qwen2.5-3b-chat-q4`               | Qwen 2.5 3B Q4_K_M            | ~2.0 GB | 4 GB  |
| `phi3-mini-3.8b-chat-q4`           | Microsoft Phi-3 Mini 3.8B     | ~2.2 GB | 4 GB  |
| `gemma2-2b-chat-q4`                | Google Gemma 2 2B Q4_K_M      | ~1.6 GB | 3 GB  |
| `deepseek-r1-distill-qwen-1.5b-q4` | DeepSeek R1 Distill Qwen 1.5B | ~1.0 GB | 2 GB  |
| `tinyllama-1.1b-chat-q4`           | TinyLlama 1.1B Q4_K_M         | ~0.7 GB | 2 GB  |
| `llama3.2-1b-chat-q4`              | Llama 3.2 1B Q4_K_M           | ~0.8 GB | 2 GB  |
| `llama3.2-3b-chat-q4`              | Llama 3.2 3B Q4_K_M           | ~2.0 GB | 4 GB  |

### Coding — generación de código

| ID | Modelo | Tamaño | RAM mín. |
|----|--------|--------|----------|
| `qwen2.5-coder-1.5b-q4` | Qwen 2.5 Coder 1.5B Q4_K_M | ~1.0 GB | 2 GB |
| `qwen2.5-coder-3b-q4`   | Qwen 2.5 Coder 3B Q4_K_M   | ~2.0 GB | 4 GB |

### Embedding — representación vectorial

| ID | Modelo | Tamaño | RAM mín. |
|----|--------|--------|----------|
| `nomic-embed-v1.5-q4` | Nomic Embed Text v1.5 Q4_K_M  | ~80 MB | 1 GB |
| `bge-small-en-q4`     | BAAI BGE-Small EN v1.5 Q4_K_M | ~30 MB | 1 GB |

### Multimodal — visión + lenguaje

Todos los modelos multimodal requieren un archivo `mmproj` adicional
(proyector visual). El script de descarga lo obtiene automáticamente.

| ID | Modelo | Tamaño | RAM mín. |
|----|--------|--------|----------|
| `smolvlm-500m-q4`      | SmolVLM 500M Q4_K_M         | ~0.4 GB | 1 GB  |
| `moondream2-f16`        | Moondream 2 1.8B F16        | ~3.5 GB | 4 GB  |
| `qwen2-vl-2b-q4`        | Qwen2-VL 2B Q4_K_M          | ~1.6 GB | 3 GB  |
| `internvl2-2b-q4`       | InternVL2 2B Q4_K_M         | ~1.6 GB | 3 GB  |
| `minicpm-v-2.0-q4`      | MiniCPM-V 2.0 2.4B Q4_K_M  | ~1.6 GB | 4 GB  |
| `llava-phi3-mini-f16`   | LLaVA Phi-3 Mini 3.8B F16   | ~7.6 GB | 10 GB |
| `minicpm-v-2.6-q4`      | MiniCPM-V 2.6 8B Q4_K_M    | ~5.0 GB | 8 GB  |

## Usar los modelos descargados

```bash
# Chat interactivo en terminal
just chat /srv/models/gguf/qwen2.5-1.5b-instruct-q4_k_m.gguf

# Servidor HTTP (API compatible con OpenAI)
just run /srv/models/gguf/qwen2.5-1.5b-instruct-q4_k_m.gguf 8080

# Benchmark
just bench /srv/models/gguf/qwen2.5-1.5b-instruct-q4_k_m.gguf

# Ver todos los modelos descargados en /srv/models
just models
```

Para modelos multimodal, usa `llama-cli` con el flag `--mmproj`:

```bash
llama-cli \
  -m /srv/models/multimodal/moondream2-text-model-f16.gguf \
  --mmproj /srv/models/multimodal/moondream2-mmproj-f16.gguf \
  --image /ruta/a/imagen.jpg \
  -p "Describe esta imagen"
```

## Formatos de cuantización

| Quantización | RAM aprox. (7B) | Calidad | Uso recomendado       |
|-------------|-----------------|---------|------------------------|
| Q2_K        | ~3 GB           | Baja    | Hardware muy limitado  |
| Q4_K_M      | ~5 GB           | Buena   | Balance ideal          |
| Q5_K_M      | ~6 GB           | Alta    | Si la RAM lo permite   |
| Q8_0        | ~9 GB           | Máxima  | Evaluación/comparación |
| F16         | ~14 GB          | Exacta  | Referencia / GPU       |

## Agregar modelos al catálogo

Edita `build/models/catalog.toml` y añade una entrada con estos campos:

```toml
[[models]]
id              = "mi-modelo-q4"           # identificador único
name            = "Nombre legible"
type            = "chat"                   # chat | coding | embedding | multimodal
hf_repo         = "org/repo-GGUF"         # repositorio HuggingFace
hf_file         = "modelo.gguf"           # archivo principal
hf_extra_files  = ["mmproj.gguf"]         # (opcional) archivos adicionales
size_gb         = 1.5                     # tamaño aproximado
ram_gb          = 3                       # RAM mínima recomendada
dest_dir        = "gguf"                  # gguf | embeddings | multimodal
description     = "Descripción breve."
```
