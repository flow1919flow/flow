"""Produce payout timelines for the exact top five rows in each MFF plan."""
from argparse import ArgumentParser
from functools import lru_cache
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from sqx_annual_variants import normalize_account, write_json
from sqx_execution_sensitivity import calendar, scenario_path
from sqx_hycomb_end_cash import inputs
from sqx_indicator_payout_check import quote_paths
from sqx_kontovergleich import FEES, HORIZON, model
from sqx_mff_news_cash import account, evaluation
from sqx_rapid_payout_timeline import HERE, JOBS, simulate, timeline, read, BUDGET
from sqx_mff_budget_1000 import digest, elapsed
from sqx_nq_roc_followup import ROOT as NQ_ROOT
from sqx_ma_entry_study import ROOT as MA_ROOT


STATIC = HERE.parents[2] / 'HY-Forschung/app/static'


def publish_ledger(ledger, existing=None):
    """Publish the dates and cents for each modeled payment, without replay internals."""
    out = dict(existing or {})
    for key, modes in ledger.items():
        out[key] = {}
        for mode, samples in modes.items():
            for sample in samples:
                entries = []
                cum = 0
                for account in sample['ledger']:
                    assert account['accounts'] == 1
                    for p in account['payouts']:
                        day = elapsed(sample['start'],p['date'])
                        value = p['net_cents']
                        cum += value
                        fees = sum(v for d,v in sample['expense'].items() if int(d) <= day)
                        entries.append([p['date'], day, value, cum, BUDGET + cum - fees])
                assert cum == sum(sample['receipts'].values())
                assert sample['end_bargeld'] == BUDGET + cum - sum(sample['expense'].values())
                out[key].setdefault(sample['start'], {})[mode] = [
                    sample['end'], sample['end_bargeld'], entries]
    target = STATIC/'cash-payout-ledgers.json'
    with NamedTemporaryFile(mode='w', encoding='utf-8',dir=STATIC,delete=False) as f:
        json.dump({'rows':out},f,separators=(',',':'))
    target.with_name(f.name.rsplit('/',1)[-1]).replace(target)


def saved_nq_timelines():
    report = read(NQ_ROOT/'Portfolio-Vergleich.json')
    samples = read(NQ_ROOT/'Portfolio-Einzelstarts.json')
    key = report['nq_strategy']
    timelines, ledgers = {}, {}
    for plan, markets in report['results'].items():
        board_key = '|'.join((plan, key, key))
        timelines[board_key] = {mode: arms['1'] for mode, arms in markets['NQ'].items()}
        ledgers[board_key] = {mode: arms['1'] for mode, arms in samples[plan]['NQ'].items()}
        for mode, series in timelines[board_key].items():
            runs = ledgers[board_key][mode]
            assert len(runs) == report['starts']
            assert round(sum(run['end_bargeld'] for run in runs)/len(runs)) == series['mean_cash_end']
    return timelines, ledgers


def publish_saved_nq():
    timelines, ledgers = saved_nq_timelines()
    path = STATIC/'cash-timelines.json'
    board = read(path)
    board['rows'].update(timelines)
    write_json(path, board)
    publish_ledger(ledgers, read(STATIC/'cash-payout-ledgers.json')['rows'])


def ema22_timelines(board):
    plan = 'rapid_eod_50k'
    name = 'HY104-EMA22'
    candidates = [r for r in board['plans'][plan]['mff'] if r['key'] == name]
    if not candidates:
        return {}, {}
    row, = candidates
    key = '|'.join((plan, row['evaluation'], row['funded']))
    evidence = read(MA_ROOT/'Vergleich.json')
    dates, meta = calendar()
    assert (evidence['dates'], evidence['sessions']) == ([dates[0], dates[-1]], len(dates))
    paths = {}
    for job in JOBS:
        paths[job] = {}
        for phase, label in (('evaluation', 'EMA22'), ('funded', 'EMA20')):
            receipt = read(MA_ROOT/'SQX'/phase/job/'verified.json')[label]
            path = Path(receipt['fills'])
            if digest(path) != receipt['sha256']:
                raise ValueError(f'SQX source changed: {path}')
            paths[job][phase] = path
    raw = quote_paths(dates, paths)
    nb = model()
    runs, ledger = {key: {}}, {key: {}}
    for slip, mode in enumerate(('normal', 'stress')):
        ev = {('rapid', d): scenario_path(raw['evaluation'][d], meta[d], slip, slip) for d in dates}
        fu = {d: scenario_path(raw['funded'][d], meta[d], slip, slip) for d in dates}

        @lru_cache(maxsize=None)
        def attempt(a, b):
            window = dates[a:b]
            return normalize_account(account(plan, window, evaluation(nb, plan, window, ev), fu), window)

        samples = [simulate(dates, i, attempt, 1, FEES[plan]) for i in range(len(dates)-HORIZON+1)]
        result = evidence['cash'][str(slip)][f'{plan}/evaluation/EMA22']
        assert [s['end_bargeld']-BUDGET for s in samples] == result['net_by_start_cents']
        target = round(row[mode]['cash'] * 100)
        summary = timeline(samples, target)
        assert (summary['mean_cash_end'], summary['first']['count'], summary['first']['median_days']) == (
            target, row[mode]['paid'], row[mode]['days'])
        runs[key][mode], ledger[key][mode] = summary, samples
        print(name, mode, 'gebühren, horizon, ziel', summary['median_challenge_fees'],
              summary['days_each_end'], summary['reaches_target'], flush=True)
    return runs, ledger


def main(ema22_only=False):
    board = read(STATIC/'cash-rankings.json')
    if ema22_only:
        runs, ledger = ema22_timelines(board)
        if not runs:
            raise ValueError('HY104-EMA22 is missing from the published cash ranking')
        current = read(STATIC/'cash-timelines.json')
        current['rows'].update(runs)
        publish_ledger(ledger, read(STATIC/'cash-payout-ledgers.json')['rows'])
        write_json(STATIC/'cash-timelines.json', current)
        return
    archived = read(HERE/'SQX-HYcomb-Endbargeld.json')['results']
    members = {(plan, r['evaluation'], r['funded']):r for plan,group in board['plans'].items()
               for r in group['mff'][:5] if r['evaluation'] in archived and r['funded'] in archived}
    labels = {f'evaluation-{e}' for _,e,_ in members} | {f'funded-{f}' for _,_,f in members}
    paths, links, *_ = inputs()
    paths = {j:{label:paths[j][links[label][j]] for label in sorted(labels)} for j in JOBS}
    dates, meta = calendar()
    print('Loading',len(labels),'distinct sources per segment', flush=True)
    raw = quote_paths(dates, paths)
    nb = model()
    runs = {}
    ledger = {}
    for slip in (0,1):
        marked = {k:{d:scenario_path(v,meta[d],slip,slip) for d,v in block.items()} for k,block in raw.items()}
        for (plan,e,f), row in members.items():
            record, = [a for a in archived[f if f != 'HY104' and f != 'HY85' else e]
                       if a['plan']==plan and a['evaluation']==e and a['funded']==f
                       and a['adverse_ticks_each_side']==slip]
            cash = round(100*row['stress' if slip else 'normal']['cash'])
            ev = {('rapid', d):p for d,p in marked[f'evaluation-{e}'].items()}
            fu = marked[f'funded-{f}']
            @lru_cache(maxsize=None)
            def attempt(a,b):
                win = dates[a:b]
                return normalize_account(account(plan,win,evaluation(nb,plan,win,ev),fu),win)
            samples = [simulate(dates,i,attempt,1,FEES[plan]) for i in range(len(dates)-HORIZON+1)]
            attempt.cache_clear()
            assert [r['end_bargeld']-BUDGET for r in samples] == record['net_by_start_cents']
            measures = timeline(samples,cash)
            assert measures['mean_cash_end'] == cash
            assert measures['first']['count'] == record['budget']['first_paid']
            key = '|'.join((plan,e,f))
            kind = 'stress' if slip else 'normal'
            runs.setdefault(key,{})[kind] = measures
            ledger.setdefault(key,{})[kind] = samples
            print(plan,e,f,kind,cash, flush=True)
    write_json(HERE/'SQX-MFF-Auszahlungsverlauf-Einzelstarts.json',ledger)
    timelines, nq_ledgers = saved_nq_timelines()
    runs.update(timelines)
    ledger.update(nq_ledgers)
    ema_runs, ema_ledger = ema22_timelines(board)
    runs.update(ema_runs)
    ledger.update(ema_ledger)
    write_json(STATIC/'cash-timelines.json',{'starts':board['starts'],'horizon':HORIZON,'rows':runs})
    publish_ledger(ledger)


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--ema22-only', action='store_true')
    main(parser.parse_args().ema22_only)
