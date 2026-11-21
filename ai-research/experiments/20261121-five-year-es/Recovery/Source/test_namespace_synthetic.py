"""Full generated-function I/O tests using ONLY synthetic market functions."""
from pathlib import Path
from datetime import date,timedelta
import copy,json,tempfile,hashlib
import namespace_prototype as proposal
from price_extract_support import ct_ns,NS,save,utcnow,sha


class ToyBook:
    def step(self,row,clock):
        return dict(signal_ns=row['ts_event_ns']+NS,consensus_side=row['event'],ambiguous_first_return=row.get('ambiguous',False),current_past_5m_grid_complete=True,state_mask_before=1,state_mask_after=1,possible_event_patterns=((1,),(-1,)) if row.get('ambiguous') else ((1,),),paths_considered=2)


def inputs(root,role):
    root.mkdir()
    for relative in proposal.OLD_TO_NEW:
        p=root/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('IMMUTABLE_KNOWN_PREIMAGE:'+relative+'\n')
    for relative in ['Source/runner.py','Source/second_kernel.py','Public/source-freeze.json','Private/root-go.json','Private/Months/toy/manifest.json','Private/sealed-candidates.csv','Private/development-candidates.csv']:
        p=root/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}\n')
    day={'known':'2025-11-24','development':'2021-11-24','sealed':'2024-11-24'}[role]
    days=[str(date.fromisoformat(day)-timedelta(days=i)) for i in range(5,0,-1)]+[day]
    schedule=[]
    for d in days:
        op=ct_ns(d,8,30);schedule.append(dict(day=d,raw_symbol='ESTOY',session_open_ns=op,session_close_ns=op+1200*NS,flatten_ns=op+1000*NS,calendar_status='SYNTHETIC_ONLY',warmup_complete=True,warmup_previous_five_same_contract_sessions=[dict(day=w,raw_symbol='ESTOY',complete_5m_grid=True) for w in days[:-1]]))
    def read_day(months,symbol,d):
        op=ct_ns(d,8,30)
        if d!=day:return [dict(ts_event_ns=op,close=100.,event=0,vendor_quality_flag='SYNTHETIC_ONLY')]
        return [dict(ts_event_ns=op+s*NS,close=100.,event=e,ambiguous=a,vendor_quality_flag='SYNTHETIC_ONLY') for s,e,a in [(60,1,False),(180,1,False),(240,0,True),(1001,1,False)]]
    return day,schedule,read_day


def toy_features(side,close,preview,clock):
    return dict(planned_risk_usd=100.,stop_price=99.,feature_stop_risk_usd=100.,feature_target_path_R=1.,feature_signed_completed_ema_slope_atr=0.,feature_completed_relative_volume20=1.,feature_chicago_session_minute=1.),None


def toy_shadow(candidate,rows,previews,clock):
    signal=candidate['signal_ns']
    if signal>clock['session_open_ns']+100*NS:return dict(label_status='excluded_delayed_entry_liquidation_proxy_beyond_stop',entry_cancel_ns=signal+2*NS)
    return dict(label_status='ok',entry_ns=signal+2*NS,exit_ns=signal+50*NS,entry_price=100.25,exit_price=100.75,normal_net_usd=20.32,stress_net_usd=-4.68,stress_net_R=-.0468,exit_reason='SYNTHETIC_ONLY',entry_gap_extra_seconds=0.,exit_gap_extra_seconds=0.)


def run_fixture(base,role,broken=False,missing_csv=False):
    input_root=base/'input';output_root=base/'output';day,schedule,reader=inputs(input_root,role)
    guard=proposal.Guard(input_root,output_root,role)
    environment=dict(vars(proposal.frozen.known))
    def authorize(path):
        guard.save(output_root/f'Private/{role}-attempt.json',dict(synthetic_only=True))
        return dict(source_freeze_path=str(input_root/'Public/source-freeze.json'))
    def complete(cases,binding):
        if missing_csv:(output_root/f'Private/{role}-candidates.csv').unlink()
        return guard.package(cases,binding)
    environment.update(HERE=output_root,INPUT_ROOT=input_root,KNOWN_MONTHS=['toy'],__file__=str(input_root/'Source/runner.py'),authorize=authorize,known_sources=lambda:({'toy':{}},schedule),read_day=reader,SecondBook=ToyBook,decision_features=toy_features,delayed_shadow=guard.capture(toy_shadow),save=guard.save,sha=guard.sha,acceptance=complete)
    code=proposal.corrected_engine(role)
    if broken:code=proposal.frozen.derived_source(role) if role!='known' else code.replace(f'Private/{role}-price-roll-freeze.json','Private/second-known-price-roll-freeze.json')
    try:
        with guard:
            exec(compile(code,'SYNTHETIC_'+role,'exec'),environment)
            environment['run_period'](input_root/'Private/root-go.json')
    except proposal.NamespaceViolation:
        assert broken;return guard
    except FileNotFoundError:
        assert missing_csv
        assert len((output_root/f'Private/{role}-intents-plan-journal.jsonl').read_text().splitlines())==2
        assert len((output_root/f'Private/{role}-intents-result-journal.jsonl').read_text().splitlines())==2
        assert len((output_root/f'Private/{role}-intents.jsonl').read_text().splitlines())==2
        return guard
    assert not broken and not missing_csv
    for relative in [v.format(role=role) for v in proposal.OLD_TO_NEW.values()]+[f'Private/{role}-release.json',f'Private/{role}-intents.jsonl',f'Private/{role}-intents.csv',f'Public/{role}-labels-completion.json']:
        assert (output_root/relative).is_file(),relative
    release=json.loads((output_root/f'Private/{role}-release.json').read_text())
    assert release['row_count']==1 and release['intent_row_count']==2
    journal=[json.loads(x) for x in (output_root/f'Private/{role}-intents-plan-journal.jsonl').read_text().splitlines()]
    proof=json.loads((output_root/f'Private/{role}-feature-before-label-proof.json').read_text())
    assert len(proof)==1 and proof[0]['feature_candidates']==len(journal)==2
    assert hashlib.sha256(json.dumps(journal,sort_keys=True,allow_nan=False).encode()).hexdigest()==proof[0]['features_before_labels_sha256']
    assert release['csv_sha256']==proposal.digest(output_root/f'Private/{role}-candidates.csv')
    assert release['intent_jsonl_sha256']==proposal.digest(output_root/f'Private/{role}-intents.jsonl')
    assert not any(name in guard.writes for name in proposal.OLD_TO_NEW)
    return guard


def main():
    checks=[]
    with tempfile.TemporaryDirectory(prefix='codex_namespace_fixture_') as folder:
        base=Path(folder)
        for role in ['known','development','sealed']:
            for label,broken,missing in [('success',False,False),('old_mapping_negative',True,False),('packaging_failure',False,True)]:
                case=base/(role+'_'+label);case.mkdir();guard=run_fixture(case,role,broken,missing)
                checks.append(dict(role=role,test=label,all_input_known_and_other_role_preimages_unchanged=True,writes_only_fresh_role_allowlist=True,actual_write_operations=len(guard.writes),synthetic_only=True))
        case=base/'guard_negatives';case.mkdir();input_root=case/'input';output_root=case/'output';inputs(input_root,'development');guard=proposal.Guard(input_root,output_root,'development')
        with guard:
            for forbidden in [input_root/'Private/second-candidates-known.csv',output_root/'Private/sealed-candidates.csv',case/'outside.txt']:
                try:forbidden.write_text('MUST_BE_DENIED')
                except proposal.NamespaceViolation:pass
                else:raise AssertionError('Runtime outside/role-collision write permitted')
            try:guard.sha(output_root/'unregistered.json')
            except proposal.NamespaceViolation:pass
            else:raise AssertionError('Unregistered output hash permitted')
        checks.append(dict(test='outside_input_other_role_write_and_unregistered_hash_rejected',synthetic_only=True))
        for occupied in [case/'empty_existing',case/'nonempty_existing']:
            occupied.mkdir()
            if occupied.name.startswith('nonempty'):(occupied/'foreign').write_text('KEEP')
            try:proposal.Guard(input_root,occupied,'development')
            except proposal.NamespaceViolation:pass
            else:raise AssertionError('Existing output namespace accepted')
        checks.append(dict(test='both_existing_empty_and_nonempty_output_roots_rejected',synthetic_only=True))
    report=dict(status='PASS_FULL_GENERATED_FUNCTION_SYNTHETIC_IO',utc=utcnow(),checks_passed=len(checks),checks=checks,sources_sha256={p.name:sha(p) for p in [Path(__file__),Path(proposal.__file__)]},all_three_roles_exercised=True,old_broken_mapping_negative_control_caught_all_roles=True,intents_durable_before_packaging_failure=True,per_day_complete_plan_hash_verified=True,no_real_signals_labels_recovery_or_fit=True,production_recovery_guard='CLOSED_PENDING_PUBLISHED_CRITERIA_AND_ROOT_GO')
    target=proposal.RECOVERY/'Public/namespace-synthetic-acceptance.json';assert not target.exists();save(target,report);print(json.dumps(report,indent=2))


if __name__=='__main__':main()
