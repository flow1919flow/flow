"""Fixed five-year Ridge research with pre-parse release and one-shot guards.

No acquisition, trading, search or provider cash model. All real fitting requires
published source/protocol hashes plus an independently audited native1s PASS.
Only separately released development files are opened before model publication.
"""
from pathlib import Path
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import argparse,csv,hashlib,io,json,math,os,re,sys
import numpy as np
import sklearn,joblib
from scipy.stats import rankdata,spearmanr
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

HERE=Path(__file__).resolve().parents[1]
DATA=HERE.parent/'ES-FiveYear-SecondData-20261121'
FEATURES=['feature_stop_risk_usd','feature_target_path_R','feature_signed_completed_ema_slope_atr','feature_completed_relative_volume20','feature_chicago_session_minute']
PERIODS={'development':('2021-11-24','2024-11-24'),'sealed':('2024-11-24','2025-11-24'),'known':('2025-11-24','2026-10-31')}
PROTOCOL_NAMES=['preregister-seconds-v2.json','preregister-seconds-v2-addendum.json','preregister-seconds-native-clarifications.json','training-preregister-amendment.json']
SEED=20261121;CT=ZoneInfo('America/Chicago');NS=1_000_000_000

class GuardError(ValueError):pass
def require(value,message):
    if not value:raise GuardError(message)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n');tmp.replace(p)
def stamp():return datetime.now(timezone.utc).isoformat()
def day_of(n):return datetime.fromtimestamp(int(n)//NS,timezone.utc).astimezone(CT).date().isoformat()
def midnight(day):return int(datetime.fromisoformat(day).replace(tzinfo=CT).timestamp())*NS
def boolean(value):
    if value is True or str(value).lower()=='true':return True
    if value is False or str(value).lower()=='false':return False
    raise GuardError('Missing or invalid explicit boolean')
def publication(receipt):
    require(receipt.get('published') is True,'Publication has not been verified')
    require(re.fullmatch('[0-9a-f]{40}',str(receipt.get('publication_commit',''))) is not None,'Missing exact publication commit')

def release_guard():
    acceptance_path=DATA/'Public/second-native-acceptance.json';audit_path=DATA/'Public/second-independent-audit.json'
    check=read(acceptance_path);m=check['metrics']
    require(check['status']=='PASS' and check['accepted'] is True,'Native acceptance failed or incomplete: NO FIT')
    require(m['native_candidates']==347 and m['matches']>=100,'Wrong native denominator or sample')
    require(m['native_recall']>=.7 and m['second_precision']>=.7,'Native candidate acceptance failed')
    require(m['NettoR_Spearman']>=.6 and m['stress_profit_sign_agreement']>=.75,'Native label agreement failed')
    require(abs(m['mean_net_R_error_second_minus_native'])<=.05,'Native mean R error failed')
    audit=read(audit_path)
    require(audit.get('status')=='PASS_INDEPENDENT_RAW_PRICE_FILL_AND_METRIC_AUDIT','Independent native audit missing')
    require(audit.get('acceptance_sha256')==sha(acceptance_path) and audit.get('frozen_sources_and_primary_outputs_unchanged') is True,'Independent audit does not bind unchanged acceptance')
    nativefreeze_path=DATA/'Public/second-source-freeze-v2.json';nativefreeze=read(nativefreeze_path)
    for name,digest in nativefreeze['sources_sha256'].items():require(sha(DATA/'Source'/name)==digest,'Known native source changed: '+name)
    require(sha(DATA/'Public/second-fixtures.json')==nativefreeze['fixtures_sha256'],'Known fixtures changed')
    calpath=HERE/'Public/calendar-independent-acceptance.json';overlaypath=HERE/'Public/calendar-overlay-2021-2025.json';cal=read(calpath)
    require(cal['status']=='PASS' and sha(overlaypath)==cal['overlay_sha256'],'Calendar audit not bound')
    freeze_path=HERE/'Public/training-code-freeze.json';freeze=read(freeze_path)
    expected={'source_sha256':sha(__file__),'native_acceptance_sha256':sha(acceptance_path),'native_independent_audit_sha256':sha(audit_path),'native_source_freeze_sha256':sha(nativefreeze_path),'native_kernel_sha256':sha(DATA/'Source/second_kernel.py'),'calendar_overlay_sha256':sha(overlaypath),'calendar_independent_acceptance_sha256':sha(calpath)}
    for key,digest in expected.items():require(freeze.get(key)==digest,'Training freeze binding missing/changed: '+key)
    fixtures_path=HERE/'Public/training-synthetic-acceptance.json';fixtures=read(fixtures_path)
    require(freeze.get('fixtures_sha256')==sha(fixtures_path) and fixtures.get('status')=='PASS' and fixtures.get('checks',0)>=18,'Frozen synthetic acceptance missing or changed')
    require(fixtures.get('training_source_sha256')==sha(__file__) and fixtures.get('fixture_source_sha256')==sha(HERE/'Source/test_training_synthetic.py'),'Synthetic fixtures do not bind current source')
    require(fixtures.get('synthetic_datasets_only') is True and fixtures.get('real_label_files_opened') is False and fixtures.get('real_models_fit') is False,'Fixture proof must not have used research labels')
    require(freeze.get('features')==FEATURES,'Training feature order changed')
    require(freeze.get('sklearn_version')==sklearn.__version__,'Training library version changed')
    protocols=freeze.get('protocol_sha256',{})
    require(set(protocols)==set(PROTOCOL_NAMES),'All preregistration and pre-fit amendment bindings required')
    for name in PROTOCOL_NAMES:require(sha(HERE/'Public'/name)==protocols[name],'Frozen protocol changed: '+name)
    published=read(HERE/'Public/training-code-github-receipt.json');publication(published)
    require(published.get('published_before_fit') is True and published.get('training_code_freeze_sha256')==sha(freeze_path) and published.get('source_sha256')==sha(__file__),'Source/guard freeze lacks before-fit publication proof')
    return check,freeze

def verify_release_manifest(path,role):
    """Check role/path/date/hash and provenance metadata BEFORE CSV parsing."""
    require(role in PERIODS,'Unknown role');path=Path(path).resolve();expected=(DATA/'Private'/f'{role}-candidates.csv').resolve()
    require(path==expected,'Only canonical separately released role CSV is allowed')
    manifest_path=path.with_name(f'{role}-release.json');manifest_bytes=manifest_path.read_bytes();m=json.loads(manifest_bytes);m['_release_sha256']=hashlib.sha256(manifest_bytes).hexdigest();low,high=PERIODS[role]
    require(m.get('schema')=='es-frozen-second-role-release-v1' and m.get('role')==role,'Wrong role release schema')
    require(m.get('csv_name')==path.name and m.get('period_start_inclusive')==low and m.get('period_end_exclusive')==high,'Wrong released file/date range')
    require(isinstance(m.get('row_count'),int) and m['row_count']>0 and low<=m.get('day_min','')<=m.get('day_max','')<high,'Bad pre-parse release bounds/count')
    for key,file in [('native_acceptance_sha256',DATA/'Public/second-native-acceptance.json'),('independent_native_audit_sha256',DATA/'Public/second-independent-audit.json')]:require(m.get(key)==sha(file),'Role release native proof changed: '+key)
    source_bindings=m.get('generator_source_hashes',{})
    require(source_bindings and 'second_kernel.py' in source_bindings,'Role release has no frozen generator/kernel binding')
    for name,digest in source_bindings.items():
        require(Path(name).name==name,'Generator binding must be a local source basename')
        require(sha(DATA/'Source'/name)==digest,'Released generator changed: '+name)
    require(m.get('generator_source_freeze_sha256')==sha(DATA/'Public/period-source-freeze.json'),'Role period source freeze changed')
    supplied={Path(b['path']).resolve():b['sha256'] for b in m.get('protocol_files',[])}
    for name in PROTOCOL_NAMES[:3]:
        p=(HERE/'Public'/name).resolve();require(supplied.get(p)==sha(p),'Role published protocol not bound: '+name)
    intents_path=path.with_name(f'{role}-intents.csv')
    require(m.get('intent_csv_name')==intents_path.name and bool(m.get('intent_semantics')),'Complete intent stream is mandatory')
    require(isinstance(m.get('intent_row_count'),int) and m['intent_row_count']>=m['row_count'],'Invalid intent release count')
    if role=='sealed':
        binding=m.get('published_model_receipt',{});pubpath=(HERE/'Public/models-frozen-github-receipt.json').resolve()
        require(Path(binding.get('path','')).resolve()==pubpath and binding.get('sha256')==sha(pubpath),'Sealed release used a different publication receipt')
        require(binding.get('required_bundle_sha256')==sha(HERE/'Public/models-frozen.json'),'Sealed release used different frozen weights')
    # Opaque bytes are hashed, not interpreted, until every metadata guard passes.
    body=path.read_bytes();intent_csv_body=intents_path.read_bytes();intent_body=path.with_name(f'{role}-intents.jsonl').read_bytes()
    require(hashlib.sha256(body).hexdigest()==m.get('csv_sha256'),'Released role CSV hash mismatch; labels not parsed')
    require(hashlib.sha256(intent_csv_body).hexdigest()==m.get('intent_csv_sha256'),'Released intent stream hash mismatch; labels not parsed')
    require(hashlib.sha256(intent_body).hexdigest()==m.get('intent_jsonl_sha256'),'Canonical intent JSONL hash mismatch; labels not parsed')
    require(m.get('known_source_freeze_sha256')==sha(DATA/'Public/second-source-freeze-v2.json') and m.get('kernel_sha256')==sha(DATA/'Source/second_kernel.py'),'Released native source/kernel proof changed')
    return m,body,intent_body

def validate_clock(row,role,filled=False):
    low,high=PERIODS[role];signal=int(row['signal_ns'])
    require(low<=row['day']<high and day_of(signal)==row['day'],'Role day is inconsistent with real decision clock')
    if filled:
        entry,exit=int(row['entry_ns']),int(row['exit_ns'])
        require(exit>=entry>=signal+2*NS,'Invalid causal market execution clocks')
        require(day_of(entry)==row['day'] and day_of(exit)==row['day'],'Unexpected cross-session label must be resolved before training')
    require(int(row['completed_feature_end_ns'])<=signal-NS,'Completed-bar feature was not known before current second')
    return signal

def feature_matrix(rows):
    x=np.array([[float(r[k]) for k in FEATURES]for r in rows],float)
    require(x.shape==(len(rows),len(FEATURES)) and np.isfinite(x).all() and (x[:,0]>0).all(),'Invalid causal feature matrix')
    return x

def load_role(path,role):
    m,body,intent_body=verify_release_manifest(path,role)
    rows=list(csv.DictReader(io.StringIO(body.decode('utf-8'))));intents=[json.loads(line) for line in intent_body.decode('utf-8').splitlines() if line]
    require(len(rows)==m['row_count'] and len(intents)==m['intent_row_count'],'Released counts changed')
    require(rows and min(r['day']for r in rows)==m['day_min'] and max(r['day']for r in rows)==m['day_max'],'Released row bounds differ')
    rows.sort(key=lambda r:(int(r['signal_ns']),r['case_key']));intents.sort(key=lambda r:(int(r['signal_ns']),r['case_key']))
    require(len({r['case_key']for r in rows})==len(rows) and len({r['case_key']for r in intents})==len(intents),'Duplicate released opportunity ID')
    require(len({(r['contract'],r['signal_ns'],r['side'])for r in intents})==len(intents),'Duplicated economic opportunity under another ID')
    for r in rows:validate_clock(r,role,True)
    for r in intents:validate_clock(r,role,False)
    x=feature_matrix(rows);feature_matrix(intents);y=np.array([float(r['stress_net_R'])for r in rows],float)
    net=np.array([[float(r['normal_net_usd']),float(r['stress_net_usd'])]for r in rows]);require(np.isfinite(y).all() and np.isfinite(net).all(),'Invalid training label')
    require(np.allclose(y,net[:,1]/x[:,0],rtol=1e-10,atol=1e-10) and np.allclose(net[:,0]-net[:,1],25.,rtol=0,atol=1e-7),'Role label risk/cost normalization differs from frozen definition')
    lookup={r['case_key']:r for r in rows};seen=set()
    for event in intents:
        if event['label_status']=='ok':
            key=event['case_key'];require(key in lookup,'Filled intent absent from released labels');seen.add(key);row=lookup[key]
            for field in ['day','contract','side','signal_ns']:require(str(event[field])==str(row[field]),'Intent identity differs from label')
            require(np.array_equal(feature_matrix([event]),feature_matrix([row])),'Intent features differ from frozen candidate features')
            event.update({k:row[k] for k in ['entry_ns','exit_ns','stress_net_R','stress_net_usd','normal_net_usd']})
        else:require(event['case_key'] not in lookup,'Cancelled intent incorrectly has a filled label')
    require(seen==set(lookup),'Incomplete filled opportunity stream')
    return rows,x,y,intents,m

def load_csv(path,role):
    rows,x,y,_,_=load_role(path,role);return rows,x,y

def estimator(name):
    if name=='Ridge':return make_pipeline(StandardScaler(),Ridge(alpha=10.,solver='svd'))
    require(name=='Boosting','Unknown prespecified model')
    return HistGradientBoostingRegressor(max_depth=1,learning_rate=.05,max_iter=100,min_samples_leaf=20,l2_regularization=1.,early_stopping=False,random_state=SEED)

def calendar_days(role='development'):
    low,high=PERIODS[role];c=read(HERE/'Public/calendar-overlay-2021-2025.json')
    return sorted(d for d,r in c['dates'].items() if r['status']=='open' and r.get('session_open_ns') is not None and r.get('session_close_ns',0)>r['session_open_ns'] and low<=d<high)

def development_design(rows,days):
    require(len(days)>132,'Too few prespecified calendar sessions')
    require(all(r['day'] in set(days)for r in rows),'Candidate has no audited open session')
    gapday=days[-1];cutoff=midnight(gapday)
    train=np.array([i for i,r in enumerate(rows) if r['day']<gapday and int(r['exit_ns'])<cutoff],int)
    require(len(train)>=30,'Insufficient causal final training cases')
    blocks=[list(z) for z in np.array_split(np.array(days[:-1][127:],object),5)];require(all(blocks),'Empty session fold')
    folds=[]
    for number,block in enumerate(blocks):
        firstpos=days.index(block[0]);eligible=set(days[:firstpos-1]);test=np.array([i for i in train if rows[i]['day'] in set(block)],int)
        require(len(test)>0,'Empty chronological fold; do not silently skip')
        firstsignal=min(int(rows[i]['signal_ns'])for i in test)
        before=np.array([i for i in train if rows[i]['day'] in eligible and int(rows[i]['exit_ns'])<firstsignal],int)
        require(len(before)>=30,'Insufficient purged fold training')
        folds.append((before,test,dict(fold=number,train_n=len(before),test_n=len(test),first_test_day=block[0],last_test_day=block[-1],whole_gap_session=days[firstpos-1],max_training_exit_ns=max(int(rows[i]['exit_ns'])for i in before),min_test_signal_ns=firstsignal)))
    return train,gapday,cutoff,folds

def calibrate(y,raw,full_train_y,final_train_raw):
    center=float(np.mean(raw));variance=float(np.sum((raw-center)**2))
    b=float(np.clip(np.sum((y-y.mean())*(raw-center))/variance,0,1)) if variance>0 else 0.
    a=float(np.mean(full_train_y));finalcenter=float(np.mean(final_train_raw))
    return dict(a=a,b=b,final_training_prediction_mean=finalcenter,cross_prediction_mean_diagnostic=center,gate_inactive_nonpositive_training_mean=bool(a<=0),centering='Final-model TRAIN prediction mean, not OOF mean; no sealed observations')

def calibrated(raw,cal):return cal['a']+cal['b']*(np.asarray(raw,float)-cal['final_training_prediction_mean'])

def portable_predict(x,portable):
    return ((np.asarray(x,float)-np.array(portable['mean']))/np.array(portable['scale']))@np.array(portable['coef'])+portable['intercept']

def replay_path(intents,scores=None):
    """Causal one-position/pending-order path; current scores, no future choice."""
    require(scores is None or len(scores)==len(intents),'Forecast/intent mismatch')
    busy_until=-1;selected=[];omitted=[];omitted_cancelled=[];blocked=[];cancelled=[];unresolved=[];daily={}
    for i,e in enumerate(intents):
        signal=int(e['signal_ns']);key=e['case_key']
        if signal<busy_until:blocked.append(key);continue
        if scores is not None and float(scores[i])<0:
            (omitted if e['label_status']=='ok' else omitted_cancelled).append(key);continue
        if e['label_status']=='ok':
            require(int(e['entry_ns'])>=signal+2*NS and int(e['exit_ns'])>=int(e['entry_ns']),'Invalid filled intent clocks')
            selected.append(key);busy_until=int(e['exit_ns']);a=daily.setdefault(e['day'],dict(R=0.,USD=0.,normal_USD=0.));a['R']+=float(e['stress_net_R']);a['USD']+=float(e['stress_net_usd']);a['normal_USD']+=float(e['normal_net_usd'])
        else:
            value=e.get('entry_cancel_ns')
            if value not in [None,'','None','nan']:
                cancel=int(value);require(cancel>=signal,'Cancellation precedes intent');busy_until=cancel;cancelled.append(key)
            else:
                unresolved.append(key);break # Unknown actual pending/position end; do not invent a clock.
    return dict(selected=selected,omitted_fillable=omitted,omitted_cancelled=omitted_cancelled,blocked=blocked,cancelled=cancelled,unresolved=unresolved,complete=not unresolved,daily=daily,sum_R=float(sum(v['R']for v in daily.values())),sum_USD=float(sum(v['USD']for v in daily.values())),sum_normal_USD=float(sum(v['normal_USD']for v in daily.values())))

def development_baseline(rows,intents):
    path=replay_path(intents);flagged=[r['case_key']for r in rows if boolean(r['base_available_for_entry'])]
    require(path['complete'] and path['selected']==flagged,'Complete-intent ungated replay does not equal frozen generator baseline')
    selected={r['case_key']:r for r in rows};values=np.array([float(selected[k]['stress_net_usd'])for k in path['selected']]);equity=np.r_[0.,np.cumsum(values)];dd=np.maximum.accumulate(equity)-equity
    return dict(scope='Causal one-position and pending-cancellation research path; same complete intent stream, no prop-account/payout model.',total_unique_shadow_candidates=len(rows),total_decision_intents=len(intents),nonoverlapping_trades=len(path['selected']),stress_sum_R=path['sum_R'],stress_net_usd=path['sum_USD'],normal_net_usd=float(sum(float(selected[k]['normal_net_usd'])for k in path['selected'])),maximum_closed_trade_drawdown_usd=float(dd.max()),profit_factor=float(values[values>0].sum()/-values[values<0].sum())if(values<0).any()else None,frozen_generator_baseline_parity=True,older_data_status='Development only; sealed labels not read.',computed_before_model_fit_utc=stamp())

def atomic_attempt(path,record):
    """Durable exclusive marker BEFORE any sealed bytes are opened; no retry."""
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    try:
        with p.open('x') as f:f.write(json.dumps(record,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
    except FileExistsError:raise GuardError('Attempt already started or completed; no automatic retry/concurrent opening')
    descriptor=os.open(p.parent,os.O_RDONLY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)
    return p

def model_publication_guard():
    frozenpath=HERE/'Public/models-frozen.json';frozen=read(frozenpath);receipt=read(HERE/'Public/models-frozen-github-receipt.json');publication(receipt)
    require(receipt.get('models_frozen_sha256')==sha(frozenpath) and receipt.get('published_before_final_labels') is True,'Frozen models lack before-label publication proof')
    bundle=receipt.get('model_bundle',{});require(Path(bundle.get('path','')).resolve()==frozenpath.resolve() and bundle.get('sha256')==sha(frozenpath),'Published exact weights/preprocessing bundle is not bound')
    require(frozen.get('source_sha256')==sha(__file__) and frozen.get('training_mean_R',0)>0 and frozen.get('sealed_labels_read') is False,'Invalid model source or development futility forbids unsealing')
    require(not(HERE/'Public/futility-stop.json').exists(),'Development futility forbids final opening')
    require(frozen.get('training_code_freeze_sha256')==sha(HERE/'Public/training-code-freeze.json'),'Model source freeze changed')
    for name in ['Ridge','Boosting']:
        require(sha(HERE/'Private'/f'{name}.joblib')==frozen['models'][name]['model_sha256'] and sha(HERE/'Private'/f'{name}-state.json')==frozen['models'][name]['state_sha256'],'Frozen fitted model/state changed')
    return frozen,receipt

def fit(args):
    _,freeze=release_guard();require(not(HERE/'Public/models-frozen.json').exists(),'No refit after models frozen')
    require(not(HERE/'Private/final-evaluation-attempt.json').exists(),'No fit after any sealed evaluation attempt')
    atomic_attempt(HERE/'Private/training-attempt.json',dict(state='started_before_development_open',utc=stamp(),source_sha256=sha(__file__)))
    rows,x,y,intents,release=load_role(args.input,'development');days=calendar_days();baseline=development_baseline(rows,intents);save(HERE/'Public/development-strategy-baseline.json',baseline)
    train,gapday,cutoff,folds=development_design(rows,days);a=float(np.mean(y[train]))
    if a<=0:
        proof=dict(state='STOP_DEVELOPMENT_FUTILITY_NO_FINAL_UNSEAL',utc=stamp(),training_mean_R=a,training_cases=len(train),source_sha256=sha(__file__),development_csv_sha256=release['csv_sha256'],models_fit=False,sealed_labels_opened=False,baseline=baseline)
        save(HERE/'Public/futility-stop.json',proof);print(json.dumps(proof));return
    summaries={};bindings={};portable={}
    with threadpool_limits(limits=1):
        for name in ['Ridge','Boosting']:
            out=[];foldproof=[]
            for before,test,binding in folds:
                model=estimator(name);model.fit(x[before],y[before]);pred=model.predict(x[test]);out.extend((int(i),float(v))for i,v in zip(test,pred));foldproof.append(binding)
            ids=np.array([i for i,_ in out],int);cross=np.array([v for _,v in out]);require(len(set(ids))==len(ids) and np.isfinite(cross).all(),'OOF overlap or nonfinite prediction')
            model=estimator(name);model.fit(x[train],y[train]);final_train_raw=model.predict(x[train]);cal=calibrate(y[ids],cross,y[train],final_train_raw)
            artifact=HERE/'Private'/f'{name}.joblib';joblib.dump(model,artifact)
            state=dict(model=name,features=FEATURES,calibration=cal,training_cases=len(train),training_csv_sha256=release['csv_sha256'],training_release_sha256=release['_release_sha256'],source_sha256=sha(__file__),folds=foldproof,sklearn_version=sklearn.__version__,created_utc=stamp())
            if name=='Ridge':
                scale,ridge=model.steps[0][1],model.steps[1][1];p=dict(mean=scale.mean_.tolist(),scale=scale.scale_.tolist(),coef=ridge.coef_.tolist(),intercept=float(ridge.intercept_))
                err=float(np.max(np.abs(portable_predict(x[train],p)-model.predict(x[train]))));require(err<1e-10,'Portable Ridge reconstruction failed')
                state.update(portable_linear_model=p,maximum_portable_reconstruction_error=err);portable[name]=dict(features=FEATURES,linear_model=p,calibration=cal)
            save(HERE/'Private'/f'{name}-state.json',state);save(HERE/'Private'/f'{name}-cross-predictions.json',[dict(case_key=rows[i]['case_key'],raw_prediction=v,y=float(y[i]))for i,v in out])
            summaries[name]={k:state[k]for k in ['training_cases','calibration','folds','sklearn_version']};bindings[name]=dict(model_sha256=sha(artifact),state_sha256=sha(HERE/'Private'/f'{name}-state.json'))
    proof=dict(state='models_frozen_before_final_labels',frozen_at_utc=stamp(),source_sha256=sha(__file__),training_code_freeze_sha256=sha(HERE/'Public/training-code-freeze.json'),development_csv_sha256=release['csv_sha256'],development_intents_sha256=release['intent_jsonl_sha256'],excluded_final_gap_session=gapday,final_train_label_exit_cutoff_ns=cutoff,training_mean_R=a,models=bindings,portable_models=portable,summaries=summaries,sealed_labels_read=False,no_payout_or_native_gate=True)
    save(HERE/'Public/models-frozen.json',proof);print(json.dumps(dict(state=proof['state'],training_cases=len(train),frozen_sha256=sha(HERE/'Public/models-frozen.json'))))

def conditional_permutation(score,y,rows,repetitions=1999):
    if np.ptp(score)==0 or np.ptp(y)==0:return None,None,None
    byday={}
    for i,r in enumerate(rows):byday.setdefault(r['day'],[]).append(i)
    strata={}
    for day,ix in byday.items():strata.setdefault((day[:4],(int(day[5:7])-1)//3,len(ix)),[]).append(ix)
    immovable=sum(len(g[0])for g in strata.values()if len(g)==1)/len(y)
    a=rankdata(score);a-=a.mean();b=rankdata(y);b-=b.mean();den=float(np.sqrt(np.dot(a,a)*np.dot(b,b)));observed=float(np.dot(a,b)/den)
    rng=np.random.default_rng(SEED);exceed=0
    for _ in range(repetitions):
        bb=b.copy()
        for groups in strata.values():
            for ix,j in zip(groups,rng.permutation(len(groups))):bb[ix]=b[groups[int(j)]]
        exceed+=float(np.dot(a,bb)/den)>=observed-1e-12
    return observed,(1+exceed)/(repetitions+1),immovable

def paired_economics(intents,scores,days,repetitions=1999):
    base=replay_path(intents);gate=replay_path(intents,scores);rdelta=gate['sum_R']-base['sum_R'];udelta=gate['sum_USD']-base['sum_USD']
    result=dict(complete=base['complete'] and gate['complete'],ungated_trades=len(base['selected']),gated_trades=len(gate['selected']),available_path_omitted_fillable=len(gate['omitted_fillable']),omitted_cancelled_intents=len(gate['omitted_cancelled']),all_available_intents_omitted=len(gate['omitted_fillable'])+len(gate['omitted_cancelled']),newly_available_trades=len(set(gate['selected'])-set(base['selected'])),ungated_sum_R=base['sum_R'],gated_sum_R=gate['sum_R'],delta_sum_R=rdelta,ungated_sum_USD=base['sum_USD'],gated_sum_USD=gate['sum_USD'],delta_sum_USD=udelta,ungated_sum_normal_USD=base['sum_normal_USD'],gated_sum_normal_USD=gate['sum_normal_USD'],delta_sum_normal_USD=gate['sum_normal_USD']-base['sum_normal_USD'],unresolved_ungated=len(base['unresolved']),unresolved_gated=len(gate['unresolved']),paired_moving5session_delta_R_CI95=None,paired_moving5session_delta_USD_CI95=None)
    if not result['complete']:return result
    require(len(days)>=5 and all(e['day']in set(days)for e in intents),'Economic path missing audited calendar sessions')
    dr=np.array([gate['daily'].get(d,{}).get('R',0.)-base['daily'].get(d,{}).get('R',0.)for d in days]);du=np.array([gate['daily'].get(d,{}).get('USD',0.)-base['daily'].get(d,{}).get('USD',0.)for d in days]);rng=np.random.default_rng(SEED);samples=[]
    for _ in range(repetitions):
        starts=rng.integers(0,len(days)-4,size=math.ceil(len(days)/5));ix=np.array([j for s in starts for j in range(s,s+5)][:len(days)],int);samples.append((float(dr[ix].sum()),float(du[ix].sum())))
    ci=np.quantile(np.array(samples),[.025,.975],axis=0);result.update(paired_moving5session_delta_R_CI95=ci[:,0].tolist(),paired_moving5session_delta_USD_CI95=ci[:,1].tolist(),paired_bootstrap_draws=repetitions)
    return result

def qualification(econ,p,primary=True):
    if econ['available_path_omitted_fillable']<10:return 'practically_inactive'
    if not primary:return 'active_descriptive_control_no_primary_selection'
    good=econ['complete'] and p is not None and p<=.05 and econ['delta_sum_R']>0 and econ['paired_moving5session_delta_USD_CI95'] is not None and econ['paired_moving5session_delta_USD_CI95'][0]>0
    return 'active_with_research_benefit'if good else'active_no_robust_benefit'

def evaluate(args):
    release_guard();frozen,publication_receipt=model_publication_guard();target=HERE/'Public/final-results.json';require(not target.exists(),'Final evaluation is one shot')
    marker=atomic_attempt(HERE/'Private/final-evaluation-attempt.json',dict(state='started_before_any_sealed_bytes',utc=stamp(),models_frozen_sha256=sha(HERE/'Public/models-frozen.json'),publication_commit=publication_receipt['publication_commit'],source_sha256=sha(__file__)))
    try:
        rows,x,y,intents,release=load_role(args.input,'sealed');all_days=calendar_days('sealed');require(all(r['day']in set(all_days)for r in rows),'Sealed cases lack audited open dates');eventx=feature_matrix(intents);result={}
        with threadpool_limits(limits=1):
            for name in ['Ridge','Boosting']:
                model=joblib.load(HERE/'Private'/f'{name}.joblib');state=read(HERE/'Private'/f'{name}-state.json');require(state['features']==FEATURES,'Frozen feature order changed');raw=model.predict(x);score=calibrated(raw,state['calibration']);eventscore=calibrated(model.predict(eventx),state['calibration']);require(np.isfinite(score).all() and np.isfinite(eventscore).all(),'Nonfinite heldout predictions')
                take=score>=0;rho=float(spearmanr(score,y).statistic)if np.ptp(score)>0 and np.ptp(y)>0 else None;p=None;immovable=None
                if name=='Ridge':rho,p,immovable=conditional_permutation(score,y,rows)
                econ=paired_economics(intents,eventscore,all_days)
                baseflags=[r['case_key']for r in rows if boolean(r['base_available_for_entry'])];require(replay_path(intents)['selected']==baseflags,'Sealed complete-intent ungated path differs from frozen baseline')
                omitted_set=set(replay_path(intents,eventscore)['omitted_fillable']);omitted_y=[float(r['stress_net_R'])for r in rows if r['case_key']in omitted_set]
                record=dict(cases=len(y),unique_days=len({r['day']for r in rows}),primary_model=name=='Ridge',spearman_calibrated_prediction_vs_stress_net_R=rho,one_sided_conditional_session_permutation_p=p,immovable_case_fraction=immovable,shadow_omitted=int((~take).sum()),shadow_taken=int(take.sum()),mean_stress_R_ungated=float(y.mean()),mean_stress_R_shadow_taken=float(y[take].mean())if take.any()else None,mean_stress_R_available_path_omitted=float(np.mean(omitted_y))if omitted_y else None,calibration=state['calibration'],economics=econ,qualification=qualification(econ,p,name=='Ridge'),model_selection_from_final_set=False)
                day_indices={d:np.array([i for i,r in enumerate(rows)if r['day']==d],int)for d in all_days};rng=np.random.default_rng(SEED);samples=[]
                for _ in range(1999):
                    starts=rng.integers(0,len(all_days)-4,size=math.ceil(len(all_days)/5));sampled=[all_days[j]for s in starts for j in range(s,s+5)][:len(all_days)];ix=np.concatenate([day_indices[d]for d in sampled])
                    if len(ix)>2 and np.ptp(score[ix])>0 and np.ptp(y[ix])>0:samples.append(float(spearmanr(score[ix],y[ix]).statistic))
                record['descriptive_moving5session_rho_CI95']=np.quantile(samples,[.025,.975]).tolist()if samples else None;record['bootstrap_valid_draws']=len(samples)
                save(HERE/'Private'/f'{name}-final-predictions.json',[dict(case_key=r['case_key'],raw=float(v),calibrated=float(s),shadow_take=bool(t),y=float(yy))for r,v,s,t,yy in zip(rows,raw,score,take,y)]);result[name]=record
        save(target,dict(state='one_shot_sealed_final_evaluated',completed_utc=stamp(),models_frozen_sha256=sha(HERE/'Public/models-frozen.json'),sealed_csv_sha256=release['csv_sha256'],sealed_intents_sha256=release['intent_jsonl_sha256'],models=result,no_payout_or_native_gate=True,forward_confirmation_required=True))
        save(HERE/'Public/final-evaluation-attempt-status.json',dict(state='COMPLETE_ONE_SHOT',utc=stamp(),attempt_marker_sha256=sha(marker),final_results_sha256=sha(target)));print(json.dumps(result,indent=2))
    except BaseException as error:
        save(HERE/'Public/final-evaluation-attempt-status.json',dict(state='FAILED_ATTEMPT_CONSUMED_NO_AUTOMATIC_RETRY',utc=stamp(),attempt_marker_sha256=sha(marker),error_type=type(error).__name__,error=str(error)));raise

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['fit','evaluate']);p.add_argument('--input',required=True);args=p.parse_args();fit(args)if args.mode=='fit'else evaluate(args)
if __name__=='__main__':main()
