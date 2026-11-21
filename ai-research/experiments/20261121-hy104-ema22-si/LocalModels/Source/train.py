"""Fixed model pairs. Requires frozen builder manifest and explicit GO receipt.

Usage: python train.py --manifest ... --models sklearn|tabpfn --go-receipt ...
Only private outputs contain row identifiers, forecasts, preprocessing states,
or model coefficients. Public outputs contain aggregates and file hashes.
"""
import os
from config import *
# Required before importing tabpfn/skrub/matplotlib.
os.environ.setdefault('SKB_DATA_DIRECTORY', str(ROOT / 'work/tools/tabpfn/skrub-data'))
os.environ.setdefault('SKRUB_DATA_DIRECTORY', str(ROOT / 'work/tools/tabpfn/skrub-data'))
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'work/tools/tabpfn/matplotlib'))
os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ.setdefault('DO_NOT_TRACK', '1')
os.environ.setdefault('TABPFN_MODEL_CACHE_DIR', str(CHECKPOINT.parent))

import argparse
import importlib.metadata
import time
import warnings
import traceback
import pandas as pd
from common import *


def resolved(manifest, key):
    p = Path(manifest[key])
    return p if p.is_absolute() else ROOT / p


def load_frozen(manifest_path):
    manifest_path = Path(manifest_path)
    m = json.loads(manifest_path.read_text())
    csv_path, npy_path, folds_path = [resolved(m, k) for k in ['dataset_csv', 'canonical_npy', 'folds_json']]
    features = m['context_features'] + m['si_features']
    # Nanosecond times are read as nullable integers, never inferred as floats.
    header = pd.read_csv(csv_path, nrows=0).columns
    ns_cols = [c for c in header if c.endswith('_ns')]
    frame = pd.read_csv(csv_path, float_precision='round_trip', dtype={c: 'Int64' for c in ns_cols})
    numeric = frame[features].to_numpy(dtype=np.float64)
    canonical = np.load(npy_path, allow_pickle=False)
    if canonical.shape != numeric.shape or not np.array_equal(numeric, canonical, equal_nan=True):
        raise ValueError('CSV / canonical NPY not numerically identical')
    if not frame[m['id_column']].is_unique:
        raise ValueError('Duplicate eligible IDs')
    if np.isinf(canonical).any():
        raise ValueError('Infinite feature value')
    loaded_folds = json.loads(folds_path.read_text())
    folds = loaded_folds['folds'] if isinstance(loaded_folds, dict) else loaded_folds
    binding = {'manifest_sha256': sha(manifest_path), 'dataset_csv_sha256': sha(csv_path), 'canonical_npy_sha256': sha(npy_path), 'folds_json_sha256': sha(folds_path)}
    for actual, declared in [('dataset_csv_sha256', 'dataset_csv_sha256'), ('canonical_npy_sha256', 'canonical_npy_sha256'), ('folds_json_sha256', 'folds_sha256')]:
        if binding[actual] != m[declared]:
            raise ValueError('Frozen file hash mismatch: ' + declared)
    validate_folds(m, frame, folds)
    return m, frame, folds, binding


def ids_for(fold, prefix, frame, idcol):
    if prefix + '_ids' in fold:
        return fold[prefix + '_ids']
    if prefix + '_indices' in fold:
        return frame.iloc[fold[prefix + '_indices']][idcol].tolist()
    raise KeyError(f'Frozen fold needs {prefix}_ids or {prefix}_indices')


def validate_folds(m, frame, folds):
    """Reject changed pairing, same-day leakage and outcomes known too late."""
    idcol, datecol = m['id_column'], m['date_column']
    index = frame.set_index(idcol, drop=False)
    seen = set()
    for f in folds:
        if f.get('status', 'ready') not in ('ready', 'ok'):
            continue
        train_ids, test_ids = [ids_for(f, p, frame, idcol) for p in ['train', 'test']]
        if set(train_ids) & set(test_ids) or seen & set(test_ids):
            raise ValueError('Fold overlap or duplicate temporal test case')
        seen.update(test_ids)
        for prefix, ids in [('train', train_ids), ('test', test_ids)]:
            if prefix + '_indices' in f and ids != frame.iloc[f[prefix + '_indices']][idcol].tolist():
                raise ValueError('Frozen ID/index order mismatch')
        tr, te = index.loc[train_ids], index.loc[test_ids]
        if not len(te):
            continue
        if len(tr) < m['initial_minimum_train_cases']:
            raise ValueError('Training smaller than predeclared initial minimum')
        if not tr[datecol].max() < f['gap_day'] < te[datecol].min():
            raise ValueError('Missing whole-day temporal gap')
        expected_gap = (pd.Timestamp(te[datecol].min()) - pd.offsets.BDay(1)).strftime('%Y-%m-%d')
        if f['gap_day'] != expected_gap:
            raise ValueError('Gap is not previous whole business date')
        outcome = m['outcome_ns_column']
        if not (tr[outcome] < int(f['test_first_information_ns'])).all():
            raise ValueError('Training outcome overlaps test information window')
        if int(tr[outcome].max()) != int(f['latest_train_outcome_ns']):
            raise ValueError('Frozen outcome boundary mismatch')
        if not set(te[datecol]) <= set(f['test_dates']):
            raise ValueError('Test rows outside frozen block')
    if len(seen) != m['test_cases']:
        raise ValueError('Test case coverage differs from manifest')


def get_model(name, features):
    p = MODEL_CONFIG[name].copy()
    kind = p.pop('kind')
    if kind == 'TabPFN_v2':
        import torch
        from tabpfn import TabPFNClassifier
        from tabpfn.constants import ModelVersion
        if sha(CHECKPOINT) != CHECKPOINT_SHA256:
            raise ValueError('Official V2 checkpoint SHA mismatch')
        torch.set_num_threads(p.pop('torch_threads'))
        p.pop('checkpoint_sha256'); p.pop('model_version')
        # Fixed side, SI coverage status, and all explicit missing flags.
        cats = [0] + ([i for i, feature in enumerate(features) if feature.lower() == 'si_status_code'])
        cats += list(range(len(features), 2 * len(features)))
        return TabPFNClassifier.create_default_for_version(ModelVersion.V2, model_path=str(CHECKPOINT), categorical_features_indices=cats, **p)
    from sklearn.linear_model import LogisticRegression, RidgeClassifier, SGDClassifier, Perceptron
    from sklearn.svm import LinearSVC
    constructors = {c.__name__: c for c in [LogisticRegression, RidgeClassifier, SGDClassifier, Perceptron, LinearSVC]}
    return constructors[kind](**p)


def forecast(model, x, probability_model, singleton):
    if probability_model:
        classes = list(model.classes_)
        if classes != [0, 1]:
            raise ValueError('Unexpected fitted class order')
        prob = np.array([model.predict_proba(row[None, :])[0, classes.index(1)] for row in x]) if singleton else model.predict_proba(x)[:, classes.index(1)]
        # Native sklearn thresholds use p>0.5 for binary ties; TabPFN argmax also
        # chooses class0 at an exact tie. Store native predict for sklearn.
        pred = (prob > .5).astype(int) if singleton else model.predict(x)
        return prob.copy(), pred, prob
    return np.asarray(model.decision_function(x)), np.asarray(model.predict(x)), None


def run(manifest_path, model_group, go_path):
    started = time.time()
    register_path = HERE / 'Public/preregister.json'
    if not register_path.exists():
        raise ValueError('Missing preregistration')
    go = json.loads(Path(go_path).read_text())
    if go.get('authorized') is not True:
        raise ValueError('No parent authorization receipt')
    m, frame, folds, binding = load_frozen(manifest_path)
    if go.get('manifest_sha256') != binding['manifest_sha256']:
        raise ValueError('GO receipt does not bind exact dataset manifest')
    idcol = m['id_column']
    idx = frame.set_index(idcol, drop=False)
    targets = m.get('target_columns', [m['label_column']])
    if isinstance(targets, dict):
        targets = list(targets.values())
    names = [k for k in MODEL_CONFIG if (k == 'ML9_TabPFN_v2') == (model_group == 'tabpfn')]
    versions = {k: importlib.metadata.version(k) for k in ['numpy', 'pandas', 'scikit-learn']}
    if model_group == 'tabpfn':
        versions['tabpfn'] = importlib.metadata.version('tabpfn')
        versions['torch'] = importlib.metadata.version('torch')
    save(HERE / f'Public/runtime-{model_group}.json', dict(utc=utc_now(), versions=versions, binding=binding, preregister_sha256=sha(register_path), sources={p.name: sha(p) for p in sorted((HERE / 'Source').glob('*.py'))}))
    all_rows, fit_records, block_metrics, skip_records = [], [], [], []
    for target in targets:
        if not set(frame[target].dropna().unique()) <= {0, 1} or frame[target].isna().any():
            raise ValueError('Frozen eligible target must be binary with no missing label')
        for f in folds:
            fid = f.get('fold', f.get('fold_id'))
            if f.get('status', 'ready') not in ('ready', 'ok'):
                skip_records.append({'fold': fid, 'target': target, 'reason': 'frozen_fold_' + f['status']})
                continue
            train_ids = ids_for(f, 'train', frame, idcol)
            test_ids = ids_for(f, 'test', frame, idcol)
            if set(train_ids) & set(test_ids) or len(set(test_ids)) != len(test_ids):
                raise ValueError('Frozen fold train/test overlap or duplicate test ID')
            tr, te = idx.loc[train_ids], idx.loc[test_ids]
            if not len(te):
                continue
            ytr, yte = tr[target].to_numpy(dtype=int), te[target].to_numpy(dtype=int)
            counts = np.bincount(ytr, minlength=2)
            if (counts == 0).any():
                skip_records.append({'fold': fid, 'target': target, 'reason': 'one_training_class', 'train_class_counts': counts.tolist(), 'skipped_models': names})
                continue
            prior = (counts[1] + 1) / (len(ytr) + 2)
            for name in names:
                pair = []
                for arm, features in [('context', m['context_features']), ('context_plus_SI', m['context_features'] + m['si_features'])]:
                    begin = time.time()
                    pre = TrainOnlyPreprocessor().fit(tr[features].to_numpy(dtype=float))
                    xtr, xte = pre.transform(tr[features]), pre.transform(te[features])
                    model = get_model(name, features)
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter('always')
                        model.fit(xtr, ytr)
                        raw, prediction, probability = forecast(model, xte, name in PROBABILITY_MODELS, name == 'ML9_TabPFN_v2')
                    if not np.isfinite(raw).all():
                        raise ValueError('Nonfinite actual forecast')
                    values = score_binary(yte, raw, prediction, probability)
                    block_metrics.append(dict(model=name, arm=arm, fold=fid, target=target, **values))
                    state = dict(model=name, arm=arm, fold=fid, target=target, features=features, train_n=len(tr), test_n=len(te), train_class_counts=counts.tolist(), preprocessing=pre.state(), warnings=[dict(category=type(w.message).__name__, message=str(w.message)) for w in caught], elapsed_seconds=time.time()-begin)
                    if hasattr(model, 'n_iter_'):
                        state['n_iter'] = np.asarray(model.n_iter_).tolist()
                    if hasattr(model, 'coef_'):
                        state['coef'] = np.asarray(model.coef_).tolist()
                        state['intercept'] = np.asarray(model.intercept_).tolist()
                    fit_records.append(state)
                    for pos, key in enumerate(test_ids):
                        pair.append({idcol:key, 'date':te.iloc[pos][m['date_column']], 'target':target, 'model':name, 'arm':arm, 'fold':fid, 'y':int(yte[pos]), 'raw_score':float(raw[pos]), 'prediction':int(prediction[pos]), 'probability':float(probability[pos]) if probability is not None else None, 'score_kind':'native_probability' if probability is not None else 'raw_decision_function', 'train_prior_probability':float(prior), 'train_prior_prediction':int(prior>.5)})
                    print(f'{target} {name} {arm} fold={fid} train={len(tr)} test={len(te)} seconds={time.time()-begin:.2f}', flush=True)
                    del model
                # Commit only a complete matched pair.
                if [r[idcol] for r in pair if r['arm']=='context'] != [r[idcol] for r in pair if r['arm']=='context_plus_SI']:
                    raise ValueError('Arm row pairing changed')
                all_rows.extend(pair)
                pd.DataFrame(all_rows).to_csv(HERE / f'Private/forecasts-{model_group}-incremental.csv', index=False)
                save(HERE / f'Private/fits-{model_group}.json', fit_records)
                save(HERE / f'Public/progress-{model_group}.json', dict(status='RUNNING', target=target, model=name, last_fold=fid, completed_fits=len(fit_records), elapsed_seconds=time.time()-started))
    predictions = pd.DataFrame(all_rows)
    if len(predictions) == 0:
        raise ValueError('No genuine out-of-fold forecasts were generated')
    pred_path = HERE / f'Private/forecasts-{model_group}.csv'
    predictions.to_csv(pred_path, index=False)
    summary = []
    for (target, name, arm), g in predictions.groupby(['target','model','arm'], sort=False):
        prob = g.probability.to_numpy() if name in PROBABILITY_MODELS else None
        blocks = [r for r in block_metrics if r['target']==target and r['model']==name and r['arm']==arm]
        summary.append(dict(target=target, model=name, arm=arm, **score_binary(g.y, g.raw_score, g.prediction, prob), within_block_auc=fold_pair_auc(blocks), pooled_auc_caveat='Across-fold raw margins can have different scales; within-block AUC is the meaningful margin ranking comparison', baseline=score_binary(g.y, g.train_prior_probability, g.train_prior_prediction, g.train_prior_probability)))
    result = dict(status='FINISHED', utc=utc_now(), model_group=model_group, models=names, fitted_pairs=len(fit_records)//2, fit_count=len(fit_records), unique_test_cases=int(predictions[idcol].nunique()), target_columns=targets, binding=binding, versions=versions, forecasts_sha256=sha(pred_path), metrics=summary, by_fold=block_metrics, skipped=skip_records, elapsed_seconds=time.time()-started, limits=['Correct native strategy-exit labels; these are not standalone SI15m markouts', 'No portfolio replay, order, gate, deployment, or fresh OOS claim', 'Historical exploratory comparison, sparse SI, unknown feed availability', 'No fitted calibration or parameter/feature search'])
    save(HERE / f'Public/results-{model_group}.json', result)
    save(HERE / f'Public/progress-{model_group}.json', dict(status='FINISHED', fit_count=len(fit_records), unique_test_cases=result['unique_test_cases'], elapsed_seconds=time.time()-started))
    print(json.dumps({k:result[k] for k in ['status','fit_count','unique_test_cases','elapsed_seconds']}, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--models', choices=['sklearn','tabpfn'], required=True)
    parser.add_argument('--go-receipt', required=True)
    a = parser.parse_args()
    try:
        run(a.manifest, a.models, a.go_receipt)
    except Exception as e:
        save(HERE / f'Public/failure-{a.models}-{int(time.time())}.json', dict(status='FAILED', utc=utc_now(), error=repr(e), traceback=traceback.format_exc()))
        raise
