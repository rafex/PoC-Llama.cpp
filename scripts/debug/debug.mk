# =============================================================================
# debug.mk — diagnóstico del entorno, binarios y runtime
# Incluido por el Makefile raíz.
# =============================================================================

.PHONY: debug debug-env debug-cpu debug-binaries debug-models check-update

## Muestra diagnóstico completo
debug: debug-env debug-cpu debug-binaries debug-models

## Variables de entorno y paths relevantes
debug-env:
	$(call log_info,=== Entorno ===)
	@echo "  OS              = $(OS)"
	@echo "  ARCH            = $(ARCH)"
	@echo "  BUILD_DATE      = $(BUILD_DATE)"
	@echo "  INSTALL_VERSION = $(INSTALL_VERSION)"
	@echo "  INSTALL_DIR     = $(INSTALL_DIR)"
	@echo "  INSTALL_CURRENT = $(INSTALL_CURRENT)"
	@echo "  MODELS_DIR      = $(MODELS_DIR)"
	@echo "  LLAMA_SRC_DIR   = $(LLAMA_SRC_DIR)"
	@echo "  CMAKE_FLAGS     = $(CMAKE_COMMON_FLAGS)"

## Capacidades de CPU detectadas
debug-cpu:
	$(call log_info,=== CPU ===)
ifeq ($(OS),Darwin)
	@sysctl -n machdep.cpu.brand_string 2>/dev/null || true
	@sysctl -n machdep.cpu.features 2>/dev/null | tr ' ' '\n' | grep -iE 'avx|sse|neon|fma|bmi' | sort || true
else
	@grep -m1 "model name" /proc/cpuinfo || true
	@grep -m1 "flags"      /proc/cpuinfo | tr ' ' '\n' | grep -iE 'avx|sse|neon|fma|bmi' | sort || true
endif

## Estado de binarios instalados
debug-binaries:
	$(call log_info,=== Binarios en $(INSTALL_CURRENT)/bin ===)
	@if [ -d "$(INSTALL_CURRENT)/bin" ]; then \
	  ls -lh $(INSTALL_CURRENT)/bin/; \
	else \
	  echo "  (directorio no encontrado)"; \
	fi
	$(call log_info,=== Symlinks en $(SYMLINK_BIN) ===)
	@ls -lh $(SYMLINK_BIN)/llama-* 2>/dev/null || echo "  (ninguno)"

## Compara la versión local de llama.cpp con la última release en GitHub
check-update:
	$(call log_info,=== Versión de llama.cpp ===)
	@python3 - <<'EOF'
import subprocess, urllib.request, json, sys, os

REPO_DIR  = "build/llama.cpp/src"
GH_API    = "https://api.github.com/repos/ggerganov/llama.cpp/releases/latest"
COLORS    = {"green": "\033[32m", "yellow": "\033[33m", "red": "\033[31m",
             "cyan": "\033[36m", "bold": "\033[1m", "reset": "\033[0m"}

def c(color, text):
    return f"{COLORS[color]}{text}{COLORS['reset']}"

# --- Versión local ---
local_tag = None
if os.path.isdir(REPO_DIR + "/.git"):
    try:
        tag = subprocess.check_output(
            ["git", "-C", REPO_DIR, "describe", "--tags", "--abbrev=0"],
            stderr=subprocess.DEVNULL, text=True).strip()
        local_tag = tag
        commit = subprocess.check_output(
            ["git", "-C", REPO_DIR, "log", "--oneline", "-1"],
            stderr=subprocess.DEVNULL, text=True).strip()
        print(f"  Local clonado : {c('bold', tag)}  ({commit})")
    except subprocess.CalledProcessError:
        commit = subprocess.check_output(
            ["git", "-C", REPO_DIR, "log", "--oneline", "-1"],
            stderr=subprocess.DEVNULL, text=True).strip()
        print(f"  Local clonado : {c('yellow', '(sin tag)')}  {commit}")
else:
    print(f"  {c('yellow', '[WARN]')} llama.cpp no está clonado en {REPO_DIR}")
    print(f"         Ejecuta: make clone")
    sys.exit(0)

# --- Versión instalada (llama-cli --version) ---
try:
    out = subprocess.check_output(["llama-cli", "--version"],
        stderr=subprocess.STDOUT, text=True).strip().splitlines()
    ver_line = next((l for l in out if "version" in l.lower()), out[0] if out else "")
    print(f"  Instalado     : {c('cyan', ver_line or '(sin output)')}")
except (subprocess.CalledProcessError, FileNotFoundError):
    print(f"  Instalado     : {c('yellow', '(llama-cli no encontrado en PATH)')}")

# --- Última release en GitHub ---
try:
    req = urllib.request.Request(GH_API, headers={"User-Agent": "PoC-Llama.cpp"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    latest_tag  = data["tag_name"]
    latest_date = data["published_at"][:10]
    print(f"  Última release: {c('bold', latest_tag)}  ({latest_date})")
except Exception as e:
    print(f"  {c('yellow', '[WARN]')} No se pudo consultar GitHub: {e}")
    sys.exit(0)

# --- Comparar ---
print()
def build_num(tag):
    return int(tag.lstrip("b")) if tag and tag.lstrip("b").isdigit() else 0

local_n  = build_num(local_tag)
latest_n = build_num(latest_tag)

if local_n == 0:
    print(f"  {c('yellow', '[?]')}  No se puede comparar — tag local no reconocido.")
elif local_n >= latest_n:
    print(f"  {c('green', '[OK]')} Estás en la última versión ({latest_tag}).")
else:
    diff = latest_n - local_n
    print(f"  {c('yellow', '[UPDATE]')} Hay una versión más reciente disponible.")
    print(f"           Local : {local_tag}  →  Disponible : {latest_tag}  ({diff} builds de diferencia)")
    print()
    print(f"  Para actualizar:")
    print(f"    make build-purge")
    print(f"    just setup-profile <tu-perfil>")
EOF

## Estado del directorio de modelos
debug-models:
	$(call log_info,=== Modelos en $(MODELS_DIR) ===)
	@if [ -d "$(MODELS_DIR)" ]; then \
	  find $(MODELS_DIR) -name "*.gguf" -exec ls -lh {} \; 2>/dev/null || echo "  (sin modelos .gguf)"; \
	else \
	  echo "  (directorio $(MODELS_DIR) no existe)"; \
	fi
