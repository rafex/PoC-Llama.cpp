# Problemas comunes

## La compilación falla con error de AVX

**Síntoma:** cmake falla mencionando instrucciones AVX no soportadas.

**Causa:** el CPU detectado no soporta las flags generadas automáticamente.

**Solución:**
```bash
# Ver qué flags se detectaron
make debug-cpu

# Compilar sin optimizaciones nativas
CMAKE_PLATFORM_FLAGS="-DGGML_NATIVE=OFF" make compile
```

## `llama-cli` no se encuentra en PATH después de install

**Causa:** los symlinks en `/usr/local/bin` apuntan a la versión activa, pero
el shell tiene el PATH cacheado.

**Solución:**
```bash
# En bash/zsh
hash -r

# Verificar
just install-check
which llama-cli
```

## El servidor no responde después de `just run`

**Posibles causas:**

1. El modelo no existe en la ruta especificada:
   ```bash
   just models
   ```

2. Puerto en uso:
   ```bash
   lsof -i :8080
   ```

3. RAM insuficiente para el modelo elegido — ver [guía de modelos](../models/guide.md).

## Metal/GPU no se activa en macOS

**Verificar que se compiló con Metal:**
```bash
make debug-env | grep METAL
llama-cli --version  # debe mencionar Metal
```

Si no aparece Metal, recompilar:
```bash
make build-clean
make compile
```

## Rollback a versión anterior

```bash
# Ver versiones disponibles
just install-list

# Cambiar a versión anterior
just switch-version 2026.05.10-arm64
```
