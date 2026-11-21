"""Synthetic uncertainty/causalclock/latency fixtures before real1scandidates."""
import copy,json,math,tempfile
from pathlib import Path
from collections import deque
from price_extract_support import HERE,ROOT,Calendar,ct_ns,sha,save,utcnow
from second_kernel import *
from second_run import metadata_pairs,authorize,verify_frozen_sources


def seeded(day,clock,state=(1,0)):
    b=SecondBook();b.ema=100.;b.atr=1.;b.previous_close=100.;b.closes=deque([100.]*19,maxlen=19);b.volumes=deque([10]*20,maxlen=20)
    b.last_completed_ema=100.;b.previous_completed_ema=99.;b.closed_atr=1.;b.relative_volume=1.;b.closed_end_ns=clock['session_open_ns']-300*NS
    b.day=day;b.bucket=0;b.bar_start=clock['session_open_ns'];b.bar_end=b.bar_start+300*NS;b.high=101.;b.low=99.;b.close=100.;b.volume=0;b.first_bar=False;b.seen_buckets={0};b.state_mask=1<<STATE_INDEX[state]
    return b


def row(day,start,op=101.,hi=101.,lo=100.,cl=100.,volume=1):
    return dict(day=day,ts_event_ns=start,open=op,high=hi,low=lo,close=cl,volume=volume)


def preview(upper=105.,lower=90.,orhigh=105.,orlow=90.,active=True):
    return dict(BB_upper_at_high=upper,BB_lower_at_low=lower,OR_high=orhigh,OR_low=orlow,OR_active_for_second=active)


def main():
    tests=[];day='2026-10-01';clock=Calendar().get(day);op=clock['session_open_ns']
    b=seeded(day,clock,(1,1));p=b.step(row(day,op+5*NS),clock)
    assert p['consensus_side']==1 and not p['ambiguous_first_return'] and p['possible_event_patterns']==((1,),)
    tests.append('BothOHLCordersagreeexactlyONEsame-sidedreturn: consensuscandidateatSECONDEND,neverearliertouch')
    b=seeded(day,clock,(1,0));p=b.step(row(day,op+5*NS,101.,104.,96.,99.),clock)
    assert p['consensus_side']==0 and p['ambiguous_first_return'] and p['state_mask_after'].bit_count()==2
    carried=p['state_mask_after'];quiet=b.step(row(day,op+6*NS,99.5,99.5,99.5,99.5),clock)
    assert quiet['state_mask_before']==carried and quiet['state_mask_after']==carried and quiet['consensus_side']==0
    tests.append('UnknownH/Lorderbranchesinto2reachableendstates; quietnextseconddoesNOTcollapseunresolvedstateorpickprofitablepath')
    mask,side,ambiguous,patterns,_=propagate(1<<STATE_INDEX[(1,1)],{((2,1),(1,-1),(2,1))})
    assert patterns==((1,-1),) and side==0 and ambiguous
    tests.append('Evenunanimoustwo-returnsequenceisambiguous: exactlyONEreturnrequired,nosilentfirst/lastselection')
    b=seeded(day,clock,(1,0));b.atr=2.;b.previous_close=200.;b.day=None;b.bucket=None
    p=b.step(row(day,op,100.,103.,99.,101.),clock)
    assert abs(p['forming_center']-(100+2/21))<1e-12 and abs(p['forming_atr']-2.2)<1e-12
    assert abs(p['BB_upper_at_close']-(100.05+1.75*math.sqrt(.0475)-.1875))<1e-12
    tests.append('GoldenEMA20/firstdaybarATR10/BB20populationformulaatsecondEND')
    b=seeded(day,clock,(1,0));before=b.closed_end_ns
    endbar=b.step(row(day,op+299*NS,100.,101.,99.,101.,30),clock)
    assert endbar['signal_ns']==op+300*NS and endbar['completed_feature_end_ns']==before
    nextbar=b.step(row(day,op+300*NS,101.,101.,100.5,101.),clock)
    assert nextbar['completed_feature_end_ns']==op+300*NS and nextbar['completed_feature_end_ns']<=op+300*NS
    assert nextbar['completed_relative_volume20']==3.
    tests.append('PRECOMMITfeaturecut: secondending5mboundarycannotusecurrentbarincompletedfeatures; nextsecondcan; relvoluses20PRIORbars')
    samples=[row(day,op+(i+5)*NS,100+math.sin(i/6),100.5+math.sin(i/6),99.5+math.sin(i/6),100+math.sin(i/6),i+1) for i in range(120)]
    def run(seq):
        z=seeded(day,clock);return [z.step(r,clock) for r in seq]
    prefix=run(samples[:40]);future=copy.deepcopy(samples)
    for r in future[40:]:r.update(open=10000.,high=20000.,low=-10000.,close=10000.,volume=10**10)
    assert prefix==run(future)[:40]
    tests.append('Physicalprefixinvariance: futureOHLCVpoisoningcannotchangepriorfeatures,consensusorreachablemasks')
    fp=dict(forming_center=100.,forming_atr=5.,BB_upper_at_close=120.,BB_lower_at_close=80.,OR_high=105.,OR_low=95.,OR_active_for_decision=False,completed_ema=100.,previous_completed_ema=99.,completed_atr=2.,completed_relative_volume20=1.5,completed_feature_end_ns=op-300*NS,signal_ns=op+30*60*NS)
    a,_=decision_features(1,100.,fp,clock);c,_=decision_features(1,100.,dict(fp,OR_high=1000.),clock)
    assert a==c and a['decision_OR_level'] is None
    leaka,_=decision_features(1,100.,dict(fp,OR_active_for_decision=True),clock);leakb,_=decision_features(1,100.,dict(fp,OR_active_for_decision=True,OR_high=1000.),clock)
    assert leaka['feature_target_path_R']!=leakb['feature_target_path_R']
    tests.append('PreORfeatureignoresfuturehourrange; deliberatelyleakyORpositivecontrolchangesandisdetected')
    negative,_=decision_features(1,100.,dict(fp,BB_upper_at_close=99.),clock)
    assert negative['feature_target_path_R']<0 and negative['decision_quote_proxy']==100.25
    assert abs(negative['planned_risk_usd']-((100.25-negative['stop_price'])*50+29.68))<1e-10
    tests.append('RiskusesDECISIONclose+adversespread,notfuturefill; negativeBBpathretainedandnotabsolutedropped')
    # Syntheticactualfills start2safterdecision; allstop/targettoucheswaitEND+2s.
    signal=op+61*60*NS;cand=dict(side=1,signal_ns=signal,stop_price=95.,planned_risk_usd=292.18)
    prices=[row(day,signal+2*NS,100.,106.,94.,101.),row(day,signal+4*NS,90.,91.,89.,90.),row(day,signal+7*NS,92.,93.,91.,92.)]
    result=delayed_shadow(cand,prices,[preview()]*3,clock)
    assert result['exit_reason']=='stop_touch_second_end_delayed_market' and result['exit_decision_ns']==signal+3*NS and result['exit_ns']==signal+7*NS
    assert result['entry_price']==100.25 and result['exit_price']==91.75 and result['exit_gap_extra_seconds']==2
    tests.append('Stop+BB+ORsame1sbar:stoppriority; decideatEND, fillfirstPRESENTOpen>=END+2s, neveratstoplevel/targetlevel')
    guardcand=dict(cand,stop_price=100.);guardrows=[row(day,signal+2*NS,100.25,101.,100.,100.5)]
    rejected=delayed_shadow(guardcand,guardrows,[preview()],clock)
    assert rejected['label_status']=='excluded_delayed_entry_liquidation_proxy_beyond_stop'
    tests.append('NativeentryguardusesOPEN−side*tickliquidationproxybeforeOPEN+side*tickentryfill; spreadstraddlestopmustcancel')
    tinyclock=dict(clock,flatten_ns=signal+3*NS);late=[row(day,signal+4*NS,100.,101.,99.,100.)]
    assert delayed_shadow(cand,late,[preview()],tinyclock)['label_status']=='excluded_delayed_entry_at_or_after_flatten'
    tests.append('Delayedentryat/afterflatteniscancelled/consumed,notfilledtheninstantaneouslystopped')
    gaprows=[row(day,signal+2*NS,100.,101.,99.,100.),row(day,signal+3*NS,94.,95.,93.,94.),row(day,signal+6*NS,93.,94.,92.,93.)]
    gap=delayed_shadow(cand,gaprows,[preview(110.)]*3,clock)
    assert gap['exit_ns']==signal+6*NS and gap['exit_decision_ns']==signal+4*NS and gap['exit_price']==92.75
    tests.append('Filledpositionlatergapsbeyondstop: NOinstantgapstop orretroactivelevelprice; secondEND+2smarketexit')
    preserve=[row(day,signal+2*NS,100.,106.,99.,101.),row(day,signal+4*NS,100.,101.,94.,96.),row(day,signal+5*NS,96.,97.,95.,96.)]
    result=delayed_shadow(cand,preserve,[preview()]*3,clock)
    assert result['exit_reason']=='moving_BB_touch_second_end_delayed_market' and result['exit_ns']==signal+5*NS
    tests.append('ExistingBBexitintentpreservedthroughlatency; latertouchingstopdoesnotreplaceearlierintentusingfutureoutcome')
    flatclock=dict(clock,flatten_ns=signal+10*NS)
    flatrows=[row(day,signal+2*NS,100.,101.,99.,100.),row(day,signal+10*NS,100.,101.,99.,100.),row(day,signal+12*NS,99.,100.,98.,99.)]
    result=delayed_shadow(cand,flatrows,[preview(110.)]*3,flatclock)
    assert result['exit_reason']=='session_flatten_delayed_market' and result['exit_decision_ns']==flatclock['flatten_ns'] and result['exit_ns']==signal+12*NS
    tests.append('SchedulednativeflattenintentfillsfirstpresentOpen>=flatten+2s,notatflattenor15:00')
    native=[dict(contract='ESZ6',day=day,side=1,signal_ns=signal,stress_net_R=999.)];cases=[dict(contract='ESZ6',day=day,side=1,signal_ns=signal+NS,stress_net_R=-999.)]
    pairs=metadata_pairs(native,cases);native[0]['stress_net_R']=-1e99;cases[0]['stress_net_R']=1e99
    assert metadata_pairs(native,cases)==pairs
    tests.append('Greedy1:1time/contract/day/sidematchingindependentofallprofit/outcomevalues')
    with tempfile.TemporaryDirectory() as temp:
        path=Path(temp)/'receipt.json';path.write_text(json.dumps(dict(authorized=True,mode='sealed')))
        try:authorize(path)
        except ValueError:pass
        else:raise AssertionError('Older/sealedmodeaccepted')
    tests.append('Known-onlyauthorizationguardrejectssealed/oldermodebeforeanysourceoroutcomeaccess')
    with tempfile.TemporaryDirectory() as temp:
        directory=Path(temp);module=directory/'module.py';module.write_text('VALUE=1\n');fixture=directory/'fixtures.json';fixture.write_text('{"status":"PASS"}\n')
        freeze=dict(sources_sha256={'module.py':sha(module)},fixtures_sha256=sha(fixture))
        verify_frozen_sources(freeze,directory,fixture)
        module.write_text('VALUE=2\n')
        try:verify_frozen_sources(freeze,directory,fixture)
        except ValueError:pass
        else:raise AssertionError('ModifiedfrozenSourceaccepted')
        module.write_text('VALUE=1\n');fixture.write_text('{"status":"CHANGED"}\n')
        try:verify_frozen_sources(freeze,directory,fixture)
        except ValueError:pass
        else:raise AssertionError('Modifiedfixtureproofaccepted')
    tests.append('Beforemarketdata/signals: everyfrozenSourcehashandfixtureproofhashvalidated; modifiedtemporarysourceandfixturebothrejected')
    save(HERE/'Public/second-fixtures.json',dict(status='PASS',utc=utcnow(),fixtures=len(tests),tests=tests,no_actual1s_candidates_or_labels=True,no_API_calls=True,source_sha256={p.name:sha(p) for p in sorted((HERE/'Source').glob('second_*.py'))}))
    print(f'{len(tests)}synthetic1sfixturesPASS; noreal1scandidatesorlabels')


if __name__=='__main__':main()
