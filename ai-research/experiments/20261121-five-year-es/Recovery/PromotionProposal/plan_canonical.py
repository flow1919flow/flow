"""READ-ONLY canonical publication planner. No apply/write-to-originals code.

Produces a reviewable plan in RecoveryRoot only, after BOTH accepted attempts.
Actual publication/restoration requires a separate explicit Root authorization.
"""
from pathlib import Path
import argparse,hashlib,json

RECOVERY=Path(__file__).resolve().parents[1]
DATA=RECOVERY.parent/'ES-FiveYear-SecondData-20261121'
INCIDENT=DATA/'Private/Incidents/development-dispatch-path-20261121'
CORE={'candidates_jsonl':'b021d522a869d69f8893232123420cba78181c9a2f6425bae3c6973e40a2c67a','candidates_csv':'163e2bb54c2539e4685e33624bdcd528eb6786fbeadb265fd68e82312766e715','schedule_json':'234897b90557cb44eda32c7ce0d6756a60841980f6eccfbe6ccc9f582c257e9d'}
SUMMARY_SHA='6121214e8a36f0a67e643046609276fec7d76e502797bd401ae598b25d8640bf'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def accepted(attempt,role):
    attempt=Path(attempt).resolve()
    if (RECOVERY/'Attempts').resolve() not in attempt.parents:raise ValueError('Read only isolated RecoveryRoot attempts')
    path=attempt/'Public/recovery-acceptance.json';r=json.loads(path.read_text())
    assert r['role']==role and r['status']=='EXACT_ORIGINAL_BYTE_AND_PLAN_MATCH'
    assert r['immutable_original_Data_root_postcheck_passed'] and r['immutable_original_ML_root_postcheck_passed']
    assert r['no_model_fit'] and r['no_sealed_access'] and r['no_selection_or_parameter_change']
    for value in r['artifacts'].values():assert sha(attempt/value['path_relative_to_attempt'])==value['sha256']
    return attempt,r,path


def plan(known,development,target):
    known,k,kreceipt=accepted(known,'known');development,d,dreceipt=accepted(development,'development')
    assert k['filled_cases']==348 and d['filled_cases']==1143 and d['decision_plans']==1145 and d['plan_days']==775 and d['resolved_entry_cancellations']==2
    original=json.loads((INCIDENT/'incident-files.json').read_text())['files']
    for name,value in original.items():assert sha(INCIDENT/name)==value['sha256']
    operations=[]
    def add(source,destination,kind,expected,old=None):
        source=Path(source).resolve();destination=DATA/destination
        assert sha(source)==expected
        if old is None:assert not destination.exists(),'New canonical role target unexpectedly exists'
        else:assert destination.exists() and sha(destination)==original[old]['sha256'],'Protected current preimage changed'
        operations.append(dict(action='COPY_BYTES_ONLY_AFTER_SEPARATE_ROOT_GO',source=str(source),destination=str(destination),source_sha256=expected,current_destination_sha256=original[old]['sha256'] if old else None,provenance_class=kind,original_preimage_preserved_in_incident=bool(old)))
    known_map={'candidates_jsonl':'Private/second-candidates-known.jsonl','candidates_csv':'Private/second-candidates-known.csv','schedule_json':'Private/second-known-price-roll-freeze.json'}
    for name,relative in known_map.items():
        assert k['artifacts'][name]['sha256']==CORE[name]
        add(known/k['artifacts'][name]['path_relative_to_attempt'],relative,'EXACT_ORIGINAL_SCIENTIFIC_BYTES',CORE[name],old=relative)
    genuine=RECOVERY/'OriginalPublished/Public/second-known-summary.json'
    add(genuine,'Public/second-known-summary.json','EXACT_AUTHENTIC_PUBLISHED_BYTES_NO_BODY_EDIT',SUMMARY_SHA,old='Public/second-known-summary.json')
    for name,relative in [('exclusions_json','Private/second-known-exclusions.json'),('ambiguities_json','Private/second-known-ambiguities.json'),('feature_proof_json','Private/second-known-feature-before-label-proof.json')]:
        add(known/k['artifacts'][name]['path_relative_to_attempt'],relative,'REGENERATED_SUPPORTING_METADATA_ORIGINAL_BYTE_COMPARISON_UNAVAILABLE',k['artifacts'][name]['sha256'],old=relative)
    assert d['artifacts']['schedule_json']['sha256']==original['Private/second-known-price-roll-freeze.json']['sha256'],'Development schedule does not match preserved incident'
    targets={'schedule_json':'price-roll-freeze.json','candidates_jsonl':'candidates.jsonl','candidates_csv':'candidates.csv','intents_jsonl':'intents.jsonl','intents_csv':'intents.csv','decision_plans_jsonl':'intents-plan-journal.jsonl','role_release_json':'release.json','exclusions_json':'exclusions.json','ambiguities_json':'ambiguities.json','feature_proof_json':'feature-before-label-proof.json'}
    for name,suffix in targets.items():
        artifact=d['artifacts'][name];add(development/artifact['path_relative_to_attempt'],'Private/development-'+suffix,'CANONICAL_DEVELOPMENT_RELEASE_EXACT_ACCEPTED_RECOVERY_BYTES',artifact['sha256'])
    stale=[]
    for name in ['Public/second-execution-start.json','Public/second-preflight-progress.json']:
        assert sha(DATA/name)==original[name]['sha256']
        stale.append(dict(path=str(DATA/name),current_sha256=original[name]['sha256'],status='ORIGINAL_KNOWN_EPHEMERAL_BYTES_UNAVAILABLE',proposal='After separate explicit Root approval, retire wrongly named current development status from canonical known namespace; preserve incident copy. Never replace with fabricated original timestamps.'))
    result=dict(schema='canonical-publication-proposal-v1',status='PROPOSAL_ONLY_NO_ORIGINAL_WRITES',known_acceptance_sha256=sha(kreceipt),development_acceptance_sha256=sha(dreceipt),operations=operations,unavailable_ephemeral_status_paths=stale,genuine_summary_provenance=dict(publication_commit='814c9030664aedde4f7009c053e059193254975e',git_blob_SHA1='2a59a18dfd240d8c033d8f2c885e222fb22ca1de',body_sha256=SUMMARY_SHA,restoration_provenance_must_be_adjacent_not_edit_body=True),requires_explicit_Root_GO=True,all_current_target_preimages_checked=True,all_source_bytes_hash_checked=True,no_original_writes_performed=True,no_all11_original_restoration_claim=True,no_model_or_training_unlocked=True,independent_all_row_raw_price_audit_and_external_training_gate_still_required=True,planner_source_sha256=sha(__file__))
    target=Path(target).resolve()
    assert (RECOVERY/'PromotionProposal').resolve() in target.parents and not target.exists()
    target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(proposal=str(target),sha256=sha(target),planned_copy_operations=len(operations),actual_original_writes=0)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--known-attempt',required=True);p.add_argument('--development-attempt',required=True);p.add_argument('--output',required=True);a=p.parse_args();plan(a.known_attempt,a.development_attempt,a.output)
