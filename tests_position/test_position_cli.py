"""Mandatory actual default-worker CLI tests; no native or fixture replacement."""
import json
import hashlib
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from entrotter_sdk import load_position


class ActualPositionCLI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.getenv('ENTROTTER_WORKER_IMAGE') or not os.getenv('ENTROTTER_RPC_URL'):
            raise RuntimeError('Actual position CLI gate requires configured image/archive RPC')
        cls.plan = Path(os.environ['ENTROTTER_POSITION_PLAN']).resolve()
        cls.source = json.loads(cls.plan.read_text())
        cls.evidence = Path(os.environ.get('ENTROTTER_POSITION_EVIDENCE','.quality/position-cli/actual'))
        cls.evidence.mkdir(parents=True,exist_ok=True)
        import entrotter_cli, entrotter_sdk, entrotter_engine
        modules = {}
        for package in (entrotter_cli, entrotter_sdk, entrotter_engine):
            folder = Path(package.__file__).parent
            modules[package.__name__] = {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(folder.glob('*.py'))
            }
        (cls.evidence/'launch.json').write_text(json.dumps({
            'worker_image': os.environ['ENTROTTER_WORKER_IMAGE'],
            'plan_sha256': hashlib.sha256(cls.plan.read_bytes()).hexdigest(),
            'Python': sys.version.split()[0],
            'source_modules_sha256': modules,
            'scope': 'Operator image and exact imported source/plan at gate launch; no RPC secrets recorded.'
        }, indent=2)+'\n')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name);self.output=self.root/'observed.json'
        self.env=dict(os.environ);self.env['ENTROTTER_EXPORT_STATE_DIR']=str(self.root/'ledger')
        self.assertEqual(self.workers(),[],'A prior worker must not be concealed or removed')

    def workers(self):
        prefix=['docker']
        if os.environ.get('ENTROTTER_DOCKER_SOCKET'):
            prefix += ['--host','unix://'+os.environ['ENTROTTER_DOCKER_SOCKET']]
        return subprocess.check_output(prefix+['ps','--all','--filter','label=org.entrotter.worker=true','--format','{{.ID}}'],text=True,timeout=10).splitlines()

    def command(self):
        return [sys.executable,'-m','entrotter_cli','trace-position',str(self.plan),'-o',str(self.output)]

    def test_actual_default_account_replay_exports_full_verified_records(self):
        run=subprocess.run(self.command(),env=self.env,capture_output=True,text=True,timeout=190)
        # Preserve the original child result before any proof assertion can fail.
        # This is evidence retention, not a change to replay success semantics.
        if self.output.exists():
            (self.evidence/'position.json').write_bytes(self.output.read_bytes())
        (self.evidence/'process.json').write_text(json.dumps({
            'returncode':run.returncode,'stdout':run.stdout,'stderr':run.stderr,
            'owned_workers_after':self.workers(),
            'scope':'Exact child output retained before receipt/record assertions; no RPC configuration recorded.'
        },indent=2)+'\n')
        self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(run.stderr,'')
        observed=load_position(self.output);report=observed.report
        self.assertEqual(report['plan'],self.source)
        self.assertTrue(observed.trace.baseline_verified)
        self.assertEqual(len(observed.trace.transactions),13)
        self.assertEqual([x.candidate.status for x in observed.trace.transactions],['executed']*12+['skipped'])
        for tx in observed.trace.transactions:self.assertEqual(tx.baseline.receipt,tx.original_receipt)
        self.assertTrue(observed.classification.complete_account_views)
        self.assertEqual(observed.classification.differences.available_borrows_base,81628966124)
        self.assertEqual(observed.classification.differences.health_factor_wad,3852169807877337)
        self.assertEqual([r.price for r in observed.prices.observations],[257082415000,256292441874,257082415000,257082415000])
        original=load_position(os.environ['ENTROTTER_POSITION_REFERENCE']).report
        self.assertEqual(report['observations'],original['observations'])
        self.assertEqual(report['classification'],original['classification'])
        for key in ['observations','classification','profile','scope']:
            self.assertEqual(report['price_report'][key],original['price_report'][key])
        stable=lambda x:{k:v for k,v in x.items() if k not in {'runtime_seconds','artifact_id'}}
        self.assertEqual(stable(report['price_report']['trace_report']),stable(original['price_report']['trace_report']))
        summary=json.loads(run.stdout);self.assertEqual(summary['artifact_id'],observed.artifact_id)
        self.assertEqual(summary['trace_artifact_id'],observed.trace.artifact_id)
        self.assertEqual(summary['price_artifact_id'],observed.prices.artifact_id)
        self.assertEqual(summary['classification'],report['classification'])
        self.assertEqual(self.workers(),[])
        (self.evidence/'position.json').write_bytes(self.output.read_bytes())
        (self.evidence/'success-summary.json').write_text(json.dumps({'returncode':0,'stdout':summary,'owned_workers_after':[]},indent=2)+'\n')

    def test_missing_worker_fails_without_export_or_native_fallback(self):
        self.output.write_text('incumbent');self.env.pop('ENTROTTER_WORKER_IMAGE',None)
        run=subprocess.run(self.command(),env=self.env,capture_output=True,text=True,timeout=10)
        self.assertEqual(run.returncode,1);self.assertEqual(run.stdout,'')
        self.assertEqual(self.output.read_text(),'incumbent');self.assertNotIn('Traceback',run.stderr)
        self.assertEqual(self.workers(),[])
        (self.evidence/'missing-worker.json').write_text(json.dumps({'returncode':run.returncode,'stderr':run.stderr,'destination_preserved':True,'owned_workers_after':[]},indent=2)+'\n')

    def test_real_SIGTERM_cancels_owned_worker_and_preserves_destination(self):
        self.output.write_text('incumbent')
        process=subprocess.Popen(self.command(),env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            until=time.monotonic()+15
            while time.monotonic()<until:
                if self.workers():break
                if process.poll() is not None:self.fail('CLI exited before actual worker admission')
                time.sleep(.05)
            else:self.fail('Actual labelled worker was not admitted')
            process.send_signal(signal.SIGTERM)
            stdout,stderr=process.communicate(timeout=15)
        finally:
            if process.poll() is None:
                process.kill();process.communicate(timeout=10)
        self.assertEqual(process.returncode,130,stderr);self.assertEqual(stdout,'')
        self.assertIn('cancelled',stderr);self.assertNotIn('Traceback',stderr)
        self.assertEqual(self.output.read_text(),'incumbent');self.assertEqual(self.workers(),[])
        (self.evidence/'cancelled.json').write_text(json.dumps({'returncode':130,'stderr':stderr,'actual_worker_admitted':True,'destination_preserved':True,'owned_workers_after':[]},indent=2)+'\n')


if __name__=='__main__':unittest.main()
