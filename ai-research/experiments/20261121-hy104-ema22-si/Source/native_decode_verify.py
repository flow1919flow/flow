from common import *
from nautilus_trader.model.objects import Price,Quantity
def main():
 rows=json.loads((PRIVATE/'native-decode-samples.json').read_text());count=0;largest=0.
 for r in rows:
  for i,(hexraw,value) in enumerate(zip(r['raw'],r['decoded'])):
   raw=int.from_bytes(bytes.fromhex(hexraw),'little',signed=i<2)
   native=Price.from_raw(raw,r['price_precision']) if i<2 else Quantity.from_raw(raw,r['size_precision'])
   err=abs(float(native.as_decimal())-value);assert err<1e-7*max(1,abs(value));largest=max(largest,err);count+=1
 save(PUBLIC/'native-decode-proof.json',{'status':'passed','scalar_checks':count,'max_abs_error':largest,'engine':'NautilusTrader1.231.0 nativePrice/Quantity.from_raw','scope':'First/last filteredquote rows,allinputfilehashesverified separately'})
 print('Native decode checks:',count)
if __name__=='__main__':main()
