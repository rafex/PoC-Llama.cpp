# Primeros pasos

## Dependencias requeridas

### macOS
```bash
brew install cmake ninja git
```

### Linux (Debian/Ubuntu)
```bash
sudo apt-get install -y cmake ninja-build build-essential git
```

### Linux (RHEL/Fedora)
```bash
sudo dnf install -y cmake ninja-build gcc-c++ git
```

## Instalación

```bash
# 1. Clona este repositorio
git clone https://github.com/rafex/PoC-Llama.cpp.git
cd PoC-Llama.cpp

# 2. Verifica dependencias
just check-deps

# 3. Flujo completo (clone → compile → install → post-install)
just setup
```

El proceso tarda entre 5 y 20 minutos según el hardware.

## Verificar la instalación

```bash
just install-check
llama-cli --version
```

## Descargar un modelo para probar

```bash
# Ejemplo con un modelo pequeño de Qwen (requiere huggingface-cli)
huggingface-cli download Qwen/Qwen2.5-1.5B-Instruct-GGUF \
  qwen2.5-1.5b-instruct-q4_k_m.gguf \
  --local-dir /srv/models/gguf/

# Probar en modo chat
just chat /srv/models/gguf/qwen2.5-1.5b-instruct-q4_k_m.gguf
```

## Iniciar el servidor HTTP

```bash
just run /srv/models/gguf/qwen2.5-1.5b-instruct-q4_k_m.gguf 8080
```

El servidor queda disponible en `http://localhost:8080` con API compatible con OpenAI.
