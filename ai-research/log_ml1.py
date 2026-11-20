"""Record actual completed prediction research in the local MLflow UI."""
from pathlib import Path
import json, os
from mlflow.tracking import MlflowClient

DE=Path(os.environ.get('HY_WORKSPACE',Path.cwd())).resolve()
HERE=DE/'outputs/AI-Forschung-20261120'

def record_cash(client,rid,value,receipt):
    path=HERE/'Cash/results.json'
    if not path.exists():return
    cash=json.loads(path.read_text())
    assert cash['state']=='complete_development_comparison'
    for cost,arms in cash['results'].items():
        for arm,metrics in arms.items():
            if isinstance(metrics,dict):
                for key in ('mean_end_cash_usd','median_end_cash_usd','mean_gain_usd','median_gain_usd'):
                    client.log_metric(rid,f'cash_{cost}_{arm}_{key}',metrics[key])
    client.log_artifact(rid,str(path),'cash')
    client.log_artifact(rid,str(HERE/'Cash/design-before-results.json'),'cash')
    client.log_artifact(rid,str(Path(__file__).parent/'replay_ml1.py'),'source')
    for p in (HERE/'SQX/gated').glob('*/verified.json'):
        client.log_artifact(rid,str(p),'acceptance/gated/'+p.parent.name)
    client.set_tag(rid,'cash_comparison_complete','true')
    client.set_tag(rid,'cash_improvement_proven','false')
    client.set_tag(rid,'conclusion','worse_than_reference_no_leaderboard_promotion')
    value.update(cash_comparison_complete=True,state='actual_training_and_native_cash_comparison_logged')
    receipt.write_text(json.dumps(value,indent=2)+'\n')

def main():
    receipt=HERE/'Training/mlflow-receipt.json'
    client=MlflowClient('http://127.0.0.1:5055')
    if receipt.exists():
        value=json.loads(receipt.read_text())
        record_cash(client,value['run_id'],value,receipt)
        print(receipt.read_text());return
    result=json.loads((HERE/'Training/results.json').read_text())
    assert result['state']=='trained_development_diagnostic'
    exp=client.get_experiment_by_name('04_ML_Forschung');assert exp
    run=client.create_run(exp.experiment_id,tags={
        'mlflow.runName':'ML1 · L2-Logistik · 9 zeitliche Prüfblöcke',
        'kind':'actual_trained_classifier_development_diagnostic',
        'trained_model':'StandardScaler + L2 LogisticRegression',
        'training_completed':'true','native_observer_parity':'6_segments_identical',
        'fresh_OOS':'false','cash_improvement_proven':'false','live_changes':'false'})
    rid=run.info.run_id
    params=dict(model='LogisticRegression',regularization='L2',C=.1,solver='lbfgs',
        features=5,first_training_sessions=80,gap_sessions=1,test_block_sessions=20,
        chronological_blocks=9,unique_common_period_candidates=347,scored_sessions=242,
        threshold='training-score 20th percentile; ties accepted',
        label='positive net after mini fees and 1 adverse tick per side',
        features_list=', '.join(result['config']['features']))
    for k,v in params.items():client.log_param(rid,k,v)
    for k,v in result['metrics'].items():
        if isinstance(v,(float,int)):client.log_metric(rid,k,v)
    for block in result['blocks']:
        for k in ('train_samples','test_samples','threshold','skipped','train_positive','test_positive'):
            client.log_metric(rid,k,block[k],step=block['block'])
    for name in ('design-before-results.json','results.json','predictions.csv'):
        client.log_artifact(rid,str(HERE/'Training'/name),'training')
    for name in ('run_sqx_observer.py','train_ml1.py','test_temporal.py'):
        client.log_artifact(rid,str(Path(__file__).parent/name),'source')
    client.log_artifact(rid,str(HERE/'temporal-tests.log'),'acceptance')
    for p in (HERE/'SQX/observer').glob('*/verified.json'):
        client.log_artifact(rid,str(p),'acceptance/'+p.parent.name)
    client.set_terminated(rid,'FINISHED')
    value=dict(run_id=rid,experiment_id=exp.experiment_id,
        url=f'http://127.0.0.1:5055/#/experiments/{exp.experiment_id}/runs/{rid}',
        state='actual_training_logged',cash_comparison_complete=False)
    receipt.write_text(json.dumps(value,indent=2)+'\n')
    record_cash(client,rid,value,receipt)
    print(receipt.read_text())

if __name__=='__main__':main()
