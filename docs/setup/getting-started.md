# Primeros pasos

## Prerequisitos del sistema

Solo se necesita `git` y `python3` (3.11+) para arrancar. El resto de
dependencias las instala automáticamente `check-deps` según el perfil
de hardware elegido.

```bash
# Debian/Ubuntu
sudo apt-get install -y git python3

# macOS
brew install git python3
```

## Instalación con perfil de hardware

```bash
# 1. Clona este repositorio
git clone https://github.com/rafex/PoC-Llama.cpp.git
cd PoC-Llama.cpp

# 2. Ver perfiles disponibles
make profile-list

# 3. Setup completo: verifica deps, instala si faltan, compila e instala
just setup-profile apple/macmini6.2
```

`setup-profile` ejecuta en orden:
1. `check-deps` — verifica comandos y librerías; llama a `apt-get` con sudo si falta algo
2. `clone` — clona llama.cpp en `build/llama.cpp/` (solo si no existe)
3. `compile` — configura cmake con el perfil y compila
4. `install` — copia binarios a `/opt/llama.cpp/versions/<fecha>-<arch>/` y crea symlinks
5. `post-install` — genera wrappers semánticos y ajusta permisos

El proceso tarda entre 10 y 30 minutos según el hardware.

## Verificar la instalación

```bash
just install-check
llama-cli --version
just install-list
```

## Recompilar (después de un cambio de perfil o error)

```bash
# Limpia el cmake cache sin borrar el repo clonado
make build-clean

# Recompila con el perfil
just compile-profile apple/macmini6.2

# O el flujo completo si también hay que reinstalar
just setup-profile apple/macmini6.2
```

## Descargar un modelo

```bash
# Menú interactivo: lista el catálogo y descarga el modelo elegido
just model-download

# Filtrar por tipo antes del menú
just model-download-type chat
just model-download-type multimodal

# Descargar directamente por ID (sin menú interactivo)
just model-download-id qwen2.5-1.5b-chat-q4

# Ver todos los modelos del catálogo
just model-list

# Ver modelos ya descargados en /srv/models
just models
```

Los modelos se guardan en `/srv/models/{gguf,embeddings,multimodal}/`
según su tipo. El catálogo completo está en `build/models/catalog.toml`.

## Usar los modelos

```bash
# Chat interactivo en terminal
just chat /srv/models/gguf/qwen2.5-1.5b-instruct-q4_k_m.gguf

# Servidor HTTP (API compatible con OpenAI) en puerto 8080
just run /srv/models/gguf/qwen2.5-1.5b-instruct-q4_k_m.gguf 8080

# Benchmark
just bench /srv/models/gguf/qwen2.5-1.5b-instruct-q4_k_m.gguf
```

El servidor queda disponible en `http://localhost:8080`.

## Gestión de versiones

```bash
# Ver versiones instaladas y cuál es la activa
just install-list

# Cambiar versión activa (actualiza symlinks en /usr/local/bin)
just switch-version 2026.05.19-x86_64

# Desinstalar versión activa
make uninstall

# Desinstalar versión específica
make uninstall-version VERSION=2026.05.19-x86_64
```
