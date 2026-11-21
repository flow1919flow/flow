"""Shared numeric table/folds for four cloud arms and local model comparisons."""
from common import *
import pandas as pd

NUMERIC_SI=SI[:3]+['SI_status_code']
def business_days(first,last):
 d=datetime.fromisoformat(first).date();end=datetime.fromisoformat(last).date();out=[]
 while d<=end:
  if d.weekday()<5:out.append(str(d))
  d+=timedelta(days=1)
 return out
def next_business(day):
 d=datetime.fromisoformat(day).date()+timedelta(days=1)
 while d.weekday()>=5:d+=timedelta(days=1)
 return str(d)
def main():
 proof=json.loads((PUBLIC/'label-proof.json').read_text());assert sha(PRIVATE/'labeled.json')==proof['labeled_sha256']
 allrows=json.loads((PRIVATE/'labeled.json').read_text());rows=sorted((r for r in allrows if r['price_status']=='ok'),key=lambda r:r['decision_ns']);assert len(rows)==159
 for r in rows:r['SI_status_code']=1 if r['SI_archive_status']=='A' else -1
 frame=pd.DataFrame(rows);array=frame[PRICE+NUMERIC_SI].to_numpy(dtype=float)
 assert np.isfinite(array[:,:8]).all() and np.isin(array[:,-1],[-1.,1.]).all()
 assert all(r['archived_count60m_cap5'] is None for r in rows if r['SI_archive_status']=='U')
 frame.to_csv(PRIVATE/'dataset.csv',index=False);np.save(PRIVATE/'canonical-features.npy',array)
 restored=pd.read_csv(PRIVATE/'dataset.csv',float_precision='round_trip');assert np.array_equal(restored[PRICE+NUMERIC_SI].to_numpy(dtype=float),array,equal_nan=True)
 # No retrospective observed-message-day eligibility. First48cases are a minimum;
 # retain every case on their final CTdate in training,then a whole businessdaygap.
 initial_last=rows[47]['date'];initial_gap=next_business(initial_last);first_test=next_business(initial_gap)
 calendar=business_days(first_test,rows[-1]['date']);folds=[]
 for begin in range(0,len(calendar),20):
  testdays=calendar[begin:begin+20];test=[i for i,r in enumerate(rows) if r['date'] in testdays]
  if not test:continue
  start=testdays[0];gap=initial_gap if begin==0 else calendar[begin-1]
  information_start=min(rows[i]['decision_ns'] for i in test)-300*NS
  train=[i for i,r in enumerate(rows) if r['date']<gap and r['native_exit_time_ns']<information_start]
  assert len(train)>=48 and max(rows[i]['native_exit_time_ns'] for i in train)<information_start
  assert max(rows[i]['date'] for i in train)<gap<min(rows[i]['date'] for i in test)
  selected=sorted(train,key=lambda i:rows[i]['decision_ns'])[-32:]
  folds.append({'fold_id':len(folds),'train_indices':train,'test_indices':test,'train_ids':[rows[i]['case_key'] for i in train],
   'test_ids':[rows[i]['case_key'] for i in test],'fewshot_indices':selected,'fewshot_ids':[rows[i]['case_key'] for i in selected],
   'train_n':len(train),'test_n':len(test),'gap_day':gap,'train_last_date':max(rows[i]['date'] for i in train),
   'test_dates':testdays,'test_first_information_ns':information_start,'latest_train_outcome_ns':max(rows[i]['native_exit_time_ns'] for i in train),
   'test_prior15_known_n':sum(rows[i]['has_prior15m_archive_match'] for i in test),
   'test_prior60_known_n':sum(rows[i]['has_prior60m_archive_match'] for i in test)})
 tests=[i for f in folds for i in f['test_indices']];assert len(set(tests))==len(tests) and len(tests)<=111
 save(PRIVATE/'folds.json',folds)
 manifest={'state':'correct_HY104_EMA22_dataset_and_temporal_folds_frozen','created_at_utc':stamp(),'dataset_csv':str(PRIVATE/'dataset.csv'),
  'canonical_npy':str(PRIVATE/'canonical-features.npy'),'folds_json':str(PRIVATE/'folds.json'),'dataset_csv_sha256':sha(PRIVATE/'dataset.csv'),
  'canonical_npy_sha256':sha(PRIVATE/'canonical-features.npy'),'folds_sha256':sha(PRIVATE/'folds.json'),
  'id_column':'case_key','label_column':'y','date_column':'date','decision_ns_column':'decision_ns','outcome_ns_column':'native_exit_time_ns',
  'context_features':PRICE,'si_features':NUMERIC_SI,'categorical_feature_indices_context_plus_SI':[11],
  'SI_status_code_legend':{'1':'Archivedprior60m message observed;fullfeedcoverage unknown','-1':'No priorarchivedmatch;fullfeedcoverage unknown,NOTactualnoSI'},
  'missing_SI_values':'NaN inNPY/emptyCSV correspond originalnull;doNOTinterpret asactualnoSI/numericalzero. Any imputation must be training-only with explicit missing indicators.',
  'source_strategy':'Native HY104EMA22 EntryAverageCase5;OpeningRange0;targetoffset.75;159executedsetupsafterfirstSIpublication',
  'cohort_n':len(rows),'common_period':[rows[0]['date'],rows[-1]['date']],'initial_minimum_train_cases':48,'initial_last_train_date':initial_last,
  'initial_gap_day':initial_gap,'first_test_date':first_test,'test_block_business_dates':20,'fold_count':len(folds),'test_cases':len(tests),
  'test_days_with_cases':len({rows[i]['date'] for i in tests}),'test_prior15_known_n':sum(rows[i]['has_prior15m_archive_match'] for i in tests),
  'test_prior60_known_n':sum(rows[i]['has_prior60m_archive_match'] for i in tests),'all159_prior15_known':8,'all159_prior60_known':27,
  'class_counts_all':{str(k):int(v) for k,v in frame.y.value_counts().items()},
  'label':'ActualnativeEMA22exit net−1.06USDfee normalization−25USD tickstress>0,not15minmarkout',
  'four_cloud_arms':'DrexMaxFinance andClef,eachsamepricecontextalonevsprice+causalSI;sharedIDs/labels/folds',
  'no_fit_started':True,'no_API_calls':True,'feature_freeze_sha256':sha(PUBLIC/'feature-freeze.json'),'label_proof_sha256':sha(PUBLIC/'label-proof.json')}
 save(PUBLIC/'dataset-manifest.json',manifest);print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
