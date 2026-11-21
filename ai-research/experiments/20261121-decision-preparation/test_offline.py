"""Offline-only causal/schema/budget fixtures. No real credentials or networking."""
from pathlib import Path
from types import SimpleNamespace
from contextlib import contextmanager,redirect_stdout
from collections import Counter
import copy,hashlib,importlib.util,io,json,os,tempfile,unittest,urllib.error

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('decision_probe_tested',HERE/'decision_probe.py');probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
PLAN=json.loads((HERE/'plan.json').read_text());CASES=json.loads((HERE/'Private/frozen-cases.json').read_text())

@contextmanager
def fixture(cases=None,error_status=None,schema_error=False):
 original_here,original_private,original_opener=probe.HERE,probe.PRIVATE,probe.urllib.request.build_opener
 prior_key=os.environ.get('DEEPINFRA_API_KEY');calls=[]
 with tempfile.TemporaryDirectory(prefix='decision-offline-test-',dir=HERE) as temp:
  folder=Path(temp);private=folder/'Private';private.mkdir();probe.HERE=folder;probe.PRIVATE=private
  cases=copy.deepcopy(cases if cases is not None else CASES[:2]);plan=copy.deepcopy(PLAN);plan['payloads_sha256']=probe.digest(cases);plan['estimated_total_conservative_reservation_usd']=sum(c['usd_reserved'] for c in cases)
  probe.save(private/'frozen-cases.json',cases);probe.save(folder/'plan.json',plan)
  auth={'approved':True,'model_ids':plan['models'],'plan_sha256':probe.sha(folder/'plan.json'),'max_usd':1.,'numeric_features_and_past_labels_to_deepinfra_approved':True}
  probe.save(folder/'authorization.json',auth);os.environ['DEEPINFRA_API_KEY']='OFFLINE_FIXTURE_ONLY_NOT_A_REAL_KEY'
  class FakeReply(io.BytesIO):
   def __init__(self,value):super().__init__(json.dumps(value).encode());self.headers={}
  class FakeOpener:
   def open(self,request,timeout=0):
    body=json.loads(request.data);calls.append(body)
    assert request.full_url==probe.API and b'OFFLINE_FIXTURE' not in request.data
    if error_status:raise urllib.error.HTTPError(probe.API,error_status,'offline fixture',{},io.BytesIO(b'synthetic error'))
    return FakeReply({'model':body['model'],'answers':{'positive':{'type':'noul','noul':'invalid' if schema_error else .6}},'usage':{'input_tokens':50,'output_tokens':1}})
  probe.urllib.request.build_opener=lambda *args:FakeOpener()
  try:yield folder,private,calls
  finally:
   probe.HERE,probe.PRIVATE,probe.urllib.request.build_opener=original_here,original_private,original_opener
   if prior_key is None:os.environ.pop('DEEPINFRA_API_KEY',None)
   else:os.environ['DEEPINFRA_API_KEY']=prior_key

class OfflineTests(unittest.TestCase):
 def test_counts_and_budget_bound(self):
  self.assertEqual(Counter(c['condition'] for c in CASES),{'full':460,'repeat':46,'zero':64})
  self.assertAlmostEqual(sum(c['usd_reserved'] for c in CASES),.995808,places=12)
  for c in CASES:self.assertLessEqual(len(probe.canonical(c['body']).encode()),2000 if c['condition']=='zero' else 4000)
 def test_current_outcome_and_identity_do_not_affect_payload(self):
  r={'features':[1.,2.,3.,4.,5.],'y':0,'ns':111,'end_ns':222,'day':'1900-01-01','stress_net_cents':-500}
  a=probe.payload(r,[],PLAN['feature_order'],PLAN['models'][0]);r.update(y=1,ns=9999999,end_ns=99999999,day='2099-12-31',stress_net_cents=1_000_000)
  self.assertEqual(a,probe.payload(r,[],PLAN['feature_order'],PLAN['models'][0]))
  self.assertEqual(set(a['state']),{'task','feature_order','past_format','current','earlier_examples'})
 def test_live_source_train_only_examples(self):
  source=probe.load_source();dates,rows,_=source.data();expected={}
  for block,train,test in source.splits(rows,dates):
   tr=sorted(train,key=lambda i:rows[i]['ns'])[-32:]
   self.assertLess(max(rows[i]['end_ns'] for i in tr),min(rows[i]['ns'] for i in test))
   expected[block]=[[probe.round_value(v) for v in rows[i]['features']]+[int(rows[i]['y'])] for i in tr]
  for c in CASES:
   self.assertEqual(c['body']['state']['earlier_examples'],[] if c['condition']=='zero' else expected[c['block']])
 def test_audit_selection_and_repeats_exact(self):
  main={(c['case_key'],c['model']):c for c in CASES if c['condition']=='full'}
  for model in PLAN['models']:
   for kind,n in [('zero',32),('repeat',23)]:
    cases=[c for c in CASES if c['model']==model and c['condition']==kind]
    self.assertEqual(len(cases),n);self.assertEqual(len({c['block'] for c in cases}),9)
   for c in CASES:
    if c['condition']=='repeat' and c['model']==model:self.assertEqual(c['body_sha256'],main[c['case_key'],model]['body_sha256'])
 def test_redirect_disabled(self):
  self.assertIsNone(probe.NoRedirect().redirect_request(None,None,302,'',{},'https://outside.invalid'))
 def test_valid_response_stays_local_in_fixture(self):
  with fixture() as (folder,private,calls),redirect_stdout(io.StringIO()):
   probe.run(SimpleNamespace(authorization=str(folder/'authorization.json')))
   self.assertEqual(len(calls),2);saved=probe.read_jsonl(private/'responses.jsonl')
   self.assertTrue(all(x['probability']==.6 for x in saved));self.assertNotIn('OFFLINE_FIXTURE',(private/'responses.jsonl').read_text())
 def test_http_errors_stop_at_first_no_retry(self):
  for status in (401,403,404,429):
   with self.subTest(status=status),fixture(error_status=status) as (folder,private,calls),redirect_stdout(io.StringIO()):
    with self.assertRaises(SystemExit):probe.run(SimpleNamespace(authorization=str(folder/'authorization.json')))
    self.assertEqual(len(calls),1);self.assertEqual(json.loads((folder/'progress.json').read_text())['state'],'blocked_after_first_error_no_retry')
 def test_schema_error_stops_at_first(self):
  with fixture(schema_error=True) as (folder,private,calls),redirect_stdout(io.StringIO()):
   with self.assertRaises(SystemExit):probe.run(SimpleNamespace(authorization=str(folder/'authorization.json')))
   self.assertEqual(len(calls),1);self.assertEqual(probe.read_jsonl(private/'responses.jsonl')[0]['status'],'request_or_schema_error')
 def test_budget_rejects_before_network(self):
  with fixture() as (folder,private,calls),redirect_stdout(io.StringIO()):
   auth=json.loads((folder/'authorization.json').read_text());auth['max_usd']=.001;probe.save(folder/'authorization.json',auth)
   with self.assertRaises(AssertionError):probe.run(SimpleNamespace(authorization=str(folder/'authorization.json')))
   self.assertEqual(calls,[])
 def test_complete_evaluator_with_explicit_synthetic_responses(self):
  with fixture(CASES) as (folder,private,calls),redirect_stdout(io.StringIO()):
   responses=[]
   for c in CASES:
    r={k:c[k] for k in ['case_key','condition','model','y','session','block','usd_reserved']};r.update(status='ok',probability=.6,usage_input_tokens=50)
    responses.append(r)
   (private/'responses.jsonl').write_text('\n'.join(probe.canonical(x) for x in responses)+'\n')
   probe.evaluate(SimpleNamespace())
   result=json.loads((folder/'results.json').read_text());self.assertEqual(result['common_later_cases'],230);self.assertEqual(result['requests_recorded'],570)
   for model in PLAN['models']:
    self.assertAlmostEqual(result['metrics'][model]['common_support']['auc'],.5)
    self.assertEqual(result['mechanism_diagnostics'][model]['repeat_valid_pairs'],23)
    self.assertEqual(result['mechanism_diagnostics'][model]['zero_shot_successes'],32)
    self.assertEqual(result['paired_uncertainty_vs_TabPFN'][model]['valid_auc_bootstrap_draws'],1999)
   self.assertEqual(calls,[])

if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(OfflineTests);result=unittest.TextTestRunner(verbosity=2).run(suite)
 summary={'status':'passed' if result.wasSuccessful() else 'FAILED','tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
  'real_API_calls':0,'real_model_outputs_generated':False,'real_credentials_read':False,'scope':'Offline actual-source provenance plus synthetic HTTP/schema/budget/evaluation fixtures;not model performance proof',
  'runner_sha256':probe.sha(HERE/'decision_probe.py'),'test_source_sha256':probe.sha(Path(__file__)),'completed_at_utc':probe.stamp()}
 probe.save(HERE/'offline-tests.json',summary)
 raise SystemExit(0 if result.wasSuccessful() else 1)
