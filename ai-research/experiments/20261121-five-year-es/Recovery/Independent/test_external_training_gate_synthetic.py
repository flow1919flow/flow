"""Synthetic-only external integrity gate tests; never opens real role labels.

Fixture roots, known fingerprints and metadata are temporary synthetic values.
Any apparent fit launch is a mocked subprocess with synthetic model metadata.
"""
from pathlib import Path
from contextlib import contextmanager
from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import patch
from datetime import date,timedelta
import hashlib,importlib.util,json,tempfile
P=Path(__file__).with_name('external_training_gate.py');spec=importlib.util.spec_from_file_location('external_gate_sut',P);g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
ORIGINAL_RECOVERY=g.RECOVERY;ORIGINAL_DATA=g.DATA;ORIGINAL_LEARNING=g.LEARNING;RESULT=[]

def dump(p,o):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,allow_nan=False)+'\n')
def bind(p):return dict(path=str(p),sha256=g.sha(p))
def update_binding(go,key,path):o=g.read(go);o[key]=bind(path);dump(go,o)
def rejects(fn):
    try:fn()
    except (ValueError,FileNotFoundError):return
    raise AssertionError('Expected closed gate')
def check(name,fn):fn();RESULT.append(name)

@contextmanager
def fixture():
    real_training=ORIGINAL_LEARNING/'Source/train_fiveyear.py'
    with tempfile.TemporaryDirectory(prefix='external-gate-synthetic-')as temp:
        base=Path(temp);r=base/'Recovery';d=base/'Data';l=base/'Learning'
        with patch.multiple(g,RECOVERY=r,DATA=d,LEARNING=l,WORKSPACE=base):
            for folder in [r/'Public',r/'Private',r/'Source',r/'Independent',r/'OSProbe/output',d/'Public',d/'Source',d/'Private',l/'Public',l/'Private',l/'Source',l/'Audit']:folder.mkdir(parents=True,exist_ok=True)
            (d/'Audit').mkdir();(d/'Audit/independent.py').write_text('SYNTHETIC INDEPENDENT NATIVE AUDIT\n')
            (d/'Source/second_kernel.py').write_text('SYNTHETIC KERNEL\n');dump(d/'Public/second-fixtures.json',{'synthetic':True});dump(d/'Public/second-source-freeze-v2.json',dict(sources_sha256={'second_kernel.py':g.sha(d/'Source/second_kernel.py')},fixtures_sha256=g.sha(d/'Public/second-fixtures.json')))
            (d/'Private/second-candidates-known.jsonl').write_text('SYNTHETIC ORIGINAL KNOWN JSONL\n');(d/'Private/second-candidates-known.csv').write_text('SYNTHETIC ORIGINAL KNOWN CSV\n');dump(d/'Private/second-known-price-roll-freeze.json',{'synthetic_original_schedule':True})
            dump(d/'Private/Months/2025-11/manifest.json',{'synthetic_known_month':True});dump(d/'Public/second-native-acceptance.json',dict(accepted=True,sourcehashes=dict(month_manifest_sha256={'2025-11':g.sha(d/'Private/Months/2025-11/manifest.json')}),synthetic=True));dump(d/'Public/second-independent-audit.json',dict(acceptance_sha256=g.sha(d/'Public/second-native-acceptance.json'),audit_source_sha256=g.sha(d/'Audit/independent.py'),synthetic=True))
            known={name:g.sha(d/name)for name in g.KNOWN_ORIGINAL}
            incident=d/'Private/Incidents/development-dispatch-path-20261121';(incident/'Private').mkdir(parents=True)
            plans=[];proof=[]
            for i in range(775):
                day=(date(2021,11,24)+timedelta(days=i)).isoformat();group=[]
                for j in range(2 if i<370 else 1):
                    p=dict(case_key=f'synthetic-{i}-{j}',contract='SYNTHETIC_ES',day=day,signal_ns=(len(plans)+1)*10000,feature_context=float(j));plans.append(p);group.append(p)
                proof.append(dict(contract='SYNTHETIC_ES',day=day,feature_candidates=len(group),features_before_labels_sha256=hashlib.sha256(json.dumps(group,sort_keys=True,allow_nan=False).encode()).hexdigest()))
            assert len(plans)==1145
            dump(incident/'Private/second-known-feature-before-label-proof.json',proof)
            (incident/'Private/second-candidates-known.jsonl').write_text(''.join(json.dumps(dict(case_key=p['case_key'],synthetic_filled=True))+'\n'for p in plans[:1143]));(incident/'Private/second-candidates-known.csv').write_text('case_key\n'+'\n'.join(p['case_key']for p in plans[:1143])+'\n');dump(incident/'Private/second-known-exclusions.json',{'synthetic_exclusions':2});dump(incident/'Private/second-known-ambiguities.json',{'synthetic_ambiguities':2})
            expected={name:g.sha(incident/name)for name in g.INCIDENT_EXPECTED}
            attempt=r/'Attempts/development-synthetic';(attempt/'Private').mkdir(parents=True);(attempt/'Public').mkdir()
            artifacts={}
            def art(key,relative,data=None):
                p=attempt/relative
                if data is not None:p.write_bytes(data)
                artifacts[key]=dict(path_relative_to_attempt=relative,sha256=g.sha(p));return p
            for key,(old,new)in g.ROLE_RENAME.items():
                data=(incident/old).read_bytes();art(key,new,data);(d/new).write_bytes(data)
            plans_path=art('decision_plans_jsonl','Private/development-intents-plan-journal.jsonl',''.join(json.dumps(p)+'\n'for p in plans).encode())
            intents=[]
            for i,p in enumerate(plans):
                e=dict(p,label_status='ok'if i<1143 else'excluded_delayed_entry_liquidation_proxy_beyond_stop',economic_path_resolved=True)
                if i>=1143:e['entry_cancel_ns']=p['signal_ns']+2
                intents.append(e)
            ip=art('intents_jsonl','Private/development-intents.jsonl',''.join(json.dumps(p)+'\n'for p in intents).encode());(d/'Private/development-intents.jsonl').write_bytes(ip.read_bytes());ic=art('intents_csv','Private/development-intents.csv',b'SYNTHETIC HUMAN CSV\n');(d/'Private/development-intents.csv').write_bytes(ic.read_bytes())
            release=dict(schema='es-frozen-second-role-release-v1',role='development',row_count=1143,intent_row_count=1145,unresolved_intent_count=0,csv_sha256=expected['Private/second-candidates-known.csv'],intent_jsonl_sha256=g.sha(ip),intent_csv_sha256=g.sha(ic),synthetic=True);rp=attempt/'Private/development-release.json';dump(rp,release);art('role_release_json','Private/development-release.json');(d/'Private/development-release.json').write_bytes(rp.read_bytes())
            common=dict(schema='es-deterministic-recovery-acceptance-v1',status='EXACT_ORIGINAL_BYTE_AND_PLAN_MATCH',no_selection_or_parameter_change=True,no_sealed_access=True,no_model_fit=True,unavailable_original_ephemeral_metadata=sorted(g.ALLOWED_UNAVAILABLE),original_timestamps_fabricated=False,synthetic=True)
            kp=r/'Attempts/known-synthetic/Public/recovery-acceptance.json';dump(kp,dict(common,role='known'))
            dp=attempt/'Public/recovery-acceptance.json';dump(dp,dict(common,role='development',root_go_sha256='e'*64,output_root=str(attempt),artifacts=artifacts,cancellation_clock_evidence='new_deterministic_recovery_evidence_not_original_capture'))
            (r/'Source/namespace_prototype.py').write_text('SYNTHETIC REVIEWED I/O SOURCE\n');np=r/'Public/namespace-synthetic-acceptance.json';dump(np,dict(status='PASS_FULL_GENERATED_FUNCTION_SYNTHETIC_IO',checks_passed=11,all_three_roles_exercised=True,old_broken_mapping_negative_control_caught_all_roles=True,intents_durable_before_packaging_failure=True,per_day_complete_plan_hash_verified=True,sources_sha256={'namespace_prototype.py':g.sha(r/'Source/namespace_prototype.py')}))
            op=r/'OSProbe/output/result-syscalls-v2.json';dump(op,dict(status='PASS_OS_READONLY_OPEN_TRUNCATE_UNLINK_RENAME',allowed_output_create_append_rename_unlink=True,denials={k:dict(OS_denied=True,errno=1)for k in ['open_truncate','unlink','rename_out_of_input']}))
            ap=r/'AuditRuns/development-synthetic/Public/development-independent-acceptance.json';auditor=r/'Independent/audit_development_recovery_release.py';auditor.write_bytes((ORIGINAL_RECOVERY/'Independent/audit_development_recovery_release.py').read_bytes());numeric=l/'Audit/audit_development_release.py';numeric.write_bytes((ORIGINAL_LEARNING/'Audit/audit_development_release.py').read_bytes());audit=dict(authorization_mode='development_recovery',recovery_authorship_preserved=True,original_scientific_go_sha256='5b67d2e4501c83234cdda16679c0bbb843fa6d8f6e0fa96080c0ee19565f3597',recovery_go_sha256='e'*64,recovery_acceptance_sha256=g.sha(dp),development_completion_sha256=g.sha(dp),independent_numeric_source_sha256=g.sha(numeric),independent_authorization_adapter_sha256=g.sha(auditor),status='PASS_INDEPENDENT_DEVELOPMENT_RAW_PRICE_FEATURE_FILL_AND_BASELINE_AUDIT',cases_verified=1143,decision_intents_verified=1145,cancelled_intents_verified=2,unresolved_intent_clocks=0,all_five_features_independently_reconstructed=True,all_entry_cancel_exit_proxy_clocks_verified=True,all_costs_and_R_verified=True,all_unique_economic_opportunities=True,complete_intent_ungated_baseline_parity=True,no_model_fits=True,no_sealed_files_opened=True,development_release_sha256=g.sha(d/'Private/development-release.json'),candidate_jsonl_sha256=expected['Private/second-candidates-known.jsonl'],independent_source_sha256=g.sha(auditor));dump(ap,audit)
            (l/'Source/train_fiveyear.py').write_bytes(real_training.read_bytes());dump(l/'Public/training-code-freeze.json',{'synthetic':True});dump(l/'Public/training-code-github-receipt.json',dict(published=True,published_before_fit=True,source_sha256=g.TRAINING_SHA,training_code_freeze_sha256=g.sha(l/'Public/training-code-freeze.json'),synthetic=True))
            fp=r/'Public/external-training-gate-synthetic-acceptance.json';dump(fp,dict(status='PASS',synthetic_only=True,gate_source_sha256=g.sha(P)));pp=r/'Public/external-training-gate-github-receipt.json';dump(pp,dict(published=True,published_before_fit=True,gate_source_sha256=g.sha(P),fixtures_sha256=g.sha(fp),publication_commit='f'*40,synthetic=True))
            go=r/'Private/root-fit-go.json';dump(go,dict(authorized=True,mode='fit-development-after-exact-recovery',gate_source_sha256=g.sha(P),gate_fixtures_sha256=g.sha(fp),gate_publication=bind(pp),known_recovery_acceptance=bind(kp),development_recovery_acceptance=bind(dp),namespace_acceptance=bind(np),OS_acceptance=bind(op),canonical_role_release=bind(d/'Private/development-release.json'),development_allrow_audit=bind(ap),execute_fit=False,synthetic=True))
            with patch.multiple(g,KNOWN_ORIGINAL=known,INCIDENT_EXPECTED=expected):yield SimpleNamespace(go=go,devproof=dp,knownproof=kp,plans=plans_path,intents=ip,canonical=d/'Private/development-release.json',allrow=ap,namespace=np,OS=op)

def positive():
    with fixture()as f:
        p=g.verify(f.go);assert p['decision_plan_days']if'decision_plan_days'in p else p['recovery_identity']['decision_plan_days']==775;assert not p['models_fit_by_gate'];assert p['recovery_identity']['resolved_entry_cancellations']==2

def known_changed_or_missing():
    for name in list(g.KNOWN_ORIGINAL):
        with fixture()as f:
            p=g.DATA/name;p.write_bytes(p.read_bytes()+b'TAMPER')
            # Other old metadata still says PASS; scientific byte check must win.
            rejects(lambda:g.verify(f.go))
    with fixture()as f:
        (g.DATA/'Private/second-candidates-known.jsonl').unlink();rejects(lambda:g.verify(f.go))

def mutate_dev(f,key,mutate):
    d=g.read(f.devproof);path=f.devproof.parent.parent/d['artifacts'][key]['path_relative_to_attempt'];mutate(path);d['artifacts'][key]['sha256']=g.sha(path);dump(f.devproof,d);update_binding(f.go,'development_recovery_acceptance',f.devproof)

def all_plans_required():
    with fixture()as f:
        def bad(p):
            v=[json.loads(s)for s in p.read_text().splitlines()];v[0]['feature_context']=99.;p.write_text(''.join(json.dumps(x)+'\n'for x in v))
        mutate_dev(f,'decision_plans_jsonl',bad);rejects(lambda:g.verify(f.go))
    with fixture()as f:
        def bad(p):
            v=p.read_text().splitlines();v[0]=v[1];p.write_text('\n'.join(v)+'\n')
        mutate_dev(f,'decision_plans_jsonl',bad);rejects(lambda:g.verify(f.go))

def original_case_equality():
    with fixture()as f:mutate_dev(f,'candidates_csv',lambda p:p.write_bytes(b'IMPROVED RESULT'));rejects(lambda:g.verify(f.go))

def two_cancel_clock_proof():
    with fixture()as f:
        def bad(p):
            v=[json.loads(s)for s in p.read_text().splitlines()];v[-1]['entry_cancel_ns']=None;p.write_text(''.join(json.dumps(x)+'\n'for x in v))
        mutate_dev(f,'intents_jsonl',bad);rejects(lambda:g.verify(f.go))
    with fixture()as f:
        d=g.read(f.devproof);d['cancellation_clock_evidence']='originally_captured';dump(f.devproof,d);update_binding(f.go,'development_recovery_acceptance',f.devproof);rejects(lambda:g.verify(f.go))

def no_scientific_metadata_waiver():
    with fixture()as f:
        d=g.read(f.knownproof);d['unavailable_original_ephemeral_metadata'].append('Private/second-candidates-known.jsonl');dump(f.knownproof,d);update_binding(f.go,'known_recovery_acceptance',f.knownproof);rejects(lambda:g.verify(f.go))

def allrow_audit_required():
    with fixture()as f:f.allrow.unlink();rejects(lambda:g.verify(f.go))
    with fixture()as f:
        a=g.read(f.allrow);a['cancelled_intents_verified']=0;dump(f.allrow,a);update_binding(f.go,'development_allrow_audit',f.allrow);rejects(lambda:g.verify(f.go))

def isolation_and_publication_required():
    with fixture()as f:
        n=g.read(f.namespace);n['old_broken_mapping_negative_control_caught_all_roles']=False;dump(f.namespace,n);update_binding(f.go,'namespace_acceptance',f.namespace);rejects(lambda:g.verify(f.go))
    with fixture()as f:
        o=g.read(f.OS);o['denials']['unlink']['OS_denied']=False;dump(f.OS,o);update_binding(f.go,'OS_acceptance',f.OS);rejects(lambda:g.verify(f.go))
    with fixture()as f:
        p=g.RECOVERY/'Public/external-training-gate-github-receipt.json';o=g.read(p);o['published']=False;dump(p,o);update_binding(f.go,'gate_publication',p);rejects(lambda:g.verify(f.go))

def changed_canonical_release():
    with fixture()as f:
        o=g.read(f.canonical);o['row_count']=1144;dump(f.canonical,o);update_binding(f.go,'canonical_role_release',f.canonical);rejects(lambda:g.verify(f.go))

def bad_known_never_launches():
    with fixture()as f:
        o=g.read(f.go);o['execute_fit']=True;dump(f.go,o);(g.DATA/'Private/second-candidates-known.csv').write_text('wrong')
        with patch.object(g.subprocess,'run',side_effect=AssertionError('No fit permitted'))as child:rejects(lambda:g.launch(f.go));assert not child.called

def verify_only_cannot_fit():
    with fixture()as f:
        with patch.object(g.subprocess,'run',side_effect=AssertionError('No fit permitted'))as child:rejects(lambda:g.launch(f.go));assert not child.called

def mocked_launch_attaches_receipt():
    with fixture()as f:
        profile=g.RECOVERY/'OSProbe/fit-synthetic.sb';profile.write_text('SYNTHETIC NEVER EXECUTED OS PROFILE');o=g.read(f.go);o.update(execute_fit=True,fit_OS_profile=bind(profile),fit_OS_profile_reviewed=True);dump(f.go,o)
        def child(args,**kwargs):
            assert args[0]=='/usr/bin/sandbox-exec' and args[-2]=='--input';r=g.read(f.canonical);dump(g.LEARNING/'Public/models-frozen.json',dict(source_sha256=g.TRAINING_SHA,development_csv_sha256=r['csv_sha256'],development_intents_sha256=r['intent_jsonl_sha256'],synthetic=True));return SimpleNamespace(returncode=0)
        with patch.object(g.subprocess,'run',side_effect=child)as process:p=g.launch(f.go);assert process.call_count==1
        assert p['state']=='FIT_COMPLETE_MODELS_BOUND_TO_PASSED_EXTERNAL_GATE'and p['models_frozen_sha256']==g.sha(g.LEARNING/'Public/models-frozen.json');assert p['gate_receipt_sha256']==g.sha(g.RECOVERY/'Private/external-fit-integrity-receipt.json');rejects(lambda:g.launch(f.go))

def main():
    for name,fn in [('complete_synthetic_recovery_gate_passes',positive),('changed_or_missing_original_known_science_blocks_despite_old_PASS',known_changed_or_missing),('all775_original_plan_hashes_and1145_unique_plans_required',all_plans_required),('original1143_case_bytes_cannot_be_replaced',original_case_equality),('both_new_cancel_clocks_and_honest_evidence_label_required',two_cancel_clock_proof),('only_two_ephemeral_status_files_may_be_unavailable',no_scientific_metadata_waiver),('independent_allrow_price_audit_is_mandatory',allrow_audit_required),('I_O_isolation_and_publication_required',isolation_and_publication_required),('canonical_release_must_equal_isolated_recovery',changed_canonical_release),('bad_known_science_never_starts_subprocess',bad_known_never_launches),('verify_only_GO_cannot_fit',verify_only_cannot_fit),('mocked_launch_binds_passed_gate_receipt_to_models_once',mocked_launch_attaches_receipt)]:check(name,fn)
    proof=dict(schema='EXTERNAL-TRAINING-GATE-SYNTHETIC-1',status='PASS',utc=g.now(),checks=len(RESULT),tests=RESULT,gate_source_sha256=g.sha(P),fixture_source_sha256=g.sha(__file__),synthetic_only=True,production_gate_run=False,real_recovery_or_restoration_run=False,real_label_files_opened=False,real_models_fit=False,real_subprocess_launched=False,sealed_files_opened=False,frozen_sources_changed=False)
    out=ORIGINAL_RECOVERY/'Public/external-training-gate-synthetic-acceptance.json';dump(out,proof);print(json.dumps(proof,indent=2))
if __name__=='__main__':main()
