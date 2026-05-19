# =============================================================================
# uninstall.just — desinstalación delegada a make
# =============================================================================

# Desinstala la versión activa y limpia symlinks
uninstall:
    make uninstall

# Solo elimina symlinks de /usr/local/bin
uninstall-symlinks:
    make uninstall-symlinks

# Desinstala una versión específica (pasa VERSION como argumento)
uninstall-version version:
    make uninstall-version VERSION={{version}}

# ¡DESTRUCTIVO! Elimina todo /opt/llama.cpp
uninstall-all:
    make uninstall-all
