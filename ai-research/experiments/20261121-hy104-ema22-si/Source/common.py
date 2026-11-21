from pathlib import Path
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
import hashlib,importlib.util,json,math
import numpy as np
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
PRIVATE=HERE/'Private';PUBLIC=HERE/'Public';NS=1_000_000_000;CT=ZoneInfo('America/Chicago')
INDEX=ROOT/'outputs/Flo-Datenimporte/TBBO-2026-05-22_bis_2026-10-30-v2/katalog_index.json'
NATIVE=ROOT/'outputs/NQ-Woche-20261118/ema22-history-acceptance-20261119/ES/SQX/evaluation'
MARKETS={'ES':(.25,50.)}
PRICE=['side','chicago_RTH_minute','signed_move60_rv300','signed_move300_rv300','log1p_rv300_ticks','spread_ticks','signed_topsize_imbalance','quote_age_seconds']
SI=['last_STOP_arrow_relative15m','last_ICEBERG_arrow_relative15m','archived_count60m_cap5','SI_archive_status']
MODELS=['nace-ai/drex-max-finance','Cloudflare/clef'];SEED=20261121
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp')
 temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n');temp.replace(path)
def stamp():return datetime.now(timezone.utc).isoformat()
def utc(ns):return datetime.fromtimestamp(int(ns)/NS,timezone.utc).isoformat()
def local_date(ns):return datetime.fromtimestamp(int(ns)/NS,timezone.utc).astimezone(CT).date().isoformat()
def si_reader():
 path=ROOT/'outputs/SI-Nautilus-Ereignistest-v1/source_reader.py'
 assert sha(path)=='c674a84d1366e440616b1aceb184a3a949a39e79246feabb7e8625bafb9f9883'
 spec=importlib.util.spec_from_file_location('original_es_si_reader',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
