"""Local-only MLflow evidence. Never logs keys, raw ticks, or remote-account data."""
from pathlib import Path
import argparse,json,os,hashlib
os.environ['MLFLOW_DISABLE_AGENT_HINT']='1'
from mlflow.tracking import MlflowClient
from mlflow.entities import Dataset,DatasetInput,InputTag
from native_check import HERE,read,write,sha

def update(arm):
    client=MlflowClient('http://127.0.0.1:5055');exp=client.get_experiment_by_name('04_ML_Forschung');assert exp
    path=HERE/'MLflow'/f'{arm}.json'
    if path.exists():rid=read(path)['run_id']
    else:
        title={'Controls':'ML1 · Zufallskontrollen1000 ·21.11.','ML1C':'L2 · kreuzweise Schwelle ·21.11.',
            'ML8':'ML8 · flaches Gradient Boosting ·21.11.','MR1':'MR1 · Ridge Netto-R ·21.11.',
            'ML9':'TabPFN-ML9 · v2 ·21.11.'}[arm]
        run=client.create_run(exp.experiment_id,tags={'mlflow.runName':title,'fresh_OOS':'false',
            'live_changes':'false','preregister_commit':read(HERE/'preregister-github-receipt.json')['commit'],
            'kind':'actual_development_research','phase':'started'})
        rid=run.info.run_id
        write(path,dict(run_id=rid,experiment_id=exp.experiment_id,
            url=f'http://127.0.0.1:5055/#/experiments/{exp.experiment_id}/runs/{rid}'))
        for k,v in dict(sessions=242,candidates=347,features=5,outer_blocks=9,arm=arm,
            preregister_sha256=sha(HERE/'preregister.json'),budget_usd=1000).items():client.log_param(rid,k,v)
        client.log_artifact(rid,str(HERE/'preregister.json'),'design')
        client.log_artifact(rid,str(HERE/'README.md'),'design')
    result=HERE/'Controls/results.json' if arm=='Controls' else HERE/'Training'/arm/'results.json'
    progress=HERE/'Training'/arm/'progress.json'
    if arm!='Controls':
        specification=read(HERE/'preregister.json')['arms'][arm]
        existing=client.get_run(rid).data.params
        for key,value in specification.items():
            if key not in existing:client.log_param(rid,key,value)
        if arm=='ML9':
            client.set_tag(rid,'attribution','Built with PriorLabs-TabPFN')
            client.set_tag(rid,'decisions_use','singleton point-in-time predictions')
    if progress.exists():
        p=read(progress);client.log_metric(rid,'completed_blocks',p['completed_blocks'])
    if arm=='Controls' and (HERE/'Controls/execution-provenance.json').exists():
        p=read(HERE/'Controls/execution-provenance.json')
        client.set_tag(rid,'executed_control_commit',p['executed_registration_commit'])
        client.log_artifact(rid,str(HERE/'Controls/execution-provenance.json'),'provenance')
    if result.exists():
        j=read(result);client.log_artifact(rid,str(result),'results')
        if arm!='Controls':
            content=dict(sources=j['sources'],features=read(HERE/'preregister.json')['features'],
                scoring_period=['2025-11-24','2026-10-30'],period_candidates=347,
                sessions=242,outer_test_predictions=230)
            digest=hashlib.sha256(json.dumps(content,sort_keys=True).encode()).hexdigest()
            manifest=HERE/'input-dataset-manifest.json';write(manifest,dict(**content,sha256=digest))
            dataset=Dataset(name='ES-C28.03 · 347 Setups · 242 Sitzungen',digest=digest[:32],
                source_type='code',source=json.dumps({'tags':{'mlflow.source.name':'ai-research/experiments/20261121/research.py',
                    'mlflow.source.git.commit':read(HERE/'preregister-github-receipt.json')['commit']}}),
                schema=json.dumps({'features':content['features']}),profile=json.dumps({'num_rows':347,'num_features':5}))
            known=client.get_run(rid).inputs.dataset_inputs
            if not any(d.dataset.digest==digest[:32] for d in known):
                client.log_inputs(rid,datasets=[DatasetInput(dataset,tags=[InputTag('mlflow.data.context','chronological_train_test')])])
            client.log_artifact(rid,str(manifest),'data')
            for k,v in j['metrics'].items():
                if isinstance(v,(int,float)) and not isinstance(v,bool):client.log_metric(rid,k,v)
            client.set_tag(rid,'training_completed','true')
            client.set_tag(rid,'phase','training_completed_native_pending')
        else:client.set_tag(rid,'phase','candidate_controls_complete_not_cash_null')
    family=HERE/'Controls/family-null.json'
    if family.exists():client.log_artifact(rid,str(family),'controls')
    for name in ['native-acceptance-summary.json','prefix-additional-acceptance.json','native-source-proof.json']:
        evidence=HERE/name
        if evidence.exists():client.log_artifact(rid,str(evidence),'native-evidence')
    client.set_tag(rid,'native_engine_version','144.2953')
    client.set_tag(rid,'cloud_compute_spend_usd','0')
    cash=HERE/'Cash/results.json'
    if cash.exists() and arm!='Controls':
        j=read(cash)
        for cost,arms in j['results'].items():
            for key in ['mean_end_cash_usd','median_end_cash_usd','mean_gain_usd','median_gain_usd']:
                client.log_metric(rid,'cash_'+cost+'_'+key,arms[arm][key])
                client.log_metric(rid,'base_'+cost+'_'+key,arms['base'][key])
        client.log_artifact(rid,str(cash),'cash');client.set_tag(rid,'phase','native_and_cash_complete_selected_year')
        client.set_terminated(rid,'FINISHED')
    if arm=='Controls' and result.exists():client.set_terminated(rid,'FINISHED')
    print(read(path)['url'],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('arm',choices=['Controls','ML1C','ML8','MR1','ML9']);update(p.parse_args().arm)
