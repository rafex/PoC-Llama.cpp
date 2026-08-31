# =============================================================================
# runtime.just — targets de runtime delegados a make
# =============================================================================

# Benchmark reproducible y perfil local por modelo
benchmark-best model objective="tg":
    make benchmark-best MODEL="{{model}}" OBJECTIVE="{{objective}}"

# Ejecuta el servidor con el perfil medido
run-best model port="43110" objective="tg":
    make run-best MODEL="{{model}}" PORT="{{port}}" OBJECTIVE="{{objective}}"

# Pruebas unitarias del runtime adaptativo
test-runtime:
    make test-runtime
