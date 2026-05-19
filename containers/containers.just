# =============================================================================
# containers.just — recetas de containers por aplicativo
#
# Importar en justfile raíz cuando se agreguen aplicativos contenerizados.
# Cada aplicativo tendrá su propio subdirectorio en containers/.
# =============================================================================

# Muestra ayuda de containers
containers-help:
    @echo "Recetas de containers disponibles:"
    @echo "  containers-help — este mensaje"
    @echo ""
    @echo "  Agrega recetas por aplicativo según se desarrollen."
