#!/usr/bin/env python3
"""
toml-reader.py — Lee un perfil build.toml y emite flags para cmake/shell/make/deps.

Soporta herencia mediante la clave `inherits` en el build.toml:

  inherits = "cpu/intel/ivybridge"

La ruta es relativa al directorio raíz de templates (build/templates/).
El perfil hijo sobreescribe valores del padre en caso de conflicto.
Las secciones tipo dict ([cmake.flags], [compiler]) se fusionan en profundidad.

Uso:
  python3 scripts/commons/toml-reader.py <perfil.toml> --format cmake
  python3 scripts/commons/toml-reader.py <perfil.toml> --format shell
  python3 scripts/commons/toml-reader.py <perfil.toml> --format make
  python3 scripts/commons/toml-reader.py <perfil.toml> --format deps
  python3 scripts/commons/toml-reader.py <perfil.toml> --key build.jobs
"""

import sys
import argparse
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # pip install tomli
    except ModuleNotFoundError:
        sys.exit(
            "[ERROR] Se requiere Python 3.11+ o instalar tomli: pip install tomli"
        )


def _load_raw(path: str) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def _deep_merge(base: dict, override: dict) -> dict:
    """Fusiona override sobre base recursivamente. override gana en conflicto."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load(path: str) -> dict:
    """Carga un perfil TOML resolviendo herencia con `inherits`."""
    profile_path = Path(path).resolve()
    data = _load_raw(str(profile_path))

    inherits = data.pop("inherits", None)
    if not inherits:
        return data

    # El raíz de templates está 2 niveles arriba de <vendor>/<model>/build.toml
    # Estructura esperada: build/templates/<vendor>/<model>/build.toml
    templates_root = profile_path.parents[2]
    cpu_path = templates_root / f"{inherits}.toml"

    if not cpu_path.exists():
        sys.exit(
            f"[ERROR] Perfil base no encontrado: {cpu_path}\n"
            f"        Declarado en: {profile_path}\n"
            f"        inherits = \"{inherits}\""
        )

    base = _load_raw(str(cpu_path))
    return _deep_merge(base, data)


def cmake_flags(data: dict) -> str:
    cmake = data.get("cmake", {}).get("flags", {})
    compiler = data.get("compiler", {})
    build = data.get("build", {})
    build_type = build.get("type", "Release")
    generator = build.get("generator", "")

    parts = []

    if generator:
        parts.append(f'-G "{generator}"')

    parts.append(f"-DCMAKE_BUILD_TYPE={build_type}")

    march = compiler.get("march", "")
    mtune = compiler.get("mtune", "")
    extra = compiler.get("cflags", "")

    if march or mtune or extra:
        cpu_flags = " ".join(filter(None, [
            f"-march={march}" if march else "",
            f"-mtune={mtune}" if mtune else "",
            extra,
        ]))
        parts.append(f'-DCMAKE_C_FLAGS="{cpu_flags}"')
        parts.append(f'-DCMAKE_CXX_FLAGS="{cpu_flags}"')

    for key, val in cmake.items():
        parts.append(f"-D{key}={val}")

    return " ".join(parts)


def deps_vars(data: dict) -> str:
    dep = data.get("dependencies", {})
    commands = " ".join(dep.get("commands", []))
    pkg_config = " ".join(dep.get("pkg_config", []))
    apt = " ".join(dep.get("apt_packages", []))
    lines = [
        f'DEP_COMMANDS="{commands}"',
        f'DEP_PKG_CONFIG="{pkg_config}"',
        f'DEP_APT_PACKAGES="{apt}"',
    ]
    return "\n".join(lines)


def shell_vars(data: dict) -> str:
    compiler = data.get("compiler", {})
    build = data.get("build", {})
    hw = data.get("hardware", {})

    march = compiler.get("march", "")
    mtune = compiler.get("mtune", "")
    extra = compiler.get("cflags", "")
    cpu_flags = " ".join(filter(None, [
        f"-march={march}" if march else "",
        f"-mtune={mtune}" if mtune else "",
        extra,
    ]))

    lines = [
        f'BUILD_TYPE="{build.get("type", "Release")}"',
        f'BUILD_JOBS="{build.get("jobs", 4)}"',
        f'BUILD_GENERATOR="{build.get("generator", "")}"',
        f'COMPILER_CFLAGS="{cpu_flags}"',
        f'COMPILER_CXXFLAGS="{cpu_flags}"',
        f'HW_ARCH="{hw.get("cpu_arch", "")}"',
        f'HW_PRODUCT="{hw.get("product", "")}"',
        f'PROFILE_CMAKE_FLAGS="{cmake_flags(data)}"',
    ]
    return "\n".join(lines)


def make_vars(data: dict) -> str:
    lines = []
    for line in shell_vars(data).splitlines():
        key, _, val = line.partition("=")
        clean = val.strip('"')
        lines.append(f"{key} := {clean}")
    return "\n".join(lines)


def get_key(data: dict, dotted: str) -> str:
    parts = dotted.split(".")
    node = data
    for p in parts:
        if not isinstance(node, dict) or p not in node:
            sys.exit(f"[ERROR] Clave '{dotted}' no encontrada en el perfil.")
        node = node[p]
    return str(node)


def main() -> None:
    parser = argparse.ArgumentParser(description="Lee build.toml y emite flags.")
    parser.add_argument("profile", help="Ruta al archivo build.toml")
    parser.add_argument(
        "--format",
        choices=["cmake", "shell", "make", "deps"],
        default="cmake",
        help="Formato de salida (default: cmake)",
    )
    parser.add_argument(
        "--key",
        help="Extrae un valor puntual usando notación dotted (ej: build.jobs)",
    )
    args = parser.parse_args()

    data = load(args.profile)

    if args.key:
        print(get_key(data, args.key))
        return

    if args.format == "cmake":
        print(cmake_flags(data))
    elif args.format == "shell":
        print(shell_vars(data))
    elif args.format == "make":
        print(make_vars(data))
    elif args.format == "deps":
        print(deps_vars(data))


if __name__ == "__main__":
    main()
