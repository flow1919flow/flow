"""Gated exact-byte canonical publisher; no broad copy/delete or legacy completion.

Actual invocation requires separately published source, a concrete plan and Root
GO. Synthetic tests use only temporary original/attempt trees.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,os,sys
import plan_canonical as planner

RECOVERY=planner.RECOVERY;DATA=planner.DATA;INCIDENT=planner.INCIDENT
KNOWN_MAP={'candidates_jsonl':'Private/second-candidates-known.jsonl','candidates_csv':'Private/second-candidates-known.csv','schedule_json':'Private/second-known-price-roll-freeze.json','exclusions_json':'Private/second-known-exclusions.json','ambiguities_json':'Private/second-known-ambiguities.json','feature_proof_json':'Private/second-known-feature-before-label-proof.json'}
DEV_MAP={k:'Private/development-'+v for k,v in {'schedule_json':'price-roll-freeze.json','candidates_jsonl':'candidates.jsonl','candidates_csv':'candidates.csv','intents_jsonl':'intents.jsonl','intents_csv':'intents.csv','decision_plans_jsonl':'intents-plan-journal.jsonl','role_release_json':'release.json','exclusions_json':'exclusions.json','ambiguities_json':'ambiguities.json','feature_proof_json':'feature-before-label-proof.json'}.items()}
SUMMARY='Public/second-known-summary.json'
POINTERS=['Public/second-execution-start.json','Public/second-preflight-progress.json']
PROVENANCE='Public/second-known-summary.restoration-receipt.json'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def stamp():return datetime.now(timezone.utc).isoformat()
def require(value,message):
    if not value:raise ValueError(message)


class WriteGuard:
    def __init__(self,allowed):self.allowed={str(Path(p).resolve()) for p in allowed};self.active=False;self.events=[];sys.addaudithook(self.hook)
    def check(self,path):
        if isinstance(path,int):return
        path=str(Path(path).resolve());require(path in self.allowed,'Forbidden canonical write path: '+path);self.events.append(path)
    def hook(self,event,args):
        if not self.active:return
        if event=='open':
            path,mode,flags=args
            if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):self.check(path)
        elif event in ['os.rename','os.replace']:self.check(args[0]);self.check(args[1])
        elif event in ['os.remove','os.rmdir','os.mkdir','os.truncate']:raise ValueError('Deletion/directory mutation forbidden during canonical apply')


def sync_parent(path):
    fd=os.open(Path(path).parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)


def write_atomic(path,body):
    path=Path(path);temporary=path.with_name(path.name+'.canonical-promotion.tmp')
    with temporary.open('xb') as stream:stream.write(body);stream.flush();os.fsync(stream.fileno())
    require(sha(temporary)==hashlib.sha256(body).hexdigest(),'Atomic staging hash mismatch')
    os.replace(temporary,path);sync_parent(path)
    require(sha(path)==hashlib.sha256(body).hexdigest(),'Canonical posthash mismatch')


def check_acceptance(attempt,role,expected):
    attempt=Path(attempt).resolve();require((RECOVERY/'Attempts').resolve() in attempt.parents,'Source attempt outside accepted namespace')
    receipt=attempt/'Public/recovery-acceptance.json';require(sha(receipt)==expected,'Changed actual recovery receipt')
    r=json.loads(receipt.read_text());require(r['role']==role and r['status']=='EXACT_ORIGINAL_BYTE_AND_PLAN_MATCH','Both actual recovery PASS records required')
    require(r['immutable_original_Data_root_postcheck_passed'] and r['immutable_original_ML_root_postcheck_passed'],'Original-root postchecks missing')
    require(r['no_model_fit'] and r['no_sealed_access'] and r['no_selection_or_parameter_change'],'Changed scientific recovery scope')
    for artifact in r['artifacts'].values():
        source=(attempt/artifact['path_relative_to_attempt']).resolve();require(attempt in source.parents and sha(source)==artifact['sha256'],'Source artifact escaped/changed')
    return attempt,r


def preflight(plan,go):
    known,k=check_acceptance(go['known_attempt'],'known',plan['known_acceptance_sha256'])
    dev,d=check_acceptance(go['development_attempt'],'development',plan['development_acceptance_sha256'])
    require(k['filled_cases']==348 and d['filled_cases']==1143 and d['decision_plans']==1145 and d['plan_days']==775 and d['resolved_entry_cancellations']==2,'Canonical opportunity identity mismatch')
    incident_path=INCIDENT/'incident-files.json';require(sha(incident_path)==go['incident_manifest_sha256'],'Incident manifest changed')
    original=json.loads(incident_path.read_text())['files']
    for name,value in original.items():require(sha(INCIDENT/name)==value['sha256'],'Protected incident byte changed')
    require(sha(DATA/'Private/development-label-attempt.json')==original['Private/development-label-attempt.json']['sha256'],'Original failed attempt marker changed')
    for directory in ['Private','Public']:require((DATA/directory).resolve()==DATA.resolve()/directory,'Canonical parent symlink forbidden')
    expected={}
    for role,attempt,record,mapping in [('known',known,k,KNOWN_MAP),('development',dev,d,DEV_MAP)]:
        for key,destination in mapping.items():
            value=record['artifacts'][key];source=(attempt/value['path_relative_to_attempt']).resolve()
            expected[destination]=(source,value['sha256'])
    for name,digest in planner.CORE.items():require(k['artifacts'][name]['sha256']==digest,'Known original core fingerprint mismatch')
    require(d['artifacts']['schedule_json']['sha256']==original['Private/second-known-price-roll-freeze.json']['sha256'],'Original development schedule mismatch')
    summary=(RECOVERY/'OriginalPublished/Public/second-known-summary.json').resolve();require(sha(summary)==planner.SUMMARY_SHA,'Authentic original summary changed')
    expected[SUMMARY]=(summary,planner.SUMMARY_SHA)
    operations=plan['operations'];require(len(operations)==len(expected) and len({r['destination'] for r in operations})==len(operations),'Non-exhaustive/duplicate canonical map')
    mapped={}
    for op in operations:
        destination=Path(op['destination']);require(not destination.is_symlink(),'Canonical target symlink forbidden')
        relative=str(destination.resolve().relative_to(DATA.resolve()))
        require(relative in expected,'Source/Raw/Incident/unlisted canonical target forbidden')
        source,digest=expected[relative]
        require(Path(op['source']).resolve()==source and op['source_sha256']==digest and sha(source)==digest,'Plan source differs from accepted concrete artifact')
        before=original.get(relative,{}).get('sha256')
        require(op['current_destination_sha256']==before,'Plan preimage differs from preserved incident')
        if before:require(destination.exists() and sha(destination)==before,'Current canonical preimage changed')
        else:require(not destination.exists(),'Unexpected existing new development target')
        mapped[relative]=dict(source=source,body=None,after=digest,before=before)
    require(set(mapped)==set(expected),'Canonical path set changed')
    for relative in POINTERS:
        require(sha(DATA/relative)==original[relative]['sha256'],'Stale metadata preimage changed')
        payload=dict(status='ORIGINAL_KNOWN_EPHEMERAL_METADATA_UNAVAILABLE',this_is_a_restoration_pointer_not_original_status=True,original_filename=relative,original_timestamp_not_fabricated=True,preserved_wrong_role_preimage_sha256=original[relative]['sha256'],incident_copy=str(INCIDENT/relative),known_recovery_receipt_sha256=plan['known_acceptance_sha256'])
        body=(json.dumps(payload,indent=2)+'\n').encode();mapped[relative]=dict(source=None,body=body,after=hashlib.sha256(body).hexdigest(),before=original[relative]['sha256'])
    require(not (DATA/PROVENANCE).exists(),'Unexpected existing restoration provenance target')
    provenance=dict(status='CANONICAL_BYTE_PUBLICATION_RECEIPT',written_at_UTC=stamp(),apply_GO_sha256=go['_receipt_sha256'],known_recovery_acceptance_sha256=plan['known_acceptance_sha256'],development_recovery_acceptance_sha256=plan['development_acceptance_sha256'],original_summary_body_SHA256=planner.SUMMARY_SHA,authentic_summary_publication_commit='814c9030664aedde4f7009c053e059193254975e',authentic_summary_git_blob_SHA1='2a59a18dfd240d8c033d8f2c885e222fb22ca1de',known_core_original_SHA256=planner.CORE,supporting_known_files='Deterministically regenerated; original byte comparison unavailable',unavailable_original_ephemeral_metadata=POINTERS,no_all11_original_restoration_claim=True,no_legacy_development_completion_fabricated=True,no_model_unlock=True)
    body=(json.dumps(provenance,indent=2)+'\n').encode();mapped[PROVENANCE]=dict(source=None,body=body,after=hashlib.sha256(body).hexdigest(),before=None)
    for relative in mapped:require(not (DATA/relative).with_name(Path(relative).name+'.canonical-promotion.tmp').exists(),'Unexpected atomic staging file')
    require(not (DATA/'Public/development-labels-completion.json').exists(),'Legacy development completion must not be fabricated')
    return mapped,original


def apply_plan(plan,go,after_commit=None):
    mapped,original=preflight(plan,go)
    output=Path(go['output_root']).resolve();require((RECOVERY/'ApplyRuns').resolve() in output.parents and not output.exists(),'Fresh separate apply output namespace required')
    output.mkdir(mode=0o700)
    journal=output/'intent-journal.jsonl';proof=output/'posthash-proof.json';failure=output/'failed-apply.json'
    allowed=[journal,proof,failure]
    for relative in mapped:
        target=DATA/relative;allowed.extend([target,target.with_name(target.name+'.canonical-promotion.tmp')])
    guard=WriteGuard(allowed)
    def append(record):
        with journal.open('a') as stream:stream.write(json.dumps(record)+'\n');stream.flush();os.fsync(stream.fileno())
    guard.active=True
    try:
        for i,(relative,operation) in enumerate(mapped.items()):
            destination=DATA/relative
            before=operation['before'];require((sha(destination) if destination.exists() else None)==before,'Target preimage changed after full preflight')
            body=operation['body'] if operation['source'] is None else operation['source'].read_bytes()
            require(hashlib.sha256(body).hexdigest()==operation['after'],'Source changed after preflight')
            append(dict(stage='INTENT_DURABLE_BEFORE_CANONICAL_WRITE',destination=relative,before_sha256=before,after_sha256=operation['after'],UTC=stamp()))
            write_atomic(destination,body)
            append(dict(stage='COMMITTED_AND_POSTHASHED',destination=relative,sha256=sha(destination),UTC=stamp()))
            if after_commit is not None:after_commit(i)
        final={relative:sha(DATA/relative) for relative in mapped}
        require(all(final[r]==v['after'] for r,v in mapped.items()),'Final canonical posthash mismatch')
        for name,value in original.items():require(sha(INCIDENT/name)==value['sha256'],'Incident mutated during apply')
        require(sha(DATA/'Private/development-label-attempt.json')==original['Private/development-label-attempt.json']['sha256'],'Original failed attempt marker mutated')
        result=dict(status='PASS_CANONICAL_BYTE_PUBLICATION',UTC=stamp(),apply_GO_sha256=go['_receipt_sha256'],published_files=final,intent_journal_sha256=sha(journal),incident_and_failed_attempt_preserved=True,no_source_raw_incident_targets=True,no_legacy_development_completion_fabricated=True,no_model_or_training_unlock=True,independent_raw_price_audit_and_external_training_gate_still_required=True)
        with proof.open('x') as stream:stream.write(json.dumps(result,indent=2)+'\n');stream.flush();os.fsync(stream.fileno())
        return result
    except Exception as error:
        with failure.open('x') as stream:stream.write(json.dumps(dict(status='PARTIAL_OR_FAILED_APPLY_STOP_NO_RETRY',UTC=stamp(),error_type=type(error).__name__,error=str(error),model_fit_forbidden=True),indent=2)+'\n');stream.flush();os.fsync(stream.fileno())
        raise
    finally:guard.active=False


def main(receipt):
    receipt=Path(receipt).resolve();go=json.loads(receipt.read_text());go['_receipt_sha256']=sha(receipt)
    require(go.get('authorized') is True and go.get('mode')=='canonical-recovery-publication','Explicit canonical APPLY Root GO required')
    require(go.get('published_before_apply') is True and len(go.get('publication_commit',''))==40,'Published apply code/plan required')
    freeze=Path(go['source_freeze_path']);require(sha(freeze)==go['source_freeze_sha256'],'Apply source freeze changed')
    f=json.loads(freeze.read_text())
    for name,digest in f['sources_sha256'].items():require(sha(Path(__file__).parent/name)==digest,'Apply source changed')
    plan_path=Path(go['plan_path']);require(sha(plan_path)==go['plan_sha256'],'Concrete reviewed canonical plan changed')
    plan=json.loads(plan_path.read_text());require(plan['status']=='PROPOSAL_ONLY_NO_ORIGINAL_WRITES','Unknown canonical plan')
    result=apply_plan(plan,go);print(json.dumps(dict(status=result['status'],published_files=len(result['published_files']),output_root=go['output_root'])))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--receipt',type=Path,required=True);main(parser.parse_args().receipt)
