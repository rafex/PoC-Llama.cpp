# =============================================================================
# build.mk — clonación, configuración y compilación de llama.cpp
#
# Variables de control:
#   PROFILE  — identificador corto del perfil (ej: apple/macmini6.2)
#              Se resuelve a build/templates/<PROFILE>/build.toml automáticamente.
#              Si se omite, se usan CMAKE_COMMON_FLAGS de commons.mk (detección automática).
#
# Ejemplos:
#   make compile
#   make compile PROFILE=apple/macmini6.2
# =============================================================================

TOML_READER       := scripts/commons/toml-reader.py
TEMPLATES_DIR     := build/templates
FETCH_LATEST_TAG  := scripts/build/fetch-latest-tag.py

ifdef PROFILE
  PROFILE_TOML        := $(TEMPLATES_DIR)/$(PROFILE)/build.toml
  PROFILE_CMAKE_FLAGS := $(shell python3 $(TOML_READER) "$(PROFILE_TOML)" --format cmake)
  BUILD_JOBS          := $(shell python3 $(TOML_READER) "$(PROFILE_TOML)" --key build.jobs)
  ACTIVE_CMAKE_FLAGS  := $(PROFILE_CMAKE_FLAGS) -DCMAKE_INSTALL_PREFIX=$(INSTALL_DIR)
  ACTIVE_JOBS         := $(BUILD_JOBS)
else
  # Flags generados automáticamente por commons.mk según la plataforma
  ACTIVE_CMAKE_FLAGS  := $(CMAKE_COMMON_FLAGS) -DCMAKE_INSTALL_PREFIX=$(INSTALL_DIR)
  ACTIVE_JOBS         := $(shell nproc 2>/dev/null || sysctl -n hw.logicalcpu)
endif

.PHONY: clone update configure compile build-clean build-purge profile-info

## Clona llama.cpp en la última release (o LLAMA_TAG=bXXXX para versión específica)
clone:
	@if [ -d "$(LLAMA_SRC_DIR)/.git" ]; then \
	  printf "$(YELLOW)[WARN]$(RESET)  El repositorio ya existe en $(LLAMA_SRC_DIR).\n"; \
	  printf "         Usa 'make update' para actualizar a la última release.\n"; \
	else \
	  tag=$${LLAMA_TAG:-$$(python3 $(FETCH_LATEST_TAG))}; \
	  printf "$(CYAN)[INFO]$(RESET)  Clonando llama.cpp @ $$tag ...\n"; \
	  git clone --depth=1 --branch "$$tag" $(LLAMA_REPO_URL) $(LLAMA_SRC_DIR) && \
	  printf "$(GREEN)[OK]$(RESET)    Repositorio clonado: llama.cpp $$tag\n"; \
	fi

## Actualiza el repo clonado a la última release (o LLAMA_TAG=bXXXX para versión específica)
update:
	@latest=$${LLAMA_TAG:-$$(python3 $(FETCH_LATEST_TAG))}; \
	if [ ! -d "$(LLAMA_SRC_DIR)/.git" ]; then \
	  printf "$(YELLOW)[WARN]$(RESET)  No hay repo clonado. Ejecutando clone...\n"; \
	  tag=$$latest $(MAKE) clone LLAMA_TAG="$$latest"; \
	else \
	  current=$$(git -C $(LLAMA_SRC_DIR) describe --tags --abbrev=0 2>/dev/null || echo "desconocido"); \
	  printf "$(CYAN)[INFO]$(RESET)  Local     : $$current\n"; \
	  printf "$(CYAN)[INFO]$(RESET)  Disponible: $$latest\n"; \
	  if [ "$$current" = "$$latest" ]; then \
	    printf "$(GREEN)[OK]$(RESET)    Ya estás en la versión más reciente.\n"; \
	  else \
	    printf "$(CYAN)[INFO]$(RESET)  Actualizando $$current → $$latest ...\n"; \
	    rm -rf $(LLAMA_SRC_DIR) $(LLAMA_BUILD_DIR); \
	    git clone --depth=1 --branch "$$latest" $(LLAMA_REPO_URL) $(LLAMA_SRC_DIR) && \
	    printf "$(GREEN)[OK]$(RESET)    Actualizado a $$latest\n"; \
	    printf "$(CYAN)[INFO]$(RESET)  Ejecuta ahora: make compile PROFILE=<tu-perfil>\n"; \
	  fi; \
	fi

## Configura cmake con el perfil activo (PROFILE=... o detección automática)
configure: clone
ifdef PROFILE
	$(call log_info,Perfil TOML: $(PROFILE))
endif
	$(call log_info,Configurando cmake en $(LLAMA_BUILD_DIR)...)
	@cmake -S $(LLAMA_SRC_DIR) -B $(LLAMA_BUILD_DIR) $(ACTIVE_CMAKE_FLAGS)
	$(call log_ok,Configuración cmake completada.)

## Compila llama.cpp
compile: configure
	$(call log_info,Compilando con $(ACTIVE_JOBS) jobs...)
	@cmake --build $(LLAMA_BUILD_DIR) --config Release --parallel $(ACTIVE_JOBS)
	$(call log_ok,Compilación completada.)

## Muestra los flags cmake que se usarían (sin compilar)
profile-info:
ifdef PROFILE
	$(call log_info,Perfil: $(PROFILE)  →  $(PROFILE_TOML))
	@python3 $(TOML_READER) "$(PROFILE_TOML)" --format shell
	@echo ""
	$(call log_info,Flags cmake resultantes:)
	@python3 $(TOML_READER) "$(PROFILE_TOML)" --format cmake | tr ' ' '\n' | grep -v '^$$'
else
	$(call log_info,Sin perfil TOML — usando detección automática de plataforma:)
	@echo "  ACTIVE_CMAKE_FLAGS = $(ACTIVE_CMAKE_FLAGS)"
	@echo "  ACTIVE_JOBS        = $(ACTIVE_JOBS)"
endif

## Lista los perfiles disponibles en build/templates/
profile-list:
	$(call log_info,Perfiles disponibles:)
	@find $(TEMPLATES_DIR) -name "build.toml" \
	  | sed "s|$(TEMPLATES_DIR)/||;s|/build.toml||" \
	  | sort \
	  | sed 's|^|  |'

## Elimina artefactos cmake (mantiene el repo clonado)
build-clean:
	$(call log_warn,Eliminando $(LLAMA_BUILD_DIR)...)
	@rm -rf $(LLAMA_BUILD_DIR)
	$(call log_ok,Limpieza completada.)

## Elimina también el repo clonado
build-purge:
	$(call log_warn,Eliminando $(LLAMA_SRC_DIR) completo...)
	@rm -rf $(LLAMA_SRC_DIR)
	$(call log_ok,Purga completada.)
