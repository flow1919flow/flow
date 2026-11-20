"""One fixed chronological classifier experiment. No parameter search.

Actual financial evaluation requires a subsequent full native SQX gate run.
The development year is previously selected material, not fresh OOS.
"""
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import csv, hashlib, json, os, warnings
import numpy as np
import sklearn
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.dummy import DummyClassifier
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.exceptions import ConvergenceWarning

FEATURES = ['planned_stop_risk_usd', 'bollinger_keltner_width_ratio',
            'signed_completed_ema_slope_atr', 'completed_relative_volume20', 'chicago_session_minute']
DE = Path(os.environ.get('HY_WORKSPACE', Path.cwd())).resolve()
HERE = DE/'outputs/AI-Forschung-20261120'
ORIGINAL = DE/'outputs/Micro-RiskSize-20261120'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())
def write(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
def day(ns):
    return datetime.fromtimestamp(int(ns)//1_000_000_000, timezone.utc).astimezone(ZoneInfo('America/Chicago')).date().isoformat()

def data():
    plan = read(ORIGINAL/'Inputs/ES/plan.json')
    dates = sorted({d for days in plan['episodes'].values() for d in days if d>='2025-11-24'})
    assert len(dates)==242 and dates[-1]=='2026-10-30'
    rows, sources = [], []
    for verified in sorted((HERE/'SQX/observer').glob('*/verified.json')):
        v=read(verified); assert v['state']=='native_observer_parity_verified'
        root=Path(v['folder']); base=read(ORIGINAL/'SQX/ES/MFF/funded'/verified.parent.name/'verified.json')
        assert sha(root/'trades.csv')==base['native_sha256']
        assert sha(root/'candidates.csv')==base['candidate_sha256']
        with (root/'ml-features.csv').open() as f: features={int(r['signal_ns']):r for r in csv.DictReader(f)}
        with (root/'candidates.csv').open() as f: candidates=list(csv.DictReader(f))
        assert len(features)==len(candidates)
        for c in candidates:
            ns=int(c['entry_decision_ns']); r=features[ns]
            sign=1 if c['side']=='LONG' else -1
            assert int(r['side'])==sign and int(r['quote_ns'])<=ns
            values=[float(r[k]) for k in FEATURES]; assert np.all(np.isfinite(values))
            net=int(c['net_pnl_cents'])-2500 # native mini commission already included; 1 adverse tick each side
            rows.append(dict(segment=verified.parent.name, ns=ns, end_ns=int(c['exit_time_ns']), day=day(ns),
                features=values, y=int(net>0), stress_net_cents=net, take=1, block=None, score=None))
        sources.append(dict(segment=verified.parent.name, features_sha256=sha(root/'ml-features.csv'),
                            candidates_sha256=sha(root/'candidates.csv'), observer_proof_sha256=sha(verified)))
    assert len(sources)==6 and len(rows)==353
    rows.sort(key=lambda r:r['ns']); assert len({r['ns'] for r in rows})==len(rows)
    assert sum(r['day'] in dates for r in rows)==347
    return dates, rows, sources

def splits(rows, dates):
    for start in range(81, len(dates), 20):
        train_days=set(dates[:start-1]); test_days=set(dates[start:start+20])
        test=[i for i,r in enumerate(rows) if r['day'] in test_days]
        if not test:
            raise ValueError('A registered test block has no candidates; report instead of silently discarding it')
        first=min(rows[i]['ns'] for i in test)
        train=[i for i,r in enumerate(rows) if r['day'] in train_days and r['end_ns']<first]
        yield start, train, test

def fit_one(X, y):
    assert len(np.unique(y))==2
    model=make_pipeline(StandardScaler(), LogisticRegression(C=.1, solver='lbfgs', l1_ratio=0,
        max_iter=2000, class_weight=None, random_state=20261120))
    with warnings.catch_warnings():
        warnings.simplefilter('error', ConvergenceWarning)
        model.fit(X,y)
    return model

def main():
    dates, rows, sources=data()
    config=dict(schema='ML1-CAUSAL-LOGIT-1', written_before_training=True,
        period=[dates[0],dates[-1]], features=FEATURES,
        label='native standalone candidate net after mini commission minus 2500 cents roundtrip tick stress > 0',
        C=.1, solver='lbfgs', max_iter=2000, scale='training_only',
        threshold='20th percentile of training-only fitted scores; ties accepted',
        first_training_sessions=80, gap_sessions=1, test_block_sessions=20,
        fixed_C_note='Fixed C is the prespecified learning rule; effective penalty relative to mean loss changes with training size.',
        fresh_OOS=False, development_year_already_selected=True, sklearn_version=sklearn.__version__,
        sources=sources, code_sha256=sha(Path(__file__)))
    write(HERE/'Training/design-before-results.json', config)
    X=np.array([r['features'] for r in rows],float); y=np.array([r['y'] for r in rows],int)
    blocks=[]; eval_indices=[]; probabilities=[]; priors=[]
    for block, train, test in splits(rows, dates):
        a,b=np.array(train),np.array(test)
        assert min(np.bincount(y[a],minlength=2))>=10, 'Too few examples of a class in the registered train block'
        model=fit_one(X[a],y[a]); prob=model.predict_proba(X[b])[:,1]
        training_scores=model.predict_proba(X[a])[:,1]
        threshold=float(np.quantile(training_scores,.2,method='linear'))
        dummy=DummyClassifier(strategy='prior').fit(X[a],y[a])
        dprob=dummy.predict_proba(X[b])[:,1]
        for i,p in zip(test,prob,strict=True):
            rows[i].update(take=int(p>=threshold), block=block, score=float(p))
        scaler=model.named_steps['standardscaler']; fitted=model.named_steps['logisticregression']
        proof=dict(block=block,train_samples=len(a),test_samples=len(b),
            train_last_day=dates[block-2], gap_day=dates[block-1],
            test_start=dates[block],test_end=dates[min(len(dates)-1,block+19)],
            train_latest_label_end_ns=max(rows[i]['end_ns'] for i in train),
            first_test_decision_ns=min(rows[i]['ns'] for i in test),
            train_positive=int(y[a].sum()),test_positive=int(y[b].sum()),
            threshold=threshold, skipped=int(sum(rows[i]['take']==0 for i in test)),
            scaler_mean=scaler.mean_.tolist(),scaler_scale=scaler.scale_.tolist(),
            coefficients=fitted.coef_[0].tolist(),intercept=float(fitted.intercept_[0]),
            train_ids_sha256=hashlib.sha256(json.dumps([rows[i]['ns'] for i in train]).encode()).hexdigest())
        assert proof['train_latest_label_end_ns']<proof['first_test_decision_ns']
        # Verify portable coefficient/scaler export numerically.
        manual=1/(1+np.exp(-((X[b]-scaler.mean_)/scaler.scale_)@fitted.coef_[0]-fitted.intercept_[0]))
        assert np.max(np.abs(manual-prob))<1e-12
        blocks.append(proof); eval_indices.extend(test); probabilities.extend(map(float,prob)); priors.extend(map(float,dprob))
        write(HERE/'Training/progress.json',dict(state='running',completed_blocks=len(blocks)))
    use=np.array(eval_indices); pred=np.array(probabilities); d=np.array(priors)
    metrics=dict(predicted_candidates=len(use), skipped_candidates=sum(rows[i]['take']==0 for i in use),
        observed_positive_rate=float(y[use].mean()), brier=float(brier_score_loss(y[use],pred)),
        dummy_brier=float(brier_score_loss(y[use],d)), log_loss=float(log_loss(y[use],pred,labels=[0,1])),
        dummy_log_loss=float(log_loss(y[use],d,labels=[0,1])), auc=float(roc_auc_score(y[use],pred)),
        calibration_claim='Unconfirmed; scores have not been independently calibrated.',
        financial_claim='None: a new full native SQX gate run and provider replay are still required.')
    write(HERE/'Training/results.json',dict(state='trained_development_diagnostic',config=config,blocks=blocks,metrics=metrics))
    out=HERE/'Training/predictions.csv'
    with out.open('w') as f:
        writer=csv.DictWriter(f,fieldnames=['segment','signal_ns','session','block','score','take','stress_net_cents'])
        writer.writeheader()
        for r in rows: writer.writerow(dict(segment=r['segment'],signal_ns=r['ns'],session=r['day'],block=r['block'],score=r['score'],take=r['take'],stress_net_cents=r['stress_net_cents']))
    for segment in {source['segment'] for source in sources}:
        folder=HERE/'Decisions'/segment; folder.mkdir(parents=True,exist_ok=True)
        with (folder/'ml-decisions.csv').open('w') as f:
            f.write('signal_ns,take\n')
            for r in rows:
                if r['segment']==segment:f.write(f"{r['ns']},{r['take']}\n")
    write(HERE/'Training/progress.json',dict(state='complete',completed_blocks=len(blocks),predicted_candidates=len(use)))
    print(json.dumps(metrics,indent=2))

if __name__=='__main__': main()
