from common import *
import sys
from mlflow.tracking import MlflowClient
from mlflow.entities import Dataset,DatasetInput,InputTag
os=None

def main():
 client=MlflowClient('http://127.0.0.1:5055');experiment=client.get_experiment_by_name('04_ML_Forschung');assert experiment
 receipt=PUB/'mlflow-receipt.json';mode=sys.argv[1]
 if mode=='start':
  assert not receipt.exists(),'Do not silently replace earlier runs'
  runs={}
  for arm in ['price_context','price_plus_SI']:
   run=client.create_run(experiment.experiment_id,tags={'mlflow.runName':f'SI1746 · TabPFN v2 · {arm}','study':'SI1746-01','model':'TabPFN v2','state':'chronological_fixed_pair',
    'scope':'Development data; fixed quote markouts, not account payouts','attribution':'Built with PriorLabs-TabPFN'})
   runs[arm]=run.info.run_id
   params={'arm':arm,'raw_notifications':1746,'eligible_episode_heads':936,'features':8 if arm=='price_context' else 14,'decision_delay_s':30,'target_horizon_s':900,
    'estimators':4,'seed':SEED,'device':'cpu','initial_train_dates':40,'test_block_dates':10,'gap_dates':1,'training_cap':1000,'hyperparameter_search':False,
    'label':'LONG SHORT FLAT net of bid/ask and frozen fees','control_matching':'frozen before labels; not fake negative training rows'}
   for k,v in params.items():client.log_param(run.info.run_id,k,str(v))
   digest=sha(PRIV/'labeled.parquet')
   ds=Dataset(name='SI1746_exact_contract_labeled_episodes',digest=digest[:32],source_type='code',source=json.dumps({'tags':{'sha256':digest,'local_only':'Private/labeled.parquet'}}))
   client.log_inputs(run.info.run_id,datasets=[DatasetInput(ds,[InputTag('mlflow.data.context','chronological_train_and_later_test')])])
  save(receipt,{'experiment_id':experiment.experiment_id,'runs':runs,'tracking_uri':'http://127.0.0.1:5055','status':'RUNNING'})
 elif mode=='progress':
  import pandas as pd
  data=json.loads(receipt.read_text());f=pd.read_csv(PRIV/'predictions-incremental.csv')
  for arm,runid in data['runs'].items():
   for fold,g in f.groupby('fold'):
    p=g[[f'{arm}_p{k}' for k in range(3)]].to_numpy();y=g.y.to_numpy(dtype=int)
    client.log_metric(runid,'fold_log_loss',float(-np.log(p[np.arange(len(y)),y]).mean()),step=int(fold))
   client.set_tag(runid,'completed_paired_blocks',str(f.fold.nunique()))
  print('Logged completed paired blocks',f.fold.nunique())
 elif mode=='finish':
  data=json.loads(receipt.read_text());result=json.loads((PUB/'results.json').read_text());assert result['status']=='FINISHED'
  for arm,runid in data['runs'].items():
   digest=sha(PRIV/'labeled.parquet');client.set_tag(runid,'actual_fit_dataset_sha256',digest)
   client.set_tag(runid,'mlflow.note.content','Zeitlich getrennter TabPFN-v2-Vergleich: 8 Kursmerkmale gegen dieselben Merkmale plus 6 SI-Attribute. Identische spätere Episoden; Log Loss niedriger ist besser. Der Versuch prüft SI-Attribute an Meldungszeitpunkten, nicht sichere SI-Abwesenheit. 1746 Meldungen geprüft,1635 gültige Labels,936 gültige Episoden. Vergleichsgrafik unter Artifacts/report. Keine Orders oder Prop-Auszahlungen gerechnet.')
   client.set_tag(runid,'prefit_transport_correction','Arrow unavailable in model venv; CSV exact feature parity, nullable nanosecond integers; IDs/classes unchanged')
   ds=Dataset(name='SI1746_actual_fit_canonical_R2',digest=digest[:32],source_type='code',source=json.dumps({'tags':{'sha256':digest,'csv_sha256':sha(PRIV/'labeled.csv'),'local_only':'Private/labeled.parquet'}}))
   client.log_inputs(runid,datasets=[DatasetInput(ds,[InputTag('mlflow.data.context','actual_fit_after_prefit_transport_correction')])])
   for name,value in result['metrics'][arm].items():client.log_metric(runid,name,float(value))
   for name in ['chronological_test_episodes','test_days_with_predictions','folds_completed']:client.log_metric(runid,name,float(result[name]))
   if arm=='price_plus_SI':
    for k in ['mean','ci95_low','ci95_high']:client.log_metric(runid,'paired_SI_logloss_improvement_'+k,float(result['paired_logloss_improvement_SI'][k]))
   for p in sorted(PUB.glob('*.json')):
    if p!=receipt:client.log_artifact(runid,str(p),artifact_path='evidence')
   for p in sorted((HERE/'Source').glob('*.py')):client.log_artifact(runid,str(p),artifact_path='source')
   for name in ['predictions.csv','folds.json','comparison-markouts.parquet']:
    client.log_artifact(runid,str(PRIV/name),artifact_path='local-research-data')
   if (HERE/'Stand.html').exists():client.log_artifact(runid,str(HERE/'Stand.html'),artifact_path='report')
   for name in ['comparison.png','README.md']:
    if (PUB/name).exists():client.log_artifact(runid,str(PUB/name),artifact_path='report')
   client.set_terminated(runid,status='FINISHED')
  data['status']='FINISHED';save(receipt,data)
  for runid in data['runs'].values():assert client.get_run(runid).info.status=='FINISHED'
  print(json.dumps(data,indent=2))
 else:raise ValueError(mode)
if __name__=='__main__':main()
