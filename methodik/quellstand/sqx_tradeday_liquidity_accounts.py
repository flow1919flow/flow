"""Apply the same Fast Pass rules to separately filled, shared-book portfolios."""

from collections import Counter, defaultdict
from csv import reader
from pathlib import Path

from sqx_kontovergleich import HORIZON
from sqx_mff_budget_1000 import BUDGET, LOSSES, elapsed
from sqx_nq_open30_portfolio import nq_calendar
from sqx_tradeday_fast_pass import NQ, ROOT, digest, read, write_json
from sqx_tradeday_fast_pass_accounts import BOARD, FastPassAccount
from sqx_tradeday_liquidity import OUT, PORTFOLIO_OUT
from sqx_tradeday_plan_comparison import FEES, TIERS, timeline_and_journal


PROFILES = ((50, 1, 1), (50, 1, 2), (100, 2, 1), (100, 2, 2))


def load_marks(*, portfolio=False):
    source_path = PORTFOLIO_OUT if portfolio else OUT
    proof = read(source_path / 'Quote-Pfade-Nachweis.json')['segments']
    result = {}
    quality = defaultdict(Counter)
    for contract, source in proof.items():
        path = Path(source['marks'])
        if digest(path) != source['marks_sha256']:
            raise ValueError(f'Quote-path receipt changed: {contract}')
        sessions = read(NQ.out / 'Basisdaten' / contract / 'staged.json')['sessions']
        with path.open(newline='') as stream:
            for line in reader(stream):
                i, quantity, first, second, slot, net, low, stressed, stress_low, count, legs, delayed, delay_ns, price_cost, missed, overlap = map(int, line)
                if sessions[i]['role'] != 'test':
                    if legs:
                        raise ValueError(f'Fills in warmup: {contract}')
                    continue
                day = sessions[i]['day']
                key = (day, quantity, first, second, slot)
                if key in result:
                    raise ValueError(f'Duplicate daily execution packet: {key}')
                result[key] = ((net, low, count), (stressed, stress_low, count))
                audit = quality[quantity, first, second, slot]
                audit.update(dict(legs=legs, delayed=delayed, cost_ticks=price_cost, missing_entry_lots=missed,
                                  skipped_orders=overlap))
                audit['max_delay_ns'] = max(audit['max_delay_ns'], delay_ns)
    return result, {'/'.join(map(str, key)): dict(value) for key, value in quality.items()}


def simulate(dates, marks, size, quantity, copies, fee, stress, *, tier=None, budget=BUDGET,
             portfolio=False):
    # A slot receives its replacement on the next session after a model loss.
    tier = TIERS[size] if tier is None else tier
    attempts = []
    slots = [None] * copies
    remaining = budget
    expense = Counter()
    for day in dates:
        for index, state in enumerate(slots):
            if state is None and remaining >= fee:
                slots[index] = FastPassAccount(day, drawdown=tier.drawdown, target=tier.target,
                                               winning_day=tier.fast_profit_day, max_withdrawal=tier.fast_payout_cap)
                remaining -= fee
                expense[elapsed(dates[0], day)] += fee

        active = [(i, state, phase) for i, state in enumerate(slots)
                  if state is not None and state.status == 'open_at_data_end'
                  if (phase := state.begin_day(day))]
        if active:
            phases = [entry[2] for entry in active]
            if portfolio:
                code = 0
                for phase in phases:
                    code = 3 * code + phase
                profile = len(phases), code
            else:
                profile = phases + [0] * (2 - len(active))
            for order, (_, state, phase) in enumerate(active):
                state.trade_day(day, phase, marks[day, quantity, *profile, order][stress])

        for index, state in enumerate(slots):
            if state is not None and state.status in LOSSES:
                attempts.append(dict(slot=index + 1, **state.record(day)))
                slots[index] = None
            elif state is not None and state.status == 'sim_to_live_review':
                if not getattr(state, 'terminal_day', None):
                    state.terminal_day = day

    for i, state in enumerate(slots):
        if state is not None:
            attempts.append(dict(slot=i + 1, **state.record(getattr(state, 'terminal_day', dates[-1]))))
    records = sorted(attempts, key=lambda a: (a['start'], a['slot']))
    events = []
    receipts = Counter()
    funded = []
    for a in records:
        for p in a['payouts']:
            receipts[elapsed(dates[0], p['date'])] += p['net_cents']
            events.append(dict(slot=a['slot'], **p))
        if a['funded_start']:
            funded.append((elapsed(dates[0], a['funded_start']), elapsed(dates[0], a['terminal_date'])
                           + (a['status'] == 'open_at_data_end'), 1))
    end_cash = remaining + sum(receipts.values())
    if end_cash != budget - sum(expense.values()) + sum(p['net_cents'] for p in events):
        raise ValueError('Purchase or payout reconciliation failed')
    return dict(start=dates[0], end=dates[-1], expense=dict(expense), receipts=dict(receipts),
                funded=funded, ledger=records, events=sorted(events, key=lambda e: (e['date'], e['slot'])),
                end_bargeld=end_cash)


def main():
    previous = read(ROOT / 'Ergebnisse.json')
    _, calendar = nq_calendar()
    dates = sorted(calendar)
    count = len(dates) - HORIZON + 1
    marks, checks = load_marks()
    if len(marks) != len(dates) * 24 or any(quality['skipped_orders'] for quality in checks.values()):
        raise ValueError('Daily paired quote coverage is incomplete or contains overlapping signals')
    results, ledgers = {}, {}
    for size, quantity, copies in PROFILES:
        key = f'{size}k-{copies}x{quantity}NQ'
        results[key] = dict(size=size, quantity=quantity, copies=copies, rates={})
        for name, fee in zip(('sale', 'list'), FEES['fast_pass'][size], strict=True):
            model = results[key]['rates'][name] = dict(fee=fee)
            for label, stress in (('normal', 0), ('stress', 1)):
                runs = [simulate(dates[i:i + HORIZON], marks, size, quantity, copies, fee, stress) for i in range(count)]
                summary, curve, journal = timeline_and_journal(runs)
                if size == 50 and quantity == 1 and copies == 1:
                    baseline = previous['results'][label]['SMA5/10 nach Außenbruch']['budgets'][name]['1']
                    if (summary['end_mean'], summary['end_median']) != (baseline['mean_cash_end'], baseline['median_cash_end']):
                        raise ValueError(f'Solo 1 NQ control changed: {name}/{label}')
                model[label] = dict(summary=summary, timeline=curve)
                ledger = ledgers.setdefault(f'{key}|{name}', {})
                for day, case in journal.items():
                    ledger.setdefault(day, {})[label] = case
            print(key, name, model['normal']['summary']['monthly_mean'] / 100,
                  model['stress']['summary']['monthly_mean'] / 100, flush=True)
    report = dict(status='completed', period=[dates[0], dates[-1]], sessions=len(dates), starts=count,
                  horizon=HORIZON, budget_cents=BUDGET, profiles=results, quote_quality=checks,
                  assumptions=[
                      'Frozen SQX execution times trigger market orders. Use shared displayed TBBO capacity.',
                      'A residual order waits for a price change or net displayed replenishment. Exits have priority, then the first account.',
                      'Separate account states, replacement purchases and payout pauses. No orders overnight; on a breach day the other path uses the full day demand precomputed for both slots.',
                      'TBBO observes book snapshots at market trades. Market depth, intervening book events, broker latency and queue priority are unknown.',
                      'Additional stress adds one adverse tick to each filled contract on each side.',
                      'Same Fast Pass fee, Sim Funded rules and 30-day cash definition as the preceding plan comparison.'
                  ])
    write_json(OUT / 'Ergebnisse.json', report)
    write_json(BOARD.with_name('tradeday-liquidity.json'), report)
    write_json(BOARD.with_name('tradeday-depth-ledgers.json'), dict(rows=ledgers))


if __name__ == '__main__':
    main()
