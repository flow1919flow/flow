"""Real filesystem publication tests on temporary synthetic original roots ONLY."""
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
import copy,json,tempfile
import apply_canonical as apply
import plan_canonical as planner


def put(path,body):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)


def snapshot(root):return {str(p.relative_to(root)):apply.sha(p) for p in root.rglob('*') if p.is_file()}


def fixture(base):
    recovery=base/'Recovery';data=base/'Data';incident=data/'Private/Incidents/preserved';incident.mkdir(parents=True)
    for d in ['Attempts','ApplyRuns','PromotionProposal','OriginalPublished/Public']:(recovery/d).mkdir(parents=True,exist_ok=True)
    known=recovery/'Attempts/known-1';dev=recovery/'Attempts/development-1'
    mappings={'known':apply.KNOWN_MAP,'development':apply.DEV_MAP};records={}
    for role,attempt in [('known',known),('development',dev)]:
        artifacts={}
        for key,destination in mappings[role].items():
            suffix=Path(destination).name
            relative='Private/'+role+'-'+key+'.opaque';path=attempt/relative
            put(path,('SYNTHETIC_RECOVERED_'+role+'_'+key+'\n').encode());artifacts[key]=dict(path_relative_to_attempt=relative,sha256=apply.sha(path))
        records[role]=dict(role=role,status='EXACT_ORIGINAL_BYTE_AND_PLAN_MATCH',filled_cases=348 if role=='known' else 1143,decision_plans=348 if role=='known' else 1145,plan_days=242 if role=='known' else 775,resolved_entry_cancellations=0 if role=='known' else 2,immutable_original_Data_root_postcheck_passed=True,immutable_original_ML_root_postcheck_passed=True,no_model_fit=True,no_sealed_access=True,no_selection_or_parameter_change=True,artifacts=artifacts)
        put(attempt/'Public/recovery-acceptance.json',(json.dumps(records[role])+'\n').encode())
    old_names=list(apply.KNOWN_MAP.values())+[apply.SUMMARY]+apply.POINTERS
    originals={}
    for name in old_names+['Private/development-label-attempt.json','development-one-attempt.log']:
        body=b'SYNTHETIC_WRONG_ROLE_PREIMAGE:'+name.encode()+b'\n'
        if name=='Private/second-known-price-roll-freeze.json':body=(dev/records['development']['artifacts']['schedule_json']['path_relative_to_attempt']).read_bytes()
        put(data/name,body);put(incident/name,body);originals[name]=dict(sha256=apply.sha(data/name),bytes=len(body))
    put(incident/'incident-files.json',(json.dumps(dict(files=originals))+'\n').encode())
    put(data/'Source/immutable.py',b'SOURCE_MUST_NEVER_CHANGE\n');put(data/'Raw/immutable.dbn',b'RAW_MUST_NEVER_CHANGE\n')
    genuine=recovery/'OriginalPublished/Public/second-known-summary.json';put(genuine,b'SYNTHETIC_AUTHENTIC_PUBLISHED_BYTES\n')
    core={key:records['known']['artifacts'][key]['sha256'] for key in planner.CORE}
    return recovery,data,incident,known,dev,core,apply.sha(genuine)


def patched(layout):
    recovery,data,incident,known,dev,core,summary=layout;stack=ExitStack()
    for module in [apply,planner]:
        for name,value in [('RECOVERY',recovery),('DATA',data),('INCIDENT',incident)]:stack.enter_context(patch.object(module,name,value))
    stack.enter_context(patch.object(planner,'CORE',core));stack.enter_context(patch.object(planner,'SUMMARY_SHA',summary))
    return stack


def scenario(base,kind):
    layout=fixture(base);recovery,data,incident,known,dev,core,summary=layout
    with patched(layout):
        planpath=recovery/'PromotionProposal/plan.json';planner.plan(known,dev,planpath);plan=json.loads(planpath.read_text())
        go=dict(known_attempt=str(known),development_attempt=str(dev),incident_manifest_sha256=apply.sha(incident/'incident-files.json'),output_root=str(recovery/'ApplyRuns/canonical-1'),_receipt_sha256='a'*64)
        protected={p:apply.sha(p) for p in [data/'Source/immutable.py',data/'Raw/immutable.dbn',data/'Private/development-label-attempt.json']}
        incident_before=snapshot(incident)
        if kind=='changed_preimage':put(data/'Private/second-candidates-known.csv',b'UNEXPECTED_EDIT')
        elif kind=='existing_new_target':put(data/'Private/development-candidates.csv',b'UNEXPECTED_EXISTING_NEW_TARGET')
        elif kind=='changed_source':put(dev/records_path(dev,'candidates_csv'),b'CHANGED_ACCEPTED_SOURCE')
        elif kind in ['Source_destination','Raw_destination','Incident_destination']:
            forbidden={'Source_destination':data/'Source/immutable.py','Raw_destination':data/'Raw/immutable.dbn','Incident_destination':incident/'incident-files.json'}
            plan['operations'][0]['destination']=str(forbidden[kind])
        elif kind=='staging_file_exists':put(data/'Private/second-candidates-known.jsonl.canonical-promotion.tmp',b'KEEP_UNEXPECTED_STAGING')
        before=snapshot(data)
        if kind in ['changed_preimage','existing_new_target','changed_source','Source_destination','Raw_destination','Incident_destination','staging_file_exists']:
            try:apply.apply_plan(plan,go)
            except (ValueError,AssertionError):pass
            else:raise AssertionError('Preflight corruption accepted: '+kind)
            assert snapshot(data)==before and not Path(go['output_root']).exists()
            return dict(test=kind,blocked_before_any_canonical_write=True)
        if kind=='crash_after_first_commit':
            def crash(index):
                if index==0:raise RuntimeError('SYNTHETIC_CRASH_AFTER_FIRST_COMMIT')
            try:apply.apply_plan(plan,go,after_commit=crash)
            except RuntimeError:pass
            else:raise AssertionError('Crash injection missed')
            output=Path(go['output_root']);journal=[json.loads(x) for x in (output/'intent-journal.jsonl').read_text().splitlines()]
            assert len(journal)==2 and journal[0]['stage']=='INTENT_DURABLE_BEFORE_CANONICAL_WRITE' and journal[1]['stage']=='COMMITTED_AND_POSTHASHED'
            assert (output/'failed-apply.json').exists() and not (output/'posthash-proof.json').exists()
            assert snapshot(incident)==incident_before
            assert all(apply.sha(p)==digest for p,digest in protected.items())
            try:apply.apply_plan(plan,go)
            except ValueError:pass
            else:raise AssertionError('Partial apply silently retried')
            return dict(test=kind,partial_state_durable_no_model_unlock=True,silent_retry_blocked=True)
        if kind=='atomic_replace_failure':
            with patch.object(apply.os,'replace',side_effect=OSError('SYNTHETIC_REPLACE_FAILURE')):
                try:apply.apply_plan(plan,go)
                except OSError:pass
                else:raise AssertionError('Replace failure missed')
            assert apply.sha(data/'Private/second-candidates-known.jsonl')==before['Private/second-candidates-known.jsonl']
            assert (data/'Private/second-candidates-known.jsonl.canonical-promotion.tmp').exists()
            output=Path(go['output_root']);journal=[json.loads(x) for x in (output/'intent-journal.jsonl').read_text().splitlines()]
            assert len(journal)==1 and journal[0]['stage']=='INTENT_DURABLE_BEFORE_CANONICAL_WRITE'
            assert (output/'failed-apply.json').exists() and not (output/'posthash-proof.json').exists()
            return dict(test=kind,original_target_atomic_preimage_retained=True,intent_durable=True)
        result=apply.apply_plan(plan,go)
        assert result['status']=='PASS_CANONICAL_BYTE_PUBLICATION' and len(result['published_files'])==20
        assert (data/'Public/second-known-summary.json').read_bytes()==(recovery/'OriginalPublished/Public/second-known-summary.json').read_bytes()
        assert apply.sha(data/'Private/development-price-roll-freeze.json')==apply.sha(incident/'Private/second-known-price-roll-freeze.json')
        for name in apply.POINTERS:
            pointer=json.loads((data/name).read_text());assert pointer['this_is_a_restoration_pointer_not_original_status'] and pointer['original_timestamp_not_fabricated'] and 'utc' not in pointer
        assert not (data/'Public/development-labels-completion.json').exists()
        assert snapshot(incident)==incident_before and all(apply.sha(p)==digest for p,digest in protected.items())
        journal=[json.loads(x) for x in (Path(go['output_root'])/'intent-journal.jsonl').read_text().splitlines()]
        assert len(journal)==40
        for a,b in zip(journal[::2],journal[1::2]):assert a['stage']=='INTENT_DURABLE_BEFORE_CANONICAL_WRITE' and b['stage']=='COMMITTED_AND_POSTHASHED' and a['destination']==b['destination'] and a['after_sha256']==b['sha256']
        return dict(test='successful_full20file_publication',all_exact_bytes_and_pointer_scope_correct=True,all_writes_intent_journaled_before_commit=True,source_raw_incident_failed_attempt_unchanged=True,no_legacy_completion_fabricated=True)


def records_path(attempt,key):return json.loads((attempt/'Public/recovery-acceptance.json').read_text())['artifacts'][key]['path_relative_to_attempt']


def main():
    checks=[]
    with tempfile.TemporaryDirectory(prefix='codex_apply_fixture_') as temp:
        root=Path(temp)
        for kind in ['success','changed_preimage','existing_new_target','changed_source','Source_destination','Raw_destination','Incident_destination','staging_file_exists','crash_after_first_commit','atomic_replace_failure']:
            base=root/kind;base.mkdir();checks.append(scenario(base,kind))
        closed=root/'closed-go.json';closed.write_text(json.dumps(dict(authorized=False)))
        try:apply.main(closed)
        except ValueError as error:assert 'Root GO required' in str(error)
        else:raise AssertionError('Unauthorised actual apply allowed')
        checks.append(dict(test='actual_apply_entry_requires_separate_explicit_Root_GO'))
        badfreeze=root/'bad-freeze.json';badfreeze.write_text(json.dumps(dict(sources_sha256={'apply_canonical.py':'0'*64})))
        badgo=root/'bad-source-go.json';badgo.write_text(json.dumps(dict(authorized=True,mode='canonical-recovery-publication',published_before_apply=True,publication_commit='a'*40,source_freeze_path=str(badfreeze),source_freeze_sha256=apply.sha(badfreeze))))
        try:apply.main(badgo)
        except ValueError as error:assert 'source changed' in str(error)
        else:raise AssertionError('Changed publication source accepted')
        checks.append(dict(test='actual_entry_source_SHA_guard_rejects_before_original_preflight'))
        guarded=root/'runtime-guard';guarded.mkdir();allowed=guarded/'allowed-journal.jsonl';forbidden=guarded/'Source-must-not-write.py';forbidden.write_text('KEEP')
        guard=apply.WriteGuard([allowed]);guard.active=True
        try:
            try:forbidden.write_text('MUST_BE_DENIED')
            except ValueError:pass
            else:raise AssertionError('Unlisted runtime write accepted')
            with allowed.open('w') as stream:stream.write('ALLOWED')
            try:allowed.unlink()
            except ValueError:pass
            else:raise AssertionError('Broad deletion permitted')
            try:forbidden.rename(allowed)
            except ValueError:pass
            else:raise AssertionError('Unlisted rename source permitted')
        finally:guard.active=False
        assert forbidden.read_text()=='KEEP' and allowed.read_text()=='ALLOWED'
        checks.append(dict(test='runtime_guard_denies_unlisted_write_delete_rename_and_allows_journal'))
    report=dict(status='PASS_SYNTHETIC_CANONICAL_APPLY_FILESYSTEM',checks_passed=len(checks),checks=checks,source_sha256={p.name:apply.sha(p) for p in [Path(__file__),Path(apply.__file__),Path(planner.__file__)]},all_original_roots_synthetic_temporary_only=True,no_actual_original_root_read_or_write=True,no_model_fit_or_unlock=True)
    target=planner.RECOVERY/'PromotionProposal/synthetic-acceptance-v3.json';assert not target.exists();target.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
