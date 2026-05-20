# Problemas comunes

## Error: `-ffinite-math-only` en ggml

**Síntoma:**
```
error: #error "some routines in ggml.c require non-finite math arithmetics
       -- pass -fno-finite-math-only to the compiler to fix"
```

**Causa:** `-ffast-math` habilita implícitamente `-ffinite-math-only`, que ggml
prohíbe porque sus rutinas usan NaN e infinitos.

**Solución:** el perfil debe incluir `-fno-finite-math-only` para sobrescribir
ese subconjunto de `-ffast-math`. Verificar en `build.toml`:
```toml
[compiler]
cflags = "-O3 -ffast-math -fno-finite-math-only"
```

Luego limpiar el cmake cache y recompilar:
```bash
make build-clean
just compile-profile apple/macmini6.2
```

## `check-deps` reporta falsos positivos (arrays vacíos)

**Síntoma:** `[WARN] Comandos faltantes: ` (línea vacía) aunque todo está instalado.

**Causa:** versión de `check-deps` anterior al fix de deduplicación con arrays vacíos.

**Solución:** `git pull` para obtener la corrección.

## `llama-cli` no se encuentra en PATH después de install

**Causa:** los symlinks en `/usr/local/bin` se crearon bien pero el shell tiene el
PATH cacheado.

```bash
hash -r          # limpia la caché de comandos en bash/zsh
which llama-cli  # debe apuntar a /usr/local/bin/llama-cli
just install-check
```

## El servidor no responde después de `just run`

1. **Modelo no existe en la ruta:**
   ```bash
   just models
   ```

2. **Puerto en uso:**
   ```bash
   ss -tlnp | grep 8080
   ```

3. **RAM insuficiente** para el modelo — ver [guía de modelos](../models/guide.md).

## cmake no encuentra OpenBLAS

**Síntoma:** `Could NOT find BLAS` durante la configuración cmake.

**Causa:** `libopenblas-dev` no está instalado.

**Solución:**
```bash
just check-deps apple/macmini6.2   # instala automáticamente
```

O manualmente:
```bash
sudo apt-get install -y libopenblas-dev pkg-config
```

## cmake no encuentra OpenSSL

**Síntoma:** `Could NOT find OpenSSL` — warning durante la configuración.

**Impacto:** `llama-server` compila sin soporte HTTPS. Para uso local no es crítico.

**Solución:**
```bash
just check-deps apple/macmini6.2   # instala libssl-dev automáticamente
make build-clean
just compile-profile apple/macmini6.2
```

## Rollback a versión anterior

```bash
just install-list                          # ver versiones disponibles
just switch-version 2026.05.10-x86_64     # cambiar versión activa
```

## Recompilar desde cero

```bash
make build-purge                           # elimina también el repo clonado
just setup-profile apple/macmini6.2        # clona, compila e instala de nuevo
```

---

## SIGILL (rc=132) al ejecutar `llama-cli`

**Síntoma:**
```
bash: llama-cli -m model.gguf ...: Instrucción ilegal
[FAIL]  llama-cli falló (rc=132)
```

**Causa raíz:** instrucción BMI2 (`SHLX`) generada en el binario y ejecutada en
hardware sin BMI2 (por ejemplo, Intel Ivy Bridge — Core i7-3xxxQM, 3ª generación).

### Diagnóstico rápido

```bash
# 1. ¿El binario tiene instrucciones SHLX (BMI2)?
objdump -d $(which llama-cli) | grep -c shlx

# 2. ¿El hardware tiene BMI2?
grep -o 'bmi[^ ]*' /proc/cpuinfo | sort -u
# Ivy Bridge: sin salida. Haswell+: bmi1 bmi2

# 3. Confirmar la instrucción exacta con GDB
gdb -batch -ex "set confirm off" \
    -ex "run --version" \
    -ex "x/1i \$rip" \
    --args llama-cli --version 2>&1 | tail -5
```

### Por qué ocurre (la trampa del cmake)

ggml tiene una opción cmake `GGML_BMI2` cuyo **default es `ON`**.
En `ggml/src/ggml-cpu/CMakeLists.txt` hay:

```cmake
# línea ~329
list(APPEND ARCH_FLAGS -mbmi2)   # cuando GGML_BMI2=ON
```

Este flag se inyecta vía `target_compile_options(ggml PRIVATE ...)`, que el
compilador recibe **después** de `CMAKE_C_FLAGS`. Como GCC usa el último flag
cuando hay conflicto, `-mbmi2` pisa cualquier `-mno-bmi2` que pongamos en
`CMAKE_C_FLAGS`. Resultado: el binario contiene SHLX aunque el perfil diga
`-mno-bmi2`.

### Solución

Añadir `GGML_BMI2 = "OFF"` explícitamente en el perfil `build.toml`. Eso
impide que cmake inyecte el flag en origen:

```toml
[cmake.flags]
GGML_AVX    = "OFF"   # también desactiva paths de código que asumen BMI2
GGML_AVX2   = "OFF"
GGML_BMI2   = "OFF"   # ← clave: evita -mbmi2 vía target_compile_options
GGML_F16C   = "OFF"
GGML_FMA    = "OFF"
GGML_NATIVE = "OFF"

[compiler]
# -mno-bmi -mno-bmi2: segunda barrera por si algún path de cmake lo re-añade
cflags = "-O3 -ffast-math -fno-finite-math-only -mno-avx -mno-avx2 -mno-fma -mno-f16c -mno-bmi -mno-bmi2"
```

Reconstruir desde cero después de actualizar el perfil:

```bash
git pull
make build-clean compile PROFILE=apple/macmini6.2
make install PROFILE=apple/macmini6.2
just test-smoke
```

### Verificación post-fix

```bash
# Debe devolver 0
objdump -d $(which llama-cli) | grep -c shlx

# El CMakeCache debe mostrar OFF
grep "GGML_BMI2" build/llama.cpp/build-out/CMakeCache.txt
# → GGML_BMI2:BOOL=OFF
```

### Modelos de CPU y soporte de extensiones x86

| Generación Intel | AVX | F16C | FMA3 | BMI1 | BMI2 | AVX2 |
|-----------------|-----|------|------|------|------|------|
| Ivy Bridge (3ª gen, i7-3xxxQM) | ✓ | ✓ | — | — | — | — |
| Haswell (4ª gen) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Broadwell+ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

Para verificar las capacidades del hardware activo:
```bash
grep -E "avx|fma|bmi|f16c" /proc/cpuinfo | tr ' ' '\n' | sort -u | grep -v "^$"
```
