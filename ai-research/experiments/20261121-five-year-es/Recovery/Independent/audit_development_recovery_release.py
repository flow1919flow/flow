"""Recovery-authorship adapter for the unchanged independent numeric auditor.

Original cfe4 source is read-only. Only authorization and output/provenance I/O
are adapted; no false original-dispatch completion file is written. All output
is confined to a fresh RecoveryRoot/AuditRuns namespace. Default CLOSED.
"""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timezone
import argparse,ast,copy,hashlib,importlib.util,json,os,sys,time
sys.dont_write_bytecode=True

RECOVERY=Path(__file__).resolve().parents[1];DATA=RECOVERY.parent/'ES-FiveYear-SecondData-20261121';LEARNING=RECOVERY.parent/'ES-FiveYear-ML-20261121'
ORIGINAL_AUDIT_SHA='cfe4d8f21b545097feca330ff69a459370e8e0bf13b1b0949c7b7df236011aa9'
ORIGINAL_GO_SHA='5b67d2e4501c83234cdda16679c0bbb843fa6d8f6e0fa96080c0ee19565f3597'
ORIGINAL_MARKER_SHA='87fa1e876210fe1428d66cde04743ade34d10ad88f804de8a135a1dcdbd31e54'
ALGORITHM_FREEZE_SHA='3234ca42565168097578e5af8cc6e581e86adc16472d20983fe1f890acec1681'
RECOVERY_FREEZE_SHA='a7bcf50550c58018a5dece7ee656846e6d341f00f31e95b2f8b9a918d7ce1d96'
DEVELOPMENT_JSONL_SHA='e9ad3462256580794182a11520f05ce2e0296f609b2998e8ef72919a147145ce'
DEVELOPMENT_CSV_SHA='432fa618624d0de557113b8efb4da68752008cc14f3d0395b89197d5239763c5'
DEVELOPMENT_SCHEDULE_SHA='576ecc9071b6eeaa4a1b4475a37a753abd16303456ce63101de690a9f1201343'
ORIGINAL_KNOWN={
 'Private/second-candidates-known.jsonl':'b021d522a869d69f8893232123420cba78181c9a2f6425bae3c6973e40a2c67a',
 'Private/second-candidates-known.csv':'163e2bb54c2539e4685e33624bdcd528eb6786fbeadb265fd68e82312766e715',
 'Private/second-known-price-roll-freeze.json':'234897b90557cb44eda32c7ce0d6756a60841980f6eccfbe6ccc9f582c257e9d'}


def need(test,message):
    if not test:raise ValueError(message)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def bound(binding,expected=None,inside=None):
    need(isinstance(binding,dict),'Missing audit authorization binding');p=Path(binding.get('path','')).resolve()
    if expected is not None:need(p==Path(expected).resolve(),'Wrong audit evidence namespace')
    if inside is not None:need(Path(inside).resolve()in p.parents,'Audit evidence escaped recovery namespace')
    need(p.is_file()and sha(p)==binding.get('sha256'),'Audit evidence missing or changed');return p

def original_numeric_module():
    p=LEARNING/'Audit/audit_development_release.py';need(sha(p)==ORIGINAL_AUDIT_SHA,'Original numeric auditor changed')
    spec=importlib.util.spec_from_file_location('immutable_numeric_cfe4',p);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def recovery_context(authorization):
    auth=read(authorization);need(auth.get('authorized')is True and auth.get('mode')=='audit-development-recovery','Explicit recovery-specific audit GO required')
    need(auth.get('adapter_source_sha256')==sha(__file__),'Audit GO binds another adapter')
    original=bound(auth.get('original_scientific_go'),expected=DATA/'Private/root-development-go.json');need(sha(original)==ORIGINAL_GO_SHA,'Original scientific authorization changed');ogo=read(original)
    need(ogo.get('authorized')is True and ogo.get('mode')=='development'and ogo.get('source_freeze_sha256')==ALGORITHM_FREEZE_SHA,'Wrong original scientific role/source')
    recovery_go=bound(auth.get('recovery_go'),inside=RECOVERY);rgo=read(recovery_go);need(rgo.get('authorized')is True and rgo.get('mode')=='development-recovery'and rgo.get('published_before_recovery')is True,'New recovery authorship not authorized/published')
    acceptance=bound(auth.get('recovery_acceptance'),inside=RECOVERY/'Attempts');proof=read(acceptance);attempt=acceptance.parent.parent
    need(proof.get('status')=='EXACT_ORIGINAL_BYTE_AND_PLAN_MATCH'and proof.get('role')=='development'and proof.get('root_go_sha256')==sha(recovery_go),'Recovery not exact or bound to real recovery GO')
    need(proof.get('immutable_original_Data_root_postcheck_passed')is True and proof.get('immutable_original_ML_root_postcheck_passed')is True,'Recovery original-root postchecks incomplete')
    need(proof.get('no_selection_or_parameter_change')is True and proof.get('no_model_fit')is True and proof.get('no_sealed_access')is True,'Recovery scientific scope changed')
    sourcefreeze=bound(rgo.get('bindings',{}).get('source_freeze'),expected=RECOVERY/'Public/recovery-source-freeze.json');need(sha(sourcefreeze)==RECOVERY_FREEZE_SHA,'Production recovery freeze changed')
    freeze=read(sourcefreeze)
    for name,digest in freeze['sources_sha256'].items():need(sha(RECOVERY/'Source'/name)==digest,'Frozen recovery source changed')
    manifest_path=bound(auth.get('canonical_release'),expected=DATA/'Private/development-release.json');manifest=read(manifest_path)
    need(manifest.get('role')=='development'and manifest.get('root_go_sha256')==sha(recovery_go),'Canonical manifest authorship was falsified or rebound')
    need(manifest.get('generator_source_freeze_sha256')==ALGORITHM_FREEZE_SHA and manifest.get('recovery_source_freeze_sha256')==RECOVERY_FREEZE_SHA,'Original algorithm and new control-plane provenance must remain distinct')
    for name,binding in proof.get('bindings',{}).items():need(binding==rgo.get('bindings',{}).get(name),'Recovery proof/evidence differs from actual recovery GO')
    artifacts=proof.get('artifacts',{})
    for key,expected in [('candidates_jsonl',DEVELOPMENT_JSONL_SHA),('candidates_csv',DEVELOPMENT_CSV_SHA),('schedule_json',DEVELOPMENT_SCHEDULE_SHA),('role_release_json',sha(manifest_path))]:
        a=artifacts[key];p=(attempt/a['path_relative_to_attempt']).resolve();need(attempt.resolve()in p.parents and sha(p)==a['sha256']==expected,'Isolated recovered artifact differs from preserved science')
    need(sha(DATA/'Private/development-candidates.jsonl')==DEVELOPMENT_JSONL_SHA and sha(DATA/'Private/development-candidates.csv')==DEVELOPMENT_CSV_SHA and sha(DATA/'Private/development-price-roll-freeze.json')==DEVELOPMENT_SCHEDULE_SHA,'Promoted scientific role bytes differ from exact isolated recovery')
    for name,digest in ORIGINAL_KNOWN.items():need(sha(DATA/name)==digest,'Original known scientific file missing or changed')
    # Authentic metadata created by the fixed original function inside recovery;
    # it is never recast as the missing original-dispatch completion record.
    summary_path=bound(auth.get('recovered_labels_summary'),expected=attempt/'Public/development-labels-summary.json');summary=read(summary_path)
    need(summary.get('status')=='DEVELOPMENT_LABELS_COMPLETE_FROZEN_ENGINE'and summary.get('root_go_sha256')==sha(recovery_go)and summary.get('source_freeze_sha256')==ALGORITHM_FREEZE_SHA,'Authentic recovered summary authorship/source mismatch')
    need(summary.get('candidates_jsonl_sha256')==DEVELOPMENT_JSONL_SHA and summary.get('candidates_csv_sha256')==DEVELOPMENT_CSV_SHA and summary.get('known_schedule_sha256')==DEVELOPMENT_SCHEDULE_SHA and summary.get('cases')==1143,'Recovered summary science differs')
    price_path=bound(auth.get('price_completeness'),expected=DATA/'Public/development-price-completeness.json');price=read(price_path)
    need(price.get('status')=='PASS_PRICE_INTEGRITY_AND_SESSION_ENUMERATION'and price.get('role')=='development'and price.get('price_only')is True and price.get('no_candidate_or_label_files_read')is True and price.get('all_planned_role_sessions_present')is True,'Original price-only completeness evidence invalid')
    need(rgo.get('bindings',{}).get('development_price_audit',{}).get('sha256')==sha(price_path),'Recovered data used another price-completeness proof')
    marker_path=bound(auth.get('original_label_attempt'),expected=DATA/'Private/Incidents/development-dispatch-path-20261121/Private/development-label-attempt.json');need(sha(marker_path)==ORIGINAL_MARKER_SHA,'Original label-attempt marker changed');marker=read(marker_path)
    need(marker.get('root_go_sha256')==ORIGINAL_GO_SHA and datetime.fromisoformat(price['utc'])<=datetime.fromisoformat(marker['utc']),'Price audit must predate ORIGINAL scientific label marker')
    need(not(LEARNING/'Public/models-frozen.json').exists()and not(LEARNING/'Private/training-attempt.json').exists(),'Independent all-row audit must precede all actual fits')
    output=Path(auth.get('output_root','')).resolve();need((RECOVERY/'AuditRuns').resolve()in output.parents and not output.exists()and output.parent.is_dir(),'Require fresh audit output below existing RecoveryRoot/AuditRuns')
    return SimpleNamespace(auth=auth,authorization_path=Path(authorization),original_go_path=original,recovery_go_path=recovery_go,recovery_go=rgo,acceptance_path=acceptance,proof=proof,manifest_path=manifest_path,manifest=manifest,summary_path=summary_path,summary=summary,price_path=price_path,price=price,marker_path=marker_path,output=output)

class CompletionHashIO(ast.NodeTransformer):
    def __init__(self,reverse=False):self.reverse=reverse;self.count=0
    def visit_BinOp(self,node):
        if not self.reverse and isinstance(node.op,ast.Div)and isinstance(node.left,ast.Name)and node.left.id=='DATA'and isinstance(node.right,ast.Constant)and node.right.value=='Public/development-labels-completion.json':
            self.count+=1;return ast.copy_location(ast.Name(id='RECOVERY_ACCEPTANCE_PATH',ctx=ast.Load()),node)
        return self.generic_visit(node)
    def visit_Name(self,node):
        if self.reverse and node.id=='RECOVERY_ACCEPTANCE_PATH':
            self.count+=1;return ast.copy_location(ast.BinOp(left=ast.Name(id='DATA',ctx=ast.Load()),op=ast.Div(),right=ast.Constant('Public/development-labels-completion.json')),node)
        return node

def audit_function(module,ctx):
    original=next(n for n in ast.parse(Path(module.__file__).read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='audit');changed=copy.deepcopy(original);transform=CompletionHashIO();changed=transform.visit(changed);ast.fix_missing_locations(changed);need(transform.count==1,'Expected exactly one legacy completion-hash I/O expression')
    restored=CompletionHashIO(reverse=True).visit(copy.deepcopy(changed));ast.fix_missing_locations(restored);need(ast.dump(restored,include_attributes=False)==ast.dump(original,include_attributes=False),'Independent arithmetic/body changed beyond named provenance I/O')
    def authorize(receipt):
        need(Path(receipt).resolve()==ctx.recovery_go_path.resolve(),'Numeric audit received wrong recovery authorship');return ctx.recovery_go,dict(ctx.summary),ctx.manifest,ctx.price
    def save(path,value):
        path=Path(path).resolve();need(ctx.output.resolve()in path.parents,'Audit write escaped fresh recovery output')
        if path.name=='development-independent-acceptance.json':
            value=dict(value,authorization_mode='development_recovery',recovery_authorship_preserved=True,original_scientific_go_sha256=sha(ctx.original_go_path),recovery_go_sha256=sha(ctx.recovery_go_path),recovery_acceptance_sha256=sha(ctx.acceptance_path),authentic_recovered_summary_sha256=sha(ctx.summary_path),original_label_marker_sha256=sha(ctx.marker_path),audit_authorization_sha256=sha(ctx.authorization_path),independent_numeric_source_sha256=ORIGINAL_AUDIT_SHA,independent_authorization_adapter_sha256=sha(__file__),development_completion_evidence_kind='authentic_isolated_recovery_acceptance_NOT_original_dispatch_completion',numeric_function_objects_unchanged=True,audit_body_only_one_metadata_hash_IO_expression_adapted=True,original_ML_and_Data_roots_written=False,all_output_under_fresh_RecoveryRoot_AuditRuns=True)
        module.save(path,value)
    env=dict(vars(module));env.update(HERE=ctx.output,__file__=__file__,RECOVERY_ACCEPTANCE_PATH=ctx.acceptance_path,authorize=authorize,save=save)
    for name in ['indicators','band','outward','expected_label','RawPrices']:need(env[name]is getattr(module,name),'Independent numeric function replaced')
    exec(compile(ast.Module(body=[changed],type_ignores=[]),'UNCHANGED_NUMERIC_AUDIT_WITH_RECOVERY_AUTH_IO','exec'),env);return env['audit']

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--authorization',type=Path,required=True);args=parser.parse_args();ctx=recovery_context(args.authorization);module=original_numeric_module()
    ctx.output.mkdir(parents=False);(ctx.output/'Public').mkdir();(ctx.output/'Private').mkdir()
    try:audit_function(module,ctx)(ctx.recovery_go_path)
    except BaseException as error:
        module.save(ctx.output/'Public/development-recovery-audit-failure.json',dict(status='AUDIT_CLOSED_NO_FIT',utc=datetime.now(timezone.utc).isoformat(),adapter_source_sha256=sha(__file__),independent_numeric_source_sha256=ORIGINAL_AUDIT_SHA,error_type=type(error).__name__,error=str(error),original_Data_or_ML_written=False,no_models_fit=True,no_sealed_files_opened=True))
        raise

if __name__=='__main__':main()
