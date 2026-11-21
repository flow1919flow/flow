"""Loopback-only ephemeral API key handoff. Never persists/prints API key.

POST /receive keeps key in this process memory only. No model call starts there.
Root must explicitly POST /start using local control token AFTER an approved,
hash-matching authorization.json exists. Runner receives key only in child env.
"""
from pathlib import Path
from http.server import HTTPServer,BaseHTTPRequestHandler
import html,json,os,secrets,subprocess,sys,time,urllib.parse
HERE=Path(__file__).resolve().parent;PRIVATE=HERE/'Private';PRIVATE.mkdir(exist_ok=True)
CONTROL=secrets.token_urlsafe(32);CSRF=secrets.token_urlsafe(32)
STATE={'key':None,'received_at':None,'process':None,'started_at':None,'last_error':None}

def write(path,value):
 path.write_text(json.dumps(value,indent=2)+'\n');os.chmod(path,0o600)
def public_status():
 child=STATE['process']
 return {'key_received_in_memory':STATE['key'] is not None,'runner_started':child is not None,
  'runner_running':bool(child is not None and child.poll() is None),'runner_exit_code':child.poll() if child is not None else None,
  'last_error_type':STATE['last_error'],'API_key_saved_to_disk':False,'API_key_returned_in_responses':False}

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def valid_host(self):return self.client_address[0]=='127.0.0.1' and self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'
 def send(self,value,status=200,mime='application/json'):
  body=(json.dumps(value) if mime=='application/json' else value).encode();self.send_response(status)
  self.send_header('Content-Type',mime+'; charset=utf-8');self.send_header('Content-Length',str(len(body)))
  self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
  self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
  self.end_headers();self.wfile.write(body)
 def do_GET(self):
  if not self.valid_host():return self.send({'error':'local_host_required'},403)
  if self.path=='/status':return self.send(public_status())
  if self.path!='/':return self.send({'error':'not_found'},404)
  status=public_status();ready=status['key_received_in_memory'];text='Schlüssel ist nur im Arbeitsspeicher angekommen. Der Test startet erst nach Freigabe des eingefrorenen Plans.' if ready else 'Bitte deinen DeepInfra-API-Key direkt hier einfügen. Nicht in den Chat posten.'
  form='' if ready or status['runner_started'] else f'<form method="post" action="/receive"><input type="hidden" name="csrf" value="{CSRF}"><label for="key">DeepInfra API-Key</label><input id="key" name="key" type="password" autocomplete="off" required maxlength="512"><button>Schlüssel verdeckt übergeben</button></form>'
  page=f'''<!doctype html><html lang="de"><meta charset="utf-8"><title>DeepInfra · Schlüssel sicher übergeben</title><style>body{{background:#f1f6fc;color:#173b60;font:18px/1.6 system-ui;margin:0}}main{{max-width:720px;margin:8vh auto;padding:36px;background:white;border:1px solid #d7e6f2;border-radius:20px}}h1{{font-size:28px}}label,input,button{{display:block}}input{{width:95%;font-size:22px;padding:12px;margin:12px 0}}button{{background:#145e9d;color:white;border:0;border-radius:8px;padding:14px 20px;font-size:18px}}.muted{{color:#60768e}}</style><main><h1>DeepInfra · Klassifikation der Setups</h1><p><b>Drex Max Finance + Clef</b> · 230 spätere Setups je Modell · maximal 1USD Gesamtbudget.</p><p>{text}</p>{form}<p class="muted">Dieses lokale Fenster speichert den Schlüssel nicht. Er bleibt ausschließlich im Arbeitsspeicher und wird nach gesonderter Freigabe nur an den lokalen Testprozess übergeben. An DeepInfra gehen fünf numerische Setup-Merkmale und frühere Vergleichsfälle mit bekannten Labels; keine Roh-Ticks, Konten, Termine oder Zugangsdaten als Modelldaten.</p><p>Kein Training großer Gewichte, keine GPU-Miete und keine Änderung laufender Sims.</p></main></html>'''
  return self.send(page,mime='text/html')
 def do_POST(self):
  if not self.valid_host():return self.send({'error':'local_host_required'},403)
  origin=self.headers.get('Origin');expected=f'http://127.0.0.1:{self.server.server_port}'
  if origin!=expected:return self.send({'error':'same_origin_required'},403)
  try:
   length=int(self.headers.get('Content-Length','0'));assert 0<length<=8192
   data=self.rfile.read(length)
   if self.path=='/receive':
    values=urllib.parse.parse_qs(data.decode(),keep_blank_values=True)
    if not secrets.compare_digest(values.get('csrf',[''])[0],CSRF):return self.send({'error':'invalid_form_token'},403)
    if STATE['process'] is not None:return self.send({'error':'already_started'},409)
    key=values.get('key',[''])[0].strip()
    if not 8<=len(key)<=512 or any(c.isspace() for c in key):return self.send({'error':'invalid_key_format'},400)
    STATE['key']=key;STATE['received_at']=time.time();key=None
    self.send_response(303);self.send_header('Location','/');self.send_header('Cache-Control','no-store');self.send_header('Content-Length','0');self.end_headers();return
   if self.path=='/start':
    values=json.loads(data)
    if not secrets.compare_digest(str(values.get('control_token','')),CONTROL):return self.send({'error':'invalid_control_token'},403)
    if STATE['process'] is not None:return self.send({'error':'already_started'},409)
    if STATE['key'] is None:return self.send({'error':'key_not_received'},409)
    auth=HERE/'authorization.json';plan=HERE/'plan.json'
    if not auth.is_file():return self.send({'error':'authorization_not_ready'},409)
    import hashlib
    approval=json.loads(auth.read_text());p=json.loads(plan.read_text())
    if not (approval.get('approved') is True and approval.get('plan_sha256')==hashlib.sha256(plan.read_bytes()).hexdigest() and approval.get('model_ids')==p['models'] and approval.get('numeric_features_and_past_labels_to_deepinfra_approved') is True and 0<float(approval.get('max_usd',0))<=1):return self.send({'error':'authorization_mismatch'},409)
    env=os.environ.copy();env['DEEPINFRA_API_KEY']=STATE['key'];env['PYTHONUNBUFFERED']='1'
    with (HERE/'runner.log').open('ab') as log:
     child=subprocess.Popen([sys.executable,str(HERE/'decision_probe.py'),'run','--authorization',str(auth)],cwd=str(HERE),env=env,stdout=log,stderr=subprocess.STDOUT)
    STATE['process']=child;STATE['started_at']=time.time();STATE['key']=None;env.pop('DEEPINFRA_API_KEY',None)
    return self.send(public_status())
   return self.send({'error':'not_found'},404)
  except Exception as exc:
   STATE['last_error']=type(exc).__name__;return self.send({'error':'local_request_failed','error_type':type(exc).__name__},400)

def main():
 server=HTTPServer(('127.0.0.1',0),Handler);server.timeout=2
 url=f'http://127.0.0.1:{server.server_port}'
 write(PRIVATE/'form-control.json',{'url':url,'control_token':CONTROL})
 write(HERE/'key-form-receipt.json',{'url':url,'status_url':url+'/status','host':'127.0.0.1','API_key_persistence':False,'submit_does_not_start_API':True,'runner_start_requires_explicit_root_control':True,'pid':os.getpid()})
 print('Local masked key form ready:',url,flush=True)
 started=time.time()
 while time.time()-started<3600:
  server.handle_request()
  if STATE['key'] is not None and time.time()-STATE['received_at']>1800:STATE['key']=None
 server.server_close();STATE['key']=None
if __name__=='__main__':main()
