"""Compute the unchanged registered 199 draws in isolated CPU processes.

Operational speedup only: same ordered RNG draws, fitted models, statistics,
and checks as research.permutations. Compare every completed sequential draw.
"""
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from multiprocessing import get_context
import csv, hashlib, json
import numpy as np
from scipy.stats import spearmanr
from threadpoolctl import threadpool_limits
import research as r

def calculate(task):
    attempt, synthetic = task
    with threadpool_limits(limits=1):
        dates, rows, _, X, _ = r.dataset()
        correlations = {}; delta = 0.
        for arm in r.ARMS:
            scores = []; outcomes = []
            for _, train, test in r.original.splits(rows, dates):
                score, model = r.fit_score(arm, X, synthetic, train, test)
                if arm == 'ML9':
                    for k in [0, len(test)-1]:
                        single = float(model.predict_proba(X[[test[k]]])[0, 1])
                        assert np.isfinite(single)
                        delta = max(delta, abs(single-score[k]))
                scores.extend(score); outcomes.extend(synthetic[test])
            rho = spearmanr(scores, outcomes).statistic
            correlations[arm] = float(rho) if np.isfinite(rho) else 0.
        return attempt, correlations, delta

def main():
    r.check_registration()
    dates, rows, _, X, net = r.dataset()
    actual = {}; index = {row['ns']: i for i, row in enumerate(rows)}
    for arm in r.ARMS:
        p = [row for row in csv.DictReader((r.HERE/'Training'/arm/'predictions.csv').open()) if row['score']]
        actual[arm] = float(spearmanr([float(row['score']) for row in p],
            [net[index[int(row['signal_ns'])]] for row in p]).statistic)
    day_rows = defaultdict(list); grouped = defaultdict(list)
    for i, row in enumerate(rows):
        if row['day'] in dates: day_rows[row['day']].append(i)
    for day, ix in day_rows.items():
        grouped[(day[:4], (int(day[5:7])-1)//3, len(ix))].append(ix)
    singleton_days = sum(len(v) for v in grouped.values() if len(v) == 1)
    rng = np.random.default_rng(r.SEED+1); tasks = []
    for attempt in range(199):
        synthetic = net.copy()
        for days in grouped.values():
            for target, source in zip(days, rng.permutation(len(days)), strict=True):
                synthetic[target] = net[days[source]]
        tasks.append((attempt, synthetic))
    old = r.read(r.HERE/'Controls/family-sequential-partial.json')
    draw_hash = hashlib.sha256(np.stack([v for _, v in tasks]).tobytes()).hexdigest()
    provenance = dict(state='running',at_utc=datetime.now(timezone.utc).isoformat(),
        workers=4, draws=199, rng_seed=r.SEED+1, synthetic_draws_sha256=draw_hash,
        statistical_design_changed=False, research_sha256=r.sha(r.HERE/'research.py'),
        sequential_rows_to_reproduce=len(old), stop_if_any_sequential_row_differs=True)
    r.write(r.HERE/'Controls/parallel-execution.json', provenance)
    found = {}; max_delta = 0.
    with ProcessPoolExecutor(4, mp_context=get_context('spawn')) as pool:
        futures = [pool.submit(calculate, t) for t in tasks]
        for future in as_completed(futures):
            attempt, correlations, delta = future.result()
            if attempt < len(old):
                assert correlations == old[attempt], ('Sequential/parallel difference', attempt)
            found[attempt] = correlations; max_delta = max(max_delta, delta)
            if len(found) % 5 == 0 or len(found) == 199:
                r.write(r.HERE/'Controls/family-progress.json',
                    dict(state='running', completed=len(found), total=199, execution='4 isolated CPU processes'))
                print('all-family null',len(found),'/199',flush=True)
    draws = [found[i] for i in range(199)]
    maximum = [max(d.values()) for d in draws]
    result = dict(state='complete', draws=199, actual=actual,
        max_statistic_adjusted_upper_tail_rank={a:(1+sum(x >= v for x in maximum))/200 for a,v in actual.items()},
        max_statistic_q95=float(np.quantile(maximum,.95)),
        unchanged_singleton_stratum_sessions=singleton_days, total_candidate_sessions=len(day_rows),
        exchangeability_warning='Conditional whole-session vectors within quarter and count strata. Not a fresh OOS or universal significance claim.',
        threshold_free=True, native_cash_or_adoption_claim=False,
        TabPFN_null_batch_singleton_max_abs=float(max_delta),
        numerical_scope='Primary null scores use batched float32 inference; first/last singleton deviations are retained. Actual trading gates use singleton scores only.')
    r.write(r.HERE/'Controls/family-null-partial.json',draws)
    r.write(r.HERE/'Controls/family-null.json',result)
    r.write(r.HERE/'Controls/family-progress.json',result)
    provenance.update(state='complete',sequential_rows_reproduced_exactly=len(old),
        output_sha256=r.sha(r.HERE/'Controls/family-null.json'))
    r.write(r.HERE/'Controls/parallel-execution.json',provenance)

if __name__ == '__main__': main()
