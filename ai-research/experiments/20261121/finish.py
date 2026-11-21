"""Resume native/cash completion while fixed null draws run independently."""
from pathlib import Path
import subprocess, time
from native_check import HERE, DE, read, write, gates
from run import PY, ENV, ARMS, step
CASH_PY=DE/'work/research_runtime/.venv/bin/python'

def main():
    while True:
        status = read(HERE/'native-first-three-status.json')
        assert status['state'] != 'failed', status
        if status['state'] == 'complete': break
        write(HERE/'run-status.json',dict(state='running',phase='awaiting-first-three-native-lock'))
        time.sleep(10)
    for arm in ARMS:
        write(HERE/'run-status.json',dict(state='running',phase='native-'+arm))
        gates(arm)
    if not (HERE/'Cash/results.json').exists(): step('cash',[CASH_PY,HERE/'replay.py'])
    while not (HERE/'Controls/family-null.json').exists():
        write(HERE/'run-status.json',dict(state='running',phase='awaiting-family-null'))
        time.sleep(10)
    assert read(HERE/'Controls/family-null.json')['state']=='complete'
    for arm in ['Controls', *ARMS]: step('track-complete-'+arm,[PY,HERE/'track.py',arm])
    step('report',[PY,HERE/'make_report.py'])
    write(HERE/'run-status.json',dict(state='complete',native_gate_jobs=24,fresh_OOS=False,live_changes=False))
    print('ALL FIXED COMPARISONS COMPLETE',flush=True)

if __name__=='__main__':
    try: main()
    except Exception as e:
        write(HERE/'run-status.json',dict(state='failed',error_type=type(e).__name__,message=str(e)))
        raise
