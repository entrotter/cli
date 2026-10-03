"""Actual recorded price wrapper and labelled synthetic controls; offline CLI."""
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from entrotter_cli.main import main
from entrotter_sdk import Client

DATA = Path(__file__).parent / "data"
SAMPLE = DATA / "observed-price32.json"


class ObservedCLITests(unittest.TestCase):
    def invoke(self, command, path):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = main([command, str(path)])
        return status, out.getvalue(), err.getvalue()

    def test_original_records_are_inspected_without_engine_network_or_exports(self):
        self.assertEqual(hashlib.sha256(SAMPLE.read_bytes()).hexdigest(),
                         "7010848300c353310fb78dab7f377daea4226633e49af3c1a384bcb3a579ba9d")
        with patch.dict(sys.modules, {"entrotter_engine": None}), patch.object(
            Client, "_request", side_effect=AssertionError("No HTTP request")
        ), patch("socket.socket", side_effect=AssertionError("No network")), patch(
            "entrotter_cli.main.ExportBudget", side_effect=AssertionError("No export ledger")
        ):
            status, out, err = self.invoke("observed-inspect", SAMPLE)
        self.assertEqual((status, err), (0, ""))
        summary = json.loads(out)
        self.assertEqual(summary["classification"]["price_difference"], 789973126)
        self.assertTrue(summary["trace"]["baseline_receipts_verified"])
        self.assertEqual(summary["trace"]["transaction_count"], 32)
        source = json.loads(SAMPLE.read_bytes())
        self.assertEqual(summary["artifact_id"], source["artifact_id"])
        self.assertEqual(summary["trace"]["artifact_id"], source["trace_artifact_id"])
        self.assertEqual([p["price"] for p in summary["observations"]],
                         [257082415000, 256292441874, 257082415000, 257082415000])
        for row, original in zip(summary["observations"], source["observations"]):
            self.assertEqual(row["head"], original["head"])
            self.assertEqual(row["base_unit"], 100000000)
            self.assertEqual(row["source_code"], original["code"]["source_code"])
            self.assertEqual(row["errors"], [])
        self.assertIn("not signed consumer strategy", summary["scope"])

    def test_verify_checks_both_reports_and_exposes_incomplete_classification(self):
        status, out, err = self.invoke("observed-verify", SAMPLE)
        self.assertEqual((status, err), (0, ""))
        summary = json.loads(out)
        self.assertTrue(summary["integrity_verified"])
        self.assertTrue(summary["classification"]["complete_price_views"])
        self.assertNotIn("observations", summary)
        self.assertIn("not provider authentication", summary["scope"])

    def test_synthetic_controls_preserve_large_exact_values_and_unproven_nulls(self):
        controls = DATA / "observed-controls.json"
        self.assertEqual(hashlib.sha256(controls.read_bytes()).hexdigest(),
                         "b68865916ac365e2ca1093c16439b4baaa628e14b3b2e209f36596f2c09bba67")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "control.json"
            for control in json.loads(controls.read_bytes()):
                with self.subTest(control=control["name"]):
                    report = json.loads(SAMPLE.read_bytes())
                    report.update({k: v for k, v in control.items() if k != "name"})
                    path.write_text(json.dumps(report))
                    for command in ("observed-inspect", "observed-verify"):
                        status, out, err = self.invoke(command, path)
                        self.assertEqual((status, err), (0, ""))
                        summary = json.loads(out)
                        self.assertEqual(summary["classification"], report["classification"])
                        if control["name"] == "large_integer":
                            self.assertEqual(summary["classification"]["baseline_price"], 2**200 - 10)
                            self.assertEqual(summary["classification"]["candidate_price"], 2**200)
                            self.assertEqual(summary["classification"]["price_difference"], 10)
                        else:
                            self.assertIsNone(summary["classification"]["price_difference"])
                    if control["name"] == "rpc_missing_head":
                        status, out, _ = self.invoke("observed-inspect", path)
                        row = json.loads(out)["observations"][0]
                        self.assertIsNone(row["head"])
                        self.assertEqual(row["errors"][0]["code"], "timeout")

    def test_invalid_hash_wrong_family_and_duplicate_keys_have_no_stdout_or_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            report = json.loads(SAMPLE.read_bytes())
            report["classification"]["price_difference"] += 1
            for payload in (json.dumps(report), (DATA / "report.json").read_text(),
                            '{"artifact_id": "a", "artifact_id": "b"}'):
                path.write_text(payload)
                for command in ("observed-inspect", "observed-verify"):
                    status, out, err = self.invoke(command, path)
                    self.assertEqual((status, out), (1, ""))
                    self.assertTrue(err.startswith("Error:"))
                    self.assertNotIn("Traceback", err)

    def test_new_commands_accept_no_execution_or_output_options(self):
        for command in ("observed-inspect", "observed-verify"):
            for option in ("--native", "--api", "--output"):
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                    main([command, str(SAMPLE), option, "unused"])
                self.assertEqual(caught.exception.code, 2)

    def test_old_sdk_has_finite_matching_version_error(self):
        with patch.dict(sys.modules, {"entrotter_sdk": types.ModuleType("entrotter_sdk")}):
            status, out, err = self.invoke("observed-inspect", SAMPLE)
        self.assertEqual((status, out), (1, ""))
        self.assertIn("Matching SDK", err)
        self.assertNotIn("Traceback", err)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO")
    def test_fifo_cannot_wait_for_a_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.fifo"
            os.mkfifo(path)
            result = subprocess.run([sys.executable, "-m", "entrotter_cli",
                                     "observed-inspect", str(path)],
                                    capture_output=True, text=True, timeout=2)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("regular JSON file", result.stderr)


if __name__ == "__main__":
    unittest.main()
