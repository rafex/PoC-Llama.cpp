# PoC-Llama.cpp

Prueba de concepto para ejecutar LLMs de manera local usando [llama.cpp](https://github.com/ggerganov/llama.cpp).

## Índice de documentación

| Documento | Descripción |
|-----------|-------------|
| [docs/setup/](docs/setup/) | Instalación y primeros pasos |
| [docs/architecture/](docs/architecture/) | Decisiones de arquitectura y estructura del proyecto |
| [docs/models/](docs/models/) | Guía de modelos: descarga, formatos y recomendaciones |
| [docs/troubleshooting/](docs/troubleshooting/) | Solución de problemas comunes |
| [AGENTS.md](AGENTS.md) | Documentación para agentes IA |

## Inicio rápido

```bash
# Instalar dependencias, compilar e instalar
just setup

# Iniciar servidor con un modelo
just run /srv/models/gguf/mi-modelo.gguf

# Chat interactivo
just chat /srv/models/gguf/mi-modelo.gguf

# Ver ayuda completa
just
make help
```

## Estructura del proyecto

```
.
├── Makefile                  # Build, compilación, instalación de binarios
├── justfile                  # Task manager: flujos, runtime, utilidades
├── scripts/
│   ├── commons/              # Variables y utilidades compartidas
│   ├── build/                # Clonación y compilación de llama.cpp
│   ├── install/              # Instalación versionada en /opt/llama.cpp
│   ├── post-install/         # Wrappers semánticos y permisos
│   ├── debug/                # Diagnóstico de entorno y binarios
│   └── uninstall/            # Desinstalación limpia
├── containers/               # Aplicativos contenerizados (futuro)
├── build/                    # Fuente de llama.cpp (gitignored)
└── docs/                     # Documentación para humanos
```

## Instalación de binarios

Los binarios se instalan en una estructura versionada:

```
/opt/llama.cpp/
├── versions/
│   └── 2026.05.18-x86_64/   # <fecha>-<arch>
│       ├── bin/
│       └── scripts/          # Wrappers semánticos
├── current -> versions/...   # Symlink a versión activa
└── models/ -> /srv/models    # Symlink a directorio de modelos

/srv/models/                  # Modelos persistentes (sobreviven recompilaciones)
├── gguf/
├── embeddings/
├── rerankers/
└── multimodal/

/usr/local/bin/llama-*        # Symlinks a /opt/llama.cpp/current/bin/
```

Para cambiar de versión activa sin reinstalar:

```bash
just switch-version 2026.06.01-x86_64
```
