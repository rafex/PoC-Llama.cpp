# =============================================================================
# debug.just — diagnóstico delegado a make
# =============================================================================

# Diagnóstico completo: entorno, CPU, binarios, modelos
debug:
    make debug

# Solo muestra variables de entorno
debug-env:
    make debug-env

# Solo muestra capacidades CPU detectadas
debug-cpu:
    make debug-cpu

# Solo muestra estado de binarios instalados
debug-binaries:
    make debug-binaries

# Solo muestra modelos disponibles
debug-models:
    make debug-models
