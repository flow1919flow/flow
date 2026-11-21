"""Pure structural helpers for 1-second ES prices, no strategy/labels/API."""
from pathlib import Path
from datetime import datetime,date,timezone,timedelta
from zoneinfo import ZoneInfo
import hashlib,json,re
import numpy as np

HERE=Path(__file__).resolve().parents[1]
ROOT=HERE.parents[1]
CT=ZoneInfo('America/Chicago');NS=1_000_000_000
TICK_NANOS=250_000_000
QUARTERLY=re.compile(r'ES[HMUZ]\d{1,2}\Z')
KNOWN_VENDOR_FLAGS={'2025-11-28':'provider_reported_degraded_known_year_retained'}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def save(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n');temp.replace(path)


def utcnow():return datetime.now(timezone.utc).isoformat()


def vendor_flag(day):return KNOWN_VENDOR_FLAGS.get(day,'no_explicit_vendor_degradation_flag_recorded')


def ns_date(d):return int(np.datetime64(str(d),'ns').astype(np.int64))


def ct_ns(day,hour,minute):
    d=date.fromisoformat(day)
    return int(datetime(d.year,d.month,d.day,hour,minute,tzinfo=CT).timestamp())*NS


def native_calendar():
    """Read only exact native session clocks, never trades or labels."""
    base=ROOT/'outputs/NQ-Woche-20261118/ema22-history-acceptance-20261119/ES/SQX/evaluation'
    rows={};sources=[]
    for manifest in sorted(base.glob('*/manifest.txt')):
        seed=Path(manifest.read_text().splitlines()[2]);sources.append(dict(path=str(seed),sha256=sha(seed)))
        for line in seed.read_text().splitlines():
            fields=line.split(',');op,cl,fl=map(int,fields[:3])
            day=datetime.fromtimestamp(op//NS,timezone.utc).astimezone(CT).date().isoformat()
            value=dict(session_open_ns=op,session_close_ns=cl,flatten_ns=fl,calendar_status='exact_native_session_metadata')
            if day in rows:assert rows[day]==value
            rows[day]=value
    return rows,sources


class Calendar:
    def __init__(self):
        self.exact,self.sources=native_calendar();self.overlay={};self.overlay_sha256=None
        path=ROOT/'outputs/ES-FiveYear-ML-20261121/Public/calendar-overlay-2021-2025.json'
        if path.exists():
            self.overlay_sha256=sha(path)
            if self.overlay_sha256!='81ce4d6785df4e94ed253faf73bf03b87ef1c5471ee49cef362eb7aabe20e5c3':raise ValueError('OlderresearchcalendaroverlaynotboundtoacceptedSHA')
            self.overlay=json.loads(path.read_text())['dates']
    def get(self,day):
        d=date.fromisoformat(day)
        if d.weekday()>=5:return None
        if day in self.exact:return self.exact[day]
        if '2025-11-24'<=day<'2026-10-31' and day not in self.exact:return None
        if day in self.overlay:
            row=self.overlay[day]
            if row['status']=='closed':return None
            if row['status']=='open':return {k:row[k] for k in ['session_open_ns','session_close_ns','flatten_ns','calendar_status']}
        return dict(session_open_ns=ct_ns(day,8,30),session_close_ns=ct_ns(day,16,0),flatten_ns=ct_ns(day,15,9),calendar_status='native_weekly450_template_older_CME_overlay_unverified')


class BarAccumulator:
    """Bounded 5min state, exact integer OHLCV, detects duplicate seconds.

    At most one small accumulator per raw-contract/5minute bucket. No raw
    seconds are retained here and no all-parent DataFrame is constructed.
    """
    def __init__(self):self.bars={};self.seconds=0
    def add(self,symbol,iid,day,calendar,rows):
        if not len(rows):return
        ts=rows['ts_event'].astype(np.int64)
        if np.any(ts%NS):raise ValueError('1s timestamp is not aligned to a second')
        bins=((ts-calendar['session_open_ns'])//(300*NS)).astype(np.int64)
        for bucket in np.unique(bins):
            group=rows[bins==bucket]
            order=np.argsort(group['ts_event'],kind='stable');group=group[order]
            stamps=group['ts_event'].astype(np.int64)
            if len(np.unique(stamps))!=len(stamps):raise ValueError('Duplicate raw-contract1s interval insidechunk')
            start=calendar['session_open_ns']+int(bucket)*300*NS
            offsets=((stamps-start)//NS).astype(int)
            mask=sum(1<<int(offset) for offset in offsets)
            key=(symbol,int(iid),day,int(bucket))
            first=int(stamps[0]);last=int(stamps[-1])
            if key not in self.bars:
                self.bars[key]=dict(raw_symbol=symbol,instrument_id=int(iid),day=day,bar_index=int(bucket),bar_start_ns=start,bar_end_ns=min(start+300*NS,calendar['session_close_ns']),available_ns=min(start+300*NS,calendar['session_close_ns']),open_nanos=int(group['open'][0]),high_nanos=int(group['high'].max()),low_nanos=int(group['low'].min()),close_nanos=int(group['close'][-1]),volume=int(group['volume'].sum(dtype=np.uint64)),second_records=len(group),first_second_ns=first,last_second_ns=last,_mask=mask)
            else:
                b=self.bars[key]
                if b['_mask']&mask:raise ValueError('Duplicate raw-contract1s interval acrosschunks')
                if first<b['first_second_ns']:b['first_second_ns']=first;b['open_nanos']=int(group['open'][0])
                if last>b['last_second_ns']:b['last_second_ns']=last;b['close_nanos']=int(group['close'][-1])
                b['high_nanos']=max(b['high_nanos'],int(group['high'].max()));b['low_nanos']=min(b['low_nanos'],int(group['low'].min()))
                b['volume']+=int(group['volume'].sum(dtype=np.uint64));b['second_records']+=len(group);b['_mask']|=mask
            self.seconds+=len(group)
    def records(self):
        result=[]
        for _,b in sorted(self.bars.items()):
            z={k:v for k,v in b.items() if k!='_mask'}
            z['expected_seconds']=(z['bar_end_ns']-z['bar_start_ns'])//NS
            z['absent_second_intervals']=z['expected_seconds']-z['second_records']
            if z['absent_second_intervals']<0:raise ValueError('Too many1s intervals in5m bucket')
            result.append(z)
        return result


def maturity(symbol):
    """Task-restricted 2021–2026 mapping; keep actual raw symbol in data."""
    m=re.fullmatch(r'ES([HMUZ])(\d{1,2})',symbol)
    if not m:raise ValueError('Not a raw ES quarterly outright')
    year=int(m[2]);year=2020+year if year<10 else 2000+year
    return year,{'H':3,'M':6,'U':9,'Z':12}[m[1]]


def select_prior(rows,incumbent):
    valid=[r for r in rows if r['rth_volume']>0 and (incumbent is None or maturity(r['raw_symbol'])>=maturity(incumbent))]
    return sorted(valid,key=lambda r:(-r['rth_volume'],r['raw_symbol']!=incumbent,maturity(r['raw_symbol']),r['raw_symbol']))[0] if valid else None
