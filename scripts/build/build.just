# =============================================================================
# build.just — recetas de build delegadas a make
#
# Uso con perfil TOML:
#   just compile-profile apple/macmini6.2
#   just compile   ← detección automática de plataforma
# =============================================================================

# Clona el repositorio llama.cpp
clone:
    make clone

# Configura cmake (detección automática de plataforma)
configure:
    make configure

# Compila llama.cpp (detección automática)
compile:
    make compile

# Compila llama.cpp con un perfil específico (ej: apple/macmini6.2)
compile-profile profile:
    make compile PROFILE={{profile}}

# Muestra los flags cmake del perfil (sin compilar)
profile-info profile="":
    #!/usr/bin/env bash
    if [[ -z "{{profile}}" ]]; then
        make profile-info
    else
        make profile-info PROFILE="{{profile}}"
    fi

# Lista los perfiles disponibles en build/templates/
profile-list:
    make profile-list

# Limpia artefactos cmake (mantiene el repo clonado)
build-clean:
    make build-clean

# Elimina también el repo clonado (reset total)
build-purge:
    make build-purge
