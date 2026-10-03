"""Agent CLI contract tests; fake optional engine never claims Docker evidence."""
from contextlib import redirect_stdout, redirect_stderr
import io,json,os,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from entrotter_cli.main import main

REFERENCE=Path(__file__).parent/'data/agent-recorded-local.json'

class AgentCLITests(unittest.TestCase):
    def test_replay_exports_complete_unchanged_record(self):
        report=json.loads(REFERENCE.read_text()); execute=Mock(return_value=report)
        runner=types.ModuleType('entrotter_engine.runner');runner.run_agent=execute
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'report.json'
            with patch.dict(sys.modules, {'entrotter_engine':types.ModuleType('entrotter_engine'),'entrotter_engine.runner':runner}), patch.dict(os.environ, {'ENTROTTER_EXPORT_STATE_DIR':directory+'/state'}), redirect_stdout(io.StringIO()):
                self.assertEqual(main(['replay',str(REFERENCE),'-o',str(target)]),0)
            self.assertEqual(json.loads(target.read_text()),report)
            execute.assert_called_once_with(report['scenario'],decision_steps=[0,1],recording=report['agent'],max_requested_gas=2000000)

    def invoke(self, arguments, report=None):
        reference=json.loads(REFERENCE.read_text()); execute=Mock(return_value=reference if report is None else report)
        runner=types.ModuleType('entrotter_engine.runner');runner.run_agent=execute
        with patch.dict(sys.modules, {'entrotter_engine':types.ModuleType('entrotter_engine'),'entrotter_engine.runner':runner}), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            status=main(arguments)
        return status, execute

    def seal(self, report):
        import hashlib
        report.pop('artifact_id',None)
        report['artifact_id']=hashlib.sha256(json.dumps(report,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()).hexdigest()
        return report

    def test_agent_run_uses_bounded_primitive_and_explicit_budget(self):
        reference=json.loads(REFERENCE.read_text())
        with tempfile.TemporaryDirectory() as directory:
            scenario=Path(directory)/'scenario.json';scenario.write_text(json.dumps(reference['scenario']))
            with patch.dict(os.environ, {'ENTROTTER_EXPORT_STATE_DIR':directory+'/state'}):
                status,execute=self.invoke(['agent-run',str(scenario),'--steps','0','1','--gas-budget','21000','-o',directory+'/result.json'])
            self.assertEqual(status,0)
            execute.assert_called_once_with(reference['scenario'],decision_steps=[0,1],recording=None,max_requested_gas=21000)

    def test_replay_refuses_divergence_before_replacing_destination(self):
        changed=json.loads(REFERENCE.read_text());changed['assumptions'].append('Different output');self.seal(changed)
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'report.json';target.write_text('incumbent')
            status,execute=self.invoke(['replay',str(REFERENCE),'-o',str(target)],changed)
            self.assertEqual(status,1);execute.assert_called_once();self.assertEqual(target.read_text(),'incumbent')

    def test_invalid_recording_parameters_fail_before_engine_call(self):
        changes=[lambda r:r.pop('agent'),lambda r:r['agent'].update(exchanges=[]),
                 lambda r:r['agent']['exchanges'][0]['request']['observation'].update(step=True),
                 lambda r:r['agent']['exchanges'][0]['request']['limits'].update(remaining_requested_gas=2.0),
                 lambda r:r['agent']['exchanges'][0]['response'].update(choice=[]),
                 lambda r:r['agent']['exchanges'][1]['request']['observation'].update(step=0)]
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'reference.json';target=Path(directory)/'report.json';target.write_text('incumbent')
            for change in changes:
                report=json.loads(REFERENCE.read_text());change(report);source.write_text(json.dumps(self.seal(report)))
                status,execute=self.invoke(['replay',str(source),'-o',str(target)])
                self.assertEqual(status,1);execute.assert_not_called();self.assertEqual(target.read_text(),'incumbent')

    def test_tampered_hash_cannot_launch_or_export(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'reference.json';report=json.loads(REFERENCE.read_text());report['agent']['provider']['model']='tampered';source.write_text(json.dumps(report))
            status,execute=self.invoke(['replay',str(source),'-o',directory+'/out.json'])
            self.assertEqual(status,1);execute.assert_not_called();self.assertFalse((Path(directory)/'out.json').exists())

    def test_inspection_displays_choices_and_provenance_without_engine(self):
        out=io.StringIO()
        with patch.dict(sys.modules, {'entrotter_engine':None,'entrotter_engine.runner':None}), redirect_stdout(out):
            self.assertEqual(main(['inspect',str(REFERENCE)]),0)
        summary=json.loads(out.getvalue())['agent'];self.assertEqual([d['choice'] for d in summary['decisions']],['execute','hold']);self.assertFalse(summary['provider']['deterministic']);self.assertIsNone(summary['provider']['cost_usd'])

    def test_inspection_rejects_response_fields_that_can_mislabel_a_step(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'reference.json'
            report=json.loads(REFERENCE.read_text())
            report['agent']['exchanges'][0]['response']['step']=31
            source.write_text(json.dumps(self.seal(report)))
            out,err=io.StringIO(),io.StringIO()
            with patch.dict(sys.modules, {'entrotter_engine':None,'entrotter_engine.runner':None}), redirect_stdout(out), redirect_stderr(err):
                self.assertEqual(main(['inspect',str(source)]),1)
            self.assertEqual(out.getvalue(),'')
            self.assertIn('supported agent recording',err.getvalue())

    def test_replay_rejects_extra_response_fields_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'reference.json'
            target=Path(directory)/'report.json';target.write_text('incumbent')
            for extra in [{'step':31},{'unused_field':'unsupported'}]:
                with self.subTest(extra=extra):
                    report=json.loads(REFERENCE.read_text())
                    report['agent']['exchanges'][0]['response'].update(extra)
                    source.write_text(json.dumps(self.seal(report)))
                    status,execute=self.invoke(['replay',str(source),'-o',str(target)])
                    self.assertEqual(status,1)
                    execute.assert_not_called()
                    self.assertEqual(target.read_text(),'incumbent')

    def test_missing_engine_is_explicit_and_preserves_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'report.json';target.write_text('incumbent')
            with patch.dict(sys.modules, {'entrotter_engine':None,'entrotter_engine.runner':None}), redirect_stderr(io.StringIO()):
                self.assertEqual(main(['replay',str(REFERENCE),'-o',str(target)]),2)
            self.assertEqual(target.read_text(),'incumbent')

    def test_native_or_api_override_is_unavailable_for_agent_commands(self):
        for args in [['replay',str(REFERENCE),'--native'],['agent-run','x','--steps','0','--api','https://example.com']]:
            with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as caught:
                main(args)
            self.assertEqual(caught.exception.code,2)

    @unittest.skipUnless(hasattr(os,'mkfifo'),'POSIX FIFO')
    def test_replay_fifo_cannot_wait_for_a_writer(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'reference.fifo';os.mkfifo(source)
            result=subprocess.run([sys.executable,'-m','entrotter_cli','replay',str(source)],capture_output=True,text=True,timeout=2)
            self.assertEqual(result.returncode,1);self.assertIn('regular file',result.stderr)

    def test_legacy_provider_signature_is_rejected_without_fallback(self):
        runner=types.ModuleType('entrotter_engine.runner')
        def legacy(scenario,controller):
            self.fail('Legacy native controller must not be called')
        runner.run_agent=legacy
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'out.json';target.write_text('incumbent')
            with patch.dict(sys.modules, {'entrotter_engine':types.ModuleType('entrotter_engine'),'entrotter_engine.runner':runner}),redirect_stderr(io.StringIO()):
                self.assertEqual(main(['replay',str(REFERENCE),'-o',str(target)]),1)
            self.assertEqual(target.read_text(),'incumbent')
