"""Fixed finite-path one-second reconstruction and symmetric delayed proxyfills.

Pure data functions: no file/network access, candidate execution entrypoint,
training or parameter search. Both prescribed OHLC orders are scenarios, not
proof that they span every possible real intrasecond tick oscillation.
"""
from collections import deque
from functools import lru_cache
import math
import numpy as np

NS=1_000_000_000;TICK=.25;POINT=50.;FEE=4.68;STRESS=25.
STATES=((0,0),(1,0),(-1,0),(1,1),(-1,-1))
STATE_INDEX={s:i for i,s in enumerate(STATES)}
FEATURES=['feature_stop_risk_usd','feature_target_path_R','feature_signed_completed_ema_slope_atr','feature_completed_relative_volume20','feature_chicago_session_minute']


def outward(price,side):
    ticks=price/TICK;nearest=round(ticks)
    if abs(ticks-nearest)<=min(8*math.ulp(ticks),1e-8):ticks=float(nearest)
    return (math.floor(ticks) if side==1 else math.ceil(ticks))*TICK


@lru_cache(maxsize=65536)
def transition(signature,state_index):
    """All uncertainty is in price-order observations, never in outcomes."""
    last,setup=STATES[state_index];events=[]
    for return_mask,contact in signature:
        if setup and return_mask&(1 if setup==1 else 2):
            events.append(setup);setup=0
        # Native event order: consume existing return before new band contact.
        if contact and contact!=last:
            if last:setup=contact
            last=contact
    return STATE_INDEX[(last,setup)],tuple(events)


def propagate(mask,signatures):
    endmask=0;patterns=set();paths=0
    for state_index in range(len(STATES)):
        if not(mask&(1<<state_index)):continue
        for signature in signatures:
            end,events=transition(signature,state_index);endmask|=1<<end;patterns.add(events);paths+=1
    if not endmask:raise ValueError('Uncertainty state set became empty')
    consensus=next(iter(patterns))[0] if len(patterns)==1 and len(next(iter(patterns)))==1 else 0
    return endmask,consensus,any(patterns) and consensus==0,tuple(sorted(patterns)),paths


class SecondBook:
    def __init__(self):
        self.ema=None;self.atr=None;self.previous_close=None;self.initial_ranges=[]
        self.closes=deque(maxlen=19);self.volumes=deque(maxlen=20);self._bb_cache={}
        self.last_completed_ema=None;self.previous_completed_ema=None;self.closed_atr=None;self.relative_volume=None;self.closed_end_ns=None
        self.day=None;self.bucket=None;self.bar_start=None;self.bar_end=None;self.high=None;self.low=None;self.close=None;self.volume=0
        self.first_bar=True;self.seen_buckets=set();self.current_grid_complete=True
        self.or_high=None;self.or_low=None;self.state_mask=1

    def center(self,price):return price if self.ema is None else self.ema+(2/21)*(price-self.ema)

    def true_range(self,high,low):
        return high-low if self.first_bar else max(high-low,abs(high-self.previous_close),abs(low-self.previous_close))

    def atr_at(self,high,low):
        tr=self.true_range(high,low)
        if self.atr is not None:return (9*self.atr+tr)/10
        return (sum(self.initial_ranges)+tr)/10 if len(self.initial_ranges)>=9 else None

    def bb_at(self,price):
        if len(self.closes)!=19:return None,None
        if price not in self._bb_cache:
            values=list(self.closes)+[price];mean=sum(values)/20
            sigma=math.sqrt(sum((v-mean)**2 for v in values)/20)
            half=1.75*sigma-.75*TICK;self._bb_cache[price]=(mean+half,mean-half)
        return self._bb_cache[price]

    def commit(self):
        if self.bucket is None:return
        center=self.center(self.close);width=self.atr_at(self.high,self.low)
        self.ema=center;self.atr=width
        self.previous_completed_ema=self.last_completed_ema;self.last_completed_ema=center;self.closed_atr=width
        if len(self.volumes)==20:
            total=sum(self.volumes);self.relative_volume=self.volume/(total/20) if total>0 else None
        self.volumes.append(self.volume)
        if width is None:self.initial_ranges.append(self.true_range(self.high,self.low))
        self.previous_close=self.close;self.closes.append(self.close);self.closed_end_ns=self.bar_end
        self._bb_cache.clear();self.first_bar=False;self.bucket=None

    def _signature(self,prices):
        high=self.high;low=self.low;signature=[]
        for price in prices:
            high=price if high is None else max(high,price);low=price if low is None else min(low,price)
            width=self.atr_at(high,low);center=self.center(price)
            if len(self.closes)<19 or width is None or width<=0:
                signature.append((0,0));continue
            returnmask=(1 if price<=center else 0)|(2 if price>=center else 0)
            contact=1 if price>=center+2*width else -1 if price<=center-2*width else 0
            signature.append((returnmask,contact))
        return tuple(signature)

    def step(self,row,clock):
        """Decision atsecondEND; completedfeatures cut atsecondSTART.

        Current formingbar's last second is used for stop/BB at its end, but
        is not committed into completed slope/volume until a later second.
        """
        day=row['day'];start=int(row['ts_event_ns']);end=start+NS
        bucket=int((start-clock['session_open_ns'])//(300*NS))
        if day!=self.day:
            self.commit();self.day=day;self.first_bar=True;self.seen_buckets=set();self.current_grid_complete=True
            self.or_high=None;self.or_low=None
        elif self.bucket is not None and bucket!=self.bucket:self.commit()
        if self.bucket is None:
            if self.seen_buckets!=set(range(bucket)):self.current_grid_complete=False
            self.seen_buckets.add(bucket);self.bucket=bucket
            self.bar_start=clock['session_open_ns']+bucket*300*NS;self.bar_end=min(self.bar_start+300*NS,clock['session_close_ns'])
            self.high=None;self.low=None;self.volume=0
        # Independent of unknown order: both scenarios include known Open/Close.
        orders={(row['open'],row['high'],row['low'],row['close']),(row['open'],row['low'],row['high'],row['close'])}
        signatures={self._signature(prices) for prices in orders}
        previous_mask=self.state_mask
        self.state_mask,side,ambiguous,patterns,paths=propagate(self.state_mask,signatures)
        self.high=row['high'] if self.high is None else max(self.high,row['high']);self.low=row['low'] if self.low is None else min(self.low,row['low']);self.close=row['close'];self.volume+=int(row['volume'])
        if start-clock['session_open_ns']<3600*NS:
            self.or_high=row['high'] if self.or_high is None else max(self.or_high,row['high'])
            self.or_low=row['low'] if self.or_low is None else min(self.or_low,row['low'])
        center=self.center(self.close);atr=self.atr_at(self.high,self.low);upper,lower=self.bb_at(self.close)
        hi_upper,_=self.bb_at(row['high']);_,lo_lower=self.bb_at(row['low'])
        if self.closed_end_ns is not None and self.closed_end_ns>start:raise ValueError('Completed feature used a bar ending after secondSTART')
        return dict(signal_ns=end,consensus_side=side,ambiguous_first_return=bool(ambiguous),possible_event_patterns=patterns,paths_considered=paths,state_mask_before=previous_mask,state_mask_after=self.state_mask,forming_center=center,forming_atr=atr,BB_upper_at_close=upper,BB_lower_at_close=lower,BB_upper_at_high=hi_upper,BB_lower_at_low=lo_lower,OR_high=self.or_high,OR_low=self.or_low,OR_active_for_decision=end-clock['session_open_ns']>=3600*NS,OR_active_for_second=start-clock['session_open_ns']>=3600*NS,completed_ema=self.last_completed_ema,previous_completed_ema=self.previous_completed_ema,completed_atr=self.closed_atr,completed_relative_volume20=self.relative_volume,completed_feature_end_ns=self.closed_end_ns,current_past_5m_grid_complete=self.current_grid_complete)


def decision_features(side,close,preview,clock):
    if preview['forming_atr'] is None or preview['forming_atr']<=0:return None,'missing_positive_ATR'
    stop=outward(preview['forming_center']-side*2.15*preview['forming_atr'],side)
    if side*(close-stop)<=0:return None,'decision_trade_already_beyond_stop'
    proxy=close+side*TICK;distance=side*(proxy-stop);risk=distance*POINT+FEE+STRESS
    if distance<=0 or risk<=0:return None,'nonpositive_planned_risk'
    bb=preview['BB_upper_at_close'] if side==1 else preview['BB_lower_at_close']
    paths=[side*(bb-proxy)]
    orlevel=preview['OR_high'] if side==1 else preview['OR_low']
    if preview['OR_active_for_decision'] and orlevel is not None and side*(orlevel-proxy)>=TICK:paths.append(side*(orlevel-proxy))
    width=preview['completed_atr'];previous=preview['previous_completed_ema'];latest=preview['completed_ema']
    slope=side*(latest-previous)/width if width is not None and width>0 and previous is not None else None
    values=[risk,min(paths)/distance,slope,preview['completed_relative_volume20'],(preview['signal_ns']-clock['session_open_ns'])/(60*NS)]
    if any(v is None or not math.isfinite(v) for v in values):return None,'incomplete_completed_feature_state'
    return dict(stop_price=stop,decision_quote_proxy=proxy,planned_risk_usd=risk,**dict(zip(FEATURES,values)),decision_BB_level=bb,decision_OR_level=orlevel if preview['OR_active_for_decision'] else None,completed_feature_end_ns=preview['completed_feature_end_ns']),None


def delayed_shadow(candidate,rows,previews,clock):
    """No retrospective/level-pricefills. Once intent exists, preserve it."""
    side=int(candidate['side']);signal=int(candidate['signal_ns']);stop=candidate['stop_price']
    stamps=np.array([int(r['ts_event_ns']) for r in rows],dtype=np.int64)
    index=int(np.searchsorted(stamps,signal+2*NS,side='left'))
    if index==len(rows):return dict(label_status='excluded_no_present_entry_second',entry_decision_ns=signal)
    entry_ns=int(stamps[index]);open_price=rows[index]['open']
    if entry_ns>=clock['flatten_ns']:return dict(label_status='excluded_delayed_entry_at_or_after_flatten',entry_decision_ns=signal,entry_cancel_ns=entry_ns)
    # Native source uses liquidation-sidebid/ask toguardthen fillsoppositeside.
    liquidation_proxy=open_price-side*TICK
    if side*(liquidation_proxy-stop)<=0:return dict(label_status='excluded_delayed_entry_liquidation_proxy_beyond_stop',entry_decision_ns=signal,entry_cancel_ns=entry_ns)
    entry=open_price+side*TICK;exit_decision=None;reason=None
    for i in range(index,len(rows)):
        r=rows[i];preview=previews[i];start=int(stamps[i]);end=start+NS
        if exit_decision is None and start>=clock['flatten_ns']:
            exit_decision=clock['flatten_ns'];reason='session_flatten_delayed_market'
        if exit_decision is not None:
            if start>=exit_decision+2*NS:
                exit_price=r['open']-side*TICK;gross=side*(exit_price-entry)*POINT
                return dict(label_status='ok',entry_ns=entry_ns,exit_ns=start,exit_decision_ns=exit_decision,entry_price=entry,exit_price=exit_price,normal_net_usd=gross-FEE,stress_net_usd=gross-FEE-STRESS,stress_net_R=(gross-FEE-STRESS)/candidate['planned_risk_usd'],exit_reason=reason,entry_latency_seconds=(entry_ns-signal)/NS,entry_gap_extra_seconds=(entry_ns-signal-2*NS)/NS,exit_latency_seconds=(start-exit_decision)/NS,exit_gap_extra_seconds=(start-exit_decision-2*NS)/NS)
            continue
        stop_touch=r['low']<=stop if side==1 else r['high']>=stop
        bb=preview['BB_upper_at_high'] if side==1 else preview['BB_lower_at_low']
        bb_touch=bb is not None and (r['high']>bb if side==1 else r['low']<bb)
        level=preview['OR_high'] if side==1 else preview['OR_low']
        or_touch=preview['OR_active_for_second'] and level is not None and side*(level-entry)>=TICK and (r['high']>=level if side==1 else r['low']<=level)
        if stop_touch:exit_decision=end;reason='stop_touch_second_end_delayed_market'
        elif bb_touch:exit_decision=end;reason='moving_BB_touch_second_end_delayed_market'
        elif or_touch:exit_decision=end;reason='OR60_touch_second_end_delayed_market'
        elif end>=clock['flatten_ns']:exit_decision=clock['flatten_ns'];reason='session_flatten_delayed_market'
    return dict(label_status='excluded_missing_delayed_exit_open',entry_ns=entry_ns,entry_price=entry,exit_decision_ns=exit_decision,exit_reason=reason)
