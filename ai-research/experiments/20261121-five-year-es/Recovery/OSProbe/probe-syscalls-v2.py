from pathlib import Path
import hashlib,json,os
root=Path(__file__).parent
source=root/'input/sentinel.txt';prior=hashlib.sha256(source.read_bytes()).hexdigest();denials={}
operations={'open_truncate':lambda:os.close(os.open(source,os.O_WRONLY|os.O_TRUNC)),'unlink':lambda:os.unlink(source),'rename_out_of_input':lambda:os.rename(source,root/'output/stolen.txt')}
for name,operation in operations.items():
    try:operation()
    except PermissionError as error:denials[name]={'errno':error.errno,'OS_denied':True}
    else:raise RuntimeError('OS protection failed: '+name)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==prior
allowed=root/'output/positive-control.txt';allowed.write_text('allowed\n')
with allowed.open('a') as stream:stream.write('append\n')
renamed=root/'output/positive-renamed.txt';os.rename(allowed,renamed);os.unlink(renamed)
result={'status':'PASS_OS_READONLY_OPEN_TRUNCATE_UNLINK_RENAME','denials':denials,'allowed_output_create_append_rename_unlink':True,'input_preimage_sha256':prior,'profile_sha256':hashlib.sha256((root/'readonly-originals.sb').read_bytes()).hexdigest(),'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'real_market_or_strategy_inputs_accessed':False,'signals_labels_recovery_or_fit':False}
(root/'output/result-syscalls-v2.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
