"""Original recorded account comparison is inspected offline, never re-executed."""
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import asdict
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from entrotter_cli.main import main
from entrotter_sdk import Client, load_position

SAMPLE = Path(__file__).parent / "data/aave-account-position13.json"

class PositionCLITests(unittest.TestCase):
    def invoke(self, command, path=SAMPLE):
        out,err=io.StringIO(),io.StringIO()
        with redirect_stdout(out),redirect_stderr(err):code=main([command,str(path)])
        return code,out.getvalue(),err.getvalue()

    def test_complete_original_account_and_price_views_without_network_engine_or_ledger(self):
        with patch.dict(sys.modules,{"entrotter_engine":None}),patch.object(Client,"_request",side_effect=AssertionError("No HTTP")),patch("socket.socket",side_effect=AssertionError("No network")),patch("entrotter_cli.main.ExportBudget",side_effect=AssertionError("No ledger")):
            code,out,err=self.invoke("position-inspect")
        self.assertEqual((code,err),(0,""));summary=json.loads(out);position=load_position(SAMPLE)
        self.assertEqual(summary["classification"],json.loads(json.dumps(asdict(position.classification))))
        self.assertEqual(summary["observations"],json.loads(json.dumps([asdict(x) for x in position.observations])))
        self.assertEqual(summary["price_observations"],json.loads(json.dumps([asdict(x) for x in position.prices.observations])))
        self.assertEqual(summary["prices"]["classification"],json.loads(json.dumps(asdict(position.prices.classification))))
        self.assertEqual(summary["prices"]["artifact_id"],position.prices.artifact_id)
        self.assertEqual(summary["trace"]["artifact_id"],position.trace.artifact_id)
        self.assertEqual(summary["trace"]["transaction_count"],13)
        self.assertEqual(summary["account"],position.account)
        self.assertIn("not",summary["scope"])
        self.assertEqual(summary["classification"]["differences"]["health_factor_wad"],3852169807877337)

    def test_verify_includes_all_three_ids_and_exact_classification(self):
        code,out,err=self.invoke("position-verify")
        self.assertEqual((code,err),(0,""));s=json.loads(out);p=load_position(SAMPLE)
        self.assertTrue(s["integrity_verified"])
        self.assertEqual(s["artifact_id"],p.artifact_id)
        self.assertNotIn("observations",s)
        self.assertEqual(s["classification"],json.loads(json.dumps(asdict(p.classification))))

    def test_invalid_wrong_family_and_duplicate_json_leave_stdout_empty(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"bad.json";r=json.loads(SAMPLE.read_bytes());r["classification"]["differences"]["available_borrows_base"]=0
            for payload in [json.dumps(r),'{"account":1,"account":2}',(SAMPLE.parent/"observed-price32.json").read_text()]:
                path.write_text(payload)
                for command in ["position-inspect","position-verify"]:
                    code,out,err=self.invoke(command,path);self.assertEqual((code,out),(1,""));self.assertNotIn("Traceback",err)

    def test_old_sdk_fails_with_matching_source_error(self):
        with patch.dict(sys.modules,{"entrotter_sdk":types.ModuleType("old_sdk")}):code,out,err=self.invoke("position-inspect")
        self.assertEqual((code,out),(1,""));self.assertIn("Matching SDK",err)

    def test_offline_commands_accept_no_execution_or_export_options(self):
        for command in ["position-inspect","position-verify"]:
            for flag in ["--api","--native","--output","--profile"]:
                with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as caught:main([command,str(SAMPLE),flag,"unused"])
                self.assertEqual(caught.exception.code,2)

if __name__ == "__main__":unittest.main()
