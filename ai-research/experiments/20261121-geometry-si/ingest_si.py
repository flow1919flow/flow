"""Load all229 verified ES SI messages into a local, auditable ML table.

No label fitting, orders, cloud calls or fabricated no-event intervals.
Message direction remains a bot-reported arrow, not inferred orderflow side.
"""
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
import hashlib,importlib.util,json,math
import pandas as pd

HERE=Path(__file__).resolve().parent;DE=HERE.parents[1]
SECOND=1_000_000_000
CHICAGO=ZoneInfo('America/Chicago')

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n');temp.replace(path)
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def utc(ns):return datetime.fromtimestamp(ns/SECOND,timezone.utc).isoformat()

def main():
    source=DE/'outputs/SI-Nautilus-Ereignistest-v1/source_reader.py'
    spec=importlib.util.spec_from_file_location('verified_si_reader',source)
    reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    all_events,audit=reader.read_archive()
    events=[e for e in all_events if e['market']=='ES' and e['event_type'] in ('STOP','ICEBERG')]
    assert len(events)==229 and len({e['message_id'] for e in events})==229
    assert Counter(e['event_type'] for e in events)=={'ICEBERG':187,'STOP':42}
    assert len({e['event_id'] for e in events})==229
    events.sort(key=lambda e:(e['ts_init'],e['event_id']))
    plan=dict(schema='SI-INGEST-229-v1',created_at_utc=datetime.now(timezone.utc).isoformat(),
        unit='one actual archived ES STOP/ICEBERG message, not one HY104 setup or independent sample',
        selection='all229 RITHMIC ES messages; all retained even if no later label available',
        source_archive_sha256=audit['source_sha256'],source_reader_sha256=sha(source),
        code_sha256=sha(Path(__file__)),known_at='max(sent,edited), Discord availability proxy only',
        decision_delay_seconds=30,primary_future_horizon_minutes=15,secondary_future_horizon_minutes=5,
        grouping='same-contract connected episodes with [decision-5min,decision+15min] overlap; Chicago calendar days for validation',
        training_started=False,price_labels_available=False,known_feed_coverage_sessions=0,
        limits=['No original Bookmap detection/receipt timestamps',
            'No true buy/sell interpretation of reported arrow',
            'Archive completeness is not complete feed coverage',
            'No model or financial superiority follows from loading data'])
    write(HERE/'SI/ingest-plan.json',plan)
    last_end={};episode_counter=Counter();prior=defaultdict(list);rows=[]
    for e in events:
        known=int(e['ts_init']);decision=known+30*SECOND
        local=datetime.fromtimestamp(decision/SECOND,timezone.utc).astimezone(CHICAGO)
        symbol=e['symbol'];start=decision-300*SECOND;end=decision+900*SECOND
        if symbol not in last_end or start>last_end[symbol]:episode_counter[symbol]+=1
        last_end[symbol]=max(end,last_end.get(symbol,end))
        event_key=hashlib.sha256((audit['source_sha256']+'|'+e['event_id']).encode()).hexdigest()
        recent=[p for p in prior[symbol] if 0<known-p<=900*SECOND]
        lo,hi=float(e['zone_low']),float(e['zone_high']);size=abs(e['signed_size'])
        row=dict(event_key=event_key,symbol=symbol,event_type=e['event_type'],
            reported_arrow=int(e['reported_direction']),absolute_reported_size=size,
            log1p_reported_size=math.log1p(size),absolute_reported_factor=abs(float(e['factor'])),
            zone_low=lo,zone_high=hi,zone_width_ticks=(hi-lo)/.25,
            known_at_ns=known,known_at_utc=utc(known),decision_ns=decision,decision_utc=utc(decision),
            chicago_calendar_day=local.date().isoformat(),chicago_minute_of_day=local.hour*60+local.minute+local.second/60,
            episode_id=f'{symbol}-{episode_counter[symbol]:04d}',
            observed_archived_count_prior15m=len(recent),edited=bool(e['edited_ns']),
            original_event_time_known=False,actual_receive_time_known=False,
            label_status='pending_exact_contract_quote_coverage',
            source_archive_sha256=audit['source_sha256'])
        rows.append(row);prior[symbol].append(known)
    frame=pd.DataFrame(rows);dest=HERE/'SI/es-events-229.parquet';dest.parent.mkdir(parents=True,exist_ok=True)
    frame.to_parquet(dest,index=False)
    frame.to_csv(HERE/'SI/es-events-229.csv',index=False)
    restored=pd.read_parquet(dest)
    pd.testing.assert_frame_equal(frame,restored)
    assert (restored['decision_ns']>restored['known_at_ns']).all()
    assert not restored['original_event_time_known'].any()
    result=dict(state='all229_ES_events_loaded_and_roundtrip_verified',rows=len(frame),
        unique_messages=229,types=dict(Counter(frame.event_type)),symbols=dict(Counter(frame.symbol)),
        utc_calendar_days=len({utc(e['ts_init'])[:10] for e in events}),
        chicago_calendar_days=int(frame.chicago_calendar_day.nunique()),
        connected_overlap_episodes=int(frame.episode_id.nunique()),edited_messages=int(frame.edited.sum()),
        first_known_at_utc=utc(events[0]['ts_init']),last_known_at_utc=utc(events[-1]['ts_init']),
        parquet_sha256=sha(dest),csv_sha256=sha(HERE/'SI/es-events-229.csv'),
        original_archive_sha256=audit['source_sha256'],original_archive_pagination_verified=audit['pagination_chain_verified'],
        parquet_roundtrip_identical=True,private_raw_messages_copied=False,
        all_rows_retained=True,supervised_model_trained=False,label_status='pending',
        verified_feed_coverage_sessions=0,absence_is_not_no_event=True,live_changed=False,cloud_spend_usd=0)
    write(HERE/'SI/ingest-result.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
