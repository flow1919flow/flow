from common import *
from prepare import Loader,context
from verify_design import provenance_guard
import pandas as pd

def main():
 events=pd.read_parquet(PRIV/'events-context.parquet');labels=pd.read_parquet(PRIV/'labeled.parquet');loader=Loader();proof=[]
 for market,g in events[events.context_status.eq('ok')].groupby('market'):
  g=g.sort_values('decision_ns');indices=np.unique(np.linspace(0,len(g)-1,20).astype(int))
  for r in g.iloc[indices].to_dict('records'):
   t=int(r['decision_ns']);tape=loader.tape(r['symbol'],t-310*NS,t+920*NS)
   full=context(tape,t,market);truncated=context([x[tape[0]<t] for x in tape],t,market)
   for key in PRICE:assert full[key]==truncated[key] and abs(full[key]-r[key])<1e-12
   provenance_guard(np.array([full['latest_feature_source_ns']]),t)
   proof.append({'market':market,'all_price_features_equal':True,'actual_sources_strictly_past':True})
 assert events.groupby('episode_id').episode_head.sum().eq(1).all()
 for _,g in events.groupby('episode_id'):
  g=g.sort_values('decision_ns');assert g.loc[g.episode_head,'decision_ns'].iloc[0]==g.decision_ns.min()
  assert (g.decision_ns.diff().dropna()<=1200*NS).all()
 m=pd.read_parquet(PRIV/'matching.parquet').query("status=='matched'")
 assert m.event_key.is_unique and m.control_key.is_unique
 q=labels.set_index('event_key');balance=[]
 for r in m.to_dict('records'):
  a=q.loc[r['event_key']];b=q.loc[r['control_key']]
  assert a.symbol==b.symbol and a.trading_day==b.trading_day and int(a.chicago_minute//30)==int(b.chicago_minute//30)
  balance.append(np.abs(a[PRICE[2:]].to_numpy(dtype=float)-b[PRICE[2:]].to_numpy(dtype=float)))
 out={'status':'passed','prefix_rows':len(proof),'prefix_rows_per_market':{m:sum(x['market']==m for x in proof) for m in MARKETS},
  'future_removed_exact_feature_parity':True,'retained_episode_heads':int(events.episode_head.sum()),'all_episode_heads_first':True,
  'matching_without_reuse':True,'matching_same_contract_day_bucket':True,'matched_count':len(m),
  'matched_mean_absolute_context_differences':dict(zip(PRICE[2:],[float(x) for x in np.mean(balance,axis=0)])),
  'scope':'80 deterministic dates/markets samples, all primary head IDs and all matched IDs; no full-engine equivalence or universal leakage proof',
  'audited_at_utc':datetime.now(timezone.utc).isoformat()}
 save(PUB/'stratified-temporal-audit.json',out);print(json.dumps(out,indent=2))
if __name__=='__main__':main()
