"""Research-only native SQX observer/gate in a separate cloned runtime.

Reuses licensed local inputs; never installs into NinjaTrader or the SQX GUI.
The observer must reproduce frozen candidate and native trades byte for byte.
"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as E
import argparse, csv, hashlib, json, os, shutil, subprocess, time

DE = Path(os.environ.get('HY_WORKSPACE', Path.cwd())).resolve()
ORIGINAL = DE / 'outputs/Micro-RiskSize-20261120'
HERE = DE / 'outputs/AI-Forschung-20261120'
APP = Path('/private/tmp/sqx-hy-ml1-20261120/resources')
SOURCE_APP = Path('/private/tmp/sqx-hy-current-install.mnqrisk-20261119/resources')
NAME = 'HYML1ESResearch'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())
def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_suffix(p.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n'); temp.replace(p)
def once(s, a, b):
    assert s.count(a) == 1, (a, s.count(a))
    return s.replace(a, b)

def build():
    old = ORIGINAL / 'Source/HYRiskInventoryES.java'
    s = old.read_text().replace('HYRiskInventoryES', NAME)
    s = once(s, 'private final PrintWriter candidateTrades, candidateMarks, nativeRisks, signalQuotes;',
        '''private final PrintWriter candidateTrades, candidateMarks, nativeRisks, signalQuotes, mlFeatures;
        private final Map<Long,Boolean> mlDecisions = new HashMap<>();
        private boolean mlGated = false;
        private long mlVolume = 0;
        private double mlLastEma = Double.NaN, mlPrevEma = Double.NaN, mlClosedAtr = Double.NaN;
        private double mlRelativeVolume = Double.NaN;
        private final Deque<Long> mlVolumes = new ArrayDeque<>();''')
    s = once(s, 'sizes = (extension >= 1 && extension <= 5) || rollingVwap != null || volumeHistory != null',
                  'sizes = true /* research observer consumes the attested trade-size stream */')
    anchor = '            signalQuotes.println("signal_ns,side,quote_ns,bid_ticks,ask_ticks,stop_ticks");'
    s = once(s, anchor, anchor + '''
            mlFeatures = new PrintWriter(Files.newBufferedWriter(result.resolve("ml-features.csv")));
            mlFeatures.println("signal_ns,side,quote_ns,planned_stop_risk_usd,bollinger_keltner_width_ratio,signed_completed_ema_slope_atr,completed_relative_volume20,chicago_session_minute");
            Path decisionFile=directory.resolve("ml-decisions.csv");
            mlGated=Files.isRegularFile(decisionFile);
            if(mlGated) {
                for(String line:Files.readAllLines(decisionFile)) {
                    if(line.startsWith("signal_ns,"))continue;
                    String[] values=line.split(",");
                    require(values.length==2,"Invalid ML decision row");
                    long ns=Long.parseLong(values[0]);
                    require(values[1].equals("0")||values[1].equals("1"),"Invalid ML decision");
                    require(mlDecisions.put(ns,values[1].equals("1"))==null,"Duplicate ML decision");
                }
            }''')
    s = once(s, '            atr = atrAt();', '''            atr = atrAt();
            mlPrevEma=mlLastEma; mlLastEma=ema; mlClosedAtr=atr;
            if(mlVolumes.size()==20) {
                long totalVolume=0; for(long value:mlVolumes)totalVolume+=value;
                mlRelativeVolume=totalVolume>0 ? mlVolume/(totalVolume/20.0) : Double.NaN;
            }
            mlVolumes.addLast(mlVolume);
            if(mlVolumes.size()>20)mlVolumes.removeFirst();''')
    s = once(s, 'if (bar < 0) { bar = slot; open = high = low = print; barVolume = 0; }',
        'if (bar < 0) { bar = slot; open = high = low = print; barVolume = 0; mlVolume=0; }\n            mlVolume+=quantity;')
    anchor = '                        signalQuotes.printf(Locale.ROOT,"%d,%d,%d,%d,%d,%d%n",ns,side,quoteTime,quoteBid,quoteAsk,shadowStop);'
    s = once(s, anchor, anchor + '''
                        double risk=side*((side==1?quoteAsk:quoteBid)-shadowStop)*12.5+4.68+25.0;
                        double bbHalf=(target(last,1)-target(last,-1))/2+targetOffset;
                        double ratio=bbHalf/(contactMultiplier*width);
                        double slope=side*(mlLastEma-mlPrevEma)/mlClosedAtr;
                        require(quoteTime<=ns && risk>0 && Double.isFinite(ratio) && Double.isFinite(slope)
                            && Double.isFinite(mlRelativeVolume),"Incomplete causal ML feature state");
                        mlFeatures.printf(Locale.ROOT,"%d,%d,%d,%.17g,%.17g,%.17g,%.17g,%.17g%n",ns,side,
                            quoteTime,risk,ratio,slope,mlRelativeVolume,(ns-dayOpen)/(60.0*SECOND));''')
    s = once(s, '                            intent = new Intent(side, ns, candidate, "first_return");',
        '''                            if(mlGated)require(mlDecisions.containsKey(ns),"Missing precomputed chronological ML decision");
                            if(!mlGated || mlDecisions.get(ns))intent = new Intent(side, ns, candidate, "first_return");''')
    s = once(s, 'nativeRisks; signalQuotes) {', 'nativeRisks; signalQuotes; mlFeatures) {')
    s = once(s, 'require(!trades.checkError(), "Could not write trades");',
        'require(!trades.checkError() && !mlFeatures.checkError(), "Could not write trades/features");')
    source = HERE / 'Source' / (NAME + '.java'); source.parent.mkdir(exist_ok=True)
    source.write_text(s)
    if not APP.is_dir():
        APP.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['cp', '-cR', str(SOURCE_APP), str(APP)], check=True)
    classes = HERE / 'Classes'; classes.mkdir(exist_ok=True)
    subprocess.run([str(APP/'j64/bin/javac'), '-cp', str(APP/'internal/libs/*'), '-d', str(classes), str(source)], check=True)
    jar = APP / 'internal/libs/Snippets.jar'; temp = jar.with_suffix('.ml1')
    with ZipFile(jar) as src, ZipFile(temp, 'w', ZIP_DEFLATED) as out:
        for info in src.infolist():
            if not info.filename.startswith('SQ/Blocks/OtherActions/' + NAME):
                out.writestr(info, src.read(info.filename))
        for p in classes.rglob('*.class'): out.write(p, p.relative_to(classes).as_posix())
    temp.replace(jar)
    dest = APP / 'user/extend/Snippets/SQ/Blocks/OtherActions' / source.name
    shutil.copy2(source, dest)
    registry = APP / 'user/settings/snippets.txt'
    prefix = '$SNIPPETS_USER_DIR$/SQ/Blocks/OtherActions/' + source.name + '|'
    registry.write_text('\n'.join([line for line in registry.read_text().splitlines() if not line.startswith(prefix)] +
        [prefix + hashlib.md5(source.read_bytes()).hexdigest()]) + '\n')
    proof = dict(source_sha256=sha(source), original_source_sha256=sha(old),
                 snippet_jar_sha256=sha(jar), observer_only_unless_decisions_present=True,
                 separate_runtime=str(APP), trading_installation_changed=False)
    write(HERE / 'source-proof.json', proof)

def prepare(old, gated):
    mode = 'gated' if gated else 'observer'
    target = HERE / 'SQX' / mode / old.name; target.mkdir(parents=True, exist_ok=True)
    for name in ('strategies', 'result_sqx'): (target / name).mkdir(exist_ok=True)
    for p in old.iterdir():
        if p.is_file() and p.suffix in ('', '.csv', '.txt'):
            shutil.copy2(p, target / p.name)
    volume = DE/'outputs/Strategie-Builder-ES-Pilot/hy-vergleich/robustheit/SQX-Strategieerweiterungen/Volumen'/old.name/'trade-sizes.csv.gz'
    assert volume.is_file()
    shutil.copy2(volume, target/'trade-sizes.csv.gz')
    if gated: shutil.copy2(HERE/'Decisions'/old.name/'ml-decisions.csv', target/'ml-decisions.csv')
    template = next((old/'strategies').glob('*.sqx'))
    with ZipFile(template) as z: members = {n:z.read(n) for n in z.namelist()}
    for name, content in list(members.items()):
        if name.endswith('.xml'):
            members[name] = content.replace(str(old).encode(), str(target).encode()).replace(b'HYRiskInventoryES', NAME.encode())
    label = 'ML1_ES_' + mode + '_' + old.name
    with ZipFile(target/'strategies'/(label+'.sqx'), 'w', ZIP_DEFLATED) as z:
        for name, content in members.items(): z.writestr(name, content)
    with ZipFile(old/'Optimizer.cfx') as z:
        cfg = z.read('config.xml').replace(str(old).encode(), str(target).encode())
    with ZipFile(target/'Optimizer.cfx', 'w', ZIP_DEFLATED) as z: z.writestr('config.xml', cfg)
    (target/'run.cli').write_text((old/'run.cli').read_text().replace(str(old), str(target)))
    write(target/'prepared.json', dict(reference=str(old/'verified.json'), reference_sha256=sha(old/'verified.json'),
        source_sha256=sha(HERE/'Source'/(NAME+'.java')), volume_sha256=sha(volume),
        decisions_sha256=sha(target/'ml-decisions.csv') if gated else None))
    return target

def execute(target, gated):
    for name in ('Strategies to optimize', 'Results'):
        folder = APP/'user/projects/Optimizer/databanks'/name
        folder.mkdir(parents=True, exist_ok=True)
        for p in folder.glob('*.sqx'): p.unlink()
    for p in (target/'strategies').glob('*.sqx'):
        shutil.copy2(p, APP/'user/projects/Optimizer/databanks/Strategies to optimize'/p.name)
    started = time.monotonic()
    proc = subprocess.run([str(APP/'sqcli'), '-run', 'file='+str(target/'run.cli')], cwd=APP,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=1800)
    safe = [line for line in proc.stdout.splitlines() if any(token in line for token in
        ('SQX version', 'Running command', 'All tasks completed', 'Error', 'Exception', 'another instance'))
        and not any(token in line.lower() for token in ('license', 'licence', 'password', 'token', 'key:'))]
    log = target/'sqx.log'
    if log.exists():
        shutil.copy2(log, target/('sqx-attempt-'+str(time.time_ns())+'.log'))
    log.write_text('\n'.join(safe)+'\n')
    assert proc.returncode == 0 and 'All tasks completed' in proc.stdout and not any(x in proc.stdout for x in (' Error '+NAME+':', 'Error:', 'another instance', 'Cannot start project')), safe[-10:]
    verify(target, gated, round(time.monotonic()-started, 2))

def verify(target, gated, seconds=None):
    old = Path(read(target/'prepared.json')['reference']); reference = read(old)
    folders = [p for p in target.glob('native_export_*') if (p/'complete.txt').is_file()]
    assert len(folders) >= 2
    for name in ('trades.csv', 'candidates.csv', 'signal-quotes.csv', 'ml-features.csv'):
        assert len({sha(p/name) for p in folders}) == 1, name
    native = folders[0]
    assert sha(native/'candidates.csv') == reference['candidate_sha256']
    assert sha(native/'signal-quotes.csv') == reference['signal_sha256']
    if not gated: assert sha(native/'trades.csv') == reference['native_sha256']
    feature_rows = list(csv.DictReader((native/'ml-features.csv').open()))
    assert len(feature_rows) == reference['candidates']
    assert all(int(r['quote_ns']) <= int(r['signal_ns']) for r in feature_rows)
    assert len(list((target/'result_sqx').glob('*.sqx'))) >= 2
    receipt = dict(state='native_gate_verified' if gated else 'native_observer_parity_verified',
        folder=str(native), seconds=seconds, feature_rows=len(feature_rows),
        source_sha256=sha(HERE/'Source'/(NAME+'.java')), original_native_trades_identical=not gated,
        candidates_identical=True, replicas_identical=True,
        features_sha256=sha(native/'ml-features.csv'), trades_sha256=sha(native/'trades.csv'))
    write(target/'verified.json', receipt)
    print(target.name, receipt['state'], receipt['seconds'], flush=True)

def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--gated', action='store_true')
    parser.add_argument('--prepare-only', action='store_true'); args = parser.parse_args()
    HERE.mkdir(exist_ok=True); build()
    completed = []
    for old in sorted((ORIGINAL/'SQX/ES/MFF/funded').iterdir()):
        if not (old/'verified.json').is_file(): continue
        prior_target = HERE/'SQX'/('gated' if args.gated else 'observer')/old.name
        previous = read(prior_target/'prepared.json') if (prior_target/'prepared.json').exists() else None
        target = prepare(old, args.gated)
        if not args.prepare_only and not (target/'verified.json').exists():
            try:
                complete = [p for p in target.glob('native_export_*') if (p/'complete.txt').exists()]
                if previous == read(target/'prepared.json') and len(complete)>=2:
                    verify(target, args.gated)
                else:
                    execute(target, args.gated)
            except Exception as exc:
                write(HERE/'observer-progress.json', dict(state='failed', gated=args.gated,
                    completed=completed, failed_segment=old.name, error_type=type(exc).__name__))
                raise
        completed.append(str(target)); write(HERE/'observer-progress.json', dict(state='running', gated=args.gated, completed=completed))
    write(HERE/'observer-progress.json', dict(state='prepared' if args.prepare_only else 'complete', gated=args.gated, completed=completed))

if __name__ == '__main__': main()
