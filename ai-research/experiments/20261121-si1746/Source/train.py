"""One fixed chronological paired experiment. No feature/parameter search."""
from common import *
import os,time,sys
os.environ.setdefault('SKB_DATA_DIRECTORY',str(ROOT/'work/tools/tabpfn/skrub-data'))
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'work/tools/tabpfn/matplotlib'))
os.environ.setdefault('HF_HUB_OFFLINE','1');os.environ.setdefault('DO_NOT_TRACK','1')
os.environ.setdefault('TABPFN_MODEL_CACHE_DIR',str(CHECKPOINT.parent))
import pandas as pd
import torch
from tabpfn import TabPFNClassifier
from tabpfn.constants import ModelVersion
from sklearn.metrics import balanced_accuracy_score
torch.set_num_threads(4)

def aligned(model,x):
 raw=model.predict_proba(x);p=np.full((len(x),3),1e-7)
 for i,c in enumerate(model.classes_):p[:,int(c)]=raw[:,i]
 p=np.clip(p,1e-7,1);return p/p.sum(axis=1,keepdims=True)
def score(y,p):
 return {'log_loss':float(-np.log(p[np.arange(len(y)),y]).mean()),
  'brier':float(np.mean(np.sum((p-np.eye(3)[y])**2,axis=1))),
  'balanced_accuracy':float(balanced_accuracy_score(y,p.argmax(axis=1))),'accuracy':float(np.mean(y==p.argmax(axis=1)))}
def main():
 assert sha(CHECKPOINT)==json.loads((PUB/'preregister.json').read_text())['checkpoint_sha256']
 cov=json.loads((PUB/'coverage.json').read_text());assert sha(PRIV/'labeled.parquet')==cov['labeled_sha256']
 frame=pd.read_csv(PRIV/'labeled.csv',float_precision='round_trip',dtype={k:'Int64' for k in ['decision_ns','known_ns','latest_feature_source_ns','entry_quote_ns','exit_quote_ns','h5_entry_quote_ns','h5_exit_quote_ns']});events=frame[(frame.kind=='event')&frame.episode_head&frame.label_status.eq('ok')].copy()
 events=events.sort_values(['decision_ns','event_key']).reset_index(drop=True);events.y=events.y.astype(int)
 assert np.isfinite(events[PRICE+SI].to_numpy()).all()
 assert (events.latest_feature_source_ns<events.decision_ns).all()
 rawdates=sorted(x['date'] for x in json.loads(INDEX.read_text())['completed'])
 dates=[d for d in rawdates if events.trading_day.min()<=d<=events.trading_day.max() and datetime.fromisoformat(d).weekday()<5]
 assert set(events.trading_day)<=set(dates)
 folds=[]
 for start in range(41,len(dates),10):
  testdates=dates[start:start+10];train=events[events.trading_day.isin(dates[:start-1])].copy();test=events[events.trading_day.isin(testdates)].copy()
  if not len(test):continue
  teststart=int(test.decision_ns.min())-300*NS;train=train[train.exit_quote_ns<teststart]
  while len(train)>1000:train=train[train.trading_day!=train.trading_day.min()]
  if len(train)<50 or train.y.nunique()<2:
   folds.append({'fold':len(folds),'status':'insufficient_training','train_n':len(train),'test_n':len(test),'test_dates':testdates});continue
  folds.append({'fold':len(folds),'status':'ready','train_n':len(train),'test_n':len(test),'train_last_day':train.trading_day.max(),'gap_day':dates[start-1],
    'test_dates':testdates,'train_ids':train.event_key.tolist(),'test_ids':test.event_key.tolist(),
    'latest_train_outcome_ns':int(train.exit_quote_ns.max()),'first_test_information_ns':teststart})
 save(PRIV/'folds.json',folds)
 save(PUB/'training-design.json',{'frozen_before_first_fit_utc':datetime.now(timezone.utc).isoformat(),'eligible_heads':len(events),'calendar':dates,
  'initial40_days':dates[:40],'gap_days':1,'test_block_days':10,'training_cap1000_whole_days':True,
  'folds':[{k:v for k,v in f.items() if k not in ('train_ids','test_ids')} for f in folds],
  'train_source_sha256':sha(Path(__file__)),'folds_sha256':sha(PRIV/'folds.json'),'labels_sha256':sha(PRIV/'labeled.parquet'),
  'fixed_models':{'version':'V2','n_estimators':4,'device':'cpu','torch_threads':4,'seed':SEED,'category_columns':{'price_context':[0],'price_plus_SI':[0,8,9]}}})
 outputs=[];fittimes=[];numeric=[];starttime=time.time()
 for f in folds:
  if f['status']!='ready':continue
  train=events.set_index('event_key').loc[f['train_ids']];test=events.set_index('event_key').loc[f['test_ids']]
  assert set(train.index).isdisjoint(test.index)
  assert train.exit_quote_ns.max()<test.decision_ns.min()-300*NS
  prior=(np.bincount(train.y,minlength=3)+1)/(len(train)+3)
  results={}
  for arm,features,cats in [('price_context',PRICE,[0]),('price_plus_SI',PRICE+SI,[0,8,9])]:
   began=time.time();model=TabPFNClassifier.create_default_for_version(ModelVersion.V2,n_estimators=4,device='cpu',random_state=SEED,
    model_path=str(CHECKPOINT),categorical_features_indices=cats,n_preprocessing_jobs=1)
   model.fit(train[features].to_numpy(),train.y.to_numpy())
   probabilities=[]
   for i in range(len(test)):
    probabilities.append(aligned(model,test[features].iloc[[i]].to_numpy())[0])
    if (i+1)%20==0:
     save(HERE/'training-progress.json',{'stage':'training','fold':f['fold'],'arm':arm,'current_predictions':i+1,'fold_total':len(test),'elapsed_s':time.time()-starttime})
   p=np.array(probabilities);results[arm]=p
   batch=aligned(model,test[features].iloc[:min(4,len(test))].to_numpy())
   numeric.append({'fold':f['fold'],'arm':arm,'diagnostic_rows':len(batch),'max_batch_singleton_abs':float(np.max(np.abs(batch-p[:len(batch)]))),
     'argmax_changes':int(np.sum(batch.argmax(axis=1)!=p[:len(batch)].argmax(axis=1))),'actual_predictions':'singletons'})
   fittimes.append({'fold':f['fold'],'arm':arm,'train_rows':len(train),'test_rows':len(test),'seconds':time.time()-began})
   print('finished',f['fold'],arm,'train',len(train),'test',len(test),'seconds',round(time.time()-began,1),flush=True)
   del model
  for i,(key,r) in enumerate(test.iterrows()):
   z={'event_key':key,'fold':f['fold'],'trading_day':r.trading_day,'market':r.market,'y':int(r.y),'long_net':r.long_net,'short_net':r.short_net,
     'long_stress_net':r.long_stress_net,'short_stress_net':r.short_stress_net}
   for arm,p in list(results.items())+[('train_prior',np.tile(prior,(len(test),1)))]:
    for k in range(3):z[f'{arm}_p{k}']=float(p[i,k])
   outputs.append(z)
  pd.DataFrame(outputs).to_csv(PRIV/'predictions-incremental.csv',index=False)
  save(PUB/'training-times.json',fittimes);save(PUB/'numeric-diagnostic.json',numeric)
 pred=pd.DataFrame(outputs);assert pred.event_key.is_unique
 pred.to_csv(PRIV/'predictions.csv',index=False)
 summary={'status':'FINISHED','model_version':'TabPFN v2 local CPU,4estimators','all_raw_events':1746,'eligible_heads':len(events),
  'chronological_test_episodes':len(pred),'test_days_with_predictions':int(pred.trading_day.nunique()),'folds_completed':len({x['fold'] for x in outputs}),
  'first_test_day':pred.trading_day.min(),'last_test_day':pred.trading_day.max(),'metrics':{},'by_market':[],
  'predictions_sha256':sha(PRIV/'predictions.csv'),'elapsed_seconds':time.time()-starttime,'fitting_completed_utc':datetime.now(timezone.utc).isoformat()}
 y=pred.y.to_numpy();losses={}
 for arm in ['price_context','price_plus_SI','train_prior']:
  p=pred[[f'{arm}_p{k}' for k in range(3)]].to_numpy();values=score(y,p);losses[arm]=-np.log(p[np.arange(len(y)),y]);decision=p.argmax(axis=1)
  normal=np.where(decision==1,pred.long_net,np.where(decision==2,pred.short_net,0.));stress=np.where(decision==1,pred.long_stress_net,np.where(decision==2,pred.short_stress_net,0.))
  values.update(hypothetical_mean_quote_net_usd=float(np.mean(normal)),hypothetical_median_quote_net_usd=float(np.median(normal)),
   hypothetical_mean_stress_quote_net_usd=float(np.mean(stress)),hypothetical_median_stress_quote_net_usd=float(np.median(stress)),nonflat_predictions=int(np.sum(decision!=0)))
  summary['metrics'][arm]=values
  for market,g in pred.groupby('market'):
   pp=g[[f'{arm}_p{k}' for k in range(3)]].to_numpy();summary['by_market'].append(dict(market=market,arm=arm,n=len(g),**score(g.y.to_numpy(),pp)))
 diff=losses['price_context']-losses['price_plus_SI'];testdays=[d for d in dates if pred.trading_day.min()<=d<=pred.trading_day.max()]
 sums=np.array([diff[pred.trading_day.eq(d)].sum() for d in testdays]);nums=np.array([int(pred.trading_day.eq(d).sum()) for d in testdays]);rng=np.random.default_rng(SEED);boots=[]
 for _ in range(1999):
  starts=rng.integers(0,max(1,len(testdays)-4),size=int(np.ceil(len(testdays)/5)))
  idx=np.concatenate([np.arange(s,min(s+5,len(testdays))) for s in starts])[:len(testdays)]
  if nums[idx].sum():boots.append(float(sums[idx].sum()/nums[idx].sum()))
 lo,hi=np.quantile(boots,[.025,.975])
 summary['paired_logloss_improvement_SI']={'mean':float(diff.mean()),'ci95_low':float(lo),'ci95_high':float(hi),'moving_day_block':5,'bootstrap_draws':len(boots),'seed':SEED,
  'interpretation':'positive favors SI; conditional development-data uncertainty, not fresh OOS or causal proof'}
 summary['macro_equal_market_logloss']={arm:float(np.mean([x['log_loss'] for x in summary['by_market'] if x['arm']==arm])) for arm in summary['metrics']}
 summary['limits']=['May-Oct2026 repeatedly studied development period','Message time proxy, not original detection/receipt time','45 fixed matched controls only; insufficient for broad causal attribution','Quote markouts, no orders, account payouts or portfolio equity','No feature/model/threshold optimization performed']
 save(PUB/'results.json',summary);save(HERE/'training-progress.json',{'stage':'FINISHED','test_episodes':len(pred),'elapsed_s':time.time()-starttime})
 print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':
 try:main()
 except Exception as e:
  save(HERE/'training-error.json',{'status':'FAILED','error':repr(e),'utc':datetime.now(timezone.utc).isoformat()});raise
