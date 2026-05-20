# PoC-Llama.cpp

Prueba de concepto para ejecutar LLMs de manera local usando [llama.cpp](https://github.com/ggerganov/llama.cpp).

## Índice de documentación

| Documento | Descripción |
|-----------|-------------|
| [docs/setup/getting-started.md](docs/setup/getting-started.md) | Instalación y primeros pasos |
| [docs/architecture/decisions.md](docs/architecture/decisions.md) | Decisiones de arquitectura |
| [docs/models/guide.md](docs/models/guide.md) | Guía de modelos: descarga, formatos y recomendaciones |
| [docs/troubleshooting/common-issues.md](docs/troubleshooting/common-issues.md) | Solución de problemas comunes |
| [AGENTS.md](AGENTS.md) | Documentación para agentes IA |

## Inicio rápido

```bash
# Ver perfiles de hardware disponibles
make profile-list

# Setup completo con perfil (verifica e instala deps, compila, instala)
just setup-profile apple/macmini6.2

# Descargar un modelo desde el catálogo curado (menú interactivo)
just model-download

# Descargar directamente por ID
just model-download-id qwen2.5-1.5b-chat-q4

# Iniciar servidor con un modelo (API compatible con OpenAI)
just run /srv/models/gguf/qwen2.5-1.5b-instruct-q4_k_m.gguf 8080

# Chat interactivo en terminal
just chat /srv/models/gguf/qwen2.5-1.5b-instruct-q4_k_m.gguf

# Ver todas las recetas disponibles
just
make help
```

## Estructura del proyecto

```
.
├── Makefile                        # Build, compilación, instalación de binarios
├── justfile                        # Task manager: flujos, runtime, utilidades
├── scripts/
│   ├── commons/                    # Variables, utilidades y check-deps
│   ├── build/                      # Clonación y compilación de llama.cpp
│   ├── install/                    # Instalación versionada en /opt/llama.cpp
│   ├── post-install/               # Wrappers semánticos y permisos
│   ├── debug/                      # Diagnóstico de entorno y binarios
│   └── uninstall/                  # Desinstalación limpia
├── build/
│   ├── templates/                  # Perfiles de compilación por hardware
│   │   └── apple/macmini6.2/      # Ivy Bridge i7-3615QM (AVX, OpenBLAS)
│   │       └── build.toml
│   └── llama.cpp/                  # Fuente clonada (gitignored)
├── containers/                     # Aplicativos contenerizados (futuro)
└── docs/                           # Documentación para humanos
```

## Perfiles de hardware

Los perfiles en `build/templates/<vendor>/<model>/build.toml` declaran:
- Flags de cmake y compilador específicos para la CPU
- Dependencias requeridas (verificadas e instaladas automáticamente)
- Generador cmake y número de jobs

```bash
make profile-list                              # listar perfiles
make profile-info PROFILE=apple/macmini6.2    # ver flags que se usarían
```

## Instalación de binarios

```
/opt/llama.cpp/
├── versions/
│   └── 2026.05.19-x86_64/    # <fecha>-<arch>
│       ├── bin/
│       └── scripts/           # Wrappers semánticos
├── current -> versions/...    # Symlink a versión activa
└── models/ -> /srv/models     # Symlink a modelos

/srv/models/                   # Modelos persistentes
├── gguf/
├── embeddings/
├── rerankers/
└── multimodal/

/usr/local/bin/llama-*         # Symlinks a /opt/llama.cpp/current/bin/
```

Cambiar de versión activa sin recompilar:

```bash
just install-list
just switch-version 2026.06.01-x86_64
```
