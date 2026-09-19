from contextlib import redirect_stdout, redirect_stderr
import io
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from entrotter_cli.main import parser, main, read_json

class CLITests(unittest.TestCase):
    def test_local_option(self): self.assertTrue(parser().parse_args(['run','x.json','--local']).local)
    def test_doctor(self):
        f=io.StringIO()
        with redirect_stdout(f): self.assertEqual(main(['doctor']),0)
        self.assertIsInstance(json.loads(f.getvalue())['anvil_installed'],bool)
    def test_doctor_no_secrets(self):
        f=io.StringIO()
        with patch.dict('os.environ',{'ENTROTTER_RPC_URL':'TOP_SECRET'}),redirect_stdout(f): main(['doctor'])
        self.assertNotIn('TOP_SECRET',f.getvalue())
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
