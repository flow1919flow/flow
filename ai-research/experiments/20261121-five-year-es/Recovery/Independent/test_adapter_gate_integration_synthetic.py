"""Producer→adapter→filesystem→external-gate integration, synthetic only.

The PASS report constructor/save tail comes verbatim from the real cfe4 audit
AST. Market verification is explicitly stubbed; this tests artifact integration,
not market evidence. Both the real adapter main and real external verify execute
on temporary roots. No fit subprocess or real label rows are accessed.
"""
from pathlib import Path
from types import SimpleNamespace,ModuleType
from unittest.mock import patch
from contextlib import redirect_stdout
import ast,copy,hashlib,importlib.util,io,json,sys,time
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
fixtures=load('existing_gate_fixture',ROOT/'Independent/test_external_training_gate_synthetic.py');g=fixtures.g
adapter=load('actual_report_adapter',ROOT/'Independent/audit_development_recovery_release.py')
ACTUAL_NUMERIC_SOURCE=fixtures.ORIGINAL_LEARNING/'Audit/audit_development_release.py'
ORIGINAL_GO=fixtures.ORIGINAL_DATA/'Private/root-development-go.json'
ORIGINAL_MARKER=fixtures.ORIGINAL_DATA/'Private/Incidents/development-dispatch-path-20261121/Private/development-label-attempt.json'
RESULT=[]

def make_producer(ctx,gate,output_root,fail=False,wrong_cancel_count=False):
 source_tree=ast.parse(ACTUAL_NUMERIC_SOURCE.read_text());function=next(n for n in source_tree.body if isinstance(n,ast.FunctionDef)and n.name=='audit');start=next(i for i,n in enumerate(function.body)if isinstance(n,ast.Assign)and any(isinstance(k,ast.Name)and k.id=='proof'for k in n.targets));tail=copy.deepcopy(function.body[start:]);actual_constructor=ast.dump(tail[0],include_attributes=False)
 prelude='''go,completion,manifest,priceproof=authorize(receipt)
canonical=DATA/'Private/development-candidates.jsonl'
cases=[json.loads(s)for s in canonical.read_text().splitlines()if s]
intents=[json.loads(s)for s in (DATA/'Private/development-intents.jsonl').read_text().splitlines()if s]
cancels=[e for e in intents if e['label_status']!='ok']
need(all(isinstance(e.get('entry_cancel_ns'),int)and e['entry_cancel_ns']>=e['signal_ns']+2000000000 for e in cancels),'Synthetic cancellation clock mismatch')
cancelled=len(cancels)
unresolved=sum(not e['economic_path_resolved']for e in intents)
baseline=dict(frozen_generator_baseline_parity=True,synthetic_market_checks_stubbed=True)
maxerr=Counter();reasons=Counter();warning_summary={}
prices=SimpleNamespace(verified_files={});began=time.time()
'''
 if wrong_cancel_count:prelude+='cancelled-=1\n'
 if fail:prelude+="raise ValueError('Deliberate synthetic raw-clock audit failure')\n"
 new=copy.deepcopy(function);new.body=ast.parse(prelude).body+tail;ast.fix_missing_locations(new)
 need_same=ast.dump(new.body[-len(tail)],include_attributes=False)==actual_constructor
 assert need_same,'Real production report constructor was altered in integration fixture'
 p=gate.RECOVERY/'Independent/synthetic_actual_report_producer.py';p.write_text(ast.unparse(ast.Module(body=[new],type_ignores=[]))+'\n')
 # Explicit synthetic stubs around unchanged actual production report code.
 module=ModuleType('synthetic_market_checks_actual_report');module.__file__=str(p);module.DATA=gate.DATA
 module.read=adapter.read;module.sha=adapter.sha;module.need=adapter.need
 def save(path,value):adapter.need(output_root.resolve()in Path(path).resolve().parents,'Fixture write outside adapter output');Path(path).write_text(json.dumps(value))
 module.save=save;module.now=lambda:__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
 module.indicators=lambda x:x;module.band=lambda *x:x;module.outward=lambda *x:x;module.expected_label=lambda *x:x;module.RawPrices=object
 module.TRAINING_SHA=gate.TRAINING_SHA;module.Counter=__import__('collections').Counter;module.datetime=__import__('datetime').datetime;module.timezone=__import__('datetime').timezone;module.time=time;module.json=json;module.SimpleNamespace=SimpleNamespace
 return module,hashlib.sha256(actual_constructor.encode()).hexdigest()

def bind_actual_inputs(f):
 # Use exact-clock synthetic cancellation intents; rebind every genuine fixture
 # artifact and release envelope instead of hand-authoring an audit PASS.
 proof=g.read(f.devproof);attempt=f.devproof.parent.parent
 ip=attempt/proof['artifacts']['intents_jsonl']['path_relative_to_attempt'];intents=[json.loads(s)for s in ip.read_text().splitlines()if s]
 for event in intents:
  if event['label_status']!='ok':event['entry_cancel_ns']=event['signal_ns']+2_000_000_000
 ip.write_text(''.join(json.dumps(e)+'\n'for e in intents));(g.DATA/'Private/development-intents.jsonl').write_bytes(ip.read_bytes());proof['artifacts']['intents_jsonl']['sha256']=g.sha(ip)
 release=g.read(f.canonical);release['intent_jsonl_sha256']=g.sha(ip);fixtures.dump(f.canonical,release);rp=attempt/proof['artifacts']['role_release_json']['path_relative_to_attempt'];rp.write_bytes(f.canonical.read_bytes());proof['artifacts']['role_release_json']['sha256']=g.sha(rp)
 recovery_go=g.RECOVERY/'Private/actual-synthetic-development-recovery-go.json';fixtures.dump(recovery_go,dict(authorized=True,mode='development-recovery',synthetic=True));proof['root_go_sha256']=g.sha(recovery_go);fixtures.dump(f.devproof,proof);fixtures.update_binding(f.go,'development_recovery_acceptance',f.devproof);fixtures.update_binding(f.go,'canonical_role_release',f.canonical)
 original_copy=g.DATA/'Private/original-scientific-go.json';original_copy.write_bytes(ORIGINAL_GO.read_bytes());marker=g.DATA/'Private/original-label-marker.json';marker.write_bytes(ORIGINAL_MARKER.read_bytes())
 summary=g.RECOVERY/'Private/authentic-synthetic-recovery-summary.json';fixtures.dump(summary,dict(status='DEVELOPMENT_LABELS_COMPLETE_FROZEN_ENGINE',root_go_sha256=g.sha(recovery_go),synthetic=True))
 authorization=g.RECOVERY/'Private/audit-authorization.json';fixtures.dump(authorization,dict(authorized=True,mode='audit-development-recovery',synthetic=True))
 fixtures.dump(g.DATA/'Public/development-price-completeness.json',dict(status='PASS_PRICE_INTEGRITY_AND_SESSION_ENUMERATION',synthetic=True))
 return recovery_go,original_copy,marker,summary,authorization

def execute_integration(label,fail=False,wrong_cancel_count=False):
 with fixtures.fixture()as f:
  recovery_go,original,marker,summary,authorization=bind_actual_inputs(f)
  # Delete the old hand-authored ideal proof. Consumer must use actual producer.
  f.allrow.unlink()
  output=g.RECOVERY/'AuditRuns'/label
  ctx=SimpleNamespace(output=output,acceptance_path=f.devproof,recovery_go_path=recovery_go,recovery_go=g.read(recovery_go),summary=g.read(summary),manifest=g.read(f.canonical),price={},original_go_path=original,summary_path=summary,marker_path=marker,authorization_path=authorization)
  producer,constructor_sha=make_producer(ctx,g,output,fail,wrong_cancel_count)
  with patch.object(adapter,'recovery_context',return_value=ctx),patch.object(adapter,'original_numeric_module',return_value=producer),patch.object(sys,'argv',['audit_adapter','--authorization',str(authorization)]),redirect_stdout(io.StringIO()):
   if fail:
    try:adapter.main()
    except ValueError as error:assert 'Deliberate synthetic' in str(error)
    else:raise AssertionError('Expected actual adapter failure path')
   else:adapter.main()
  actual=output/'Public/development-independent-acceptance.json'
  if fail:
   failure=output/'Public/development-recovery-audit-failure.json';assert failure.exists()and not actual.exists();assert g.read(failure)['status']=='AUDIT_CLOSED_NO_FIT'
   # Even with the accepted consumer filename and rebound hash, FAILED evidence
   # must be rejected; this prevents trivial filename-only negative controls.
   actual.write_bytes(failure.read_bytes())
  fixtures.update_binding(f.go,'development_allrow_audit',actual)
  with patch.object(g.subprocess,'run',side_effect=AssertionError('No fit subprocess permitted'))as child:
   if fail or wrong_cancel_count:fixtures.rejects(lambda:g.verify(f.go))
   else:
    result=g.verify(f.go);proof=g.read(actual);assert result['status']=='PASS_ALL_SCIENTIFIC_BYTES_RECOVERY_AND_ALLROW_AUDIT';assert proof['cases_verified']==1143 and proof['decision_intents_verified']==1145 and proof['cancelled_intents_verified']==2
    assert proof['recovery_authorship_preserved']and proof['original_scientific_go_sha256']==adapter.ORIGINAL_GO_SHA and proof['recovery_go_sha256']==g.sha(recovery_go)
    assert proof['recovery_acceptance_sha256']==g.sha(f.devproof)==proof['development_completion_sha256'];assert proof['independent_numeric_source_sha256']==adapter.ORIGINAL_AUDIT_SHA and proof['independent_authorization_adapter_sha256']==adapter.sha(adapter.__file__)
   assert not child.called
  assert not(g.LEARNING/'Public/development-independent-acceptance.json').exists()and not(g.LEARNING/'Public/models-frozen.json').exists()
  RESULT.append(dict(test=label,status='PASS',actual_adapter_main_and_real_report_save_executed=True,actual_external_gate_verify_executed=True,actual_cfe4_report_constructor_AST_sha256=constructor_sha,numeric_market_checks_explicit_synthetic_stubs=True,hand_authored_PASS_proof_consumed=False,failed_proof_negative_control=fail,no_fit_subprocess=True))

def main():
 execute_integration('producer-adapter-to-external-gate')
 execute_integration('failed-real-adapter-proof-is-rejected',fail=True)
 execute_integration('real-report-wrong-cancel-count-is-rejected',wrong_cancel_count=True)
 proof=dict(schema='ADAPTER-TO-EXTERNAL-GATE-INTEGRATION-1',status='PASS',utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),checks=len(RESULT),tests=RESULT,adapter_source_sha256=adapter.sha(adapter.__file__),gate_source_sha256=g.sha(g.__file__),fixture_source_sha256=g.sha(__file__),synthetic_only=True,production_gate_or_audit_run=False,real_row_labels_read=False,actual_fit_invoked=False,original_roots_written=False,sealed_files_opened=False)
 fixtures.dump(ROOT/'Public/adapter-external-gate-integration-synthetic-acceptance.json',proof);print(json.dumps(proof,indent=2))
if __name__=='__main__':main()
