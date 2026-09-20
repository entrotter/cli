from contextlib import redirect_stdout, redirect_stderr
import io
import hashlib
import json
import tempfile
import os
import subprocess
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
from entrotter_cli.main import parser, main, read_json

class CLITests(unittest.TestCase):
    def test_hashed_report_with_malformed_mode_has_no_traceback(self):
        report = json.loads((Path(__file__).parent / 'data/report.json').read_text())
        report.pop('artifact_id')
        report['mode'] = []
        canonical = json.dumps(report, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
        report['artifact_id'] = hashlib.sha256(canonical).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'malformed.json'
            path.write_text(json.dumps(report))
            error = io.StringIO()
            with redirect_stderr(error):
                self.assertEqual(main(['verify', str(path)]), 1)
            self.assertIn('Unknown result mode', error.getvalue())
            self.assertNotIn('Traceback', error.getvalue())

    def test_native_cannot_override_an_api_server(self):
        error = io.StringIO()
        with redirect_stderr(error):
            self.assertEqual(main(['run', '/does/not/exist', '--native']), 1)
        self.assertIn('--native requires --local', error.getvalue())

    def test_local_option(self): self.assertTrue(parser().parse_args(['run','x.json','--local']).local)
    def test_doctor(self):
        f=io.StringIO()
        with redirect_stdout(f): self.assertEqual(main(['doctor']),0)
        self.assertIsInstance(json.loads(f.getvalue())['anvil_installed'],bool)
    def test_doctor_no_secrets(self):
        f=io.StringIO()
        with patch.dict('os.environ',{'ENTROTTER_RPC_URL':'TOP_SECRET'}),redirect_stdout(f): main(['doctor'])
        self.assertNotIn('TOP_SECRET',f.getvalue())
    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'POSIX FIFO regression')
    def test_fifo_input_cannot_wait_for_a_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.fifo'
            os.mkfifo(path)
            result = subprocess.run([sys.executable, '-m', 'entrotter_cli', 'verify', str(path)],
                                    capture_output=True, text=True, timeout=2)
            self.assertEqual(result.returncode, 1)
            self.assertIn('regular file', result.stderr)

    def test_size_limit(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';p.write_text('x'*100)
            with self.assertRaises(ValueError): read_json(str(p),10)
    def test_read_json(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';p.write_text('{"a":1}');self.assertEqual(read_json(str(p),100),{'a':1})
    def test_error_no_traceback(self):
        f=io.StringIO()
        with redirect_stderr(f): self.assertEqual(main(['verify','/no/such/report.json']),1)
        self.assertNotIn('Traceback',f.getvalue())

if __name__=='__main__': unittest.main()
