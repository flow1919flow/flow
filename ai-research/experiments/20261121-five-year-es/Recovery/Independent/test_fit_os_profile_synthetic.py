"""Actual macOS syscall controls on synthetic roots; no training or labels."""
from pathlib import Path
import hashlib,importlib.util,json,os,subprocess,tempfile,datetime
R=Path(__file__).resolve().parents[1];source=Path(__file__).with_name('prepare_fit_os_profile.py');spec=importlib.util.spec_from_file_location('profile_builder',source);p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
PYTHON=R.parents[1]/'work/tools/mlflow/.venv/bin/python'
with tempfile.TemporaryDirectory(prefix='fit-os-synthetic-',dir=R/'OSProbe')as t:
    base=Path(t);d=base/'Data';l=base/'Learning';(d/'Private').mkdir(parents=True);(d/'Source').mkdir();(l/'Private').mkdir(parents=True);(l/'Public').mkdir();(l/'Source').mkdir()
    protected=[d/'Private/second-candidates-known.jsonl',d/'Private/development-candidates.csv',d/'Source/second_kernel.py',l/'Source/train_fiveyear.py',l/'Public/preregister.json',l/'Private/existing-science.json']
    for f in protected:f.write_text('IMMUTABLE_SYNTHETIC')
    sealed=d/'Private/sealed-candidates.csv';sealed.write_text('SEALED_SYNTHETIC');price=d/'Private/raw-price.parquet';price.write_text('SYNTHETIC_PRICE')
    allowed=[x for x in p.allowed_paths(l)if x.suffix];profile=base/'fit.sb';profile.write_text(p.profile(d,l));probe=base/'probe.py'
    probe.write_text('''from pathlib import Path
import errno,json,sys,numpy,sklearn
protected=json.loads(sys.argv[1]);allowed=json.loads(sys.argv[2]);sealed=Path(sys.argv[3]);price=Path(sys.argv[4]);checks=[]
for name in protected:
    f=Path(name)
    for operation in ['truncate','unlink','rename']:
        try:
            if operation=='truncate':f.write_text('TAMPER')
            elif operation=='unlink':f.unlink()
            else:f.rename(f.with_suffix('.renamed'))
        except OSError as e:assert e.errno==errno.EPERM,(operation,e);checks.append(operation)
        else:raise AssertionError('Forbidden scientific write permitted')
for name in allowed:
    f=Path(name);f.parent.mkdir(parents=True,exist_ok=True);f.write_text('ALLOWED_OUTPUT')
    if f.name.endswith('.tmp'):f.replace(f.with_name(f.name[:-4]))
try:sealed.read_bytes()
except OSError as e:assert e.errno==errno.EPERM
else:raise AssertionError('Sealed label read permitted')
assert price.read_text()=='SYNTHETIC_PRICE'
try:price.with_name('unregistered-output').write_text('BAD')
except OSError as e:assert e.errno==errno.EPERM
else:raise AssertionError('Unregistered write permitted')
print(json.dumps({'protected_operations_denied':len(checks),'all_allowed_writes_and_atomic_replacements':True,'sealed_read_denied':True,'price_read_allowed':True,'unregistered_output_denied':True,'numpy_sklearn_import_without_fit':True}))
''')
    result=subprocess.run(['/usr/bin/sandbox-exec','-f',str(profile),str(PYTHON),str(probe),json.dumps([str(x)for x in protected]),json.dumps([str(x)for x in allowed]),str(sealed),str(price)],capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    if result.returncode:raise RuntimeError(result.stderr)
    check=json.loads(result.stdout);assert all(f.read_text()=='IMMUTABLE_SYNTHETIC'for f in protected)
    actual=R/'OSProbe/fit-frozen-trainer-exact-outputs.sb';proof={'schema':'FROZEN-FIT-OS-EXACT-OUTPUT-SYNTHETIC-1','status':'PASS_OS_SYSCALL_WRITE_AND_SEALED_READ_CONTROLS','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'profile_sha256':hashlib.sha256(actual.read_bytes()).hexdigest(),'profile_builder_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'fixture_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'actual_sandbox_exec_exercised':True,'controls':check,'synthetic_roots_only':True,'actual_fit_or_real_label_read':False,'original_roots_written':False}
    out=R/'Public/fit-os-profile-synthetic-acceptance.json';out.write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2))
