"""Synthetic metadata/authorization tests; no actual development audit executes."""
from pathlib import Path
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch
import ast,hashlib,importlib.util,json,tempfile,sys
sys.dont_write_bytecode=True
P=Path(__file__).with_name('audit_development_recovery_release.py');sp=importlib.util.spec_from_file_location('audit_adapter_sut',P);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);R=m.RECOVERY;RESULT=[]

def dump(p,o):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o)+'\n')
def bind(p):return dict(path=str(p),sha256=m.sha(p))
def rejects(fn):
    try:fn()
    except ValueError:return
    raise AssertionError('Expected guard rejection')
def check(name,fn):fn();RESULT.append(name)

@contextmanager
def fixture():
    with tempfile.TemporaryDirectory(prefix='recovery-audit-auth-synthetic-')as tmp:
        r=Path(tmp)/'Recovery';d=Path(tmp)/'Data';l=Path(tmp)/'ML'
        for p in [r/'Independent',r/'Public',r/'Private',r/'Source',r/'AuditRuns',d/'Private',d/'Public',l/'Public',l/'Private']:p.mkdir(parents=True,exist_ok=True)
        original=d/'Private/root-development-go.json';dump(original,dict(authorized=True,mode='development',source_freeze_sha256=m.ALGORITHM_FREEZE_SHA,synthetic=True));original_sha=m.sha(original)
        marker=d/'Private/Incidents/development-dispatch-path-20261121/Private/development-label-attempt.json';dump(marker,dict(root_go_sha256=original_sha,utc='2026-11-21T03:00:00+00:00',synthetic=True))
        price=d/'Public/development-price-completeness.json';dump(price,dict(status='PASS_PRICE_INTEGRITY_AND_SESSION_ENUMERATION',role='development',price_only=True,no_candidate_or_label_files_read=True,all_planned_role_sessions_present=True,utc='2026-11-21T02:00:00+00:00',synthetic=True))
        (r/'Source/recover_exact.py').write_text('SYNTHETIC CONTROL SOURCE\n');freeze=r/'Public/recovery-source-freeze.json';dump(freeze,dict(sources_sha256={'recover_exact.py':m.sha(r/'Source/recover_exact.py')},synthetic=True))
        recovery_go=r/'Private/root-development-recovery-go.json';dump(recovery_go,dict(authorized=True,mode='development-recovery',published_before_recovery=True,bindings=dict(source_freeze=bind(freeze),development_price_audit=bind(price)),synthetic=True))
        attempt=r/'Attempts/development-synthetic';(attempt/'Private').mkdir(parents=True);(attempt/'Public').mkdir();artifacts={}
        expected={}
        for key,name in [('candidates_jsonl','development-candidates.jsonl'),('candidates_csv','development-candidates.csv'),('schedule_json','development-price-roll-freeze.json')]:
            p=attempt/'Private'/name;p.write_text('SYNTHETIC SCIENCE '+key+'\n');expected[key]=m.sha(p);(d/'Private'/name).write_bytes(p.read_bytes());artifacts[key]=dict(path_relative_to_attempt='Private/'+name,sha256=m.sha(p))
        manifest=d/'Private/development-release.json';value=dict(role='development',root_go_sha256=m.sha(recovery_go),generator_source_freeze_sha256=m.ALGORITHM_FREEZE_SHA,recovery_source_freeze_sha256=m.sha(freeze),synthetic=True);dump(manifest,value);(attempt/'Private/development-release.json').write_bytes(manifest.read_bytes());artifacts['role_release_json']=dict(path_relative_to_attempt='Private/development-release.json',sha256=m.sha(manifest))
        proof=attempt/'Public/recovery-acceptance.json';dump(proof,dict(status='EXACT_ORIGINAL_BYTE_AND_PLAN_MATCH',role='development',root_go_sha256=m.sha(recovery_go),immutable_original_Data_root_postcheck_passed=True,immutable_original_ML_root_postcheck_passed=True,no_selection_or_parameter_change=True,no_model_fit=True,no_sealed_access=True,bindings=m.read(recovery_go)['bindings'],artifacts=artifacts,synthetic=True))
        summary=attempt/'Public/development-labels-summary.json';dump(summary,dict(status='DEVELOPMENT_LABELS_COMPLETE_FROZEN_ENGINE',root_go_sha256=m.sha(recovery_go),source_freeze_sha256=m.ALGORITHM_FREEZE_SHA,candidates_jsonl_sha256=expected['candidates_jsonl'],candidates_csv_sha256=expected['candidates_csv'],known_schedule_sha256=expected['schedule_json'],cases=1143,month_manifest_sha256={},synthetic=True))
        known={}
        for name in m.ORIGINAL_KNOWN:
            p=d/name;p.write_text('SYNTHETIC KNOWN SCIENCE '+name+'\n');known[name]=m.sha(p)
        auth=r/'Private/root-audit-go.json';dump(auth,dict(authorized=True,mode='audit-development-recovery',adapter_source_sha256=m.sha(P),original_scientific_go=bind(original),recovery_go=bind(recovery_go),recovery_acceptance=bind(proof),canonical_release=bind(manifest),recovered_labels_summary=bind(summary),price_completeness=bind(price),original_label_attempt=bind(marker),output_root=str(r/'AuditRuns/development-synthetic'),synthetic=True))
        with patch.multiple(m,RECOVERY=r,DATA=d,LEARNING=l,ORIGINAL_GO_SHA=original_sha,ORIGINAL_MARKER_SHA=m.sha(marker),RECOVERY_FREEZE_SHA=m.sha(freeze),DEVELOPMENT_JSONL_SHA=expected['candidates_jsonl'],DEVELOPMENT_CSV_SHA=expected['candidates_csv'],DEVELOPMENT_SCHEDULE_SHA=expected['schedule_json'],ORIGINAL_KNOWN=known):yield SimpleNamespace(auth=auth,original=original,recovery_go=recovery_go,proof=proof,manifest=manifest,summary=summary,price=price,marker=marker,attempt=attempt)

def positive_authors():
    with fixture()as f:
        c=m.recovery_context(f.auth);assert c.recovery_go['mode']=='development-recovery'and c.summary['status']=='DEVELOPMENT_LABELS_COMPLETE_FROZEN_ENGINE';assert not(m.DATA/'Public/development-labels-completion.json').exists()

def reject_relabelled_original():
    with fixture()as f:
        v=m.read(f.manifest);v['root_go_sha256']=m.ORIGINAL_GO_SHA;dump(f.manifest,v);a=m.read(f.auth);a['canonical_release']=bind(f.manifest);dump(f.auth,a);rejects(lambda:m.recovery_context(f.auth))

def reject_wrong_original_GO():
    with fixture()as f:
        v=m.read(f.original);v['synthetic_tamper']=True;dump(f.original,v);a=m.read(f.auth);a['original_scientific_go']=bind(f.original);dump(f.auth,a);rejects(lambda:m.recovery_context(f.auth))

def price_must_precede_original_marker():
    with fixture()as f:
        v=m.read(f.price);v['utc']='2026-11-21T04:00:00+00:00';dump(f.price,v)
        # Rebind the synthetic new recovery evidence: late historical proof is still invalid.
        g=m.read(f.recovery_go);g['bindings']['development_price_audit']=bind(f.price);dump(f.recovery_go,g);newsha=m.sha(f.recovery_go)
        s=m.read(f.summary);s['root_go_sha256']=newsha;dump(f.summary,s)
        q=m.read(f.manifest);q['root_go_sha256']=newsha;dump(f.manifest,q);(f.attempt/'Private/development-release.json').write_bytes(f.manifest.read_bytes())
        p=m.read(f.proof);p['root_go_sha256']=newsha;p['bindings']=g['bindings'];p['artifacts']['role_release_json']['sha256']=m.sha(f.manifest);dump(f.proof,p)
        a=m.read(f.auth)
        for name,path in [('recovery_go',f.recovery_go),('recovered_labels_summary',f.summary),('canonical_release',f.manifest),('recovery_acceptance',f.proof),('price_completeness',f.price)]:a[name]=bind(path)
        dump(f.auth,a);rejects(lambda:m.recovery_context(f.auth))

def models_and_known_changes_block():
    with fixture()as f:dump(m.LEARNING/'Public/models-frozen.json',{'synthetic':True});rejects(lambda:m.recovery_context(f.auth))
    with fixture()as f:(m.DATA/'Private/second-candidates-known.csv').write_text('wrong');rejects(lambda:m.recovery_context(f.auth))

def actual_numeric_AST_is_unchanged():
    module=m.original_numeric_module()
    with tempfile.TemporaryDirectory(prefix='ast-only-no-data-')as tmp:
        c=SimpleNamespace(output=Path(tmp),acceptance_path=Path(tmp)/'authentic-recovery.json');fn=m.audit_function(module,c)
        for name in ['indicators','band','outward','expected_label','RawPrices']:assert fn.__globals__[name]is getattr(module,name)
        assert fn.__globals__['HERE']==Path(tmp)and fn.__globals__['RECOVERY_ACCEPTANCE_PATH']==c.acceptance_path
    assert sys.dont_write_bytecode is True

def synthetic_end_to_end_metadata_IO():
    with fixture()as f:
        c=m.recovery_context(f.auth);c.output.mkdir();(c.output/'Public').mkdir();(c.output/'Private').mkdir()
        source=c.output/'synthetic_numeric_module.py';source.write_text('''from pathlib import Path
import hashlib,json
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value))
def indicators(x):return x
def band(*x):return x
def outward(*x):return x
def expected_label(*x):return x
class RawPrices:pass
def audit(receipt):
    go,completion,manifest,price=authorize(receipt)
    value=dict(root_go_sha256=sha(receipt),development_completion_sha256=sha(DATA/'Public/development-labels-completion.json'),independent_source_sha256=sha(__file__),numeric_fixture_only=True)
    save(HERE/'Public/development-independent-acceptance.json',value)
    return value
''')
        spec=importlib.util.spec_from_file_location('synthetic_numeric_only',source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.DATA=m.DATA
        m.audit_function(module,c)(c.recovery_go_path);p=m.read(c.output/'Public/development-independent-acceptance.json')
        assert p['root_go_sha256']==m.sha(f.recovery_go)and p['original_scientific_go_sha256']==m.sha(f.original)and p['development_completion_sha256']==m.sha(f.proof)
        assert p['recovery_authorship_preserved']and p['independent_numeric_source_sha256']==m.ORIGINAL_AUDIT_SHA and p['independent_source_sha256']==m.sha(P)
        assert not(m.DATA/'Public/development-labels-completion.json').exists()and not(m.LEARNING/'Public/development-independent-acceptance.json').exists()

def main():
    for name,fn in [('original_and_recovery_authorship_stay_distinct',positive_authors),('cannot_rewrite_recovery_manifest_as_original_dispatch',reject_relabelled_original),('exact_original_scientific_GO_required',reject_wrong_original_GO),('price_audit_must_predate_original_not_recovery_marker',price_must_precede_original_marker),('any_prior_fit_or_changed_known_science_blocks',models_and_known_changes_block),('actual_cfe4_numeric_functions_and_arithmetic_AST_unchanged',actual_numeric_AST_is_unchanged),('full_synthetic_metadata_adapter_IO_no_legacy_file_fabrication',synthetic_end_to_end_metadata_IO)]:check(name,fn)
    proof=dict(status='PASS',schema='RECOVERY-AUDIT-AUTHORIZATION-SYNTHETIC-1',utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),checks=len(RESULT),tests=RESULT,adapter_source_sha256=m.sha(P),fixture_source_sha256=m.sha(__file__),independent_numeric_source_sha256=m.ORIGINAL_AUDIT_SHA,original_scientific_go_sha256=m.ORIGINAL_GO_SHA,synthetic_only=True,actual_audit_executed=False,real_label_files_opened=False,model_fits=False,original_Data_or_ML_written=False,sealed_files_opened=False)
    dump(R/'Public/recovery-audit-authorization-synthetic-acceptance.json',proof);print(json.dumps(proof,indent=2))
if __name__=='__main__':main()
