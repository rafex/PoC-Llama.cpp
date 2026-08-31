# Manual de uso — PoC-Llama.cpp

Guía completa para compilar, instalar y ejecutar llama.cpp con perfiles de hardware optimizados.

## Índice

1. [Introducción](#1-introducción)
2. [Prerequisitos](#2-prerequisitos)
3. [Instalación rápida](#3-instalación-rápida)
4. [Sistema de perfiles](#4-sistema-de-perfiles)
5. [Perfiles soportados](#5-perfiles-soportados)
6. [Compilación](#6-compilación)
7. [Modelos](#7-modelos)
8. [Runtime](#8-runtime)
9. [Gestión de versiones](#9-gestión-de-versiones)
10. [Diagnóstico](#10-diagnóstico)
11. [Desinstalación](#11-desinstalación)
12. [Contribuir: nuevo hardware](#12-contribuir-nuevo-hardware)

---

## 1. Introducción

PoC-Llama.cpp es una prueba de concepto para ejecutar modelos de lenguaje (LLMs) localmente usando [llama.cpp](https://github.com/ggerganov/llama.cpp). Compila llama.cpp con flags optimizados para la CPU del host, lo instala en una estructura versionada y expone los binarios vía symlinks.

### Arquitectura del proyecto

| Componente | Responsabilidad |
|------------|-----------------|
| `Makefile` | Build, compilación, instalación de binarios |
| `justfile` | Task manager, flujos de alto nivel, runtime |
| `build/templates/` | Perfiles TOML de CPU y hardware |
| `scripts/` | Implementación por dominio (build, install, debug, etc.) |

Principio fundamental: **Makefile nunca llama a just; justfile nunca duplica lógica del Makefile**. Compilar siempre pasa por `make`.

### Estructura de directorios

```
/opt/llama.cpp/
├── versions/
│   └── 2026.07.30-x86_64/        # <fecha>-<arquitectura>
│       ├── bin/                   # Binarios compilados
│       └── models -> /srv/models
├── current -> versions/...        # Symlink a la versión activa
└── models/ -> /srv/models

/srv/models/                       # Modelos persistentes
├── gguf/                          # Modelos de chat e instruct
├── embeddings/                    # Modelos de embeddings
├── rerankers/                     # Modelos de reranking
└── multimodal/                    # Modelos visión+lenguaje

/usr/local/bin/llama-*             # Symlinks a /opt/llama.cpp/current/bin/
```

---

## 2. Prerequisitos

### Dependencias base

Solo se necesita `git` y `python3` (3.11+) para arrancar. El resto se instala automáticamente según el perfil elegido.

```bash
# Debian/Ubuntu
sudo apt-get install -y git python3

# macOS
brew install git python3
```

### Dependencias por perfil

| Perfil | Tipo | Requisito adicional |
|--------|------|---------------------|
| `apple/macmini6.2` | Hardware | gcc, g++, openblas |
| `raspi/4b` | Hardware | gcc, g++, openblas |
| `cpu/intel/cometlake.toml` | CPU (herencia) | **gcc-12+, g++-12+**, openblas |
| `cpu/intel/ivybridge.toml` | CPU (herencia) | gcc, g++, openblas |

El sistema `check-deps` verifica e instala automáticamente las dependencias declaradas en cada perfil.

---

## 3. Instalación rápida

### Flujo recomendado (con perfil explícito)

```bash
git clone https://github.com/rafex/PoC-Llama.cpp.git
cd PoC-Llama.cpp

# Ver perfiles disponibles
make profile-list

# Setup completo: verifica deps, compila, instala
just setup-profile apple/macmini6.2
```

`setup-profile` ejecuta en orden:
1. `check-deps` — verifica comandos y librerías; instala con `apt-get` si falta algo
2. `clone` — clona llama.cpp en `build/llama.cpp/`
3. `compile` — configura cmake con el perfil y compila
4. `install` — copia binarios a `/opt/llama.cpp/versions/<fecha>-<arch>/`
5. `post-install` — genera wrappers semánticos y ajusta permisos

### Flujo sin perfil (detección automática)

```bash
just setup
```

Usa los flags cmake generados por `commons.mk` según la plataforma detectada (macOS → Metal; Linux x86_64 → AVX2/AVX/fallback).

### Verificar la instalación

```bash
llama-cli --version
just install-check
just install-list
```

---

## 4. Sistema de perfiles

### ¿Qué es un perfil?

Un perfil es un archivo TOML que declara:
- **Flags del compilador**: `march`, `mtune`, `cflags`
- **Flags cmake de CPU**: `GGML_AVX2`, `GGML_FMA`, `GGML_BMI2`, etc.
- **Dependencias**: comandos requeridos (`gcc-12`), librerías (`openblas`), paquetes apt

### Tipos de perfiles

| Tipo | Ubicación | Uso directo con `PROFILE=` | Ejemplo |
|------|-----------|---------------------------|---------|
| **Perfil de hardware** | `<vendor>/<device>/build.toml` | Sí | `apple/macmini6.2` |
| **Perfil de CPU** | `cpu/<vendor>/<arch>.toml` | No (solo herencia) | `cpu/intel/cometlake.toml` |

> Los perfiles de CPU son **bibliotecas reutilizables**. No se usan directamente con `PROFILE=` — los perfiles de hardware los heredan mediante la clave `inherits`. Para compilar con un perfil de CPU, primero hay que crear un perfil de hardware que herede de él (ver [Contribuir](#12-contribuir-nuevo-hardware)).

### Herencia

Los perfiles de hardware heredan de un perfil de CPU mediante la clave `inherits`:

```toml
# build.toml del equipo
inherits = "cpu/intel/ivybridge"  # Hereda SIMD, march, cflags, GGML_*

[hardware]
manufacturer = "Apple Inc."
product      = "Macmini6,2"
# ...

[cmake.flags]
# Solo flags específicos del hardware (BLAS, METAL, etc.)
GGML_BLAS        = "ON"
GGML_BLAS_VENDOR = "OpenBLAS"
```

El sistema fusiona ambos perfiles: el de CPU define cómo compilar para el procesador, el de hardware añade datos del equipo y flags de aceleración (BLAS, CUDA, METAL).

---

## 5. Perfiles soportados

### Perfiles usables directamente (`PROFILE=`)

Estos perfiles se pueden usar con `make compile PROFILE=<nombre>` o `just setup-profile <nombre>`:

| Perfil | Equipo | CPU | Cores | SIMD |
|--------|--------|-----|-------|------|
| `apple/macmini6.2` | Apple Mac mini 6,2 | Intel Core i7-3615QM (hereda de ivybridge) | 4C/8T | SSE4.2, AVX |
| `raspi/4b` | Raspberry Pi 4 Model B | ARM Cortex-A72 | 4C/4T | NEON, CRC32 |
| `lenovo/20frs09m1g` | ThinkPad X1 Yoga 1st | Intel Core i7-6600U (hereda de skylake) | 2C/4T | AVX2, FMA, F16C, BMI2, Vulkan |

### Perfiles de CPU (herencia solamente)

Estos perfiles son bibliotecas para que los perfiles de hardware hereden de ellos. No se usan directamente con `PROFILE=`:

| Archivo | Microarquitectura | Generación | SIMD habilitado | gcc requerido | Heredado por |
|---------|-------------------|------------|-----------------|---------------|--------------|
| `cpu/intel/ivybridge.toml` | Intel Ivy Bridge | 3ª gen | SSE4.2, AVX | cualquiera | `apple/macmini6.2` |
| `cpu/intel/cometlake.toml` | Intel Comet Lake | 10ª gen | AVX2, FMA, BMI2, F16C | **gcc-12+** | _(ninguno aún)_ |
| `cpu/intel/skylake.toml` | Intel Skylake | 6ª gen | AVX2, FMA, BMI2, F16C | cualquiera | `lenovo/20frs09m1g` |

### Extensiones por perfil de CPU

| Extensión | Ivy Bridge | Comet Lake |
|-----------|-----------|-------------|
| SSE4.1 | ON | ON |
| SSE4.2 | ON | ON |
| AVX | OFF (ADR-005) | ON |
| AVX2 | OFF | **ON** |
| FMA | OFF | **ON** |
| F16C | OFF | **ON** |
| BMI1 | OFF | **ON** |
| BMI2 | OFF | **ON** |
| AVX-512 | OFF | OFF |

### Cómo elegir el perfil correcto

```bash
# Opción 1: ver la lista de perfiles de hardware usables
make profile-list

# Opción 2: ver todos los perfiles de CPU disponibles para herencia
ls build/templates/cpu/intel/
ls build/templates/cpu/arm/

# Opción 3: inspeccionar los flags de un perfil de CPU
python3 scripts/commons/toml-reader.py build/templates/cpu/intel/cometlake.toml --format cmake

# Opción 4: detectar automáticamente tu CPU (ejecutar en el equipo destino)
python3 scripts/debug/detect-cpu-profile.py
```

Si tu equipo coincide con un perfil de hardware (`apple/macmini6.2`, `raspi/4b`), úsalo directamente. Si solo coincide el procesador (ej: Comet Lake), crea tu propio perfil de hardware que herede del perfil de CPU correspondiente (ver [Contribuir](#12-contribuir-nuevo-hardware)).

---

## 6. Compilación

### Compilar con perfil de hardware

```bash
# Con perfil de hardware (hereda flags de CPU + flags del equipo)
make compile PROFILE=apple/macmini6.2

# Con perfil de hardware para Raspberry Pi
make compile PROFILE=raspi/4b
```

### Compilar sin perfil (detección automática)

```bash
make compile
```

Detecta automáticamente la plataforma (`commons.mk`):
- **macOS**: habilita Metal (`GGML_METAL=ON`)
- **Linux x86_64**: detecta AVX2 → AVX → fallback SSE4.2

### Flujo completo

```bash
# Todo en uno
just setup-profile apple/macmini6.2

# Paso a paso
make clone
make configure PROFILE=apple/macmini6.2
make compile PROFILE=apple/macmini6.2
make install PROFILE=apple/macmini6.2
```

Si tu CPU no tiene un perfil de hardware, crea uno (ver [Contribuir](#12-contribuir-nuevo-hardware)) o usa la detección automática.

### Inspeccionar flags de un perfil

```bash
# Perfil de hardware
make profile-info PROFILE=apple/macmini6.2

# Perfil de CPU (solo TOML, sin compilar)
python3 scripts/commons/toml-reader.py build/templates/cpu/intel/cometlake.toml --format cmake
python3 scripts/commons/toml-reader.py build/templates/cpu/intel/ivybridge.toml --format cmake
```

### Limpiar y recompilar

```bash
# Limpia artefactos cmake (mantiene el repo clonado)
make build-clean

# Recompila con el perfil
make compile PROFILE=apple/macmini6.2

# O el flujo completo
just setup-profile apple/macmini6.2
```

### Eliminar todo y empezar de cero

```bash
# Elimina el repo clonado también
make build-purge

# Vuelve a clonar y compilar
just setup-profile apple/macmini6.2
```

---

## 7. Modelos

### Catálogo curado

El proyecto incluye un catálogo de modelos pre-configurados en `build/models/catalog.toml`.

```bash
# Ver catálogo completo
make model-list

# Ver modelos clasificados según tu hardware (Eficiente / Suficiente / Excede)
make model-list-smart

# Filtrar por tipo
make model-list-smart-type TYPE=chat
make model-list-smart-type TYPE=coding
```

### Descargar modelos

```bash
# Menú interactivo (recomendado)
make model-download

# Menú inteligente: detecta hardware, clasifica y descarga
make model-download-smart

# Menú inteligente filtrado por tipo
make model-download-smart-type TYPE=chat

# Descargar directamente por ID
make model-download-id ID=qwen2.5-1.5b-chat-q4
```

### Directorio de modelos

Los modelos se guardan en `/srv/models/` organizados por tipo:

```
/srv/models/
├── gguf/           # Modelos de chat e instruct (Qwen, Llama, Gemma, etc.)
├── embeddings/     # Modelos de embedding (BGE, Nomic, etc.)
├── rerankers/      # Modelos de reranking
└── multimodal/     # Modelos visión+lenguaje (LLaVA, Qwen2.5-VL, etc.)
```

### Listar modelos descargados

```bash
just models
make debug-models
```

---

## 8. Runtime

### Servidor HTTP (API compatible con OpenAI)

```bash
# Iniciar servidor en puerto 8080
just run /srv/models/gguf/qwen2.5-1.5b-instruct-q4_k_m.gguf 8080

# Puerto personalizado
just run /srv/models/gguf/qwen2.5-1.5b-instruct-q4_k_m.gguf 9090

# Con modelo del catálogo por ID
just run-id qwen2.5-1.5b-chat-q4
```

El servidor expone endpoints compatibles con OpenAI en `http://localhost:8080/v1/chat/completions`.

### Chat interactivo en terminal

```bash
just chat /srv/models/gguf/qwen2.5-1.5b-instruct-q4_k_m.gguf
```

### Benchmark

```bash
just bench /srv/models/gguf/qwen2.5-1.5b-instruct-q4_k_m.gguf
```

### Detener el servidor

```bash
just stop-server
```

---

## 9. Gestión de versiones

### Listar versiones instaladas

```bash
just install-list
make install-list
```

Salida:

```
Versiones instaladas en /opt/llama.cpp/versions:
  2026.07.30-x86_64
  2026.07.28-x86_64

Versión activa (current):
  /opt/llama.cpp/versions/2026.07.30-x86_64
```

### Cambiar versión activa

```bash
just switch-version 2026.07.28-x86_64
```

Esto actualiza el symlink `current` y recrea los symlinks en `/usr/local/bin/`. Sin recompilar.

### Actualizar llama.cpp a una nueva release

```bash
# Detección automática
just upgrade

# Con perfil explícito (siempre recompila)
just upgrade-profile apple/macmini6.2
```

### Forzar una versión específica de llama.cpp

```bash
LLAMA_TAG=b4938 make clone
make compile PROFILE=cpu/intel/cometlake
```

---

## 10. Diagnóstico

### Diagnóstico completo

```bash
make debug
```

Ejecuta: `debug-env` + `debug-cpu` + `debug-binaries` + `debug-models`.

### Solo CPU

```bash
make debug-cpu
```

Muestra modelo de CPU y extensiones SIMD detectadas.

### Solo binarios instalados

```bash
make debug-binaries
```

Muestra binarios en `/opt/llama.cpp/current/bin/` y symlinks en `/usr/local/bin/`.

### Solo entorno

```bash
make debug-env
```

Muestra OS, arquitectura, versión de build, paths de instalación y flags cmake.

### Verificar actualizaciones de llama.cpp

```bash
make check-update
```

Compara la versión local clonada con la última release en GitHub.

### Diagnóstico de SIGILL (ADR-005)

Si un binario crashea con `SIGILL`:

```bash
# Verificar flags GGML activos
grep "^GGML_" build/llama.cpp/build-out/CMakeCache.txt | grep "=ON"

# Contar instrucciones BMI2 en el binario
objdump -d $(which llama-cli) | grep -cE "shlx|shrx|sarx|rorx|pdep|pext"

# Confirmar instrucción exacta con GDB
gdb -batch -ex "run --version" -ex "x/1i \$rip" --args llama-cli --version
```

Ver [docs/architecture/decisions.md](architecture/decisions.md) ADR-005 para más detalles.

---

## 11. Desinstalación

### Desinstalar versión activa

```bash
make uninstall
```

Elimina la versión apuntada por `current` y los symlinks en `/usr/local/bin/`.

### Desinstalar versión específica

```bash
make uninstall-version VERSION=2026.07.28-x86_64
```

### Desinstalar todo (DESTRUCTIVO)

```bash
make uninstall-all
```

Requiere confirmación interactiva. Elimina todo `/opt/llama.cpp/`.

> Los modelos en `/srv/models/` **no se tocan** en ningún target de desinstalación. Son persistentes.

---

## 12. Contribuir: nuevo hardware

Si tu equipo no tiene un perfil en el proyecto, puedes generar uno y contribuirlo.

### Flujo automático (recomendado)

Ejecuta en el equipo destino:

```bash
# Genera perfil de CPU + hardware automáticamente
python3 scripts/debug/detect-cpu-profile.py
```

El script analiza `/proc/cpuinfo`, detecta la microarquitectura, las extensiones SIMD y genera dos archivos:

1. **Perfil de CPU**: `cpu/<vendor>/<arch>.toml` — flags de compilador y GGML
2. **Perfil de hardware**: `<vendor>/<device>/build.toml` — datos del equipo con herencia

Para guardar en disco:

```bash
python3 scripts/debug/detect-cpu-profile.py --output-dir build/templates
```

### Flujo manual

Si no puedes ejecutar el script en el equipo, usa el collector:

```bash
# En el equipo destino
bash scripts/debug/collect-hw-info.sh > mi-equipo.toml

# Copia mi-equipo.toml a tu máquina de desarrollo y genera los perfiles
python3 scripts/debug/detect-cpu-profile.py --from-template mi-equipo.toml
```

### Estructura que debes crear

```
build/templates/
├── cpu/
│   └── <vendor>/
│       └── <arch>.toml         # Perfil de CPU nuevo
└── <vendor>/
    └── <device>/
        └── build.toml           # Perfil de hardware nuevo (hereda de cpu/...)
```

### Ejemplo: agregar soporte para un Dell OptiPlex 7080 con i5-10500T

El perfil de CPU ya existe (`cpu/intel/cometlake.toml`). Solo hay que crear el perfil de hardware:

```bash
# 1. Recopilar datos del equipo
bash scripts/debug/collect-hw-info.sh

# 2. Crear el perfil de hardware
# build/templates/dell/optiplex-7080/build.toml
```

Contenido del perfil de hardware:

```toml
inherits = "cpu/intel/cometlake"

[hardware]
manufacturer   = "Dell Inc."
product        = "OptiPlex 7080"
cpu_model      = "Intel Core i5-10500T"
cpu_arch       = "cometlake"
logical_cpus   = 12
physical_cores = 6
os             = "linux"

[build]
jobs      = 12
type      = "Release"
generator = "Unix Makefiles"

[dependencies]
commands = ["git", "cmake", "gcc-12", "g++-12", "pkg-config"]
pkg_config = ["openblas", "openssl"]
apt_packages = [
  "build-essential", "cmake", "git",
  "gcc-12", "g++-12",
  "libopenblas-dev", "libssl-dev", "pkg-config",
]

[cmake.flags]
BUILD_SHARED_LIBS    = "OFF"
GGML_BLAS            = "ON"
GGML_BLAS_VENDOR     = "OpenBLAS"
GGML_METAL           = "OFF"
LLAMA_BUILD_TESTS    = "OFF"
LLAMA_BUILD_EXAMPLES = "ON"
```

### Validación del perfil

Antes de contribuir, valida que:

```bash
# 1. El TOML es sintácticamente válido
python3 scripts/commons/toml-reader.py build/templates/dell/optiplex-7080/build.toml --format cmake

# 2. La herencia se resuelve correctamente
# Debe mostrar los flags de cometlake.toml más los del hardware

# 3. El perfil aparece en la lista
make profile-list

# 4. Compila sin errores (si tienes acceso al hardware)
make compile PROFILE=dell/optiplex-7080
./build/llama.cpp/build-out/bin/llama-cli --version

# 5. No hay SIGILL
./build/llama.cpp/build-out/bin/llama-cli --version  # Debe imprimir versión sin crash
```

### Lista de verificación para contribuir

- [ ] Perfil de CPU creado (si es una microarquitectura nueva)
- [ ] Perfil de hardware creado con `inherits` correcto
- [ ] Extensiones SIMD declaradas correctamente (`true`/`false`)
- [ ] Flags GGML_* configurados según ADR-005 (defensa en profundidad)
- [ ] Dependencias declaradas (comandos, pkg_config, apt_packages)
- [ ] gcc-12+ en dependencias si se usa `march=cometlake` o posterior
- [ ] GGML_AVX512=OFF si el CPU no lo soporta
- [ ] Perfil validado con `toml-reader.py --format cmake`
- [ ] Probado en hardware real (si es posible)
