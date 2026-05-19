# =============================================================================
# commons.just — variables y recetas utilitarias compartidas
# Importado por el justfile raíz.
# =============================================================================

# --- Variables base -----------------------------------------------------------
install_base    := "/opt/llama.cpp"
models_dir      := "/srv/models"
symlink_bin     := "/usr/local/bin"
llama_repo_url  := "https://github.com/ggerganov/llama.cpp.git"
llama_src_dir   := justfile_directory() / "build/llama.cpp"

build_date      := `date +%Y.%m.%d`
arch            := `uname -m`
os              := `uname -s`

install_version := build_date + "-" + arch
install_dir     := install_base / "versions" / install_version
install_current := install_base / "current"

# --- Receta: verificar dependencias del sistema ------------------------------
[private]
check-deps:
    #!/usr/bin/env bash
    set -euo pipefail
    missing=()
    for cmd in git cmake gcc; do
        command -v "$cmd" &>/dev/null || missing+=("$cmd")
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "[ERROR] Dependencias faltantes: ${missing[*]}"
        exit 1
    fi
    echo "[OK] Todas las dependencias están presentes."

# --- Receta: mostrar variables de entorno ------------------------------------
[private]
show-env:
    @echo "install_base    = {{install_base}}"
    @echo "install_version = {{install_version}}"
    @echo "install_dir     = {{install_dir}}"
    @echo "models_dir      = {{models_dir}}"
    @echo "llama_src_dir   = {{llama_src_dir}}"
    @echo "os              = {{os}}"
    @echo "arch            = {{arch}}"
