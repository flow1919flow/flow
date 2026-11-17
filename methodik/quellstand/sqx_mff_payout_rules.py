"""Funded payout simulation for MyFundedFutures Pro and Rapid plans.

The provider implements EOD trails and checks open equity against the current
floor intraday. Withdrawal submission, approval and trail reset are modelled
at the session close. The account receives funds net of the published split.
No cash is attributed to a discretionary review, a live account or a reserve.

Sources:
  https://help.myfundedfutures.com/en/articles/16158363-rapid-eod-50k-a-comprehensive-look
  https://help.myfundedfutures.com/en/articles/13134718-understanding-rapid-live
  https://help.myfundedfutures.com/en/articles/17573707-comprehensive-look-into-redesigned-pro-plan
  https://myfundedfutures.com/plans/pro
  https://help.myfundedfutures.com/en/articles/13745661-payout-policy-overview-best-and-fastest-prop-firm-payouts
  https://help.myfundedfutures.com/en/articles/11802674-legacy-pro-plan-sim-funded-and-live-account-highlights
  https://help.myfundedfutures.com/en/articles/16596524-inactivity-rule-one-time-payment-model
  https://help.myfundedfutures.com/en/articles/8348565-end-of-day-eod-drawdown-explained
"""

from dataclasses import dataclass
from datetime import date, timedelta


RAPID_EOD = 'rapid_eod_50k'
RAPID_INTRADAY = 'rapid_intraday_150k'
PRO = 'pro_50k'
PRO_150K = 'pro_150k'
RAPID_PLANS = (RAPID_EOD, RAPID_INTRADAY)
PRO_PLANS = (PRO, PRO_150K)
BUFFER_CENTS = 210_000
MAX_LOSS_CENTS = 200_000
LOCK_CENTS = 10_000
DAY_NS = 86_400 * 10**9
RAPID_LIVE_DAY_CENTS = 1_000_000
PRO_REVIEW_PROFIT_CENTS = 2_000_000
PRO_USER_CAP_CENTS = 10_000_000


@dataclass(frozen=True)
class PayoutPolicy:
    name: str
    extra_buffer_cents: int = 0
    pro_early_draw: bool = False
    pro_elapsed_clock: bool = False
    continue_after_pro_review: bool = False
    pro_calendar_cycles_from_first_trade: bool = False


DEFAULT = PayoutPolicy('buffer_cleared_calendar_days')
POLICIES = (
    DEFAULT,
    PayoutPolicy('retain_extra_250_usd', extra_buffer_cents=25_000),
    PayoutPolicy('retain_extra_500_usd', extra_buffer_cents=50_000),
    PayoutPolicy('pro_early_draw_legacy_sensitivity', pro_early_draw=True),
    PayoutPolicy('pro_14_elapsed_24h_periods', pro_elapsed_clock=True),
    PayoutPolicy('pro_continue_after_human_review', continue_after_pro_review=True),
    PayoutPolicy('pro_calendar_cycles_anchored_at_first_trade', pro_calendar_cycles_from_first_trade=True),
)


def policies_for(plan):
    if plan not in (*RAPID_PLANS, *PRO_PLANS):
        raise ValueError(f'Unsupported funded plan: {plan}')
    return POLICIES if plan in PRO_PLANS else POLICIES[:3]


def _payout_allowed(plan, policy, session, close_ns, first_trade, last_payout):
    if first_trade is None:
        return False
    previous_date, previous_ns = last_payout or first_trade
    if plan == RAPID_INTRADAY:
        return close_ns - previous_ns >= DAY_NS
    if plan == RAPID_EOD:
        if last_payout is None:
            return close_ns - previous_ns >= DAY_NS
        return session > previous_date
    if policy.pro_elapsed_clock:
        return close_ns - previous_ns >= 14 * DAY_NS
    if policy.pro_calendar_cycles_from_first_trade:
        # The payout overview also admits calendar cycles anchored at the first
        # trade. Permit one request per cycle, beginning in the second cycle.
        first_date, _ = first_trade
        return (session - first_date).days // 14 > (previous_date - first_date).days // 14
    # Biweekly cadence model: dates are counted from first fill, then from the
    # prior approved payout. Use elapsed-clock sensitivity for DST/library clocks.
    return (session - previous_date).days >= 14


def _gross_withdrawal(plan, policy, balance, net_paid, has_payout, buffer_cents):
    gross = balance - buffer_cents - policy.extra_buffer_cents
    if plan in RAPID_PLANS:
        return gross if gross >= 50_000 else 0
    if policy.pro_early_draw and not has_payout and 0 < balance < buffer_cents:
        # The legacy Pro FAQ permits one early withdrawal at 60%. The current
        # Pro-specific terms require the buffer to be cleared. Sensitivity only.
        gross = min(balance * 60 // 100, balance - LOCK_CENTS)
    gross = min(gross, (PRO_USER_CAP_CENTS - net_paid) * 100 // 80)
    return gross if gross >= 100_000 else 0


def replay_funded(plan, passed_date, sessions, paths, *, policy=DEFAULT):
    """Replay from the first available session after the evaluation passes."""
    if policy not in policies_for(plan):
        raise ValueError(f'Policy {policy.name} is unavailable for {plan}')
    if not sessions or passed_date not in sessions or any(a >= b for a, b in zip(sessions, sessions[1:])):
        raise ValueError('Expected sorted unique sessions including the evaluation pass')

    max_loss_cents = 450_000 if plan in (RAPID_INTRADAY, PRO_150K) else MAX_LOSS_CENTS
    buffer_cents = max_loss_cents + LOCK_CENTS
    is_rapid = plan in RAPID_PLANS
    balance = gross_paid = net_paid = cycle_profit = 0
    floor = -max_loss_cents
    first_trade = last_payout = None
    last_trade_date = date.fromisoformat(passed_date)
    max_cumulative_profit = 0
    payouts = []
    review_date = review_reason = None
    result = dict(status='open_at_data_end', terminal_date=sessions[-1], breach=None)

    for day in sessions:
        if day <= passed_date:
            continue
        session = date.fromisoformat(day)
        # A fill on day 7 leaves only six fully inactive intervening dates.
        expiry = last_trade_date + timedelta(days=8)
        if session >= expiry:
            result.update(status='funded_inactive', terminal_date=expiry.isoformat())
            break
        if day not in paths:
            result.update(status='data_gap', terminal_date=day)
            break

        path = paths[day]
        if path['status'] != 'complete' or not path['path']:
            raise ValueError(f'Incomplete funded session path: {day}')

        for timestamp, kind, equity_offset, cash_offset, *_ in path['path']:
            equity = balance + equity_offset
            if plan == RAPID_INTRADAY:
                floor = max(floor, min(LOCK_CENTS, equity - max_loss_cents))
            if equity < floor:
                result.update(status='funded_breached', terminal_date=day,
                              breach=dict(timestamp_ns=timestamp, equity_cents=equity,
                                          floor_cents=floor, cause='market'))
                balance += cash_offset
                break
            if is_rapid and cash_offset >= RAPID_LIVE_DAY_CENTS:
                balance += RAPID_LIVE_DAY_CENTS
                max_cumulative_profit = max(max_cumulative_profit, balance + gross_paid)
                result.update(status='live_transition', terminal_date=day,
                              transition_reason='rapid_10000_realized_single_session', transition_ns=timestamp)
                break
            if kind == 'fill_entry':
                first_trade = first_trade or (session, timestamp)
                last_trade_date = session
            max_cumulative_profit = max(max_cumulative_profit, balance + cash_offset + gross_paid)
        if result['status'] in ('funded_breached', 'live_transition'):
            break

        close_ns = path['path'][-1][0]
        balance += path['net_cents']
        cycle_profit += path['net_cents']
        if plan == RAPID_EOD:
            floor = max(floor, min(LOCK_CENTS, balance - max_loss_cents))
        elif not is_rapid and not payouts:
            floor = max(floor, balance - max_loss_cents)

        gross = _gross_withdrawal(plan, policy, balance, net_paid, bool(payouts), buffer_cents)
        eligible = gross and _payout_allowed(plan, policy, session, close_ns, first_trade, last_payout)
        if plan == RAPID_EOD and payouts and cycle_profit < 50_000:
            eligible = False
        if eligible:
            split = 90 if is_rapid else 80
            net = (gross * split + 50) // 100
            new_floor = floor if is_rapid else LOCK_CENTS
            balance_after = balance - gross
            payouts.append(dict(date=day, timestamp_ns=close_ns, gross_cents=gross, net_cents=net,
                                balance_before_cents=balance, balance_after_cents=balance_after,
                                floor_before_cents=floor, floor_after_cents=new_floor))
            balance, floor = balance_after, new_floor
            gross_paid += gross
            net_paid += net
            last_payout = session, close_ns
            cycle_profit = 0
            if balance < floor:
                result.update(status='funded_breached', terminal_date=day,
                              breach=dict(timestamp_ns=close_ns, equity_cents=balance,
                                          floor_cents=floor, cause='payout'))
                break

        if not is_rapid and net_paid >= PRO_USER_CAP_CENTS:
            result.update(status='review', terminal_date=day)
            review_date, review_reason = day, 'pro_user_payout_cap'
            break
        if (not is_rapid and review_date is None
                and (len(payouts) >= 3 or max_cumulative_profit >= PRO_REVIEW_PROFIT_CENTS)):
            review_date = day
            review_reason = ('pro_three_payouts' if len(payouts) >= 3 else 'pro_20000_cumulative_realized_profit')
            if not policy.continue_after_pro_review:
                result.update(status='review', terminal_date=day)
                break

    return dict(**result, payouts=payouts, ending_funded_balance_cents=balance,
                ending_floor_cents=floor, review_date=review_date, review_reason=review_reason,
                policy=policy.name, gross_paid_cents=gross_paid, net_paid_cents=net_paid,
                maximum_cumulative_funded_profit_cents=max_cumulative_profit)
