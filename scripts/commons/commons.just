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

# --- Receta: verificar e instalar dependencias del sistema -------------------
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
    apt_packages=""

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
        apt_packages="$DEP_APT_PACKAGES"

        for cmd in $DEP_COMMANDS; do
            command -v "$cmd" &>/dev/null || missing_cmds+=("$cmd")
        done

        # Verificar librerías solo si pkg-config ya está disponible;
        # si no lo está, quedará en missing_cmds y se instalará junto con las libs.
        if [[ -n "$DEP_PKG_CONFIG" ]] && command -v pkg-config &>/dev/null; then
            for lib in $DEP_PKG_CONFIG; do
                pkg-config --exists "$lib" 2>/dev/null || missing_libs+=("$lib")
            done
        elif [[ -n "$DEP_PKG_CONFIG" ]]; then
            missing_libs+=($DEP_PKG_CONFIG)
        fi
    fi

    # Deduplica arrays
    mapfile -t missing_cmds < <(printf '%s\n' "${missing_cmds[@]}" | sort -u)
    mapfile -t missing_libs < <(printf '%s\n' "${missing_libs[@]}" | sort -u)

    # --- Sin faltantes: todo bien ---------------------------------------------
    if [[ ${#missing_cmds[@]} -eq 0 && ${#missing_libs[@]} -eq 0 ]]; then
        echo "[OK] Todas las dependencias están presentes."
        exit 0
    fi

    # --- Hay faltantes: intentar instalar con apt-get -------------------------
    [[ ${#missing_cmds[@]} -gt 0 ]] && echo "[WARN] Comandos faltantes: ${missing_cmds[*]}"
    [[ ${#missing_libs[@]} -gt 0 ]] && echo "[WARN] Librerías faltantes: ${missing_libs[*]}"

    if [[ -z "$apt_packages" ]] || ! command -v apt-get &>/dev/null; then
        echo "[ERROR] No se puede instalar automáticamente. Instala manualmente y vuelve a intentar."
        exit 1
    fi

    echo "[INFO] Instalando dependencias: $apt_packages"
    if [[ $EUID -eq 0 ]]; then
        apt-get install -y $apt_packages
    else
        sudo apt-get install -y $apt_packages
    fi

    # --- Verificación post-instalación ----------------------------------------
    failed=()
    for cmd in "${missing_cmds[@]}"; do
        command -v "$cmd" &>/dev/null || failed+=("$cmd")
    done
    for lib in "${missing_libs[@]}"; do
        pkg-config --exists "$lib" 2>/dev/null || failed+=("lib:$lib")
    done

    if [[ ${#failed[@]} -gt 0 ]]; then
        echo "[ERROR] Siguen faltando tras la instalación: ${failed[*]}"
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
