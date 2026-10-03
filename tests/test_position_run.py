"""Bounded local dispatch, request identity, cancellation and protected exports."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from entrotter_cli.main import main

DATA = Path(__file__).parent / 'data'


class Stopped(BaseException):
    def __init__(self, code): self.code = code


class PositionRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.report = json.loads((DATA/'aave-account-position13.json').read_bytes())
        self.plan = self.root/'plan.json'
        self.plan.write_text(json.dumps(self.report['plan']))
        self.output = self.root/'result.json'
        self.output.write_text('incumbent')
        self.executor = Mock(return_value=deepcopy(self.report))
        observed = types.ModuleType('entrotter_engine.position_observations')
        observed.validate_plan = deepcopy
        observed.run_position = self.executor
        trace = types.ModuleType('entrotter_engine.consumer_observations')
        trace.ObservationStopped = Stopped
        self.modules = {'entrotter_engine': types.ModuleType('entrotter_engine'),
                        'entrotter_engine.position_observations': observed,
                        'entrotter_engine.consumer_observations': trace}
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {'ENTROTTER_EXPORT_STATE_DIR': str(self.root/'ledger')}).start()

    def invoke(self, path=None):
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(sys.modules, self.modules), redirect_stdout(out), redirect_stderr(err):
            code = main(['trace-position', str(path or self.plan), '-o', str(self.output)])
        return code, out.getvalue(), err.getvalue()

    def test_default_dispatch_exports_exact_validated_wrapper_without_HTTP(self):
        with patch('socket.socket', side_effect=AssertionError('No test network')), patch(
            'entrotter_sdk.Client', side_effect=AssertionError('No API')):
            code, out, err = self.invoke()
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(json.loads(self.output.read_text()), self.report)
        self.assertEqual(json.loads(out)['classification'], self.report['classification'])
        self.executor.assert_called_once_with(self.report['plan'])

    def test_foreign_valid_wrapper_and_mutating_executor_cannot_replace_destination(self):
        admitted = deepcopy(self.report['plan']); admitted['account'] = '0x'+'11'*20
        self.plan.write_text(json.dumps(admitted))
        for mutation in (False, True):
            def run(plan):
                if mutation:
                    plan.clear(); plan.update(deepcopy(self.report['plan']))
                return deepcopy(self.report)
            self.executor.side_effect = run
            code, out, err = self.invoke()
            self.assertEqual((code, out), (1, ''))
            self.assertIn('admitted plan', err)
            self.assertEqual(self.output.read_text(), 'incumbent')
        self.assertEqual(json.loads(self.plan.read_text()), admitted)

    def test_invalid_hash_and_wrong_family_preserve_destination_and_stdout(self):
        bad = deepcopy(self.report);bad['classification']['differences']['available_borrows_base'] += 1
        for value in (bad, json.loads((DATA/'report.json').read_bytes())):
            self.executor.return_value = value
            code, out, err = self.invoke()
            self.assertEqual((code, out), (1, ''))
            self.assertNotIn('Traceback', err)
            self.assertEqual(self.output.read_text(), 'incumbent')

    def test_quota_refusal_preserves_destination_and_success_stdout(self):
        with patch('entrotter_cli.main.ExportBudget.write', side_effect=ValueError('Shared export budget exceeded')):
            code,out,err = self.invoke()
        self.assertEqual((code,out),(1,''))
        self.assertIn('export budget',err)
        self.assertEqual(self.output.read_text(),'incumbent')

    def test_deadline_cancellation_and_keyboard_interrupt_preserve_destination(self):
        for exc, expected in ((Stopped('deadline'),124),(Stopped('cancelled'),130),(KeyboardInterrupt(),130)):
            self.executor.side_effect = exc
            code, out, err = self.invoke()
            self.assertEqual((code, out), (expected, ''))
            self.assertNotIn('Traceback', err)
            self.assertEqual(self.output.read_text(), 'incumbent')

    @unittest.skipUnless(os.name=='posix', 'POSIX signal delivery')
    def test_SIGTERM_reaches_cleanup_and_restores_callers_handler(self):
        original = signal.getsignal(signal.SIGTERM)
        cleanup = []
        def run(plan):
            try: signal.raise_signal(signal.SIGTERM)
            finally: cleanup.append(True)
        self.executor.side_effect = run
        code, out, err = self.invoke()
        self.assertEqual((code, out), (130, ''))
        self.assertEqual(cleanup, [True])
        self.assertEqual(signal.getsignal(signal.SIGTERM), original)
        self.assertEqual(self.output.read_text(), 'incumbent')

    def test_missing_or_old_engine_has_no_API_native_or_export_fallback(self):
        self.modules['entrotter_engine.position_observations'] = types.ModuleType('old_engine')
        code, out, err = self.invoke()
        self.assertEqual((code, out), (1, ''))
        self.assertIn('Matching SDK and bounded position Engine', err)
        self.assertEqual(self.output.read_text(), 'incumbent')
        self.executor.assert_not_called()

    def test_input_limits_and_invalid_JSON_fail_before_executor(self):
        for contents in ('x'*262145, '{broken', '['*2000+'0'+']'*2000,
                         '{"through_index":0,"through_index":31}',
                         '{"source":{"chain_id":1,"chain_id":2}}'):
            self.plan.write_text(contents)
            code, out, err = self.invoke()
            self.assertEqual((code, out), (1, ''))
            self.assertEqual(self.output.read_text(), 'incumbent')
        self.executor.assert_not_called()

    @unittest.skipUnless(hasattr(os,'mkfifo'),'POSIX FIFO')
    def test_FIFO_is_rejected_without_waiting_for_writer(self):
        path = self.root/'input.fifo';os.mkfifo(path)
        code, out, err = self.invoke(path)
        self.assertEqual((code, out), (1,''))
        self.assertIn('regular file',err)
        self.executor.assert_not_called()

    def test_no_API_native_profile_callback_or_selector_options(self):
        for flag in ('--api','--native','--profile','--callback','--selector'):
            with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as caught:
                main(['trace-position',str(self.plan),flag,'unused'])
            self.assertEqual(caught.exception.code,2)
        self.executor.assert_not_called()


if __name__=='__main__':unittest.main()
