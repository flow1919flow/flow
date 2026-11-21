"""Synthetic price audit checks; no role labels/outcomes read or generated."""
from pathlib import Path
import copy,json,tempfile
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import audit_role_prices as audit
from price_extract_support import HERE,NS,ct_ns,sha,save,utcnow


def rejected(call,fragment):
    try:call()
    except ValueError as error:assert fragment in str(error),(fragment,str(error))
    else:raise AssertionError('Expected audit rejection: '+fragment)


class CalendarFixture:
    def __init__(self,days):self.days=days
    def get(self,day):return self.days.get(day)


def main():
    checks=[];day='2022-01-03';op=ct_ns(day,8,30)
    clock=dict(session_open_ns=op,session_close_ns=op+600*NS,flatten_ns=op+540*NS,calendar_status='synthetic_exact_calendar')
    states={}
    audit.observe_prices(states,'ESH2',day,[op,op+NS],[2,3],['unknown']*2,clock)
    audit.observe_prices(states,'ESH2',day,[op+300*NS,op+599*NS],[4,5],['unknown']*2,clock)
    actual=audit.finalize_price(states[(day,'ESH2')],clock)
    assert actual['second_records']==4 and actual['rth_volume']==14 and actual['complete_5m_grid']
    assert actual['max_internal_absent_seconds']==298 and actual['absent_print_intervals']==596
    checks.append('Independent cross-batch seconds/volume/bucket/gap recount; sparse seconds may still cover the full 5m grid and remain unfilled')
    missing={};audit.observe_prices(missing,'ESH2',day,[op],[1],['unknown'],clock)
    assert audit.finalize_price(missing[(day,'ESH2')],clock)['missing_5m_buckets']==[1]
    checks.append('Absent 5m bucket is explicit, not hidden by a fabricated second/bar')
    rejected(lambda:audit.observe_prices({},'ESH2',day,[op,op],[1,1],['x','x'],clock),'Duplicate/unordered')
    rejected(lambda:audit.observe_prices(states,'ESH2',day,[op+599*NS],[1],['x'],clock),'cross-batch')
    rejected(lambda:audit.observe_prices({},'ESH2',day,[op+1],[1],['x'],clock),'fractional-second')
    rejected(lambda:audit.observe_prices({},'ESH2',day,[op+600*NS],[1],['x'],clock),'Out-of-session')
    checks.append('Duplicate, reversed cross-batch, fractional-second and outside-session records are rejected')
    days=['2022-01-03','2022-01-04','2022-01-05','2022-01-06','2022-01-07','2022-01-10','2022-01-11']
    calendar=CalendarFixture({d:dict(clock,session_open_ns=ct_ns(d,8,30),session_close_ns=ct_ns(d,8,30)+600*NS,flatten_ns=ct_ns(d,8,30)+540*NS) for d in days})
    coverage=[]
    for d in days:
        coverage.extend([dict(day=d,raw_symbol='ESH2',rth_volume=100,complete_5m_grid=True),dict(day=d,raw_symbol='ESM2',rth_volume=50,complete_5m_grid=True)])
    baseline,_=audit.independent_roll(coverage,days,calendar)
    poison=copy.deepcopy(coverage)
    for r in poison:
        if r['day']>=days[4] and r['raw_symbol']=='ESM2':r['rth_volume']=10**9
    changed,_=audit.independent_roll(poison,days,calendar)
    assert changed[:5]==baseline[:5] and changed[5]['raw_symbol']=='ESM2'
    assert all(r['selection_information_day']<r['day'] for r in changed if r['selection_information_day'])
    checks.append('Independent roll uses only prior session volume; poisoned future/current volume cannot alter earlier selections')
    tie=copy.deepcopy(coverage)
    for r in tie:
        if r['day']==days[1]:r['rth_volume']=100
    tied,_=audit.independent_roll(tie,days,calendar);assert tied[2]['raw_symbol']=='ESH2'
    rollover=copy.deepcopy(coverage)
    for r in rollover:
        if r['day']==days[1] and r['raw_symbol']=='ESM2':r['rth_volume']=1000
        if r['day']>=days[2] and r['raw_symbol']=='ESH2':r['rth_volume']=10**9
    rolled,_=audit.independent_roll(rollover,days,calendar)
    assert all(r['raw_symbol']=='ESM2' for r in rolled[2:])
    checks.append('Roll tie preserves incumbent and selected maturities cannot move backwards even if expired contract volume rises')
    damaged=copy.deepcopy(coverage)
    next(r for r in damaged if r['day']==days[2] and r['raw_symbol']=='ESH2')['complete_5m_grid']=False
    gaps,_=audit.independent_roll(damaged,days,calendar)
    assert baseline[5]['warmup_complete'] and not gaps[5]['warmup_complete']
    checks.append('Incomplete same-contract history remains an explicit five-session warmup deviation')
    require_days=audit.month_days({'2022-01':{}},calendar)
    assert require_days==days
    checks.append('Planned sessions enumerate calendar dates independently of observed price start/end, exposing omitted whole sessions')
    with tempfile.TemporaryDirectory() as temp:
        temp=Path(temp);directory=temp/'Private/Months/2022-01';directory.mkdir(parents=True)
        raw=temp/'raw.synthetic';raw.write_bytes(b'synthetic-price-only-original')
        mapping=directory/'dated-raw-contract-mappings.json';mapping.write_text('[]\n')
        data=pa.table(dict(day=[day,day],ts_event_ns=[op,op+300*NS],volume=pa.array([2,3],type=pa.uint64()),vendor_quality_flag=['unknown','unknown']))
        shardpath=directory/'ESH2-1s.parquet';pq.write_table(data,shardpath)
        barpath=directory/'bars-5m.parquet';pq.write_table(pa.table(dict(bar_index=[0,1])),barpath)
        ledger=[dict(day=day,raw_symbol='ESH2',rth_volume=5,second_records=2,observed_5m_bars=2,expected_5m_bars=2,missing_5m_buckets=[],complete_5m_grid=True,vendor_quality_flag='unknown')]
        ledgerpath=directory/'contract-session-price-coverage.json';ledgerpath.write_text(json.dumps(ledger))
        manifest=dict(zero_cost_download_receipt=dict(quoted_cost_USD=0),raw_source_path=str(raw),raw_source_bytes=raw.stat().st_size,raw_source_sha256=sha(raw),bars_5m_sha256=sha(barpath),dated_mapping_sha256=sha(mapping),session_coverage_sha256=sha(ledgerpath),bars_5m_rows=2,second_shards=[dict(raw_symbol='ESH2',path_relative_to_task=str(shardpath.relative_to(temp)),sha256=sha(shardpath),rows=2)],counts=dict(ES_quarterly_RTH_second_records=2))
        (directory/'manifest.json').write_text(json.dumps(manifest))
        previous=audit.TASK;audit.TASK=temp
        try:
            observed,_,proof=audit.collect_months({'2022-01':manifest},CalendarFixture({day:clock}))
            assert proof['2022-01']['second_rows']==2 and observed[(day,'ESH2')]['complete_5m_grid']
            checks.append('Bounded real Parquet batch integration matches manifest and recomputed per-session coverage without reading prices/outcomes')
            corrupt=copy.deepcopy(manifest);corrupt['second_shards'][0]['rows']=3
            rejected(lambda:audit.collect_months({'2022-01':corrupt},CalendarFixture({day:clock})),'row count differs')
            checks.append('Parquet header/batch row count mismatch is a critical rejection')
            corrupt=copy.deepcopy(manifest);corrupt['second_shards'][0]['sha256']='0'*64
            rejected(lambda:audit.collect_months({'2022-01':corrupt},CalendarFixture({day:clock})),'Second price shard changed')
            checks.append('Changed second shard rejected before session enumeration')
            raw.write_bytes(b'tampered')
            rejected(lambda:audit.collect_months({'2022-01':manifest},CalendarFixture({day:clock})),'Raw monthly original changed')
            checks.append('Changed raw monthly bytes/hash rejected independently of canonical shards')
            raw.write_bytes(b'synthetic-price-only-original')
            wrong=copy.deepcopy(ledger);wrong[0]['second_records']=3;ledgerpath.write_text(json.dumps(wrong))
            corrupt=copy.deepcopy(manifest);corrupt['session_coverage_sha256']=sha(ledgerpath)
            rejected(lambda:audit.collect_months({'2022-01':corrupt},CalendarFixture({day:clock})),'Recomputed price coverage mismatch')
            checks.append('Even a self-rehashed incorrect coverage ledger fails independent recount')
        finally:audit.TASK=previous
    summary_clock=CalendarFixture({day:clock});row=dict(day=day,raw_symbol='ESH2',selection_information_day='2021-12-31',**clock,warmup_previous_five_same_contract_sessions=[],warmup_complete=False)
    rejected(lambda:audit.summarize_sessions([row],{},day,'2022-01-04'),'Missing selected role session')
    checks.append('Entire missing selected session blocks completeness proof rather than becoming an omitted label day')
    audit.dispatch.verify_known_immutable()
    for role in audit.dispatch.PERIODS:assert not (HERE/f'Private/{role}-label-attempt.json').exists()
    checks.append('All fixtures are synthetic; frozen known sources unchanged and real role label markers remain absent')
    report=dict(status='PASS_SYNTHETIC_PRICE_COMPLETENESS_AUDIT',utc=utcnow(),checks_passed=len(checks),checks=checks,no_real_role_price_audit_or_signal_label_model_execution=True)
    save(HERE/'Public/price-completeness-audit-fixtures.json',report);print(json.dumps(report,indent=2))


if __name__=='__main__':main()
