# =============================================================================
# build.just — recetas de build delegadas a make
# justfile NUNCA duplica lógica de compilación; delega a Makefile/build.mk.
# =============================================================================

# Clona el repositorio llama.cpp
clone:
    make clone

# Configura cmake
configure:
    make configure

# Compila llama.cpp
compile:
    make compile

# Limpia artefactos de build sin borrar el repo clonado
build-clean:
    make build-clean

# Elimina también el repo clonado (reset total)
build-purge:
    make build-purge
