"""Correct-cohort offline fixtures only:no real requests or real key access."""
from common import *
from contextlib import contextmanager,redirect_stdout
from types import SimpleNamespace
from collections import Counter
import copy,io,os,tempfile,unittest,urllib.error
import cloud_probe as probe
from cohort import price_context,si_context
PLAN=json.loads((PUBLIC/'cloud-plan.json').read_text())
CASES=json.loads((PRIVATE/'cloud-cases.json').read_text())

@contextmanager
def fixture(allcases=False,error=None,bad_schema=False):
 before=(probe.HERE,probe.PRIVATE,probe.PUBLIC,probe.urllib.request.build_opener);oldkey=os.environ.get('DEEPINFRA_API_KEY');calls=[]
 with tempfile.TemporaryDirectory(prefix='hy104-offline-test-',dir=HERE) as name:
  folder=Path(name);priv=folder/'Private';pub=folder/'Public';priv.mkdir();pub.mkdir();(folder/'Source').symlink_to(HERE/'Source',target_is_directory=True)
  data=copy.deepcopy(CASES if allcases else CASES[:2]);plan=copy.deepcopy(PLAN);plan.update(private_cases_semantic_sha256=probe.digest(data),max_total_reserved_usd=sum(c['usd_reserved'] for c in data))
  save(priv/'cloud-cases.json',data);plan['private_cases_sha256']=sha(priv/'cloud-cases.json');save(pub/'cloud-plan.json',plan)
  # Complete evaluator reads only immutable realsource dataset,not fake outcomeinputs.
  (pub/'dataset-manifest.json').write_bytes((PUBLIC/'dataset-manifest.json').read_bytes())
  auth={'approved':True,'plan_sha256':sha(pub/'cloud-plan.json'),'model_ids':MODELS,'max_usd':1,'numeric_features_and_past_labels_to_deepinfra_approved':True}
  save(folder/'authorization.json',auth);probe.HERE,probe.PRIVATE,probe.PUBLIC=folder,priv,pub
  os.environ['DEEPINFRA_API_KEY']='OFFLINE_SYNTHETIC_NOT_A_REAL_KEY'
  class Reply(io.BytesIO):
   def __init__(self,x):super().__init__(json.dumps(x).encode());self.headers={}
  class Opener:
   def open(self,request,timeout=0):
    body=json.loads(request.data);calls.append(body);assert request.full_url==probe.API and b'OFFLINE_SYNTHETIC' not in request.data
    if error is not None:raise urllib.error.HTTPError(probe.API,error,'syntheticfixture',{},io.BytesIO(b'notreal'))
    return Reply({'model':body['model'],'answers':{'positive':{'noul':None if bad_schema else .6,'type':'noul'}},'usage':{'input_tokens':50,'output_tokens':1}})
  probe.urllib.request.build_opener=lambda *args:Opener()
  try:yield folder,priv,pub,calls
  finally:
   probe.HERE,probe.PRIVATE,probe.PUBLIC,probe.urllib.request.build_opener=before
   if oldkey is None:os.environ.pop('DEEPINFRA_API_KEY',None)
   else:os.environ['DEEPINFRA_API_KEY']=oldkey

class Tests(unittest.TestCase):
 def test_true_cohort_and_manifest_parity(self):
  m,rows,x,y,folds=probe.load_dataset();self.assertEqual(len(rows),159);self.assertEqual(x.shape,(159,12));self.assertEqual(sum(f['test_n'] for f in folds),110)
  self.assertEqual({int(r['SI_status_code']) for r in rows},{-1,1})
  for i,r in enumerate(rows):
   self.assertEqual(int(r['y']),int(int(r['stress_net_cents'])>0));self.assertEqual(int(r['normalized_net_cents']),int(r['native_net_cents'])-106)
   self.assertEqual(int(r['stress_net_cents']),int(r['normalized_net_cents'])-2500)
   self.assertLess(int(r['latest_price_source_ns']),int(r['decision_ns']))
 def test_folds_have_whole_day_gap_and_completed_outcomes(self):
  _,rows,_,_,folds=probe.load_dataset();seen=set()
  for f in folds:
   self.assertGreaterEqual(f['train_n'],48);self.assertEqual(len(f['fewshot_indices']),32)
   self.assertTrue(set(f['train_ids']).isdisjoint(f['test_ids']));self.assertTrue(seen.isdisjoint(f['test_ids']));seen.update(f['test_ids'])
   self.assertLess(max(rows[i]['date'] for i in f['train_indices']),f['gap_day']);self.assertLess(f['gap_day'],min(rows[i]['date'] for i in f['test_indices']))
   self.assertLess(max(int(rows[i]['native_exit_time_ns']) for i in f['train_indices']),f['test_first_information_ns'])
 def test_no_fixed_future_horizon_filter(self):
  t=int(datetime(2026,9,8,19,59,tzinfo=timezone.utc).timestamp()*NS);times=t+np.arange(-310,1,dtype=np.int64)*NS
  bid=np.ones(len(times))*7000;ask=bid+.25;size=np.ones(len(times))*2;tape=[times,times.copy(),times.copy(),bid,ask,size.copy(),size.copy(),np.ones(len(times),bool)]
  result=price_context(tape,t,1);self.assertEqual(result['price_status'],'ok')
  before=price_context([v[times<t] for v in tape],t,1);self.assertTrue(all(result[k]==before[k] for k in PRICE))
 def test_SI_delay_contract_and_missing_semantics(self):
  t=10000*NS;row={'decision_ns':t,'symbol':'ESU6','side':-1}
  def event(age,kind='STOP',symbol='ESU6'):return {'ts_init':t-age*NS,'symbol':symbol,'event_type':kind,'reported_direction':1,'event_id':str(age)}
  s=si_context(row,[event(29),event(30),event(900,'ICEBERG'),event(901),event(3600),event(3601),event(40,symbol='ESZ6')])
  self.assertEqual(s['last_STOP_arrow_relative15m'],-1);self.assertEqual(s['last_ICEBERG_arrow_relative15m'],-1);self.assertEqual(s['archived_count60m_cap5'],4)
  q=si_context(row,[event(29),event(3601)]);self.assertIsNone(q['last_STOP_arrow_relative15m']);self.assertIsNone(q['last_ICEBERG_arrow_relative15m']);self.assertIsNone(q['archived_count60m_cap5']);self.assertEqual(q['SI_archive_status'],'U')
 def test_payloads_and_budget(self):
  self.assertEqual(Counter(r['condition'] for r in CASES),{'main':440,'repeat':44});self.assertAlmostEqual(sum(r['usd_reserved'] for r in CASES),.9507696,places=12)
  self.assertTrue(all(len(probe.canonical(r['body']).encode())<=4500 for r in CASES))
  for c in CASES:
   n=8 if c['arm']=='context' else 12;self.assertEqual(len(c['body']['state']['current']),n);self.assertEqual(len(c['body']['state']['past']),32)
   self.assertTrue(all(len(r)==n+1 for r in c['body']['state']['past']))
 def test_same_ids_labels_history_all_four_arms(self):
  groups={}
  for c in CASES:
   if c['condition']=='main':groups.setdefault(c['case_key'],[]).append(c)
  self.assertEqual(len(groups),110)
  for group in groups.values():
   self.assertEqual(len(group),4);self.assertEqual(len({r['y'] for r in group}),1)
   baseline=group[0]['body']['state']['current'][:8]
   self.assertTrue(all(r['body']['state']['current'][:8]==baseline for r in group))
   labels=[r[-1] for r in group[0]['body']['state']['past']]
   self.assertTrue(all([r[-1] for r in q['body']['state']['past']]==labels for q in group))
 def test_repeat_metadata_and_payload_identity(self):
  main={r['case_key']+'|'+r['model']+'|'+r['arm']:r for r in CASES if r['condition']=='main'}
  for model in MODELS:
   for arm in probe.ARMS:
    rr=[r for r in CASES if r['condition']=='repeat' and r['model']==model and r['arm']==arm];self.assertEqual(len(rr),11);self.assertEqual(len({r['fold_id'] for r in rr}),5)
    for r in rr:self.assertEqual(r['body_sha256'],main[r['case_key']+'|'+model+'|'+arm]['body_sha256'])
 def test_redirect_disabled(self):self.assertIsNone(probe.NoRedirect().redirect_request(None,None,302,'',{},'https://outside.invalid'))
 def test_success_fixture_no_secret_in_body_or_output(self):
  with fixture() as (folder,priv,pub,calls),redirect_stdout(io.StringIO()):
   probe.run(SimpleNamespace(authorization=str(folder/'authorization.json')));self.assertEqual(len(calls),2)
   self.assertNotIn('OFFLINE_SYNTHETIC',(priv/'responses.jsonl').read_text())
 def test_HTTP_failures_stop_immediately(self):
  for status in [401,403,404,429]:
   with self.subTest(status=status),fixture(error=status) as (folder,priv,pub,calls),redirect_stdout(io.StringIO()):
    with self.assertRaises(SystemExit):probe.run(SimpleNamespace(authorization=str(folder/'authorization.json')))
    self.assertEqual(len(calls),1);self.assertEqual(json.loads((folder/'progress.json').read_text())['state'],'blocked_after_first_error_no_retry')
 def test_schema_failure_stops_immediately(self):
  with fixture(bad_schema=True) as (folder,priv,pub,calls),redirect_stdout(io.StringIO()):
   with self.assertRaises(SystemExit):probe.run(SimpleNamespace(authorization=str(folder/'authorization.json')))
   self.assertEqual(len(calls),1)
 def test_budget_rejects_before_network(self):
  with fixture() as (folder,priv,pub,calls),redirect_stdout(io.StringIO()):
   auth=json.loads((folder/'authorization.json').read_text());auth['max_usd']=.0001;save(folder/'authorization.json',auth)
   with self.assertRaises(AssertionError):probe.run(SimpleNamespace(authorization=str(folder/'authorization.json')))
   self.assertEqual(calls,[])
 def test_full_evaluator_explicit_synthetic_probabilities_only(self):
  with fixture(allcases=True) as (folder,priv,pub,calls),redirect_stdout(io.StringIO()):
   rr=[]
   for c in CASES:
    q={k:c[k] for k in ['request_key','case_key','condition','model','arm','fold_id','date','y','stress_net_cents','prior60_known','prior15_known','usd_reserved']};q.update(status='ok',probability=.6);rr.append(q)
   (priv/'responses.jsonl').write_text('\n'.join(probe.canonical(x) for x in rr)+'\n');probe.evaluate(SimpleNamespace())
   result=json.loads((pub/'cloud-results.json').read_text());self.assertEqual(result['common_all_four_cases'],110);self.assertTrue(result['full_coverage_all_four'])
   for model in MODELS:self.assertEqual(result['paired_SI_increment'][model]['logloss_improvement_SI'],0);self.assertEqual(result['paired_SI_increment'][model]['brier_improvement_SI'],0)
   for x in result['metrics'].values():self.assertEqual(x['known_prior60_descriptive']['n'],26);self.assertFalse(x['known_prior60_descriptive']['inference_claim'])
   self.assertEqual(calls,[])
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 save(PUBLIC/'cloud-offline-tests.json',{'status':'passed' if result.wasSuccessful() else 'FAILED','tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
  'actual_API_calls':0,'real_model_predictions_generated':False,'real_secret_values_read':False,'runner_sha256':sha(HERE/'Source/cloud_probe.py'),'test_sha256':sha(Path(__file__)),
  'scope':'Actualdataset/foldprovenance plus explicitlysyntheticHTTP/evaluationfixtures,notmodelperformanceresults','completed_at_utc':stamp()})
 raise SystemExit(0 if result.wasSuccessful() else 1)
