"""Bounded independent design checks, before fitting; no outcome optimization."""
from common import *
from prepare import context
from labels import label
import pandas as pd

def provenance_guard(sources,decision):
 if np.max(sources)>=decision:raise ValueError('future feature source')
def main():
 tests=[]
 # Dense toy quotes: fixed spread and exact known future path. Entry ask101,
 # exit bid111: 10 ES points less5.74 fees. This is not OHLC optimism.
 t=int(datetime(2026,9,8,16,tzinfo=timezone.utc).timestamp()*NS)
 times=t+np.arange(-310,931,dtype=np.int64)*NS
 bid=np.where(times<t+600*NS,100.,111.);ask=bid+1.;sz=np.ones(len(times))*4
 tape=[times,times.copy(),times.copy(),bid,ask,sz.copy(),sz.copy(),np.ones(len(times),dtype=bool)]
 c=context(tape,t,'ES');assert c['context_status']=='ok';provenance_guard(np.array([c['latest_feature_source_ns']]),t)
 prefix=[v[times<t] for v in tape];assert all(context(prefix,t,'ES')[k]==c[k] for k in PRICE);tests.append('past_features_physically_future_removed')
 try:provenance_guard(np.array([t-1,t+1]),t)
 except ValueError:tests.append('deliberately_future_timestamp_rejected_by_guard')
 else:raise AssertionError('Leaky sentinel accepted')
 r={'decision_ns':t,'market':'ES','context_status':'ok'};z=label(tape,r,900)
 assert abs(z['long_net']-494.26)<1e-7 and abs(z['short_net']+605.74)<1e-7
 assert abs(z['long_stress_net']-469.26)<1e-7 and z['y']==1;tests.append('bid_ask_fees_two_side_tickstress_hand_calculation')
 flat=[v.copy() for v in tape];flat[3][:]=100;flat[4][:]=101
 q=label(flat,r,900);assert q['y']==0 and q['long_net']<0 and q['short_net']<0;tests.append('flat_after_spread_and_fees')
 broken=[v.copy() for v in tape];broken[7][np.searchsorted(times,t)-1]=False
 assert context(broken,t,'ES')['context_status']=='decision_quote_invalid_or_stale';tests.append('invalid_latest_quote_not_backfilled')
 broken=[v.copy() for v in tape];broken[7][(times>=t+300*NS)&(times<=t+360*NS)]=False
 assert label(broken,r,900)['label_status']=='future_path_insufficient';tests.append('future_label_path_gap_rejected')
 for d in ['2026-03-10T00:00:00+00:00','2026-11-03T00:00:00+00:00']:
  ts=int(datetime.fromisoformat(d).timestamp()*NS);day,minute,start,end=clock(ts);assert (end-start)/NS==23*3600
 tests.append('Chicago_DST_session_clock')
 frame=pd.read_parquet(PRIV/'labeled.parquet');assert len(frame[frame.kind=='event'])==1746
 valid=frame[(frame.kind=='event')&frame.label_status.eq('ok')]
 assert ((valid.long_net>0).astype(int)+(valid.short_net>0).astype(int)<=1).all()
 assert (valid.latest_feature_source_ns<valid.decision_ns).all()
 tests.append('all1746_retained_and_mutually_exclusive_labels')
 save(PUB/'design-tests.json',{'status':'passed','tests':tests,'count':len(tests),'scope':'Bounded fixtures and actual retained-row provenance; no universal bug-free guarantee',
  'verified_before_fit_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':sha(Path(__file__))})
 print('Design tests passed:',len(tests))
if __name__=='__main__':main()
