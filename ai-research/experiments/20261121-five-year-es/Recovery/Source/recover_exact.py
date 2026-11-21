"""Guarded deterministic restoration CLI; no promotion or new scientific test.

BUILD ONLY until a hash-bound, published Root GO authorizes a concrete attempt.
Real execution MUST be inside the supplied restrictive sandbox-exec profile.
"""
from pathlib import Path
from collections import defaultdict
import argparse,copy,hashlib,json,os,sys,time,importlib.metadata,traceback
from contextlib import redirect_stdout,redirect_stderr
import namespace_prototype as prototype
from price_extract_support import sha,save,utcnow,Calendar,CT,NS

RECOVERY=prototype.RECOVERY;DATA=prototype.TASK
ML=DATA.parent/'ES-FiveYear-ML-20261121'
INCIDENT=DATA/'Private/Incidents/development-dispatch-path-20261121'
KNOWN_EXPECTED={'candidates_jsonl':'b021d522a869d69f8893232123420cba78181c9a2f6425bae3c6973e40a2c67a','candidates_csv':'163e2bb54c2539e4685e33624bdcd528eb6786fbeadb265fd68e82312766e715','schedule_json':'234897b90557cb44eda32c7ce0d6756a60841980f6eccfbe6ccc9f582c257e9d'}
KNOWN_PUBLISHED_SHA='6121214e8a36f0a67e643046609276fec7d76e502797bd401ae598b25d8640bf'
REQUIRED_BINDINGS={'source_freeze','incident_manifest','incident_public_report','recovery_criteria','known_published_summary','native_acceptance','native_independent_audit','development_price_audit','development_price_root_review','namespace_acceptance','OS_acceptance','OS_profile','protocol_main','protocol_addendum','protocol_native'}
SOURCE_DIR=Path(__file__).parent
EXPECTED_ENV={'python':'3.12.14','numpy':'2.5.4','pandas':'3.1.1','scipy':'1.18.1','pyarrow':'26.0.1','databento':'0.90.0'}


def require(value,message):
    if not value:raise ValueError(message)


def verify_OS_enforcement():
    """Real OS denial required; this canary never names protected original data."""
    path=RECOVERY/'OSProbe/input'/f'production-denial-{os.getpid()}-{time.time_ns()}.canary'
    try:descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except PermissionError as error:
        require(error.errno in [1,13],'Unexpected OS denial');return dict(OS_denied=True,errno=error.errno,canary_parent=str(path.parent))
    else:
        os.close(descriptor)
        raise ValueError('STOP: restrictive OS profile is NOT applied; no market read permitted. Synthetic canary retained.')


def verify_go(mode,receipt):
    actual=dict(python=sys.version.split()[0],**{p:importlib.metadata.version(p) for p in EXPECTED_ENV if p!='python'})
    require(actual==EXPECTED_ENV,'Exact original research_runtime environment required for byte proof')
    receipt=Path(receipt).resolve();go=json.loads(receipt.read_text())
    require(go.get('authorized') is True and go.get('mode')==mode,'Explicit mode-matching ROOT RECOVERY GO required')
    require(go.get('published_before_recovery') is True and len(go.get('publication_commit',''))==40,'Published incident/criteria/source proof required before recovery')
    bindings=go.get('bindings',{});require(REQUIRED_BINDINGS<=set(bindings),'Missing mandatory recovery evidence bindings')
    for name,b in bindings.items():require(sha(b['path'])==b['sha256'],'Changed recovery binding: '+name)
    require(sha(bindings['known_published_summary']['path'])==KNOWN_PUBLISHED_SHA,'Known summary must be authentic published bytes')
    require(json.loads(Path(bindings['namespace_acceptance']['path']).read_text())['status']=='PASS_FULL_GENERATED_FUNCTION_SYNTHETIC_IO','Namespace integration proof missing')
    require(json.loads(Path(bindings['OS_acceptance']['path']).read_text())['status']=='PASS_OS_READONLY_OPEN_TRUNCATE_UNLINK_RENAME','OS syscall proof missing')
    freeze=json.loads(Path(bindings['source_freeze']['path']).read_text())
    for name,expected in freeze['sources_sha256'].items():require(sha(SOURCE_DIR/name)==expected,'Changed production recovery source: '+name)
    for relative,expected in freeze.get('public_files_sha256',{}).items():require(sha(RECOVERY/relative)==expected,'Changed published recovery proof: '+relative)
    prototype.frozen.verify_known_immutable()
    original=json.loads((DATA/'Public/period-source-freeze.json').read_text())
    prototype.frozen.known.verify_frozen_sources(original,DATA/'Source',DATA/'Public/period-fixtures.json')
    # All preserved incident bytes verified BEFORE any market read, never repaired.
    incident=json.loads(Path(bindings['incident_manifest']['path']).read_text())
    for name,proof in incident['files'].items():require(sha(INCIDENT/name)==proof['sha256'],'Preserved incident preimage changed: '+name)
    criteria=json.loads(Path(bindings['recovery_criteria']['path']).read_text())
    require(criteria.get('published_incident_source_sha256')==bindings['incident_public_report']['sha256'],'Machine criteria do not bind published incident bytes')
    public_incident=json.loads(Path(bindings['incident_public_report']['path']).read_text())
    require(all(public_incident['incident_files'][name]['sha256']==value['sha256'] for name,value in incident['files'].items()),'Private incident does not match published incident fingerprints')
    forbidden=['sealed-candidates.csv','sealed-candidates.jsonl','sealed-intents.csv','sealed-intents.jsonl','sealed-label-attempt.json','sealed-release.json']
    require(not any((DATA/'Private'/name).exists() for name in forbidden),'STOP: sealed label/intent/attempt evidence exists')
    require(criteria.get('known_core_expected_sha256')==KNOWN_EXPECTED,'Published known criteria differ from genuine original digests')
    require(criteria.get('development_expected_filled_cases')==1143 and criteria.get('development_expected_plan_days')==775 and criteria.get('development_expected_decision_plans')==1145 and criteria.get('development_expected_resolved_entry_cancellations')==2,'Published complete-opportunity criteria mismatch')
    out=Path(go['output_root']).resolve();attempts=(RECOVERY/'Attempts').resolve()
    require(attempts in out.parents and not out.exists(),'Require a fresh nonexistent attempt beneath separate RecoveryRoot/Attempts')
    require(mode.split('-')[0] in out.name,'Attempt namespace must name its role')
    require(go.get('os_profile_enforced') is True,'OS enforcement declaration required')
    profile=Path(bindings['OS_profile']['path']).read_text()
    require('(deny file-write*)' in profile and '(deny network*)' in profile,'OS profile must deny network and outside writes')
    # This exact profile text permits ONLY this concrete attempt, not RecoveryRoot.
    expected_profile='(version 1)\n(allow default)\n(deny file-write*)\n(allow file-write* (subpath '+json.dumps(str(out))+'))\n(deny network*)\n'
    require(profile==expected_profile,'OS write scope differs from exact attempt output root')
    return go,incident,original


class RecoveryGuard(prototype.Guard):
    def __init__(self,input_root,output_root,role,receipt,go):
        # GO/evidence paths are immutable extra read-only files, never write scopes.
        self.readonly={str(Path(b['path']).resolve()):b['sha256'] for b in go['bindings'].values()}
        self.readonly[str(Path(receipt).resolve())]=sha(receipt)
        super().__init__(input_root,output_root,role)
        self.targets.update(['Public/recovery-acceptance.json','Public/recovery-execution.json','Public/original-metadata-unavailable.json'])
        self.allowed=self.targets|{p+'.tmp' for p in self.targets}
        self.ml_preimages={str(p.relative_to(ML)):sha(p) for p in ML.rglob('*') if p.is_file()}

    def sha(self,path):
        resolved=str(Path(path).resolve())
        if resolved in self.readonly:
            actual=sha(resolved);require(actual==self.readonly[resolved],'Read-only recovery evidence changed');self.hashes.append(resolved);return actual
        return super().sha(path)

    def __exit__(self,*args):
        super().__exit__(*args)
        after={str(p.relative_to(ML)):sha(p) for p in ML.rglob('*') if p.is_file()}
        require(after==self.ml_preimages,'Protected ML root changed during recovery')


def verify_complete_plans(plans,proof_path):
    proof=json.loads(Path(proof_path).read_text());groups=defaultdict(list)
    for plan in plans:groups[(plan['contract'],plan['day'])].append(plan)
    require(len(proof)==775 and sum(r['feature_candidates'] for r in proof)==1145,'Original full plan proof count mismatch')
    for row in proof:
        values=groups.pop((row['contract'],row['day']),[])
        require(len(values)==row['feature_candidates'],'Changed decision-plan day count')
        require(hashlib.sha256(json.dumps(values,sort_keys=True,allow_nan=False).encode()).hexdigest()==row['features_before_labels_sha256'],'Changed complete pre-label decision plan hash')
    require(not groups and len(plans)==1145,'Unregistered decision-plan group')


def package_recovery(guard,cases,binding,go,incident,algorithm_freeze,receipt):
    role=guard.role;root=guard.output
    artifact_names={'candidates_jsonl':f'Private/{role}-candidates.jsonl','candidates_csv':f'Private/{role}-candidates.csv','schedule_json':f'Private/{role}-price-roll-freeze.json','decision_plans_jsonl':f'Private/{role}-intents-plan-journal.jsonl','intents_jsonl':f'Private/{role}-intents.jsonl','exclusions_json':f'Private/{role}-exclusions.json','ambiguities_json':f'Private/{role}-ambiguities.json','feature_proof_json':f'Private/{role}-feature-before-label-proof.json'}
    actual={name:guard.sha(root/path) for name,path in artifact_names.items()}
    if role=='known':
        for name,expected in KNOWN_EXPECTED.items():require(actual[name]==expected,'STOP: known core artifact not byte-identical: '+name)
        require(len(cases)==348,'Known filled count changed')
    else:
        expected_names={'candidates_jsonl':'Private/second-candidates-known.jsonl','candidates_csv':'Private/second-candidates-known.csv','exclusions_json':'Private/second-known-exclusions.json','ambiguities_json':'Private/second-known-ambiguities.json','feature_proof_json':'Private/second-known-feature-before-label-proof.json'}
        for name,old in expected_names.items():require(actual[name]==incident['files'][old]['sha256'],'STOP: development artifact not byte-identical: '+name)
        require(len(cases)==1143,'Development filled count changed')
        saved_plans=[json.loads(line) for line in (root/artifact_names['decision_plans_jsonl']).read_text().splitlines()]
        require(saved_plans==guard.plans,'Durable plan journal differs from observed plans')
        verify_complete_plans(saved_plans,INCIDENT/'Private/second-known-feature-before-label-proof.json')
        cancels=[x for x in guard.intents if x['label_status']!='ok']
        require(len(cancels)==2 and all(isinstance(x.get('entry_cancel_ns'),int) and x['economic_path_resolved'] for x in cancels),'Complete resolved entry-cancellation stream mismatch')
    lo,hi=prototype.frozen.PERIODS[role] if role!='known' else ('2025-11-24','2026-10-31')
    require(all(lo<=c['day']<hi for c in cases),'Role output escaped frozen window')
    require(len(guard.plans)==len(guard.intents) and {x['successful_case_key'] for x in guard.intents if x['label_status']=='ok'}=={c['case_key'] for c in cases},'Incomplete opportunity journal')
    intents_csv=root/f'Private/{role}-intents.csv';prototype.pd.DataFrame(guard.intents).to_csv(intents_csv,index=False)
    days=[c['day'] for c in cases]
    release=dict(schema='es-frozen-second-role-release-v1',role=role,csv_name=f'{role}-candidates.csv',csv_sha256=actual['candidates_csv'],row_count=len(cases),day_min=min(days),day_max=max(days),period_start_inclusive=lo,period_end_exclusive=hi,native_acceptance_sha256=prototype.frozen.KNOWN_ACCEPTANCE_SHA,independent_native_audit_sha256=prototype.frozen.KNOWN_AUDIT_SHA,known_source_freeze_sha256=prototype.frozen.KNOWN_FREEZE_SHA,protocol_sha256='498b90431dfeef1f65b8aea232cdff7e9ca2a44153131a5b8c8faeba36b813fa',generator_source_hashes=algorithm_freeze['sources_sha256'],generator_source_freeze_sha256='3234ca42565168097578e5af8cc6e581e86adc16472d20983fe1f890acec1681',algorithm_provenance_note='Original frozen strategy/math input provenance; broken original I/O dispatcher was NOT used unchanged. Separate recovery control plane supplies isolated validated path mapping.',protocol_files=[go['bindings'][k] for k in ['protocol_main','protocol_addendum','protocol_native']],kernel_sha256=sha(DATA/'Source/second_kernel.py'),intent_semantics='EveryeligibledecisionplanpersistedBEFORElabel;resolvedintentsincludeexactentry_cancel_ns;canonicalJSONLinteger/nullclocks;humanCSVseparatelyhashed',intent_csv_name=intents_csv.name,intent_csv_sha256=guard.sha(intents_csv),intent_jsonl_sha256=actual['intents_jsonl'],intent_row_count=len(guard.intents),unresolved_intent_count=sum(not x['economic_path_resolved'] for x in guard.intents),released_utc=utcnow(),root_go_sha256=guard.sha(receipt),recovery_source_freeze_sha256=go['bindings']['source_freeze']['sha256'],recovery_OS_profile_sha256=go['bindings']['OS_profile']['sha256'],recovery_control_source_hashes={p.name:sha(p) for p in SOURCE_DIR.glob('*.py')},no_model_fit_by_recovery=True)
    guard.save(root/f'Private/{role}-release.json',release)
    artifact_names.update(intents_csv=f'Private/{role}-intents.csv',role_release_json=f'Private/{role}-release.json')
    artifacts={name:dict(path_relative_to_attempt=path,sha256=guard.sha(root/path)) for name,path in artifact_names.items()}
    record=dict(schema='es-deterministic-recovery-acceptance-v1',status='PENDING_IMMUTABLE_INPUT_POSTCHECK',role=role,output_root=str(root),utc=utcnow(),filled_cases=len(cases),decision_plans=len(guard.plans),plan_days=len(json.loads((root/artifact_names['feature_proof_json']).read_text())),resolved_entry_cancellations=sum(x['label_status']!='ok' and x.get('entry_cancel_ns') is not None for x in guard.intents),artifacts=artifacts,known_core_expected_sha256=KNOWN_EXPECTED,bindings=go['bindings'],root_go_sha256=guard.sha(receipt),immutable_input_preimages_sha256=hashlib.sha256(json.dumps(guard.preimages,sort_keys=True).encode()).hexdigest(),original_ML_preimages_sha256=hashlib.sha256(json.dumps(guard.ml_preimages,sort_keys=True).encode()).hexdigest(),algorithm_mathematics_unchanged=True,output_namespace_isolated=True,no_promotion_to_originals=True,no_new_scientific_acceptance_calculation=True,no_models_fit=True,no_model_fit=True,no_selection_or_parameter_change=True,no_sealed_access=True,no_sealed_access_scope='No sealed labels/intents/metrics; price-only bytes/warmup remain permitted',original_timestamps_fabricated=False,unavailable_original_files=['Public/second-execution-start.json','Public/second-preflight-progress.json'],unavailable_original_ephemeral_metadata=['Public/second-execution-start.json','Public/second-preflight-progress.json'],cancellation_clock_evidence='new_deterministic_recovery_evidence_not_original_capture',all_row_independent_raw_price_audit_still_required=True,environment=EXPECTED_ENV)
    guard.save(root/'Public/recovery-acceptance.json',record)
    return dict(status='PENDING_IMMUTABLE_INPUT_POSTCHECK')


def run(mode,receipt):
    go,incident,algorithm=verify_go(mode,receipt);role=mode.split('-')[0]
    OS_proof=verify_OS_enforcement() # Kernel-level denial before market reads.
    guard=RecoveryGuard(DATA,Path(go['output_root']),role,receipt,go)
    with guard:
        with (guard.output/'run.log').open('x') as run_log, redirect_stdout(run_log), redirect_stderr(run_log):
            guard.save(guard.output/'Public/recovery-execution.json',dict(utc=utcnow(),role=role,mode=mode,receipt_sha256=guard.sha(receipt),purpose='Deterministic exact-byte restoration only; no new scientific attempt or performance analysis',output_root=str(guard.output),OS_enforcement=OS_proof))
            try:
                # All manifests/shards and causal calendar/roll checked before signals.
                months,schedule=prototype.frozen.known.known_sources() if role=='known' else prototype.frozen.period_sources('development')
                environment=dict(vars(prototype.frozen.known))
                original_source_freeze=DATA/'Public/second-source-freeze-v2.json' if role=='known' else DATA/'Public/period-source-freeze.json'
                def authorize(path):
                    guard.save(guard.output/f'Private/{role}-attempt.json',dict(utc=utcnow(),root_go_sha256=guard.sha(receipt),recovery_source_freeze_sha256=go['bindings']['source_freeze']['sha256']))
                    return dict(source_freeze_path=str(original_source_freeze))
                environment.update(HERE=guard.output,INPUT_ROOT=DATA,KNOWN_MONTHS=list(months),__file__=str(DATA/'Source/second_run.py'),authorize=authorize,known_sources=lambda:(months,schedule),sha=guard.sha,save=guard.save,delayed_shadow=guard.capture(prototype.frozen.known.delayed_shadow),acceptance=lambda cases,binding:package_recovery(guard,cases,binding,go,incident,algorithm,receipt))
                code=prototype.corrected_engine(role)
                exec(compile(code,'FROZEN_ALGORITHM_ISOLATED_RECOVERY','exec'),environment)
                environment['run_period'](receipt)
            except Exception as error:
                guard.save(guard.output/f'Public/{role}-failed-attempt.json',dict(utc=utcnow(),status='STOP_NO_RETRY_NO_VERSION_CHOICE',error_type=type(error).__name__,error=str(error)));traceback.print_exc();raise
    # Only after BOTH immutable original-root postchecks can acceptance be final.
    guard.active=True
    try:
        target=guard.output/'Public/recovery-acceptance.json';record=json.loads(target.read_text())
        require(record['status']=='PENDING_IMMUTABLE_INPUT_POSTCHECK','Unexpected acceptance staging state')
        record.update(status='EXACT_ORIGINAL_BYTE_AND_PLAN_MATCH',immutable_original_Data_root_postcheck_passed=True,immutable_original_ML_root_postcheck_passed=True,finalized_utc=utcnow())
        guard.save(target,record)
    finally:guard.active=False


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['known-recovery','development-recovery']);parser.add_argument('--receipt',type=Path,required=True);args=parser.parse_args();run(args.mode,args.receipt)
