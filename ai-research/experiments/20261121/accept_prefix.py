"""Additional signal/stop parity and an explicit future-information sentinel.

The sentinel tests the comparison validator, not a deployed model feature.
"""
from native_check import HERE,OLD,read,write,sha
from pathlib import Path

def compare(expected,actual):
    if expected!=actual:raise AssertionError('Prefix information changed')

def main():
    assert read(HERE/'prefix-progress.json')['state']=='complete'
    proofs=[]
    for target in sorted((HERE/'SQX/prefix').iterdir()):
        v=read(target/'verified.json');cutoff=v['cutoff_ns'];old=OLD/'SQX/observer'/target.name
        reference=Path(read(old/'verified.json')['folder'])
        expected=[line for line in (reference/'signal-quotes.csv').read_text().splitlines()
            if line.startswith('signal_ns,') or int(line.split(',')[0])<=cutoff]
        folders=[p for p in target.glob('native_export_*') if (p/'prefix-complete.txt').exists()]
        for folder in folders:compare(expected,(folder/'signal-quotes.csv').read_text().splitlines())
        full_future_count=int((old/'manifest.txt').read_text().splitlines()[1])
        prefix_count=read(target/'prefix-input-proof.json')['callbacks']
        assert full_future_count>prefix_count
        # A column containing the final future input count is intentionally noncausal.
        # Exact prefix comparison must reject it; never used in model fitting.
        rejected=False
        try:compare([r+','+str(full_future_count) for r in expected],[r+','+str(prefix_count) for r in expected])
        except AssertionError:rejected=True
        assert rejected
        proofs.append(dict(segment=target.name,signal_quote_stop_rows=len(expected)-1,
            exact_signal_quote_stop_parity=True,replicas=len(folders),intentional_future_count_column_rejected=True,
            sentinel_scope='validator sensitivity control; not a native trained feature',
            native_prefix_proof_sha256=sha(target/'verified.json')))
    write(HERE/'prefix-additional-acceptance.json',dict(state='passed',strict_cut_decisions=len(proofs),
        total_prefix_parity_rows=sum(p['signal_quote_stop_rows'] for p in proofs),proofs=proofs,
        expanded_random_and_boundary_cut_samples='not yet performed; no universal guarantee'))
    print('Native feature + signal/stop prefix checks passed:',len(proofs),'decision cuts')

if __name__=='__main__':main()
