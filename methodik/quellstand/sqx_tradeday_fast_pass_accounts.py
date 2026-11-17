"""TradeDay 2.0 Fast Pass 50k account replay from verified SQX fills."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from functools import lru_cache
from pathlib import Path
from statistics import mean, median
import subprocess
from tempfile import TemporaryDirectory

import sqx_offene_equity
from sqx_kontovergleich import HORIZON, adjust_path
from sqx_mff_budget_1000 import BUDGET, elapsed
from sqx_nq_annual_accounts import summary, verifier_source
from sqx_nq_open30_portfolio import nq_calendar
from sqx_rapid_payout_timeline import simulate, timeline
from sqx_tradeday_fast_pass import CASES, ENTRY_CASES, NEWS_LEAD_SECONDS, NQ, ROOT, digest, read, write_json


DISCOUNT_FEE = 9_900
LIST_FEE = 24_800
COMMISSION_PER_SIDE = 288
DRAWDOWN = 200_000
TARGET = 300_000
CONSISTENCY = 45
MIN_EVAL_DAYS = 3
MIN_PROFITABLE_DAYS = 5
WINNING_DAY = 15_000
MIN_WITHDRAWAL = 25_000
MAX_WITHDRAWAL = 150_000
SIM_SPLIT = 80
SIM_PAYOUTS = 5
INACTIVITY_DAYS = 30
CHECKPOINT_DAYS = 90
VARIANTS = tuple(CASES[i] for i in ENTRY_CASES)
BOARD = ROOT.parents[5] / 'HY-Forschung' / 'app' / 'static' / 'tradeday-results.json'


def consistent(best, profit):
    return 100 * best <= CONSISTENCY * profit


class FastPassAccount:
    def __init__(self, start, *, drawdown=DRAWDOWN, target=TARGET, winning_day=WINNING_DAY,
                 max_withdrawal=MAX_WITHDRAWAL):
        self.start = start
        self.drawdown, self.target = drawdown, target
        self.winning_day, self.max_withdrawal = winning_day, max_withdrawal
        self.balance = self.high = self.best = self.days = self.winning = 0
        self.paid_gross = self.cycle_start = 0
        self.limit = -drawdown
        self.passed = self.funded_start = self.last_trade = self.waiting = None
        self.payouts = []
        self.status = 'open_at_data_end'

    def begin_day(self, day):
        if self.waiting is not None:
            self.payouts.append(dict(date=day, **self.waiting))
            self.waiting = None
            if len(self.payouts) == SIM_PAYOUTS:
                self.status = 'sim_to_live_review'
            return 0
        if self.passed is None:
            return 1
        if self.funded_start is None:
            self.funded_start = day
            self.last_trade = None
        return 2

    def trade_day(self, day, phase, packet):
        net, low, count = packet
        if self.last_trade is not None and elapsed(self.last_trade, day) >= INACTIVITY_DAYS:
            self.status = 'inactive_model' if phase == 1 else 'funded_inactive'
            return
        if self.balance + low <= self.limit:
            self.status = 'max_loss_breached' if phase == 1 else 'funded_breached'
            return
        if count:
            self.last_trade = day
            self.days += 1
        elif self.last_trade is None:
            self.last_trade = self.start if phase == 1 else self.funded_start
        self.balance += net
        self.best = max(self.best, net)
        self.high = max(self.high, self.balance)
        self.limit = min(0, self.high - self.drawdown)
        if phase == 1:
            if self.days >= MIN_EVAL_DAYS and self.balance >= self.target and consistent(self.best, self.balance):
                self.passed = day
                self.balance = self.high = self.best = self.days = 0
                self.limit = -self.drawdown
            return

        self.winning += net >= self.winning_day
        if (self.winning >= MIN_PROFITABLE_DAYS and self.balance > self.cycle_start and self.balance > 0
                and consistent(self.best, self.balance + self.paid_gross)):
            gross = min(self.balance // 2, self.max_withdrawal)
            if gross >= MIN_WITHDRAWAL:
                self.balance -= gross
                self.paid_gross += gross
                self.cycle_start = self.balance
                self.winning = 0
                # The first request locks the floor at starting capital.
                self.high = max(self.high, self.drawdown)
                self.limit = 0
                self.waiting = dict(request_date=day, gross_cents=gross, net_cents=(gross * SIM_SPLIT + 50) // 100)

    def record(self, day):
        return dict(start=self.start, terminal_date=day, status=self.status,
                    evaluation_status='model_passed' if self.passed else 'not_passed',
                    evaluation_end=self.passed, funded_start=self.funded_start, payouts=self.payouts,
                    pending_payout=self.waiting)


def account(dates, evaluation, funded, **rules):
    state = FastPassAccount(dates[0], **rules)
    for day in dates:
        phase = state.begin_day(day)
        if phase:
            state.trade_day(day, phase, (evaluation if phase == 1 else funded)[day])
        if state.status != 'open_at_data_end':
            break
    return state.record(day)


def quote_paths(proofs):
    sqx_offene_equity.PILOT = NQ.out / 'Basisdaten'
    result = {case: {} for case in VARIANTS}
    with TemporaryDirectory(prefix='sqx-tradeday-bbo-') as temp, ThreadPoolExecutor(4) as pool:
        folder = Path(temp)
        source, binary = folder / 'paths.cpp', folder / 'paths'
        source.write_text(verifier_source(NQ))
        subprocess.run(['clang++', '-O3', '-std=c++17', str(source), '-lz', '-o', str(binary)], check=True)

        def segment(item):
            name, receipt = item
            paths = {}
            for ordinal, case in enumerate(VARIANTS):
                fill = receipt['cases'][case]
                path = Path(fill['fills'])
                if digest(path) != fill['sha256']:
                    raise ValueError(f'SQX fills changed: {name}/{case}')
                paths[str(ordinal)] = path
            marks = sqx_offene_equity.calculate(binary, name, folder, paths, dict.fromkeys(paths, (0, 0)))
            return {case: marks[str(index)] for index, case in enumerate(VARIANTS)}

        for block in pool.map(segment, proofs.items()):
            for case, days in block.items():
                if days.keys() & result[case].keys():
                    raise ValueError(f'Duplicate scoring session at rollover: {case}')
                result[case].update(days)
    return result


def compact(paths):
    return {
        day: (value['net_cents'], min(row[2] for row in value['path']), len(value['trades']))
        for day, value in paths.items()
    }


def payout_stats(runs):
    mean_cash = round(mean(r['end_bargeld'] for r in runs))
    stats = timeline(runs, mean_cash)
    stats['median_cash_end'] = median(r['end_bargeld'] for r in runs)
    latest = stats['daily'][CHECKPOINT_DAYS]
    stats['net_per_30d_through_90_mean'] = (latest['cash'] - BUDGET) / 3
    stats['net_per_30d_through_90_median'] = (latest['median_cash'] - BUDGET) / 3
    stats['max_funded_by_90'] = max(
        sum(q for start, end, q in r['funded'] if start <= day < end)
        for r in runs for day in range(CHECKPOINT_DAYS + 1)
    )
    first = [r['ledger'][0] for r in runs]
    passed = [r for r in first if r['evaluation_end']]
    stats['eval_first_purchase'] = dict(count=len(passed),
        median_days=median(elapsed(r['start'], r['evaluation_end']) for r in passed) if passed else None)
    stats['funded_loss_before_first_payout_first_purchase'] = sum(
        r['status'] == 'funded_breached' and not r['payouts'] for r in first)
    stats['terminal_status_first_purchase'] = dict(Counter(r['status'] for r in first))
    return stats


def publish_board(report):
    stats_fields = ('mean_cash_end', 'median_cash_end', 'median_challenge_fees',
                    'net_per_30d_through_90_mean', 'net_per_30d_through_90_median', 'max_funded_by_90',
                    'first', 'eval_first_purchase')
    rows = [{
        'case': case,
        **{mode: {'without_top10': modes[case]['net_without_top10_cents'],
                  'budgets': {price: {slots: {key: values[key] for key in stats_fields}
                                      for slots, values in price_data.items()}
                              for price, price_data in modes[case]['budgets'].items()}}
           for mode, modes in report['results'].items()}
    } for case in VARIANTS]
    if not BOARD.parent.is_dir():
        raise ValueError(f'TradeDay static directory is missing: {BOARD.parent}')
    write_json(BOARD, {key: report[key] for key in ('sessions', 'starts', 'period', 'horizon_sessions',
                                                   'budget_cents', 'monthly_period_days')} | {'rows': rows})


def summarize():
    segments = tuple(read(NQ.out / 'plan.json')['episodes'])
    proofs = {name: read(ROOT / 'SQX' / name / 'verified.json') for name in segments}
    clocks, test = nq_calendar()
    dates = sorted(test)
    raw = quote_paths(proofs)
    if any(set(stream) != test for stream in raw.values()):
        raise ValueError('SQX account path is missing a scoring session')
    count = len(dates) - HORIZON + 1
    rows = {}
    ledger = {}
    added_fee = COMMISSION_PER_SIDE - NQ.roundtrip_cents // 2
    for mode, stress in (('normal', 0), ('stress', 1)):
        runs = {case: {d: adjust_path(data, dict(open=clocks[d][0], close=clocks[d][1]),
                                     stress, added_fee, tick_cents=NQ.pnl_per_tick_cents)
                       for d, data in stream.items()} for case, stream in raw.items()}
        ev = compact(runs[VARIANTS[0]])
        rows[mode], ledger[mode] = {}, {}
        for case, paths in runs.items():
            fu = compact(paths)
            trades = sorted((t['net_pnl_cents'] for data in paths.values() for t in data['trades']), reverse=True)
            item = rows[mode][case] = dict(strategy=summary(paths), net_without_top10_cents=(
                sum(trades[10:]) if len(trades) > 10 else None), budgets={})
            ledger[mode][case] = {}

            @lru_cache(maxsize=None)
            def attempt(first, last):
                return account(dates[first:last], ev, fu)

            for price, fee, slots in (('sale', DISCOUNT_FEE, (1, 3, 5)), ('list', LIST_FEE, (1, 3, 4))):
                portfolio = item['budgets'][price] = {}
                for copies in slots:
                    accounts = [simulate(dates, i, attempt, copies, fee) for i in range(count)]
                    portfolio[copies] = payout_stats(accounts)
                    if copies == 1:
                        ledger[mode][case][price] = accounts
            print(mode, case, item['budgets']['sale'][1]['mean_cash_end']/100, flush=True)
    write_json(ROOT / 'Einzelstarts.json', ledger)
    report = dict(status='completed', provider='TradeDay',
        plan='Fast Pass 50k', provider_rules_date='2026-11-16', period=[dates[0], dates[-1]],
        sessions=len(dates), starts=count, horizon_sessions=HORIZON, budget_cents=BUDGET,
        commission_cents_per_side=COMMISSION_PER_SIDE, sale_fee_cents=DISCOUNT_FEE, list_fee_cents=LIST_FEE,
        monthly_period_days=CHECKPOINT_DAYS, news_lead_seconds=NEWS_LEAD_SECONDS,
        assumptions=[
            'All start windows use the current advertised one-time TradeDay 2.0 purchase terms.',
            'Three evaluation trade days per the product card. Sim Funded starts next session after passing.',
            'Request the maximum up to half of net account profit on the first eligible day. Apply 45% to lifetime gross profit and the largest Funded day.',
            'Credit on the next exchange session and skip trading it. Actual bank settlement and Rise fees are outside the model.',
            'End Sim Funded after the fifth payout. Earlier discretionary graduation, separate CME price-limit enforcement and the Live phase are outside the model.',
            'Simulate simultaneous synchronized accounts, fixed initial purchase budget with no reinvestment of payouts.',
            'Tick stress worsens both fills and leaves the SQX strategy signal timing fixed.'
        ], proofs=proofs, results=rows)
    write_json(ROOT / 'Ergebnisse.json', report)
    publish_board(report)


if __name__ == '__main__':
    summarize()
