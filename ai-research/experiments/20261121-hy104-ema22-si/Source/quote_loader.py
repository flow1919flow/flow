"""Verified Arrow quote decoder/Loader reused;no event labels oroldstudy writes."""
from common import *
import pyarrow.parquet as pq

def decoded(c):
 a=c.combine_chunks();v=np.frombuffer(a.buffers()[1],dtype='<u8',count=len(a)*2,offset=a.offset*16).reshape(-1,2)
 return (v[:,0].astype(np.float64)+v[:,1].view('<i8').astype(np.float64)*18446744073709551616.)/1e16

class Loader:
 def __init__(self):
  self.days={x['date']:x for x in json.loads(INDEX.read_text())['completed']}
  self.manifest={};self.native=[];self.reports={}
 def tape(self,symbol,start,end):
  market=symbol[:2];tick=MARKETS[market][0];parts=[]
  first=datetime.fromtimestamp(start/NS,timezone.utc).date();last=datetime.fromtimestamp(end/NS,timezone.utc).date()
  for k in range((last-first).days+1):
   day=self.days.get(str(first+timedelta(days=k)))
   if day is None:continue
   base=Path(day['catalog']);pointer=Path(day['completion_pointer'])
   if day['date'] not in self.reports:
    assert sha(pointer)==day['completion_pointer_sha256']
    ptr=json.loads(pointer.read_text());rp=Path(ptr['report']);assert sha(rp)==ptr['sha256']
    report=json.loads(rp.read_text());assert report['source_sha256']==day['source_sha256']
    self.reports[day['date']]=report
   report=self.reports[day['date']]
   for path in sorted((base/'data/quote_tick'/f'{symbol}.GLBX').glob('*.parquet')):
    relative=str(path.relative_to(base));expected=report['parquet_sha256'][relative]
    if str(path) not in self.manifest:
     assert sha(path)==expected, f'Quote hash mismatch: {path}'
     self.manifest[str(path)]={'sha256':expected,'source_sha256':day['source_sha256'],'date':day['date'],'instrument':symbol}
    table=pq.read_table(path,filters=[('ts_init','>=',int(start-10*NS)),('ts_init','<=',int(end+10*NS))])
    if not len(table):continue
    cols=[decoded(table[x]) for x in ('bid_price','ask_price','bid_size','ask_size')]
    for ix in (0,len(table)-1):
     self.native.append({'path':str(path),'row_in_filtered_table':ix,'raw':[table[x][ix].as_py().hex() for x in ('bid_price','ask_price','bid_size','ask_size')],
      'decoded':[float(c[ix]) for c in cols],'price_precision':int(table.schema.metadata[b'price_precision']),'size_precision':int(table.schema.metadata[b'size_precision'])})
    ev=table['ts_event'].to_numpy();init=table['ts_init'].to_numpy();ts=np.maximum(ev,init).astype(np.int64)
    bid,ask,bs,az=cols
    valid=np.isfinite(bid)&np.isfinite(ask)&np.isfinite(bs)&np.isfinite(az)&(bid>0)&(ask>=bid)&(ask<1e8)&(bs>=1)&(az>=1)&(bs<1e12)&(az<1e12)
    for c in (bid,ask):
     assert np.max(np.abs(c[valid]/tick-np.rint(c[valid]/tick)),initial=0)<1e-5
    parts.append((ts,ev.astype(np.int64),init.astype(np.int64),bid,ask,bs,az,valid))
  if not parts:return None
  arrays=[np.concatenate([p[i] for p in parts]) for i in range(8)]
  order=np.argsort(arrays[0],kind='stable');arrays=[x[order] for x in arrays]
  # Duplicate timestamp: deterministic latest source row; never backfill invalid snapshots.
  keep=np.r_[arrays[0][1:]!=arrays[0][:-1],True];return [x[keep] for x in arrays]

