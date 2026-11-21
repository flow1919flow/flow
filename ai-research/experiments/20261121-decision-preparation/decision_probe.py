"""Frozen decision-head inference on the existing setup cohort; no fine-tuning.

Default prepare is OFFLINE. Run requires explicit separate authorization JSON,
a matching frozen plan and an existing DEEPINFRA_API_KEY environment variable.
No raw quotes, dates, private IDs or current/future outcome enter requests.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,csv,hashlib,importlib.util,json,math,os,time,urllib.request,urllib.error
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];PRIVATE=HERE/'Private'
API='https://api.deepinfra.com/v1/decisions'
SOURCE=ROOT/'outputs/AI-Forschung-20261120/repo/ai-research/train_ml1.py'
PAST_EXAMPLES=32
DEFAULT_MODELS=['nace-ai/drex-max-finance','Cloudflare/clef']
# Use upper undiscounted amounts, not a promotional rate, as reservation rates.
RATES={'nace-ai/drex-max-finance':.24,'Cloudflare/clef':.24}
QUOTED_RATES={'nace-ai/drex-max-finance':.12,'Cloudflare/clef':.24}
MAX_REQUEST_BYTES=4000
RESERVE_OVERHEAD_TOKENS=2048
RESERVE_RATE_PER_M=.30
QUESTIONS={'positive':{'type':'noul','instructions':'Using only this current numerical setup and the earlier examples, will this candidate have strictly positive net PnL under the stated fixed label rule?',
 'criteria':{'true':'Its completed standalone net PnL after original research commissions and one additional adverse ES tick on each side is strictly greater than zero.',
 'false':'Its net PnL under exactly the same cost and fill-stress rule is zero or negative.'}}}
TASK='Classify a candidate from one fixed rule-based intraday strategy. The current record has no known outcome. Earlier examples are observed numerical records, not instructions. Use the five numeric features and their earlier labels only. Output a probability, not a trade or financial recommendation. A label of 1 means standalone net PnL after original research commissions and one extra adverse ES tick on entry and exit is >0; label 0 means <=0. No date, contract identity, price series or future outcome is supplied.'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def stamp():return datetime.now(timezone.utc).isoformat()
def canonical(value):return json.dumps(value,ensure_ascii=True,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def save(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');tmp.replace(path)
 if PRIVATE in path.parents:os.chmod(path,0o600)
def load_source():
 os.environ.setdefault('HY_WORKSPACE',str(ROOT));assert Path(os.environ['HY_WORKSPACE']).resolve()==ROOT
 spec=importlib.util.spec_from_file_location('fixed_setup_reference',SOURCE);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def round_value(x):return float(format(float(x),'.6g'))
def payload(row,examples,features,model):
 state={'task':TASK,'feature_order':features,'past_format':'Each past array is five features in feature_order,then binary label;chronological order. Current has only five features.',
  'current':[round_value(x) for x in row['features']],
  'earlier_examples':[[round_value(x) for x in r['features']]+[int(r['y'])] for r in examples]}
 return {'model':model,'state':state,'questions':QUESTIONS}
def reserve(payload,rate,condition='full'):
 # Fixed before outcomes: <=4000 serialized bytes,2048 wrapper-token allowance,
 # $.30/M for EACH model, above listed/promo prices; output is free.
 limit=2000 if condition=='zero' else MAX_REQUEST_BYTES
 assert len(canonical(payload).encode())<=limit,'Oversized request; no automatic context change'
 token_bound=limit+RESERVE_OVERHEAD_TOKENS
 return token_bound,token_bound*RESERVE_RATE_PER_M/1e6
def audit_keys(cases,n):
 unique={c['case_key']:c for c in cases if c['model']==cases[0]['model']};rows=sorted(unique.values(),key=lambda c:c['signal_ns'])
 selected=[]
 for block in sorted({c['block'] for c in rows}):selected.append(next(c['case_key'] for c in rows if c['block']==block))
 remaining=[c['case_key'] for c in rows if c['case_key'] not in selected]
 positions=np.linspace(0,len(remaining)-1,n-len(selected)).astype(int)
 selected.extend(remaining[i] for i in positions);assert len(selected)==n and len(set(selected))==n
 return set(selected)
def build(models):
 m=load_source();dates,rows,sources=m.data();cases=[];folds=[]
 baseline_path=ROOT/'outputs/AI-Forschung-20261121/Training/ML9/predictions.csv'
 with baseline_path.open() as f:expected={int(x['signal_ns']) for x in csv.DictReader(f) if x['score']}
 for block,train,test in m.splits(rows,dates):
  tr=sorted(train,key=lambda i:rows[i]['ns']);examples=[rows[i] for i in tr[-PAST_EXAMPLES:]]
  assert max(r['end_ns'] for r in examples)<min(rows[i]['ns'] for i in test)
  folds.append({'block':block,'train_n':len(train),'fewshot_n':len(examples),'test_n':len(test),
   'train_last_day':max(rows[i]['day'] for i in train),'test_first_day':min(rows[i]['day'] for i in test),'test_last_day':max(rows[i]['day'] for i in test),
   'fewshot_ids_sha256':digest([r['ns'] for r in examples]),'train_ids_sha256':digest([rows[i]['ns'] for i in train])})
  for i in test:
   r=rows[i];key=hashlib.sha256(f'{r["segment"]}|{r["ns"]}'.encode()).hexdigest()
   for model in models:
    body=payload(r,examples,m.FEATURES,model);bound,cost=reserve(body,RATES[model])
    cases.append({'case_key':key,'condition':'full','signal_ns':r['ns'],'end_ns':r['end_ns'],'session':r['day'],'block':block,'model':model,
     'y':int(r['y']),'stress_net_usd':r['stress_net_cents']/100,'body':body,'body_sha256':digest(body),'input_token_reservation':bound,'usd_reserved':cost})
 assert len({x['signal_ns'] for x in cases})==230 and {x['signal_ns'] for x in cases}==expected
 zero=audit_keys(cases,32);repeat=audit_keys(cases,23);extra=[]
 for case in cases:
  if case['case_key'] in repeat:extra.append(dict(case,condition='repeat'))
  if case['case_key'] in zero:
   new=dict(case,condition='zero');body=json.loads(canonical(case['body']));body['state']['earlier_examples']=[]
   bound,cost=reserve(body,RATES[case['model']],condition='zero');new.update(body=body,body_sha256=digest(body),input_token_reservation=bound,usd_reserved=cost);extra.append(new)
 cases.extend(extra);assert len(cases)==570
 return cases,folds,sources,m.FEATURES,sha(baseline_path)
def prepare(args):
 assert not (PRIVATE/'responses.jsonl').exists(),'Do not change design after calls; preserve this experiment'
 models=args.models or DEFAULT_MODELS;assert len(models)==2 and len(set(models))==2 and all(x in RATES for x in models)
 cases,folds,sources,features,baseline_sha=build(models)
 plan={'schema':'DEEPINFRA-DECISION-SETUPS-01','state':'prepared_offline_not_executed','created_at_utc':stamp(),
  'models':models,'endpoint':API,'operation':'pretrained decision-head inference with fixed32 past examples,NOT supervised weight training/fine-tuning',
  'period':['2025-11-24','2026-10-30'],'sessions':242,'period_candidates':347,'later_test_candidates_per_model':230,
  'source_sha256':sha(SOURCE),'runner_sha256':sha(Path(__file__)),'feature_order':features,'fewshot_count':PAST_EXAMPLES,'selection':'last32 eligible training candidates per fixed outer block;identical examples and question for both models;request numbers fixed6 significant digits,original data retained locally',
  'label':'Original standalone native candidate net including research mini commission minus25USD extra adverse roundtrip ES tickstress >0',
  'folds':folds,'source_manifests':sources,'tabpfn_reference_sha256':baseline_sha,'payloads_sha256':digest(cases),
  'input_price_reservation_USD_per_M':{x:RESERVE_RATE_PER_M for x in models},'max_request_bytes':MAX_REQUEST_BYTES,'wrapper_token_allowance':RESERVE_OVERHEAD_TOKENS,'estimated_total_conservative_reservation_usd':sum(x['usd_reserved'] for x in cases),
  'endpoint_output_cost':0,'quoted_input_price_USD_per_M':{x:QUOTED_RATES[x] for x in models},'undiscounted_upper_input_price_USD_per_M':{x:RATES[x] for x in models},
  'pricing_source_urls':['https://deepinfra.com/nace-ai/drex-max-finance/api','https://deepinfra.com/Cloudflare/clef/api','https://docs.deepinfra.com/integrations/clef'],
  'price_scope':'Checked21Nov2026:Clef.24/M,Finance.12/M promotional.Reserve.30/M for each;6048 tokens main/repeat,4048 zero-shot,free output;570 reservations=.995808USD.Not provider-side billing cap.',
  'budget_rule':'Separate explicit authorization JSON required; fail before first call if entire conservative reservation exceeds authorized cap; reserve before every send incl failed calls; no retries; halt if usage exceeds reservation.',
  'current_label_never_sent':True,'no_dates_or_IDs_or_raw_quotes_sent':True,'seed_temperature':'Not supported by decision schema; no invented generation parameters',
  'primary':'AUC/rank discrimination on identical230 outer IDs against TabPFN;raw Brier andLogLoss retained to diagnose calibration.Moving5-session paired block bootstrap1999 draws,seed20261121,97.5percent interval permodel as Bonferroni2-comparison family95percent diagnostic.Development data only,not fresh inference.',
  'reference_diagnostics':'Full-training-only and exact32-example class priors,original Logit,TabPFN on same IDs;perblock Brier/logloss/AUC and coverage;no prompt/parameter/threshold search.Raw proper scores clip1e-7;fixed.01-.99 sensitivity reported separately,never replaces raw.',
  'mechanism_audits':{'zero_shot_cases_per_model':32,'repeat_full_context_cases_per_model':23,'selection':'Metadata only:first case per9 blocks plus evenly spaced remaining chronological cases;never outcomes or model outputs','zero_shot_role':'Separate small mechanism control,not a competing winner-selection arm','repeat_role':'Measure response reproducibility on exact same payloads,not improve or average main scores','total_requests':570},
  'secondary':['Brier','ROC-AUC','accuracy@0.5','per-block coverage','request latency','input_tokens','reserved and reported-price costs'],
  'failure_rule':'Keep every response/error;no invented fallback scores;report full coverage and paired common support. Positive claims require full230 coverage for both arms.',
  'scope':'Repeatedly selected development year,not fresh OOS or evidence of provider payouts. No orders/Sims/leaderboard changes. SQX full rerun needed before any economics claim.',
  'external_data':'Only five numeric setup features and earlier binary outcome labels sent to DeepInfra;still user research data. No credential in outputs.',
  'privacy_source':'https://docs.deepinfra.com/account/data-privacy','retention':'Vendor states input/output not stored/trained and metadata logged;not an independent privacy audit',
  'calls_made':0,'uncertainty':{'draws':1999,'seed':20261121,'block_sessions':5,'primary_comparisons':2,'per_comparison_coverage':.975}}
 save(PRIVATE/'frozen-cases.json',cases);save(HERE/'plan.json',plan)
 save(HERE/'access-presence.json',{'DEEPINFRA_API_KEY_environment_present':bool(os.environ.get('DEEPINFRA_API_KEY')),'secret_values_read_or_logged':False,'checked_at_utc':stamp()})
 print(canonical({'state':plan['state'],'models':models,'cases_each':230,'requests':len(cases),'conservative_reservation_usd':plan['estimated_total_conservative_reservation_usd'],'plan_sha256':sha(HERE/'plan.json')}))
def read_jsonl(path):return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,request,fp,code,msg,headers,newurl):return None
def run(args):
 plan=json.loads((HERE/'plan.json').read_text());authorization=json.loads(Path(args.authorization).read_text())
 assert authorization.get('approved') is True and authorization['plan_sha256']==sha(HERE/'plan.json')
 assert authorization['model_ids']==plan['models'] and authorization.get('numeric_features_and_past_labels_to_deepinfra_approved') is True
 cap=float(authorization['max_usd']);assert 0<cap<=1.,'Experiment runner hard limit is1USD total'
 assert sha(Path(__file__))==plan['runner_sha256'] and sha(SOURCE)==plan['source_sha256']
 assert plan['estimated_total_conservative_reservation_usd']<=cap
 key=os.environ.get('DEEPINFRA_API_KEY');assert key,'DEEPINFRA_API_KEY missing; never paste into chat'
 cases=json.loads((PRIVATE/'frozen-cases.json').read_text());assert digest(cases)==plan['payloads_sha256']
 responsepath=PRIVATE/'responses.jsonl';old=read_jsonl(responsepath);completed={(r['case_key'],r['model'],r['condition']) for r in old};spent=sum(r['usd_reserved'] for r in old)
 assert len(completed)==len(old),'Duplicate request IDs found; inspect instead of rerunning'
 assert all(r['status']=='ok' for r in old),'Prior failed ledger is blocked; inspect instead of continuing automatically'
 for case in cases:
  identity=(case['case_key'],case['model'],case['condition'])
  if identity in completed:continue
  assert digest(case['body'])==case['body_sha256']
  if spent+case['usd_reserved']>cap:
   save(HERE/'progress.json',{'state':'budget_stopped','reserved_usd':spent,'completed':len(completed)});return
  spent+=case['usd_reserved'];start=time.time()
  # Reservation is persisted BEFORE sending; ambiguous crashes are not retried.
  inflight=HERE/'inflight.json';assert not inflight.exists(),'Unresolved prior request: inspect before retrying'
  save(inflight,{'case_key':case['case_key'],'model':case['model'],'condition':case['condition'],'usd_reserved':case['usd_reserved'],'started_at_utc':stamp()})
  result={k:case[k] for k in ['case_key','condition','signal_ns','session','block','model','y','stress_net_usd','usd_reserved','body_sha256']}
  result.update(status='pending',probability=None,usage_input_tokens=None,started_at_utc=stamp())
  try:
   request=urllib.request.Request(API,data=canonical(case['body']).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
   with urllib.request.build_opener(NoRedirect()).open(request,timeout=90) as reply:
    response=json.loads(reply.read().decode());result['provider_request_id']=reply.headers.get('x-request-id')
   answer=response['answers']['positive'];p=answer['noul'];assert isinstance(p,(int,float)) and not isinstance(p,bool) and math.isfinite(p) and 0<=p<=1
   usage=response['usage'];tokens=usage['input_tokens'];assert isinstance(tokens,int) and tokens>=0
   assert response.get('model') in (None,case['model'])
   result.update(status='ok',probability=float(p),usage_input_tokens=tokens,provider_response_model=response.get('model'),
    quoted_price_cost_estimate_usd=tokens*QUOTED_RATES[case['model']]/1e6,undiscounted_price_cost_upper_estimate_usd=tokens*RATES[case['model']]/1e6,
    actual_provider_invoice_cost_known=False,answer_type=answer.get('type'),raw_response_sha256=digest(response))
   if tokens>case['input_token_reservation']:result['status']='token_bound_breached_stop'
  except urllib.error.HTTPError as exc:
   error=exc.read();result.update(status='http_error',http_status=exc.code,error_body_sha256=hashlib.sha256(error).hexdigest())
  except Exception as exc:result.update(status='request_or_schema_error',error_type=type(exc).__name__)
  result.update(elapsed_s=time.time()-start,completed_at_utc=stamp())
  with responsepath.open('a') as f:f.write(canonical(result)+'\n')
  os.chmod(responsepath,0o600);inflight.rename(PRIVATE/'last-completed-request.json');completed.add(identity)
  save(HERE/'progress.json',{'state':'running','requests_recorded':len(completed),'requests_total':len(cases),'reserved_usd':spent,'last_status':result['status']})
  print('request',len(completed),'/',len(cases),case['model'],result['status'],flush=True)
  if result['status']!='ok':
   save(HERE/'progress.json',{'state':'blocked_after_first_error_no_retry','requests_recorded':len(completed),'requests_total':len(cases),'reserved_usd':spent,
    'last_status':result['status'],'http_status':result.get('http_status'),'automatic_retry':False})
   raise SystemExit(2)
 save(HERE/'progress.json',{'state':'requests_complete','requests_recorded':len(completed),'reserved_usd':spent})
def evaluate(args):
 from sklearn.metrics import log_loss,brier_score_loss,roc_auc_score
 from scipy.stats import spearmanr
 plan=json.loads((HERE/'plan.json').read_text());responses=read_jsonl(PRIVATE/'responses.jsonl');cases=json.loads((PRIVATE/'frozen-cases.json').read_text())
 lookup={(r['case_key'],r['model'],r['condition']):r for r in responses};assert len(lookup)==len(responses)
 validsets={model:{r['case_key'] for r in responses if r['model']==model and r['condition']=='full' and r['status']=='ok'} for model in plan['models']}
 common=set.intersection(*validsets.values());metrics={};target={r['case_key']:r['y'] for r in cases}
 def score(y,p):
  raw=np.asarray(p,float);p=np.clip(raw,1e-7,1-1e-7);y=np.asarray(y,int);sensitivity=np.clip(raw,.01,.99)
  return {'n':len(y),'log_loss':float(log_loss(y,p,labels=[0,1])),'brier':float(brier_score_loss(y,p)),
   'auc':float(roc_auc_score(y,raw)) if len(set(y))==2 else None,'accuracy_at_0_5':float(np.mean((p>=.5)==y)),
   'sensitivity_clip01_log_loss':float(log_loss(y,sensitivity,labels=[0,1])),'sensitivity_clip01_brier':float(brier_score_loss(y,sensitivity))}
 for model in plan['models']:
  keys=sorted(validsets[model]);metrics[model]={'successful_predictions':len(keys),'failed_or_missing':230-len(keys),
   'all_successful':score([target[k] for k in keys],[lookup[k,model,'full']['probability'] for k in keys]) if keys else None,
   'common_support':score([target[k] for k in sorted(common)],[lookup[k,model,'full']['probability'] for k in sorted(common)]) if common else None}
 m=load_source();dates,rows,_,=m.data();idmap={r['ns']:hashlib.sha256(f'{r["segment"]}|{r["ns"]}'.encode()).hexdigest() for r in rows};baselines={};reference_scores={}
 for name,path in [('original_logit',ROOT/'outputs/AI-Forschung-20261120/Training/predictions.csv'),('TabPFN_v2',ROOT/'outputs/AI-Forschung-20261121/Training/ML9/predictions.csv')]:
  with path.open() as f:rr={idmap[int(r['signal_ns'])]:float(r['score']) for r in csv.DictReader(f) if r['score']}
  assert set(rr)==set(target);keys=sorted(common)
  reference_scores[name]=rr
  baselines[name]=score([target[k] for k in keys],[rr[k] for k in keys]) if keys else None
 priors={};fewshot_priors={}
 for _,train,test in m.splits(rows,dates):
  prior=(sum(rows[i]['y'] for i in train)+1)/(len(train)+2)
  few=sorted(train,key=lambda i:rows[i]['ns'])[-PAST_EXAMPLES:];fewprior=(sum(rows[i]['y'] for i in few)+1)/(len(few)+2)
  for i in test:priors[idmap[rows[i]['ns']]]=prior;fewshot_priors[idmap[rows[i]['ns']]]=fewprior
 baselines['training_only_prior']=score([target[k] for k in sorted(common)],[priors[k] for k in sorted(common)]) if common else None
 baselines['exact32_example_prior']=score([target[k] for k in sorted(common)],[fewshot_priors[k] for k in sorted(common)]) if common else None
 reference_scores['training_only_prior']=priors
 by_block=[];case_lookup={r['case_key']:r for r in cases if r['condition']=='full'};uncertainty={};diagnostics={}
 for model in plan['models']:
  for fold in plan['folds']:
   keys=sorted(k for k in common if case_lookup[k]['block']==fold['block'])
   by_block.append({'model':model,'block':fold['block'],'n':len(keys),'expected':fold['test_n'],'metrics':score([target[k] for k in keys],[lookup[k,model,'full']['probability'] for k in keys]) if keys else None})
  if common:
   keys=sorted(common);y=np.array([target[k] for k in keys]);pred=np.clip([lookup[k,model,'full']['probability'] for k in keys],1e-7,1-1e-7)
   base=np.clip([reference_scores['TabPFN_v2'][k] for k in keys],1e-7,1-1e-7)
   loss=-(y*np.log(pred)+(1-y)*np.log(1-pred));baseloss=-(y*np.log(base)+(1-y)*np.log(1-base));delta=baseloss-loss
   dd=[case_lookup[k]['session'] for k in keys];calendar=[d for d in dates if min(dd)<=d<=max(dd)]
   sums=np.array([sum(delta[i] for i,d in enumerate(dd) if d==day) for day in calendar]);counts=np.array([sum(d==day for d in dd) for day in calendar]);rng=np.random.default_rng(20261121);draws=[];auc_draws=[]
   for _ in range(1999):
    starts=rng.integers(0,max(1,len(calendar)-4),size=math.ceil(len(calendar)/5));ix=np.concatenate([np.arange(s,min(s+5,len(calendar))) for s in starts])[:len(calendar)]
    if counts[ix].sum():draws.append(float(sums[ix].sum()/counts[ix].sum()))
    selected=np.concatenate([np.flatnonzero(np.array(dd)==calendar[j]) for j in ix])
    if len(selected) and len(np.unique(y[selected]))==2:auc_draws.append(float(roc_auc_score(y[selected],pred[selected])-roc_auc_score(y[selected],base[selected])))
   lower,upper=np.quantile(draws,[.0125,.9875])
   auc_lo,auc_hi=np.quantile(auc_draws,[.0125,.9875]) if auc_draws else (None,None)
   net=np.array([case_lookup[k]['stress_net_usd'] for k in keys]);rho=float(spearmanr(pred,net).statistic) if np.ptp(pred)>0 else None
   uncertainty[model]={'paired_mean_logloss_improvement_vs_TabPFN':float(delta.mean()),'ci97_5_low':float(lower),'ci97_5_high':float(upper),'draws':len(draws),'block_sessions':5,'test_days_with_cases':len(set(dd)),
    'paired_auc_improvement_vs_TabPFN':float(roc_auc_score(y,pred)-roc_auc_score(y,base)) if len(set(y))==2 else None,'auc_ci97_5_low':float(auc_lo) if auc_lo is not None else None,'auc_ci97_5_high':float(auc_hi) if auc_hi is not None else None,'valid_auc_bootstrap_draws':len(auc_draws),
    'spearman_probability_stress_net':rho,'positive_means':'Decision model lower loss/higherAUC than existingTabPFN;conditional selected-year diagnostic,not untouched validation','two_comparison_family_coverage':.95}
  repeats=[r for r in responses if r['model']==model and r['condition']=='repeat' and r['status']=='ok' and (r['case_key'],model,'full') in lookup and lookup[r['case_key'],model,'full']['status']=='ok']
  changes=[r['probability']-lookup[r['case_key'],model,'full']['probability'] for r in repeats]
  zero=[r for r in responses if r['model']==model and r['condition']=='zero' and r['status']=='ok'];zk=[r['case_key'] for r in zero];zp=[r['probability'] for r in zero]
  diagnostics[model]={'repeat_expected':23,'repeat_valid_pairs':len(changes),'repeat_max_abs_probability_change':max(map(abs,changes),default=None),
   'repeat_mean_abs_probability_change':float(np.mean(np.abs(changes))) if changes else None,'repeat_classification_flips_at_0_5':sum((r['probability']>=.5)!=(lookup[r['case_key'],model,'full']['probability']>=.5) for r in repeats),
   'zero_shot_expected':32,'zero_shot_successes':len(zero),'zero_shot_metrics':score([target[k] for k in zk],zp) if zk else None,
   'zero_shot_full_train_prior_same_cases':score([target[k] for k in zk],[priors[k] for k in zk]) if zk else None,
   'scope':'Small fixed mechanism/reproducibility diagnostics only;no competing winner-selection arm,averaging or prompt search'}
 result={'state':'evaluation_complete','requests_expected':570,'requests_recorded':len(responses),'common_later_cases':len(common),'full_coverage_both':len(common)==230,
  'metrics':metrics,'reference_common_support':baselines,'reserved_cost_usd':sum(r['usd_reserved'] for r in responses),
  'quoted_price_cost_estimate_usd':sum(r.get('quoted_price_cost_estimate_usd',0.) for r in responses),
  'undiscounted_price_cost_upper_estimate_usd':sum(r.get('undiscounted_price_cost_upper_estimate_usd',0.) for r in responses),
  'actual_invoice_cost_known':False,'responses_sha256':sha(PRIVATE/'responses.jsonl'),
  'by_block':by_block,'paired_uncertainty_vs_TabPFN':uncertainty,'mechanism_diagnostics':diagnostics,'financial_or_unchanged_strategy_profit_claim':False,'no_fine_tuning':True,'fresh_OOS':False,'completed_at_utc':stamp()}
 save(HERE/'results.json',result);print(json.dumps(result,indent=2))
def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','run','evaluate']);p.add_argument('--models',nargs=2);p.add_argument('--authorization');a=p.parse_args()
 if a.mode=='prepare':prepare(a)
 elif a.mode=='run':
  assert a.authorization,'Explicit authorization JSON path is required';run(a)
 else:evaluate(a)
if __name__=='__main__':main()
