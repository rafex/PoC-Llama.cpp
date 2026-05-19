# =============================================================================
# install.just — recetas de instalación delegadas a make
# =============================================================================

# Instala binarios, crea estructura de modelos y configura symlinks
install:
    make install

# Solo actualiza symlinks (útil al cambiar de versión activa manualmente)
install-symlinks:
    make install-symlinks

# Verifica que los binarios estén en PATH
install-check:
    make install-check

# Lista versiones instaladas y cuál es la activa
install-list:
    make install-list
