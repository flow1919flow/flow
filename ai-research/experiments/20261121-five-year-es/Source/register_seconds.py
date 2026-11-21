"""A single, separately registered finer-resolution reconstruction, not a search."""
from pathlib import Path
from datetime import datetime, timezone
import copy, hashlib, json

HERE=Path(__file__).resolve().parents[1]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    target=HERE/'Public/preregister-seconds-v2.json'
    assert not target.exists(), 'Do not overwrite after outcomes'
    original=HERE/'Public/preregister.json'
    assert sha(original)=='07bcf9570e68ab5cbeef5b58ca6b23c543979d8f96ac4c17986ddd2f43311faf'
    plan=copy.deepcopy(json.loads(original.read_text()))
    plan.update(schema='ES-FIVE-YEAR-ML-2-ONE-SECOND',created_at_utc=datetime.now(timezone.utc).isoformat(),
        supersedes_reconstruction_only='Minute-close v1 failed recall57.64%,precision68.73%; old FAIL/source/data retained. No older labels or fits generated.',
        parent_preregister_sha256=sha(original),
        new_reconstruction_attempts_allowed=1,
        no_minute_v2_or_resolution_search=True)
    plan['data'].update(source='Original GLBX.MDP3 OHLCV-1s ES.FUT, exact dated quarterly outrights, no adjusted continuous prices.',
        resolution='One-second OHLCV, NOT bid/ask TBBO or a known true intrasecond tick path.',
        price_gate='Authenticated get_cost exact0USD immediately before EVERY monthly request; positive or error stops without that data request.',
        first_authenticated_quote_sha256=sha(HERE/'Public/authenticated-finer-quotes.json'),
        quality='Preserve vendor degraded flags, including known28Nov2025; no silent outcome-based exclusion.',
        acquisition='Known Nov2025–Oct2026 months first, then Nov2021–Oct2025; raw prices only, sealed outcomes remain uncomputed.')
    plan['review']['accepted_specs']='Actual Claude confirmation of one-second-end decisions and symmetric >=2-second market fills, 21 November 2026; no private session metadata published.'
    plan['candidate'].update(
        reconstruction='O-H-L-C and O-L-H-C are uncertainty scenarios only. Both include Open and Close; forming5min range updated in scenario order. Carry all unresolved finite sequence states across seconds, deduplicated without outcome information.',
        consensus='A candidate only if all paths/states agree in direction and second. Ambiguous first returns count as missing in native acceptance, never pick the profitable path.',
        decision='At second interval END, using only information available then; stop and five features fixed there. No retrospective trade at an earlier intrasecond EMA touch.',
        entry='Market fill at first observed second interval Open at least2seconds after decision. It must precede native flatten. Report missing intervals/delays; never invent a bar.',
        stop='Decision-end EMA20 − side×2.15formingATR10, outward0.25tick; fixed after decision.',
        spread='Fill trade-price proxy plus one adverse tick for buy, minus one for sell. This is an explicit conservative spread approximation, independent of later stress.')
    plan['labels'].update(
        primary='One-second approximation of original C28.03 moving BB/OR/stop decisions with >=2s market-fill latency. Not native tick labels.',
        BB='20-value forming population BB1.75 with0.75tick offset; target touch during a second is reconstructed without claiming the actual path. Decision at secondEND.',
        OR='Fixed first60min high/low afterminute60; actualentry favorable-distance guard>=1tick. Touch triggers an exit intent, NOT fillatlevel.',
        priority='If stop and any target touch within same second, stop wins. Once an exit intent exists, preserve it; no later outcome-based replacement.',
        exit='All stop/BB/OR market exits fill first observed secondOpen >= exitdecisionEND+2s, with adverse spread tick. No guaranteed stop/target-price fills.',
        flatten='At native flatten time an exit intent is generated, then first observed secondOpen >=flatten+2s, with adverse spread; no new entries at/afterflatten.',
        net_R='(gross from actual proxyfills−4.68−25.00)/(side×(decisionClose+side×0.25−fixedStop)×50+4.68+25.00)',
        risk_causality='Decision quote proxy is decisionClose+side×1spreadtick; never use later actual entryprice to select features/size/risk.',
        secondary='No bracket-rule or separate label search in this one reconstruction; original movingtarget label is primary.')
    check=plan['mandatory_known_year_approximation_acceptance']
    check.update(minimum_mean_R_error_abs_maximum=0.05,
                 signed_mean_R_error_abs_must_be_at_most=0.05,
                 ambiguous_cases='Count as unmatched, included in denominator; do not prune native reference to easy cases.',
                 failure_action='End bar-reconstruction route after this one-second attempt; no older labels/training, no relaxed thresholds. Consult actual Claude on the final result.')
    plan['feature_rules']='Decision-second END only. CurrentsecondOHLC is then known. Planned risk uses decision quoteproxy, not future fill. ORfeature eligibility uses decisionquoteproxy; actualentryguard only for later exit label. Slope and relvol from completed5min bars. No intrasecond backdating, future highs/lows/MFE or SI-history invention.'
    plan['software_references'].append('https://databento.com/docs/api-historical/basics/')
    plan['register_source_sha256']=sha(Path(__file__))
    target.write_text(json.dumps(plan,indent=2,ensure_ascii=False)+'\n')
    print('Registered one-second attempt',sha(target))

if __name__=='__main__':main()
