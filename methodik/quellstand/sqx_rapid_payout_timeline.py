"""Cash and funding timelines from the locked SQX Rapid EOD trade pair."""
from bisect import bisect_right
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from statistics import mean, median, quantiles

from sqx_annual_variants import normalize_account, write_json
from sqx_execution_sensitivity import calendar, scenario_path
from sqx_indicator_payout_check import quote_paths
from sqx_mff_budget_1000 import BUDGET, LOSSES, chain, elapsed, stats
from sqx_mff_news_cash import account, evaluation
from sqx_rapid_size2 import HERE, JOBS, OUT, PHASES, SECTION, digest, prior, read
from sqx_kontovergleich import FEES, HORIZON, model


PLAN = 'rapid_eod_50k'
FEE = FEES[PLAN]
KEY = 'HY104 → HYcomb-28-HY104-03'
FUNDED = 'HYcomb-28-HY104-03'
CHECKPOINTS = [0, 15, 30, 45, 50, 60, 75, 84, 90, 100, 120]


def scale(path, size):
    if size == 1:
        return path
    return {**path, 'net_cents': path['net_cents'] * size,
            'path': [[t, k, eq * size, cash * size, *rest] for t,k,eq,cash,*rest in path['path']],
            'trades': [{**t, 'net_pnl_cents': t['net_pnl_cents'] * size} for t in path['trades']]}


def simulate(dates, origin, attempt, slots, fee=FEE, *, budget=BUDGET):
    limit = origin + HORIZON
    i = origin
    cohorts = []
    spent = 0
    width = slots
    while i < limit and spent + fee <= budget:
        qty = min(width, (budget - spent) // fee)
        row = attempt(i, limit)
        cohorts.append((qty, row))
        spent += qty * fee
        if row['status'] not in LOSSES:
            break
        i = bisect_right(dates, row['terminal_date'], lo=i + 1, hi=limit)
        width = qty
    start, end = dates[origin], dates[limit-1]
    spend, paid, funded, ledger = {}, {}, [], []
    for qty, row in cohorts:
        d = elapsed(start, row['start'])
        spend[d] = spend.get(d, 0) + qty * fee
        for event in row['payouts']:
            d = elapsed(start, event['date'])
            paid[d] = paid.get(d, 0) + qty * event['net_cents']
        if row['funded_start']:
            last = elapsed(start, row['terminal_date'])
            funded.append((elapsed(start, row['funded_start']),
                           last + (row['status'] == 'open_at_data_end'), qty))
        ledger.append({'accounts':qty, **row})
    return dict(start=start, end=end, expense=spend, receipts=paid, funded=funded, ledger=ledger,
                end_bargeld=budget - sum(spend.values()) + sum(paid.values()))


def timeline(runs, target, *, budget=BUDGET):
    if max(CHECKPOINTS) > min(elapsed(r['start'], r['end']) for r in runs):
        raise ValueError('Unequal date coverage at a displayed checkpoint')
    daily_end = min(elapsed(r['start'], r['end']) for r in runs)
    daily = []
    targets, pay_times, pay_sizes = [], [], []
    milestones = {}
    for row in runs:
        first = min(row['receipts'], default=None)
        if first is not None:
            pay_times.append(first)
            pay_sizes.append(row['receipts'][first])
        dates = sorted(row['expense'].keys() | row['receipts'].keys())
        cash = budget
        for d in dates:
            cash += row['receipts'].get(d, 0)-row['expense'].get(d, 0)
            if cash >= target:
                targets.append(d)
                break
        payouts = sorted(row['receipts'].items())
        for n,(d,p) in enumerate(payouts, start=1):
            milestones.setdefault(n, []).append((d,p,sum(v for _,v in payouts[:n])))
    for cutoff in range(daily_end + 1):
        cash, out, fees, occupancy = [], [], [], []
        for row in runs:
            got = sum(v for k,v in row['receipts'].items() if k <= cutoff)
            spent = sum(v for k,v in row['expense'].items() if k <= cutoff)
            out.append(got)
            fees.append(spent)
            cash.append(budget + got - spent)
            occupancy.append(sum(q for a,b,q in row['funded'] if a <= cutoff < b))
        daily.append(dict(day=cutoff, receipts=round(mean(out)), cash=round(mean(cash)),
                          median_cash=median(cash), fees=round(mean(fees)),
                          any_paid=sum(v > 0 for v in out), funded=mean(occupancy)))
    q1, _, q3 = quantiles(pay_times, n=4) if len(pay_times)>1 else (None,None,None)
    return dict(starts=len(runs), daily=daily, mean_cash_end=round(mean(r['end_bargeld'] for r in runs)),
                mean_challenge_fees=round(mean(sum(r['expense'].values()) for r in runs)),
                median_challenge_fees=round(median(sum(r['expense'].values()) for r in runs)),
                days_each_end=[min(elapsed(r['start'],r['end']) for r in runs),
                               max(elapsed(r['start'],r['end']) for r in runs)],
                first=dict(count=len(pay_times), median_days=median(pay_times) if pay_times else None,
                           day_q1=q1, day_q3=q3, median_cents=median(pay_sizes) if pay_sizes else None),
                reaches_target=dict(target=target, count=len(targets),
                                    median_days=median(targets) if targets else None),
                milestones=[dict(n=n, count=len(seq), median_days=median(d for d,_,_ in seq),
                                 median_amount=median(p for _,p,_ in seq),
                                 median_cumulative=median(c for _,_,c in seq))
                            for n,seq in sorted(milestones.items())],
                mean_funded_through_day_90=mean(d['funded'] for d in daily[:91]))


def main():
    dates, meta = calendar()
    paths = {job:{phase:prior(job, phase) for phase in PHASES} for job in JOBS}
    reference = read(HERE/'SQX-HYcomb-Endbargeld.json')['results'][FUNDED]
    receipts = [read(SECTION/phase/job/'verified.json') for phase in PHASES for job in JOBS
                if (SECTION/phase/job/'verified.json').exists()]
    doubled = len(receipts) == len(JOBS)*len(PHASES)
    if doubled and not all(digest(Path(r['fills'])) == r['sha256'] for r in receipts):
        raise ValueError('Native 2 ES fills changed after verification')
    print('Read sealed SQX fills and quote paths', flush=True)
    raw = quote_paths(dates, paths)
    nb = model()
    count = len(dates)-HORIZON+1
    cases = {}
    ledger = {}
    for slip in (0,1):
        benchmark, = [r for r in reference if r['plan'] == PLAN and r['adverse_ticks_each_side'] == slip
                      and r['evaluation'] == 'HY104' and r['funded'] == FUNDED]
        target = round(BUDGET + benchmark['budget']['end_net_mean_cents'])
        for size in ((1,2) if doubled else (1,)):
            ev = {('rapid', d):scale(scenario_path(raw['evaluation'][d], meta[d], slip, slip), size) for d in dates}
            fu = {d:scale(scenario_path(raw['funded'][d], meta[d], slip, slip), size) for d in dates}
            @lru_cache(maxsize=None)
            def attempt(i,j):
                window = dates[i:j]
                return normalize_account(account(PLAN,window,evaluation(nb,PLAN,window,ev),fu),window)
            for slots in ((1,3) if size == 1 else (1,)):
                key = f'{size}es-{slots}parallel-{slip}tick'
                runs = [simulate(dates,i,attempt,slots) for i in range(count)]
                cases[key] = item = timeline(runs, target)
                ledger[key] = runs
                if slots == 1:
                    check = [chain(dates,i,FEE,attempt) for i in range(count)]
                    assert all(r['end_bargeld'] == BUDGET + c['net_cents'] for r,c in zip(runs,check,strict=True))
                    if size == 1:
                        assert item['mean_cash_end'] == target
                        assert [r['end_bargeld']-BUDGET for r in runs] == benchmark['net_by_start_cents']
                    singles = [r['ledger'][0] for r in runs]
                    item['first_eval_passed'] = sum(r['evaluation_status']=='model_passed' for r in singles)
                    item['first_eval_median_days'] = median(elapsed(r['start'],r['evaluation_end']) for r in singles
                                                            if r['evaluation_status']=='model_passed')
                    item['legacy_summary'] = stats(check)
                print(key, item['mean_cash_end']/100, item['first'], flush=True)
            attempt.cache_clear()
    write_json(OUT/'Auszahlungsverlauf-Einzelstarts.json', ledger)
    write_json(OUT/'Auszahlungsverlauf.json',
               dict(key=KEY, plan=PLAN, starts=count, horizon=HORIZON, budget=BUDGET, fee=FEE,
                    checkpoints=CHECKPOINTS, cases=cases))


if __name__ == '__main__':
    main()
