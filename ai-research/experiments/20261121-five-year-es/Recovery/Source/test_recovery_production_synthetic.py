"""Production run() end-to-end on synthetic full-count opportunity streams.

All market functions and authorization are explicit synthetic substitutes.
No real strategy reconstruction, outcome recovery or model fitting occurs.
"""
from pathlib import Path
from datetime import date,timedelta
from contextlib import ExitStack
from unittest.mock import patch
import json,tempfile,hashlib,os
import recover_exact as production
import namespace_prototype as prototype
from test_namespace_synthetic import ToyBook,toy_features
from price_extract_support import ct_ns,NS,sha,save,utcnow


def make_fixture(base,role):
    input_root=base/'input';input_root.mkdir();ml=base/'ml';ml.mkdir();(ml/'immutable.txt').write_text('ML_INPUT_PREIMAGE\n')
    for name in list(prototype.OLD_TO_NEW)+['Source/second_run.py','Source/second_kernel.py','Public/period-source-freeze.json','Public/second-source-freeze-v2.json','Public/source-freeze.json','Private/root-go.json','Private/Months/toy/manifest.json']:
        p=input_root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}\n')
    start=date.fromisoformat('2021-11-24' if role=='development' else '2025-11-24');n=775 if role=='development' else 174
    days=[str(start+timedelta(days=i)) for i in range(-5,n)];active=days[5:];schedule=[];events={};all_signals=[]
    for i,d in enumerate(days):
        op=ct_ns(d,8,30);warm=[dict(day=w,raw_symbol='ESTOY',complete_5m_grid=True) for w in days[max(0,i-5):i]]
        schedule.append(dict(day=d,raw_symbol='ESTOY',session_open_ns=op,session_close_ns=op+1200*NS,flatten_ns=op+1000*NS,calendar_status='SYNTHETIC_ONLY',warmup_previous_five_same_contract_sessions=warm,warmup_complete=len(warm)==5))
        if d in active:
            ix=active.index(d);count=(2 if ix<370 else 1) if role=='development' else 2
            events[d]=[op+(60+100*j)*NS for j in range(count)];all_signals.extend(t+NS for t in events[d])
    cancelled=set(all_signals[-2:]) if role=='development' else set()
    def read_day(months,symbol,d):
        return [dict(ts_event_ns=t,close=100.,event=1,vendor_quality_flag='SYNTHETIC_ONLY') for t in events.get(d,[])]
    def shadow(candidate,rows,previews,clock):
        signal=candidate['signal_ns']
        if signal in cancelled:return dict(label_status='excluded_delayed_entry_liquidation_proxy_beyond_stop',entry_decision_ns=signal,entry_cancel_ns=signal+2*NS)
        return dict(label_status='ok',entry_ns=signal+2*NS,exit_ns=signal+50*NS,entry_price=100.25,exit_price=100.75,normal_net_usd=20.32,stress_net_usd=-4.68,stress_net_R=-.0468,exit_reason='SYNTHETIC_ONLY',entry_gap_extra_seconds=0.,exit_gap_extra_seconds=0.)
    return input_root,ml,schedule,read_day,shadow


def reference(base,role,inputs):
    input_root,ml,schedule,reader,shadow=inputs;out=base/'reference';guard=prototype.Guard(input_root,out,role)
    environment=dict(vars(prototype.frozen.known));environment.update(HERE=out,INPUT_ROOT=input_root,KNOWN_MONTHS=['toy'],__file__=str(input_root/'Source/second_run.py'),authorize=lambda p:dict(source_freeze_path=str(input_root/'Public/source-freeze.json')),known_sources=lambda:({'toy':{}},schedule),read_day=reader,SecondBook=ToyBook,decision_features=toy_features,delayed_shadow=guard.capture(shadow),save=guard.save,sha=guard.sha,acceptance=guard.package)
    with guard:
        exec(compile(prototype.corrected_engine(role),'SYNTHETIC_REFERENCE','exec'),environment);environment['run_period'](input_root/'Private/root-go.json')
    return out


def actual_production_entry(base,role,inputs,expected_output,corrupt=False):
    input_root,ml,schedule,reader,shadow=inputs;incident=base/'incident';incident.mkdir();files={}
    inverse={v.format(role=role):k for k,v in prototype.OLD_TO_NEW.items()}
    for relative,old in inverse.items():
        src=expected_output/relative;dst=incident/old;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(src.read_bytes());files[old]=dict(sha256=sha(dst))
    if corrupt:files['Private/second-candidates-known.csv']['sha256']='0'*64
    bindings={name:dict(path=str(input_root/'Public/source-freeze.json'),sha256=sha(input_root/'Public/source-freeze.json')) for name in ['source_freeze','OS_profile','protocol_main','protocol_addendum','protocol_native']}
    out=base/'production';go=dict(output_root=str(out),bindings=bindings)
    algorithm=dict(sources_sha256={'second_kernel.py':sha(input_root/'Source/second_kernel.py')})
    expected_known={name:sha(expected_output/f'Private/{role}-{suffix}') for name,suffix in [('candidates_jsonl','candidates.jsonl'),('candidates_csv','candidates.csv'),('schedule_json','price-roll-freeze.json')]}
    with ExitStack() as stack:
        for name,value in [('DATA',input_root),('ML',ml),('INCIDENT',incident),('KNOWN_EXPECTED',expected_known)]:stack.enter_context(patch.object(production,name,value))
        stack.enter_context(patch.object(production,'verify_go',lambda mode,p:(go,dict(files=files),algorithm)))
        stack.enter_context(patch.object(production,'verify_OS_enforcement',lambda:dict(OS_denied=True,synthetic_stub=True)))
        stack.enter_context(patch.object(prototype.frozen,'period_sources',lambda role:({'toy':{}},schedule)))
        for name,value in [('known_sources',lambda:({'toy':{}},schedule)),('read_day',reader),('SecondBook',ToyBook),('decision_features',toy_features),('delayed_shadow',shadow)]:stack.enter_context(patch.object(prototype.frozen.known,name,value))
        if corrupt:
            try:production.run(role+'-recovery',input_root/'Private/root-go.json')
            except ValueError as error:assert 'not byte-identical' in str(error)
            else:raise AssertionError('Changed scientific byte criteria accepted')
            assert not (out/'Public/recovery-acceptance.json').exists()
            assert (out/f'Public/{role}-failed-attempt.json').exists()
            assert len((out/f'Private/{role}-intents-plan-journal.jsonl').read_text().splitlines())==1145
            return dict(role=role,changed_CSV_criteria_STOP=True,intents_durable=True)
        production.run(role+'-recovery',input_root/'Private/root-go.json')
    acceptance=json.loads((out/'Public/recovery-acceptance.json').read_text())
    assert acceptance['status']=='EXACT_ORIGINAL_BYTE_AND_PLAN_MATCH'
    assert all(acceptance[k] is True for k in ['no_selection_or_parameter_change','no_sealed_access','no_model_fit'])
    assert acceptance['original_timestamps_fabricated'] is False
    assert acceptance['unavailable_original_ephemeral_metadata']==['Public/second-execution-start.json','Public/second-preflight-progress.json']
    assert acceptance['cancellation_clock_evidence']=='new_deterministic_recovery_evidence_not_original_capture'
    assert acceptance['immutable_original_Data_root_postcheck_passed'] and acceptance['immutable_original_ML_root_postcheck_passed']
    assert acceptance['filled_cases']==(1143 if role=='development' else 348)
    if role=='development':assert acceptance['decision_plans']==1145 and acceptance['plan_days']==775 and acceptance['resolved_entry_cancellations']==2
    for key,entry in acceptance['artifacts'].items():assert sha(out/entry['path_relative_to_attempt'])==entry['sha256']
    for name in ['candidates.jsonl','candidates.csv','exclusions.json','ambiguities.json','feature-before-label-proof.json']:
        assert (out/f'Private/{role}-{name}').read_bytes()==(expected_output/f'Private/{role}-{name}').read_bytes()
    return dict(role=role,production_run_end_to_end_synthetic=True,filled_cases=acceptance['filled_cases'],decision_plans=acceptance['decision_plans'],input_and_ML_roots_unchanged=True,byte_and_plan_checks_pass=True,canonical_release_and_all_artifact_hashes_valid=True)


def main():
    checks=[]
    with tempfile.TemporaryDirectory(prefix='codex_fullcount_recovery_fixture_') as temp:
        base=Path(temp)
        for role in ['known','development']:
            case=base/role;case.mkdir();inputs=make_fixture(case,role);expected=reference(case,role,inputs);checks.append(actual_production_entry(case,role,inputs,expected))
        case=base/'corrupt_development';case.mkdir();inputs=make_fixture(case,'development');expected=reference(case,'development',inputs);checks.append(actual_production_entry(case,'development',inputs,expected,corrupt=True))
        closed=base/'closed-go.json';closed.write_text(json.dumps(dict(authorized=False,mode='known-recovery')))
        try:production.verify_go('known-recovery',closed)
        except ValueError as error:assert 'GO required' in str(error)
        else:raise AssertionError('Missing GO allowed')
        checks.append(dict(test='unauthorized_actual_CLI_control_stops_before_market_read'))
        with patch.object(production.os,'open',side_effect=PermissionError(1,'SYNTHETIC_OS_DENIAL')):assert production.verify_OS_enforcement()['OS_denied']
        with patch.object(production.os,'open',return_value=999),patch.object(production.os,'close'):
            try:production.verify_OS_enforcement()
            except ValueError as error:assert 'NOT applied' in str(error)
            else:raise AssertionError('OS assertion alone accepted')
        checks.append(dict(test='real_denial_required_not_GO_boolean_alone',actual_OS_syscalls_separately_proven=True))
    report=dict(status='PASS_PRODUCTION_ENTRY_SYNTHETIC_FULL_COUNTS',utc=utcnow(),checks_passed=len(checks),checks=checks,sources_sha256={p.name:sha(p) for p in [Path(__file__),Path(production.__file__),Path(prototype.__file__)]},authorization_and_market_functions_are_explicit_synthetic_stubs=True,actual_production_run_function_exercised=True,no_real_market_rows_or_labels_read_or_recovered=True,no_models_fit=True,production_recovery_guard='CLOSED_UNTIL_PUBLISHED_SOURCE_AND_ROOT_GO')
    target=prototype.RECOVERY/'Public/production-synthetic-acceptance-v4.json';assert not target.exists();save(target,report);print(json.dumps(report,indent=2))


if __name__=='__main__':main()
