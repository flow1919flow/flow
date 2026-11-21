"""Correct EMA22 executed setups; features freeze precedes strategy-label access."""
from common import *
from collections import Counter
import csv,sys
from decimal import Decimal
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import pandas as pd
from quote_loader import Loader

def metadata():
 es,archive=si_reader().read_archive();es=[r for r in es if r['market']=='ES'];assert len(es)==229
 start=min(int(r['ts_init']) for r in es)+30*NS
 result=[];sources=[]
 for verified in sorted(NATIVE.glob('*/verified.json')):
  v=json.loads(verified.read_text())['1'];path=Path(v['fills']);assert sha(path)==v['sha256']
  prepared=json.loads((verified.parent/'prepared.json').read_text());assert prepared['entry_average_case']==5 and prepared['entry_average_label']=='EMA22'
  assert prepared['phase']=='evaluation'
  for report in v['reports']:
   with ZipFile(report) as z:tree=ET.fromstring(z.read('strategy_Portfolio.xml'))
   variables={n.findtext('id'):Decimal(n.findtext('value')) for n in tree.findall('Strategy/Variables/variable')}
   assert variables['EntryAverageCase']==5 and variables['TargetOffsetTicks']==Decimal('.75')
  count=0
  # Do not inspect net/exit values in this stage; only identity and entry metadata.
  with path.open() as f:
   rows=csv.reader(f);header=next(rows);cols={k:header.index(k) for k in ['side','entry_decision_ns']}
   for source_row,fields in enumerate(rows):
    count+=1;t=int(fields[cols['entry_decision_ns']]);day=local_date(t)
    if t<start or day>'2026-10-30':continue
    symbol=verified.parent.name.split('-')[-1];side=1 if fields[cols['side']]=='LONG' else -1
    result.append({'case_key':hashlib.sha256(f'EMA22|{verified.parent.name}|{t}'.encode()).hexdigest(),'segment':verified.parent.name,'symbol':symbol,'decision_ns':t,
     'date':day,'side':side,'source_file':str(path),'source_row':source_row})
  assert count==v['trades']
  sources.append({'segment':verified.parent.name,'verified':str(verified.relative_to(ROOT)),'verified_sha256':sha(verified),'native_trade_file':str(path.relative_to(ROOT)),
   'native_trade_sha256':sha(path),'native_rows':count,'entry_case':5,'entry_average':'EMA22','target_offset_ticks':.75,'phase':'evaluation','source_not_C28_03':True})
 assert len(result)==159 and len({r['case_key'] for r in result})==159
 result.sort(key=lambda r:r['decision_ns']);return result,es,archive,sources,start

def si_context(row,events):
 t=int(row['decision_ns']);prior=[e for e in events if e['symbol']==row['symbol'] and t-3600*NS<=int(e['ts_init'])<=t-30*NS]
 near=[e for e in prior if int(e['ts_init'])>=t-900*NS];last={}
 for kind in ['STOP','ICEBERG']:
  a=sorted((e for e in near if e['event_type']==kind),key=lambda e:(e['ts_init'],e['event_id']))
  last[kind]=int(a[-1]['reported_direction'])*int(row['side']) if a else None
 return {'last_STOP_arrow_relative15m':last['STOP'],'last_ICEBERG_arrow_relative15m':last['ICEBERG'],
  'archived_count60m_cap5':min(5,len(prior)) if prior else None,
  'SI_archive_status':'A' if prior else 'U','has_prior60m_archive_match':bool(prior),'has_prior15m_archive_match':bool(near),
  'latest_SI_known_ns':max((int(e['ts_init']) for e in prior),default=None)}

def asof(tape,points):
 j=np.searchsorted(tape[0],points,side='left')-1;safe=np.maximum(j,0)
 valid=(j>=0)&tape[7][safe]&((points-tape[0][safe])<=5*NS)&(points>tape[0][safe])
 return safe,valid,(tape[3][safe]+tape[4][safe])/2
def longest_missing(x):
 a=np.flatnonzero(np.r_[True,x,True]);return int(np.max(np.diff(a)-1,initial=0))
def price_context(tape,t,side):
 # Past only: deliberately no future15min horizon/session-end condition.
 if tape is None:return {'price_status':'exact_contract_quotes_missing'}
 points=t+np.arange(-300,1,dtype=np.int64)*NS;j,valid,mid=asof(tape,points)
 if not valid[-1]:return {'price_status':'decision_quote_invalid_or_stale'}
 if not valid[0] or not valid[-61]:return {'price_status':'past_anchor_invalid_or_stale'}
 if np.mean(valid)<.8 or longest_missing(valid)>30:return {'price_status':'past_path_insufficient'}
 pair=valid[1:]&valid[:-1];rv=max(float(np.sqrt(np.sum(np.diff(mid)[pair]**2))),.25);i=j[-1]
 dt=datetime.fromtimestamp(t/NS,timezone.utc).astimezone(CT);minute=(dt.hour*60+dt.minute+dt.second/60+dt.microsecond/60e6)-510
 latest=int(tape[0][j].max());assert latest<t and int(tape[1][j].max())<t and int(tape[2][j].max())<t
 return {'price_status':'ok','side':int(side),'chicago_RTH_minute':minute,'signed_move60_rv300':side*float(mid[-1]-mid[-61])/rv,
  'signed_move300_rv300':side*float(mid[-1]-mid[0])/rv,'log1p_rv300_ticks':float(np.log1p(rv/.25)),
  'spread_ticks':float((tape[4][i]-tape[3][i])/.25),'signed_topsize_imbalance':side*float((tape[5][i]-tape[6][i])/(tape[5][i]+tape[6][i])),
  'quote_age_seconds':float((t-tape[0][i])/NS),'latest_price_source_ns':latest,'past_valid_fraction':float(np.mean(valid))}

def features():
 assert not (PRIVATE/'labeled.json').exists(),'Preserve label study;do not overwrite feature freeze after labels'
 rows,es,archive,sources,start=metadata();loader=Loader();output=[];proof=[]
 for (symbol,day),g in pd.DataFrame(rows).groupby(['symbol','date'],sort=True):
  # Read payload through last decision only;future-removal oracle still tested below.
  tape=loader.tape(symbol,int(g.decision_ns.min())-310*NS,int(g.decision_ns.max())+1)
  for row in g.to_dict('records'):
   t=int(row['decision_ns']);p=price_context(tape,t,int(row['side']));s=si_context(row,es);row.update(p);row.update(s)
   if p['price_status']=='ok':
    truncated=[a[tape[0]<t] for a in tape];past=price_context(truncated,t,int(row['side']))
    assert all(p[k]==past[k] for k in PRICE)
    # SI entries at/afterdecision−30s excluded;future messages cannot affect context.
    si_past=si_context(row,[e for e in es if int(e['ts_init'])<=t-30*NS]);assert s==si_past
    proof.append({'price_future_truncation_equal':True,'SI_future_truncation_equal':True})
   output.append(row)
 output.sort(key=lambda r:r['decision_ns']);save(PRIVATE/'features.json',output);save(PRIVATE/'quote-manifest.json',loader.manifest);save(PRIVATE/'native-decode-samples.json',loader.native)
 valid=[r for r in output if r['price_status']=='ok']
 cfg={'state':'correct_HY104_EMA22_features_frozen_before_labels','frozen_at_utc':stamp(),'metadata_cohort':159,'price_eligible':len(valid),
  'price_status':dict(Counter(r['price_status'] for r in output)),'period':[output[0]['date'],output[-1]['date']],
  'cutoff_rule':'Firstknown ESarchive availability+30s,then every subsequent nativeEMA22trade through30Oct2026;NOT observed-message-day selection',
  'archive_cutoff_utc':utc(start),'ES_archived_messages':229,'other_market_SI_rows_used':0,
  'all159_prior15m':sum(r['has_prior15m_archive_match'] for r in output),'all159_prior60m':sum(r['has_prior60m_archive_match'] for r in output),
  'eligible_prior15m':sum(r['has_prior15m_archive_match'] for r in valid),'eligible_prior60m':sum(r['has_prior60m_archive_match'] for r in valid),
  'PRICE':PRICE,'SI':SI,'SI_status_legend':{'A':'Actual archived same-contract message in prior60m;fullfeedcoverage still unknown','U':'No matching archived message;coverage unknown,not actualnoSI'},
  'missing_SI_numeric_values':'null,notzero','features_sha256':sha(PRIVATE/'features.json'),'private_quote_manifest_sha256':sha(PRIVATE/'quote-manifest.json'),
  'quote_files_verified':len(loader.manifest),'native_source_manifests':sources,'archive_sha256':archive['source_sha256'],
  'bounded_prefix_checks':len(proof),'all_prefix_checks_passed':all(all(x.values()) for x in proof),'labels_accessed_by_feature_builder':False,
  'source_sha256':{f.name:sha(f) for f in sorted((HERE/'Source').glob('*.py'))},'claim':'Source rows are actually executed nativeEMA22 trades,not all counterfactual signals. Generic causal TBBOpricecontext,not copiedC28MLindicators. No fixed15min outcome oraccount payout.'}
 save(PUBLIC/'feature-freeze.json',cfg);print(json.dumps({k:v for k,v in cfg.items() if k not in ('native_source_manifests','source_sha256')},indent=2))

def labels():
 freeze=json.loads((PUBLIC/'feature-freeze.json').read_text());assert freeze['features_sha256']==sha(PRIVATE/'features.json')
 rows=json.loads((PRIVATE/'features.json').read_text());cache={};output=[]
 for row in rows:
  p=Path(row['source_file'])
  if p not in cache:
   with p.open() as f:cache[p]=list(csv.DictReader(f))
  r=cache[p][row['source_row']];assert int(r['entry_decision_ns'])==row['decision_ns']
  side=int(row['side']);gross=side*(int(r['exit_price_cents'])-int(r['entry_price_cents']))*50
  assert int(r['net_pnl_cents'])==gross-468
  normalized=int(r['net_pnl_cents'])-106;stress=normalized-2500
  output.append(dict(row,native_exit_time_ns=int(r['exit_time_ns']),native_net_cents=int(r['net_pnl_cents']),normalized_net_cents=normalized,
   stress_net_cents=stress,y=int(stress>0),native_exit_reason=r['exit_reason']))
 save(PRIVATE/'labeled.json',output)
 valid=[r for r in output if r['price_status']=='ok'];summary={'state':'actual_native_EMA22_cost_adjusted_labels_built','all159_retained':len(output)==159,'eligible':len(valid),
  'stress_label_counts':dict(Counter(str(r['y']) for r in valid)),'label':'Actual strategy exit net;native4.68fee normalized to5.74(subtract1.06),then additional25USD stress;positive iff>0',
  'no_fixed15min_markout_label':True,'future_input_outcome_columns':False,'feature_freeze_sha256':sha(PUBLIC/'feature-freeze.json'),'labeled_sha256':sha(PRIVATE/'labeled.json'),
  'completed_at_utc':stamp()}
 save(PUBLIC/'label-proof.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':
 if sys.argv[1]=='features':features()
 elif sys.argv[1]=='labels':labels()
 else:raise ValueError('features orlabels')
