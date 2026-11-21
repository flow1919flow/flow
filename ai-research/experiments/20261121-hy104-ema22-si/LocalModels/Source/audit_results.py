"""Independent numerical acceptance of saved forecasts, no new model fits."""
from config import *
from common import *
from train import load_frozen, ids_for
import pandas as pd
from scipy.special import expit


def pairwise_auc(y, scores):
    y, scores = np.asarray(y), np.asarray(scores)
    a, b = scores[y == 1], scores[y == 0]
    return float(((a[:, None] > b[None, :]) + .5 * (a[:, None] == b[None, :])).mean()) if len(a) and len(b) else None


def main():
    m, frame, folds, binding = load_frozen(ROOT / 'outputs/HY104-EMA22-SI-DeepInfra-20261121/Public/dataset-manifest.json')
    idcol = m['id_column']
    idx = frame.set_index(idcol, drop=False)
    predictions, summaries = [], []
    checks = []
    warnings_summary = []
    maximum_score_reconstruction_error = 0.
    for group in ['sklearn', 'tabpfn']:
        source = HERE / f'Public/results-{group}.json'
        results = json.loads(source.read_text())
        assert results['status'] == 'FINISHED' and results['binding'] == binding
        rawpath = HERE / f'Private/forecasts-{group}.csv'
        assert sha(rawpath) == results['forecasts_sha256']
        pred = pd.read_csv(rawpath, float_precision='round_trip')
        fits = json.loads((HERE / f'Private/fits-{group}.json').read_text())
        assert results['fit_count'] == len(fits) == (60 if group == 'sklearn' else 10)
        for state in fits:
            f = next(f for f in folds if f['fold_id'] == state['fold'])
            tr = idx.loc[ids_for(f, 'train', frame, idcol)]
            te = idx.loc[ids_for(f, 'test', frame, idcol)]
            assert state['train_class_counts'] == np.bincount(tr.y, minlength=2).tolist()
            features = state['features']
            # Independently compute imputation/scaler values from original train.
            original = tr[features].to_numpy(dtype=float)
            medians = np.array([np.median(c[np.isfinite(c)]) if np.isfinite(c).any() else 0. for c in original.T])
            missing = np.isnan(original)
            aug = np.concatenate([np.where(missing, medians, original), missing.astype(float)], axis=1)
            st = state['preprocessing']
            assert np.array_equal(medians, st['median_'])
            assert np.array_equal(aug.mean(axis=0), st['mean_'])
            scales = aug.std(axis=0); scales[scales == 0] = 1.
            assert np.array_equal(scales, st['scale_'])
            s = pred[(pred.model == state['model']) & (pred.arm == state['arm']) & (pred.fold == state['fold'])]
            assert s[idcol].tolist() == te[idcol].tolist()
            assert s.y.tolist() == te.y.tolist()
            if state['warnings']:
                warnings_summary.append(dict(model=state['model'], arm=state['arm'], fold=state['fold'], warnings=state['warnings']))
            if 'coef' in state:
                a = te[features].to_numpy(dtype=float); nulls = np.isnan(a)
                xtest = (np.concatenate([np.where(nulls, medians, a), nulls.astype(float)], axis=1) - aug.mean(axis=0)) / scales
                margins = (xtest @ np.array(state['coef']).T + np.array(state['intercept'])).ravel()
                native = expit(margins) if state['model'] in PROBABILITY_MODELS else margins
                error = float(np.max(np.abs(native - s.raw_score.to_numpy())))
                maximum_score_reconstruction_error = max(maximum_score_reconstruction_error, error)
                assert error < 1e-10
        for summary in results['metrics']:
            s = pred[(pred.model == summary['model']) & (pred.arm == summary['arm'])]
            y, score = s.y.to_numpy(), s.raw_score.to_numpy()
            assert abs(np.mean(y == s.prediction) - summary['accuracy']) < 1e-14
            assert abs(pairwise_auc(y, score) - summary['auc']) < 1e-14
            pairs, correct = 0, 0.
            for _, b in s.groupby('fold'):
                pos, neg = b.loc[b.y == 1, 'raw_score'].to_numpy(), b.loc[b.y == 0, 'raw_score'].to_numpy()
                pairs += len(pos) * len(neg)
                correct += float(((pos[:, None] > neg[None, :]) + .5 * (pos[:, None] == neg[None, :])).sum())
            assert abs(correct / pairs - summary['within_block_auc']['auc']) < 1e-14
            if summary['model'] in PROBABILITY_MODELS:
                p = s.probability.to_numpy()
                eps = np.finfo(p.dtype).eps
                clipped = np.clip(p, eps, 1 - eps)
                ll = float(-(y * np.log(clipped) + (1-y) * np.log1p(-clipped)).mean())
                assert abs(ll - summary['log_loss']) < 1e-10
                assert abs(np.mean((p-y)**2) - summary['brier']) < 1e-14
            else:
                assert s.probability.isna().all() and 'log_loss' not in summary and 'brier' not in summary
        predictions.append(pred)
        summaries.extend(results['metrics'])
        checks.append(f'{group}: all fits and native scores/probabilities independently accepted; exact frozen test IDs and y; no fake probability metrics')
    combined = pd.concat(predictions, ignore_index=True)
    expected = [key for f in folds for key in f['test_ids']]
    for (_, _), s in combined.groupby(['model', 'arm']):
        assert s[idcol].tolist() == expected
    assert combined.model.nunique() == 7 and len(combined) == 7 * 2 * 110
    checks.append('All14modelarms contain identical ordered110eligibletestcases over5folds')
    checks.append('Train-only preprocessing independently reconstructed for70fits; all60linear forecasts reproduced from saved coefficients within1e-10')
    checks.append('Accuracy, pairwise pooled AUC, within-block pair AUC, native LogLoss/Brier independently recomputed from1540savedforecasts')
    prereg = json.loads((HERE / 'Public/preregister.json').read_text())
    go = json.loads((HERE / 'Public/root-go-receipt.json').read_text())
    assert prereg['registered_utc'] < go['created_utc']
    for group in ['sklearn', 'tabpfn']:
        runtime = json.loads((HERE / f'Public/runtime-{group}.json').read_text())
        assert go['created_utc'] < runtime['utc']
        assert runtime['preregister_sha256'] == go['preregister_sha256'] == sha(HERE / 'Public/preregister.json')
        for name, digest in prereg['source_sha256'].items():
            assert sha(HERE / 'Source' / name) == digest == runtime['sources'][name]
    checks.append('Exact model/preprocessing/runner preregistration source hashes unchanged; registration precedes GO and both training runtimes')
    pairs = []
    for name in MODEL_CONFIG:
        base, si = [next(s for s in summaries if s['model'] == name and s['arm'] == arm) for arm in ['context', 'context_plus_SI']]
        entry = dict(model=name, n=base['n'], context_accuracy=base['accuracy'], SI_accuracy=si['accuracy'], accuracy_delta_SI_minus_context=si['accuracy']-base['accuracy'], context_pooled_auc=base['auc'], SI_pooled_auc=si['auc'], context_within_block_auc=base['within_block_auc']['auc'], SI_within_block_auc=si['within_block_auc']['auc'], within_block_auc_delta_SI_minus_context=si['within_block_auc']['auc']-base['within_block_auc']['auc'])
        if 'log_loss' in base:
            entry.update(context_log_loss=base['log_loss'], SI_log_loss=si['log_loss'], paired_log_loss_improvement=base['log_loss']-si['log_loss'], context_brier=base['brier'], SI_brier=si['brier'])
        pairs.append(entry)
    output = dict(status='FINISHED_AND_AUDITED', utc=utc_now(), binding=binding, preregister_sha256=sha(HERE / 'Public/preregister.json'), fixtures_sha256=sha(HERE / 'Public/fixtures.json'), total_fits=70, model_arms=14, forecasts_saved=1540, shared_cases=110, shared_dates=67, initial_training_cases=48, folds=5, primary_label=m['label'], test_SI15_known=8, test_SI60_known=26, pairs=pairs, train_prior_accuracy=summaries[0]['baseline']['accuracy'], train_prior_log_loss=summaries[0]['baseline']['log_loss'], checks=checks, fit_warnings=warnings_summary, maximum_linear_score_reconstruction_error=maximum_score_reconstruction_error, interpretation='Exploratory development-data model comparison. Sparse SI overlap gives low power; mixed or null changes do not prove that SI carries no information. No strategy gate, account/payout replay or deployment.', pooled_auc_caveat='Across-fold margins may have different scales; assess the within-block ranking separately. Final one-row fold has undefined AUC.', result_source_sha256={f'results-{g}.json':sha(HERE / f'Public/results-{g}.json') for g in ['sklearn','tabpfn']})
    save(HERE / 'Public/results-combined.json', output)
    save(HERE / 'Public/independent-acceptance.json', dict(status='PASS', utc=utc_now(), checks=checks, count=len(checks), maximum_linear_score_reconstruction_error=maximum_score_reconstruction_error, model_fits=70, saved_forecasts=1540, binding=binding))
    pd.DataFrame(pairs).to_csv(HERE / 'Public/model-pairs-summary.csv', index=False)
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
