# Guía de modelos

## Estructura de directorios

```
/srv/models/
├── gguf/         — modelos de lenguaje en formato GGUF (llama-cli, llama-server)
├── embeddings/   — modelos de embeddings (llama-embedding)
├── rerankers/    — modelos de reranking para RAG
└── multimodal/   — modelos con capacidades de visión
```

## Formatos de cuantización recomendados

| Quantización | RAM aprox. (7B) | Calidad | Uso recomendado |
|-------------|-----------------|---------|-----------------|
| Q2_K        | ~3 GB           | Baja    | Hardware muy limitado |
| Q4_K_M      | ~5 GB           | Buena   | Balance ideal |
| Q5_K_M      | ~6 GB           | Alta    | Si la RAM lo permite |
| Q8_0        | ~9 GB           | Máxima  | Evaluación/comparación |

## Modelos sugeridos para esta PoC

### Modelos pequeños (< 4 GB RAM)
- `Qwen/Qwen2.5-1.5B-Instruct-GGUF` — excelente para bajo hardware
- `microsoft/Phi-3-mini-4k-instruct-gguf` — eficiente en razonamiento

### Modelos medianos (4-8 GB RAM)
- `Qwen/Qwen2.5-7B-Instruct-GGUF`
- `mistralai/Mistral-7B-Instruct-v0.3-GGUF`

### Embeddings
- `nomic-ai/nomic-embed-text-v1.5-GGUF`
- `sentence-transformers/all-MiniLM-L6-v2` (convertir a GGUF)

## Descarga con huggingface-cli

```bash
pip install huggingface-hub

# Descargar modelo específico
huggingface-cli download <org>/<repo> <archivo.gguf> \
  --local-dir /srv/models/gguf/

# Descargar con autenticación (modelos con licencia)
huggingface-cli login
huggingface-cli download <org>/<repo> <archivo.gguf> \
  --local-dir /srv/models/gguf/
```

## Ver modelos disponibles

```bash
just models
```
