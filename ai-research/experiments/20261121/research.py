"""Prespecified small-table comparisons, separate from native cash replay.

No hyperparameter/feature search. All reported tests use later sessions.
The development year has already been selected: none of this is fresh OOS.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
import argparse, csv, hashlib, importlib.util, json, os, sys, time
import numpy as np
import sklearn
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, brier_score_loss, log_loss, mean_squared_error
from scipy.stats import spearmanr
from threadpoolctl import threadpool_limits

HERE=Path(__file__).resolve().parent; DE=HERE.parents[1]
OLD=DE/'outputs/AI-Forschung-20261120'
sys.path.insert(0,str(OLD/'repo/ai-research'))
import train_ml1 as original
from native_check import read,write,sha

BOOST=dict(max_depth=1,learning_rate=.05,max_iter=100,min_samples_leaf=20,
    l2_regularization=1.,early_stopping=False,random_state=20261121)
ARMS=['ML1C','ML8','MR1','ML9']
SEED=20261121

def dataset():
    dates,rows,sources=original.data()
    X=np.array([r['features'] for r in rows],float)
    net=np.array([r['stress_net_cents']/100 for r in rows],float)
    return dates,rows,sources,X,net

def register():
    assert not (HERE/'Training').exists(), 'Do not overwrite a plan after training'
    dates,rows,sources,_,_=dataset()
    config=dict(schema='ES-ML-COMPARISON-20261121-v1',created_at_utc=datetime.now(timezone.utc).isoformat(),
        period=[dates[0],dates[-1]],sessions=242,unique_period_candidates=347,features=original.FEATURES,
        existing_reference='ML1 frozen original in-sample-training-score threshold; preserved separately',
        arms=dict(ML1C=dict(model='L2 LogisticRegression',C=.1,threshold_control=True),
            ML8=dict(model='HistGradientBoostingClassifier',**BOOST),
            MR1=dict(model='StandardScaler + Ridge',alpha=10.,solver='svd',
                target='stress net USD / planned_stop_risk_usd',gate_score='predicted R * planned_stop_risk_usd'),
            ML9=dict(model='TabPFNClassifier',model_version='V2',package_version='10.2.0',
                n_estimators=4,device='cpu',random_state=SEED,
                input='same five raw features, model internal training-only preprocessing',
                licence='Prior Labs v2 model license, exact downloaded text and weight hash recorded before fit')),
        outer_split='same 9 expanding blocks as original:80 initial train sessions,1 gap,20 test',
        threshold='20th percentile of inner chronological held-out scores; ties accepted; NOT in-sample context scores',
        inner_split='5 contiguous calendar-session folds inside outer train; train on other4, embargo adjacent1session on both sides; all labels already known before outer decision',
        final_fit='refit same fixed model on all eligible outer train;20percent threshold from cross-fitted training scores',
        class_failure_rule='stop and report, do not silently drop blocks or change parameters',
        validation='native physical prefix audit before new model fits; outer training uses only already-known outcomes; TabPFN singleton/batch check',
        random_omissions=dict(draws=1000,seed=SEED,match='same number of omissions within each outer test block',
            scope='candidate-utility diagnostic, not a provider cash/null distribution'),
        permutation=dict(legacy_ML1_draws=1000,new_family_max_rank_draws=199,seed=SEED+1,unit='whole within-day ordered outcome vectors',
            strata='calendar quarter and same candidate count per day',refit='entire original ML1 pipeline each draw',
            scope='conditional diagnostic; day exchangeability and remaining serial dependence limit formal inference'),
        utility='candidate omission diagnostic: accepted mean stress net minus omitted mean; primary new-family screen is threshold-free Spearman(score,stress net)',
        permutation_cost_rule='For threshold-free statistic refit outer models only; cross-fitting affects gate threshold, not the outer scores. Same first199 permutations, max statistic across4arms. Conditional screen, no fresh-confirmation claim.',
        native_cash='each new completed gate rerun in all6 native SQX segments, same unchanged provider replay; no deleting old fills',
        economic_target='mean and median end cash from1000USD over143 dependent100-session windows; normal and1adverse tick per side',
        adoption='none without later genuinely new evidence; no live changes or leaderboard promotion from this selected year',
        sources=sources,sklearn_version=sklearn.__version__,
        code={p.name:sha(p) for p in [Path(__file__),HERE/'native_check.py']},
        cost='local compute; no cloud calls/GPU rental/data purchase',
        SI='separate coverage/availability feasibility audit; no missing-feed intervals encoded as no event')
    write(HERE/'preregister.json',config)
    print('Registered',sha(HERE/'preregister.json'),flush=True)

def check_registration():
    cfg=read(HERE/'preregister.json')
    for name,digest in cfg['code'].items():assert sha(HERE/name)==digest, 'Code changed after registration: '+name
    receipt=read(HERE/'preregister-github-receipt.json')
    assert receipt['preregister_sha256']==sha(HERE/'preregister.json') and receipt['state']=='published_before_training'
    return cfg

def model_for(arm):
    if arm=='ML1C': return make_pipeline(StandardScaler(), original.LogisticRegression(C=.1,
        solver='lbfgs',l1_ratio=0,max_iter=2000,class_weight=None,random_state=20261120))
    if arm=='ML8':return HistGradientBoostingClassifier(**BOOST)
    if arm=='MR1':return make_pipeline(StandardScaler(),Ridge(alpha=10.,solver='svd'))
    assert arm=='ML9'
    from tabpfn import TabPFNClassifier
    from tabpfn.constants import ModelVersion
    assert read(HERE/'tabpfn-weight-proof.json')['model_version']=='V2'
    return TabPFNClassifier.create_default_for_version(ModelVersion.V2,n_estimators=4,device='cpu',random_state=SEED,
        model_path=str(HERE/'Models'/read(HERE/'tabpfn-weight-proof.json')['filename']))

def fit_score(arm,X,net,train,test):
    a,b=np.array(train),np.array(test)
    y=(net>0).astype(int)
    assert min(np.bincount(y[a],minlength=2))>=5, 'Too few examples of a class'
    model=model_for(arm)
    if arm=='MR1':
        model.fit(X[a],net[a]/X[a,0]);score=model.predict(X[b])*X[b,0]
    else:
        model.fit(X[a],y[a]);score=model.predict_proba(X[b])[:,1]
    assert np.all(np.isfinite(score))
    return np.array(score),model

def metrics(net,score,take,probability=True):
    y=(net>0).astype(int)
    result=dict(candidates=len(net),accepted=int(take.sum()),omitted=int((~take).sum()),
        auc=float(roc_auc_score(y,score)) if len(np.unique(y))==2 else None,
        mean_accepted_stress_net_usd=float(net[take].mean()) if take.any() else None,
        mean_omitted_stress_net_usd=float(net[~take].mean()) if (~take).any() else None,
        selected_candidate_sum_usd=float(net[take].sum()),all_candidate_sum_usd=float(net.sum()),
        no_cash_claim=True)
    result['spearman_score_stress_net']=float(spearmanr(score,net).statistic) if np.ptp(score)>0 and len(net)>1 else None
    if probability: result.update(brier=float(brier_score_loss(y,score)),log_loss=float(log_loss(y,score,labels=[0,1])))
    return result

def fit_arm(arm):
    check_registration(); assert read(HERE/'prefix-progress.json')['state']=='complete'
    dates,rows,sources,X,net=dataset(); y=net>0
    predictions=[dict(segment=r['segment'],signal_ns=r['ns'],session=r['day'],block=None,
        score=None,take=1,stress_net_usd=float(net[i])) for i,r in enumerate(rows)]
    blocks=[]; indices=[];scores=[];takes=[]
    for start,train,test in original.splits(rows,dates):
        cross_scores={};fold_proofs=[]
        train_days=dates[:start-1]
        for day_indices in np.array_split(np.arange(len(train_days)),5):
            lo,hi=int(day_indices[0]),int(day_indices[-1])
            validation_days=set(train_days[lo:hi+1])
            embargo=set(train_days[max(0,lo-1):min(len(train_days),hi+2)])
            validation=[i for i in train if rows[i]['day'] in validation_days]
            inner=[i for i in train if rows[i]['day'] not in embargo]
            assert validation and inner
            calibration_score,_=fit_score(arm,X,net,inner,validation)
            for i,p in zip(validation,calibration_score,strict=True):cross_scores[i]=float(p)
            fold_proofs.append(dict(start=train_days[lo],end=train_days[hi],inner_samples=len(inner),validation_samples=len(validation)))
        assert set(cross_scores)==set(train)
        threshold=float(np.quantile(list(cross_scores.values()),.2,method='linear'))
        score,model=fit_score(arm,X,net,train,test)
        take=score>=threshold
        for i,p,k in zip(test,score,take,strict=True):predictions[i].update(block=start,score=float(p),take=int(k))
        # TabPFN additionally gets a singleton/batch check: no later test rows may be context.
        singleton_check=None
        if arm=='ML9':
            single=np.array([model.predict_proba(X[[i]])[0,1] for i in test])
            delta=float(np.max(np.abs(single-score)))
            assert delta<1e-6, 'TabPFN scores depend materially on other test rows'
            assert np.array_equal(single>=threshold,take), 'Numerical batch differences changed a trading decision'
            score=single;take=score>=threshold
            for i,p,k in zip(test,score,take,strict=True):predictions[i].update(score=float(p),take=int(k))
            singleton_check=delta
        proof=dict(block=start,train_samples=len(train),calibration_samples=len(train),folds=fold_proofs,
            singleton_batch_max_abs_difference=singleton_check,
            first_test_day=dates[start],threshold=threshold,train_ids_sha256=hashlib.sha256(json.dumps([rows[i]['ns'] for i in train]).encode()).hexdigest(),
            metrics=metrics(net[test],score,take,arm!='MR1'))
        assert max(rows[i]['end_ns'] for i in train)<min(rows[i]['ns'] for i in test)
        blocks.append(proof); indices.extend(test);scores.extend(score);takes.extend(take)
        write(HERE/'Training'/arm/'progress.json',dict(state='running',completed_blocks=len(blocks)))
        print(arm,'block',len(blocks),'complete',flush=True)
    score=np.array(scores);take=np.array(takes,bool);indices=np.array(indices)
    result=dict(state='chronological_training_complete_not_native_cash',arm=arm,preregister_sha256=sha(HERE/'preregister.json'),
        blocks=blocks,metrics=metrics(net[indices],score,take,arm!='MR1'),fresh_OOS=False,
        selected_year=True,sources=sources,sklearn_version=sklearn.__version__)
    if arm=='MR1':result['metrics']['net_usd_mse']=float(mean_squared_error(net[indices],score))
    write(HERE/'Training'/arm/'results.json',result)
    path=HERE/'Training'/arm/'predictions.csv'
    with path.open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(predictions[0]));w.writeheader();w.writerows(predictions)
    for segment in {r['segment'] for r in rows}:
        target=HERE/'Decisions'/arm/segment/'ml-decisions.csv';target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text('signal_ns,take\n'+''.join(f'{r["signal_ns"]},{r["take"]}\n' for r in predictions if r['segment']==segment))
    result['random_omission_control']=matched_random(net[indices],take,np.array([p['block'] for p in predictions if p['block'] is not None]))
    write(HERE/'Training'/arm/'results.json',result)
    write(HERE/'Training'/arm/'progress.json',dict(state='complete',completed_blocks=len(blocks)))
    print(json.dumps(result['metrics']),flush=True)

def utility(net,take):
    return float(net[take].mean()-net[~take].mean()) if take.any() and (~take).any() else 0.

def matched_random(net,take,blocks):
    rng=np.random.default_rng(SEED);samples=[]
    for _ in range(1000):
        mask=np.ones(len(take),bool)
        for block in np.unique(blocks):
            index=np.flatnonzero(blocks==block);k=int((~take[index]).sum())
            mask[rng.choice(index,k,replace=False)]=False
        samples.append(utility(net,mask))
    observed=utility(net,take)
    return dict(draws=1000,observed_utility_usd=observed,null_q95_usd=float(np.quantile(samples,.95)),
        upper_tail_rank=(1+sum(v>=observed for v in samples))/1001,
        scope='candidate utility only; no position path or cash claim')

def original_pipeline(X,net,rows,dates):
    result=[]
    for start,train,test in original.splits(rows,dates):
        model=original.fit_one(X[train],(net[train]>0).astype(int))
        scores=model.predict_proba(X[test])[:,1]
        threshold=np.quantile(model.predict_proba(X[train])[:,1],.2,method='linear')
        result.extend((i,float(p),bool(p>=threshold),start) for i,p in zip(test,scores,strict=True))
    return result

def controls():
    check_registration(); dates,rows,_,X,net=dataset()
    baseline=original_pipeline(X,net,rows,dates)
    saved={int(r['signal_ns']):r for r in csv.DictReader((OLD/'Training/predictions.csv').open()) if r['score']}
    assert all(abs(float(saved[rows[i]['ns']]['score'])-p)<1e-12 and int(saved[rows[i]['ns']]['take'])==k for i,p,k,_ in baseline)
    use=np.array([r[0] for r in baseline]);take=np.array([r[2] for r in baseline]);blocks=np.array([r[3] for r in baseline])
    result=dict(state='running',original_predictions_reproduced=True,random_omission=matched_random(net[use],take,blocks),
        old_auc_by_block=[dict(block=int(b),metrics=metrics(net[use[blocks==b]],np.array([r[1] for r in baseline])[blocks==b],take[blocks==b])) for b in np.unique(blocks)])
    grouped=defaultdict(list)
    day_rows=defaultdict(list)
    for i,r in enumerate(rows):
        if r['day'] in dates:day_rows[r['day']].append(i)
    for day,ix in day_rows.items():grouped[(day[:4],(int(day[5:7])-1)//3,len(ix))].append(ix)
    rng=np.random.default_rng(SEED+1);samples=[]
    for attempt in range(1000):
        synthetic=net.copy()
        for days in grouped.values():
            for target,source in zip(days,rng.permutation(len(days)),strict=True):synthetic[target]=net[days[source]]
        p=original_pipeline(X,synthetic,rows,dates)
        assert [r[0] for r in p]==use.tolist()
        mask=np.array([r[2] for r in p]);samples.append(utility(synthetic[use],mask))
        if (attempt+1)%25==0:
            result.update(completed_permutations=attempt+1);write(HERE/'Controls/progress.json',result)
            print('ML1 null pipeline',attempt+1,'/1000',flush=True)
    observed=utility(net[use],take)
    result.update(state='complete',permutations=dict(draws=1000,observed_utility_usd=observed,
        null_q95_usd=float(np.quantile(samples,.95)),conditional_upper_tail_rank=(1+sum(v>=observed for v in samples))/1001,
        exchangeability_warning='Conditional within-quarter equal-count session-block diagnostic; not an unconditional market-stationary test',
        no_cash_claim=True),completed_permutations=1000)
    write(HERE/'Controls/results.json',result);write(HERE/'Controls/progress.json',result)

def permutations():
    check_registration();dates,rows,_,X,net=dataset()
    actual={}
    for arm in ARMS:
        path=HERE/'Training'/arm/'predictions.csv';p=[r for r in csv.DictReader(path.open()) if r['score']]
        index={r['ns']:i for i,r in enumerate(rows)}
        actual[arm]=float(spearmanr([float(r['score']) for r in p],[net[index[int(r['signal_ns'])]] for r in p]).statistic)
    day_rows=defaultdict(list);grouped=defaultdict(list)
    for i,r in enumerate(rows):
        if r['day'] in dates:day_rows[r['day']].append(i)
    for day,ix in day_rows.items():grouped[(day[:4],(int(day[5:7])-1)//3,len(ix))].append(ix)
    singleton_days=sum(len(v) for v in grouped.values() if len(v)==1)
    rng=np.random.default_rng(SEED+1);draws=[]
    for attempt in range(199):
        synthetic=net.copy()
        for days in grouped.values():
            for target,source in zip(days,rng.permutation(len(days)),strict=True):synthetic[target]=net[days[source]]
        correlations={}
        for arm in ARMS:
            scores=[];outcomes=[]
            for _,train,test in original.splits(rows,dates):
                score,model=fit_score(arm,X,synthetic,train,test)
                if arm=='ML9':
                    for k in [0,len(test)-1]:
                        single=float(model.predict_proba(X[[test[k]]])[0,1])
                        assert abs(single-score[k])<1e-6,'Null predictor depends on other test inputs'
                scores.extend(score);outcomes.extend(synthetic[test])
            rho=spearmanr(scores,outcomes).statistic
            correlations[arm]=float(rho) if np.isfinite(rho) else 0.
        draws.append(correlations)
        if (attempt+1)%5==0:
            write(HERE/'Controls/family-progress.json',dict(state='running',completed=attempt+1,total=199))
            write(HERE/'Controls/family-null-partial.json',draws)
            print('all-family null',attempt+1,'/199',flush=True)
    maximum=[max(d.values()) for d in draws]
    result=dict(state='complete',draws=199,actual=actual,
        max_statistic_adjusted_upper_tail_rank={a:(1+sum(x>=v for x in maximum))/200 for a,v in actual.items()},
        max_statistic_q95=float(np.quantile(maximum,.95)),unchanged_singleton_stratum_sessions=singleton_days,
        total_candidate_sessions=len(day_rows),exchangeability_warning='Conditional whole-session vectors within quarter and count strata. Not a fresh OOS or universal significance claim.',
        threshold_free=True,native_cash_or_adoption_claim=False)
    write(HERE/'Controls/family-null.json',result);write(HERE/'Controls/family-progress.json',result)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('action',choices=['register','controls','fit','permutations']);a.add_argument('--arm',choices=ARMS);args=a.parse_args()
    with threadpool_limits(limits=1):
        if args.action=='register':register()
        elif args.action=='controls':controls()
        elif args.action=='permutations':permutations()
        else:fit_arm(args.arm)
