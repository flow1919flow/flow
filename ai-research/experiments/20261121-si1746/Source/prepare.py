"""Stage1: verified quotes and strictly past context; no future label access."""
from common import *
from collections import Counter,defaultdict
import pandas as pd
import pyarrow.parquet as pq

def decoded(c):
 a=c.combine_chunks();v=np.frombuffer(a.buffers()[1],dtype='<u8',count=len(a)*2,offset=a.offset*16).reshape(-1,2)
 return (v[:,0].astype(np.float64)+v[:,1].view('<i8').astype(np.float64)*18446744073709551616.)/1e16

class Loader:
 def __init__(self):
  self.days={x['date']:x for x in json.loads(INDEX.read_text())['completed']}
  self.manifest={};self.native=[];self.reports={}
 def tape(self,symbol,start,end):
  market=symbol[:2];tick=MARKETS[market][0];parts=[]
  first=datetime.fromtimestamp(start/NS,timezone.utc).date();last=datetime.fromtimestamp(end/NS,timezone.utc).date()
  for k in range((last-first).days+1):
   day=self.days.get(str(first+timedelta(days=k)))
   if day is None:continue
   base=Path(day['catalog']);pointer=Path(day['completion_pointer'])
   if day['date'] not in self.reports:
    assert sha(pointer)==day['completion_pointer_sha256']
    ptr=json.loads(pointer.read_text());rp=Path(ptr['report']);assert sha(rp)==ptr['sha256']
    report=json.loads(rp.read_text());assert report['source_sha256']==day['source_sha256']
    self.reports[day['date']]=report
   report=self.reports[day['date']]
   for path in sorted((base/'data/quote_tick'/f'{symbol}.GLBX').glob('*.parquet')):
    relative=str(path.relative_to(base));expected=report['parquet_sha256'][relative]
    if str(path) not in self.manifest:
     assert sha(path)==expected, f'Quote hash mismatch: {path}'
     self.manifest[str(path)]={'sha256':expected,'source_sha256':day['source_sha256'],'date':day['date'],'instrument':symbol}
    table=pq.read_table(path,filters=[('ts_init','>=',int(start-10*NS)),('ts_init','<=',int(end+10*NS))])
    if not len(table):continue
    cols=[decoded(table[x]) for x in ('bid_price','ask_price','bid_size','ask_size')]
    for ix in (0,len(table)-1):
     self.native.append({'path':str(path),'row_in_filtered_table':ix,'raw':[table[x][ix].as_py().hex() for x in ('bid_price','ask_price','bid_size','ask_size')],
      'decoded':[float(c[ix]) for c in cols],'price_precision':int(table.schema.metadata[b'price_precision']),'size_precision':int(table.schema.metadata[b'size_precision'])})
    ev=table['ts_event'].to_numpy();init=table['ts_init'].to_numpy();ts=np.maximum(ev,init).astype(np.int64)
    bid,ask,bs,az=cols
    valid=np.isfinite(bid)&np.isfinite(ask)&np.isfinite(bs)&np.isfinite(az)&(bid>0)&(ask>=bid)&(ask<1e8)&(bs>=1)&(az>=1)&(bs<1e12)&(az<1e12)
    for c in (bid,ask):
     assert np.max(np.abs(c[valid]/tick-np.rint(c[valid]/tick)),initial=0)<1e-5
    parts.append((ts,ev.astype(np.int64),init.astype(np.int64),bid,ask,bs,az,valid))
  if not parts:return None
  arrays=[np.concatenate([p[i] for p in parts]) for i in range(8)]
  order=np.argsort(arrays[0],kind='stable');arrays=[x[order] for x in arrays]
  # Duplicate timestamp: deterministic latest source row; never backfill invalid snapshots.
  keep=np.r_[arrays[0][1:]!=arrays[0][:-1],True];return [x[keep] for x in arrays]

def at(tape,points):
 ts=tape[0];ii=np.searchsorted(ts,points,side='left')-1;safe=np.maximum(ii,0)
 fresh=(ii>=0)&tape[7][safe]&((points-ts[safe])<=5*NS)&(points>ts[safe])
 mid=(tape[3][safe]+tape[4][safe])/2
 return safe,fresh,mid

def longest_false(x):
 p=np.flatnonzero(np.r_[True,x,True]);return int(np.max(np.diff(p)-1,initial=0))

def context(tape,t,market):
 td,minute,start,end=clock(t);base={'trading_day':td,'chicago_minute':minute}
 if t-300*NS<start or t+900*NS>end:return dict(base,context_status='session_boundary')
 if tape is None:return dict(base,context_status='exact_contract_quotes_missing')
 points=t+np.arange(-300,1,dtype=np.int64)*NS
 ix,valid,mid=at(tape,points)
 if not valid[-1]:return dict(base,context_status='decision_quote_invalid_or_stale')
 if not valid[0] or not valid[-61]:return dict(base,context_status='past_anchor_invalid_or_stale')
 if np.mean(valid)<.8 or longest_false(valid)>30:return dict(base,context_status='past_path_insufficient')
 delta=np.diff(mid);pair=valid[1:]&valid[:-1];tick=MARKETS[market][0]
 rv=max(float(np.sqrt(np.sum(delta[pair]**2))),tick);j=ix[-1]
 values=dict(market_code=list(MARKETS).index(market),chicago_minute=minute,
  move60_rv=float((mid[-1]-mid[-61])/rv),move300_rv=float((mid[-1]-mid[0])/rv),
  log_rv_ticks=float(np.log1p(rv/tick)),spread_ticks=float((tape[4][j]-tape[3][j])/tick),
  size_imbalance=float((tape[5][j]-tape[6][j])/(tape[5][j]+tape[6][j])),quote_age_s=float((t-tape[0][j])/NS))
 assert max(tape[1][ix].max(),tape[2][ix].max())<t
 return dict(base,**values,context_status='ok',past_rv=rv,decision_mid=float(mid[-1]),
  latest_feature_source_ns=int(tape[0][ix].max()),past_valid_fraction=float(np.mean(valid)))

def main():
 e,a,all_archived=reader().read_archive(include_all=True)
 assert len(e)==1746 and Counter(x['market'] for x in e)=={'ES':229,'NQ':907,'GC':208,'CL':402}
 e.sort(key=lambda x:(x['ts_init'],x['event_id']))
 rows=[];ends={};counts=Counter();heads=set();alltimes=defaultdict(list)
 for x in all_archived:
  if x['market'] in MARKETS:alltimes[x['symbol']].append(int(x['ts_init']))
 for sym in alltimes:alltimes[sym]=np.sort(alltimes[sym])
 for x in e:
  d=int(x['ts_init'])+30*NS;s=x['symbol']
  head=s not in ends or d-300*NS>ends[s]
  if head:counts[s]+=1
  ends[s]=max(ends.get(s,0),d+900*NS)
  key=hashlib.sha256((a['source_sha256']+'|'+x['event_id']).encode()).hexdigest()
  row=dict(event_key=key,kind='event',symbol=s,market=x['market'],known_ns=int(x['ts_init']),decision_ns=d,
   episode_id=f'{s}-{counts[s]:04}',episode_head=head,edited=bool(x['edited_ns']),
   type_code=int(x['event_type']=='STOP'),reported_arrow=int(x['reported_direction']),
   log_reported_size=float(np.log1p(abs(x['signed_size']))),absolute_factor=abs(float(x['factor'])),
   zone_low=float(x['zone_low']),zone_high=float(x['zone_high']))
  row['utc_day']=utc(d)[:10];row['trading_day']=clock(d)[0];rows.append(row)
 frame=pd.DataFrame(rows);loader=Loader();output=[];controls=[];checks=[]
 groups=list(frame.groupby(['symbol','trading_day'],sort=True))
 for gi,((sym,td),g) in enumerate(groups):
  market=g.iloc[0].market;lo=int(g.decision_ns.min());hi=int(g.decision_ns.max())
  tape=loader.tape(sym,lo-310*NS,hi+920*NS)
  for row in g.to_dict('records'):
   c=context(tape,row['decision_ns'],market);row.update(c)
   if c['context_status']=='ok':
    row['zone_width_rv']=(row['zone_high']-row['zone_low'])/c['past_rv']
    row['arrow_zone_distance_rv']=row['reported_arrow']*(c['decision_mid']-(row['zone_high']+row['zone_low'])/2)/c['past_rv']
    if len(checks)<80:
     short=[x[tape[0]<row['decision_ns']] for x in tape]
     cp=context(short,row['decision_ns'],market)
     assert all(c[k]==cp[k] for k in PRICE)
     # Sentinel falsely declares a future source timestamp; same guard must reject it.
     sentinel_rejected=not (row['decision_ns']+1<row['decision_ns'])
     assert sentinel_rejected
     checks.append({'symbol':sym,'decision_ns':row['decision_ns'],'features_equal_after_physical_future_removal':True,'future_timestamp_sentinel_rejected':True})
   output.append(row)
  # No label access here. Archive-bracketed controls; no feed-absence claim.
  times=alltimes[sym]
  for d in range(((lo//(60*NS))+1)*60*NS,hi,60*NS):
   j=np.searchsorted(times,d);near=[]
   if j:near.append(d-times[j-1])
   if j<len(times):near.append(times[j]-d)
   if min(near,default=0)<=1230*NS:continue
   c=context(tape,d,market)
   if c['context_status']!='ok':continue
   controls.append(dict(c,event_key=f'control-{sym}-{d}',kind='control',symbol=sym,market=market,decision_ns=d,episode_head=False,episode_id=None))
  save(HERE/'progress.json',{'stage':'past_context','groups_complete':gi+1,'groups_total':len(groups),'events_checked':len(output),'control_candidates':len(controls)})
  if (gi+1)%20==0:print('context',gi+1,'/',len(groups),'events',len(output),'controls',len(controls),flush=True)
 events=pd.DataFrame(output);ctrl=pd.DataFrame(controls)
 # Preserve optional nanosecond values as nullable integer, never float64.
 for target,records in [(events,output),(ctrl,controls)]:
  for k in ['latest_feature_source_ns','known_ns','decision_ns']:
   if k in target:target[k]=pd.array([r.get(k) for r in records],dtype='Int64')
 match=[];used=set();keys=['move60_rv','move300_rv','log_rv_ticks','spread_ticks','size_imbalance','quote_age_s'];cal=np.array([.5,.5,.5,1.,.5,2.])
 for r in events[events.episode_head].sort_values(['decision_ns','event_key']).to_dict('records'):
  rec={'event_key':r['event_key'],'control_key':None,'status':'invalid_event_context'}
  if r['context_status']=='ok':
   q=ctrl[(ctrl.symbol==r['symbol'])&(ctrl.trading_day==r['trading_day'])&((ctrl.chicago_minute//30)==int(r['chicago_minute']//30))&(~ctrl.event_key.isin(used))].copy() if len(ctrl) else ctrl
   if len(q):
    dist=(q[keys].to_numpy()-np.array([r[k] for k in keys]))/cal;eligible=np.max(np.abs(dist),axis=1)<=1
    q=q.loc[eligible];dist=dist[eligible]
    if len(q):
     q['distance']=(dist**2).sum(axis=1);best=q.sort_values(['distance','decision_ns','event_key']).iloc[0]
     rec.update(control_key=best.event_key,status='matched',distance=float(best.distance));used.add(best.event_key)
    else:rec['status']='no_control_within_fixed_calipers'
   else:rec['status']='no_same_bucket_archive_bracketed_control'
  match.append(rec)
 matches=pd.DataFrame(match)
 events.to_parquet(PRIV/'events-context.parquet',index=False);ctrl.to_parquet(PRIV/'control-candidates.parquet',index=False);matches.to_parquet(PRIV/'matching.parquet',index=False)
 selected=ctrl[ctrl.event_key.isin(used)].copy() if len(ctrl) else ctrl
 selected.to_parquet(PRIV/'selected-controls-context.parquet',index=False)
 save(PRIV/'native-decode-samples.json',loader.native);save(PRIV/'quote-manifest.json',loader.manifest)
 save(PUB/'context-checks.json',{'future_truncation_rows':len(checks),'all_equal':all(x['features_equal_after_physical_future_removal'] for x in checks),'sentinel':'Timestamp-provenance guard only, not proof against all semantic leakage','rows':checks})
 summary={'stage':'context_and_matching_frozen_before_labels','frozen_at_utc':datetime.now(timezone.utc).isoformat(),'events':len(events),'by_market':dict(Counter(events.market)),
  'context_status':dict(Counter(events.context_status)),'episode_heads':int(events.episode_head.sum()),'control_candidates':len(ctrl),'matched_heads':len(used),'matching_status':dict(Counter(matches.status)),
  'edited_events':int(events.edited.sum()),'verified_quote_files':len(loader.manifest),'verified_quote_bytes':sum(Path(p).stat().st_size for p in loader.manifest),
  'index_sha256':sha(INDEX),'archive_sha256':a['source_sha256'],'files':{str(p.relative_to(HERE)):sha(p) for p in [PRIV/'events-context.parquet',PRIV/'control-candidates.parquet',PRIV/'matching.parquet',PRIV/'selected-controls-context.parquet',PRIV/'quote-manifest.json']},
  'source_sha256':{p.name:sha(p) for p in sorted((HERE/'Source').glob('*.py'))},'price_labels_computed':False,'model_fitted':False}
 save(PUB/'context-freeze.json',summary);print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':main()
