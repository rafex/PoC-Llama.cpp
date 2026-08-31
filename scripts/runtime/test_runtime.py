import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime import (
    RuntimeFailure,
    discover_devices,
    parse_benchmark_output,
    profile_compatible,
    resolve_model,
    select_best,
    server_command,
)


class RuntimeParserTests(unittest.TestCase):
    def test_parse_json_benchmark_records(self):
        payload = [
            {"n_prompt": 128, "n_gen": 0, "avg_ts": 10.5, "stddev_ts": 0.2, "devices": "BLAS"},
            {"n_prompt": 0, "n_gen": 128, "avg_ts": 20.5, "stddev_ts": 0.4, "devices": "BLAS"},
        ]
        records = parse_benchmark_output(json.dumps(payload))
        self.assertEqual([record["test"] for record in records], ["pp", "tg"])
        self.assertEqual(records[1]["avg_ts"], 20.5)

    def test_parse_markdown_benchmark_records(self):
        markdown = """\
| model | dev | test | t/s |
| --- | --- | --- | ---: |
| model | BLAS | pp128 | 10.50 ± 0.10 |
| model | BLAS | tg128 | 20.50 ± 0.20 |
"""
        records = parse_benchmark_output(markdown, "md")
        self.assertEqual(records[0]["test"], "pp")
        self.assertEqual(records[1]["test"], "tg")
        self.assertEqual(records[1]["avg_ts"], 20.5)


class RuntimeSelectionTests(unittest.TestCase):
    def test_selects_fastest_generation(self):
        results = [
            {"device": "BLAS", "ngl": 0, "pp": {"avg_ts": 40}, "tg": {"avg_ts": 40}},
            {"device": "Vulkan0", "ngl": 99, "pp": {"avg_ts": 80}, "tg": {"avg_ts": 20}},
        ]
        self.assertEqual(select_best(results, "tg")["device"], "BLAS")
        self.assertEqual(select_best(results, "pp")["device"], "Vulkan0")

    def test_prefers_blas_when_within_five_percent(self):
        results = [
            {"device": "BLAS", "ngl": 0, "pp": {"avg_ts": 100}, "tg": {"avg_ts": 100}},
            {"device": "Vulkan0", "ngl": 99, "pp": {"avg_ts": 104}, "tg": {"avg_ts": 104}},
        ]
        self.assertEqual(select_best(results, "tg")["device"], "BLAS")

    def test_fails_without_objective_measurement(self):
        with self.assertRaises(RuntimeFailure):
            select_best([{"device": "BLAS", "ngl": 0, "tg": None}], "pp")

    @patch("runtime.hardware_info", return_value={"fingerprint": "same"})
    def test_profile_compatibility_requires_model_and_devices(self, _hardware):
        profile = {
            "schema_version": 1,
            "model": {"sha256": "abc"},
            "hardware": {"fingerprint": "same"},
            "best": {
                "pp": {"device": "Vulkan0"},
                "tg": {"device": "BLAS"},
            },
        }
        self.assertTrue(profile_compatible(profile, "abc", ["BLAS", "Vulkan0"]))
        self.assertFalse(profile_compatible(profile, "different", ["BLAS", "Vulkan0"]))
        self.assertFalse(profile_compatible(profile, "abc", ["BLAS"]))


class RuntimeEnvironmentTests(unittest.TestCase):
    @patch(
        "runtime.subprocess.run",
        return_value=type("Result", (), {
            "stdout": "Available devices:\n  Vulkan0: Intel HD 520\n  BLAS: OpenBLAS\n",
            "stderr": "",
            "returncode": 0,
        })(),
    )
    def test_discovers_blas_before_vulkan(self, _run):
        self.assertEqual(discover_devices("llama-bench"), ["BLAS", "Vulkan0"])

    def test_rejects_missing_model(self):
        with self.assertRaises(RuntimeFailure):
            resolve_model("/tmp/does-not-exist-llama-model.gguf")

    def test_server_command_uses_threads_and_batch_separately(self):
        args = type(
            "Args",
            (),
            {
                "llama_server": "/bin/llama-server",
                "host": "127.0.0.1",
                "port": 43110,
                "ctx_size": 4096,
                "n_predict": 512,
                "threads": 4,
                "batch": 256,
                "cache_ram": None,
                "extra": [],
            },
        )()
        command = server_command(args, Path("/tmp/model.gguf"), {"device": "BLAS", "ngl": 0})
        self.assertEqual(command[command.index("-t") + 1], "4")
        self.assertEqual(command[command.index("-tb") + 1], "4")
        self.assertEqual(command[command.index("-b") + 1], "256")
        self.assertEqual(command[command.index("-ub") + 1], "256")
        self.assertEqual(command[command.index("--device") + 1], "BLAS")


if __name__ == "__main__":
    unittest.main()
