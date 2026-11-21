"""Independent PRICE-ONLY completeness proof before released role labels.

No strategy books, candidates, outcomes, models or API calls. Reads bounded
Parquet batches and only price timestamp/volume/quality columns. Frozen source
is imported solely for integrity and role/calendar/roll metadata dispatch.
"""
from pathlib import Path
from datetime import date,timedelta
from collections import Counter,defaultdict
import argparse,json,math,re,sys
import numpy as np
import pyarrow.parquet as pq

TASK=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(TASK/'Source'))
import period_dispatch as dispatch
from price_extract_support import Calendar,sha,save,utcnow,NS

PERIOD_FREEZE_SHA='3234ca42565168097578e5af8cc6e581e86adc16472d20983fe1f890acec1681'


def require(condition,message):
    if not condition:raise ValueError(message)


def check_frozen_integrity():
    freeze=TASK/'Public/period-source-freeze.json'
    require(sha(freeze)==PERIOD_FREEZE_SHA,'Period freeze changed')
    proof=json.loads(freeze.read_text())
    dispatch.known.verify_frozen_sources(proof,TASK/'Source',TASK/'Public/period-fixtures.json')
    dispatch.verify_known_immutable()
    audit_freeze=TASK/'Public/price-completeness-audit-source-freeze.json'
    audit=json.loads(audit_freeze.read_text())
    for filename,expected in audit['sources_sha256'].items():require(sha(TASK/'PriceOps'/filename)==expected,'Price-only audit source changed')
    require(sha(TASK/'Public/price-completeness-audit-fixtures.json')==audit['fixtures_sha256'],'Price-only audit fixtures changed')
    return proof


def month_days(months,calendar):
    first=date.fromisoformat(min(months)+'-01')
    end_month=np.datetime64(max(months),'M')+np.timedelta64(1,'M')
    end=date.fromisoformat(str(end_month)+'-01')
    return [str(first+timedelta(days=i)) for i in range((end-first).days) if calendar.get(str(first+timedelta(days=i))) is not None]


def maturity(symbol):
    match=re.fullmatch(r'ES([HMUZ])(\d{1,2})',symbol)
    require(match is not None,'Non-outright in roll schedule')
    year=int(match[2]);return (2020+year if year<10 else 2000+year,{'H':3,'M':6,'U':9,'Z':12}[match[1]])


def independent_roll(coverage,days,calendar):
    byday=defaultdict(list);lookup={}
    for row in coverage:
        key=(row['day'],row['raw_symbol']);require(key not in lookup,'Duplicate contract/session ledger')
        lookup[key]=row;byday[row['day']].append(row)
    incumbent=None;prior=None;schedule=[]
    for i,day in enumerate(days):
        valid=[r for r in byday[prior] if r['rth_volume']>0 and (incumbent is None or maturity(r['raw_symbol'])>=maturity(incumbent))] if prior else []
        ranked=sorted(valid,key=lambda r:(-r['rth_volume'],r['raw_symbol']!=incumbent,maturity(r['raw_symbol']),r['raw_symbol']))
        symbol=ranked[0]['raw_symbol'] if ranked else None
        warm=[]
        for previous in days[max(0,i-5):i]:
            row=lookup.get((previous,symbol))
            warm.append(dict(day=previous,raw_symbol=symbol,complete_5m_grid=bool(row and row['complete_5m_grid'])))
        clock=calendar.get(day)
        require('unverified' not in clock['calendar_status'],'Unresolved calendar day: '+day)
        schedule.append(dict(day=day,raw_symbol=symbol,selection_information_day=prior,**clock,warmup_previous_five_same_contract_sessions=warm,warmup_complete=len(warm)==5 and all(x['complete_5m_grid'] for x in warm)))
        if symbol is not None:incumbent=symbol
        prior=day
    return schedule,lookup


def observe_prices(acc,symbol,day,stamps,volumes,flags,clock):
    """Pure structural bounded accumulation, also exercised synthetically."""
    stamps=np.asarray(stamps,dtype=np.int64);volumes=np.asarray(volumes,dtype=np.uint64)
    require(len(stamps)==len(volumes)==len(flags) and len(stamps)>0,'Invalid price batch')
    op,cl=clock['session_open_ns'],clock['session_close_ns']
    require(np.all(stamps%NS==0) and np.all((stamps>=op)&(stamps<cl)),'Out-of-session or fractional-second price interval')
    require(np.all(np.diff(stamps)>0),'Duplicate/unordered price intervals')
    key=(day,symbol)
    if key not in acc:acc[key]=dict(day=day,raw_symbol=symbol,rows=0,volume=0,buckets=set(),first_ns=int(stamps[0]),last_ns=None,max_internal_absent_seconds=0,quality_flags=set())
    state=acc[key]
    if state['last_ns'] is not None:
        require(int(stamps[0])>state['last_ns'],'Duplicate or reversed cross-batch interval')
        state['max_internal_absent_seconds']=max(state['max_internal_absent_seconds'],(int(stamps[0])-state['last_ns'])//NS-1)
    if len(stamps)>1:state['max_internal_absent_seconds']=max(state['max_internal_absent_seconds'],int(np.max(np.diff(stamps)))//NS-1)
    state['rows']+=len(stamps);state['volume']+=int(volumes.sum(dtype=np.uint64));state['last_ns']=int(stamps[-1])
    state['buckets'].update(map(int,(stamps-op)//(300*NS)));state['quality_flags'].update(flags)


def finalize_price(state,clock):
    op,cl=clock['session_open_ns'],clock['session_close_ns'];expected=(cl-op)//NS
    expected_bars=math.ceil(expected/300)
    missing=sorted(set(range(expected_bars))-state['buckets'])
    return dict(day=state['day'],raw_symbol=state['raw_symbol'],second_records=state['rows'],rth_volume=state['volume'],expected_second_intervals=expected,absent_print_intervals=expected-state['rows'],observed_5m_bars=len(state['buckets']),expected_5m_bars=expected_bars,missing_5m_buckets=missing,complete_5m_grid=not missing,first_ns=state['first_ns'],last_ns=state['last_ns'],first_present_offset_seconds=(state['first_ns']-op)//NS,last_absent_seconds=(cl-state['last_ns'])//NS-1,max_internal_absent_seconds=state['max_internal_absent_seconds'],max_absent_run_seconds=max(state['max_internal_absent_seconds'],(state['first_ns']-op)//NS,(cl-state['last_ns'])//NS-1),quality_flags=sorted(state['quality_flags']))


def collect_months(months,calendar):
    observed={};coverage=[];monthproof={}
    for month,manifest in sorted(months.items()):
        directory=TASK/'Private/Months'/month
        require(manifest['zero_cost_download_receipt']['quoted_cost_USD']==0,'Nonzero source receipt')
        raw=Path(manifest['raw_source_path'])
        require(raw.stat().st_size==manifest['raw_source_bytes'] and sha(raw)==manifest['raw_source_sha256'],'Raw monthly original changed')
        extra={'bars-5m.parquet':manifest['bars_5m_sha256'],'dated-raw-contract-mappings.json':manifest['dated_mapping_sha256'],'contract-session-price-coverage.json':manifest['session_coverage_sha256']}
        for name,expected in extra.items():require(sha(directory/name)==expected,'Price structural artifact changed: '+month+'/'+name)
        require(pq.ParquetFile(directory/'bars-5m.parquet').metadata.num_rows==manifest['bars_5m_rows'],'5m row count differs from manifest')
        ledger=json.loads((directory/'contract-session-price-coverage.json').read_text());coverage.extend(ledger)
        total=0;shards=[]
        for shard in manifest['second_shards']:
            path=TASK/shard['path_relative_to_task'];require(sha(path)==shard['sha256'],'Second price shard changed')
            parquet=pq.ParquetFile(path);count=parquet.metadata.num_rows
            require(count==shard['rows'],'Second shard row count differs from manifest')
            counted=0
            for batch in parquet.iter_batches(batch_size=100000,columns=['day','ts_event_ns','volume','vendor_quality_flag']):
                values=batch.to_pydict();day_array=np.asarray(values['day'],dtype=object);timestamps=np.asarray(values['ts_event_ns'],dtype=np.int64);volumes=np.asarray(values['volume'],dtype=np.uint64);flags=np.asarray(values['vendor_quality_flag'],dtype=object)
                for day in np.unique(day_array):
                    mask=day_array==day;clock=calendar.get(day)
                    require(clock is not None,'Price record on closed calendar day')
                    observe_prices(observed,shard['raw_symbol'],day,timestamps[mask],volumes[mask],flags[mask],clock)
                counted+=len(day_array)
            require(counted==count,'Batch reader missed price records')
            total+=count;shards.append(dict(path=shard['path_relative_to_task'],sha256=shard['sha256'],rows=count))
        require(total==manifest['counts']['ES_quarterly_RTH_second_records'],'Per-month second total differs from manifest')
        monthproof[month]=dict(manifest_sha256=sha(directory/'manifest.json'),zero_quote=True,raw_sha256=manifest['raw_source_sha256'],raw_bytes=raw.stat().st_size,second_rows=total,second_shards=len(shards),bars_5m_rows=manifest['bars_5m_rows'],all_second_shards=shards,structural_artifact_hashes=extra)
        print('price-only audited',month,'second rows',total,flush=True)
    result={key:finalize_price(value,calendar.get(key[0])) for key,value in observed.items()}
    require(set(result)=={(r['day'],r['raw_symbol']) for r in coverage},'Actual price contract/session keys differ from coverage ledger')
    for row in coverage:
        actual=result[(row['day'],row['raw_symbol'])]
        for field in ['rth_volume','second_records','observed_5m_bars','expected_5m_bars','missing_5m_buckets','complete_5m_grid']:
            require(row[field]==actual[field],'Recomputed price coverage mismatch: '+row['day']+'/'+row['raw_symbol']+'/'+field)
        require(actual['quality_flags']==[row['vendor_quality_flag']],'Vendor quality flag mismatch')
    return result,coverage,monthproof


def summarize_sessions(schedule,observed,lo,hi):
    sessions=[]
    for row in schedule:
        if not lo<=row['day']<hi:continue
        symbol=row['raw_symbol'];actual=observed.get((row['day'],symbol))
        require(symbol is not None and actual is not None,'Missing selected role session: '+row['day'])
        warm=[]
        for w in row['warmup_previous_five_same_contract_sessions']:
            value=observed.get((w['day'],symbol))
            require(w['complete_5m_grid']==bool(value and value['complete_5m_grid']),'Warmup coverage differs from raw second data')
            warm.append(dict(w,second_records=value['second_records'] if value else 0,missing_5m_buckets=value['missing_5m_buckets'] if value else None))
        sessions.append(dict(row,actual_price_coverage=actual,warmup_price_details=warm))
    require(bool(sessions),'Empty role sessions')
    counts=Counter(s['calendar_status'] for s in sessions)
    gaps=[s for s in sessions if not s['actual_price_coverage']['complete_5m_grid']]
    unready=[s for s in sessions if not s['warmup_complete']]
    summary=dict(planned_open_sessions=len(sessions),selected_sessions_with_prices=len(sessions),selected_second_records=sum(s['actual_price_coverage']['second_records'] for s in sessions),sessions_with_incomplete_current_5m_grid=len(gaps),sessions_with_incomplete_prior5_warmup=len(unready),calendar_status_counts=dict(counts),retained_quality_flags=dict(Counter(flag for s in sessions for flag in s['actual_price_coverage']['quality_flags'])),median_present_second_records=float(np.median([s['actual_price_coverage']['second_records'] for s in sessions])),max_absent_print_run_seconds=max(s['actual_price_coverage']['max_absent_run_seconds'] for s in sessions),calendar_shortened_sessions=sum(s['session_close_ns']-s['session_open_ns']<450*60*NS for s in sessions))
    return sessions,summary


def audit(role):
    freeze=check_frozen_integrity()
    require(not (TASK/f'Private/{role}-label-attempt.json').exists(),'Price audit must precede the one-shot role label marker')
    months,schedule=dispatch.period_sources(role) # All role files/hashes required, no candidate execution.
    known_months,known_schedule=dispatch.known.known_sources() # PRICE-only known baseline, no model test.
    calendar=Calendar();all_months=dict(known_months);all_months.update(months)
    observed,coverage,monthproof=collect_months(all_months,calendar)
    role_coverage=[r for r in coverage if r['day'][:7] in months]
    independent,lookup=independent_roll(role_coverage,month_days(months,calendar),calendar)
    require(independent==schedule,'Independent prior-session roll/calendar/warmup schedule differs from frozen dispatch')
    lo,hi=dispatch.PERIODS[role]
    selected,summary=summarize_sessions(schedule,observed,lo,hi)
    expected_days=[d for d in month_days(months,calendar) if lo<=d<hi]
    require([s['day'] for s in selected]==expected_days,'Selected role sessions differ from entire planned calendar')
    known_selected,known_summary=summarize_sessions(known_schedule,observed,'2025-11-24','2026-10-31')
    require(len(known_selected)==242 and known_summary['sessions_with_incomplete_prior5_warmup']==2,'Known price-only comparison baseline changed')
    private=TASK/f'Private/{role}-price-completeness-sessions.json'
    require(not private.exists(),'Preserve previous price audit rather than overwrite')
    save(private,selected)
    deviations=[dict(day=s['day'],raw_symbol=s['raw_symbol'],current_missing_5m_buckets=s['actual_price_coverage']['missing_5m_buckets'],warmup_complete=s['warmup_complete'],quality_flags=s['actual_price_coverage']['quality_flags']) for s in selected if not s['warmup_complete'] or not s['actual_price_coverage']['complete_5m_grid'] or s['actual_price_coverage']['quality_flags']!=['no_explicit_vendor_degradation_flag_recorded']]
    deviation_path=TASK/f'Private/{role}-price-completeness-deviations.json';save(deviation_path,deviations)
    proof=dict(schema='role-price-completeness-v1',status='PASS_PRICE_INTEGRITY_AND_SESSION_ENUMERATION',role=role,utc=utcnow(),period_start_inclusive=lo,period_end_exclusive=hi,required_months=dispatch.required_months(role),all_role_months_complete=True,all_raw_second_5m_mapping_coverage_hashes_verified=True,all_price_row_counts_independently_recounted=True,all_planned_role_sessions_present=True,prior_session_only_roll_independently_equal=True,all_warmup_grids_recomputed_from_seconds=True,summary=summary,known_price_only_baseline=known_summary,role_month_proofs={m:monthproof[m] for m in months},known_month_manifest_hashes={m:monthproof[m]['manifest_sha256'] for m in known_months},sessions_private_file=private.name,sessions_private_sha256=sha(private),deviations_private_file=deviation_path.name,deviations_private_sha256=sha(deviation_path),coverage_deviations=len(deviations),coverage_deviations_require_root_review=bool(deviations),missing_seconds_interpretation='AbsentOHLCVprintintervalsarenotprovenfeedlossandarenotfilled;explicit5m/warmupdeviationsretainedwithfrozeneligibilityrules',calendar_overlay_sha256=freeze['calendar_overlay_sha256'],native_acceptance_sha256=dispatch.KNOWN_ACCEPTANCE_SHA,independent_native_audit_sha256=dispatch.KNOWN_AUDIT_SHA,period_source_freeze_sha256=PERIOD_FREEZE_SHA,audit_source_sha256=sha(__file__),price_audit_source_freeze_sha256=sha(TASK/'Public/price-completeness-audit-source-freeze.json'),price_only=True,no_candidate_or_label_files_read=True,no_signals_labels_models_or_API_calls=True,known_year_is_DATA_acceptance_only_no_model_performance_supplement=True)
    target=TASK/f'Public/{role}-price-completeness.json';require(not target.exists(),'Price completeness proof already exists')
    save(target,proof);print(json.dumps(dict(path=str(target),sha256=sha(target),summary=summary),indent=2))
    return proof


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--role',choices=list(dispatch.PERIODS),required=True);args=parser.parse_args()
    try:audit(args.role)
    except Exception as error:
        save(TASK/f'Public/{args.role}-price-audit-failure-{__import__("time").time_ns()}.json',dict(utc=utcnow(),status='PRICE_ONLY_AUDIT_CLOSED',error_type=type(error).__name__,error=str(error),no_signals_labels_models_or_API_calls=True));raise
