# =============================================================================
# test.just — pruebas de validación delegadas a make
# =============================================================================

# Suite completa: binarios instalados + ejecución --version
test:
    make test

# Solo verifica que los binarios existen y son ejecutables
test-binaries:
    make test-binaries

# Solo ejecuta --version en cada binario
test-versions:
    make test-versions

# Smoke test: inferencia rápida con el primer modelo disponible
test-smoke:
    make test-smoke

# Prueba de API HTTP OpenAI (/health y /v1/chat/completions)
test-api:
    make test-api

# test-runtime está definido por el dominio scripts/runtime.
