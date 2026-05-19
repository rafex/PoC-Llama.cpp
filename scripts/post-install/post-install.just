# =============================================================================
# post-install.just — recetas de post-instalación delegadas a make
# =============================================================================

# Ejecuta todos los pasos de post-instalación
post-install:
    make post-install

# Genera wrappers semánticos sin repetir el install completo
post-install-wrappers:
    make post-install-wrappers
