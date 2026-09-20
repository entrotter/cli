"""CLI output boundary tests with a verified, injected SDK response."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from entrotter_cli.main import main
from entrotter_sdk import RunResult


def result(note='fixture'):
    report = dict(schema_version='0.1.0', mode='fixture', scenario={}, baseline={}, candidate={}, comparison={}, note=note)
    raw = json.dumps(report, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()
    report['artifact_id'] = hashlib.sha256(raw).hexdigest()
    return RunResult.parse(report)


class ExportTests(unittest.TestCase):
    def invoke(self, output, response):
        stdout, stderr = io.StringIO(), io.StringIO()
        scenario = Path(__file__).parent / 'data/fixture.json'
        with patch('entrotter_sdk.Client.run', return_value=response), redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(['run', str(scenario), '-o', str(output)])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_oversized_export_preserves_previous_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'report.json'
            output.write_text('previous contents')
            code, _, error = self.invoke(output, result('x' * (8 * 1024 * 1024)))
            self.assertEqual(code, 1)
            self.assertIn('8 MiB', error)
            self.assertEqual(output.read_text(), 'previous contents')

    def test_successful_export_is_complete_and_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'report.json'
            expected = result()
            code, _, _ = self.invoke(output, expected)
            self.assertEqual(code, 0)
            self.assertEqual(RunResult.parse(json.loads(output.read_bytes())), expected)
            self.assertEqual([p.name for p in Path(directory).iterdir()], ['report.json'])

    def test_failed_replace_preserves_destination_and_removes_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'report.json'
            output.write_text('previous contents')
            with patch('os.replace', side_effect=OSError('injected disk failure')):
                code, _, error = self.invoke(output, result())
            self.assertEqual(code, 1)
            self.assertNotIn('Traceback', error)
            self.assertEqual(output.read_text(), 'previous contents')
            self.assertEqual([p.name for p in Path(directory).iterdir()], ['report.json'])


if __name__ == '__main__':
    unittest.main()
