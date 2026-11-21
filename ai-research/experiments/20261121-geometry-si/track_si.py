"""Local MLflow ingestion record. A finished import is not a fitted model."""
from pathlib import Path
import json,os
os.environ['MLFLOW_DISABLE_AGENT_HINT']='1'
from mlflow.tracking import MlflowClient
from mlflow.entities import Dataset,DatasetInput,InputTag

HERE=Path(__file__).resolve().parent

def main():
    j=json.loads((HERE/'SI/ingest-result.json').read_text())
    assert j['rows']==229 and j['parquet_roundtrip_identical']
    c=MlflowClient('http://127.0.0.1:5055');exp=c.get_experiment_by_name('04_ML_Forschung');assert exp
    receipt=HERE/'SI/mlflow-ingest.json'
    if receipt.exists():rid=json.loads(receipt.read_text())['run_id']
    else:
        rid=c.create_run(exp.experiment_id,tags={'mlflow.runName':'SI · 229 ES-Meldungen · Datenimport',
            'kind':'data_ingestion_not_model_training','supervised_model_trained':'false',
            'live_changes':'false','cloud_compute_spend_usd':'0','phase':'all229_loaded_labels_pending'}).info.run_id
    for k in ['rows','chicago_calendar_days','connected_overlap_episodes','unique_messages','edited_messages']:
        c.log_metric(rid,k,j[k])
    for k,v in j['types'].items():c.log_metric(rid,k.lower()+'_events',v)
    c.set_tag(rid,'availability','Discord sent/edited proxy +30s; not actual Bookmap receive time')
    c.set_tag(rid,'feed_absence','unknown, never encoded as no-event controls')
    dataset=Dataset(name='SI ES · 229 Meldungen · 78 Tage',digest=j['parquet_sha256'][:32],
        source_type='code',source=json.dumps({'tags':{'mlflow.source.name':'ingest_si.py',
            'source_archive_sha256':j['original_archive_sha256']}}),
        profile=json.dumps({'num_rows':229,'connected_overlap_episodes':j['connected_overlap_episodes']}))
    if not any(d.dataset.digest==dataset.digest for d in c.get_run(rid).inputs.dataset_inputs):
        c.log_inputs(rid,datasets=[DatasetInput(dataset,[InputTag('mlflow.data.context','ingestion_only')])])
    for name in ['ingest-plan.json','ingest-result.json','es-events-229.parquet','es-events-229.csv']:
        c.log_artifact(rid,str(HERE/'SI'/name),'data')
    c.log_artifact(rid,str(HERE/'ingest_si.py'),'source')
    c.set_terminated(rid,'FINISHED')
    output=dict(run_id=rid,url=f'http://127.0.0.1:5055/#/experiments/{exp.experiment_id}/runs/{rid}',
        state='finished_import_not_supervised_training',rows=229,parquet_sha256=j['parquet_sha256'])
    receipt.write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output))

if __name__=='__main__':main()
