"""Fixed settings declared before any corrected-cohort model fit."""
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
SEED = 20261121
CHECKPOINT = ROOT / 'outputs/AI-Forschung-20261121/Models/tabpfn-v2-classifier-finetuned-zk73skhh.ckpt'
CHECKPOINT_SHA256 = 'cf8c519c01eaf1613ee91239006d57b1c806ff5f23ac1aeb1315ba1015210e49'
MODEL_CONFIG = {
    'ML2_L1_LogisticRegression': dict(kind='LogisticRegression', C=.1, l1_ratio=1., solver='saga', max_iter=10000, tol=1e-5, fit_intercept=True, class_weight=None, random_state=SEED),
    'ML3_ElasticNet_LogisticRegression': dict(kind='LogisticRegression', C=.1, l1_ratio=.5, solver='saga', max_iter=10000, tol=1e-5, fit_intercept=True, class_weight=None, random_state=SEED),
    'ML4_RidgeClassifier': dict(kind='RidgeClassifier', alpha=1., solver='svd', fit_intercept=True, class_weight=None),
    'ML5_LinearSVC': dict(kind='LinearSVC', C=.1, penalty='l2', loss='squared_hinge', dual=False, tol=1e-5, max_iter=10000, fit_intercept=True, class_weight=None, random_state=SEED),
    'ML6_SGDClassifier_log_loss': dict(kind='SGDClassifier', loss='log_loss', penalty='l2', alpha=.0001, learning_rate='optimal', max_iter=10000, tol=1e-5, shuffle=False, early_stopping=False, average=False, fit_intercept=True, class_weight=None, random_state=SEED),
    'ML7_Perceptron': dict(kind='Perceptron', penalty=None, alpha=.0001, eta0=1., max_iter=10000, tol=1e-5, shuffle=False, early_stopping=False, fit_intercept=True, class_weight=None, random_state=SEED),
    'ML9_TabPFN_v2': dict(kind='TabPFN_v2', n_estimators=4, device='cpu', random_state=SEED, n_preprocessing_jobs=1, torch_threads=4, model_version='V2', checkpoint_sha256=CHECKPOINT_SHA256),
}
PROBABILITY_MODELS = {'ML2_L1_LogisticRegression', 'ML3_ElasticNet_LogisticRegression', 'ML6_SGDClassifier_log_loss', 'ML9_TabPFN_v2'}
