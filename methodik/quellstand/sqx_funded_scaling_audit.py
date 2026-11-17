"""Compare cash at calendar day 90 from verified ES and NQ annual paths."""

from argparse import ArgumentParser
from statistics import mean, median

from sqx_mff_budget_1000 import BUDGET, elapsed
from sqx_nq_open30_portfolio import nq_calendar
from sqx_rapid_payout_timeline import FEE, HORIZON, OUT as MFF, read, write_json
from sqx_tradeday_liquidity import OUT as TRADEDAY
from sqx_tradeday_liquidity_accounts import load_marks, simulate
from sqx_tradeday_plan_comparison import FEES, Tier


FAST_PASS_25K = Tier(150_000, 100_000, 10_000, 75_000, (1,))
FAST_PASS_FEES = {25: (6900, 17300), **FEES['fast_pass']}


def cash_90(run):
    received = sum(amount for day, amount in run['receipts'].items() if int(day) <= 90)
    spent = sum(amount for day, amount in run['expense'].items() if int(day) <= 90)
    return received - spent, received > 0


def replay_mff(row, slots):
    remaining = BUDGET
    received = 0
    for account in row['ledger']:
        width = min(slots, remaining // FEE)
        if not width or elapsed(row['start'], account['start']) > 90:
            break
        remaining -= width * FEE
        received += width * sum(event['net_cents'] for event in account['payouts']
                                if elapsed(row['start'], event['date']) <= 90)
    return remaining - BUDGET + received, received > 0


def summarize(outcomes):
    outcomes = list(outcomes)
    net = [balance for balance, _ in outcomes]
    p10 = sorted(net)[int(0.10 * (len(net) - 1))]
    return dict(monthly_mean=round(mean(net) / 300, 2), monthly_median=round(median(net) / 300, 2),
                monthly_p10=round(p10 / 300, 2),
                paid=sum(paid for _, paid in outcomes), positive=sum(amount > 0 for amount in net),
                starts=len(net))


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--ema22', action='store_true', help='Rebuild the exact EMA22 leaderboard cash paths')
    args = parser.parse_args()
    mff = read(MFF / 'Auszahlungsverlauf-Einzelstarts.json')
    ema22 = None
    if args.ema22:
        from sqx_mff_top_payout_timelines import STATIC, ema22_timelines

        _, by_strategy = ema22_timelines(read(STATIC / 'cash-rankings.json'))
        ema22, = by_strategy.values()
    reference = read(TRADEDAY / 'Ergebnisse.json')['profiles']
    marks, _ = load_marks()
    dates = sorted(nq_calendar()[1])
    windows = [dates[i:i + HORIZON] for i in range(len(dates) - HORIZON + 1)]
    reports = {}
    for stress, mode in enumerate(('normal', 'stress')):
        single = mff[f'1es-1parallel-{stress}tick']
        triple = mff[f'1es-3parallel-{stress}tick']
        assert [row['start'] for row in single] == [window[0] for window in windows]
        assert [row['start'] for row in triple] == [row['start'] for row in single]
        assert all(replay_mff(row, 1) == cash_90(row) for row in single)
        assert all(replay_mff(row, 3) == cash_90(control)
                   for row, control in zip(single, triple, strict=True))
        if ema22 is not None:
            single = ema22[mode]
            assert [row['start'] for row in single] == [window[0] for window in windows]
            assert all(replay_mff(row, 1) == cash_90(row) for row in single)
        es = {n: [replay_mff(row, n) for row in single] for n in (1, 2, 3)}
        td = {}
        pairs = {}
        for size, fees in FAST_PASS_FEES.items():
            tier = FAST_PASS_25K if size == 25 else None
            for quantity in tier.sizes if tier else (1, 2):
                for slots in (1, 2):
                    for label, fee in zip(('sale', 'list'), fees, strict=True):
                        if slots * fee > BUDGET:
                            continue
                        key = f'{size}k-{slots}x{quantity}NQ'
                        results = [cash_90(simulate(window, marks, size, quantity, slots, fee, stress, tier=tier))
                                   for window in windows]
                        values = summarize(results)
                        if key in reference:
                            baseline = reference[key]['rates'][label][mode]['summary']
                            assert values['monthly_mean'] == round(baseline['monthly_mean'] / 100, 2)
                            assert values['monthly_median'] == round(baseline['monthly_median'] / 100, 2)
                        td[f'{key}|{label}'] = values
                        if key == '50k-2x1NQ':
                            for n, outcomes in es.items():
                                pairs[f'{n}es+{key}|{label}'] = summarize(
                                    (left + right, a or b)
                                    for (left, a), (right, b) in zip(outcomes, results, strict=True))
        reports[mode] = dict(mff={n: summarize(values) for n, values in es.items()},
                             tradeday=td, paired=pairs)
    result = dict(period=[dates[0], dates[-1]], starts=len(windows), budget_per_provider=BUDGET / 100,
                  cutoff_calendar_days=90, reports=reports,
                  mff_evaluation='HY104-EMA22' if args.ema22 else 'HY104',
                  mff_funded='HYcomb-28-HY104-03, identical fills per parallel account',
                  tradeday='HY3 EMA20 → SMA5/10, shared visible TBBO, phase and cash tracked by slot',
                  paired='Same calendar start, separate budgets, sum cash flows by start')
    path = TRADEDAY / ('Skalierung-90-Tage-EMA22.json' if args.ema22 else 'Skalierung-90-Tage.json')
    write_json(path, result)
    print(path, flush=True)


if __name__ == '__main__':
    main()
