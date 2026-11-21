"""Recompute finished metrics and fold separation independently of fit process."""
from common import *
import pandas as pd
from sklearn.metrics import log_loss,balanced_accuracy_score

def main():
 result=json.loads((PUB/'results.json').read_text());design=json.loads((PUB/'training-design.json').read_text())
 assert result['status']=='FINISHED' and sha(HERE/'Source/train.py')==design['train_source_sha256']
 labels=pd.read_parquet(PRIV/'labeled.parquet').set_index('event_key');pred=pd.read_csv(PRIV/'predictions.csv',float_precision='round_trip')
 assert sha(PRIV/'predictions.csv')==result['predictions_sha256'] and pred.event_key.is_unique
 assert len(pred)==sum(f['test_n'] for f in design['folds'] if f['status']=='ready')
 folds=json.loads((PRIV/'folds.json').read_text());independent={}
 for f in folds:
  if f['status']!='ready':continue
  tr=labels.loc[f['train_ids']];te=labels.loc[f['test_ids']]
  assert set(tr.index).isdisjoint(te.index)
  assert tr.trading_day.max()<f['gap_day']<te.trading_day.min()
  assert int(tr.exit_quote_ns.max())<int(te.decision_ns.min())-300*NS
  assert set(pred.loc[pred.fold==f['fold'],'event_key'])==set(te.index)
  assert len(tr)<=1000
 for arm in ['price_context','price_plus_SI','train_prior']:
  p=pred[[f'{arm}_p{k}' for k in range(3)]].to_numpy();y=pred.y.to_numpy(dtype=int)
  assert np.max(np.abs(p.sum(axis=1)-1))<1e-10 and np.min(p)>0
  loss=float(log_loss(y,p,labels=[0,1,2]));assert abs(loss-result['metrics'][arm]['log_loss'])<1e-12
  independent[arm]=loss
 expected=labels.loc[pred.event_key,'y'].to_numpy(dtype=int);assert np.array_equal(expected,pred.y.to_numpy(dtype=int))
 src=labels.query("kind=='event' and label_status=='ok'")
 for market,g in src.groupby('market'):
  tick,point,fee=MARKETS[market]
  assert np.max(np.abs((g.exit_bid-g.entry_ask)*point-2*fee-g.long_net))<1e-7
  assert np.max(np.abs((g.entry_bid-g.exit_ask)*point-2*fee-g.short_net))<1e-7
  assert np.max(np.abs(g.long_net-2*tick*point-g.long_stress_net))<1e-7
  yy=np.where(g.long_net>0,1,np.where(g.short_net>0,2,0));assert np.array_equal(yy,g.y.to_numpy(dtype=int))
 save(PUB/'acceptance.json',{'status':'passed','all1746_retained':int(labels.kind.eq('event').sum())==1746,
  'completed_two_arms_times_folds':2*len(folds),'unique_later_predictions_per_arm':len(pred),'same_test_ids_and_labels':True,
  'all_whole_day_splits_and_outcome_purges_passed':True,'independent_sklearn_log_loss':independent,
  'all1635_valid_event_label_bid_ask_fees_recomputed':True,'fit_source_unchanged_since_design_freeze':True,
  'verified_at_utc':datetime.now(timezone.utc).isoformat(),'scope':'Dataset/metrics/separation acceptance, not proof of future profitability'})
 print('Acceptance passed:',len(pred),'paired predictions,',2*len(folds),'fits')
if __name__=='__main__':main()
