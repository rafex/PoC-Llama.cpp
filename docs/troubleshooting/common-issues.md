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
