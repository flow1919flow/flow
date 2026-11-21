"""Synthetic causal/execution fixtures before the known-year preflight."""
import copy, json, tempfile
from pathlib import Path
import pandas as pd
from coarse_candidates import *
from extract_prices import aggregate_5m,select,derive_schedule


def main():
    tests=[];day='2026-10-01';op=session_ns(day,'08:30');cal=dict(session_open_ns=op,session_close_ns=session_ns(day,'16:00'),flatten_ns=session_ns(day,'15:09'))
    state=Indicators();state.ema=100.;state.atr=2.;state.previous_close=200.;state.closes=deque([100.]*19,maxlen=19)
    state.last_completed_ema=100.;state.prior_completed_ema=99.;state.closed_atr=2.;state.volumes=deque([10.]*20,maxlen=20)
    r=dict(date=day,bar_index=0,ts_event_ns=op,open=100.,high=103.,low=99.,close=101.,volume=5.)
    preview=state.step(r,cal)
    assert abs(preview['center']-(100+2/21))<1e-12
    assert abs(preview['atr']-2.2)<1e-12 # first daybar ignores priorclose200
    assert abs(preview['bb_upper']-(100.05+1.75*math.sqrt(.0475)-.1875))<1e-12
    tests.append('Golden native EMA20 forming, firstdaybar ATR10 TR=H-L, BB20 population sigma and0.75tickoffset')
    for i in range(1,5):state.step(dict(r,ts_event_ns=op+i*60*NS),cal)
    state.step(dict(r,bar_index=1,ts_event_ns=op+300*NS,high=103.,low=102.,close=102.5),cal)
    assert state.relative_volume==2.5
    assert abs(state.atr-2.2)<1e-12
    assert abs(state.atr_at()-2.18)<1e-12
    tests.append('Five-minute commits preserve Wilder memory, laterTRincludespreviousclose, relativevolume compareslastclosedbaragainst20precedingbars')
    template=dict(center=100.,atr=5.,bb_upper=120.,bb_lower=80.,or_high=105.,or_low=95.,or_active=False,completed_ema=100.,previous_completed_ema=99.,completed_atr=2.,relative_volume=1.5)
    a,_=decision_features(1,100.,template,op+30*60*NS,op)
    b,_=decision_features(1,100.,dict(template,or_high=1000.),op+30*60*NS,op)
    assert a==b and a['decision_OR_level'] is None
    leaky_a,_=decision_features(1,100.,dict(template,or_active=True),op+30*60*NS,op)
    leaky_b,_=decision_features(1,100.,dict(template,or_active=True,or_high=1000.),op+30*60*NS,op)
    assert leaky_a['feature_target_path_R']!=leaky_b['feature_target_path_R']
    tests.append('PreORdecisionfeature ignoresfuturecompletedOR; intentionallyleakyORpositivecontrolchangesandisdetected')
    neg,_=decision_features(1,100.,dict(template,bb_upper=99.),op+30*60*NS,op)
    assert neg['feature_target_path_R']<0
    tests.append('Zero/negativeBBdirectionalpathsremainvalidsignedfeatures; no outcome-basedtargetexclusion')
    active,_=decision_features(1,100.,dict(template,or_active=True),op+60*60*NS,op)
    assert active['feature_target_path_R']==5/(100-active['stop_price'])
    tests.append('ORfeatureusesdecisioncloseproxyonly; futureactualentryopenisnotanargument')
    prefix=[]
    for i in range(80):
        close=100+2*math.sin(i/8)
        prefix.append(dict(date=day,bar_index=i//5,ts_event_ns=op+i*60*NS,open=close-.1,high=close+.2,low=close-.2,close=close,volume=10+i%3))
    def run(seq):
        z=Indicators();return [z.step(row,cal) for row in seq]
    before=run(prefix[:30]);mutated=copy.deepcopy(prefix)
    for row in mutated[30:]:row.update(open=10000.,high=20000.,low=-10000.,close=10000.,volume=10**12)
    assert before==run(mutated)[:30]
    tests.append('Physicalprefix: truncatingallminutesafterpreORdecisionorpoisoningfutureOHLCVcannotchangeanypriorprevieworcontact/returnstate')
    # All same-minute exit collisions must follow the frozen stop priority.
    c=dict(side=1,signal_ns=op+61*60*NS,stop_price=95.,planned_risk_usd=279.68)
    pp=dict(bb_upper=110.,bb_lower=90.,or_high=105.,or_low=95.)
    rows=[dict(ts_event_ns=c['signal_ns'],open=94.,high=106.,low=93.,close=104.)]
    result=label_one(c,rows,[pp],cal)
    assert result['exit_reason']=='entry_beyond_stop_immediate' and result['entry_price']==result['exit_price']==94. and abs(result['stress_net_usd']+29.68)<1e-12
    tests.append('Entrygapbeyondfixedstopisimmediateatentryopen,fees/stressretained; gapopenneverusedindecisionfeatures')
    rows=[dict(ts_event_ns=c['signal_ns'],open=100.,high=106.,low=94.,close=104.)]
    result=label_one(c,rows,[pp],cal)
    assert result['exit_reason']=='fixed_stop_touch' and result['exit_price']==95. and result['exit_ns']==c['signal_ns']+60*NS
    tests.append('Same1mbarhitsstopandOR:stopwins; OHLCtouchinformationclockisconservativeminuteEND')
    rows=[dict(ts_event_ns=c['signal_ns'],open=100.,high=102.,low=99.,close=101.),dict(ts_event_ns=c['signal_ns']+60*NS,open=94.,high=95.,low=93.,close=94.)]
    result=label_one(c,rows,[dict(pp,bb_upper=100.),pp],cal)
    assert result['exit_reason']=='stop_gap_open' and result['exit_price']==94.
    tests.append('NextopenadversegapstophaspriorityoverpriorBBclosecrossscheduledexit')
    missing=label_one(c,[dict(rows[0],ts_event_ns=c['signal_ns']+60*NS)],[pp],cal)
    assert missing['label_status']=='excluded_missing_exact_next_minute_open'
    tests.append('Missingexactnextentryminuteisreportedexclusion; neverjumpaheadtoinventexecutionliquidity')
    fl=dict(c,signal_ns=cal['flatten_ns']);one=dict(ts_event_ns=fl['signal_ns'],open=100.,high=101.,low=99.,close=100.)
    assert label_one(fl,[one],[pp],cal)['exit_reason']=='session_flatten_first_open'
    tests.append('Nativeflattenexitsfirstobservedopenatcutoff; no sessionclose15:00substitution')
    # Exercise actual state-machine ordering, not just an expected output label.
    q=Indicators();q.ema=100.;q.atr=1.;q.previous_close=100.;q.closes=deque([100.]*19,maxlen=19);q.last_band=1;q.setup_side=1
    output=q.step(dict(r,high=100.,low=95.,close=95.),cal)
    assert output['first_return_side']==1 and q.setup_side==-1 and q.last_band==-1
    tests.append('Existingreturnisconsumedbeforecurrentcloseestablishesoppositebandsetup')
    assert outward(99.99999999999999,1)==100. and outward(100.00000000000001,-1)==100.
    tests.append('Nativeoutwardtickroundingretainsnear-integertickswithoutfloatingpointoffbyone')
    d1,d2='2022-03-11','2022-03-14';d3,d4='2022-11-04','2022-11-07'
    assert session_ns(d1,'08:30')-session_ns(d1,'00:00')==int(8.5*3600*NS)
    assert datetime.fromtimestamp(session_ns(d1,'08:30')//NS,timezone.utc).hour==14 and datetime.fromtimestamp(session_ns(d2,'08:30')//NS,timezone.utc).hour==13
    assert datetime.fromtimestamp(session_ns(d3,'08:30')//NS,timezone.utc).hour==13 and datetime.fromtimestamp(session_ns(d4,'08:30')//NS,timezone.utc).hour==14
    assert all(session_ns(d,'16:00')-session_ns(d,'08:30')==450*60*NS for d in [d1,d2,d3,d4])
    tests.append('CivilChicagoDSTspring/fallshiftsUTCopenbyonehourwhilekeeping450minuteRTH')
    prior=[dict(raw_symbol='ESZ5',rth_volume=100),dict(raw_symbol='ESH6',rth_volume=100),dict(raw_symbol='ESU5',rth_volume=100000)]
    assert select(prior,'ESZ5')['raw_symbol']=='ESZ5'
    assert select([dict(raw_symbol='ESH6',rth_volume=101),prior[0]],'ESZ5')['raw_symbol']=='ESH6'
    tests.append('Priorvolumeonlyselection:tiesretainincumbent; no backwardmaturityevenifoldercontractvolumegreater')
    smallcal={d:dict(session_open_ns=session_ns(d,'08:30'),session_close_ns=session_ns(d,'16:00'),flatten_ns=session_ns(d,'15:09'),calendar_status='fixture') for d in ['2026-10-01','2026-10-02','2026-10-05']}
    sessions=[dict(date=d,raw_symbol='ESZ6',rth_volume=100,observed_5m_bars=90,complete_5m_grid=True) for d in smallcal]
    original=derive_schedule(sessions,smallcal);changed=copy.deepcopy(sessions)
    changed[1]['rth_volume']=10**15
    assert original[:2]==derive_schedule(changed,smallcal)[:2]
    tests.append('Rollprefix/currentdayvolumepoisoncannotchangeselectionatthatdaysopen')
    proto=ROOT/'outputs/ES-FiveYear-ML-20261121/Public/preregister.json'
    with tempfile.TemporaryDirectory() as temp:
        receipt=Path(temp)/'receipt.json';receipt.write_text(json.dumps(dict(authorized=True,mode='sealed',protocol_sha256=PROTOCOL_SHA)))
        try:guard('sealed',proto,receipt)
        except ValueError:pass
        else:raise AssertionError('Sealedguardacceptednofrozenmodel')
    tests.append('SealedfourthyearoutcomeguardrejectsevenauthorizedmodewithoutfinalfrozenmodelSHAreceipt')
    manifest=json.loads((HERE/'Private/price-data-manifest.json').read_text());schedule=json.loads(Path(manifest['schedule_file']).read_text());known=[x for x in schedule if '2025-11-24'<=x['date']<'2026-10-31']
    assert len(known)==242 and all(x['calendar_status']=='observed_exact_native_seed' for x in known)
    assert all(x['selection_information_date']<x['date'] for x in known)
    tests.append('ActualcanonicalknownpricecalendarcontainsEXACT242nativeknownsessions; fullclosuresexcludedbeforepriorvolumeselection')
    minute=pd.read_parquet(manifest['minute_file']);bars=pd.read_parquet(manifest['all_contract_5m_file'])
    # Independent OHLCV reconciliation on both sides of month/DST/year edges.
    sample_dates=['2021-11-30','2021-12-01','2022-03-11','2022-03-14','2022-11-04','2022-11-07','2025-12-31','2026-01-02']
    checked=0
    for d in sample_dates:
        b=bars[(bars.date==d)&bars.complete_five_minute_records]
        if not len(b):continue
        # Highest observed volume bar is a price-only QA sample, not strategy selection.
        b=b.sort_values('volume',ascending=False).iloc[0]
        source=minute[(minute.date==d)&(minute.raw_symbol==b.raw_symbol)&(minute.bar_index==b.bar_index)].sort_values('ts_event_ns')
        assert len(source)==5
        assert int(b.open_nanos)==int(source.open_nanos.iloc[0]) and int(b.close_nanos)==int(source.close_nanos.iloc[-1])
        assert int(b.high_nanos)==int(source.high_nanos.max()) and int(b.low_nanos)==int(source.low_nanos.min()) and int(b.volume)==int(source.volume.sum())
        assert b.available_ns==b.bar_end_ns and b.bar_start_ns==int(source.ts_event_ns.min())
        checked+=1
    assert checked==8
    tests.append('Eightactualmonth/DST/yearboundary5mOHLCVbarsindependentlyreconciledtofiveoriginal1mrecords; pricesremainintegernano-units')
    from accept_known import match_metadata
    native=[dict(contract='ESZ6',day=day,side=1,signal_ns=op+100*NS,stress_net_R=100),dict(contract='ESZ6',day=day,side=1,signal_ns=op+200*NS,stress_net_R=-100)]
    coarse=[dict(contract='ESZ6',day=day,side=1,signal_ns=op+110*NS,stress_net_R=-999),dict(contract='ESZ6',day=day,side=1,signal_ns=op+205*NS,stress_net_R=999)]
    matched=match_metadata(native,coarse)
    for x in native+coarse:x['stress_net_R']=-x['stress_net_R']*1000000
    assert matched==match_metadata(native,coarse) and len({x[0] for x in matched})==len({x[1] for x in matched})==2
    tests.append('Greedyone-to-onematchingusesonlycontract/date/side/time; poisoningalloutcomescannotchangepairs')
    save(HERE/'Public/coarse-fixtures.json',dict(status='PASS',count=len(tests),tests=tests,utc=datetime.now(timezone.utc).isoformat(),protocol_sha256=PROTOCOL_SHA,no_real_candidate_or_outcome_generated=True,source_sha256={p.name:sha(p) for p in sorted((HERE/'Source').glob('*.py'))}))
    print(f'{len(tests)}synthetic/datafixturesPASS; norealcoarsecandidateexecuted')


if __name__=='__main__':main()
