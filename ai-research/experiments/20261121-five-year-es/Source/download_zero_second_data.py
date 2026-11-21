"""Download only exact 0-USD quotes. Key lives in memory, never in artifacts."""
from pathlib import Path
from datetime import date, datetime, timezone
import getpass, hashlib, json, os, sys, time
import databento as db

HERE = Path(__file__).resolve().parents[1]
OUT = HERE.parent/'ES-FiveYear-SecondData-20261121'
RAW = OUT/'Raw'
PUBLIC = OUT/'Public'

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def stamp(): return datetime.now(timezone.utc).isoformat()

def save(path,x):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n');tmp.replace(path)

def months(first,last):
    d=first
    while d<last:
        e=date(d.year+(d.month==12),1 if d.month==12 else d.month+1,1)
        yield d,e
        d=e

def main():
    RAW.mkdir(parents=True,exist_ok=True);PUBLIC.mkdir(parents=True,exist_ok=True)
    key=getpass.getpass('Databento API key (hidden, memory only; zero-only downloads): ')
    client=db.Historical(key=key);key=None
    # Known year first: its mandatory native acceptance can start while older
    # prices download. Downloading prices does not generate sealed outcomes.
    blocks=list(months(date(2025,11,1),date(2026,11,1)))+list(months(date(2021,11,1),date(2025,11,1)))
    manifest_path=PUBLIC/'download-manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    done={r['month']:r for r in manifest if r.get('status')=='downloaded_and_header_verified'}
    for start,end in blocks:
        month=start.strftime('%Y-%m');target=RAW/f'GLBX-{month}.dbn.zst'
        if month in done:
            assert target.is_file() and sha(target)==done[month]['sha256'],'Existing artifact differs; stop'
            continue
        assert not target.exists(),'Unattested existing file; do not overwrite'
        part=target.with_suffix(target.suffix+'.part')
        assert not part.exists(),'Prior incomplete download; inspect before retrying'
        req=dict(dataset='GLBX.MDP3',symbols=['ES.FUT'],stype_in='parent',schema='ohlcv-1s',
                 start=start.isoformat()+'T00:00:00Z',end=end.isoformat()+'T00:00:00Z')
        rec=dict(month=month,request=req,quoted_at_utc=stamp(),status='price_pending')
        try:
            price=float(client.metadata.get_cost(**req));rec['quoted_cost_USD']=price
            save(PUBLIC/'download-progress.json',dict(state='quoting',month=month,completed=len(done),total=len(blocks),new_cost_USD=0))
            if price!=0.0:
                rec['status']='positive_or_invalid_quote_BLOCKED_NO_DOWNLOAD'
                manifest.append(rec);save(manifest_path,manifest)
                save(PUBLIC/'download-progress.json',dict(state='stopped_nonzero_quote',month=month,completed=len(done),total=len(blocks),new_cost_USD=0))
                print(json.dumps(rec),flush=True);return
            # Revalidate the exact request immediately before the outbound data.
            save(PUBLIC/'download-progress.json',dict(state='downloading_zero_quoted_block',month=month,completed=len(done),total=len(blocks),new_cost_USD=0))
            t=time.time();store=client.timeseries.get_range(**req,path=part)
            assert str(store.metadata.dataset)=='GLBX.MDP3'
            assert str(store.metadata.schema)=='ohlcv-1s'
            assert part.is_file() and part.stat().st_size>0
            part.replace(target)
            rec.update(status='downloaded_and_header_verified',completed_at_utc=stamp(),
                       relative_path='Raw/'+target.name,bytes=target.stat().st_size,
                       sha256=sha(target),seconds=time.time()-t,
                       schema=str(store.metadata.schema),dataset=str(store.metadata.dataset),
                       metadata_start=str(store.metadata.start),metadata_end=str(store.metadata.end),
                       key_persisted=False)
            del store
            done[month]=rec;manifest.append(rec);save(manifest_path,manifest)
            save(PUBLIC/'download-progress.json',dict(state='running',last_completed=month,completed=len(done),total=len(blocks),new_cost_USD=0,
                       downloaded_bytes=sum(r['bytes'] for r in done.values()),known_year_complete=all(d.strftime('%Y-%m') in done for d,_ in blocks[:12])))
            print(json.dumps({k:rec[k] for k in ['month','status','quoted_cost_USD','bytes','seconds','sha256']}),flush=True)
        except Exception as exc:
            rec.update(status='error_no_automatic_retry',error_type=type(exc).__name__,at_utc=stamp())
            manifest.append(rec);save(manifest_path,manifest)
            save(PUBLIC/'download-progress.json',dict(state='stopped_error_no_retry',month=month,error_type=type(exc).__name__,completed=len(done),total=len(blocks),new_cost_USD=0))
            print(json.dumps({'state':'stopped_error_no_retry','month':month,'error_type':type(exc).__name__}),flush=True)
            return
    save(PUBLIC/'download-progress.json',dict(state='all60_months_complete',completed=len(done),total=len(blocks),new_cost_USD=0,
         downloaded_bytes=sum(r['bytes'] for r in done.values()),known_year_complete=True,key_persisted=False,
         no_candidate_labels_or_models=True,completed_at_utc=stamp()))
    print('All 60 zero-quoted months complete; no key saved, no outcomes/model computed.',flush=True)

if __name__=='__main__':main()
