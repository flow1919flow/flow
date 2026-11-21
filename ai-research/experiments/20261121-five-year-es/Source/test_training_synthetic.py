"""Synthetic-only audit: temporal fit/calibration, publication and one-shot guards.

All datasets and proof envelopes below are visibly synthetic temporary fixtures.
Never opens any real candidate/label CSV, performs API calls or fits real data.
"""
from pathlib import Path
from contextlib import contextmanager,redirect_stdout
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import csv,hashlib,importlib.util,io,json,tempfile,traceback
import numpy as np
import pandas as pd

SCRIPT=Path(__file__).with_name('train_fiveyear.py');spec=importlib.util.spec_from_file_location('sut_training',SCRIPT);t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
ORIGINAL_HERE=t.HERE;ORIGINAL_DATA=t.DATA;RESULTS=[]

def write_csv(p,rows):
    fields=sorted(set().union(*(r.keys()for r in rows)));stream=io.StringIO();w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();w.writerows(rows);p.write_text(stream.getvalue())
def dump(p,value):p.parent.mkdir(exist_ok=True,parents=True);p.write_text(json.dumps(value,allow_nan=False)+'\n')
def fixture_rows(days,negative=False):
    rows=[]
    for i,day in enumerate(days):
        signal=t.midnight(day)+9*3600*t.NS;yy=(-.5 if negative else .5)+.1*np.sin(i);risk=500+i
        r=dict(case_key=f'synthetic-{day}',contract='SYNTHETIC_ES',side=1,day=day,signal_ns=signal,entry_ns=signal+2*t.NS,exit_ns=signal+62*t.NS,completed_feature_end_ns=signal-60*t.NS,label_status='ok',base_available_for_entry=True,stress_net_R=float(yy),stress_net_usd=float(yy*risk),normal_net_usd=float(yy*risk+25))
        r.update(dict(zip(t.FEATURES,[risk,.4+np.cos(i),np.sin(i),1+i%3,30.])))
        rows.append(r)
    return rows

def release(role,rows,intents=None):
    intents=rows if intents is None else intents;p=t.DATA/'Private'/f'{role}-candidates.csv';write_csv(p,rows);ip=p.with_name(f'{role}-intents.csv');write_csv(ip,intents);jp=p.with_name(f'{role}-intents.jsonl');jp.write_text(''.join(json.dumps(x)+'\n'for x in intents));lo,hi=t.PERIODS[role]
    m=dict(schema='es-frozen-second-role-release-v1',synthetic=True,role=role,csv_name=p.name,csv_sha256=t.sha(p),row_count=len(rows),day_min=min(x['day']for x in rows),day_max=max(x['day']for x in rows),period_start_inclusive=lo,period_end_exclusive=hi,native_acceptance_sha256=t.sha(t.DATA/'Public/second-native-acceptance.json'),independent_native_audit_sha256=t.sha(t.DATA/'Public/second-independent-audit.json'),generator_source_hashes={'second_kernel.py':t.sha(t.DATA/'Source/second_kernel.py')},generator_source_freeze_sha256=t.sha(t.DATA/'Public/period-source-freeze.json'),known_source_freeze_sha256=t.sha(t.DATA/'Public/second-source-freeze-v2.json'),kernel_sha256=t.sha(t.DATA/'Source/second_kernel.py'),protocol_files=[dict(path=str(t.HERE/'Public'/name),sha256=t.sha(t.HERE/'Public'/name))for name in t.PROTOCOL_NAMES[:3]],intent_csv_name=ip.name,intent_csv_sha256=t.sha(ip),intent_jsonl_sha256=t.sha(jp),intent_row_count=len(intents),intent_semantics='All eligible decision-feature intents in synthetic fixture')
    if role=='sealed':
        pub=t.HERE/'Public/models-frozen-github-receipt.json';m['published_model_receipt']=dict(path=str(pub),sha256=t.sha(pub),required_bundle_sha256=t.sha(t.HERE/'Public/models-frozen.json'))
    dump(p.with_name(f'{role}-release.json'),m);return p

@contextmanager
def fixture(negative=False):
    with tempfile.TemporaryDirectory(prefix='fiveyear-synthetic-') as root:
        t.HERE=Path(root)/'ML';t.DATA=Path(root)/'Data'
        for base in [t.HERE,t.DATA]:
            for folder in ['Public','Private','Source']:(base/folder).mkdir(exist_ok=True,parents=True)
        (t.DATA/'Source/second_kernel.py').write_text('SYNTHETIC frozen kernel, never executed\n');dump(t.DATA/'Public/second-fixtures.json',{'synthetic':True})
        dump(t.DATA/'Public/second-source-freeze-v2.json',dict(sources_sha256={'second_kernel.py':t.sha(t.DATA/'Source/second_kernel.py')},fixtures_sha256=t.sha(t.DATA/'Public/second-fixtures.json')))
        dump(t.DATA/'Public/period-source-freeze.json',{'synthetic':True})
        acceptance=dict(status='PASS',accepted=True,synthetic=True,metrics=dict(native_candidates=347,matches=347,native_recall=1.,second_precision=1.,NettoR_Spearman=1.,stress_profit_sign_agreement=1.,mean_net_R_error_second_minus_native=0.))
        dump(t.DATA/'Public/second-native-acceptance.json',acceptance);dump(t.DATA/'Public/second-independent-audit.json',dict(status='PASS_INDEPENDENT_RAW_PRICE_FILL_AND_METRIC_AUDIT',acceptance_sha256=t.sha(t.DATA/'Public/second-native-acceptance.json'),frozen_sources_and_primary_outputs_unchanged=True,synthetic=True))
        days=[d.date().isoformat()for d in pd.bdate_range('2022-01-03',periods=180)];sealed=[d.date().isoformat()for d in pd.bdate_range('2025-02-03',periods=12)]
        dates={d:dict(status='open',session_open_ns=t.midnight(d)+8*3600*t.NS+30*60*t.NS,session_close_ns=t.midnight(d)+16*3600*t.NS)for d in days+sealed};dump(t.HERE/'Public/calendar-overlay-2021-2025.json',dict(synthetic=True,dates=dates));dump(t.HERE/'Public/calendar-independent-acceptance.json',dict(status='PASS',overlay_sha256=t.sha(t.HERE/'Public/calendar-overlay-2021-2025.json'),synthetic=True))
        for name in t.PROTOCOL_NAMES:(t.HERE/'Public'/name).write_text('SYNTHETIC ONLY '+name+'\n')
        (t.HERE/'Source/test_training_synthetic.py').write_bytes(Path(__file__).read_bytes())
        dump(t.HERE/'Public/training-synthetic-acceptance.json',dict(status='PASS',checks=18,training_source_sha256=t.sha(SCRIPT),fixture_source_sha256=t.sha(__file__),synthetic_datasets_only=True,real_label_files_opened=False,real_models_fit=False,synthetic=True))
        freeze=dict(fixtures_sha256=t.sha(t.HERE/'Public/training-synthetic-acceptance.json'),source_sha256=t.sha(SCRIPT),native_acceptance_sha256=t.sha(t.DATA/'Public/second-native-acceptance.json'),native_independent_audit_sha256=t.sha(t.DATA/'Public/second-independent-audit.json'),native_source_freeze_sha256=t.sha(t.DATA/'Public/second-source-freeze-v2.json'),native_kernel_sha256=t.sha(t.DATA/'Source/second_kernel.py'),calendar_overlay_sha256=t.sha(t.HERE/'Public/calendar-overlay-2021-2025.json'),calendar_independent_acceptance_sha256=t.sha(t.HERE/'Public/calendar-independent-acceptance.json'),features=t.FEATURES,sklearn_version=t.sklearn.__version__,protocol_sha256={n:t.sha(t.HERE/'Public'/n)for n in t.PROTOCOL_NAMES},synthetic=True)
        dump(t.HERE/'Public/training-code-freeze.json',freeze);dump(t.HERE/'Public/training-code-github-receipt.json',dict(published=True,publication_commit='f'*40,published_before_fit=True,training_code_freeze_sha256=t.sha(t.HERE/'Public/training-code-freeze.json'),source_sha256=t.sha(SCRIPT),synthetic=True))
        rows=fixture_rows(days,negative);path=release('development',rows)
        try:yield days,rows,path,sealed
        finally:t.HERE=ORIGINAL_HERE;t.DATA=ORIGINAL_DATA

def rejected(function):
    try:function()
    except t.GuardError:return
    raise AssertionError('Expected explicit guard rejection')
def test(name,fn):
    try:
        with redirect_stdout(io.StringIO()):fn()
        RESULTS.append(dict(name=name,status='PASS'))
    except Exception as error:RESULTS.append(dict(name=name,status='FAIL',error_type=type(error).__name__,error=str(error)));raise

def role_and_metadata():
    with fixture()as(days,rows,p,sealed):
        r,x,y,intents,m=t.load_role(p,'development');assert len(r)==180 and len(intents)==180
        rejected(lambda:t.load_role(p,'sealed'))
        mp=p.with_name('development-release.json');bad=json.loads(mp.read_text());bad['role']='sealed';dump(mp,bad)
        with patch.object(t.csv,'DictReader',side_effect=AssertionError('CSV parser must never be called')):rejected(lambda:t.load_role(p,'development'))

def hash_before_parse():
    with fixture()as(_,_,p,_):
        with p.open('a')as stream:stream.write('TAMPERED\n')
        with patch.object(t.csv,'DictReader',side_effect=AssertionError('No label parse on bad hash')):rejected(lambda:t.load_role(p,'development'))

def chronology_guard():
    with fixture()as(days,rows,p,_):
        rows[0]['signal_ns']=t.midnight('2025-01-02')+9*3600*t.NS;release('development',rows);rejected(lambda:t.load_role(p,'development'))

def feature_clock_guard():
    with fixture()as(_,rows,p,_):
        rows[0]['completed_feature_end_ns']=rows[0]['signal_ns'];release('development',rows);rejected(lambda:t.load_role(p,'development'))

def cost_and_r_guard():
    with fixture()as(_,rows,p,_):
        rows[0]['stress_net_R']+=1;release('development',rows);rejected(lambda:t.load_role(p,'development'))

def hash_integrity():
    with fixture():
        t.release_guard();q=t.DATA/'Source/second_kernel.py';q.write_text(q.read_text()+'mutated');rejected(t.release_guard)
    with fixture():
        q=t.HERE/'Public/training-code-github-receipt.json';o=json.loads(q.read_text());o['published']=False;dump(q,o);rejected(t.release_guard)
    with fixture():
        q=t.HERE/'Public/training-code-freeze.json';o=json.loads(q.read_text());o['source_sha256']='0'*64;dump(q,o);rejected(t.release_guard)

def split_purge():
    with fixture()as(days,rows,_,_):
        rows[0]['exit_ns']=t.midnight(days[-1])+t.NS
        train,gap,cutoff,folds=t.development_design(rows,days);assert 0 not in train and gap==days[-1]
        seen=[]
        for before,test,binding in folds:
            assert set(before).isdisjoint(test);assert max(rows[i]['day']for i in before)<binding['whole_gap_session']<binding['first_test_day'];assert max(rows[i]['exit_ns']for i in before)<min(rows[i]['signal_ns']for i in test);seen.extend(test)
        assert len(seen)==len(set(seen)) and len(folds)==5

def calibration_and_clipping():
    y=np.array([0.,1.,2.]);raw=np.array([100.,101.,102.]);full=np.array([2.,3.,4.]);final=np.array([2.9,3.,3.1]);cal=t.calibrate(y,raw,full,final);assert cal['b']==1 and t.calibrated([3.],cal)[0]==3.
    assert t.calibrate(-y,raw,full,final)['b']==0
    assert t.calibrate(2*y,np.array([1.,2.,3.]),full,final)['b']==1
    assert t.calibrate(y,np.ones(3),full,final)['b']==0

def scaler_and_portable():
    rng=np.random.default_rng(4);x=rng.normal(size=(80,5));x[:,4]=1.;y=.4+x[:,0]+rng.normal(0,.05,80);model=t.estimator('Ridge');model.fit(x[:60],y[:60]);s,r=model.steps[0][1],model.steps[1][1]
    assert np.allclose(s.mean_,x[:60].mean(axis=0));future=x[60:]*1e4;means=s.mean_.copy();model.predict(future);assert np.array_equal(s.mean_,means)
    p=dict(mean=s.mean_.tolist(),scale=s.scale_.tolist(),coef=r.coef_.tolist(),intercept=float(r.intercept_));assert np.max(abs(t.portable_predict(future,p)-model.predict(future)))<1e-9
    assert t.estimator('Ridge').steps[1][1].alpha==10.
    b=t.estimator('Boosting');assert b.max_depth==1 and b.max_iter==100 and not b.early_stopping

def intent_event(key,signal,end=None,y=1.,status='ok'):
    e=dict(case_key=key,signal_ns=signal,day='2025-02-03',label_status=status,stress_net_R=y,stress_net_usd=y*100,normal_net_usd=y*100+25,entry_ns=signal+2*t.NS)
    if status=='ok':e['exit_ns']=end
    elif end is not None:e['entry_cancel_ns']=end
    return e

def causal_reentry():
    n=t.midnight('2025-02-03')+9*3600*t.NS
    events=[intent_event('A',n,n+100*t.NS,-1),intent_event('B',n+20*t.NS,n+40*t.NS,2),intent_event('C',n+110*t.NS,n+130*t.NS,1)]
    base=t.replay_path(events);gate=t.replay_path(events,[-1,1,1]);assert base['selected']==['A','C'] and gate['selected']==['B','C'];assert gate['sum_R']-base['sum_R']==3
    assert gate['omitted_fillable']==['A']

def cancellation_pending():
    n=t.midnight('2025-02-03')+9*3600*t.NS;events=[intent_event('cancel',n,n+30*t.NS,status='cancelled'),intent_event('B',n+10*t.NS,n+20*t.NS,2),intent_event('C',n+40*t.NS,n+60*t.NS,1)]
    base=t.replay_path(events);gate=t.replay_path(events,[-1,1,1]);assert base['selected']==['C'] and gate['selected']==['B','C'];assert not gate['omitted_fillable'] and gate['omitted_cancelled']==['cancel'];assert base['cancelled']==['cancel']
    unresolved=t.replay_path([intent_event('unknown',n,None,status='missing_exit')]);assert not unresolved['complete'] and unresolved['unresolved']==['unknown']

def baseline_parity():
    n=t.midnight('2025-02-03')+9*3600*t.NS;events=[intent_event('cancel',n,n+30*t.NS,status='cancelled'),intent_event('B',n+10*t.NS,n+20*t.NS,2),intent_event('C',n+40*t.NS,n+60*t.NS,1)]
    rows=[dict(events[1],base_available_for_entry=False,normal_net_usd=225),dict(events[2],base_available_for_entry=True,normal_net_usd=125)];proof=t.development_baseline(rows,events);assert proof['nonoverlapping_trades']==1 and proof['frozen_generator_baseline_parity']
    rows[0]['base_available_for_entry']=True;rejected(lambda:t.development_baseline(rows,events))

def economics_qualification():
    days=[d.date().isoformat()for d in pd.bdate_range('2025-02-03',periods=10)];events=[]
    for day in days:
        n=t.midnight(day)+9*3600*t.NS;e=intent_event(day,n,n+100*t.NS,-1);e['day']=day;events.append(e)
    e=t.paired_economics(events,[-1]*10,days,repetitions=29);assert e['delta_sum_R']==10 and e['paired_moving5session_delta_USD_CI95'][0]>0;assert t.qualification(e,.01)=='active_with_research_benefit';assert t.qualification(e,.2)=='active_no_robust_benefit';assert t.qualification(e,.01,False)=='active_descriptive_control_no_primary_selection'
    e['available_path_omitted_fillable']=9;assert t.qualification(e,.01)=='practically_inactive'

def atomic_one_shot():
    with tempfile.TemporaryDirectory(prefix='atomic-synthetic-')as root:
        p=Path(root)/'attempt.json'
        def go(i):
            try:t.atomic_attempt(p,{'synthetic':i});return 'started'
            except t.GuardError:return 'blocked'
        with ThreadPoolExecutor(max_workers=2)as pool:result=list(pool.map(go,[1,2]))
        assert sorted(result)==['blocked','started'] and p.exists();rejected(lambda:t.atomic_attempt(p,{}))

def failed_eval_consumes_lock():
    with fixture():
        frozen={};receipt=dict(publication_commit='f'*40)
        with patch.object(t,'release_guard',return_value=({},{})),patch.object(t,'model_publication_guard',return_value=(frozen,receipt)),patch.object(t,'load_role',side_effect=t.GuardError('Synthetic deliberate post-lock failure'))as loader:
            t.save(t.HERE/'Public/models-frozen.json',{'synthetic':True})
            rejected(lambda:t.evaluate(SimpleNamespace(input='never_opened')));assert(t.HERE/'Private/final-evaluation-attempt.json').exists();assert loader.call_count==1
            rejected(lambda:t.evaluate(SimpleNamespace(input='never_opened')));assert loader.call_count==1
            assert t.read(t.HERE/'Public/final-evaluation-attempt-status.json')['state']=='FAILED_ATTEMPT_CONSUMED_NO_AUTOMATIC_RETRY'

def futility_no_fit_or_unseal():
    with fixture(negative=True)as(_,_,p,_):
        with patch.object(t,'estimator',side_effect=AssertionError('No model fitting permitted under futility')):t.fit(SimpleNamespace(input=str(p)))
        assert(t.HERE/'Public/futility-stop.json').exists() and not(t.HERE/'Public/models-frozen.json').exists();rejected(t.model_publication_guard)if(t.HERE/'Public/models-frozen.json').exists()else None

def permutation_all_immovable():
    score=np.array([.1,.4,.8]);y=np.array([0.,1.,2.]);rows=[dict(day='2025-01-02'),dict(day='2025-04-02'),dict(day='2025-07-02')];rho,p,imm=t.conditional_permutation(score,y,rows,repetitions=19);assert p==1 and imm==1 and rho==1

def synthetic_fit_and_final_pipeline():
    with fixture()as(days,rows,p,sealed):
        observed=[];original=t.StandardScaler.fit
        def recorded(self,x,y=None,**kwargs):
            answer=original(self,x,y,**kwargs);observed.append(self.mean_.copy());return answer
        with patch.object(t.StandardScaler,'fit',new=recorded):t.fit(SimpleNamespace(input=str(p)))
        train,gap,cutoff,folds=t.development_design(rows,days);x=t.feature_matrix(rows);expected=[x[b].mean(axis=0)for b,_,_ in folds]+[x[train].mean(axis=0)];assert len(observed)==len(expected) and all(np.allclose(a,b)for a,b in zip(observed,expected))
        frozen=t.read(t.HERE/'Public/models-frozen.json');assert frozen['training_mean_R']>0 and frozen['sealed_labels_read']is False
        pub=t.HERE/'Public/models-frozen-github-receipt.json';dump(pub,dict(published=True,publication_commit='e'*40,published_before_final_labels=True,models_frozen_sha256=t.sha(t.HERE/'Public/models-frozen.json'),model_bundle=dict(path=str(t.HERE/'Public/models-frozen.json'),sha256=t.sha(t.HERE/'Public/models-frozen.json')),synthetic=True))
        q=release('sealed',fixture_rows(sealed));t.model_publication_guard();t.evaluate(SimpleNamespace(input=str(q)));result=t.read(t.HERE/'Public/final-results.json');assert result['state']=='one_shot_sealed_final_evaluated' and result['no_payout_or_native_gate'];rejected(lambda:t.evaluate(SimpleNamespace(input=str(q))));rejected(lambda:t.fit(SimpleNamespace(input=str(p))))
        artifact=t.HERE/'Private/Ridge.joblib'
        with artifact.open('ab')as stream:stream.write(b'tamper')
        rejected(t.model_publication_guard)

def main():
    tests=[('separate_role_manifest_before_parse',role_and_metadata),('changed_csv_hash_stops_before_parser',hash_before_parse),('actual_signal_day_and_role_consistency',chronology_guard),('completed_feature_clock_past_only',feature_clock_guard),('frozen_cost_and_R_label_normalization',cost_and_r_guard),('source_audit_and_publication_integrity',hash_integrity),('five_causal_folds_whole_gap_and_final_exit_purge',split_purge),('OOF_slope_final_TRAIN_centering_and_clipping',calibration_and_clipping),('train_only_scaling_and_portable_Ridge_parity',scaler_and_portable),('gate_releases_later_candidate_causally',causal_reentry),('pending_cancellation_blocks_and_unknown_stops',cancellation_pending),('complete_intent_baseline_matches_generator_flags',baseline_parity),('paired_session_economics_and_fixed_qualification',economics_qualification),('exclusive_durable_attempt_concurrency_guard',atomic_one_shot),('failure_cannot_reopen_sealed_set',failed_eval_consumes_lock),('development_futility_blocks_fitting_and_unsealing',futility_no_fit_or_unseal),('immovable_permutation_is_p1_not_false_significance',permutation_all_immovable),('synthetic_only_complete_fit_publication_final_pipeline',synthetic_fit_and_final_pipeline)]
    for name,fn in tests:test(name,fn)
    proof=dict(schema='ES-FIVEYEAR-TRAINING-SYNTHETIC-AUDIT-1',status='PASS',utc=t.stamp(),checks=len(RESULTS),tests=RESULTS,training_source_sha256=t.sha(SCRIPT),fixture_source_sha256=t.sha(__file__),sklearn_version=t.sklearn.__version__,synthetic_datasets_only=True,real_label_files_opened=False,real_models_fit=False,real_sealed_labels_opened=False,network_calls=0)
    p=ORIGINAL_HERE/'Public/training-synthetic-acceptance.json';t.save(p,proof);print(json.dumps(dict(status=proof['status'],checks=proof['checks'],source_sha256=proof['training_source_sha256'],proof_sha256=t.sha(p)),indent=2))
if __name__=='__main__':main()
