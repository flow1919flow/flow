"""Write before cohort fitting; schema/freeze binding is a separate receipt."""
from config import *
from common import *

save(HERE / 'Public/preregister.json', {
    'registered_utc': utc_now(), 'task': 'Native HY104 EMA22 strategy-outcome classification, context vs context plus SI',
    'status_at_registration': 'No corrected-cohort fits; dataset pending freeze and parent go-ahead',
    'seed': SEED, 'models': MODEL_CONFIG, 'fit_matrix': 'Each fixed classifier independently in both arms, on the identical frozen fold IDs; no search',
    'source_policy': 'Correct 348 native trades in 242-session year; main cohort after ES SI archive starts; never use old 347 C28.03 or standalone SI15m labels',
    'targets': {'primary': 'Frozen y: actual native strategy exit net after normalized roundtrip 5.74 USD, then additional 25 USD cost stress > 0; not a fixed 15-minute markout'},
    'splits': {'initial_training_eligible_trades': 48, 'test_block_business_days': 20, 'whole_business_day_gap': 1, 'purge': 'Training outcomes must be known strictly before frozen test information cutoff', 'fold_source': 'Canonical dataset builder; no local fold optimization'},
    'preprocessing': {'fit_rows': 'training only', 'missing_values': 'column train median, zero if all train values missing', 'missing_indicators': 'One indicator per input feature, always present', 'scaling': 'Train means and population standard deviations after imputation and indicator append; zero standard deviations become one', 'SI_absence': 'Null is unknown, never evidence of no SI; coverage status provided as explicit numeric features'},
    'prediction': {'TabPFN': 'One test row per predict_proba call; official V2 checkpoint, CPU, no cloud; categorical indices side, SI_status_code when present, and every appended missing flag', 'others': 'Native predict and native predict_proba only for models that implement it; decision_function retained as raw scores', 'probability_clip_for_scoring': 'Only sklearn log_loss numerical endpoint handling; actual probabilities saved unmodified', 'calibration': 'None; no test fitted calibration'},
    'shortages': {'one_training_class': 'Skip both arms of that model/fold/target with explicit reason', 'minority_n1': 'Fit fixed settings; record counts and warnings; no synthetic samples', 'one_test_class': 'Save forecasts/accuracy; AUC undefined null, with reason', 'fit_failure': 'Retain error, stop model pair; do not silently switch algorithms'},
    'metrics': {'primary': ['accuracy', 'AUC within each chronological block', 'positive-negative-pair weighted within-block AUC'], 'descriptive_only': ['Pooled AUC across folds; margin scale may vary by fold'], 'native_probability_only': ['LogLoss', 'Brier'], 'baseline': 'Train-only Laplace positive prior, no fitted features', 'selection': 'No winner deployment, threshold search, gate, native SQX job or payout claim'},
    'limits': ['Selected historical year is development data, not fresh OOS', 'Very sparse SI overlap and incomplete feed uptime limit inference', 'Strategy outcomes are not portfolio payouts', 'Seven model families and two arms are exploratory multiple comparisons'],
    'execution': {'checkpoint_sha256': CHECKPOINT_SHA256, 'model_runtime': 'work/tools/tabpfn/.venv Python3.12; sklearn runtime work/tools/mlflow/.venv', 'network': 'HF_HUB_OFFLINE=1, DO_NOT_TRACK=1; no API/GPU/orders'},
    'source_sha256': {p.name: sha(p) for p in sorted((HERE / 'Source').glob('*.py'))},
})
print('Registered fixed settings before cohort fits')
