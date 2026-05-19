# AGENTS.md — Documentación para agentes IA

Guía de contexto para agentes IA que trabajen en este repositorio.

## Propósito del proyecto

PoC para ejecutar LLMs localmente con llama.cpp. Objetivo principal: compilar
llama.cpp con flags optimizados para la CPU del host, instalarlo en una
estructura versionada en `/opt/llama.cpp/`, y exponer los binarios vía
symlinks en `/usr/local/bin/`.

## Reglas de arquitectura — OBLIGATORIAS

| Componente | Responsabilidad | Restricciones |
|------------|-----------------|---------------|
| `Makefile` | Build, compilación, instalación de binarios | **NUNCA** llama a `just` o `justfile` |
| `justfile` | Task manager, flujos, runtime, utilidades | **NUNCA** duplica lógica del Makefile; delega compilación con `make` |
| `scripts/*/` | Implementación por dominio | Cada carpeta tiene un `.mk` y un `.just` |
| `containers/` | Aplicativos contenerizados | Separados por aplicativo; actualmente vacío |
| `build/` | Fuente clonada de llama.cpp | Gitignored; no modificar manualmente |

## Estructura de scripts

Cada subdirectorio de `scripts/` corresponde a un dominio semántico:

- `commons/` — variables compartidas, detectores de plataforma, macros de log
- `build/` — clonar repo, configurar cmake, compilar
- `install/` — instalar binarios versionados, crear symlinks
- `post-install/` — generar wrappers, ajustar permisos
- `debug/` — diagnóstico de entorno, CPU, binarios, modelos
- `uninstall/` — desinstalación limpia por versión o total

## Paths del sistema

```
/opt/llama.cpp/versions/<BUILD_DATE>-<ARCH>/   ← binarios versionados
/opt/llama.cpp/current/                        ← symlink a versión activa
/srv/models/{gguf,embeddings,rerankers,multimodal}/  ← modelos GGUF
/usr/local/bin/llama-*                         ← symlinks a current/bin/
```

`BUILD_DATE` = `YYYY.MM.DD`, `ARCH` = salida de `uname -m`.

## Detección de plataforma

El archivo `scripts/commons/commons.mk` detecta automáticamente:
- macOS (Darwin): habilita Metal (`GGML_METAL=ON`)
- Linux x86_64: detecta AVX2 > AVX > fallback sin extensiones
- El tag de versión incluye `uname -m` para distinguir builds

## Convenciones

- Los targets de `make` y las recetas de `just` tienen el mismo nombre cuando
  la receta de just solo delega en make. Esto facilita la discoverability.
- Los targets destructivos (`uninstall-all`, `build-purge`) requieren
  confirmación interactiva en el Makefile.
- Los modelos en `/srv/models/` son persistentes y no se tocan en
  ningún target de install/uninstall de binarios.

## Qué NO hacer

- No mover la lógica de compilación cmake fuera de `scripts/build/build.mk`
- No agregar targets en `justfile` que dupliquen lo que hace `Makefile`
- No commitear el directorio `build/llama.cpp/` (está en `.gitignore`)
- No crear archivos de configuración de contenedores fuera de `containers/`
- No instalar binarios directamente en `/usr/local/bin/` — siempre usar la
  estructura versionada en `/opt/llama.cpp/`
