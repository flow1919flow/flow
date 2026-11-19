from pathlib import Path
import ast, dataclasses, hashlib, json, random, subprocess
from datetime import date
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
ROBUST=ROOT/'Strategie-Builder-ES-Pilot/hy-vergleich/robustheit'
SDK=Path('/private/tmp/es-tickzeit-dotnet')

def load_td():
    src=ROBUST/'sqx_tradeday_fast_pass_accounts.py'; tree=ast.parse(src.read_text()); ns={}
    for n in tree.body:
        if isinstance(n,ast.Assign):
            try:v=ast.literal_eval(n.value)
            except (TypeError,ValueError):continue
            for t in n.targets:
                if isinstance(t,ast.Name):ns[t.id]=v
    nodes=[n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in ('FastPassAccount','consistent')]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(src),'exec'),ns)
    ns['elapsed']=lambda a,b:(date.fromisoformat(b)-date.fromisoformat(a)).days
    return ns,src

def compile_and_run():
    refs=SDK/'packs/Microsoft.NETCore.App.Ref/8.0.34/ref/net8.0'
    exe=HERE/'AccountHarness.dll'
    cmd=[str(SDK/'dotnet'),str(SDK/'sdk/8.0.428/Roslyn/bincore/csc.dll'),'/nologo','/warn:4','/langversion:7.3','/target:exe','/out:'+str(exe)]
    cmd += ['/r:'+str(p) for p in refs.glob('*.dll')]
    cmd += [str(HERE/'AccountHarness.cs'),str(HERE.parent/'Strategies/HYAccountReplayV8.cs')]
    r=subprocess.run(cmd,capture_output=True,text=True);(HERE/'compile.log').write_text(r.stdout+r.stderr)
    assert r.returncode==0,r.stdout+r.stderr
    exe.with_suffix('.runtimeconfig.json').write_text(json.dumps({'runtimeOptions':{'tfm':'net8.0','framework':{'name':'Microsoft.NETCore.App','version':'8.0.34'}}}))
    r=subprocess.run([str(SDK/'dotnet'),str(exe),str(HERE/'scenarios.json')],capture_output=True,text=True)
    (HERE/'run.log').write_text(r.stderr);assert r.returncode==0,r.stdout+r.stderr
    (HERE/'actual-results.jsonl').write_text(r.stdout)
    return [json.loads(x) for x in r.stdout.splitlines()],r.stderr

def scenarios():
    rows=[]
    for profile in ('TradeDayEvaluation','TradeDayFunded','MffEvaluation','MffFunded'):
        nq=profile.startswith('TradeDay');rng=random.Random(491)
        for name,pattern in [('steady',[120]*25),('mixed',[100,-120,80,-80,160,40,0,100,120,80]*3),
                             ('loss',[-500]*4),('payout',[300]*30),('inactive',[0]*35),
                             ('random',[rng.randrange(-240,300) for _ in range(40)])]:
            days=[]
            for i,ticks in enumerate(pattern):
                days.append({'offset':i,'halfday':i%9==3,'trades':[] if ticks==0 else
                    [{'ticks':ticks,'adverse':max(1,-ticks) if ticks<0 else 1,'side':1 if i%2 else -1}]})
            rows.append({'key':profile+'-'+name,'profile':profile,'days':days})
        rows.append({'key':profile+'-intraday-recovery','profile':profile,'days':[
            {'offset':0,'halfday':False,'trades':[{'ticks':200,'adverse':450 if nq else 180,'side':-1}]}]})
        rows.append({'key':profile+'-multiple-trades','profile':profile,'days':[
            {'offset':i,'halfday':False,'trades':[{'ticks':80,'adverse':4,'side':1},
                {'ticks':-50,'adverse':50,'side':-1},{'ticks':100,'adverse':6,'side':1}]} for i in range(12)]})
    (HERE/'scenarios.json').write_text(json.dumps(rows,indent=2)+'\n')

def main():
    scenarios();actual,structural=compile_and_run();td,tdsrc=load_td()
    # Pure standard-library replay modules: no project imports or backtest launch.
    mffsrc=ROBUST/'sqx_mff_payout_rules.py';mff={'__name__':'oracle_mff_rules'}
    sys.modules['oracle_mff_rules']=type(sys)('oracle_mff_rules');mff=sys.modules['oracle_mff_rules'].__dict__
    exec(compile(mffsrc.read_text(),str(mffsrc),'exec'),mff)
    evalsrc=ROOT/'MFFU-HY18b-ES-v1/konten.py';mod=type(sys)('oracle_mff_eval');sys.modules[mod.__name__]=mod
    exec(compile('from __future__ import annotations\n'+evalsrc.read_text(),str(evalsrc),'exec'),mod.__dict__)
    comparisons=[]
    for row in actual:
        profile=row['profile'];results=row['results'];first=results[0]['day']
        if profile.startswith('TradeDay'):
            state=td['FastPassAccount'](first)
            phase=1 if profile.endswith('Evaluation') else 2
            if phase==2:state.passed='2026-11-18';state.funded_start=first
            for r in results:
                p=state.begin_day(r['day'])
                if p:state.trade_day(r['day'],p,(r['net'],r['low'],r['count']))
                status=state.status
                assert r['breached']==(status in ('max_loss_breached','funded_breached')),(row['key'],r,status)
                if r['passed']:
                    assert state.passed==r['day'];break
                if r['review']:
                    assert status=='sim_to_live_review';break
                if r['terminal']:
                    assert status in ('inactive_model','funded_inactive');break
                if not r['breached']:
                    assert (r['balance'],r['high'],r['floor'],r['paid'],r['payouts'])==(state.balance,state.high,state.limit,
                        sum(p['net_cents'] for p in state.payouts),len(state.payouts)),(row['key'],r,state.__dict__)
                comparisons.append((row['key'],r['day'],'exact TradeDay account state/status'))
        elif profile=='MffEvaluation':
            days={('rapid',r['day']):{'status':'complete','path':r['path'],'trades':[{}]*r['count'],'net_cents':r['net'],'dll_ns':None} for r in results}
            for stop,r in enumerate(results):
                window={'start':first,'end':r['day'],'days':[q['day'] for q in results[:stop+1]]}
                out=mod.evaluate(mod.PROFILES[0],window,days)
                assert r['breached']==(out['status']=='max_loss_breached'),(row['key'],r,out)
                assert r['passed']==(out['status']=='model_passed'),(row['key'],r,out)
                assert bool(r['terminal'])==(out['status']=='inactive_model'),(row['key'],r,out)
                if r['terminal']:assert out['status']=='inactive_model'
                if not r['breached']:
                    assert (r['balance'],r['floor'])==(out['terminal_cash_cents']-mod.START,out['terminal_floor_cents']-mod.START),(row['key'],r,out)
                comparisons.append((row['key'],r['day'],'exact MFF evaluation balance/floor/status'))
        else:
            sessions=['2026-11-18']+[r['day'] for r in results]
            # C# fixture ticks are ET. Convert them to UTC nanoseconds for the original payout clock.
            from datetime import datetime
            from zoneinfo import ZoneInfo
            epoch_ticks=621355968000000000
            def ns(ticks):
                seconds=(ticks-epoch_ticks)/10**7
                local=datetime.fromtimestamp(seconds,ZoneInfo('UTC')).replace(tzinfo=ZoneInfo('America/New_York'))
                return round(local.timestamp()*10**9)
            paths={r['day']:{'status':'complete','path':[[ns(q[0]),*q[1:]] for q in r['path']],
                            'net_cents':r['net'],'trades':[{}]*r['count']} for r in results}
            for i,r in enumerate(results):
                out=mff['replay_funded'](mff['RAPID_EOD'],'2026-11-18',sessions[:i+2],paths)
                assert r['breached']==(out['status']=='funded_breached'),(row['key'],r,out)
                assert bool(r['terminal'])==(out['status']=='funded_inactive'),(row['key'],r,out)
                if r['terminal']:assert out['status']=='funded_inactive'
                if not r['breached']:
                    assert (r['balance'],r['floor'],r['paid'],r['payouts'])==(out['ending_funded_balance_cents'],out['ending_floor_cents'],sum(p['net_cents'] for p in out['payouts']),len(out['payouts'])),(row['key'],r,out)
                comparisons.append((row['key'],r['day'],'exact MFF funded balance/floor/payouts/status'))
    proof={'status':'PASS_EXACT_ACCOUNT_ORACLES_AND_COMPILED_STORAGE_TESTS_NOT_NATIVE',
           'structural':structural.strip(),'scenarios':len(actual),'day_comparisons':len(comparisons),
           'oracle_sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (tdsrc,mffsrc,evalsrc)},
           'scope':'Compiled actual C# book/store and unmodified saved Python account oracles on explicit fixtures. No native NinjaTrader or raw-tick parity claim.',
           'comparisons':comparisons}
    (HERE.parent/'evidence/account-tests.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({k:v for k,v in proof.items() if k not in ('comparisons','oracle_sources')},indent=2))

if __name__=='__main__':main()
