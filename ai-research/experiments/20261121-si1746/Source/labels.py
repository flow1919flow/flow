"""Stage2: only after context/matching are frozen, fixed bid/ask outcomes."""
from common import *
from prepare import Loader,at,longest_false
from collections import Counter
import pandas as pd

def label(tape,row,horizon):
 t=int(row['decision_ns']);m=row['market'];tick,point,fee=MARKETS[m]
 if row['context_status']!='ok':return {'label_status':row['context_status']}
 if tape is None:return {'label_status':'quotes_missing'}
 start=np.searchsorted(tape[0],t,side='left')
 # Invalid snapshots at execution time are not skipped to manufacture a fill.
 if start>=len(tape[0]) or tape[0][start]-t>5*NS or not tape[7][start]:return {'label_status':'entry_quote_invalid_or_late'}
 entry=int(tape[0][start]);target=entry+horizon*NS;end=np.searchsorted(tape[0],target,side='left')
 if end>=len(tape[0]) or tape[0][end]-target>5*NS or not tape[7][end]:return {'label_status':'exit_quote_invalid_or_late'}
 if tape[0][end]>clock(t)[3]:return {'label_status':'exit_after_session_end'}
 grid=entry+np.arange(1,horizon+1,dtype=np.int64)*NS
 _,v,_=at(tape,grid)
 if np.mean(v)<.8 or longest_false(v)>30:return {'label_status':'future_path_insufficient'}
 long=float((tape[3][end]-tape[4][start])*point-2*fee);short=float((tape[3][start]-tape[4][end])*point-2*fee)
 assert not (long>0 and short>0)
 return dict(label_status='ok',y=1 if long>0 else 2 if short>0 else 0,long_net=long,short_net=short,
  long_stress_net=long-2*tick*point,short_stress_net=short-2*tick*point,entry_quote_ns=entry,exit_quote_ns=int(tape[0][end]),
  entry_bid=float(tape[3][start]),entry_ask=float(tape[4][start]),exit_bid=float(tape[3][end]),exit_ask=float(tape[4][end]),future_valid_fraction=float(np.mean(v)))

def main():
 freeze=json.loads((PUB/'context-freeze.json').read_text())
 for p,s in freeze['files'].items():assert sha(HERE/p)==s
 assert json.loads((PUB/'native-decode-proof.json').read_text())['status']=='passed'
 events=pd.read_parquet(PRIV/'events-context.parquet');controls=pd.read_parquet(PRIV/'selected-controls-context.parquet');both=pd.concat([events,controls],ignore_index=True)
 loader=Loader();output=[];groups=list(both.groupby(['symbol','trading_day'],sort=True))
 for gi,((sym,td),g) in enumerate(groups):
  tape=loader.tape(sym,int(g.decision_ns.min())-310*NS,int(g.decision_ns.max())+930*NS)
  for row in g.to_dict('records'):
   row.update(label(tape,row,900));row.update({'h5_'+k:v for k,v in label(tape,row,300).items()});output.append(row)
  if (gi+1)%30==0:print('labels',gi+1,'/',len(groups),flush=True)
 frame=pd.DataFrame(output);assert len(frame[frame.kind=='event'])==1746
 for k in ['decision_ns','known_ns','latest_feature_source_ns','entry_quote_ns','exit_quote_ns','h5_entry_quote_ns','h5_exit_quote_ns']:
  if k in frame:frame[k]=pd.array([r.get(k) if pd.notna(r.get(k)) else None for r in output],dtype='Int64')
 frame.to_parquet(PRIV/'labeled.parquet',index=False)
 frame.to_csv(PRIV/'labeled.csv',index=False)
 restored=pd.read_csv(PRIV/'labeled.csv',float_precision='round_trip')
 for k in PRICE+SI:
  assert np.array_equal(frame[k].to_numpy(dtype=float),restored[k].to_numpy(dtype=float),equal_nan=True)
 ev=frame[frame.kind=='event'];head=ev[ev.episode_head&ev.label_status.eq('ok')]
 counts=[]
 for m,g in ev.groupby('market'):
  counts.append({'market':m,'all_events':len(g),'past_context_ok':int(g.context_status.eq('ok').sum()),'labels_ok':int(g.label_status.eq('ok').sum()),'episode_heads':int(g.episode_head.sum()),'eligible_heads':int((g.episode_head&g.label_status.eq('ok')).sum()),'status':dict(Counter(g.label_status))})
 match=pd.read_parquet(PRIV/'matching.parquet');paired=[]
 for r in match[match.status.eq('matched')].to_dict('records'):
  e=frame[frame.event_key.eq(r['event_key'])].iloc[0];c=frame[frame.event_key.eq(r['control_key'])].iloc[0]
  ok=e.label_status=='ok' and c.label_status=='ok'
  paired.append({'market':e.market,'both_labels_ok':ok,'event_y':int(e.y) if e.label_status=='ok' else None,'control_y':int(c.y) if c.label_status=='ok' else None,
   'event_arrow_net':float(e.long_net if e.reported_arrow>0 else e.short_net) if ok else None,
   'control_same_arrow_net':float(c.long_net if e.reported_arrow>0 else c.short_net) if ok else None})
 pd.DataFrame(paired).to_parquet(PRIV/'comparison-markouts.parquet',index=False)
 stats={'state':'labels_complete_for_all1746_audited_events','by_market':counts,'all_label_status':dict(Counter(ev.label_status)),
  'total_labels_ok':int(ev.label_status.eq('ok').sum()),'eligible_episode_heads':len(head),'eligible_days':int(head.trading_day.nunique()),'class_counts_heads':{str(k):int(v) for k,v in Counter(head.y.astype(int)).items()},
  'matched_controls_before_labels':len(paired),'matched_pairs_both_labels_ok':sum(x['both_labels_ok'] for x in paired),
  'labeled_sha256':sha(PRIV/'labeled.parquet'),'context_freeze_sha256':sha(PUB/'context-freeze.json'),'completed_at_utc':datetime.now(timezone.utc).isoformat()}
 if paired:
  pg=pd.DataFrame(paired).query('both_labels_ok');stats['descriptive_matched_arrow_net_difference_USD']=float((pg.event_arrow_net-pg.control_same_arrow_net).mean()) if len(pg) else None
 save(PUB/'coverage.json',stats);print(json.dumps(stats,indent=2),flush=True)
if __name__=='__main__':main()
