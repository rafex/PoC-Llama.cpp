# Decisiones de arquitectura

## ADR-001: Instalación versionada en /opt/llama.cpp

**Contexto:** los binarios de llama.cpp cambian con frecuencia y diferentes
compilaciones (AVX2, Metal, OpenBLAS) tienen características distintas.

**Decisión:** instalar en `/opt/llama.cpp/versions/<fecha>-<arch>/` con un
symlink `current` que apunta a la versión activa.

**Consecuencias:**
- Rollback instantáneo: `sudo ln -sfn /opt/llama.cpp/versions/<otra> /opt/llama.cpp/current`
- Múltiples compilaciones coexisten sin conflicto
- Los symlinks en `/usr/local/bin/` siempre apuntan a `current/bin/`

## ADR-002: Separación de modelos en /srv/models

**Contexto:** los modelos GGUF pesan varios GB y sobreviven a recompilaciones.

**Decisión:** modelos en `/srv/models/{gguf,embeddings,rerankers,multimodal}/`,
enlazados desde la instalación como `current/models -> /srv/models`.

**Consecuencias:**
- Recompilar no requiere re-descargar modelos
- Fácil montar `/srv/models` en un volumen separado o NFS
- Organización semántica por tipo de modelo

## ADR-003: Makefile para builds, justfile para tareas

**Contexto:** necesitamos separar preocupaciones entre construcción y operación.

**Decisión:**
- `Makefile` compila, instala, crea artefactos. Nunca llama a `just`.
- `justfile` orquesta flujos, runtime y utilidades. Delega compilación a `make`.

**Consecuencias:**
- Se puede usar `make install` en pipelines CI sin instalar `just`
- `just setup` es el punto de entrada amigable para desarrolladores
- No hay lógica duplicada entre los dos sistemas

## ADR-004: Scripts organizados por dominio semántico

**Contexto:** el proyecto crecerá con más targets y funciones.

**Decisión:** cada dominio (`build`, `install`, `debug`, etc.) tiene su propia
carpeta en `scripts/` con un `.mk` y un `.just`. El Makefile y justfile raíz
solo hacen `include`/`import`.

**Consecuencias:**
- Fácil agregar nuevos dominios sin tocar los archivos raíz
- Cada script es testeable de forma aislada
- Responsabilidad clara por archivo
