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
# Uso:
#   just check-deps                     ← deps base únicamente
#   just check-deps apple/macmini6.2    ← deps base + las del perfil TOML
[private]
check-deps profile="":
    #!/usr/bin/env bash
    set -euo pipefail
    TOML_READER="scripts/commons/toml-reader.py"
    TEMPLATES_DIR="build/templates"
    missing_cmds=()
    missing_libs=()

    # --- Deps base (siempre) --------------------------------------------------
    for cmd in git cmake; do
        command -v "$cmd" &>/dev/null || missing_cmds+=("$cmd")
    done

    # --- Deps del perfil TOML (si se proporcionó) -----------------------------
    if [[ -n "{{profile}}" ]]; then
        toml_file="${TEMPLATES_DIR}/{{profile}}/build.toml"
        if [[ ! -f "$toml_file" ]]; then
            echo "[ERROR] Perfil no encontrado: $toml_file"
            exit 1
        fi
        eval "$(python3 "$TOML_READER" "$toml_file" --format deps)"

        for cmd in $DEP_COMMANDS; do
            command -v "$cmd" &>/dev/null || missing_cmds+=("$cmd")
        done

        if [[ -n "$DEP_PKG_CONFIG" ]]; then
            command -v pkg-config &>/dev/null || missing_cmds+=("pkg-config")
            for lib in $DEP_PKG_CONFIG; do
                pkg-config --exists "$lib" 2>/dev/null || missing_libs+=("$lib")
            done
        fi
    fi

    # --- Reporte --------------------------------------------------------------
    ok=true
    if [[ ${#missing_cmds[@]} -gt 0 ]]; then
        echo "[ERROR] Comandos faltantes: ${missing_cmds[*]}"
        ok=false
    fi
    if [[ ${#missing_libs[@]} -gt 0 ]]; then
        echo "[ERROR] Librerías faltantes (pkg-config): ${missing_libs[*]}"
        if [[ -n "{{profile}}" ]]; then
            toml_file="${TEMPLATES_DIR}/{{profile}}/build.toml"
            eval "$(python3 "$TOML_READER" "$toml_file" --format deps)"
            echo "        Instalar con: sudo apt-get install -y $DEP_APT_PACKAGES"
        fi
        ok=false
    fi
    [[ "$ok" == "true" ]] && echo "[OK] Todas las dependencias están presentes." || exit 1

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
