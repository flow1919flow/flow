"""One fixed minute approximation of native C28.03, guarded label periods.

Contact and return use minute CLOSE only. H/L updates the forming indicator
range and opening range, and tests stop/OR exits. This is never called TBBO.
"""
from pathlib import Path
from collections import deque,Counter
from datetime import datetime,timezone
import argparse, hashlib, json, math, time
import numpy as np
import pandas as pd
from inventory_local import HERE,ROOT,sha,save
from extract_prices import NS,CT,session_ns

FEE=4.68;STRESS=25.;POINT=50.;TICK=.25
PROTOCOL_SHA='07bcf9570e68ab5cbeef5b58ca6b23c543979d8f96ac4c17986ddd2f43311faf'
FEATURES=['feature_stop_risk_usd','feature_target_path_R','feature_signed_completed_ema_slope_atr','feature_completed_relative_volume20','feature_chicago_session_minute']
RANGES={'known':('2025-11-24','2026-10-31'),'development':('2021-11-24','2024-11-24'),'sealed':('2024-11-24','2025-11-24')}


def outward(price,side):
    tick=price/TICK;nearest=round(tick)
    if abs(tick-nearest)<=min(8*math.ulp(tick),1e-8):tick=float(nearest)
    return (math.floor(tick) if side==1 else math.ceil(tick))*TICK


def decision_features(side,close,preview,signal,session_open):
    stop=outward(preview['center']-side*2.15*preview['atr'],side)
    distance=side*(close-stop)
    if distance<=0:return None,'consumed_return_stop_already_beyond_decision_close'
    risk=distance*POINT+FEE+STRESS
    slope=None if preview['completed_atr'] is None or preview['previous_completed_ema'] is None or preview['completed_atr']<=0 else side*(preview['completed_ema']-preview['previous_completed_ema'])/preview['completed_atr']
    bb=preview['bb_upper'] if side==1 else preview['bb_lower']
    paths=[side*(bb-close)]
    orlevel=preview['or_high'] if side==1 else preview['or_low']
    # No actual next-open execution price can enter this decision-time feature.
    if preview['or_active'] and orlevel is not None and side*(orlevel-close)>=TICK:paths.append(side*(orlevel-close))
    feature=[risk,min(paths)/distance,slope,preview['relative_volume'],(signal-session_open)/(60*NS)]
    if any(v is None or not math.isfinite(v) for v in feature):return None,'consumed_return_incomplete_completed_feature_state'
    return dict(stop_price=stop,planned_risk_usd=risk,**dict(zip(FEATURES,feature)),decision_BB_level=bb,decision_OR_level=orlevel if preview['or_active'] else None),None


class Indicators:
    """Same completed/forming EMA20/ATR10/BB20 conventions as native Java."""
    def __init__(self):
        self.ema=None;self.atr=None;self.previous_close=None
        self.initial_ranges=[];self.closes=deque(maxlen=19);self.volumes=deque(maxlen=20)
        self.last_completed_ema=None;self.prior_completed_ema=None;self.closed_atr=None;self.relative_volume=None
        self.last_band=0;self.setup_side=0;self.day=None;self.bucket=None;self.high=None;self.low=None;self.close=None;self.volume=0
        self.first_bar=True;self.seen_buckets=set();self.day_grid_complete=True
        self.or_high=None;self.or_low=None

    def ema_at(self,last):return last if self.ema is None else self.ema+(2/21)*(last-self.ema)

    def true_range(self):
        span=self.high-self.low
        return span if self.first_bar else max(span,abs(self.high-self.previous_close),abs(self.low-self.previous_close))

    def atr_at(self):
        tr=self.true_range()
        if self.atr is not None:return (9*self.atr+tr)/10
        if len(self.initial_ranges)<9:return None
        return (sum(self.initial_ranges)+tr)/10

    def bb(self,last):
        if len(self.closes)!=19:return None,None
        values=list(self.closes)+[last];mean=sum(values)/20
        sigma=math.sqrt(sum((x-mean)**2 for x in values)/20)
        half=1.75*sigma-.75*TICK
        return mean+half,mean-half

    def commit(self):
        if self.bucket is None:return
        value=self.ema_at(self.close);width=self.atr_at()
        self.ema=value;self.atr=width
        self.prior_completed_ema=self.last_completed_ema;self.last_completed_ema=value;self.closed_atr=width
        if len(self.volumes)==20:
            total=sum(self.volumes);self.relative_volume=self.volume/(total/20) if total>0 else None
        self.volumes.append(self.volume)
        if width is None:self.initial_ranges.append(self.true_range())
        self.previous_close=self.close;self.closes.append(self.close);self.first_bar=False
        self.bucket=None

    def step(self,r,calendar):
        day=r['date'];bucket=int(r['bar_index'])
        if day!=self.day:
            self.commit();self.day=day;self.first_bar=True;self.seen_buckets=set();self.day_grid_complete=True
            self.or_high=None;self.or_low=None
        elif self.bucket is not None and bucket!=self.bucket:self.commit()
        if self.bucket is None:
            if self.seen_buckets!=set(range(bucket)):self.day_grid_complete=False
            self.seen_buckets.add(bucket);self.bucket=bucket
            self.high=r['high'];self.low=r['low'];self.volume=0.
        self.high=max(self.high,r['high']);self.low=min(self.low,r['low']);self.close=r['close'];self.volume+=r['volume']
        if int(r['ts_event_ns'])-calendar['session_open_ns']<3600*NS:
            self.or_high=r['high'] if self.or_high is None else max(self.or_high,r['high'])
            self.or_low=r['low'] if self.or_low is None else min(self.or_low,r['low'])
        center=self.ema_at(r['close']);atr=self.atr_at();upper,lower=self.bb(r['close'])
        signal=int(r['ts_event_ns'])+60*NS
        result=dict(center=center,atr=atr,bb_upper=upper,bb_lower=lower,or_high=self.or_high,or_low=self.or_low,or_active=signal-calendar['session_open_ns']>=3600*NS,completed_ema=self.last_completed_ema,previous_completed_ema=self.prior_completed_ema,completed_atr=self.closed_atr,relative_volume=self.relative_volume,current_grid_complete=self.day_grid_complete)
        entered=0
        if len(self.closes)==19 and atr is not None and atr>0:
            # Native order: consume an existing setup return BEFORE recognizing
            # the current close as a new opposite-band contact.
            if self.setup_side and self.setup_side*(r['close']-center)<=0:
                entered=self.setup_side;self.setup_side=0
            contact=1 if r['close']>=center+2*atr else -1 if r['close']<=center-2*atr else 0
            if contact and contact!=self.last_band:
                if self.last_band:self.setup_side=contact
                self.last_band=contact
        result['first_return_side']=entered
        return result


def label_one(candidate,rows,previews,calendar):
    """One independent counterfactual path; all features already frozen."""
    side=candidate['side'];signal=candidate['signal_ns'];stop=candidate['stop_price']
    loc=[i for i,r in enumerate(rows) if int(r['ts_event_ns'])==signal]
    if len(loc)!=1:return dict(label_status='excluded_missing_exact_next_minute_open')
    start=loc[0];entry=rows[start]['open'];pending_bb=False
    for i in range(start,len(rows)):
        r=rows[i];ns=int(r['ts_event_ns']);op=r['open'];preview=previews[i]
        reason=None;price=None
        # A gap stop has priority over scheduled BB and flatten exits.
        if side*(op-stop)<=0:
            price=op;reason='stop_gap_open' if i>start else 'entry_beyond_stop_immediate'
        elif ns>=calendar['flatten_ns']:
            price=op;reason='session_flatten_first_open'
        elif pending_bb:
            price=op;reason='moving_BB_close_cross_next_open'
        elif r['low']<=stop if side==1 else r['high']>=stop:
            price=stop;reason='fixed_stop_touch'
        else:
            level=preview['or_high'] if side==1 else preview['or_low']
            # At minute START the first60minutes must already be complete.
            or_active=ns-calendar['session_open_ns']>=3600*NS
            if or_active and level is not None and side*(level-entry)>=TICK and (r['high']>=level if side==1 else r['low']<=level):
                price=level;reason='OR60_level_touch'
            else:
                bound=preview['bb_upper'] if side==1 else preview['bb_lower']
                pending_bb=bound is not None and side*(r['close']-bound)>0
        if reason:
            gross=side*(price-entry)*POINT;normal=gross-FEE;stress=normal-STRESS
            # A stop/OR touch is known only when that OHLC minute completes.
            # Its conservative exit information clock is the interval END.
            exit_ns=ns+60*NS if reason in ('fixed_stop_touch','OR60_level_touch') else ns
            return dict(label_status='ok',entry_ns=int(rows[start]['ts_event_ns']),exit_ns=exit_ns,entry_price=entry,exit_price=price,normal_net_usd=normal,stress_net_usd=stress,stress_net_R=stress/candidate['planned_risk_usd'],exit_reason=reason,secondary_fixed_bracket_stress_net_R=None,secondary_label_status='uncomputed_preflight_only')
    return dict(label_status='excluded_no_observed_flatten_or_exit_open')


def guard(mode,protocol,receipt):
    if sha(protocol)!=PROTOCOL_SHA:raise ValueError('Published preflight protocol SHA mismatch')
    r=json.loads(Path(receipt).read_text())
    if r.get('authorized') is not True or r.get('protocol_sha256')!=PROTOCOL_SHA or r.get('mode')!=mode:raise ValueError('Missing exact root mode/protocol authorization')
    if mode=='development':
        acceptance=json.loads((HERE/'Public/known-year-acceptance.json').read_text())
        if acceptance.get('accepted') is not True:raise ValueError('Known-year approximation did not pass; older labels forbidden')
    if mode=='sealed':
        if r.get('sealed_evaluation_authorized') is not True or not re_full_sha(r.get('final_frozen_model_sha256','')):raise ValueError('Sealed labels require final frozen model SHA receipt')
    return r


def re_full_sha(x):return isinstance(x,str) and len(x)==64 and all(c in '0123456789abcdef' for c in x)


def build(mode,protocol,receipt):
    authorization=guard(mode,protocol,receipt);began=time.time()
    manifest=json.loads((HERE/'Private/price-data-manifest.json').read_text());p=Path(manifest['minute_file'])
    assert sha(p)==manifest['minute_sha256']
    schedule=json.loads(Path(manifest['schedule_file']).read_text());assert sha(Path(manifest['schedule_file']))==manifest['schedule_sha256']
    lo,hi=RANGES[mode];target=[s for s in schedule if lo<=s['date']<hi]
    if mode!='known' and any(s['calendar_status']!='observed_exact_native_seed' for s in target):
        raise ValueError('Older session calendar must be verified before older labels; no generic weekday template permitted')
    minute=pd.read_parquet(p)
    minute['open']=minute.open_nanos/1e9;minute['high']=minute.high_nanos/1e9;minute['low']=minute.low_nanos/1e9;minute['close']=minute.close_nanos/1e9
    frames={(symbol,day):g.to_dict('records') for (symbol,day),g in minute.groupby(['raw_symbol','date'],sort=True,observed=True)}
    calendar={s['date']:s for s in schedule}
    # Keep each selected raw contract in a separately warmed episode.
    episodes=[]
    for s in target:
        if s['raw_symbol'] is None:continue
        if not episodes or episodes[-1]['symbol']!=s['raw_symbol']:
            episodes.append(dict(symbol=s['raw_symbol'],sessions=[]))
        episodes[-1]['sessions'].append(s)
    candidates=[];exclusions=[];all_preview_rows=[];episode_proof=[]
    for episode in episodes:
        symbol=episode['symbol'];state=Indicators();first=episode['sessions'][0]
        warm_dates=[w['date'] for w in first['warmup_previous_five_same_contract_sessions']]
        feed_dates=warm_dates+[s['date'] for s in episode['sessions']]
        active={s['date']:s for s in episode['sessions']}
        episode_candidates=[];byday={};preview_byday={};baseline_exit_ns=-1
        for day in feed_dates:
            rows=frames.get((symbol,day),[]);meta=calendar[day];previews=[]
            for r in rows:
                preview=state.step(r,meta);previews.append(preview)
                side=preview['first_return_side'];signal=int(r['ts_event_ns'])+60*NS
                if not side or day not in active:continue
                reason=None
                if signal>=meta['flatten_ns']:reason='consumed_return_at_or_after_native_flatten'
                elif not active[day]['warmup_complete']:reason='consumed_return_incomplete_prior_five_same_contract_sessions'
                elif not preview['current_grid_complete']:reason='consumed_return_missing_past_current_session_5m_bucket'
                elif preview['atr'] is None or preview['atr']<=0:reason='consumed_return_missing_positive_ATR'
                if reason:
                    exclusions.append(dict(contract=symbol,day=day,signal_ns=signal,side=side,reason=reason));continue
                feature,reason=decision_features(side,r['close'],preview,signal,meta['session_open_ns'])
                if reason:
                    exclusions.append(dict(contract=symbol,day=day,signal_ns=signal,side=side,reason=reason));continue
                row=dict(case_key=hashlib.sha256(f'C28coarse1m|{symbol}|{signal}|{side}'.encode()).hexdigest(),contract=symbol,day=day,signal_ns=signal,side=side,decision_price=r['close'],**feature,calendar_status=meta['calendar_status'],source_resolution='original1mOHLCV_notTBBO',base_was_flat=None)
                episode_candidates.append(row)
            byday[day]=rows;preview_byday[day]=previews
        episode_proof.append(dict(contract=symbol,first_scored_day=first['date'],last_scored_day=episode['sessions'][-1]['date'],same_contract_warmup_dates=warm_dates,candidate_features_before_label=len(episode_candidates)))
        # Features for this episode have all been constructed without its labels.
        for c in episode_candidates:
            c['base_was_flat']=c['signal_ns']>=baseline_exit_ns
            result=label_one(c,byday[c['day']],preview_byday[c['day']],calendar[c['day']])
            c.update(result)
            if c['label_status']=='ok':
                if c['base_was_flat']:baseline_exit_ns=c['exit_ns']
                candidates.append(c)
            else:exclusions.append(dict(contract=symbol,day=c['day'],signal_ns=c['signal_ns'],side=c['side'],reason=c['label_status']))
        print('coarse',mode,symbol,'feature_candidates',len(episode_candidates),'valid_so_far',len(candidates),flush=True)
    candidates.sort(key=lambda r:(r['signal_ns'],r['contract'],r['side']))
    assert all(lo<=r['day']<hi for r in candidates)
    assert len({r['case_key'] for r in candidates})==len(candidates)
    csv=HERE/f'Private/coarse-candidates-{mode}.csv';pd.DataFrame(candidates).to_csv(csv,index=False)
    jsonl=HERE/f'Private/coarse-candidates-{mode}.jsonl';jsonl.write_text(''.join(json.dumps(c,allow_nan=False)+'\n' for c in candidates))
    save(HERE/f'Private/coarse-exclusions-{mode}.json',exclusions);save(HERE/f'Private/coarse-episodes-{mode}.json',episode_proof)
    summary=dict(status='COARSE_PRIMARY_CANDIDATES_LABELED_NOT_NATIVE_TICKS',mode=mode,date_range=[lo,hi+'exclusive'],created_utc=datetime.now(timezone.utc).isoformat(),protocol_sha256=PROTOCOL_SHA,builder_sha256=sha(Path(__file__)),price_manifest_sha256=sha(HERE/'Private/price-data-manifest.json'),authorization_sha256=sha(receipt),cases=len(candidates),case_days=len({r['day'] for r in candidates}),base_was_flat_n=sum(c['base_was_flat'] for c in candidates),exclusion_reasons=dict(Counter(r['reason'] for r in exclusions)),csv_sha256=sha(csv),jsonl_sha256=sha(jsonl),labels_outside_authorized_mode=0,sealed_labels_generated=mode=='sealed',features=FEATURES,feature_OR_activation='Atdecision>=60min andORlevel>=1tickfavorablefromdecisionclose(proxyplannedentry);actualnextopenneverfeature',secondary_fixed_bracket='uncomputed_preflight_only',elapsed_seconds=time.time()-began)
    save(HERE/f'Public/coarse-candidates-{mode}-summary.json',summary);print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=list(RANGES),required=True);ap.add_argument('--protocol',type=Path,required=True);ap.add_argument('--receipt',type=Path,required=True);a=ap.parse_args()
    build(a.mode,a.protocol,a.receipt)
