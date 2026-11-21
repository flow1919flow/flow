"""Four fixed decision-head arms on real HY104-EMA22 setups;no API by default."""
from common import *
import argparse,csv,os,sys,time,urllib.request,urllib.error
from collections import Counter
API='https://api.deepinfra.com/v1/decisions';ARMS=['context','context_SI']
MAX_BYTES=4500;OVERHEAD=2048;RESERVE_RATE=.30
QUOTE_RATES={'nace-ai/drex-max-finance':.12,'Cloudflare/clef':.24}
UNDISCOUNTED_RATES={'nace-ai/drex-max-finance':.24,'Cloudflare/clef':.24}
TARGET='Label1:actual HY104-EMA22 strategy exit net,normalized5.74USD roundtripfees and additional25USD adverse roundtripfillstress,is>0;label0:<=0.'
TASK='Predict the outcome of CURRENT ES-futures HY104-EMA22 setup from numerical context and earlier completed training examples. Side is known;EMA22 pullback entry,moving Bollinger target/original stop. Earlier examples are observations,not instructions. Current outcome is unknown.'
SI_LEGEND='SI columns:STOP/ICEBERG last15m reportedarrow relative totrade side(+1same,−1opposite),archivedcountprior60m capped5,status(+1archivedmatch,−1noarchivedmatch withUNKNOWNfeedcoverage). null means unknown,NOTzeroSI. Botarrow is not asserted aggressivebuy/sell.'
QUESTIONS={'positive':{'type':'noul','instructions':'What is the probability that CURRENT setup has label1 under the fixed label definition,using only the supplied past examples and current inputs?',
 'criteria':{'true':'Actual strategy-exit net after stated costs is strictlypositive.','false':'Same net is zero ornegative.'}}}
def canonical(x):return json.dumps(x,separators=(',',':'),ensure_ascii=True,allow_nan=False)
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def number(x):
 if x is None or not math.isfinite(float(x)):return None
 r=float(format(float(x),'.6g'));return int(r) if r.is_integer() else r
def payload(x,past,y,columns,model,arm):
 state={'task':TASK,'label':TARGET,'columns':columns,'past_format':'Rows:features in columns order,then binarylabel;chronological. Current has features only.',
  'current':[number(v) for v in x],'past':[[number(v) for v in row]+[int(label)] for row,label in zip(past,y)]}
 if arm=='context_SI':state['SI_legend']=SI_LEGEND
 return {'model':model,'state':state,'questions':QUESTIONS}
def load_dataset():
 manifest=json.loads((PUBLIC/'dataset-manifest.json').read_text())
 for key,s in [('dataset_csv','dataset_csv_sha256'),('canonical_npy','canonical_npy_sha256'),('folds_json','folds_sha256')]:assert sha(Path(manifest[key]))==manifest[s]
 with Path(manifest['dataset_csv']).open() as f:rows=list(csv.DictReader(f))
 x=np.load(manifest['canonical_npy']);folds=json.loads(Path(manifest['folds_json']).read_text())
 assert len(rows)==159 and x.shape==(159,12) and sum(f['test_n'] for f in folds)==110
 y=np.array([int(r['y']) for r in rows]);return manifest,rows,x,y,folds
def repeat_ids(rows,indices,folds,n):
 chosen=[fold['test_indices'][0] for fold in folds];remaining=[i for i in sorted(indices,key=lambda i:int(rows[i]['decision_ns'])) if i not in chosen]
 positions=np.linspace(0,len(remaining)-1,n-len(chosen)).astype(int);chosen.extend(remaining[i] for i in positions)
 assert len(chosen)==n and len(set(chosen))==n;return set(chosen)
def cases():
 manifest,rows,x,y,folds=load_dataset();out=[];testindices=[i for fold in folds for i in fold['test_indices']];repeat_count=math.ceil(len(testindices)*.1);repeats=repeat_ids(rows,testindices,folds,repeat_count)
 for fold in folds:
  training=fold['fewshot_indices'];assert len(training)==32
  assert max(int(rows[i]['native_exit_time_ns']) for i in training)<min(int(rows[i]['decision_ns']) for i in fold['test_indices'])-300*NS
  for i in fold['test_indices']:
   for model in MODELS:
    for arm in ARMS:
     n=8 if arm=='context' else 12;columns=manifest['context_features']+([] if n==8 else manifest['si_features'])
     body=payload(x[i,:n],x[training,:n],y[training],columns,model,arm)
     assert len(canonical(body).encode())<=MAX_BYTES,'Fixed request-byte cap exceeded;do not autochange context'
     out.append({'request_key':digest([rows[i]['case_key'],model,arm,'main']),'case_key':rows[i]['case_key'],'row_index':i,'condition':'main','model':model,'arm':arm,
      'fold_id':fold['fold_id'],'date':rows[i]['date'],'y':int(y[i]),'stress_net_cents':int(rows[i]['stress_net_cents']),
      'prior60_known':rows[i]['has_prior60m_archive_match']=='True','prior15_known':rows[i]['has_prior15m_archive_match']=='True',
      'body':body,'body_sha256':digest(body),'usd_reserved':(MAX_BYTES+OVERHEAD)*RESERVE_RATE/1e6,'input_token_bound':MAX_BYTES+OVERHEAD})
 auxiliary=[dict(r,condition='repeat',request_key=digest([r['case_key'],r['model'],r['arm'],'repeat'])) for r in out if r['row_index'] in repeats]
 return out+auxiliary,manifest,folds,repeat_count
def prepare(args):
 assert not (PRIVATE/'responses.jsonl').exists(),'No overwrite after real calls'
 data,manifest,folds,nrepeat=cases();total=sum(r['usd_reserved'] for r in data);assert total<=1
 save(PRIVATE/'cloud-cases.json',data)
 plan={'state':'prepared_correct_HY104_EMA22_SI_four_cloud_arms_no_calls','created_at_utc':stamp(),'models':MODELS,'arms':ARMS,'endpoint':API,
  'source_strategy':'Actual nativeHY104EMA22,NOT C28.03;native actualstrategyexits,NOTpostSI15minmarks','period':manifest['common_period'],
  'all_context_eligible_setups':159,'later_test_cases_each_arm':110,'folds':5,'initial_train_minimum_cases':48,'whole_CT_gap_days':1,
  'fewshot_rows_per_request':32,'fewshot_selection':'Mostrecent32 eligiblecompletedtrainingcases,fixedwithinblock;identicalIDs/labels acrossfourarms',
  'request_one_current_setup':True,'numeric_rounding':'Fixed6significantdigits,originaldataunchanged','outgoing_data':'Only8pastprice/setupfeatures;SIarmadds3nullablearchivedSIattributesandunknownstatus;pastbinarylabels.No dates/IDs/contracts/absoluteprices/rawquotes/currentfuturelabels',
  'label':TARGET,'input_features_context':manifest['context_features'],'input_features_context_SI':manifest['context_features']+manifest['si_features'],
  'SI_scope':'OwnESRITHMIC229 only,sameexactcontract,knownmaxsentedit<=decision−30s;STOP/ICEBERG15m,count60m.Nulls+explicitunknownstatus,nevertrueabsencezeros',
  'shared_cohort_rule':'EveryEMA22setupafterfirstESarchivepublication+30s;no conditioning onfuture samedaymessages',
  'priors':'Fulltraining andexact32-example training winrates;no test-targetcalibration','primary':'PairedSIincrement permodel:LogLoss(context)−LogLoss(contextSI),Brier same difference.Positive favorsSI.',
  'uncertainty':'1999 moving5businessdateblock bootstrap,seed20261121;97.5percent interval permodel as two-comparisonfamily95percentdiagnostic;conditional selected-dataonly',
  'secondary':'AUC/rank,perblockcoverage,rawproper1e-7clipping plusfixed.01-.99sensitivity;knownprior60SItestsubset26cases descriptiveonly,no formalclaim below30',
  'mechanism':'Exactlymetadata-preselected10percentrepeatIDs perarm,onefirstcaseeach5folds+evenlyspacedremaining;measureduplicateprobabilities,do notaverageorselectwinner',
  'repeats_per_arm':nrepeat,'main_requests':440,'repeat_requests':len(data)-440,'total_requests':len(data),'max_request_bytes':MAX_BYTES,'wrapper_token_bound':OVERHEAD,
  'reservation_input_USD_per_M_each':RESERVE_RATE,'output_cost':0,'max_total_reserved_usd':total,'hard_client_cap_usd':1.,
  'quoted_input_USD_per_M':QUOTE_RATES,'undiscounted_upper_input_USD_per_M':UNDISCOUNTED_RATES,'cost_scope':'Quotes checked21Nov2026;Finance.12promo,Clef.24;estimatesnotactualinvoice;clientreservationnotvendorbillingcap',
  'sources':['https://deepinfra.com/nace-ai/drex-max-finance/api','https://deepinfra.com/Cloudflare/clef/api','https://docs.deepinfra.com/integrations/clef','https://docs.deepinfra.com/account/data-privacy'],
  'calls_made':0,'no_fine_tuning':True,'no_API_by_prepare':True,'no_SQX_or_payout_claim':True,
  'model_scope':'Pretraineddecision-headinference withpast-exampleconditioning,notdocumentedsupervisedweighttraining/calibrationforthistradingtask;userexplicitlyrequestedbothmodels',
  'model_privacy':'Vendorstatesnostorage/trainingofrequestcontent fortheseinferenceAPIs;metadatalogged.Still external numericresearchdata transfer',
  'fail_closed':'Noauthenticatedredirects,noautomaticretry;first401/403/404/429/network/schema/tokenbounderrorstopsallnextcalls.Preserveledger,inflightandcoverage.No fakefallback probabilities.',
  'dataset_manifest_sha256':sha(PUBLIC/'dataset-manifest.json'),'canonical_npy_sha256':manifest['canonical_npy_sha256'],'dataset_csv_sha256':manifest['dataset_csv_sha256'],'folds_sha256':manifest['folds_sha256'],
  'private_cases_sha256':sha(PRIVATE/'cloud-cases.json'),'private_cases_semantic_sha256':digest(data),'runner_sha256':sha(Path(__file__)),
  'source_sha256':{p.name:sha(p) for p in sorted((HERE/'Source').glob('*.py'))}}
 save(PUBLIC/'cloud-plan.json',plan);print(canonical({'state':plan['state'],'main':440,'repeat':len(data)-440,'total':len(data),'reserved_usd':total,'largest_payload_bytes':max(len(canonical(r['body']).encode()) for r in data),'plan_sha256':sha(PUBLIC/'cloud-plan.json')}))
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,request,fp,code,msg,headers,newurl):return None
def ledger(path):return [json.loads(s) for s in path.read_text().splitlines() if s.strip()] if path.exists() else []
def run(args):
 plan=json.loads((PUBLIC/'cloud-plan.json').read_text());auth=json.loads(Path(args.authorization).read_text())
 assert auth.get('approved') is True and auth['plan_sha256']==sha(PUBLIC/'cloud-plan.json') and auth['model_ids']==MODELS
 assert auth.get('numeric_features_and_past_labels_to_deepinfra_approved') is True
 cap=float(auth['max_usd']);assert 0<cap<=1 and plan['max_total_reserved_usd']<=cap
 assert sha(Path(__file__))==plan['runner_sha256'] and sha(PUBLIC/'dataset-manifest.json')==plan['dataset_manifest_sha256']
 for name,value in plan['source_sha256'].items():assert sha(HERE/'Source'/name)==value,'Sourcechangedafterfreeze'
 key=os.environ.get('DEEPINFRA_API_KEY');assert key,'APIkey notprovided;neverputinchat'
 path=PRIVATE/'cloud-cases.json';assert sha(path)==plan['private_cases_sha256'];data=json.loads(path.read_text());assert digest(data)==plan['private_cases_semantic_sha256']
 logfile=PRIVATE/'responses.jsonl';old=ledger(logfile);done={r['request_key'] for r in old};spent=sum(r['usd_reserved'] for r in old)
 assert len(done)==len(old) and all(r['status']=='ok' for r in old),'Previousfailed/duplicateledger requiresinspection,notautoretry'
 assert not (HERE/'inflight.json').exists(),'Unresolvedpriorrequest;do not retry blindly'
 for case in data:
  if case['request_key'] in done:continue
  assert digest(case['body'])==case['body_sha256'] and len(canonical(case['body']).encode())<=MAX_BYTES
  if spent+case['usd_reserved']>cap:
   save(HERE/'progress.json',{'state':'budget_stopped','requests':len(done),'reserved_usd':spent});return
  spent+=case['usd_reserved'];started=time.time();save(HERE/'inflight.json',{'request_key':case['request_key'],'usd_reserved':case['usd_reserved'],'started_at_utc':stamp()})
  out={k:case[k] for k in ['request_key','case_key','condition','model','arm','fold_id','date','y','stress_net_cents','prior60_known','prior15_known','usd_reserved','body_sha256']}
  out.update(status='pending',probability=None,started_at_utc=stamp())
  try:
   request=urllib.request.Request(API,data=canonical(case['body']).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
   with urllib.request.build_opener(NoRedirect()).open(request,timeout=90) as reply:response=json.loads(reply.read());request_id=reply.headers.get('x-request-id')
   answer=response['answers']['positive'];p=answer['noul'];assert isinstance(p,(int,float)) and not isinstance(p,bool) and math.isfinite(p) and 0<=p<=1
   tokens=response['usage']['input_tokens'];assert isinstance(tokens,int) and tokens>=0 and response.get('model') in (None,case['model'])
   out.update(status='ok',probability=float(p),usage_input_tokens=tokens,provider_request_id=request_id,provider_model=response.get('model'),raw_response_sha256=digest(response),
    quoted_price_cost_estimate_usd=tokens*QUOTE_RATES[case['model']]/1e6,undiscounted_upper_cost_estimate_usd=tokens*UNDISCOUNTED_RATES[case['model']]/1e6,actual_invoice_cost_known=False)
   if tokens>case['input_token_bound']:out['status']='token_bound_breached'
  except urllib.error.HTTPError as e:out.update(status='http_error',http_status=e.code,error_body_sha256=hashlib.sha256(e.read()).hexdigest())
  except Exception as e:out.update(status='request_or_schema_error',error_type=type(e).__name__)
  out.update(completed_at_utc=stamp(),elapsed_s=time.time()-started)
  with logfile.open('a') as f:f.write(canonical(out)+'\n')
  os.chmod(logfile,0o600);(HERE/'inflight.json').replace(PRIVATE/'last-completed-request.json');done.add(case['request_key'])
  save(HERE/'progress.json',{'state':'running' if out['status']=='ok' else 'blocked_after_first_error_no_retry','requests':len(done),'total':len(data),'reserved_usd':spent,'last_status':out['status'],'http_status':out.get('http_status')})
  print('request',len(done),'/',len(data),case['model'],case['arm'],case['condition'],out['status'],flush=True)
  if out['status']!='ok':raise SystemExit(2)
 save(HERE/'progress.json',{'state':'requests_complete','requests':len(done),'reserved_usd':spent})

def evaluate(args):
 from sklearn.metrics import log_loss,brier_score_loss,roc_auc_score
 from scipy.stats import spearmanr
 manifest,rows,x,y,folds=load_dataset();responses=ledger(PRIVATE/'responses.jsonl');lookup={r['request_key']:r for r in responses};assert len(lookup)==len(responses)
 main=[r for r in responses if r['condition']=='main'];maprows={(r['case_key'],r['model'],r['arm']):r for r in main};casesdata=json.loads((PRIVATE/'cloud-cases.json').read_text());casebyid={r['case_key']:r for r in casesdata}
 allids={r['case_key'] for r in casesdata};valid={ (model,arm):{r['case_key'] for r in main if r['model']==model and r['arm']==arm and r['status']=='ok'} for model in MODELS for arm in ARMS}
 common=set.intersection(*valid.values());metrics={};byblock=[];differences={};repeat={};priors={};fewpriors={}
 def score(yy,pp):
  raw=np.asarray(pp,float);pp=np.clip(raw,1e-7,1-1e-7);yy=np.asarray(yy,int);clip=np.clip(raw,.01,.99)
  return {'n':len(yy),'log_loss':float(log_loss(yy,pp,labels=[0,1])),'brier':float(brier_score_loss(yy,pp)),
   'auc':float(roc_auc_score(yy,raw)) if len(set(yy))==2 else None,'accuracy_at0_5':float(np.mean((raw>=.5)==yy)),
   'sensitivity_clip01_log_loss':float(log_loss(yy,clip,labels=[0,1])),'sensitivity_clip01_brier':float(brier_score_loss(yy,clip))}
 for f in folds:
  prior=(sum(y[i] for i in f['train_indices'])+1)/(f['train_n']+2);few=(sum(y[i] for i in f['fewshot_indices'])+1)/34
  for i in f['test_indices']:priors[rows[i]['case_key']]=float(prior);fewpriors[rows[i]['case_key']]=float(few)
 for model in MODELS:
  for arm in ARMS:
   ids=sorted(valid[model,arm]);shared=sorted(common);out=[maprows[k,model,arm] for k in ids]
   rec={'successful_main':len(ids),'missing_or_failed_main':110-len(ids),'all_successful_metrics':score([r['y'] for r in out],[r['probability'] for r in out]) if out else None,
    'all_four_common_metrics':score([casebyid[k]['y'] for k in shared],[maprows[k,model,arm]['probability'] for k in shared]) if shared else None}
   known=[k for k in ids if casebyid[k]['prior60_known']];rec['known_prior60_descriptive']={'n':len(known),'metrics':score([casebyid[k]['y'] for k in known],[maprows[k,model,arm]['probability'] for k in known]) if known else None,'inference_claim':False,'reason':'Only26 knownSItestcases;below30,fixeddescriptiveonly'}
   net=[casebyid[k]['stress_net_cents']/100 for k in ids];p=[maprows[k,model,arm]['probability'] for k in ids]
   rec['spearman_probability_actual_stress_net']=float(spearmanr(p,net).statistic) if p and np.ptp(p)>0 else None;metrics[model+'/'+arm]=rec
   for fold in folds:
    ss=[k for k in ids if casebyid[k]['fold_id']==fold['fold_id']]
    byblock.append({'model':model,'arm':arm,'fold_id':fold['fold_id'],'expected':fold['test_n'],'successful':len(ss),'metrics':score([casebyid[k]['y'] for k in ss],[maprows[k,model,arm]['probability'] for k in ss]) if ss else None})
   duplicated=[r for r in responses if r['model']==model and r['arm']==arm and r['condition']=='repeat' and r['status']=='ok' and r['case_key'] in valid[model,arm]]
   dd=[r['probability']-maprows[r['case_key'],model,arm]['probability'] for r in duplicated]
   repeat[model+'/'+arm]={'expected':11,'successful_pairs':len(dd),'max_absolute_probability_difference':max(map(abs,dd),default=None),
    'mean_absolute_probability_difference':float(np.mean(np.abs(dd))) if dd else None,'flips_at0_5':sum((r['probability']>=.5)!=(maprows[r['case_key'],model,arm]['probability']>=.5) for r in duplicated),'main_scores_never_averaged_or_replaced':True}
  ids=sorted(valid[model,'context']&valid[model,'context_SI'])
  if ids:
   yy=np.array([casebyid[k]['y'] for k in ids]);p0=np.clip([maprows[k,model,'context']['probability'] for k in ids],1e-7,1-1e-7);p1=np.clip([maprows[k,model,'context_SI']['probability'] for k in ids],1e-7,1-1e-7)
   dl=-(yy*np.log(p0)+(1-yy)*np.log(1-p0))+(yy*np.log(p1)+(1-yy)*np.log(1-p1));db=(p0-yy)**2-(p1-yy)**2
   days=[casebyid[k]['date'] for k in ids];calendar=[];d=datetime.fromisoformat(min(days)).date();end=datetime.fromisoformat(max(days)).date()
   while d<=end:
    if d.weekday()<5:calendar.append(str(d))
    d+=timedelta(days=1)
   count=np.array([sum(x==day for x in days) for day in calendar]);sums=np.array([[float(v[np.array(days)==day].sum()) for day in calendar] for v in [dl,db]])
   rng=np.random.default_rng(SEED);samples=[]
   for _ in range(1999):
    starts=rng.integers(0,max(1,len(calendar)-4),size=math.ceil(len(calendar)/5));ix=np.concatenate([np.arange(s,min(s+5,len(calendar))) for s in starts])[:len(calendar)]
    if count[ix].sum():samples.append(sums[:,ix].sum(axis=1)/count[ix].sum())
   ci=np.quantile(np.array(samples),[.0125,.9875],axis=0)
   differences[model]={'paired_cases':len(ids),'logloss_improvement_SI':float(dl.mean()),'logloss_ci97_5_low':float(ci[0,0]),'logloss_ci97_5_high':float(ci[1,0]),
    'brier_improvement_SI':float(db.mean()),'brier_ci97_5_low':float(ci[0,1]),'brier_ci97_5_high':float(ci[1,1]),'bootstrap_draws':len(samples),'block_businessdates':5,'seed':SEED,
    'interpretation':'PositivefavorsSI;conditionaldevelopmentdiagnostic,two modelprimarycomparisons;notcausalornewOOSproof'}
 ids=sorted(common);baseline={'full_training_prior':score([casebyid[k]['y'] for k in ids],[priors[k] for k in ids]) if ids else None,'same32_example_prior':score([casebyid[k]['y'] for k in ids],[fewpriors[k] for k in ids]) if ids else None}
 result={'state':'four_arm_decision_diagnostic_evaluated','source':'ActualHY104EMA22only,noC28orpostSI15minlabels','expected_main_per_arm':110,'common_all_four_cases':len(common),'full_coverage_all_four':len(common)==110,
  'responses_expected':484,'responses_recorded':len(responses),'metrics':metrics,'paired_SI_increment':differences,'training_priors_on_all_four_common':baseline,'per_block':byblock,'repeat_diagnostic':repeat,
  'client_reserved_cost_usd':sum(r['usd_reserved'] for r in responses),'quoted_price_cost_estimate_usd':sum(r.get('quoted_price_cost_estimate_usd',0.) for r in responses),
  'undiscounted_upper_cost_estimate_usd':sum(r.get('undiscounted_upper_cost_estimate_usd',0.) for r in responses),'actual_invoice_cost_known':False,
  'fresh_OOS':False,'native_gate_or_account_payout_computed':False,'SI_coverage':'Archivecoverageunknown,missingnullnotnoSIzero;26knownpriorSItestcasesonly',
  'responses_sha256':sha(PRIVATE/'responses.jsonl'),'completed_at_utc':stamp()}
 save(PUBLIC/'cloud-results.json',result);print(json.dumps(result,indent=2))
def main():
 parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','run','evaluate']);parser.add_argument('--authorization');args=parser.parse_args()
 if args.mode=='prepare':prepare(args)
 elif args.mode=='run':assert args.authorization,'Explicitauthorizationfile required';run(args)
 else:evaluate(args)
if __name__=='__main__':main()
