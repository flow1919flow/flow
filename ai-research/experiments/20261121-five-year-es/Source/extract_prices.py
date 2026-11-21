"""Canonical raw ES minute/5-minute prices and causal roll schedule only.

No candidate, outcome, strategy PnL or model is computed in this module.
450-minute native research session, exact known native calendar overrides.
"""
from inventory_local import HERE,ROOT,sha,save,day_ns
from datetime import datetime,timezone,date,timedelta
from zoneinfo import ZoneInfo
from collections import Counter
import json, re, time
import numpy as np
import pandas as pd
import databento as db

CT=ZoneInfo('America/Chicago')
NS=1_000_000_000
NATIVE=ROOT/'outputs/NQ-Woche-20261118/ema22-history-acceptance-20261119'
SPLIT_START='2021-11-24'
SPLIT_HOLDOUT='2024-11-24'
SPLIT_SUPPLEMENT='2025-11-24'


def session_ns(day,hm):
    d=date.fromisoformat(day);h,m=map(int,hm.split(':'))
    return int(datetime(d.year,d.month,d.day,h,m,tzinfo=CT).timestamp())*NS


def native_calendar():
    calendar={};sources=[]
    for p in sorted((NATIVE/'ES/SQX/evaluation').glob('*/manifest.txt')):
        seed=__import__('pathlib').Path(p.read_text().splitlines()[2]);sources.append(dict(path=str(seed),sha256=sha(seed)))
        for line in seed.read_text().splitlines():
            fields=line.split(',');op,cl,fl=map(int,fields[:3])
            day=datetime.fromtimestamp(op//NS,timezone.utc).astimezone(CT).date().isoformat()
            row=dict(session_open_ns=op,session_close_ns=cl,flatten_ns=fl,calendar_status='observed_exact_native_seed')
            if day in calendar:assert calendar[day]==row
            calendar[day]=row
    return calendar,sources


def role(day):
    if day<SPLIT_START:return 'preperiod_price_warmup'
    if day<SPLIT_HOLDOUT:return 'oldest_three_years_development_prices_only'
    if day<SPLIT_SUPPLEMENT:return 'sealed_fourth_year_prices_only_NO_LABELS'
    return 'known_2025_2026_development_supplement'


def maturity(symbol):
    m=re.fullmatch(r'ES([HMUZ])(\d)',symbol)
    if not m:raise ValueError('Unexpected raw outright symbol '+symbol)
    # Explicit task window2021–2026; observed contract universeESZ1..ESZ7.
    return 2020+int(m[2]),{'H':3,'M':6,'U':9,'Z':12}[m[1]]


def select(prior,incumbent):
    candidates=[r for r in prior if r['rth_volume']>0 and (incumbent is None or maturity(r['raw_symbol'])>=maturity(incumbent))]
    if not candidates:return None
    return sorted(candidates,key=lambda r:(-r['rth_volume'],r['raw_symbol']!=incumbent,maturity(r['raw_symbol']),r['raw_symbol']))[0]


def derive_schedule(sessions,calendar):
    days=sorted(calendar)
    lookup={(r['date'],r['raw_symbol']):r for r in sessions}
    byday={d:[] for d in days}
    for r in sessions:byday[r['date']].append(r)
    incumbent=None;previous=None;output=[]
    for pos,day in enumerate(days):
        prior=byday[previous] if previous else []
        chosen=select(prior,incumbent) if previous else None
        symbol=chosen['raw_symbol'] if chosen else None
        prior_days=days[max(0,pos-5):pos]
        warm=[]
        for d in prior_days:
            r=lookup.get((d,symbol))
            warm.append(dict(date=d,raw_symbol=symbol,observed_5m_bars=int(r['observed_5m_bars']) if r else 0,expected_5m_bars=(calendar[d]['session_close_ns']-calendar[d]['session_open_ns'])//(300*NS),complete_5m_grid=bool(r and r['complete_5m_grid'])))
        current=lookup.get((day,symbol))
        output.append(dict(date=day,raw_symbol=symbol,selection_information_date=previous,prior_rth_volume=chosen['rth_volume'] if chosen else None,roll_from=incumbent if chosen and incumbent!=symbol else None,**calendar[day],split_role=role(day),warmup_previous_five_same_contract_sessions=warm,warmup_complete=len(warm)==5 and all(x['complete_5m_grid'] for x in warm),current_data_available=bool(current),current_complete_5m_grid=bool(current and current['complete_5m_grid']),current_data_never_changes_selection=True,selection_status='selected_from_prior_weekday_session_volume' if chosen else 'unavailable_prior_weekday_session_no_retrospective_fallback'))
        if chosen:incumbent=symbol
        previous=day
    return output


def aggregate_5m(minutes):
    grouped=minutes.sort_values(['raw_symbol','date','ts_event_ns']).groupby(['raw_symbol','date','instrument_id','bar_index'],sort=True,observed=True)
    bars=grouped.agg(bar_start_ns=('bar_start_ns','first'),bar_end_ns=('bar_end_ns','first'),open_nanos=('open_nanos','first'),high_nanos=('high_nanos','max'),low_nanos=('low_nanos','min'),close_nanos=('close_nanos','last'),volume=('volume','sum'),minute_records=('ts_event_ns','size'),first_minute_start_ns=('ts_event_ns','min'),last_minute_start_ns=('ts_event_ns','max')).reset_index()
    bars['complete_five_minute_records']=bars.minute_records.eq(5)
    bars['available_ns']=bars.bar_end_ns
    return bars


def main():
    began=time.time();inventory=json.loads((HERE/'Private/raw-source-inventory.json').read_text())
    exact,sources=native_calendar();calendar={}
    for day in pd.date_range('2021-11-01','2026-10-30',freq='B').strftime('%Y-%m-%d'):
        # The exact native known-year session calendar excludes full closures.
        # This uses attested session metadata only, never a strategy outcome.
        if '2025-11-24'<=day<='2026-10-30' and day not in exact:
            continue
        calendar[day]=exact.get(day,dict(session_open_ns=session_ns(day,'08:30'),session_close_ns=session_ns(day,'16:00'),flatten_ns=session_ns(day,'15:09'),calendar_status='weekly_native_template_CME_holiday_overlay_unresolved'))
    source_refs={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'work/plan_keltner_contracts.py',ROOT/'work/plan_keltner_history_segments.py',ROOT/'work/audit_tbbo_history.py',NATIVE/'Quellstand/HY104EMA22HistoryIntegrity.java']}
    freeze=dict(frozen_before_any_new_candidate_or_label_utc=datetime.now(timezone.utc).isoformat(),source_sha256=sha(__import__('pathlib').Path(__file__)),input_inventory_sha256=sha(HERE/'Private/raw-source-inventory.json'),native_sources=source_refs,native_seed_sources=sources,normal_CT_session=['08:30','16:00'],normal_CT_flatten='15:09',bar_alignment='5min from civilChicago08:30inclusive; closeexclusive; ts_event1m is intervalSTART; features available no earlier than intervalEND',roll='Original prior-weekday RTH-volume-only maximum; no backward maturity; ties retain incumbent then earlier maturity; missing precedingweekday invalidates selection; currentdayavailability never substitutes',warmup='Previousfive samecontractsessiongrids; carry state within episode, reset from samecontracthistory atroll; no splicing or inventedbars',calendar='Exact nativeknownyearseed overrides retained; other holiday/earlyclose decisions unresolved, weeklytemplate flagged; no strategytrainingreleased',split_roles={'preperiod':['2021-11-01','2021-11-24'],'development_oldest3':['2021-11-24','2024-11-24'],'sealed_final_fourth_year':['2024-11-24','2025-11-24'],'known_development_supplement':['2025-11-24','2026-10-31']},prices_only=True,labels_computed=False)
    save(HERE/'Private/native-seed-source-proof.json',sources)
    save(HERE/'Public/price-extraction-freeze.json',{k:v for k,v in freeze.items() if k!='native_seed_sources'})
    pieces=[]
    for num,f in enumerate(inventory,1):
        p=__import__('pathlib').Path(f['path']);assert sha(p)==f['sha256']
        store=db.DBNStore.from_file(p);mappings=f['ES_mapping_intervals'];by_id={}
        for z in mappings:by_id.setdefault(z['instrument_id'],[]).append(z)
        for array in store.to_ndarray(count=250000):
            subset=array[np.isin(array['instrument_id'],list(by_id))]
            if not len(subset):continue
            for iid,intervals in by_id.items():
                a=subset[subset['instrument_id']==iid]
                for z in intervals:
                    rows=a[(a['ts_event']>=day_ns(z['start_date']))&(a['ts_event']<day_ns(z['end_date']))]
                    if not len(rows):continue
                    times=pd.to_datetime(rows['ts_event'],unit='ns',utc=True).tz_convert(CT)
                    minute=times.hour*60+times.minute
                    mask=(times.dayofweek<5)&(minute>=510)&(minute<960)
                    rows,times=rows[mask],times[mask]
                    if not len(rows):continue
                    dates=times.strftime('%Y-%m-%d')
                    observed_calendar=np.array([d in calendar for d in dates])
                    rows,dates=rows[observed_calendar],dates[observed_calendar]
                    if not len(rows):continue
                    cl=np.array([calendar[d]['session_close_ns'] for d in dates],dtype=np.int64)
                    keep=rows['ts_event']<cl;rows=rows[keep];dates=dates[keep]
                    if not len(rows):continue
                    ts=rows['ts_event'].astype(np.int64)
                    opens=np.array([calendar[d]['session_open_ns'] for d in dates],dtype=np.int64)
                    buckets=((ts-opens)//(300*NS)).astype(np.int16)
                    table=pd.DataFrame(dict(raw_symbol=z['raw_symbol'],instrument_id=rows['instrument_id'],date=dates,ts_event_ns=ts,available_ns=ts+60*NS,open_nanos=rows['open'],high_nanos=rows['high'],low_nanos=rows['low'],close_nanos=rows['close'],volume=rows['volume'],bar_index=buckets,bar_start_ns=opens+buckets.astype(np.int64)*300*NS,bar_end_ns=opens+(buckets.astype(np.int64)+1)*300*NS,source_file_index=num-1))
                    pieces.append(table)
        print('price-only decoded',num,'/',len(inventory),p.name,flush=True)
    minute=pd.concat(pieces,ignore_index=True).sort_values(['raw_symbol','date','ts_event_ns']).reset_index(drop=True)
    assert not minute.duplicated(['raw_symbol','date','ts_event_ns']).any()
    assert (minute.ts_event_ns%(60*NS)==0).all()
    bars=aggregate_5m(minute)
    session=[]
    for (day,symbol),g in bars.groupby(['date','raw_symbol'],observed=True):
        expected=(calendar[day]['session_close_ns']-calendar[day]['session_open_ns'])//(300*NS)
        missing=sorted(set(range(expected))-set(map(int,g.bar_index)))
        session.append(dict(date=day,raw_symbol=symbol,rth_volume=int(g.volume.sum()),observed_5m_bars=len(g),expected_5m_bars=expected,missing_5m_buckets=missing,complete_5m_grid=not missing,minute_records=int(g.minute_records.sum()),calendar_status=calendar[day]['calendar_status']))
    schedule=derive_schedule(session,calendar)
    selected_map={s['date']:s['raw_symbol'] for s in schedule}
    active=bars[bars.raw_symbol==bars.date.map(selected_map)].copy()
    minute_path=HERE/'Private/ES-raw-outright-RTH-1m.parquet';minute.to_parquet(minute_path,index=False)
    bars_path=HERE/'Private/ES-raw-outright-RTH-5m.parquet';bars.to_parquet(bars_path,index=False)
    active_path=HERE/'Private/ES-selected-single-session-5m.parquet';active.to_parquet(active_path,index=False)
    schedule_path=HERE/'Private/ES-causal-roll-schedule.json';save(schedule_path,schedule)
    save(HERE/'Private/ES-contract-session-price-coverage.json',session)
    manifest=dict(status='PRICE_ONLY_EXTRACTED_NATIVE450_CALENDAR_HISTORICAL_OVERLAY_UNRESOLVED',created_utc=datetime.now(timezone.utc).isoformat(),source_inventory_sha256=sha(HERE/'Private/raw-source-inventory.json'),extraction_freeze_sha256=sha(HERE/'Public/price-extraction-freeze.json'),minute_file=str(minute_path),minute_sha256=sha(minute_path),minute_rows=len(minute),all_contract_5m_file=str(bars_path),all_contract_5m_sha256=sha(bars_path),all_contract_5m_rows=len(bars),selected_5m_file=str(active_path),selected_5m_sha256=sha(active_path),selected_5m_rows=len(active),schedule_file=str(schedule_path),schedule_sha256=sha(schedule_path),schedule_sessions=len(schedule),selected_sessions=sum(x['raw_symbol'] is not None for x in schedule),selected_sessions_complete_warmup=sum(x['warmup_complete'] for x in schedule),native_calendar_dates=len(exact),rolls=[{k:r[k] for k in ['date','selection_information_date','roll_from','raw_symbol']} for r in schedule if r['roll_from'] is not None],first_date=minute.date.min(),last_date=minute.date.max(),price_unit='integer1e-9USDpriceunits,ES.25tick;50USDperpoint',volume_unit='contracts',minute_no_trade_semantics='Absent1mrecord maymean no trades; no fillforward or inventedzero-volume bar',within_5m_missing_minutes=int((~bars.complete_five_minute_records).sum()),no_strategy_candidates=True,no_labels=True,no_models=True,no_downloads=True,elapsed_seconds=time.time()-began)
    save(HERE/'Private/price-data-manifest.json',manifest)
    save(HERE/'Public/price-extraction-summary.json',{k:v for k,v in manifest.items() if not k.endswith('_file')})
    print(json.dumps({k:v for k,v in manifest.items() if not k.endswith('_file')},indent=2),flush=True)


if __name__=='__main__':main()
