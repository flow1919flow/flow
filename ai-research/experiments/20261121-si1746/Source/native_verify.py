"""Independent decode API comparison in original Nautilus runtime."""
from common import *
from nautilus_trader.model.objects import Price,Quantity
def main():
 rows=json.loads((PRIV/'native-decode-samples.json').read_text());n=0;max_error=0.
 for row in rows:
  for i,(raw,value) in enumerate(zip(row['raw'],row['decoded'])):
   rawint=int.from_bytes(bytes.fromhex(raw),'little',signed=i<2)
   obj=Price.from_raw(rawint,row['price_precision']) if i<2 else Quantity.from_raw(rawint,row['size_precision'])
   native=float(obj.as_decimal());err=abs(native-value);assert err<1e-7*max(1.,abs(native));max_error=max(max_error,err);n+=1
 save(PUB/'native-decode-proof.json',{'status':'passed','sample_rows':len(rows),'scalars_checked':n,'max_abs_error':max_error,'engine':'NautilusTrader1.231.0 native Price.from_raw/Quantity.from_raw','scope':'First/last row of each filtered quote file read; full file hashes and price tick-grid assertions checked separately'})
 print('Native scalar checks passed:',n)
if __name__=='__main__':main()
