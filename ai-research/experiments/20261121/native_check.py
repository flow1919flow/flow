"""Isolated native SQX prefix audits and frozen-family gate runs.

No change to the GUI installation, licensed original inputs, or NinjaTrader.
Prefix reports are diagnostic: unfinished trades are not performance results.
"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as ET
from datetime import datetime, timezone, timedelta
import argparse, csv, gzip, hashlib, json, shutil, subprocess, time

HERE = Path(__file__).resolve().parent
DE = HERE.parents[1]
OLD = DE/'outputs/AI-Forschung-20261120'
ROBUST = DE/'outputs/Strategie-Builder-ES-Pilot/hy-vergleich/robustheit'
APP = DE/'work/sqx_ml_20261121/resources'
INSTALLED = Path('/Applications/StrategyQuantXB144_arm.app/Contents/Resources')
NAME = 'HYML1ESResearch'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def write(p, value):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_suffix(p.suffix+'.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n'); temp.replace(p)

def once(text, before, after):
    assert text.count(before) == 1, before
    return text.replace(before, after)

def build():
    if not APP.exists():
        APP.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['cp', '-cR', str(INSTALLED), str(APP)], check=True)
    source = (OLD/'Source'/f'{NAME}.java').read_text()
    anchor = '            try (tape; seeds; trades; sizes; candidateTrades; candidateMarks; nativeRisks; signalQuotes; mlFeatures) {'
    source = once(source, anchor, anchor+'''
                if (Files.exists(result.getParent().resolve("ml-prefix-only.txt"))) {
                    require(seen == expected && tape.readLine() == null && seeds.readLine() == null,
                            "Native prefix did not consume exactly its physical input");
                    require(sizes == null || sizes.readLine() == null, "Unused prefix trade sizes");
                    require(!mlFeatures.checkError(), "Prefix feature output error");
                    Files.writeString(result.resolve("prefix-complete.txt"),seen+"\\n"+previous+"\\n");
                    return; // Diagnostic prefix may end with open positions; never report its PnL.
                }''')
    out = HERE/'Source'/f'{NAME}.java'; out.parent.mkdir(exist_ok=True); out.write_text(source)
    helpers = ['SqxCompletedBarIndicators','SqxSessionVwap','SqxSessionPriceProfile',
               'SqxParametricTpoProfile','SqxExtensionBarIndicators','SqxRollingVwap']
    helper_sources = [ROBUST/(n+'.java') for n in helpers]
    assert all(p.exists() for p in helper_sources), 'Missing frozen helper source'
    classes = HERE/'Classes'; classes.mkdir(exist_ok=True)
    subprocess.run([str(APP/'j64/bin/javac'), '-cp', str(APP/'internal/libs/*'),
        '-d', str(classes), *map(str, helper_sources), str(out)], check=True, timeout=120)
    jar = APP/'internal/libs/Snippets.jar'; temp = jar.with_suffix('.ml21')
    prefixes = tuple('SQ/Blocks/OtherActions/'+n for n in [NAME, *helpers])
    with ZipFile(jar) as src, ZipFile(temp, 'w', ZIP_DEFLATED) as dst:
        for item in src.infolist():
            if not item.filename.startswith(prefixes): dst.writestr(item, src.read(item.filename))
        for p in classes.rglob('*.class'): dst.write(p, p.relative_to(classes).as_posix())
    temp.replace(jar)
    dest = APP/'user/extend/Snippets/SQ/Blocks/OtherActions'/out.name
    dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(out, dest)
    registry = APP/'user/settings/snippets.txt'; key = '$SNIPPETS_USER_DIR$/SQ/Blocks/OtherActions/'+out.name+'|'
    registry.write_text('\n'.join([r for r in registry.read_text().splitlines() if not r.startswith(key)]
        + [key+hashlib.md5(out.read_bytes()).hexdigest()])+'\n')
    write(HERE/'native-source-proof.json', dict(original_sha256=sha(OLD/'Source'/out.name),
        source_sha256=sha(out), helpers={p.name:sha(p) for p in helper_sources},
        only_source_change='finish-time diagnostic prefix branch; feature and trading calculations unchanged',
        installed_application_changed=False, ninja_changed=False, isolated_runtime=str(APP)))

def execute(cli, log):
    started = time.monotonic()
    p = subprocess.run([str(APP/'sqcli'), '-run', 'file='+str(cli)], cwd=APP,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=2400)
    safe = [line for line in p.stdout.splitlines() if any(s in line for s in
        ['SQX version','Running command','All tasks completed','Error','Exception','another instance','Imported','imported'])
        and not any(s in line.lower() for s in ['license','licence','password','token','key:'])]
    Path(log).write_text('\n'.join(safe)+'\n')
    assert p.returncode == 0 and 'All tasks completed' in p.stdout, safe[-12:]
    assert not any(s in p.stdout for s in ['Error:', 'another instance','Cannot start project']), safe[-12:]
    return round(time.monotonic()-started,2)

def prepare(old, target, prefix=None, gate=None):
    target.mkdir(parents=True, exist_ok=True)
    for folder in ['strategies','result_sqx']: (target/folder).mkdir(exist_ok=True)
    for p in old.iterdir():
        if p.is_file() and p.suffix in ('','.csv','.txt','.gz'): shutil.copy2(p,target/p.name)
    if gate is not None: shutil.copy2(gate,target/'ml-decisions.csv')
    template = next((old/'strategies').glob('*.sqx'))
    with ZipFile(template) as z: members={n:z.read(n) for n in z.namelist()}
    for n,b in list(members.items()):
        if n.endswith('.xml'): members[n]=b.replace(str(old).encode(),str(target).encode())
    label = target.parent.name+'_'+old.name
    with ZipFile(target/'strategies'/(label+'.sqx'),'w',ZIP_DEFLATED) as z:
        for n,b in members.items(): z.writestr(n,b)
    with ZipFile(old/'Optimizer.cfx') as z: cfg=z.read('config.xml').replace(str(old).encode(),str(target).encode())
    if prefix:
        cfg = prefix_inputs(old,target,prefix,cfg)
    with ZipFile(target/'Optimizer.cfx','w',ZIP_DEFLATED) as z: z.writestr('config.xml',cfg)
    (target/'run.cli').write_text((old/'run.cli').read_text().replace(str(old),str(target)))
    return target

def prefix_inputs(old,target,cutoff,cfg):
    """Physically remove future tape, sizes, carrier quotes, and session seeds."""
    manifest=(old/'manifest.txt').read_text().splitlines()
    count=trades=0; last_day=-1; last_clock=last_ns=0
    size_stream=gzip.open(old/'trade-sizes.csv.gz','rt')
    source_quotes=Path(manifest[3]).parent/'quotes.csv'
    with gzip.open(manifest[3],'rt') as tape, gzip.open(target/'prefix-tape.csv.gz','wt',compresslevel=1) as out, \
            gzip.open(target/'trade-sizes.csv.gz','wt',compresslevel=1) as sizes, \
            source_quotes.open() as quotes, (target/'prefix-quotes.csv').open('w') as carrier:
        carrier.write(quotes.readline())
        for line in tape:
            fields=line.split(','); ns=int(fields[1])
            if ns>cutoff: break
            quote=quotes.readline(); assert quote, 'Native carrier shorter than tape'
            out.write(line); carrier.write(quote); count+=1
            last_clock=int(fields[0]); last_ns=ns; last_day=int(fields[2])
            if fields[5]=='2':
                size=size_stream.readline(); assert size
                sizes.write(size); trades+=1
    size_stream.close()
    seeds=Path(manifest[2]).read_text().splitlines()
    (target/'prefix-seeds.csv').write_text('\n'.join(seeds[:last_day+1])+'\n')
    manifest[1]=str(count); manifest[2]=str(target/'prefix-seeds.csv'); manifest[3]=str(target/'prefix-tape.csv.gz')
    (target/'manifest.txt').write_text('\n'.join(manifest)+'\n')
    (target/'ml-prefix-only.txt').write_text(str(cutoff)+'\n')
    root=ET.fromstring(cfg)
    symbols={e.get('symbol') for e in root.findall('.//Data/Setups/Setup/Chart')}
    assert len(symbols)==1; original_symbol=symbols.pop(); symbol='MLPREFIX'+old.name.replace('-','').replace('2026','')
    for e in root.findall('.//Data/Setups/Setup'):
        e.set('dateTo',(datetime.fromtimestamp(last_clock/1000,timezone.utc)+timedelta(days=1)).strftime('%Y.%m.%d'))
        for chart in e.findall('Chart'):chart.set('symbol',symbol)
    for p in (target/'strategies').glob('*.sqx'):
        with ZipFile(p) as z: members={n:z.read(n).replace(original_symbol.encode(),symbol.encode()) if n.endswith('.xml') else z.read(n) for n in z.namelist()}
        with ZipFile(p,'w',ZIP_DEFLATED) as z:
            for n,b in members.items():z.writestr(n,b)
    cli=target/'import.cli'
    cli.write_text(f'-instrument action=add instrument={symbol} datatype=futures pointvalue=50 ticksize=0.25 tickstep=0.25 defaultspread=1 minDistance=0 orderSizeMultiplier=1 orderSizeStep=1\n'
        f'-symbol action=add symbols={symbol} instrument={symbol} datasource=file datatype=TICK bartype=startofbar\n'
        f'-data action=import symbol={symbol} filepath="{target / "prefix-quotes.csv"}" format="SQ Tick Downloader" timezone=Etc/UTC timeframe=TICK errorhandling=stop\n')
    write(target/'prefix-input-proof.json',dict(cutoff_ns=cutoff,last_ns=last_ns,callbacks=count,trade_events=trades,
        files={n:sha(target/n) for n in ['prefix-tape.csv.gz','prefix-seeds.csv','trade-sizes.csv.gz','prefix-quotes.csv']},
        physical_future_ticks_removed=True, symbol=symbol))
    return ET.tostring(root)

def run_job(target):
    for bank in ['Strategies to optimize','Results']:
        folder=APP/'user/projects/Optimizer/databanks'/bank; folder.mkdir(parents=True,exist_ok=True)
        for p in folder.glob('*.sqx'):p.unlink()
    dest=APP/'user/projects/Optimizer/databanks/Strategies to optimize'
    for p in (target/'strategies').glob('*.sqx'):shutil.copy2(p,dest/p.name)
    return execute(target/'run.cli',target/'sqx.log')

def prefixes():
    completed=[]
    for old in sorted((OLD/'SQX/observer').iterdir()):
        v=read(old/'verified.json'); native=Path(v['folder'])
        features=list(csv.DictReader((native/'ml-features.csv').open()))
        if not features:
            completed.append(dict(segment=old.name,state='no_candidates_in_full_segment',rows=0));continue
        cutoff=int(features[len(features)//2]['signal_ns'])
        target=HERE/'SQX/prefix'/old.name
        if not (target/'verified.json').exists():
            prepare(old,target,prefix=cutoff)
            execute(target/'import.cli',target/'import.log')
            seconds=run_job(target)
            folders=[p for p in target.glob('native_export_*') if (p/'prefix-complete.txt').exists()]
            assert len(folders)>=2,'Missing native prefix replicas'
            expected=[line for line in (native/'ml-features.csv').read_text().splitlines() if line.startswith('signal_ns,') or int(line.split(',')[0])<=cutoff]
            for p in folders:
                assert (p/'ml-features.csv').read_text().splitlines()==expected,'Future removal changed an earlier feature'
                values=(p/'prefix-complete.txt').read_text().splitlines()
                assert int(values[1])<=cutoff and int(values[0])==read(target/'prefix-input-proof.json')['callbacks']
            write(target/'verified.json',dict(state='native_physical_prefix_identical',segment=old.name,cutoff_ns=cutoff,
                rows=len(expected)-1,replicas=len(folders),seconds=seconds,features_sha256=sha(folders[0]/'ml-features.csv'),
                reference_features_sha256=sha(native/'ml-features.csv'),source_sha256=sha(HERE/'Source'/f'{NAME}.java')))
        completed.append(read(target/'verified.json'))
        write(HERE/'prefix-progress.json',dict(state='running',completed=completed))
        print(old.name,'prefix verified',flush=True)
    write(HERE/'prefix-progress.json',dict(state='complete',completed=completed,
        scope='One intrabar decision-time cutoff per each nonempty segment; five causal features; not a universal proof'))

def gates(arm):
    completed=[]
    for old in sorted((OLD/'SQX/observer').iterdir()):
        target=HERE/'SQX'/arm/old.name
        if not (target/'verified.json').exists():
            prepare(old,target,gate=HERE/'Decisions'/arm/old.name/'ml-decisions.csv')
            stage=DE/'outputs/Micro-RiskSize-20261120/Inputs/ES/Basisdaten'/old.name
            receipt=HERE/'Imports'/f'{old.name}.json'
            if not receipt.exists(): write(receipt,dict(seconds=execute(stage/'import.cli',HERE/'Imports'/f'{old.name}.log')))
            seconds=run_job(target)
            folders=[p for p in target.glob('native_export_*') if (p/'complete.txt').exists()]
            assert len(folders)>=2
            for name in ['trades.csv','candidates.csv','signal-quotes.csv','ml-features.csv']:
                assert len({sha(p/name) for p in folders})==1,name
            reference=read(old/'verified.json'); base=Path(reference['folder']); native=folders[0]
            for name in ['candidates.csv','signal-quotes.csv','ml-features.csv']:
                assert sha(native/name)==sha(base/name),'Gate changed eligible candidates/features: '+name
            write(target/'verified.json',dict(state='native_gate_verified',arm=arm,folder=str(native),seconds=seconds,
                replicas_identical=True,candidates_identical=True,features_sha256=sha(native/'ml-features.csv'),
                trades_sha256=sha(native/'trades.csv'),source_sha256=sha(HERE/'Source'/f'{NAME}.java')))
        completed.append(str(target));write(HERE/f'{arm}-native-progress.json',dict(state='running',completed=completed))
        print(arm,old.name,'native verified',flush=True)
    write(HERE/f'{arm}-native-progress.json',dict(state='complete',completed=completed))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['build','prefix','gates']);parser.add_argument('--arm')
    args=parser.parse_args()
    if args.action=='build': build()
    elif args.action=='prefix': prefixes()
    else:
        assert args.arm in ['ML8','MR1','ML9'];gates(args.arm)
