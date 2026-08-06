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

## ADR-005: Flags cmake de CPU por opción GGML_*, no solo por CMAKE_C_FLAGS

**Contexto:** durante la resolución de un SIGILL en Mac mini 6,2 (Ivy Bridge,
sin BMI2) se descubrió que poner `-mno-bmi2` en `CMAKE_C_FLAGS` no es suficiente.

**El problema:** ggml usa `target_compile_options(ggml PRIVATE -mbmi2)` para
inyectar flags de CPU. `target_compile_options()` se aplica **después** de
`CMAKE_C_FLAGS` en la línea de compilación. GCC resuelve flags contradictorios
usando el **último**; `-mbmi2` pisa `-mno-bmi2`. El binario resultante contenía
45 instrucciones `SHLX` (BMI2) y crasheaba con SIGILL en Ivy Bridge.

La causa específica: `GGML_BMI2` tiene **default `ON`** en ggml cmake.
`CMAKE_C_FLAGS` no puede vencerlo porque llega antes en el comando del compilador.

**Decisión:** los perfiles `build.toml` deben deshabilitar explícitamente cada
extensión CPU mediante las opciones `GGML_*` correspondientes, **además** de
los flags `-mno-*` del compilador:

```toml
[cmake.flags]
GGML_AVX    = "OFF"   # desactiva código AVX y la cadena BMI/FMA asociada
GGML_AVX2   = "OFF"
GGML_BMI2   = "OFF"   # impide target_compile_options(-mbmi2) en ggml-cpu
GGML_F16C   = "OFF"
GGML_FMA    = "OFF"
GGML_NATIVE = "OFF"

[compiler]
# Segunda barrera: -mno-* rechaza el flag en tiempo de compilación
# si algún path de cmake lo re-introduce.
cflags = "... -mno-avx -mno-bmi -mno-bmi2 ..."
```

**Jerarquía de precedencia cmake (de menor a mayor):**
```
CMAKE_C_FLAGS
  ↓ (siempre antes)
target_compile_options(PRIVATE ...)
  ↓ (siempre después, gana en conflicto)
```

**Consecuencias:**
- Los perfiles de hardware antiguo deben revisar todas las opciones `GGML_*`
  que tengan default `ON` y que el hardware no soporte
- `GGML_NATIVE=OFF` no es suficiente; hay que desactivar cada extensión
  individualmente
- El doble mecanismo (opción cmake + flag compilador) ofrece defensa en
  profundidad: si una capa falla, la otra detiene la compilación
- Documentar en el perfil `build.toml` qué extensiones tiene y no tiene el
  hardware para que el razonamiento sea auditable

**Cómo diagnosticar si vuelve a ocurrir:**
```bash
# 1. Verificar qué opciones GGML_* están ON en el cache
grep "^GGML_" build/llama.cpp/build-out/CMakeCache.txt | grep "=ON"

# 2. Contar instrucciones problemáticas en el binario
objdump -d $(which llama-cli) | grep -cE "shlx|shrx|sarx|rorx|pdep|pext"

# 3. Confirmar instrucción exacta con GDB
gdb -batch -ex "run --version" -ex "x/1i \$rip" --args llama-cli --version 2>&1
```

## ADR-006: Detección de GPU y Aceleración Universal vía Vulkan / CUDA / Metal

**Contexto:** Las GPUs integradas (como Intel HD Graphics 4000, Iris, Arc) y GPUs discretas pueden acelerar considerablemente la ejecución de modelos LLM descargando capas de la CPU a la GPU (`-ngl` / `--n-gpu-layers`).

**Decisión:**
- Crear un detector universal de GPUs (`scripts/commons/detect-gpu.py`) que evalúe disponibilidad de Vulkan, CUDA, ROCm y Metal.
- Utilizar **Vulkan** (`GGML_VULKAN=ON`) como el backend GPU universal multiplataforma para GPUs Intel/AMD/NVIDIA sin CUDA nativo.
- Permitir la descarga dinámica de capas GPU mediante el parámetro `ngl` en `Justfile` (`just run <model> 8080 ngl=99`).

**Consecuencias:**
- `make debug-gpu` y `just gpu-info` diagnostican rápidamente la GPU instalada y el soporte de drivers.
- Equipos con iGPUs Intel HD Graphics 4000 o superiores pueden aprovechar aceleración gráfica mediante Vulkan.

