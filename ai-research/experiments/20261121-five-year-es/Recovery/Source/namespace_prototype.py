"""SYNTHETIC-ONLY namespace/packaging prototype, not a real recovery runner.

Frozen strategy source is read, never changed or executed on real market data.
Production recovery remains CLOSED pending separate Root/Claude authorization.
"""
from pathlib import Path
import ast,copy,hashlib,json,os,sys
import pandas as pd

RECOVERY=Path(__file__).resolve().parents[1]
TASK=RECOVERY.parent/'ES-FiveYear-SecondData-20261121'
sys.path.insert(0,str(TASK/'Source'))
import period_dispatch as frozen

OLD_TO_NEW={
 'Private/second-known-price-roll-freeze.json':'Private/{role}-price-roll-freeze.json',
 'Public/second-execution-start.json':'Public/{role}-label-execution-start.json',
 'Public/second-preflight-progress.json':'Public/{role}-label-progress.json',
 'Private/second-candidates-known.jsonl':'Private/{role}-candidates.jsonl',
 'Private/second-candidates-known.csv':'Private/{role}-candidates.csv',
 'Private/second-known-exclusions.json':'Private/{role}-exclusions.json',
 'Private/second-known-ambiguities.json':'Private/{role}-ambiguities.json',
 'Private/second-known-feature-before-label-proof.json':'Private/{role}-feature-before-label-proof.json',
 'Public/second-known-summary.json':'Public/{role}-labels-summary.json'}
EXTRA=['Private/{role}-attempt.json','Private/{role}-intents-plan-journal.jsonl','Private/{role}-intents-result-journal.jsonl','Private/{role}-intents.jsonl','Private/{role}-intents.csv','Private/{role}-release.json','Public/{role}-labels-completion.json','Public/{role}-failed-attempt.json','run.log']


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def output_targets(role):return {x.format(role=role) for x in list(OLD_TO_NEW.values())+EXTRA}


class InputManifestPath(ast.NodeTransformer):
    def __init__(self,reverse=False):self.reverse=reverse
    def visit_BinOp(self,node):
        node=self.generic_visit(node)
        old='INPUT_ROOT' if self.reverse else 'HERE';new='HERE' if self.reverse else 'INPUT_ROOT'
        if isinstance(node.op,ast.Div) and isinstance(node.left,ast.Name) and node.left.id==old and isinstance(node.right,ast.Constant) and node.right.value=='Private/Months':node.left.id=new
        return node


def corrected_engine(role):
    original=next(n for n in ast.parse((TASK/'Source/second_run.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='run')
    mapping=frozen.replacements(role) if role!='known' else {}
    mapping.update({old:new.format(role=role) for old,new in OLD_TO_NEW.items()})
    changed=frozen.LiteralDispatch(mapping).visit(copy.deepcopy(original))
    changed=InputManifestPath().visit(changed);ast.fix_missing_locations(changed)
    # This is a supplementary math/control proof; runtime I/O tests are mandatory.
    restored=InputManifestPath(reverse=True).visit(copy.deepcopy(changed))
    restored=frozen.LiteralDispatch({v:k for k,v in mapping.items()},reverse=True).visit(restored)
    assert ast.dump(original,include_attributes=False)==ast.dump(restored,include_attributes=False)
    literals={n.value for n in ast.walk(changed) if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.startswith(('Private/','Public/'))}
    assert literals-{'Private/Months'}=={x.format(role=role) for x in OLD_TO_NEW.values()},literals
    assert not literals.intersection(OLD_TO_NEW)
    return ast.unparse(ast.Module(body=[changed],type_ignores=[]))+'\n'


class NamespaceViolation(RuntimeError):pass


class Guard:
    """Explicit fresh output and immutable input namespace, including hash I/O."""
    def __init__(self,input_root,output_root,role):
        self.input=Path(input_root).resolve();self.output=Path(output_root).resolve();self.role=role
        if not self.input.is_dir() or self.output.exists():raise NamespaceViolation('Require existing immutable input and nonexistent output root')
        if self.output==self.input or self.input in self.output.parents or self.output in self.input.parents:raise NamespaceViolation('Physically disjoint input/output roots required')
        self.targets=output_targets(role);self.allowed=self.targets|{p+'.tmp' for p in self.targets}
        self.writes=[];self.hashes=[];self.active=False;self.plans=[];self.intents=[]
        self.preimages={str(p.relative_to(self.input)):digest(p) for p in self.input.rglob('*') if p.is_file()}
        self.output.mkdir(mode=0o700)
        (self.output/'Private').mkdir();(self.output/'Public').mkdir()
        sys.addaudithook(self.audit_hook)

    def relative_output(self,path):
        try:return str(Path(path).resolve().relative_to(self.output))
        except ValueError:raise NamespaceViolation('Write outside isolated output root: '+str(path))

    def check_write(self,path):
        if isinstance(path,int):return
        relative=self.relative_output(path)
        if relative not in self.allowed:raise NamespaceViolation('Write outside role allowlist: '+relative)
        self.writes.append(relative)

    def audit_hook(self,event,args):
        if not self.active:return
        if event=='open':
            path,mode,flags=args
            if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):self.check_write(path)
        elif event in ['os.rename','os.replace']:
            self.check_write(args[0]);self.check_write(args[1])
        elif event in ['os.remove','os.rmdir','os.truncate']:self.check_write(args[0])
        elif event=='os.mkdir':raise NamespaceViolation('Unexpected runtime directory creation')

    def __enter__(self):self.active=True;return self
    def __exit__(self,*args):
        self.active=False
        after={str(p.relative_to(self.input)):digest(p) for p in self.input.rglob('*') if p.is_file()}
        assert after==self.preimages,'IMMUTABLE INPUT/Known preimage changed'

    def sha(self,path):
        path=Path(path).resolve()
        if self.input not in path.parents:
            relative=self.relative_output(path)
            if relative not in self.targets:raise NamespaceViolation('Hash outside role allowlist: '+relative)
        self.hashes.append(str(path));return digest(path)

    def save(self,path,value):
        path=Path(path);self.check_write(path);temp=path.with_suffix(path.suffix+'.tmp')
        temp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');temp.replace(path)

    def append(self,relative,value):
        path=self.output/relative;self.check_write(path)
        with path.open('a') as stream:
            stream.write(json.dumps(value,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())

    def capture(self,delegate):
        def observed(candidate,rows,previews,clock):
            plan=copy.deepcopy(candidate);self.plans.append(plan)
            # Durable BEFORE label function, not delayed until final packaging.
            self.append(f'Private/{self.role}-intents-plan-journal.jsonl',plan)
            result=delegate(candidate,rows,previews,clock)
            self.append(f'Private/{self.role}-intents-result-journal.jsonl',dict(case_key=plan['case_key'],result=copy.deepcopy(result)))
            terminal=result.get('exit_ns') if result['label_status']=='ok' else result.get('entry_cancel_ns')
            intent=dict(plan,**copy.deepcopy(result),successful_case_key=plan['case_key'] if result['label_status']=='ok' else '',pending_terminal_ns=terminal,economic_path_resolved=terminal is not None)
            self.intents.append(intent);self.append(f'Private/{self.role}-intents.jsonl',intent)
            return result
        return observed

    def package(self,cases,binding):
        journal=self.output/f'Private/{self.role}-intents.jsonl'
        assert journal.exists() and len(journal.read_text().splitlines())==len(self.plans)==len(self.intents)
        # Intents are durable even if the following final CSV check fails.
        csv=self.output/f'Private/{self.role}-candidates.csv';assert self.sha(csv)==binding['candidates_csv_sha256']
        assert {x['successful_case_key'] for x in self.intents if x['label_status']=='ok'}=={c['case_key'] for c in cases}
        intent_csv=self.output/f'Private/{self.role}-intents.csv';pd.DataFrame(self.intents).to_csv(intent_csv,index=False)
        release=dict(schema='es-frozen-second-role-release-v1',role=self.role,csv_name=csv.name,csv_sha256=self.sha(csv),row_count=len(cases),intent_csv_name=intent_csv.name,intent_csv_sha256=self.sha(intent_csv),intent_jsonl_sha256=self.sha(journal),intent_row_count=len(self.intents),unresolved_intent_count=sum(not x['economic_path_resolved'] for x in self.intents),prototype_synthetic_only=True)
        self.save(self.output/f'Private/{self.role}-release.json',release)
        self.save(self.output/f'Public/{self.role}-labels-completion.json',dict(status='SYNTHETIC_PACKAGE_COMPLETE',**release))
        return dict(status='SYNTHETIC_PACKAGE_COMPLETE')
