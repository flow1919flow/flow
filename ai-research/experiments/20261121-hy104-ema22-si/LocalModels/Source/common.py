import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    temp.replace(path)


class TrainOnlyPreprocessor:
    """Median imputation, one missing flag per column, then train-only scaling.

    All-missing training columns use the preregistered constant zero. Their
    missing flags remain available. No test-derived feature selection occurs.
    """
    def fit(self, x):
        x = np.asarray(x, dtype=np.float64)
        if x.ndim != 2 or np.isinf(x).any():
            raise ValueError('Expected a 2D finite-or-NaN feature matrix')
        self.width_ = x.shape[1]
        self.all_missing_ = np.isnan(x).all(axis=0)
        self.median_ = np.array([np.median(v[~np.isnan(v)]) if (~np.isnan(v)).any() else 0. for v in x.T])
        augmented = self._augment(x)
        self.mean_ = augmented.mean(axis=0)
        self.scale_ = augmented.std(axis=0)
        self.scale_[self.scale_ == 0] = 1.
        return self

    def _augment(self, x):
        missing = np.isnan(x)
        return np.column_stack((np.where(missing, self.median_, x), missing.astype(float)))

    def transform(self, x):
        x = np.asarray(x, dtype=np.float64)
        if x.ndim != 2 or x.shape[1] != self.width_ or np.isinf(x).any():
            raise ValueError('Feature width changed or infinity in features')
        return (self._augment(x) - self.mean_) / self.scale_

    def state(self):
        return {k: getattr(self, k).tolist() for k in ['median_', 'all_missing_', 'mean_', 'scale_']}


def score_binary(y, raw_score, prediction, probability=None):
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score, log_loss, brier_score_loss
    y, raw_score, prediction = map(np.asarray, (y, raw_score, prediction))
    out = {'n': int(len(y)), 'positive': int(y.sum()), 'accuracy': float(accuracy_score(y, prediction)),
           'balanced_accuracy': float(balanced_accuracy_score(y, prediction)) if len(np.unique(y)) == 2 else None,
           'auc': float(roc_auc_score(y, raw_score)) if len(np.unique(y)) == 2 else None,
           'auc_status': 'ok' if len(np.unique(y)) == 2 else 'undefined_single_test_class'}
    if probability is not None:
        p = np.asarray(probability)
        if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
            raise ValueError('Invalid actual probability output')
        out.update(log_loss=float(log_loss(y, np.column_stack((1-p, p)), labels=[0, 1])),
                   brier=float(brier_score_loss(y, p)))
    return out


def fold_pair_auc(block_metrics):
    valid = [m for m in block_metrics if m['auc'] is not None]
    weights = [m['positive'] * (m['n'] - m['positive']) for m in valid]
    return {'auc': float(np.average([m['auc'] for m in valid], weights=weights)) if sum(weights) else None,
            'weight': 'positive_negative_pairs_within_each_block', 'eligible_blocks': len(valid),
            'undefined_single_class_blocks': len(block_metrics) - len(valid)}
