#!/usr/bin/env python3
"""Benchmark y selección de backend para la ejecución de llama.cpp.

Los resultados son locales al equipo y se guardan fuera del repositorio. El
binario actual expone OpenBLAS como dispositivo ``BLAS`` y los dispositivos
Vulkan disponibles; el selector compara esos dispositivos con las mismas
pruebas de prompt processing (pp) y token generation (tg).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_PROMPT = 128
DEFAULT_GENERATION = 128
DEFAULT_BATCH = 128
DEFAULT_REPETITIONS = 3
TIE_TOLERANCE = 0.05
PROFILE_SCHEMA = 1


class RuntimeFailure(RuntimeError):
    """Error controlado que se muestra como diagnóstico de runtime."""


def default_state_dir() -> Path:
    configured = os.environ.get("LLAMA_STATE_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path(os.environ.get("XDG_STATE_HOME", "~/.local/state")).expanduser() / "llama.cpp"


def resolve_model(value: str, repo_root: Path | None = None) -> Path:
    """Resuelve una ruta GGUF o un ID existente del catálogo, sin descargar."""
    direct = Path(value).expanduser()
    if direct.is_file():
        return direct.resolve()

    if repo_root is not None:
        resolver = repo_root / "scripts/models/model-download.py"
        if resolver.is_file():
            result = subprocess.run(
                [sys.executable, str(resolver), "--path", value],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                candidate = Path(result.stdout.strip()).expanduser()
                if candidate.is_file():
                    return candidate.resolve()

    raise RuntimeFailure(
        f"Modelo no encontrado: {value}. Usa una ruta .gguf existente o un ID "
        "del catálogo ya descargado."
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cpu_model() -> str:
    if sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/cpuinfo").read_text(errors="replace").splitlines():
                if line.lower().startswith("model name") and ":" in line:
                    return line.split(":", 1)[1].strip()
        except OSError:
            pass
    if sys.platform == "darwin":
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return platform.processor() or "unknown"


def hardware_info() -> dict[str, Any]:
    values = {
        "system": platform.system(),
        "machine": platform.machine(),
        "cpu_model": cpu_model(),
        "logical_cpus": os.cpu_count() or 1,
    }
    encoded = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    values["fingerprint"] = hashlib.sha256(encoded).hexdigest()[:16]
    return values


def binary_path(name: str, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    env_name = "LLAMA_" + name.upper().replace("-", "_")
    if os.environ.get(env_name):
        return os.environ[env_name]
    found = shutil.which(name)
    if found:
        return found
    installed = Path("/opt/llama.cpp/current/bin") / name
    if installed.is_file():
        return str(installed)
    return name


def discover_devices(llama_bench: str) -> list[str]:
    result = subprocess.run(
        [llama_bench, "--list-devices"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = f"{result.stdout}\n{result.stderr}"
    devices: list[str] = []
    for line in output.splitlines():
        match = re.match(r"^\s*([A-Za-z][A-Za-z0-9_-]*):", line)
        if match:
            name = match.group(1)
            if name not in devices and (name == "BLAS" or name.startswith("Vulkan")):
                devices.append(name)
    if "BLAS" in devices:
        devices.remove("BLAS")
        devices.insert(0, "BLAS")
    return devices


def _json_payload(text: str) -> Any:
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("[")
        end = stripped.rfind("]")
        if start < 0 or end <= start:
            raise RuntimeFailure("llama-bench no devolvió JSON válido")
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError as exc:
            raise RuntimeFailure(f"JSON de llama-bench inválido: {exc}") from exc


def _normalise_json_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        payload = payload.get("results", [payload])
    if not isinstance(payload, list):
        raise RuntimeFailure("El JSON de llama-bench no contiene una lista de resultados")

    records: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict) or "avg_ts" not in item:
            continue
        n_prompt = int(item.get("n_prompt", 0) or 0)
        n_gen = int(item.get("n_gen", 0) or 0)
        test = "pp" if n_prompt > 0 and n_gen == 0 else "tg" if n_gen > 0 else "unknown"
        records.append(
            {
                "test": test,
                "avg_ts": float(item["avg_ts"]),
                "stddev_ts": float(item.get("stddev_ts", 0) or 0),
                "devices": item.get("devices", ""),
                "build_commit": item.get("build_commit", "unknown"),
                "build_number": item.get("build_number"),
                "n_prompt": n_prompt,
                "n_gen": n_gen,
            }
        )
    return [record for record in records if record["test"] != "unknown"]


def _markdown_records(text: str) -> list[dict[str, Any]]:
    rows = [line for line in text.splitlines() if line.strip().startswith("|")]
    if len(rows) < 3:
        raise RuntimeFailure("Markdown de llama-bench sin filas de resultados")
    headers = [part.strip().lower() for part in rows[0].strip().strip("|").split("|")]
    try:
        test_index = headers.index("test")
        speed_index = headers.index("t/s")
    except ValueError as exc:
        raise RuntimeFailure("Markdown de llama-bench sin columnas test/t/s") from exc
    device_index = headers.index("dev") if "dev" in headers else None

    records: list[dict[str, Any]] = []
    for row in rows[2:]:
        values = [part.strip() for part in row.strip().strip("|").split("|")]
        if len(values) <= max(test_index, speed_index):
            continue
        test = values[test_index].lower()
        speed = re.match(r"[-+]?\d+(?:\.\d+)?", values[speed_index])
        if not speed or test not in {"pp", "tg", "pp128", "tg128"}:
            continue
        records.append(
            {
                "test": "pp" if test.startswith("pp") else "tg",
                "avg_ts": float(speed.group(0)),
                "stddev_ts": 0.0,
                "devices": values[device_index] if device_index is not None and len(values) > device_index else "",
                "n_prompt": 1 if test.startswith("pp") else 0,
                "n_gen": 1 if test.startswith("tg") else 0,
            }
        )
    return records


def parse_benchmark_output(text: str, format_hint: str = "json") -> list[dict[str, Any]]:
    """Parsea JSON real y Markdown de llama-bench para poder probar ambos formatos."""
    if format_hint == "md" or re.search(r"\|\s*test\s*\|", text) or re.search(r"\|\s*t/s\s*\|", text):
        return _markdown_records(text)
    return _normalise_json_records(_json_payload(text))


def benchmark_command(
    llama_bench: str,
    model: Path,
    device: str,
    threads: int,
    prompt: int,
    generation: int,
    batch: int,
    repetitions: int,
) -> list[str]:
    ngl = "0" if device == "BLAS" else "99"
    return [
        llama_bench,
        "-m",
        str(model),
        "-p",
        str(prompt),
        "-n",
        str(generation),
        "-t",
        str(threads),
        "-b",
        str(batch),
        "-ub",
        str(batch),
        "-ngl",
        ngl,
        "-dev",
        device,
        "-r",
        str(repetitions),
        "-o",
        "json",
    ]


def run_benchmark(command: list[str], timeout: int = 900) -> list[dict[str, Any]]:
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        message = detail[-1] if detail else "sin salida"
        raise RuntimeFailure(f"benchmark falló ({result.returncode}): {message}")
    return parse_benchmark_output(result.stdout, "json")


def _result_for(records: Iterable[dict[str, Any]], objective: str) -> dict[str, Any] | None:
    matches = [record for record in records if record.get("test") == objective]
    if not matches:
        return None
    return max(matches, key=lambda record: float(record["avg_ts"]))


def select_best(results: list[dict[str, Any]], objective: str, tolerance: float = TIE_TOLERANCE) -> dict[str, Any]:
    candidates = [item for item in results if item.get(objective)]
    if not candidates:
        raise RuntimeFailure(f"No hay resultados válidos para el objetivo {objective}")
    fastest = max(candidates, key=lambda item: float(item[objective]["avg_ts"]))
    threshold = float(fastest[objective]["avg_ts"]) * (1.0 - tolerance)
    near = [item for item in candidates if float(item[objective]["avg_ts"]) >= threshold]
    near.sort(key=lambda item: (0 if item["device"] == "BLAS" else 1, -float(item[objective]["avg_ts"])))
    selected = near[0]
    return {
        "device": selected["device"],
        "ngl": selected["ngl"],
        "avg_ts": selected[objective]["avg_ts"],
        "stddev_ts": selected[objective].get("stddev_ts", 0.0),
        "objective": objective,
    }


def profile_path(state_dir: Path, model_hash: str) -> Path:
    return state_dir / "benchmarks" / f"{model_hash}.json"


def build_profile(
    model: Path,
    model_hash: str,
    results: list[dict[str, Any]],
    devices: list[str],
    parameters: dict[str, int],
) -> dict[str, Any]:
    best = {objective: select_best(results, objective) for objective in ("pp", "tg")}
    build_commit = "unknown"
    for item in results:
        for record in item.get("records", []):
            if record.get("build_commit"):
                build_commit = record["build_commit"]
                break
    return {
        "schema_version": PROFILE_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": {
            "path": str(model),
            "sha256": model_hash,
            "size_bytes": model.stat().st_size,
        },
        "hardware": hardware_info(),
        "llama": {"build_commit": build_commit},
        "parameters": parameters,
        "devices": devices,
        "results": results,
        "best": best,
    }


def save_profile(profile: dict[str, Any], state_dir: Path) -> Path:
    path = profile_path(state_dir, profile["model"]["sha256"])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)
    return path


def load_profile(state_dir: Path, model_hash: str) -> dict[str, Any] | None:
    path = profile_path(state_dir, model_hash)
    try:
        payload = json.loads(path.read_text())
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def profile_compatible(profile: dict[str, Any], model_hash: str, devices: list[str]) -> bool:
    if profile.get("schema_version") != PROFILE_SCHEMA:
        return False
    if profile.get("model", {}).get("sha256") != model_hash:
        return False
    if profile.get("hardware", {}).get("fingerprint") != hardware_info().get("fingerprint"):
        return False
    for objective in ("pp", "tg"):
        selected = profile.get("best", {}).get(objective, {})
        if selected.get("device") not in devices:
            return False
    return True


def print_profile_summary(profile: dict[str, Any], path: Path) -> None:
    print(f"[OK] Perfil guardado: {path}")
    for objective in ("pp", "tg"):
        selected = profile["best"][objective]
        print(
            f"[OK] Mejor {objective}: {selected['device']} "
            f"({selected['avg_ts']:.2f} t/s)"
        )


def benchmark(args: argparse.Namespace) -> int:
    model = resolve_model(args.model, args.repo_root)
    model_hash = sha256_file(model)
    bench = binary_path("llama-bench", args.llama_bench)
    devices = discover_devices(bench)
    if not devices:
        raise RuntimeFailure("No se detectaron dispositivos BLAS/Vulkan en llama-bench")

    parameters = {
        "prompt": args.prompt,
        "generation": args.generation,
        "batch": args.batch,
        "repetitions": args.repetitions,
        "threads": args.threads,
    }
    results: list[dict[str, Any]] = []
    for device in devices:
        print(f"[INFO] Probando {device} ...", flush=True)
        command = benchmark_command(
            bench,
            model,
            device,
            args.threads,
            args.prompt,
            args.generation,
            args.batch,
            args.repetitions,
        )
        try:
            records = run_benchmark(command, args.timeout)
            pp = _result_for(records, "pp")
            tg = _result_for(records, "tg")
            if pp is None and tg is None:
                raise RuntimeFailure("sin mediciones pp/tg")
            results.append(
                {
                    "device": device,
                    "ngl": 0 if device == "BLAS" else 99,
                    "pp": pp,
                    "tg": tg,
                    "records": records,
                }
            )
            print(
                f"[OK] {device}: pp={pp['avg_ts']:.2f} t/s  tg={tg['avg_ts']:.2f} t/s"
                if pp and tg
                else f"[OK] {device}: medición parcial"
            )
        except (RuntimeFailure, subprocess.TimeoutExpired) as exc:
            print(f"[WARN] {device} no disponible: {exc}", file=sys.stderr)

    if not results:
        raise RuntimeFailure("Ningún backend produjo una medición válida")
    profile = build_profile(model, model_hash, results, devices, parameters)
    path = save_profile(profile, args.state_dir)
    print_profile_summary(profile, path)
    selected = profile["best"][args.objective]
    print(f"[INFO] Objetivo solicitado: {args.objective} -> {selected['device']}")
    return 0


def process_exists(name: str) -> bool:
    return subprocess.run(["pgrep", "-x", name], capture_output=True, check=False).returncode == 0


def stop_existing(stop_script: Path | None) -> None:
    if stop_script and stop_script.is_file() and os.access(stop_script, os.X_OK):
        subprocess.run([str(stop_script), "--all", "--force"], check=False)
        return
    if process_exists("llama-server"):
        subprocess.run(["pkill", "-TERM", "-x", "llama-server"], check=False)
        for _ in range(20):
            if not process_exists("llama-server"):
                return
            subprocess.run(["sleep", "0.25"], check=False)
        subprocess.run(["pkill", "-KILL", "-x", "llama-server"], check=False)


def server_command(args: argparse.Namespace, model: Path, selected: dict[str, Any]) -> list[str]:
    threads = args.threads
    batch = args.batch
    command = [
        binary_path("llama-server", args.llama_server),
        "-m",
        str(model),
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--jinja",
        "--ctx-size",
        str(args.ctx_size),
        "-n",
        str(args.n_predict),
        "-t",
        str(threads),
        "-tb",
        str(threads),
        "-b",
        str(batch),
        "-ub",
        str(batch),
        "-ngl",
        str(selected["ngl"]),
    ]
    if selected.get("device"):
        command.extend(["--device", str(selected["device"])])
    if args.cache_ram is not None:
        command.extend(["--cache-ram", str(args.cache_ram)])
    return command + list(args.extra)


def serve(args: argparse.Namespace) -> int:
    model = resolve_model(args.model, args.repo_root)
    model_hash = sha256_file(model)
    bench = binary_path("llama-bench", args.llama_bench)
    devices = discover_devices(bench)
    profile = load_profile(args.state_dir, model_hash)
    selected: dict[str, Any]
    if profile and profile_compatible(profile, model_hash, devices):
        selected = profile["best"][args.objective]
        print(
            f"[INFO] Usando perfil medido: {selected['device']} "
            f"({selected['avg_ts']:.2f} t/s, objetivo={args.objective})"
        )
    else:
        if profile:
            print("[WARN] Perfil ausente, vencido o incompatible; usando fallback BLAS.", file=sys.stderr)
        else:
            print("[WARN] No hay benchmark guardado; usando fallback BLAS.", file=sys.stderr)
        if "BLAS" in devices:
            selected = {"device": "BLAS", "ngl": 0, "avg_ts": 0.0}
        else:
            selected = {"device": None, "ngl": 0, "avg_ts": 0.0}

    stop_existing(Path(args.stop_script) if args.stop_script else Path("/opt/llama.cpp/current/scripts/stop-server.sh"))
    if process_exists("llama-server"):
        raise RuntimeFailure("No fue posible detener el llama-server anterior")
    command = server_command(args, model, selected)
    print("[INFO] Ejecutando: " + " ".join(command))
    if args.dry_run:
        return 0
    completed = subprocess.run(command, check=False)
    return completed.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark y ejecución adaptativa de llama.cpp")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bench = subparsers.add_parser("benchmark", help="mide BLAS/Vulkan y guarda el perfil local")
    bench.add_argument("model")
    bench.add_argument("--objective", choices=["pp", "tg"], default="tg")
    bench.add_argument("--repo-root", type=Path)
    bench.add_argument("--state-dir", type=Path, default=default_state_dir())
    bench.add_argument("--llama-bench")
    bench.add_argument("--threads", type=int, default=os.cpu_count() or 1)
    bench.add_argument("--prompt", type=int, default=DEFAULT_PROMPT)
    bench.add_argument("--generation", type=int, default=DEFAULT_GENERATION)
    bench.add_argument("--batch", type=int, default=DEFAULT_BATCH)
    bench.add_argument("--repetitions", type=int, default=DEFAULT_REPETITIONS)
    bench.add_argument("--timeout", type=int, default=900)
    bench.set_defaults(handler=benchmark)

    serve_parser = subparsers.add_parser("serve", help="ejecuta llama-server con el mejor perfil local")
    serve_parser.add_argument("model")
    serve_parser.add_argument("--objective", choices=["pp", "tg"], default="tg")
    serve_parser.add_argument("--repo-root", type=Path)
    serve_parser.add_argument("--state-dir", type=Path, default=default_state_dir())
    serve_parser.add_argument("--llama-bench")
    serve_parser.add_argument("--llama-server")
    serve_parser.add_argument("--stop-script")
    serve_parser.add_argument("--host", default="0.0.0.0")
    serve_parser.add_argument("--port", type=int, default=43110)
    serve_parser.add_argument("--ctx-size", type=int, default=4096)
    serve_parser.add_argument("--n-predict", type=int, default=512)
    serve_parser.add_argument("--threads", type=int, default=os.cpu_count() or 1)
    serve_parser.add_argument("--batch", type=int, default=256)
    serve_parser.add_argument("--cache-ram", type=int, default=None)
    serve_parser.add_argument("--dry-run", action="store_true")
    serve_parser.add_argument("extra", nargs=argparse.REMAINDER)
    serve_parser.set_defaults(handler=serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (RuntimeFailure, FileNotFoundError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired as exc:
        print(f"[ERROR] timeout ejecutando {exc.cmd}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
