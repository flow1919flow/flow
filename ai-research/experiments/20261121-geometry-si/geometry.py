"""One registered causal geometry measurement in an isolated native SQX runtime.

An observer only. No fitted model, gate change, financial replay or live edits.
"""
from pathlib import Path
from collections import defaultdict
from zipfile import ZipFile, ZIP_DEFLATED
from datetime import datetime,timezone
import csv,gzip,hashlib,importlib.util,json,shutil,subprocess,sys
import numpy as np
from scipy.stats import spearmanr

HERE=Path(__file__).resolve().parent;DE=HERE.parents[1]
PRIOR=DE/'outputs/AI-Forschung-20261121'
sys.path.insert(0,str(PRIOR))
import native_check as native
OLD=native.OLD
APP=DE/'work/sqx_geometry_20261121/resources'

def read(p):return json.loads(Path(p).read_text())
def write(p,j):native.write(p,j)
def sha(p):return native.sha(p)
def once(text,a,b):assert text.count(a)==1,a;return text.replace(a,b)

def source_and_plan():
    original=PRIOR/'Source/HYML1ESResearch.java'
    text=original.read_text()
    text=once(text,'nativeRisks, signalQuotes, mlFeatures;',
        'nativeRisks, signalQuotes, mlFeatures, geometryFeatures;')
    text=once(text,'            Path decisionFile=directory.resolve("ml-decisions.csv");',
        '''            geometryFeatures = new PrintWriter(Files.newBufferedWriter(result.resolve("ml-target-geometry.csv")));
            geometryFeatures.println("signal_ns,side,quote_ns,entry_ticks,stop_ticks,bb_price,or_price,or_ready,or_active,nearest_target_r,or_position_signed,nearest_target_stress_net_usd");
            Path decisionFile=directory.resolve("ml-decisions.csv");''')
    anchor='''                            quoteTime,risk,ratio,slope,mlRelativeVolume,(ns-dayOpen)/(60.0*SECOND));'''
    text=once(text,anchor,anchor+'''
                        int decisionEntry = side==1 ? quoteAsk : quoteBid;
                        double entryPrice = decisionEntry*INSTRUMENT_TICK;
                        double stopDistance = side*(decisionEntry-shadowStop)*INSTRUMENT_TICK;
                        double bbPrice = target(last,side);
                        boolean orReady = openingRangeDuration>0 && ns-dayOpen>=openingRangeDuration && openingLow<=openingHigh;
                        double orPrice = orReady ? (side==1?openingHigh:openingLow)*INSTRUMENT_TICK : Double.NaN;
                        boolean orActive = orReady && side*(orPrice-entryPrice)>=INSTRUMENT_TICK;
                        double distance = side*(bbPrice-entryPrice);
                        if(orActive)distance=Math.min(distance,side*(orPrice-entryPrice));
                        double rangePosition = orReady && openingHigh>openingLow
                            ? side*((decisionEntry-openingLow)/(double)(openingHigh-openingLow)-0.5) : Double.NaN;
                        require(stopDistance>0 && Double.isFinite(distance),"Invalid geometry observation");
                        geometryFeatures.printf(Locale.ROOT,"%d,%d,%d,%d,%d,%.17g,%.17g,%d,%d,%.17g,%.17g,%.17g%n",
                            ns,side,quoteTime,decisionEntry,shadowStop,bbPrice,orPrice,orReady?1:0,orActive?1:0,
                            distance/stopDistance,rangePosition,distance*50-4.68-25.0);''')
    text=once(text,'signalQuotes; mlFeatures) {','signalQuotes; mlFeatures; geometryFeatures) {')
    text=once(text,'require(!mlFeatures.checkError(), "Prefix feature output error");',
        'require(!mlFeatures.checkError() && !geometryFeatures.checkError(), "Prefix feature output error");')
    text=once(text,'require(!trades.checkError() && !mlFeatures.checkError(), "Could not write trades/features");',
        'require(!trades.checkError() && !mlFeatures.checkError() && !geometryFeatures.checkError(), "Could not write trades/features");')
    out=HERE/'Source/HYML1ESResearch.java';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(text)
    cfg=dict(schema='ES-Geometry-01',created_at_utc=datetime.now(timezone.utc).isoformat(),
        role='single exploratory no-fit measurement; selected development year, not confirmation',
        primary='Spearman(nearest_target_r, candidate stress net USD), positive one-sided',
        population='same347 unique scoring-period ES C28.03 candidates,24Nov2025–30Oct2026',
        geometry='known executable-side decision quote; signed BB distance; OR only after60min and>=1tick on profit side; nearest signed active distance divided by raw planned stop distance; negative BB distance retained',
        secondary_outputs='OR readiness/activity and signed range location described only, not alternative significance tests',
        permutation=dict(draws=1000,seed=20261124,strata='calendar quarter and equal number of candidates in session',
            unit='whole ordered session outcome vector',scope='conditional development diagnostic, not independent confirmations'),
        native='6 full observer segments, exact trades/candidates/old-features/quotes parity,5 pre-existing physical prefix fixtures',
        prefix_scope='five strict cuts, earlier rows parity; no general no-leak guarantee',
        next='No model training before measurement; no deployment or leaderboard promotion',
        code_sha256=sha(Path(__file__)),source_sha256=sha(out),prior_source_sha256=sha(original),
        live_changed=False,cloud_spend_usd=0)
    write(HERE/'geometry-preregister.json',cfg)
    print('Prepared geometry observer and plan',sha(out),flush=True)

def build():
    cfg=read(HERE/'geometry-preregister.json')
    assert cfg['code_sha256']==sha(Path(__file__)) and cfg['source_sha256']==sha(HERE/'Source/HYML1ESResearch.java')
    assert read(HERE/'geometry-github-receipt.json')['state']=='published_before_measurement'
    if not APP.exists():
        APP.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(['cp','-cR',str(native.APP),str(APP)],check=True)
    classes=HERE/'Classes';classes.mkdir(exist_ok=True)
    source=HERE/'Source/HYML1ESResearch.java'
    helpers=['SqxCompletedBarIndicators','SqxSessionVwap','SqxSessionPriceProfile',
        'SqxParametricTpoProfile','SqxExtensionBarIndicators','SqxRollingVwap']
    helper_sources=[native.ROBUST/(n+'.java') for n in helpers]
    subprocess.run([str(APP/'j64/bin/javac'),'-cp',str(APP/'internal/libs/*'),'-d',str(classes),
        *map(str,helper_sources),str(source)],check=True)
    jar=APP/'internal/libs/Snippets.jar';temp=jar.with_suffix('.geometry')
    prefixes=tuple('SQ/Blocks/OtherActions/'+n for n in ['HYML1ESResearch',*helpers])
    with ZipFile(jar) as src,ZipFile(temp,'w',ZIP_DEFLATED) as dst:
        for item in src.infolist():
            if not item.filename.startswith(prefixes):dst.writestr(item,src.read(item.filename))
        for p in classes.rglob('*.class'):dst.write(p,p.relative_to(classes).as_posix())
    temp.replace(jar)
    dest=APP/'user/extend/Snippets/SQ/Blocks/OtherActions/HYML1ESResearch.java';shutil.copy2(source,dest)
    registry=APP/'user/settings/snippets.txt';key='$SNIPPETS_USER_DIR$/SQ/Blocks/OtherActions/HYML1ESResearch.java|'
    registry.write_text('\n'.join([r for r in registry.read_text().splitlines() if not r.startswith(key)]
        +[key+hashlib.md5(source.read_bytes()).hexdigest()])+'\n')

def prepare(old,target):
    # Metadata is copied; large immutable tapes/volumes get private APFS CoW copies.
    target.mkdir(parents=True,exist_ok=True)
    for name in ['strategies','result_sqx']:(target/name).mkdir(exist_ok=True)
    for p in old.iterdir():
        if p.is_file() and p.suffix in ('','.csv','.txt','.gz') and p.name!='prefix-quotes.csv':
            subprocess.run(['cp','-c',str(p),str(target/p.name)],check=True)
    template=next((old/'strategies').glob('*.sqx'))
    with ZipFile(template) as z:members={n:z.read(n) for n in z.namelist()}
    for n,b in list(members.items()):
        if n.endswith('.xml'):members[n]=b.replace(str(old).encode(),str(target).encode())
    with ZipFile(target/'strategies'/('Geometry_'+old.name+'.sqx'),'w',ZIP_DEFLATED) as z:
        for n,b in members.items():z.writestr(n,b)
    with ZipFile(old/'Optimizer.cfx') as z:cfg=z.read('config.xml').replace(str(old).encode(),str(target).encode())
    with ZipFile(target/'Optimizer.cfx','w',ZIP_DEFLATED) as z:z.writestr('config.xml',cfg)
    (target/'run.cli').write_text((old/'run.cli').read_text().replace(str(old),str(target)))

def execute():
    build();native.APP=APP
    completed=[]
    for old in sorted((OLD/'SQX/observer').iterdir()):
        target=HERE/'Geometry/SQX'/old.name
        if not (target/'verified.json').exists():
            prepare(old,target);seconds=native.run_job(target)
            folders=[p for p in target.glob('native_export_*') if (p/'complete.txt').exists()]
            assert len(folders)==3
            base=Path(read(old/'verified.json')['folder'])
            for name in ['trades.csv','candidates.csv','ml-features.csv','signal-quotes.csv']:
                assert all(sha(p/name)==sha(base/name) for p in folders),'Observer changed '+name
            assert len({sha(p/'ml-target-geometry.csv') for p in folders})==1
            write(target/'verified.json',dict(state='geometry_observer_parity_verified',folder=str(folders[0]),
                replicas=3,seconds=seconds,geometry_sha256=sha(folders[0]/'ml-target-geometry.csv'),
                source_sha256=sha(HERE/'Source/HYML1ESResearch.java')))
        completed.append(old.name);write(HERE/'geometry-progress.json',dict(state='running',phase='observer',completed=completed))
        print('Geometry observer',old.name,'verified',flush=True)
    prefixes=[]
    for old in sorted((PRIOR/'SQX/prefix').iterdir()):
        if not (old/'verified.json').exists():continue
        target=HERE/'Geometry/Prefix'/old.name
        if not (target/'verified.json').exists():
            prepare(old,target);seconds=native.run_job(target)
            folders=[p for p in target.glob('native_export_*') if (p/'prefix-complete.txt').exists()]
            assert len(folders)==3
            cutoff=read(old/'verified.json')['cutoff_ns']
            full=Path(read(HERE/'Geometry/SQX'/old.name/'verified.json')['folder'])
            expected=[r for r in (full/'ml-target-geometry.csv').read_text().splitlines()
                if r.startswith('signal_ns,') or int(r.split(',')[0])<=cutoff]
            for p in folders:
                assert (p/'ml-target-geometry.csv').read_text().splitlines()==expected,'Geometry depends on physical future'
            write(target/'verified.json',dict(state='geometry_physical_prefix_verified',cutoff_ns=cutoff,
                rows=len(expected)-1,replicas=3,seconds=seconds,physical_fixture_source_sha256=sha(old/'prefix-input-proof.json')))
        prefixes.append(read(target/'verified.json'))
        write(HERE/'geometry-progress.json',dict(state='running',phase='prefix',completed=len(prefixes)))
        print('Geometry prefix',old.name,'verified',flush=True)
    assert len(prefixes)==5
    measure(prefixes)

def measure(prefixes):
    sys.path.insert(0,str(OLD/'repo/ai-research'));import train_ml1 as base
    dates,rows,_=base.data();rows=[r for r in rows if r['day'] in dates];assert len(rows)==347
    observed={}
    for p in (HERE/'Geometry/SQX').glob('*/verified.json'):
        folder=Path(read(p)['folder'])
        for row in csv.DictReader((folder/'ml-target-geometry.csv').open()):
            ns=int(row['signal_ns']);assert ns not in observed;observed[ns]=row
    x=np.array([float(observed[r['ns']]['nearest_target_r']) for r in rows])
    y=np.array([r['stress_net_cents']/100 for r in rows])
    assert np.isfinite(x).all() and np.isfinite(y).all()
    rho=float(spearmanr(x,y).statistic)
    days=defaultdict(list);groups=defaultdict(list)
    for i,r in enumerate(rows):days[r['day']].append(i)
    for day,ix in days.items():groups[(day[:4],(int(day[5:7])-1)//3,len(ix))].append(ix)
    rng=np.random.default_rng(20261124);null=[]
    for _ in range(1000):
        perm=y.copy()
        for sessions in groups.values():
            for target,source in zip(sessions,rng.permutation(len(sessions)),strict=True):perm[target]=y[sessions[source]]
        null.append(float(spearmanr(x,perm).statistic))
    result=dict(state='native_geometry_measurement_complete',candidates=347,spearman_rho=rho,
        conditional_upper_tail_rank=(1+sum(r>=rho for r in null))/1001,
        null_q95=float(np.quantile(null,.95)),draws=1000,
        negative_target_distance_candidates=int((x<0).sum()),
        OR_ready_candidates=sum(observed[r['ns']]['or_ready']=='1' for r in rows),
        OR_active_candidates=sum(observed[r['ns']]['or_active']=='1' for r in rows),
        strict_physical_prefix_cuts=5,prefix_parity_rows=sum(p['rows'] for p in prefixes),
        observer_segments=6,trade_logic_unchanged=True,no_model_trained=True,no_cash_claim=True,
        selected_year=True,fresh_OOS=False,source_sha256=sha(HERE/'Source/HYML1ESResearch.java'))
    write(HERE/'Geometry/results.json',result);write(HERE/'geometry-progress.json',dict(state='complete'))
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':
    try:
        if sys.argv[1]=='prepare':source_and_plan()
        elif sys.argv[1]=='run':execute()
        else:raise ValueError('prepare or run required')
    except Exception as e:
        write(HERE/'geometry-progress.json',dict(state='failed',error_type=type(e).__name__,message=str(e)));raise
