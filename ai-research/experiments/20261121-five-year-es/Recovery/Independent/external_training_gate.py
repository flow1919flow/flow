"""External post-incident fit entrypoint; frozen learning Source is untouched.

Default CLOSED. Verification binds original scientific bytes, complete recovery,
canonical release and independent raw-price acceptance. --fit additionally needs
explicit Root GO, published wrapper/fixtures, reviewed OS profile and no prior
fit marker. This module must never be used to recover or alter strategy outputs.
"""
from pathlib import Path
from collections import defaultdict,Counter
from datetime import datetime,timezone
import argparse,hashlib,json,os,re,subprocess,sys,time

RECOVERY=Path(__file__).resolve().parents[1]
DATA=RECOVERY.parent/'ES-FiveYear-SecondData-20261121'
LEARNING=RECOVERY.parent/'ES-FiveYear-ML-20261121'
WORKSPACE=RECOVERY.parents[1]
TRAINING_SHA='59426a4be09d9adceff489baebf1849a691e1bc5ff8ee32f3164330fd99646ba'
KNOWN_ORIGINAL={
 'Private/second-candidates-known.jsonl':'b021d522a869d69f8893232123420cba78181c9a2f6425bae3c6973e40a2c67a',
 'Private/second-candidates-known.csv':'163e2bb54c2539e4685e33624bdcd528eb6786fbeadb265fd68e82312766e715',
 'Private/second-known-price-roll-freeze.json':'234897b90557cb44eda32c7ce0d6756a60841980f6eccfbe6ccc9f582c257e9d',
 'Public/second-native-acceptance.json':'61ecb4431327aa4fb5994fc1d64ca765b82ea0f6e7bd09fa98566692e5b33f5f',
 'Public/second-independent-audit.json':'a1f071d15a1ce8eb5d1af4cca70b7b87d2f276a1a917c232e461a538740d609c',
 'Public/second-source-freeze-v2.json':'c3ddf25c74a0f9798a469c7401a3a67416018aa339d0a6746b162db5fc9d5c6a',
 'Source/second_kernel.py':'9a39d551d80a51a93d74b761ee253e340679d621344a42d06bc2aac3225cc9b2'}
INCIDENT_EXPECTED={
 'Private/second-candidates-known.jsonl':'e9ad3462256580794182a11520f05ce2e0296f609b2998e8ef72919a147145ce',
 'Private/second-candidates-known.csv':'432fa618624d0de557113b8efb4da68752008cc14f3d0395b89197d5239763c5',
 'Private/second-known-exclusions.json':'c12545840eea9c4d6e9e478f71ca9cb8e3b8b79468892a656d3bb40dade06dd9',
 'Private/second-known-ambiguities.json':'df03a3bda4a3a03919f0f4d19ad4680b6c00603dde3b30997175c952d815dd3c',
 'Private/second-known-feature-before-label-proof.json':'1071f17bef916db7dbcafd404ac7e10c6de872e0704d094d8c63fa382c069632'}
ALLOWED_UNAVAILABLE={'Public/second-execution-start.json','Public/second-preflight-progress.json'}
ROLE_RENAME={'candidates_jsonl':('Private/second-candidates-known.jsonl','Private/development-candidates.jsonl'),'candidates_csv':('Private/second-candidates-known.csv','Private/development-candidates.csv'),'exclusions_json':('Private/second-known-exclusions.json','Private/development-exclusions.json'),'ambiguities_json':('Private/second-known-ambiguities.json','Private/development-ambiguities.json'),'feature_proof_json':('Private/second-known-feature-before-label-proof.json','Private/development-feature-before-label-proof.json')}

def need(value,message):
    if not value:raise ValueError(message)
def sha(path):
    p=Path(path);need(p.is_file(),'Required artifact unavailable: '+str(p));return hashlib.sha256(p.read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def now():return datetime.now(timezone.utc).isoformat()
def save_new(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x')as f:f.write(json.dumps(value,indent=2,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
    fd=os.open(p.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return p

def bound(binding,expected=None,inside=None):
    need(isinstance(binding,dict),'Missing exact artifact binding');p=Path(binding.get('path','')).resolve()
    if expected is not None:need(p==Path(expected).resolve(),'Artifact points to the wrong namespace')
    if inside is not None:need(Path(inside).resolve()in p.parents,'Artifact escapes approved namespace')
    need(sha(p)==binding.get('sha256'),'Bound artifact missing/changed: '+str(p));return p

def original_integrity():
    """This catches the incident even when old metadata release_guard says PASS."""
    result={}
    for name,digest in KNOWN_ORIGINAL.items():need(sha(DATA/name)==digest,'ORIGINAL_KNOWN_SCIENTIFIC_FILE_MISMATCH: '+name);result[name]=digest
    frozen=read(DATA/'Public/second-source-freeze-v2.json')
    for name,digest in frozen['sources_sha256'].items():need(sha(DATA/'Source'/name)==digest,'Original native frozen Source changed: '+name)
    need(sha(DATA/'Public/second-fixtures.json')==frozen['fixtures_sha256'],'Original native fixture proof changed')
    acceptance=read(DATA/'Public/second-native-acceptance.json');audit=read(DATA/'Public/second-independent-audit.json')
    need(acceptance.get('accepted')is True and audit.get('acceptance_sha256')==KNOWN_ORIGINAL['Public/second-native-acceptance.json'],'Original native audit/acceptance disagree')
    need(sha(DATA/'Audit/independent.py')==audit.get('audit_source_sha256'),'Original independent native audit source changed')
    for month,digest in acceptance['sourcehashes']['month_manifest_sha256'].items():need(sha(DATA/'Private/Months'/month/'manifest.json')==digest,'Original known month manifest changed')
    return result

def artifact(proof,key,root):
    a=proof.get('artifacts',{}).get(key);need(isinstance(a,dict),'Recovery proof missing artifact: '+key)
    relative=a.get('path_relative_to_attempt','');need(not Path(relative).is_absolute(),'Recovery artifact must use relative path');p=(root/relative).resolve();need(root.resolve()in p.parents,'Recovery artifact escapes attempt')
    need(sha(p)==a.get('sha256'),'Recovered artifact changed: '+key);return p

def recovered_identity(known_binding,development_binding):
    kp=bound(known_binding,inside=RECOVERY/'Attempts');dp=bound(development_binding,inside=RECOVERY/'Attempts');known=read(kp);dev=read(dp)
    for p,role in [(known,'known'),(dev,'development')]:
        need(p.get('schema')=='es-deterministic-recovery-acceptance-v1'and p.get('status')=='EXACT_ORIGINAL_BYTE_AND_PLAN_MATCH'and p.get('role')==role,'Recovery is not exact/complete for '+role)
        need(p.get('no_selection_or_parameter_change')is True and p.get('no_sealed_access')is True and p.get('no_model_fit')is True,'Recovery changes/unauthorized access not excluded')
        unavailable=set(p.get('unavailable_original_ephemeral_metadata',[]));need(unavailable<=ALLOWED_UNAVAILABLE and p.get('original_timestamps_fabricated')is False,'Original ephemeral timestamps were fabricated or scientific metadata waived')
    root=dp.parent.parent;need(Path(dev.get('output_root','')).resolve()==root.resolve(),'Development proof output namespace mismatch')
    incident=DATA/'Private/Incidents/development-dispatch-path-20261121'
    for key,(incident_rel,canonical_rel)in ROLE_RENAME.items():
        expected=INCIDENT_EXPECTED[incident_rel];need(sha(incident/incident_rel)==expected,'Preserved incident artifact changed')
        need(sha(artifact(dev,key,root))==expected and sha(DATA/canonical_rel)==expected,'Recovered/promoted development bytes differ from failed attempt: '+key)
    plans_path=artifact(dev,'decision_plans_jsonl',root);plans=[json.loads(line)for line in plans_path.read_text().splitlines()if line];need(len(plans)==1145,'Expected exactly1145 original decision plans')
    need(len({p['case_key']for p in plans})==1145,'Duplicated recovered decision plan')
    forbidden={'label_status','entry_ns','exit_ns','entry_price','exit_price','stress_net_R','normal_net_usd','stress_net_usd'}
    need(not any(forbidden.intersection(p)for p in plans),'Decision plan journal contains future results')
    grouped=defaultdict(list)
    for p in plans:grouped[(p['contract'],p['day'])].append(p)
    original=read(incident/'Private/second-known-feature-before-label-proof.json');need(len(original)==775 and sum(p['feature_candidates']for p in original)==1145,'Original plan ledger changed')
    allowed={(p['contract'],p['day'])for p in original};need(set(grouped)<=allowed,'Recovered plans contain unregistered contract/day')
    for row in original:
        values=grouped[(row['contract'],row['day'])];need(len(values)==row['feature_candidates'],'Original per-day plan count differs')
        digest=hashlib.sha256(json.dumps(values,sort_keys=True,allow_nan=False).encode()).hexdigest();need(digest==row['features_before_labels_sha256'],'Original per-day complete plan hash differs')
    intents_path=artifact(dev,'intents_jsonl',root);intents=[json.loads(line)for line in intents_path.read_text().splitlines()if line];need(len(intents)==1145,'Incomplete recovered intent stream')
    need({p['case_key']for p in intents}=={p['case_key']for p in plans},'Intent identities differ from complete plans')
    filled=[e for e in intents if e['label_status']=='ok'];cancelled=[e for e in intents if e['label_status']=='excluded_delayed_entry_liquidation_proxy_beyond_stop']
    need(len(filled)==1143 and len(cancelled)==2 and all(e.get('economic_path_resolved')is True for e in intents),'Unexpected filled/cancelled/unresolved opportunity count')
    need(all(isinstance(e.get('entry_cancel_ns'),int)and e['entry_cancel_ns']>=e['signal_ns']for e in cancelled),'Cancellation clocks missing/invalid')
    need(dev.get('cancellation_clock_evidence')=='new_deterministic_recovery_evidence_not_original_capture','Recovered cancellation clocks falsely described as originally captured')
    return dict(known_proof_sha256=sha(kp),development_proof_sha256=sha(dp),development_recovery_go_sha256=dev.get('root_go_sha256'),decision_plan_days=775,decision_plans=1145,filled_cases=1143,resolved_entry_cancellations=2,intents_path=str(intents_path),intents_sha256=sha(intents_path),release_path=str(artifact(dev,'role_release_json',root)),release_sha256=sha(artifact(dev,'role_release_json',root)))

def isolation_guard(go):
    np=bound(go.get('namespace_acceptance'),expected=RECOVERY/'Public/namespace-synthetic-acceptance.json');n=read(np)
    need(n.get('status')=='PASS_FULL_GENERATED_FUNCTION_SYNTHETIC_IO'and n.get('checks_passed',0)>=11,'End-to-end I/O acceptance missing')
    for key in ['all_three_roles_exercised','old_broken_mapping_negative_control_caught_all_roles','intents_durable_before_packaging_failure','per_day_complete_plan_hash_verified']:need(n.get(key)is True,'Namespace acceptance missing: '+key)
    for name,digest in n['sources_sha256'].items():need(sha(RECOVERY/'Source'/name)==digest,'Reviewed namespace source changed')
    op=bound(go.get('OS_acceptance'),expected=RECOVERY/'OSProbe/output/result-syscalls-v2.json');o=read(op)
    need(o.get('status')=='PASS_OS_READONLY_OPEN_TRUNCATE_UNLINK_RENAME'and o.get('allowed_output_create_append_rename_unlink')is True,'OS I/O protection acceptance missing')
    need(all(o['denials'].get(k,{}).get('OS_denied')is True and o['denials'][k].get('errno')==1 for k in ['open_truncate','unlink','rename_out_of_input']),'OS protection negative controls failed')
    return dict(namespace_acceptance_sha256=sha(np),OS_acceptance_sha256=sha(op))

def verify(go_path):
    go=read(go_path);need(go.get('authorized')is True and go.get('mode')=='fit-development-after-exact-recovery','Explicit reviewed Root fit GO required')
    need(go.get('gate_source_sha256')==sha(__file__),'Root GO binds another gate source')
    fp=RECOVERY/'Public/external-training-gate-synthetic-acceptance.json';f=read(fp)
    need(f.get('status')=='PASS'and f.get('synthetic_only')is True and f.get('gate_source_sha256')==sha(__file__)and go.get('gate_fixtures_sha256')==sha(fp),'Gate fixtures not bound to current source')
    pp=bound(go.get('gate_publication'),expected=RECOVERY/'Public/external-training-gate-github-receipt.json');pub=read(pp)
    need(pub.get('published')is True and pub.get('published_before_fit')is True and pub.get('gate_source_sha256')==sha(__file__)and pub.get('fixtures_sha256')==sha(fp),'Gate source/fixtures not published before fit')
    need(re.fullmatch('[0-9a-f]{40}',str(pub.get('publication_commit','')))is not None,'Gate publication lacks exact commit')
    need(not(RECOVERY/'Private/external-fit-launch-attempt.json').exists(),'Prior external fit launch exists; no automatic retry')
    originals=original_integrity();isolation=isolation_guard(go);identity=recovered_identity(go.get('known_recovery_acceptance'),go.get('development_recovery_acceptance'))
    rp=bound(go.get('canonical_role_release'),expected=DATA/'Private/development-release.json');release=read(rp)
    need(sha(rp)==identity['release_sha256'],'Promoted role manifest differs from isolated recovered release')
    need(release.get('role')=='development'and release.get('schema')=='es-frozen-second-role-release-v1'and release.get('row_count')==1143 and release.get('intent_row_count')==1145 and release.get('unresolved_intent_count')==0,'Canonical role release incomplete')
    need(sha(DATA/'Private/development-candidates.csv')==release['csv_sha256']==INCIDENT_EXPECTED['Private/second-candidates-known.csv'],'Canonical development CSV changed')
    need(sha(DATA/'Private/development-intents.jsonl')==release['intent_jsonl_sha256']==identity['intents_sha256'],'Canonical complete intent stream changed')
    need(sha(DATA/'Private/development-intents.csv')==release['intent_csv_sha256'],'Canonical human intent CSV changed')
    ap=bound(go.get('development_allrow_audit'),inside=RECOVERY/'AuditRuns');need(ap.name=='development-independent-acceptance.json','Wrong recovery-specific all-row proof filename');audit=read(ap)
    need(audit.get('status')=='PASS_INDEPENDENT_DEVELOPMENT_RAW_PRICE_FEATURE_FILL_AND_BASELINE_AUDIT','Independent all-row raw-price audit unavailable')
    need(audit.get('cases_verified')==1143 and audit.get('decision_intents_verified')==1145 and audit.get('cancelled_intents_verified')==2 and audit.get('unresolved_intent_clocks')==0,'All-row audit did not verify every recovered opportunity')
    for key in ['all_five_features_independently_reconstructed','all_entry_cancel_exit_proxy_clocks_verified','all_costs_and_R_verified','all_unique_economic_opportunities','complete_intent_ungated_baseline_parity','no_model_fits','no_sealed_files_opened']:need(audit.get(key)is True,'Required independent scientific check missing: '+key)
    need(audit.get('development_release_sha256')==sha(rp)and audit.get('candidate_jsonl_sha256')==INCIDENT_EXPECTED['Private/second-candidates-known.jsonl'],'All-row audit binds another dataset')
    source=RECOVERY/'Independent/audit_development_recovery_release.py';need(audit.get('independent_source_sha256')==sha(source)==audit.get('independent_authorization_adapter_sha256'),'Recovery audit authorization adapter changed')
    numeric=LEARNING/'Audit/audit_development_release.py';need(audit.get('independent_numeric_source_sha256')==sha(numeric)=='cfe4d8f21b545097feca330ff69a459370e8e0bf13b1b0949c7b7df236011aa9','Independent numeric audit source changed')
    need(audit.get('authorization_mode')=='development_recovery'and audit.get('recovery_authorship_preserved')is True,'Recovery audit authorship was misrepresented')
    need(audit.get('original_scientific_go_sha256')=='5b67d2e4501c83234cdda16679c0bbb843fa6d8f6e0fa96080c0ee19565f3597'and audit.get('recovery_go_sha256')==identity['development_recovery_go_sha256'],'Original scientific and actual recovery GO do not match audit')
    need(audit.get('recovery_acceptance_sha256')==identity['development_proof_sha256']and audit.get('development_completion_sha256')==identity['development_proof_sha256'],'Audit must bind real recovery acceptance, not fabricated old completion')
    training=LEARNING/'Source/train_fiveyear.py';need(sha(training)==TRAINING_SHA,'Frozen learning code changed')
    tp=LEARNING/'Public/training-code-github-receipt.json';oldpub=read(tp);need(oldpub.get('published')is True and oldpub.get('published_before_fit')is True and oldpub.get('source_sha256')==TRAINING_SHA,'Original training source publication invalid')
    need(oldpub.get('training_code_freeze_sha256')==sha(LEARNING/'Public/training-code-freeze.json'),'Original training freeze changed')
    need(not(LEARNING/'Public/models-frozen.json').exists()and not(LEARNING/'Private/training-attempt.json').exists()and not(LEARNING/'Private/final-evaluation-attempt.json').exists(),'A previous fit/final attempt already exists')
    return dict(schema='EXTERNAL-POSTINCIDENT-FIT-INTEGRITY-1',status='PASS_ALL_SCIENTIFIC_BYTES_RECOVERY_AND_ALLROW_AUDIT',utc=now(),root_go_sha256=sha(go_path),gate_source_sha256=sha(__file__),gate_fixtures_sha256=sha(fp),gate_publication_sha256=sha(pp),gate_publication_commit=pub['publication_commit'],known_original_scientific_hashes=originals,recovery_identity=identity,isolation=isolation,canonical_release_sha256=sha(rp),development_allrow_audit_sha256=sha(ap),training_source_sha256=TRAINING_SHA,training_source_publication_sha256=sha(tp),development_csv_sha256=release['csv_sha256'],development_intents_sha256=release['intent_jsonl_sha256'],cancel_clocks_are_new_recovery_evidence=True,known_year_model_performance_test=False,no_outcome_based_selection=True,sealed_files_opened=False,models_fit_by_gate=False)

def launch(go_path):
    """Only after a reviewed and published Root GO; never called by fixtures."""
    proof=verify(go_path);go=read(go_path);need(sha(go_path)==proof['root_go_sha256'],'Root GO changed during gate verification');need(go.get('execute_fit')is True,'Verification only; actual fit not authorized')
    profile=bound(go.get('fit_OS_profile'),inside=RECOVERY/'OSProbe');need(go.get('fit_OS_profile_reviewed')is True,'Fit OS profile not reviewed')
    receipt=RECOVERY/'Private/external-fit-integrity-receipt.json';save_new(receipt,proof)
    marker=RECOVERY/'Private/external-fit-launch-attempt.json';save_new(marker,dict(utc=now(),receipt_sha256=sha(receipt),root_go_sha256=sha(go_path),no_automatic_retry=True))
    python=WORKSPACE/'work/tools/mlflow/.venv/bin/python';script=LEARNING/'Source/train_fiveyear.py';args=['/usr/bin/sandbox-exec','-f',str(profile),str(python),str(script),'fit','--input',str(DATA/'Private/development-candidates.csv')]
    result=subprocess.run(args,check=False,env=dict(os.environ,LOKY_MAX_CPU_COUNT='1',DO_NOT_TRACK='1',MLFLOW_DISABLE_AGENT_HINT='1'))
    sidecar=dict(schema='MODELS-EXTERNAL-INTEGRITY-BINDING-1',utc=now(),gate_receipt_sha256=sha(receipt),root_go_sha256=sha(go_path),gate_source_sha256=sha(__file__),training_source_sha256=TRAINING_SHA,process_exit_code=result.returncode,known_year_model_performance_test=False,sealed_files_opened=False)
    if result.returncode==0 and(LEARNING/'Public/models-frozen.json').exists():
        model=read(LEARNING/'Public/models-frozen.json');need(model['source_sha256']==TRAINING_SHA and model['development_csv_sha256']==proof['development_csv_sha256']and model['development_intents_sha256']==proof['development_intents_sha256'],'Fitted models bind other inputs')
        sidecar.update(state='FIT_COMPLETE_MODELS_BOUND_TO_PASSED_EXTERNAL_GATE',models_frozen_sha256=sha(LEARNING/'Public/models-frozen.json'))
    elif result.returncode==0 and(LEARNING/'Public/futility-stop.json').exists():sidecar.update(state='DEVELOPMENT_FUTILITY_NO_FINAL_UNSEAL',futility_sha256=sha(LEARNING/'Public/futility-stop.json'))
    else:sidecar.update(state='FIT_FAILED_ATTEMPT_CONSUMED_NO_RETRY')
    save_new(LEARNING/'Public/models-external-integrity.json',sidecar);need(result.returncode==0,'Fitting failed; preserve attempt and do not retry automatically');return sidecar

def main():
    p=argparse.ArgumentParser();p.add_argument('--go',type=Path,required=True);p.add_argument('--fit',action='store_true');a=p.parse_args();result=launch(a.go)if a.fit else verify(a.go);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
