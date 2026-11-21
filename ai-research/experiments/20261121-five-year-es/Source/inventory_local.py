"""Read-only audit of existing raw Databento minute bars, never strategy labels.

Retain outright contract mappings and per-file hashes. No roll, price adjustment,
candidate extraction, labels, training, API call or paid download occurs here.
"""
from pathlib import Path
from datetime import datetime, timezone, date
from collections import Counter
import hashlib, json, re, os, time
import numpy as np
import databento as db

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
SOURCE = ROOT / 'outputs/Databento-Bestand.json'
START = np.datetime64('2021-11-24T00:00:00', 'ns').astype(np.int64).item()
END = np.datetime64('2025-11-24T00:00:00', 'ns').astype(np.int64).item()
WARM_START = np.datetime64('2021-11-01T00:00:00', 'ns').astype(np.int64).item()
FULL_END = np.datetime64('2026-11-01T00:00:00', 'ns').astype(np.int64).item()


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def save(path, obj):
    p = Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    tmp = p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n');tmp.replace(p)


def day_ns(d):
    return np.datetime64(str(d), 'ns').astype(np.int64).item()


def iso(n):
    return np.datetime_as_string(np.datetime64(int(n), 'ns'), unit='s')+'Z'


def main():
    began = time.time()
    prior = json.loads(SOURCE.read_text())
    minute = [x for x in prior['files'] if x.get('schema') == 'ohlcv-1m' and 'ES.FUT' in x.get('symbols', [])]
    selected=[]
    for x in minute:
        a,b=[int(datetime.fromisoformat(x[k]).timestamp()*1e9) for k in ['requested_start','requested_end']]
        if a < FULL_END and b > WARM_START:
            selected.append(x)
    selected.sort(key=lambda x:x['requested_start'])
    assert len(selected)==60
    totals=Counter();days=Counter();contracts=Counter();files=[];all_mappings=[]
    for number, old in enumerate(selected, 1):
        p=Path(old['path']);assert p.exists() and p.stat().st_size==old['bytes']
        store=db.DBNStore.from_file(p);m=store.metadata
        assert str(m.schema)=='ohlcv-1m' and m.dataset=='GLBX.MDP3' and str(m.stype_in)=='parent'
        mappings=[]
        for symbol, intervals in m.mappings.items():
            if not re.fullmatch(r'ES[HMUZ]\d{1,2}',symbol):continue
            for interval in intervals:
                z=dict(raw_symbol=symbol,instrument_id=int(interval['symbol']),start_date=str(interval['start_date']),end_date=str(interval['end_date']))
                mappings.append(z)
                all_mappings.append(dict(source_file=p.name,**z))
        assert mappings
        file_contracts=Counter();file_days=Counter();record_count=0;extra=0;bad=0;first=None;last=None
        mapping_by_id={}
        for z in mappings:mapping_by_id.setdefault(z['instrument_id'],[]).append(z)
        for array in store.to_ndarray(count=250000):
            record_count+=len(array)
            ids=np.array(list(mapping_by_id),dtype=array['instrument_id'].dtype)
            candidate=array[np.isin(array['instrument_id'],ids)]
            for instrument, intervals in mapping_by_id.items():
                sub=candidate[candidate['instrument_id']==instrument]
                if not len(sub):continue
                for z in intervals:
                    mask=(sub['ts_event']>=max(WARM_START,day_ns(z['start_date'])))&(sub['ts_event']<min(FULL_END,day_ns(z['end_date'])))
                    rows=sub[mask]
                    if not len(rows):continue
                    file_contracts[z['raw_symbol']]+=len(rows)
                    within=(rows['ts_event']>=START)&(rows['ts_event']<END)
                    extra+=int(within.sum())
                    if first is None or int(rows['ts_event'].min())<first:first=int(rows['ts_event'].min())
                    if last is None or int(rows['ts_event'].max())>last:last=int(rows['ts_event'].max())
                    # Price integrity only, no strategy event/label/outcome.
                    bad+=int(((rows['low']>rows['high'])|(rows['open']<rows['low'])|(rows['open']>rows['high'])|(rows['close']<rows['low'])|(rows['close']>rows['high'])).sum())
                    dates,counts=np.unique(rows['ts_event'].astype('datetime64[ns]').astype('datetime64[D]'),return_counts=True)
                    file_days.update({str(k):int(v) for k,v in zip(dates,counts)})
        assert bad==0
        row=dict(path=str(p),name=p.name,bytes=p.stat().st_size,sha256=sha(p),dataset=m.dataset,schema=str(m.schema),stype_in=str(m.stype_in),stype_out=str(m.stype_out),metadata_start_ns=m.start,metadata_end_ns=m.end,all_parent_records=record_count,ES_quarterly_outright_records=sum(file_contracts.values()),ES_four_extra_year_records=extra,first_ES_timestamp=iso(first),last_ES_timestamp=iso(last),ES_raw_contract_counts=dict(file_contracts),ES_UTC_date_counts=dict(sorted(file_days.items())),ES_mapping_intervals=mappings,ohlc_invariant_violations=bad)
        files.append(row);days.update(file_days);contracts.update(file_contracts)
        totals.update(compressed_bytes=p.stat().st_size,all_parent_records=record_count,ES_quarterly_outright_records=sum(file_contracts.values()),ES_four_extra_year_records=extra)
        save(HERE/'Private/raw-source-inventory-incremental.json',files)
        save(HERE/'Public/progress.json',dict(status='AUDITING_EXISTING_LOCAL_PRICES',completed=number,total=len(selected),last_month=p.name,elapsed_seconds=time.time()-began,network_calls=0,new_download_cost_USD=0))
        print(number,len(selected),p.name,'ESoutright',sum(file_contracts.values()),flush=True)
    relevant_dates=sorted(d for d in days if '2021-11-24'<=d<'2025-11-24')
    expected=[];d=np.datetime64('2021-11-24');e=np.datetime64('2025-11-24')
    while d<e:
        # Missing weekday is a coverage flag, not automatically a missing trading session.
        if date.fromisoformat(str(d)).weekday()<5:expected.append(str(d))
        d+=np.timedelta64(1,'D')
    gaps=sorted(set(expected)-set(relevant_dates))
    source_path=HERE/'Private/raw-source-inventory.json';save(source_path,files)
    save(HERE/'Private/ES-raw-contract-mapping-intervals.json',all_mappings)
    save(HERE/'Private/ES-UTC-date-record-counts.json',dict(sorted(days.items())))
    summary=dict(status='EXISTING_LOCAL_OHLCV_VERIFIED_NO_DOWNLOAD_NEEDED',checked_at_utc=datetime.now(timezone.utc).isoformat(),scope='Read-only raw price metadata/counts/hash audit, no strategy candidates/labels/outcomes/training',original_inventory_sha256=sha(SOURCE),original_ohlcv_files_all_history=len(minute),original_ohlcv_files_existing=sum(Path(x['path']).exists() for x in minute),original_ohlcv_requested_span=[min(x['requested_start'] for x in minute),max(x['requested_end'] for x in minute)],audit_files=len(files),audit_span=['2021-11-01','2026-11-01_exclusive'],four_extra_year_span=['2021-11-24','2025-11-24_exclusive'],totals=dict(totals),distinct_ES_raw_quarterly_symbols=len(contracts),four_extra_year_UTC_dates_with_ES_records=len(relevant_dates),weekdays_without_any_ES_records=gaps,weekday_gap_interpretation='UTC weekday flag only; holidays and exchange-session calendar still require final protocol validation',ohlc_invariant_violations=0,preserves_raw_contracts=True,includes_spreads=False,back_adjusted=False,roll_selection='None chosen here; retain raw symbol and dated instrument_id mapping, candidate protocol must freeze roll rule',credentials={'DATABENTO_API_KEY_present':bool(os.environ.get('DATABENTO_API_KEY')),'DB_API_KEY_present':bool(os.environ.get('DB_API_KEY')),'other_secret_stores_searched':False},network_calls=0,new_downloads=0,new_usage_cost_USD=0,new_credit_consumption_USD=0,files_inventory_sha256=sha(source_path),elapsed_seconds=time.time()-began)
    save(HERE/'Public/local-coverage.json',summary)
    save(HERE/'Public/progress.json',dict(status=summary['status'],completed=len(files),network_calls=0,new_download_cost_USD=0,elapsed_seconds=time.time()-began))
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
