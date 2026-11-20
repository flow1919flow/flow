"""New SQX gate fills -> frozen quote-equity reader -> unchanged account model."""
from pathlib import Path
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor
import gzip, hashlib, json, os, subprocess, sys

DE=Path(os.environ.get('HY_WORKSPACE',Path.cwd())).resolve()
HERE=DE/'outputs/AI-Forschung-20261120'
OLD=DE/'outputs/Micro-RiskSize-20261120'
sys.path.insert(0,str(OLD))
import financial_matrix as engine
import sqx_offene_equity as equity

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,value):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,indent=2)+'\n')

def main():
    segments=sorted((HERE/'SQX/gated').iterdir())
    assert len(segments)==6
    inputs={}
    for segment in segments:
        gate=read(segment/'verified.json');assert gate['state']=='native_gate_verified'
        observer=read(HERE/'SQX/observer'/segment.name/'verified.json')
        assert gate['features_sha256']==observer['features_sha256'], 'Entry gating changed past feature states'
        inputs[segment.name]={'base':Path(observer['folder'])/'trades.csv','ML1':Path(gate['folder'])/'trades.csv'}
    source=engine.old.ROBUST/'sqx_equity_paths.cpp'
    design=dict(state='written_before_cash',date_range=[engine.DATES[0],engine.DATES[-1]],
        budget_usd=1000,scoring_sessions=242,starts=143,horizon_sessions=100,
        plan='MFF Rapid EOD 50k',evaluation='frozen HY104 EMA22 in both arms',
        funded=['frozen C28.03','C28.03 with first chronological L2-logit entry gate'],
        training_period_behavior='No model decision before first out-of-time block; baseline accepted entries during first80+gap sessions.',
        sources={str(p.relative_to(DE)):sha(p) for p in [Path(__file__),OLD/'financial_matrix.py',
            OLD/'path_supplier.py',OLD/'provider_generators.py',source,HERE/'Training/results.json']},
        fill_sources={s:{k:sha(p) for k,p in files.items()} for s,files in inputs.items()},
        claim='One prespecified model; no random omission/permutation robustness acceptance or fresh OOS. No leaderboard promotion.')
    write(HERE/'Cash/design-before-results.json',design)
    raw={'base':{},'ML1':{}}
    equity.PILOT=engine.old.PILOT
    with TemporaryDirectory(prefix='ml1-equity-') as tmp:
        folder=Path(tmp);exe=folder/'paths'
        subprocess.run(['clang++','-O3','-std=c++17',str(source),'-lz','-o',str(exe)],check=True)
        def one(segment):
            return equity.calculate(exe,segment,folder,inputs[segment],dict.fromkeys(('base','ML1'),(0,0)))
        with ThreadPoolExecutor(2) as pool:
            for group in pool.map(one,inputs):
                for arm,days in group.items():
                    assert not raw[arm].keys() & days.keys()
                    raw[arm].update(days)
    study=engine.Study('MES','rapid_eod_50k','native',False,'price-memory')
    ref=read(OLD/'Results-r3/MES/rapid_eod_50k/native/results.json')
    results={}
    for label,stress in [('normal',0),('stress',1)]:
        results[label]={}
        original=study.mini[stress]['funded']
        for arm in ('base','ML1'):
            paths={d:engine.adjust_path(raw[arm][d],study.meta[d],stress,0,tick_cents=1250) for d in engine.DATES}
            if arm=='base':
                assert json.dumps(paths,sort_keys=True)==json.dumps(original,sort_keys=True), 'Reconstructed baseline differs from accepted R3 quote paths'
            study.mini[stress]['funded']=paths
            runs=[study.run(i,dict(evaluation='mini1',funded='mini1'),stress,arm) for i in range(143)]
            engine.packed(HERE/'Cash'/(label+'--'+arm+'.json.gz'),runs)
            summary=engine.stats_summary(runs)
            if arm=='base':
                expected=ref['results'][label]['mini1__mini1']
                assert all(expected[k]==v for k,v in summary.items()), 'Full baseline cash differs from frozen R3'
                assert set(expected)-set(summary)=={'mean_delta_from_mini_usd','median_delta_from_mini_usd'}
            results[label][arm]=summary
    output=dict(state='complete_development_comparison',design=design,results=results,
        original_account_counterchecks=study.counterchecks,
        native_gate_segments=6,no_fresh_OOS=True,no_leaderboard_change=True)
    for label in results:
        output['results'][label]['delta_mean_usd']=round(results[label]['ML1']['mean_end_cash_usd']-results[label]['base']['mean_end_cash_usd'],2)
        output['results'][label]['delta_median_usd']=round(results[label]['ML1']['median_end_cash_usd']-results[label]['base']['median_end_cash_usd'],2)
    write(HERE/'Cash/results.json',output)
    print(json.dumps({k:{a:{m:v[m] for m in ('mean_end_cash_usd','median_end_cash_usd')} for a,v in r.items() if isinstance(v,dict)} for k,r in results.items()},indent=2))

if __name__=='__main__':main()
