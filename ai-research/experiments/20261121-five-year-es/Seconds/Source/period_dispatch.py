"""Guarded date/calendar/output dispatch of the EXACT frozen known run body.

The readable generated engine changes only registered period literals, output
names and metadata. Its normalized AST must equal the frozen known function.
Signal/feature/label functions are the same immutable imported function objects.
No model fitting, no new known-year run, no resolution or parameter selection.
"""
from pathlib import Path
from datetime import date,timedelta
from collections import defaultdict
import argparse,ast,copy,hashlib,json,os,time
import numpy as np
import second_run as known
from price_extract_support import HERE,ROOT,Calendar,sha,save,utcnow,select_prior

PERIODS={'development':('2021-11-24','2024-11-24'),'sealed':('2024-11-24','2025-11-24')}
KNOWN_FREEZE=HERE/'Public/second-source-freeze-v2.json'
KNOWN_FREEZE_SHA='c3ddf25c74a0f9798a469c7401a3a67416018aa339d0a6746b162db5fc9d5c6a'
KNOWN_ACCEPTANCE_SHA='61ecb4431327aa4fb5994fc1d64ca765b82ea0f6e7bd09fa98566692e5b33f5f'
KNOWN_AUDIT_SHA='a1f071d15a1ce8eb5d1af4cca70b7b87d2f276a1a917c232e461a538740d609c'
PROTOCOL_HASHES={'498b90431dfeef1f65b8aea232cdff7e9ca2a44153131a5b8c8faeba36b813fa','b228b39c640dc6ff5a0ef79575c4c6d9557f70eaa77732900ebcb1dc2048aba7','c9ed499b4e861afd58b208c3e5f42234826efe78ce4c548c9bb5b0c199589598'}


def required_months(role):
    lo,hi=PERIODS[role];month=np.datetime64(lo[:7],'M');last=np.datetime64(hi[:7],'M');result=[]
    while month<=last:result.append(str(month));month+=np.timedelta64(1,'M')
    return result


def verify_known_immutable():
    if sha(KNOWN_FREEZE)!=KNOWN_FREEZE_SHA:raise ValueError('Knownsourcefreezechangedsincereview')
    f=json.loads(KNOWN_FREEZE.read_text());known.verify_frozen_sources(f,HERE/'Source',HERE/'Public/second-fixtures.json')
    if sha(HERE/'Public/second-native-acceptance.json')!=KNOWN_ACCEPTANCE_SHA or sha(HERE/'Public/second-independent-audit.json')!=KNOWN_AUDIT_SHA:raise ValueError('KnownPASSorauditproofchangedsincereview')
    acceptance=json.loads((HERE/'Public/second-native-acceptance.json').read_text());audit=json.loads((HERE/'Public/second-independent-audit.json').read_text())
    if acceptance.get('accepted') is not True or audit.get('status')!='PASS_INDEPENDENT_RAW_PRICE_FILL_AND_METRIC_AUDIT':raise ValueError('Independentlyaudited1sPASSrequired')
    return f


def replacements(role):
    lo,hi=PERIODS[role]
    return {'2025-11-24':lo,'2026-10-31':hi,'known':role,
        'second-known-price-roll-freeze.json':f'{role}-price-roll-freeze.json','second-execution-start.json':f'{role}-label-execution-start.json',
        'second-preflight-progress.json':f'{role}-label-progress.json','second-candidates-known.jsonl':f'{role}-candidates.jsonl','second-candidates-known.csv':f'{role}-candidates.csv',
        'second-known-exclusions.json':f'{role}-exclusions.json','second-known-ambiguities.json':f'{role}-ambiguities.json','second-known-feature-before-label-proof.json':f'{role}-feature-before-label-proof.json','second-known-summary.json':f'{role}-labels-summary.json',
        'RUNNING_KNOWN_ONLY_ONE_ATTEMPT':f'RUNNING_{role.upper()}_EXACT_FROZEN_ENGINE','KNOWN_1S_SINGLE_ATTEMPT_RECONSTRUCTION_COMPLETE':f'{role.upper()}_LABELS_COMPLETE_FROZEN_ENGINE',
        'known1s':f'{role}1s','No genuinefilledknown1scandidates':f'No genuinefilled{role}candidates','Guard:labeloutsideknownwindow':f'Guard:labeloutside{role}window'}


class LiteralDispatch(ast.NodeTransformer):
    def __init__(self,mapping,reverse=False):self.mapping=mapping;self.reverse=reverse
    def visit_Constant(self,node):
        if isinstance(node.value,str) and node.value in self.mapping:return ast.copy_location(ast.Constant(self.mapping[node.value]),node)
        return node
    def visit_keyword(self,node):
        node=self.generic_visit(node)
        if node.arg==('no_unauthorized_period_labels' if self.reverse else 'no_older_labels'):node.arg='no_older_labels' if self.reverse else 'no_unauthorized_period_labels'
        return node
    def visit_FunctionDef(self,node):
        node=self.generic_visit(node)
        if node.name==('run_period' if self.reverse else 'run'):node.name='run' if self.reverse else 'run_period'
        return node


def derived_source(role):
    verify_known_immutable();tree=ast.parse((HERE/'Source/second_run.py').read_text());original=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
    changed=LiteralDispatch(replacements(role)).visit(copy.deepcopy(original));ast.fix_missing_locations(changed)
    restored=LiteralDispatch({v:k for k,v in replacements(role).items()},reverse=True).visit(copy.deepcopy(changed));ast.fix_missing_locations(restored)
    if ast.dump(original,include_attributes=False)!=ast.dump(restored,include_attributes=False):raise ValueError('PerioddispatchchangedfrozenalgorithmAST')
    text=ast.unparse(ast.Module(body=[changed],type_ignores=[]))+'\n'
    return text


def prepare_engines():
    proof={}
    for role in PERIODS:
        text=derived_source(role);path=HERE/f'Source/{role}_engine_generated.py'
        if path.exists() and path.read_text()!=text:raise ValueError('Refusetoreplacepreviouslygeneratedengine')
        path.write_text(text)
        proof[role]=dict(date_range=PERIODS[role],required_full_months=required_months(role),generated_source_sha256=sha(path),normalized_AST_exactly_equals_frozen_known_run=True,only_literal_period_outputs_and_metadata_changed=True)
    save(HERE/'Public/period-dispatch-proof.json',dict(status='PREPARED_NO_OLDER_LABELS',utc=utcnow(),known_source_freeze_sha256=KNOWN_FREEZE_SHA,known_kernel_sha256=sha(HERE/'Source/second_kernel.py'),roles=proof,global_bindings_changed_only=['authorize:roleintegrity/modelguard','known_sources:requiredrolemonths+calendar','acceptance:completion/baselineprovenance','KNOWN_MONTHS:fixedroleinputmonths','delayed_shadow:transparentidentity-returnintentcapture'],known_source_untouched=True,no_signals_or_labels_or_models=True))
    return proof


def verify_months(role,verify_shards=False):
    result={};downloads=json.loads((HERE/'Public/download-manifest.json').read_text())
    for month in required_months(role):
        p=HERE/'Private/Months'/month/'manifest.json'
        if not p.exists():raise ValueError('Missingcompletedrolepricemonth:'+month)
        m=json.loads(p.read_text())
        if m['status']!='COMPLETE_LOCAL_1S_PRICE_ONLY' or m['zero_cost_download_receipt']['quoted_cost_USD']!=0:raise ValueError('Rolemonthunattestedornonzero')
        matches=[d for d in downloads if d.get('month')==month and d.get('status')=='downloaded_and_header_verified']
        if len(matches)!=1 or matches[0]!=m['zero_cost_download_receipt']:raise ValueError('Rolemonthnotboundtocurrentcompletedzeroreceipt:'+month)
        if m['source_month']!=month or m['schema']!='ohlcv-1s' or m['raw_source_sha256']!=matches[0]['sha256']:raise ValueError('Rolemonthsourceidentitymismatch')
        if verify_shards:
            for shard in m['second_shards']:
                if sha(HERE/shard['path_relative_to_task'])!=shard['sha256']:raise ValueError('Rolesecondpricechanged')
        result[month]=m
    return result


def verify_final_published_model(go):
    """Sealedlabelrelease requiresconcretepublishedweights/preprocessing/rule."""
    binding=go.get('published_model_receipt')
    if not isinstance(binding,dict):raise ValueError('Sealedlabelsrequirepublishedfinal-modelreceipt')
    p=Path(binding['path'])
    if sha(p)!=binding.get('sha256'):raise ValueError('FinalmodelreceiptSHAdoesnotmatchrootGO')
    receipt=json.loads(p.read_text())
    if receipt.get('published') is not True or not receipt.get('publication_commit'):raise ValueError('Finalmodelfreezemusthavepublicationproof')
    if receipt.get('published_before_final_labels') is not True:raise ValueError('Publicationmustprecedefinallabelrelease')
    artifact=receipt.get('model_bundle')
    if not isinstance(artifact,dict) or sha(artifact['path'])!=artifact.get('sha256'):raise ValueError('Frozenfinalmodelbundlemissingorchanged')
    if receipt.get('models_frozen_sha256')!=artifact['sha256']:raise ValueError('Publishedfrozenmodelreceiptbundlebindingmismatch')
    if binding.get('required_bundle_sha256')!=artifact['sha256']:raise ValueError('RootGOdoesnotbindexactfinalweightsbundle')
    return receipt


def authorize_period(role,path):
    go=json.loads(Path(path).read_text())
    if go.get('authorized') is not True or go.get('mode')!=role:raise ValueError('RolelabelguardCLOSEDwithoutmatchingexplicitrootrelease')
    verify_known_immutable()
    if go.get('known_acceptance_sha256')!=sha(HERE/'Public/second-native-acceptance.json') or go.get('known_independent_audit_sha256')!=sha(HERE/'Public/second-independent-audit.json'):raise ValueError('Rootreleaseunboundtoaudited1sPASS')
    for binding in go.get('protocol_files',[]):
        if sha(binding['path'])!=binding['sha256']:raise ValueError('Publishedprotocolchanged')
    if {b['sha256'] for b in go.get('protocol_files',[])}!=PROTOCOL_HASHES:raise ValueError('Allthreeexactpublished1sprotocolbindingsrequired')
    freeze_path=Path(go.get('source_freeze_path',HERE/'Public/period-source-freeze.json'))
    if sha(freeze_path)!=go.get('source_freeze_sha256'):raise ValueError('RootGOdoesnotbindexactperiodsourcefreeze')
    freeze=json.loads(freeze_path.read_text());known.verify_frozen_sources(freeze,HERE/'Source',HERE/'Public/period-fixtures.json')
    if role=='sealed':verify_final_published_model(go)
    verify_months(role,verify_shards=True) # Price-onlyreadiness, allmonthsbeforesinglelabelrun.
    if (HERE/f'Private/{role}-candidates.jsonl').exists():raise ValueError('Rolelabelscompletedalready; noautomaticrerun')
    reserve_attempt(role,path,freeze_path)
    go['source_freeze_path']=str(freeze_path);return go


def reserve_attempt(role,path,freeze_path):
    marker=HERE/f'Private/{role}-label-attempt.json'
    try:
        with marker.open('x') as stream:stream.write(json.dumps(dict(utc=utcnow(),root_go_sha256=sha(path),source_freeze_sha256=sha(freeze_path),role=role))+'\n')
    except FileExistsError:raise ValueError('Rolelabelattemptalreadyrecorded; nohiddenretry')


def period_sources(role):
    months=verify_months(role,verify_shards=True);calendar=Calendar();coverage=[]
    for month,m in months.items():
        p=HERE/'Private/Months'/month/'contract-session-price-coverage.json'
        if sha(p)!=m['session_coverage_sha256']:raise ValueError('Rolecoverageproofchanged')
        coverage.extend(json.loads(p.read_text()))
    byday=defaultdict(list);lookup={}
    for r in coverage:byday[r['day']].append(r);lookup[(r['day'],r['raw_symbol'])]=r
    start=date.fromisoformat(min(r['day'] for r in coverage));end=date.fromisoformat(max(r['day'] for r in coverage))
    days=[str(start+timedelta(days=i)) for i in range((end-start).days+1) if calendar.get(str(start+timedelta(days=i))) is not None]
    incumbent=None;prior=None;schedule=[]
    for i,day in enumerate(days):
        row=select_prior(byday[prior],incumbent) if prior else None;symbol=row['raw_symbol'] if row else None;warm=[]
        for d in days[max(0,i-5):i]:
            r=lookup.get((d,symbol));warm.append(dict(day=d,raw_symbol=symbol,complete_5m_grid=bool(r and r['complete_5m_grid'])))
        clock=calendar.get(day)
        if 'unverified' in clock['calendar_status']:raise ValueError('Rolecalendarhasunresolvedday:'+day)
        schedule.append(dict(day=day,raw_symbol=symbol,selection_information_day=prior,**clock,warmup_previous_five_same_contract_sessions=warm,warmup_complete=len(warm)==5 and all(w['complete_5m_grid'] for w in warm)))
        if row:incumbent=symbol
        prior=day
    return months,schedule


def capture_intents(delegate,events):
    """Observe exact frozen calls, preserving arguments, identity and outcomes."""
    def observed(candidate,rows,previews,clock):
        result=delegate(candidate,rows,previews,clock)
        terminal=result.get('exit_ns') if result['label_status']=='ok' else result.get('entry_cancel_ns')
        events.append(dict(copy.deepcopy(candidate),**copy.deepcopy(result),successful_case_key=candidate['case_key'] if result['label_status']=='ok' else '',pending_terminal_ns=terminal,economic_path_resolved=terminal is not None))
        return result
    return observed


def role_release(role,cases,binding,receipt_path,intents):
    """Adjacent hash envelope permits consumers to verify BEFORE CSV parsing."""
    go=json.loads(Path(receipt_path).read_text())
    if sha(receipt_path)!=binding['root_go_sha256']:raise ValueError('RootGOchangedduringlabelrun')
    csvpath=HERE/f'Private/{role}-candidates.csv';freeze=json.loads(Path(go['source_freeze_path']).read_text())
    days=[c['day'] for c in cases];lo,hi=PERIODS[role]
    if not days or not all(lo<=d<hi for d in days):raise ValueError('Wrongroleinreleaseenvelope')
    if sha(csvpath)!=binding['candidates_csv_sha256']:raise ValueError('CandidateCSVchangedbeforelabelrelease')
    intents=sorted(intents,key=lambda e:(e['signal_ns'],e['contract'],e['side']))
    if len({e['case_key'] for e in intents})!=len(intents):raise ValueError('Duplicatecapturedintent')
    if {e['successful_case_key'] for e in intents if e['label_status']=='ok'}!={c['case_key'] for c in cases}:raise ValueError('Capturedsuccessfulintentsdonotexactlymatchfilledinventory')
    if not all(lo<=e['day']<hi for e in intents):raise ValueError('Intentoutsideauthorizedrole')
    intentpath=HERE/f'Private/{role}-intents.csv';known.pd.DataFrame(intents).to_csv(intentpath,index=False)
    intentjson=HERE/f'Private/{role}-intents.jsonl';intentjson.write_text(''.join(json.dumps(e,allow_nan=False)+'\n' for e in intents))
    manifest=dict(schema='es-frozen-second-role-release-v1',role=role,csv_name=csvpath.name,csv_sha256=sha(csvpath),row_count=len(cases),day_min=min(days),day_max=max(days),period_start_inclusive=lo,period_end_exclusive=hi,native_acceptance_sha256=KNOWN_ACCEPTANCE_SHA,independent_native_audit_sha256=KNOWN_AUDIT_SHA,known_source_freeze_sha256=KNOWN_FREEZE_SHA,protocol_sha256='498b90431dfeef1f65b8aea232cdff7e9ca2a44153131a5b8c8faeba36b813fa',protocol_files=go['protocol_files'],generator_source_hashes=freeze['sources_sha256'],generator_source_freeze_sha256=sha(go['source_freeze_path']),root_go_sha256=sha(receipt_path),released_utc=utcnow(),kernel_sha256=sha(HERE/'Source/second_kernel.py'),no_model_fit_by_generator=True,intent_csv_name=intentpath.name,intent_csv_sha256=sha(intentpath),intent_jsonl_sha256=sha(intentjson),intent_row_count=len(intents),unresolved_intent_count=sum(not e['economic_path_resolved'] for e in intents),intent_semantics='Alleligibledecisionfeatureintentsincludingunfilled; wrapperreturnsidenticalfrozenresult; missingterminaltimesremainunknown')
    if role=='sealed':manifest['published_model_receipt']=go['published_model_receipt']
    save(HERE/f'Private/{role}-release.json',manifest)
    return manifest


def completion(role,cases,binding,receipt_path,intents):
    # No nativecomparison rerun, no target/search changes, no model fitting.
    report=dict(status='ROLE_LABELS_COMPLETE_NO_MODEL',role=role,utc=utcnow(),cases=len(cases),case_days=len({c['day'] for c in cases}),date_range=PERIODS[role],no_unauthorized_period_labels=True,no_models_fit=True,**binding)
    if role=='development':
        values=np.array([c['stress_net_R'] for c in cases]);report['development_strategy_baseline']=dict(n=len(values),mean_stress_net_R=float(values.mean()),median_stress_net_R=float(np.median(values)),positive_fraction=float(np.mean(values>0)),mean_normal_net_usd=float(np.mean([c['normal_net_usd'] for c in cases])),mean_stress_net_usd=float(np.mean([c['stress_net_usd'] for c in cases])),interpretation='Standaloneindependentcandidateoutcomes,notdeployableportfolioorproviderpayouts')
    else:report['sealed_evaluation']='Labelsreleasedonlyafterpublishedfinalmodelbundle;performanceevaluationownedbyfrozenrootmodelpipeline'
    release=role_release(role,cases,binding,receipt_path,intents);report['role_release_sha256']=sha(HERE/f'Private/{role}-release.json')
    report['intent_count']=release['intent_row_count'];report['unresolved_intent_count']=release['unresolved_intent_count']
    save(HERE/f'Public/{role}-labels-completion.json',report);return report


def run_period(role,receipt):
    expected=derived_source(role);path=HERE/f'Source/{role}_engine_generated.py'
    if not path.exists() or path.read_text()!=expected:raise ValueError('Generatedperiodengineisnotexactalloweddispatch')
    intents=[]
    environment=dict(vars(known));environment.update(__file__=str(Path(__file__)),KNOWN_MONTHS=required_months(role),authorize=lambda p:authorize_period(role,p),known_sources=lambda:period_sources(role),acceptance=lambda cases,binding:completion(role,cases,binding,receipt,intents),delayed_shadow=capture_intents(known.delayed_shadow,intents))
    exec(compile(expected,str(path),'exec'),environment)
    environment['run_period'](receipt)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--prepare-engines',action='store_true');ap.add_argument('--role',choices=list(PERIODS));ap.add_argument('--receipt',type=Path);a=ap.parse_args()
    if a.prepare_engines:print(json.dumps(prepare_engines(),indent=2))
    elif a.role and a.receipt:
        try:run_period(a.role,a.receipt)
        except Exception as error:
            save(HERE/f'Public/{a.role}-label-failure-{time.time_ns()}.json',dict(status='FAILED_PRESERVE_ROLE_ATTEMPT_EVIDENCE',role=a.role,utc=utcnow(),error_type=type(error).__name__,error=str(error),no_automatic_retry=True,no_models_fit=True))
            raise
    else:ap.error('Require --prepare-engines or explicit--roleand--receipt; no implicitlabelrelease')
