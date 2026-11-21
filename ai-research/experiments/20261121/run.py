"""Execute authorized fixed comparisons and actual native/cash evidence."""
from pathlib import Path
import os,subprocess,time,traceback
from native_check import HERE,DE,read,write,gates

PY=DE/'work/tools/mlflow/.venv/bin/python'
TP=DE/'work/tools/tabpfn/.venv/bin/python'
CASH_PY=DE/'work/research_runtime/.venv/bin/python'
ENV={**os.environ,'HY_WORKSPACE':str(DE),'MLFLOW_DISABLE_AGENT_HINT':'1',
    'SKB_DATA_DIRECTORY':str(DE/'work/tools/tabpfn/skrub-data'),
    'MPLCONFIGDIR':str(DE/'work/tools/tabpfn/matplotlib'),
    'HF_HUB_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1','DO_NOT_TRACK':'1',
    'TABPFN_MODEL_CACHE_DIR':str(HERE/'Models'),'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
ARMS=['ML1C','ML8','MR1','ML9']

def step(phase,command,timeout=14400):
    write(HERE/'run-status.json',dict(state='running',phase=phase,at=time.time()))
    print('START',phase,flush=True)
    with (HERE/(phase+'.log')).open('w') as log:
        subprocess.run(list(map(str,command)),cwd=DE,env=ENV,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=timeout)
    print('DONE',phase,flush=True)

def main():
    assert read(HERE/'Controls/results.json')['state']=='complete'
    assert read(HERE/'prefix-progress.json')['state']=='complete'
    step('prefix-additional',[PY,HERE/'accept_prefix.py'])
    for arm in ARMS:
        result=HERE/'Training'/arm/'results.json'
        if not result.exists():
            step('track-start-'+arm,[PY,HERE/'track.py',arm])
            step('train-'+arm,[TP,HERE/'research.py','fit','--arm',arm])
        step('track-trained-'+arm,[PY,HERE/'track.py',arm])
    null_log=(HERE/'family-null.log').open('w')
    null=None
    if not (HERE/'Controls/family-null.json').exists():
        null=subprocess.Popen([str(TP),str(HERE/'research.py'),'permutations'],cwd=DE,env=ENV,stdout=null_log,stderr=subprocess.STDOUT)
    first_three=HERE/'native-first-three-status.json'
    while first_three.exists() and read(first_three)['state']!='complete':
        assert read(first_three)['state']!='failed',read(first_three)
        write(HERE/'run-status.json',dict(state='running',phase='awaiting-first-three-native-lock'))
        time.sleep(10)
    for arm in ARMS:
        write(HERE/'run-status.json',dict(state='running',phase='native-'+arm))
        print('START native-'+arm,flush=True);gates(arm);print('DONE native-'+arm,flush=True)
    if not (HERE/'Cash/results.json').exists():step('cash',[CASH_PY,HERE/'replay.py'])
    if null is not None:
        write(HERE/'run-status.json',dict(state='running',phase='awaiting-family-null'))
        assert null.wait(timeout=14400)==0,'Family null pipeline failed; inspect family-null.log'
    null_log.close()
    for arm in ARMS:step('track-complete-'+arm,[PY,HERE/'track.py',arm])
    write(HERE/'run-status.json',dict(state='complete',native_gate_jobs=24,fresh_OOS=False,live_changes=False))
    print('ALL FIXED MODEL COMPARISONS COMPLETE',flush=True)

if __name__=='__main__':
    try:main()
    except Exception as e:
        write(HERE/'run-status.json',dict(state='failed',error_type=type(e).__name__,message=str(e)))
        raise
