"""Mandatory real Docker CLI executions; never skipped for missing prerequisites."""
import hashlib,json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class ActualAgentCLITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.env={**os.environ,'ENTROTTER_EXPORT_STATE_DIR':str(self.root/'exports')}
        self.model=json.loads((ROOT/'tests/data/agent-recorded-local.json').read_text())
        self.risk=json.loads((ROOT/'tests/data/agent-risk-local.json').read_text())
        self.scenario=self.root/'scenario.json';self.scenario.write_text(json.dumps(self.model['scenario']))

    def invoke(self,args,status=0,env=None):
        result=subprocess.run([sys.executable,'-m','entrotter_cli',*map(str,args)],env=self.env if env is None else env,capture_output=True,text=True,timeout=200)
        self.assertEqual(result.returncode,status,result.stderr)
        return result

    def test_risk_execution_and_replay_match_original_complete_report(self):
        target=self.root/'risk.json';self.invoke(['agent-run',self.scenario,'--steps','0','1','-o',target])
        self.assertEqual(json.loads(target.read_text()),self.risk)
        replayed=self.root/'replayed.json';self.invoke(['replay',target,'-o',replayed])
        self.assertEqual(json.loads(replayed.read_text()),self.risk)
        self.invoke(['verify',replayed])

    def test_original_model_replay_and_inspection_need_no_provider(self):
        target=self.root/'model.json';self.invoke(['replay',ROOT/'tests/data/agent-recorded-local.json','-o',target])
        self.assertEqual(json.loads(target.read_text()),self.model)
        summary=json.loads(self.invoke(['inspect',target]).stdout)['agent']
        self.assertEqual([d['choice'] for d in summary['decisions']],['execute','hold'])
        self.assertFalse(summary['provider']['deterministic']);self.assertIsNone(summary['provider']['cost_usd'])

    def test_changed_state_refuses_then_recovers_without_overwriting(self):
        changed=json.loads(json.dumps(self.model));changed['scenario']['actor_balance_wei']='9000000000000000000';changed.pop('artifact_id')
        changed['artifact_id']=hashlib.sha256(json.dumps(changed,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
        source=self.root/'changed.json';source.write_text(json.dumps(changed));target=self.root/'incumbent.json';target.write_text('incumbent')
        self.invoke(['replay',source,'-o',target],1);self.assertEqual(target.read_text(),'incumbent')
        self.invoke(['replay',ROOT/'tests/data/agent-recorded-local.json','-o',target]);self.assertEqual(json.loads(target.read_text()),self.model)

    def test_missing_image_refuses_without_native_fallback_or_overwrite(self):
        target=self.root/'incumbent.json';target.write_text('incumbent')
        self.invoke(['agent-run',self.scenario,'--steps','0','1','-o',target],1,{**self.env,'ENTROTTER_WORKER_IMAGE':''})
        self.assertEqual(target.read_text(),'incumbent')
