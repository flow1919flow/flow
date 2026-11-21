from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import hashlib, json, importlib.util
import numpy as np

HERE=Path(__file__).resolve().parents[1]
ROOT=HERE.parents[1]
PRIV=HERE/'Private'; PUB=HERE/'Public'
NS=1_000_000_000; CT=ZoneInfo('America/Chicago')
MARKETS={'ES':(.25,50.,2.87),'NQ':(.25,20.,2.87),'GC':(.1,100.,3.14),'CL':(.01,1000.,2.99)}
PRICE=['market_code','chicago_minute','move60_rv','move300_rv','log_rv_ticks','spread_ticks','size_imbalance','quote_age_s']
SI=['type_code','reported_arrow','log_reported_size','absolute_factor','zone_width_rv','arrow_zone_distance_rv']
SEED=20261121
INDEX=ROOT/'outputs/Flo-Datenimporte/TBBO-2026-05-22_bis_2026-10-30-v2/katalog_index.json'
CHECKPOINT=ROOT/'outputs/AI-Forschung-20261121/Models/tabpfn-v2-classifier-finetuned-zk73skhh.ckpt'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 q=p.with_suffix(p.suffix+'.tmp');q.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n');q.replace(p)
def utc(n):return datetime.fromtimestamp(int(n)/NS,timezone.utc).isoformat()
def clock(n):
 d=datetime.fromtimestamp(int(n)/NS,timezone.utc).astimezone(CT)
 td=d.date()+timedelta(days=int(d.hour>=17))
 start=datetime.combine(td-timedelta(days=1),datetime.min.time(),CT)+timedelta(hours=17)
 end=datetime.combine(td,datetime.min.time(),CT)+timedelta(hours=16)
 return str(td),d.hour*60+d.minute+d.second/60,int(start.timestamp()*NS),int(end.timestamp()*NS)
def reader():
 p=ROOT/'outputs/SI-Kontrollvergleich-v1/source_reader.py'
 s=importlib.util.spec_from_file_location('verified_reader',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
