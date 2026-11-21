"""Native gate fills -> original quote-equity reader -> unchanged provider model."""
from pathlib import Path
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor
import json, subprocess, sys
from native_check import HERE,DE,OLD,read,write,sha

PRIOR=DE/'outputs/Micro-RiskSize-20261120'
sys.path.insert(0,str(PRIOR))
import financial_matrix as engine
import sqx_offene_equity as equity

ARMS=['base','ML1C','ML8','MR1','ML9']

def main():
    inputs={}
    for p in sorted((OLD/'SQX/observer').iterdir()):
        base=read(p/'verified.json');inputs[p.name]={'base':Path(base['folder'])/'trades.csv'}
        for arm in ARMS[1:]:
            gate=read(HERE/'SQX'/arm/p.name/'verified.json')
            assert gate['state']=='native_gate_verified' and gate['features_sha256']==base['features_sha256']
            inputs[p.name][arm]=Path(gate['folder'])/'trades.csv'
    source=engine.old.ROBUST/'sqx_equity_paths.cpp'
    write(HERE/'Cash/design-before-results.json',dict(preregister_sha256=sha(HERE/'preregister.json'),
        budget_usd=1000,sessions=242,horizon_sessions=100,overlapping_starts=143,plan='MFF Rapid EOD50k',
        evaluation='HY104EMA22, same in all arms',funded=ARMS,
        sources={str(p.relative_to(DE)):sha(p) for p in [Path(__file__),PRIOR/'financial_matrix.py',PRIOR/'provider_generators.py',source]},
        native_fills={s:{a:sha(p) for a,p in arms.items()} for s,arms in inputs.items()},
        fresh_OOS=False,no_leaderboard_promotion=True))
    raw={a:{} for a in ARMS};equity.PILOT=engine.old.PILOT
    with TemporaryDirectory(prefix='ml21-quote-paths-') as tmp:
        folder=Path(tmp);exe=folder/'paths'
        subprocess.run(['clang++','-O3','-std=c++17',str(source),'-lz','-o',str(exe)],check=True)
        def one(segment):return equity.calculate(exe,segment,folder,inputs[segment],dict.fromkeys(ARMS,(0,0)))
        with ThreadPoolExecutor(2) as pool:
            for segment,group in zip(inputs,pool.map(one,inputs),strict=True):
                for arm,days in group.items():
                    assert not raw[arm].keys() & days.keys();raw[arm].update(days)
                print('Quote paths complete',segment,flush=True)
    study=engine.Study('MES','rapid_eod_50k','native',False,'price-memory')
    ref=read(PRIOR/'Results-r3/MES/rapid_eod_50k/native/results.json')
    results={}
    for label,stress in [('normal',0),('stress',1)]:
        results[label]={};original=study.mini[stress]['funded']
        for arm in ARMS:
            paths={d:engine.adjust_path(raw[arm][d],study.meta[d],stress,0,tick_cents=1250) for d in engine.DATES}
            if arm=='base':assert json.dumps(paths,sort_keys=True)==json.dumps(original,sort_keys=True),'Frozen baseline quote path mismatch'
            study.mini[stress]['funded']=paths
            runs=[study.run(i,dict(evaluation='mini1',funded='mini1'),stress,arm) for i in range(143)]
            engine.packed(HERE/'Cash'/(label+'--'+arm+'.json.gz'),runs)
            summary=engine.stats_summary(runs)
            if arm=='base':
                expected=ref['results'][label]['mini1__mini1']
                assert all(expected[k]==v for k,v in summary.items()),'Accepted baseline cash mismatch'
            results[label][arm]=summary
            write(HERE/'Cash/progress.json',dict(state='running',cost=label,completed_arm=arm))
            print(label,arm,summary['mean_end_cash_usd'],summary['median_end_cash_usd'],flush=True)
    output=dict(state='complete_native_gate_and_original_cash_comparison',results=results,
        original_account_counterchecks=study.counterchecks,preregister_sha256=sha(HERE/'preregister.json'),
        baseline_reproduced_exactly=True,fresh_OOS=False,leaderboard_changed=False,ninja_changed=False)
    write(HERE/'Cash/results.json',output);write(HERE/'Cash/progress.json',dict(state='complete'))

if __name__=='__main__':main()
