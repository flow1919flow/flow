"""Synthetic dispatch/release control fixtures; never computes older signals."""
from pathlib import Path
import copy,json,tempfile
import period_dispatch as dispatch
from price_extract_support import HERE,sha,save,utcnow,Calendar,NS
from second_fixtures import row,preview


def rejected(call,fragment):
    try:call()
    except (ValueError,FileNotFoundError,KeyError) as error:
        assert fragment in str(error),(fragment,str(error))
    else:raise AssertionError('Expected closed guard: '+fragment)


def main():
    checks=[]
    dispatch.verify_known_immutable()
    checks.append('All six frozen known Source files, original fixtures, native PASS and independent audit retain reviewed hashes')
    for role in dispatch.PERIODS:
        source=dispatch.derived_source(role)
        assert source==(HERE/f'Source/{role}_engine_generated.py').read_text()
        compile(source,role,'exec')
    checks.append('Both generated role engines reverse to exactly the frozen known run AST; same mathematical calls and conditional control flow')
    assert dispatch.PERIODS['development'][1]==dispatch.PERIODS['sealed'][0]
    assert dispatch.PERIODS['sealed'][1]=='2025-11-24'
    assert len(dispatch.required_months('development'))==37 and len(dispatch.required_months('sealed'))==13
    assert dispatch.required_months('development')[0]=='2021-11' and dispatch.required_months('development')[-1]=='2024-11'
    checks.append('Disjoint fixed three-year development/one-year sealed date windows; boundary UTC months explicitly included for five-session warmup')
    with tempfile.TemporaryDirectory() as temp:
        temp=Path(temp);go=temp/'go.json'
        go.write_text(json.dumps(dict(authorized=False,mode='development')))
        rejected(lambda:dispatch.authorize_period('development',go),'CLOSED')
        go.write_text(json.dumps(dict(authorized=True,mode='sealed')))
        rejected(lambda:dispatch.authorize_period('development',go),'CLOSED')
        checks.append('Absent authorization or wrong role rejects before market data, source dispatch, attempt marker or labels')
        rejected(lambda:dispatch.verify_final_published_model({}),'requirepublished')
        checks.append('Sealed labels reject missing published final-model receipt')
        model=temp/'models-frozen.json';model.write_text('{"synthetic_frozen_model":true}\n')
        publication=temp/'publication.json'
        receipt=dict(published=True,publication_commit='synthetic-test-commit',published_before_final_labels=True,models_frozen_sha256=sha(model),model_bundle=dict(path=str(model),sha256=sha(model)))
        def binding(obj):
            publication.write_text(json.dumps(obj));return dict(published_model_receipt=dict(path=str(publication),sha256=sha(publication),required_bundle_sha256=sha(model)))
        rejected(lambda:dispatch.verify_final_published_model(binding(dict(receipt,published=False))),'publicationproof')
        rejected(lambda:dispatch.verify_final_published_model(binding(dict(receipt,published_before_final_labels=False))),'precedefinal')
        checks.append('Unpublished or publication-after-final-labels model proof cannot open sealed labels')
        wrong=copy.deepcopy(receipt);wrong['model_bundle']['sha256']='0'*64
        rejected(lambda:dispatch.verify_final_published_model(binding(wrong)),'missingorchanged')
        go_model=binding(receipt);assert dispatch.verify_final_published_model(go_model)==receipt
        model.write_text('changed weights\n')
        rejected(lambda:dispatch.verify_final_published_model(go_model),'missingorchanged')
        checks.append('Only exact published bundle SHA passes; subsequent model-byte mutation is rejected')
        original_here=dispatch.HERE;dispatch.HERE=temp
        try:
            (temp/'Public').mkdir();(temp/'Private').mkdir();(temp/'Source').mkdir()
            (temp/'Public/download-manifest.json').write_text('[]')
            rejected(lambda:dispatch.verify_months('development'),'Missingcompletedrolepricemonth:2021-11')
            assert not list((temp/'Private').glob('*-label-attempt.json'))
            checks.append('Missing first required completed price month blocks the whole run with no partial-year labels or attempt marker')
            freeze=temp/'freeze.json';freeze.write_text('{}')
            dispatch.reserve_attempt('development',go,freeze)
            rejected(lambda:dispatch.reserve_attempt('development',go,freeze),'nohiddenretry')
            checks.append('Exclusive durable role attempt marker rejects a second attempt and preserves the first receipt')
            fixture=temp/'fixture-proof.json';fixture.write_text('{"passed":true}')
            source=temp/'Source/dispatcher.py';source.write_text('immutable synthetic dispatcher\n')
            proof=dict(sources_sha256={'dispatcher.py':sha(source)},fixtures_sha256=sha(fixture))
            dispatch.known.verify_frozen_sources(proof,temp/'Source',fixture)
            source.write_text('tampered source\n')
            rejected(lambda:dispatch.known.verify_frozen_sources(proof,temp/'Source',fixture),'Sourcehashmismatch')
            source.write_text('immutable synthetic dispatcher\n');fixture.write_text('{"passed":false}')
            rejected(lambda:dispatch.known.verify_frozen_sources(proof,temp/'Source',fixture),'fixtureproofhashmismatch')
            checks.append('New dispatcher Source and fixture hash verification rejects tampered code or proof before any labels')
            kernel=temp/'Source/second_kernel.py';kernel.write_text('synthetic fixture only\n')
            freeze.write_text(json.dumps(dict(sources_sha256={'synthetic.py':'a'*64})))
            go.write_text(json.dumps(dict(source_freeze_path=str(freeze),protocol_files=[])))
            cases=[dict(case_key='fixture-filled',day='2022-01-03',signal_ns=1,contract='ESH2',side=1)]
            csvpath=temp/'Private/development-candidates.csv';csvpath.write_text('case_key,day\nfixture-filled,2022-01-03\n')
            events=[dict(cases[0],successful_case_key='fixture-filled',label_status='ok',pending_terminal_ns=5,economic_path_resolved=True),dict(case_key='fixture-cancelled',day='2022-01-03',signal_ns=2,contract='ESH2',side=1,successful_case_key='',label_status='excluded_delayed_entry_liquidation_proxy_beyond_stop',entry_cancel_ns=4,pending_terminal_ns=4,economic_path_resolved=True)]
            envelope=dispatch.role_release('development',cases,dict(root_go_sha256=sha(go),candidates_csv_sha256=sha(csvpath)),go,events)
            assert envelope['row_count']==1 and envelope['intent_row_count']==2 and envelope['unresolved_intent_count']==0
            assert envelope['csv_sha256']==sha(csvpath) and envelope['intent_csv_sha256']==sha(temp/'Private/development-intents.csv')
            assert envelope['period_start_inclusive']=='2021-11-24' and envelope['independent_native_audit_sha256']==dispatch.KNOWN_AUDIT_SHA
            checks.append('Adjacent release binds filled CSV and complete cancelled/filled intent stream, counts, fixed dates, protocols and audit before consumer parsing')
        finally:dispatch.HERE=original_here
    seen=[];args=[{'case_key':'transparent','signal_ns':1,'contract':'ESZ1','side':1,'day':'2021-11-24'},[],[],{}]
    result=dict(label_status='excluded_no_present_entry_second',entry_decision_ns=1)
    def delegate(*received):
        assert all(a is b for a,b in zip(received,args));return result
    observed=dispatch.capture_intents(delegate,seen)
    assert observed(*args) is result
    args[0]['future_mutation']=True
    assert 'future_mutation' not in seen[0] and seen[0]['pending_terminal_ns'] is None and seen[0]['economic_path_resolved'] is False
    checks.append('Intent observer passes identical argument objects and returns identical frozen result; copies metadata and never invents unknown terminal time')
    day='2026-10-01';clock=Calendar().get(day);signal=clock['session_open_ns']+61*60*NS
    candidate=dict(case_key='synthetic-cancel',day=day,contract='ESZ6',side=1,signal_ns=signal,stop_price=100.,planned_risk_usd=292.18)
    rows=[row(day,signal+2*NS,100.25,101.,100.,100.5)];previews=[preview()];events=[]
    expected=dispatch.known.delayed_shadow(candidate,rows,previews,clock)
    got=dispatch.capture_intents(dispatch.known.delayed_shadow,events)(candidate,rows,previews,clock)
    assert got==expected and events[0]['entry_cancel_ns']==signal+2*NS and events[0]['successful_case_key']==''
    checks.append('Actual frozen liquidation-proxy cancellation retained as an unfilled blocking intent without changing native guard or adverse entry spread')
    candidate=dict(candidate,case_key='synthetic-filled',stop_price=95.)
    rows=[row(day,signal+2*NS,100.,106.,94.,101.),row(day,signal+4*NS,90.,91.,89.,90.),row(day,signal+7*NS,92.,93.,91.,92.)]
    events=[];expected=dispatch.known.delayed_shadow(candidate,rows,[preview()]*3,clock)
    got=dispatch.capture_intents(dispatch.known.delayed_shadow,events)(candidate,rows,[preview()]*3,clock)
    assert got==expected and events[0]['successful_case_key']==candidate['case_key'] and events[0]['pending_terminal_ns']==got['exit_ns']
    checks.append('Actual frozen stop-priority/latency filled result and all net labels unchanged through intent capture')
    for role in dispatch.PERIODS:
        assert not (HERE/f'Private/{role}-candidates.csv').exists()
        assert not (HERE/f'Private/{role}-label-attempt.json').exists()
    dispatch.verify_known_immutable()
    checks.append('Synthetic fixtures leave all real older/sealed outputs and attempt markers absent; known source and existing outputs immutable')
    report=dict(status='PASS_SYNTHETIC_PERIOD_GUARDS_NO_OLDER_LABELS',utc=utcnow(),checks_passed=len(checks),checks=checks,no_older_signals_or_labels_or_models=True,known_source_unchanged=True)
    save(HERE/'Public/period-fixtures.json',report);print(json.dumps(report,indent=2))


if __name__=='__main__':main()
