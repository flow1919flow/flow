"""Exact-output write allowlist for the unchanged frozen trainer; no execution."""
from pathlib import Path
import json,re
PUBLIC=['development-strategy-baseline.json','futility-stop.json','models-frozen.json']
PRIVATE=['training-attempt.json','Ridge.joblib','Boosting.joblib','Ridge-state.json','Boosting-state.json','Ridge-cross-predictions.json','Boosting-cross-predictions.json']
def allowed_paths(learning):
    out=[learning/'Public',learning/'Private']
    for folder,names in [('Public',PUBLIC),('Private',PRIVATE)]:
        for name in names:
            p=learning/folder/name;out.append(p)
            if name.endswith('.json')and name!='training-attempt.json':out.append(p.with_suffix(p.suffix+'.tmp'))
    return out

def profile(data,learning):
    quote=lambda p:json.dumps(str(Path(p).resolve()))
    lines=['(version 1)','(allow default)','(deny file-write*)','(allow file-write*']
    lines += ['  (literal '+quote(p)+')'for p in allowed_paths(learning)]
    lines += [')','(deny network*)','(deny file-read* (regex '+json.dumps('^'+re.escape(str((data/'Private').resolve()))+'/sealed-')+'))']
    return '\n'.join(lines)+'\n'
if __name__=='__main__':
    root=Path(__file__).resolve().parents[1];data=root.parent/'ES-FiveYear-SecondData-20261121';learning=root.parent/'ES-FiveYear-ML-20261121';out=root/'OSProbe/fit-frozen-trainer-exact-outputs.sb'
    with out.open('x')as f:f.write(profile(data,learning))
    print(out)
