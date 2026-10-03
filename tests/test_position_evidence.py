"""Synthetic child/parser fault verifies pre-assertion CI evidence retention."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests_position import test_position_cli as actual


class PositionEvidenceTests(unittest.TestCase):
    def test_unverified_baseline_fails_but_exact_child_record_is_retained(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            case=actual.ActualPositionCLI("test_actual_default_account_replay_exports_full_verified_records")
            case.output=root/"child.json";case.evidence=root/"evidence";case.evidence.mkdir()
            case.source={};case.env={};case.command=lambda:["synthetic-no-child"]
            case.workers=lambda:[]
            contents=b'{"synthetic_baseline_verified":false}'
            def child(*args,**kwargs):
                case.output.write_bytes(contents)
                return SimpleNamespace(returncode=0,stdout='{"synthetic":true}',stderr="")
            parsed=SimpleNamespace(report={"plan":{}},trace=SimpleNamespace(baseline_verified=False))
            with patch.object(actual.subprocess,"run",side_effect=child),patch.object(actual,"load_position",return_value=parsed):
                with self.assertRaises(AssertionError):
                    case.test_actual_default_account_replay_exports_full_verified_records()
            self.assertEqual((case.evidence/"position.json").read_bytes(),contents)
            process=json.loads((case.evidence/"process.json").read_text())
            self.assertEqual(process["returncode"],0)
            self.assertEqual(process["stdout"],'{"synthetic":true}')
            self.assertEqual(process["owned_workers_after"],[])
            self.assertEqual(process["stderr"],"")

if __name__=="__main__":unittest.main()
