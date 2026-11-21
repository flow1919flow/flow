"""Explicit public allowlist: code + aggregate evidence, never private SI/quotes."""
from common import *
def main():
 assert json.loads((PUB/'acceptance.json').read_text())['status']=='passed'
 assert json.loads((PUB/'mlflow-receipt.json').read_text())['status']=='FINISHED'
 prefix='ai-research/experiments/20261121-si1746/';entries=[];audit=[]
 for path in sorted((HERE/'Source').glob('*.py'))+sorted(PUB.glob('*.json'))+[PUB/'README.md']:
  content=path.read_text()
  if path.name=='context-checks.json':
   value=json.loads(content);value.pop('rows',None);content=json.dumps(value,indent=2,ensure_ascii=False)+'\n'
  if path.name=='training-design.json':
   value=json.loads(content)
   for f in value['folds']:
    for key in ['latest_train_outcome_ns','first_test_information_ns']:f.pop(key,None)
   content=json.dumps(value,indent=2,ensure_ascii=False)+'\n'
  dest=prefix+str(path.relative_to(HERE));entries.append({'path':dest,'mode':'100644','type':'blob','content':content})
  audit.append({'path':dest,'original_sha256':sha(path),'export_sha256':hashlib.sha256(content.encode()).hexdigest()})
 entries.append({'path':prefix+'README.md','mode':'100644','type':'blob','content':(PUB/'README.md').read_text()+'\n![Gepaarter Vergleich](Public/comparison.png)\n'})
 save(PRIV/'github-export-entries.json',entries)
 save(PUB/'public-export-proof.json',{'allowlist':'Source Python, Public aggregate JSON/README, aggregate PNG. No Private folder, inputs, raw quote bytes, raw messages/IDs or weights.',
  'entries':audit,'private_row_data_uploaded':False,'redactions':'Remove event-level exact timestamp proof rows; retain aggregate prefix counts. Strip single outcome boundary timestamps from public fold design.'})
 print('Prepared public allowlist entries:',len(entries))
if __name__=='__main__':main()
