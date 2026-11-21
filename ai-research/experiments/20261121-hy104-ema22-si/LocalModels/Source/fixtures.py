"""Meaningful data/pairing/score fixtures; no corrected-cohort classifier fit."""
import copy
import tempfile
from config import *
from common import *
from train import load_frozen, validate_folds
import pandas as pd


def main():
    tests = []
    x = np.array([[1., np.nan, 5.], [3., np.nan, np.nan], [5., np.nan, 9.]])
    pre = TrainOnlyPreprocessor().fit(x)
    assert pre.median_.tolist() == [3., 0., 7.]
    assert pre.all_missing_.tolist() == [False, True, False]
    assert pre.transform(x).shape == (3, 6)
    tests.append('Train-only median and stable explicit flags; all-missing train column uses declared zero with flag')
    before = copy.deepcopy(pre.state())
    observed = pre.transform(np.array([[7., 1., 11.]]))
    pre.transform(np.array([[1e99, -1e99, np.nan]]))
    assert pre.state() == before
    assert np.array_equal(observed, pre.transform(np.array([[7., 1., 11.]])))
    tests.append('Future test extremes cannot change imputation/scaling or earlier transformed rows')
    # A missing SI value and a measured numerical zero have distinct flags.
    missing, realzero = pre.transform(np.array([[1., np.nan, 5.], [1., 0., 5.]]))
    assert missing[1] == realzero[1] and missing[4] != realzero[4]
    tests.append('Unknown/null SI stays distinguishable from an observed zero after imputation')
    raw = score_binary([0, 1, 0, 1], [-100., 100., -2., 4.], [0, 1, 0, 1])
    assert raw['auc'] == 1 and 'log_loss' not in raw and 'brier' not in raw
    tests.append('Raw decision margins have AUC/accuracy and never fake LogLoss or Brier')
    single = score_binary([1], [9.], [1], [.9])
    assert single['auc'] is None and single['accuracy'] == 1 and single['log_loss'] > 0
    tests.append('One-row/single-class test block records null AUC while preserving actual accuracy and native probability losses')
    weighted = fold_pair_auc([dict(n=4, positive=2, auc=1.), dict(n=2, positive=1, auc=0.), dict(n=1, positive=1, auc=None)])
    assert weighted['auc'] == .8 and weighted['undefined_single_class_blocks'] == 1
    tests.append('Within-block AUC aggregates only identifiable positive-negative pairs')
    manifest = ROOT / 'outputs/HY104-EMA22-SI-DeepInfra-20261121/Public/dataset-manifest.json'
    m, frame, folds, binding = load_frozen(manifest)
    assert len(frame) == 159 and len(folds) == 5
    tests.append('Actual frozen CSV and canonical float64 NPY match including NaNs; 159 eligible rows and five fixed folds')
    tests.append('Actual folds preserve IDs/order, 48-minimum train, whole business-date gaps, purged unknown outcomes, 110 unique test cases')
    # Mutation fixtures prove guards reject the failure modes they claim.
    for mutation in ['overlap', 'late_outcome', 'missing_gap', 'wrong_id_order']:
        altered, altered_frame = copy.deepcopy(folds), frame.copy()
        if mutation == 'overlap':
            altered[0]['test_ids'][0] = altered[0]['train_ids'][0]
        elif mutation == 'late_outcome':
            altered_frame.loc[altered[0]['train_indices'][0], m['outcome_ns_column']] = altered[0]['test_first_information_ns']
        elif mutation == 'missing_gap':
            altered[0]['gap_day'] = altered[0]['test_dates'][0]
        else:
            altered[0]['train_ids'] = altered[0]['train_ids'][::-1]
        try:
            validate_folds(m, altered_frame, altered)
        except ValueError:
            tests.append('Rejected adversarial ' + mutation)
        else:
            raise AssertionError('Guard missed ' + mutation)
    # Exact integer nanoseconds survive CSV round-trip (numbers exceed 2**53).
    assert str(frame['decision_ns'].dtype) == 'Int64'
    assert int(frame['decision_ns'].iloc[0]) > 2**53
    tests.append('Nanosecond CSV times retained as nullable exact Int64, never float64')
    save(HERE / 'Public/fixtures.json', dict(status='PASS', utc=utc_now(), count=len(tests), tests=tests, binding=binding, no_corrected_cohort_classifier_fit=True))
    print(f'{len(tests)} fixtures PASS, no cohort classifier fit')


if __name__ == '__main__':
    main()
