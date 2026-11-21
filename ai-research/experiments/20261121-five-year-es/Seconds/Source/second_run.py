"""ONE guarded1s known-year reconstruction, no model fitting or API calls.

Requires all12knownprice months and exact published protocol bindings in a
root authorization receipt. Never reads a whole parent or whole year dataframe.
"""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,csv,hashlib,importlib.util,json,math,time
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy.stats import spearmanr
from price_extract_support import HERE,ROOT,Calendar,sha,save,utcnow,select_prior
from second_kernel import *

KNOWN_MONTHS=['2025-11','2025-12']+[f'2026-{m:02d}' for m in range(1,11)]


def verify_frozen_sources(freeze,source_directory,fixtures_path):
    """Control-plane integrity only; run before any marketdata/outcome access."""
    for name,expected in freeze['sources_sha256'].items():
        if sha(Path(source_directory)/name)!=expected:raise ValueError('FrozenSourcehashmismatch:'+name)
    if sha(fixtures_path)!=freeze['fixtures_sha256']:raise ValueError('Frozenfixtureproofhashmismatch')


def authorize(receipt):
    value=json.loads(Path(receipt).read_text())
    if value.get('authorized') is not True or value.get('mode')!='known':raise ValueError('Only explicitlyauthorizedknown-yearone-shotpreflightallowed')
    bindings=value.get('protocol_files',[])
    if len(bindings)<3:raise ValueError('Publishedprotocol+entryguard/unanimity+proxy/precommitclarificationsrequired')
    for item in bindings:
        if sha(item['path'])!=item['sha256']:raise ValueError('Protocolfilehashmismatch')
    if (HERE/'Private/second-candidates-known.jsonl').exists():raise ValueError('One-shotknowncandidatesalreadyexist; noautomaticrerun')
    freeze_path=Path(value.get('source_freeze_path',HERE/'Public/second-source-freeze-v2.json'))
    if value.get('source_freeze_sha256')!=sha(freeze_path):raise ValueError('RootGOdoesnotbindexactno-resultsourcefreeze')
    freeze=json.loads(freeze_path.read_text())
    verify_frozen_sources(freeze,HERE/'Source',HERE/'Public/second-fixtures.json')
    value['source_freeze_path']=str(freeze_path)
    return value


def known_sources():
    calendar=Calendar();months={};coverage=[]
    for month in KNOWN_MONTHS:
        p=HERE/'Private/Months'/month/'manifest.json'
        if not p.exists():raise ValueError('All12knownmonthsrequired; missing'+month)
        m=json.loads(p.read_text())
        if m['status']!='COMPLETE_LOCAL_1S_PRICE_ONLY' or m['zero_cost_download_receipt']['quoted_cost_USD']!=0:raise ValueError('Incomplete/nonzero inputproof')
        for shard in m['second_shards']:
            if sha(HERE/shard['path_relative_to_task'])!=shard['sha256']:raise ValueError('RawcontractpriceParquetchanged')
        q=p.parent/'contract-session-price-coverage.json'
        if sha(q)!=m['session_coverage_sha256']:raise ValueError('Pricecoverageproofchanged')
        coverage.extend(json.loads(q.read_text()));months[month]=m
    byday=defaultdict(list);lookup={}
    for row in coverage:byday[row['day']].append(row);lookup[(row['day'],row['raw_symbol'])]=row
    start=min(row['day'] for row in coverage);end='2026-10-30'
    from datetime import date,timedelta
    first=date.fromisoformat(start);last=date.fromisoformat(end)
    days=[str(first+timedelta(days=i)) for i in range((last-first).days+1) if calendar.get(str(first+timedelta(days=i))) is not None]
    incumbent=None;prior=None;schedule=[]
    for pos,day in enumerate(days):
        selected=select_prior(byday[prior],incumbent) if prior else None;symbol=selected['raw_symbol'] if selected else None
        warm=[]
        for previous in days[max(0,pos-5):pos]:
            r=lookup.get((previous,symbol));warm.append(dict(day=previous,raw_symbol=symbol,complete_5m_grid=bool(r and r['complete_5m_grid'])))
        schedule.append(dict(day=day,raw_symbol=symbol,selection_information_day=prior,**calendar.get(day),warmup_previous_five_same_contract_sessions=warm,warmup_complete=len(warm)==5 and all(w['complete_5m_grid'] for w in warm)))
        if selected:incumbent=symbol
        prior=day
    known=[s for s in schedule if '2025-11-24'<=s['day']<'2026-10-31']
    if len(known)!=242 or any(s['calendar_status']!='exact_native_session_metadata' for s in known):raise ValueError('Exact242nativecalendarrequired')
    return months,schedule


def read_day(months,symbol,day):
    month=months[day[:7]];shard=next((x for x in month['second_shards'] if x['raw_symbol']==symbol),None)
    if shard is None:return []
    columns=['ts_event_ns','instrument_id','open_nanos','high_nanos','low_nanos','close_nanos','volume','vendor_quality_flag']
    data=pq.read_table(HERE/shard['path_relative_to_task'],columns=columns,filters=[('day','=',day)]).to_pydict()
    if not data['ts_event_ns']:return []
    stamps=np.array(data['ts_event_ns'],dtype=np.int64)
    if np.any(np.diff(stamps)<=0) or len(set(data['instrument_id']))!=1:raise ValueError('Noncanonicalperdayrawcontractsecondorder/ID')
    return [dict(day=day,ts_event_ns=int(ns),open=data['open_nanos'][i]/1e9,high=data['high_nanos'][i]/1e9,low=data['low_nanos'][i]/1e9,close=data['close_nanos'][i]/1e9,volume=int(data['volume'][i]),vendor_quality_flag=data['vendor_quality_flag'][i]) for i,ns in enumerate(stamps)]


def native_reference():
    path=ROOT/'outputs/AI-Forschung-20261120/repo/ai-research/train_ml1.py'
    spec=importlib.util.spec_from_file_location('frozen_native347_reader',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    dates,rows,proof=module.data();lookup={(r['segment'],r['ns']):r for r in rows if r['day'] in dates};native=[]
    for verified in sorted((ROOT/'outputs/AI-Forschung-20261120/SQX/observer').glob('*/verified.json')):
        v=json.loads(verified.read_text());segment=verified.parent.name
        for c in csv.DictReader((Path(v['folder'])/'candidates.csv').open()):
            r=lookup.get((segment,int(c['entry_decision_ns'])))
            if r is None:continue
            native.append(dict(contract=segment.rsplit('-',1)[-1],day=r['day'],side=1 if c['side']=='LONG' else-1,signal_ns=r['ns'],stress_net_usd=r['stress_net_cents']/100,stress_net_R=r['stress_net_cents']/100/r['features'][0],risk=r['features'][0],slope=r['features'][2],relvol=r['features'][3],minute=r['features'][4]))
    assert len(native)==347
    return sorted(native,key=lambda r:r['signal_ns']),dict(native_reader_sha256=sha(path),native_sources=proof)


def metadata_pairs(native,cases):
    proposed=[]
    for ni,n in enumerate(native):
        for ci,c in enumerate(cases):
            if any(n[k]!=c[k] for k in ['contract','day','side']):continue
            difference=abs(n['signal_ns']-c['signal_ns'])
            if difference<=300*NS:proposed.append((difference,n['signal_ns'],c['signal_ns'],ni,ci))
    usedn=set();usedc=set();matched=[]
    for difference,_,__,ni,ci in sorted(proposed):
        if ni in usedn or ci in usedc:continue
        usedn.add(ni);usedc.add(ci);matched.append((ni,ci,difference))
    return matched


def acceptance(cases,binding):
    native,proof=native_reference();pairs=metadata_pairs(native,cases);rows=[]
    for ni,ci,difference in pairs:
        n,c=native[ni],cases[ci]
        rows.append(dict(native_signal_ns=n['signal_ns'],second_case_key=c['case_key'],second_signal_ns=c['signal_ns'],contract=n['contract'],day=n['day'],side=n['side'],absolute_decision_offset_seconds=difference/NS,signed_decision_offset_seconds=(c['signal_ns']-n['signal_ns'])/NS,native_stress_net_R=n['stress_net_R'],second_stress_net_R=c['stress_net_R'],net_R_error=c['stress_net_R']-n['stress_net_R'],native_stress_net_usd=n['stress_net_usd'],second_stress_net_usd=c['stress_net_usd'],risk_error=c['planned_risk_usd']-n['risk'],slope_error=c['feature_signed_completed_ema_slope_atr']-n['slope'],relvol_error=c['feature_completed_relative_volume20']-n['relvol'],session_minute_error=c['feature_chicago_session_minute']-n['minute']))
    frame=pd.DataFrame(rows);frame.to_csv(HERE/'Private/second-native-matched-pairs.csv',index=False)
    count=len(rows);rho=float(spearmanr(frame.native_stress_net_R,frame.second_stress_net_R).statistic) if count>=2 else None
    if rho is not None and not math.isfinite(rho):rho=None
    sign=float(((frame.native_stress_net_usd>0)==(frame.second_stress_net_usd>0)).mean()) if count else None
    mean=float(frame.net_R_error.mean()) if count else None
    metrics=dict(native_candidates=347,second_candidates=len(cases),matches=count,native_recall=count/347,second_precision=count/len(cases) if cases else 0.,NettoR_Spearman=rho,stress_profit_sign_agreement=sign,mean_net_R_error_second_minus_native=mean,absolute_signed_mean_R_error=abs(mean) if mean is not None else None,mean_absolute_net_R_error=float(frame.net_R_error.abs().mean()) if count else None,mean_stress_USD_error=float((frame.second_stress_net_usd-frame.native_stress_net_usd).mean()) if count else None,mean_absolute_stress_USD_error=float((frame.second_stress_net_usd-frame.native_stress_net_usd).abs().mean()) if count else None,median_absolute_decision_offset_seconds=float(frame.absolute_decision_offset_seconds.median()) if count else None,max_absolute_decision_offset_seconds=float(frame.absolute_decision_offset_seconds.max()) if count else None)
    thresholds=dict(minimum_matches=100,minimum_native_recall=.70,minimum_second_precision=.70,minimum_NettoR_Spearman=.60,minimum_stress_profit_sign_agreement=.75,maximum_absolute_signed_mean_R_error=.05)
    checks=dict(minimum_matches=count>=100,minimum_native_recall=metrics['native_recall']>=.70,minimum_second_precision=metrics['second_precision']>=.70,minimum_NettoR_Spearman=rho is not None and rho>=.60,minimum_stress_profit_sign_agreement=sign is not None and sign>=.75,maximum_absolute_signed_mean_R_error=mean is not None and abs(mean)<=.05)
    deviations={k:dict(mean_signed=float(frame[k+'_error'].mean()),mean_absolute=float(frame[k+'_error'].abs().mean()),max_absolute=float(frame[k+'_error'].abs().max())) for k in ['risk','slope','relvol','session_minute']} if count else {}
    result=dict(status='PASS' if all(checks.values()) else 'FAIL',accepted=all(checks.values()),utc=utcnow(),thresholds=thresholds,checks=checks,metrics=metrics,feature_deviations=deviations,ambiguous_native_cases_never_pruned=True,native_reference_denominator=347,sourcehashes=dict(**binding,**proof),no_older_labels=True,no_models_fit=True,next_action='Verifyoldercalendarandobtainexplicitrootreleasebeforeolderlabels;nofithere' if all(checks.values()) else 'STOPbar-reconstructionrouteafterthisONE1sattempt;noolderlabels/training;noalternateresolution/threshold/featurepolicy')
    save(HERE/'Public/second-native-acceptance.json',result);print(json.dumps(result,indent=2),flush=True)
    return result


def run(receipt):
    authorization=authorize(receipt);began=time.time();months,schedule=known_sources()
    known=[s for s in schedule if '2025-11-24'<=s['day']<'2026-10-31'];clock_byday={s['day']:s for s in schedule}
    save(HERE/'Private/second-known-price-roll-freeze.json',schedule)
    binding=dict(source_freeze_sha256=sha(authorization['source_freeze_path']),root_go_sha256=sha(receipt),known_schedule_sha256=sha(HERE/'Private/second-known-price-roll-freeze.json'),month_manifest_sha256={m:sha(HERE/'Private/Months'/m/'manifest.json') for m in KNOWN_MONTHS},builder_sha256=sha(Path(__file__)),kernel_sha256=sha(Path(__file__).with_name('second_kernel.py')))
    save(HERE/'Public/second-execution-start.json',dict(utc=utcnow(),mode='known',no_older_labels=True,**binding))
    episodes=[]
    for s in known:
        if s['raw_symbol'] is None:continue
        if not episodes or episodes[-1]['symbol']!=s['raw_symbol']:episodes.append(dict(symbol=s['raw_symbol'],sessions=[]))
        episodes[-1]['sessions'].append(s)
    cases=[];exclusions=[];ambiguities=[];stats=Counter();feature_proof=[]
    for episode in episodes:
        symbol=episode['symbol'];book=SecondBook();first=episode['sessions'][0]
        warm=[w['day'] for w in first['warmup_previous_five_same_contract_sessions']];active={s['day']:s for s in episode['sessions']}
        baseline_busy_until=-1;baseline_entry_ns=None
        for day in warm+[s['day'] for s in episode['sessions']]:
            rows=read_day(months,symbol,day);clock=clock_byday[day];previews=[];features=[]
            for row in rows:
                preview=book.step(row,clock);previews.append(preview)
                if day not in active:continue
                stats['known_seconds_processed']+=1
                if preview['ambiguous_first_return']:
                    stats['ambiguous_return_seconds_all_windows']+=1
                    if preview['signal_ns']<clock['flatten_ns'] and active[day]['warmup_complete'] and preview['current_past_5m_grid_complete']:
                        stats['ambiguous_return_seconds_entry_eligible_clock_and_history']+=1
                        ambiguities.append(dict(contract=symbol,day=day,signal_ns=preview['signal_ns'],state_mask_before=preview['state_mask_before'],state_mask_after=preview['state_mask_after'],possible_event_patterns=preview['possible_event_patterns'],paths_considered=preview['paths_considered']))
                side=preview['consensus_side']
                if not side:continue
                stats['unanimous_single_return_seconds']+=1;signal=preview['signal_ns'];reason=None
                if signal>=clock['flatten_ns']:reason='consumed_consensus_at_or_after_flatten'
                elif not active[day]['warmup_complete']:reason='consumed_consensus_incomplete_prior_five_same_contract_warmup'
                elif not preview['current_past_5m_grid_complete']:reason='consumed_consensus_missing_past_current5m_bucket'
                if reason:exclusions.append(dict(contract=symbol,day=day,signal_ns=signal,side=side,reason=reason));continue
                feature,reason=decision_features(side,row['close'],preview,clock)
                if reason:exclusions.append(dict(contract=symbol,day=day,signal_ns=signal,side=side,reason=reason));continue
                features.append(dict(case_key=hashlib.sha256(f'C28_1s_consensus_v2|{symbol}|{signal}|{side}'.encode()).hexdigest(),contract=symbol,day=day,signal_ns=signal,side=side,decision_price=row['close'],**feature,vendor_quality_flag=row['vendor_quality_flag'],source_resolution='OHLCV1s_prescribed_order_scenarios_not_TBBO',state_mask_before=preview['state_mask_before'],state_mask_after=preview['state_mask_after']))
            if day not in active:continue
            # Freeze thisday's features without any label-dependent selection.
            digest=hashlib.sha256(json.dumps(features,sort_keys=True,allow_nan=False).encode()).hexdigest()
            feature_proof.append(dict(contract=symbol,day=day,feature_candidates=len(features),features_before_labels_sha256=digest))
            for candidate in features:
                signal=candidate['signal_ns'];available=signal>=baseline_busy_until
                was_flat=baseline_entry_ns is None or not(baseline_entry_ns<=signal<baseline_busy_until)
                result=delayed_shadow(candidate,rows,previews,clock)
                if result['label_status']!='ok':
                    exclusions.append(dict(contract=symbol,day=day,signal_ns=signal,side=candidate['side'],reason=result['label_status']))
                    if available and result.get('entry_cancel_ns') is not None:baseline_busy_until=result['entry_cancel_ns'];baseline_entry_ns=None
                    continue
                candidate.update(result,base_was_flat=bool(was_flat),base_available_for_entry=bool(available))
                if available:baseline_busy_until=result['exit_ns'];baseline_entry_ns=result['entry_ns']
                cases.append(candidate)
            save(HERE/'Public/second-preflight-progress.json',dict(status='RUNNING_KNOWN_ONLY_ONE_ATTEMPT',contract=symbol,last_day=day,cases_so_far=len(cases),ambiguities_so_far=len(ambiguities),known_seconds_processed=stats['known_seconds_processed'],elapsed_seconds=time.time()-began,no_older_labels=True,no_models=True))
            print('known1s',symbol,day,'filledcases',len(cases),'ambiguous',len(ambiguities),flush=True)
    cases.sort(key=lambda c:(c['signal_ns'],c['contract'],c['side']))
    if not cases:raise ValueError('No genuinefilledknown1scandidates')
    if not all('2025-11-24'<=c['day']<'2026-10-31' for c in cases):raise ValueError('Guard:labeloutsideknownwindow')
    if len({c['case_key'] for c in cases})!=len(cases):raise ValueError('Duplicated1scandidate')
    jsonl=HERE/'Private/second-candidates-known.jsonl';jsonl.write_text(''.join(json.dumps(c,allow_nan=False)+'\n' for c in cases))
    csvpath=HERE/'Private/second-candidates-known.csv';pd.DataFrame(cases).to_csv(csvpath,index=False)
    save(HERE/'Private/second-known-exclusions.json',exclusions);save(HERE/'Private/second-known-ambiguities.json',ambiguities);save(HERE/'Private/second-known-feature-before-label-proof.json',feature_proof)
    binding.update(candidates_jsonl_sha256=sha(jsonl),candidates_csv_sha256=sha(csvpath))
    summary=dict(status='KNOWN_1S_SINGLE_ATTEMPT_RECONSTRUCTION_COMPLETE',utc=utcnow(),cases=len(cases),days=len({c['day'] for c in cases}),stats=dict(stats),exclusion_reasons=dict(Counter(e['reason'] for e in exclusions)),degraded_date_cases_retained=sum(c['day']=='2025-11-28' for c in cases),latency_gaps=dict(max_entry_extra_seconds=max(c['entry_gap_extra_seconds'] for c in cases),max_exit_extra_seconds=max(c['exit_gap_extra_seconds'] for c in cases),entries_with_gap=sum(c['entry_gap_extra_seconds']>0 for c in cases),exits_with_gap=sum(c['exit_gap_extra_seconds']>0 for c in cases)),elapsed_seconds=time.time()-began,no_older_labels=True,no_models_fit=True,**binding)
    save(HERE/'Public/second-known-summary.json',summary)
    result=acceptance(cases,binding)
    save(HERE/'Public/second-preflight-progress.json',dict(status='FINISHED_'+result['status'],cases=len(cases),elapsed_seconds=time.time()-began,no_older_labels=True,no_models=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--receipt',type=Path,required=True);args=parser.parse_args()
    try:run(args.receipt)
    except Exception as error:
        save(HERE/'Public'/f'second-failure-{time.time_ns()}.json',dict(status='FAILED_ONE_SHOT_PRESERVE_EVIDENCE',utc=utcnow(),error_type=type(error).__name__,error=str(error),no_older_labels=True,no_models=True));raise
