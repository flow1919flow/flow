"""Measure 90-day cash for TradeDay Fast Pass portfolios of up to five accounts."""

from sqx_funded_scaling_audit import FAST_PASS_25K, FAST_PASS_FEES, cash_90, replay_mff, summarize
from sqx_kontovergleich import HORIZON
from sqx_nq_open30_portfolio import nq_calendar
from sqx_tradeday_liquidity import PORTFOLIO_OUT
from sqx_tradeday_liquidity_accounts import load_marks, simulate
from sqx_tradeday_plan_comparison import TIERS, read, write_json


def verify_controls(marks, dates):
    previous, _ = load_marks()
    for day in dates:
        for quantity in (1, 2):
            for first in (1, 2):
                assert marks[day, quantity, 1, first, 0] == previous[day, quantity, first, 0, 0]
                for second in (1, 2):
                    for slot in range(2):
                        assert marks[day, quantity, 2, 3 * first + second, slot] == previous[
                            day, quantity, first, second, slot]


def portfolio_report():
    from sqx_mff_top_payout_timelines import STATIC, ema22_timelines

    marks, quality = load_marks(portfolio=True)
    dates = sorted(nq_calendar()[1])
    assert len(marks) == len(dates) * 4 * sum(n * 2**n for n in range(1, 6))
    verify_controls(marks, dates)
    windows = [dates[i:i + HORIZON] for i in range(len(dates) - HORIZON + 1)]
    _, mff_ledgers = ema22_timelines(read(STATIC / 'cash-rankings.json'))
    mff, = mff_ledgers.values()
    assert all([r['start'] for r in phase] == [w[0] for w in windows] for phase in mff.values())
    tiers = {25: FAST_PASS_25K, **TIERS}
    size_limits = {25: 1, 50: 2, 100: 3, 150: 4}
    rows = []
    for size, tier in tiers.items():
        for quantity in range(1, size_limits[size] + 1):
            for copies in range(1, 6):
                for budget in (100_000, 400_000):
                    for price, fee in zip(('sale', 'list'), FAST_PASS_FEES[size], strict=True):
                        if fee * copies > budget:
                            continue
                        row = dict(size=size, quantity=quantity, copies=copies, fee=fee / 100,
                                   price=price, budget=budget / 100)
                        for stress, label in enumerate(('normal', 'stress')):
                            outcomes = [
                                cash_90(simulate(w, marks, size, quantity, copies, fee, stress,
                                                 tier=tier, budget=budget, portfolio=True))
                                for w in windows
                            ]
                            row[label] = summarize(outcomes)
                            if budget == 100_000:
                                row[label]['combined'] = {
                                    n: summarize((amount + other, paid or mff_paid)
                                                 for (amount, paid), (other, mff_paid) in zip(
                                                     outcomes, (replay_mff(r, n) for r in mff[label]),
                                                     strict=True))
                                    for n in (2, 3)
                                }
                        rows.append(row)
        print(f'{size}k complete; {len(rows)} portfolio/fee/budget scenarios', flush=True)
    meta = {
        'period': [dates[0], dates[-1]], 'sessions': len(dates), 'starts': len(windows),
        'window_sessions': HORIZON, 'cutoff_calendar_days': 90,
        'tick_stress_per_side': 1,
        'mff_control': 'Rapid EOD 50k, HY104-EMA22 Eval → 104-C28.03 Funded; separate $1000 budget',
        'mff_sizes': [2, 3], 'td_signal': 'HY3 EMA20 Eval → SMA5/10 Funded',
        'checked_legacy_fill_outcomes': len(dates) * 20,
        'liquidity_note': 'Shared top of book, ordered slots, exits first, frozen SQX signal times',
        'size_note': 'Same tier and fixed NQ quantity per portfolio. Quantity capped at initial Sim Funded limit.',
        'cash_note': 'Cash received less fees through calendar day 90, divided by three. No reinvestment.',
        'live_note': 'Individual accounts stop at Sim-to-Live review; Funded Live cash is outside this scenario.',
    }
    write_json(PORTFOLIO_OUT / 'Ergebnisse.json', dict(**meta, rows=rows))
    write_json(PORTFOLIO_OUT / 'Quote-Qualitaet.json', quality)


if __name__ == '__main__':
    portfolio_report()
