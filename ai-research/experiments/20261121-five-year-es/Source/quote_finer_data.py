"""Ephemeral key, metadata only. No time-series request or purchase exists here."""
from pathlib import Path
from datetime import datetime, timezone
import getpass, json, os, sys
import databento as db

HERE = Path(__file__).resolve().parents[1]
REQUESTS = [
    dict(symbols=['ES.FUT'], stype_in='parent', start='2021-11-24T00:00:00Z', end='2025-11-24T00:00:00Z'),
    dict(symbols=['ESZ1'], stype_in='raw_symbol', start='2021-11-01T00:00:00Z', end='2021-12-14T00:00:00Z'),
    dict(symbols=['ESZ5'], stype_in='raw_symbol', start='2025-11-12T00:00:00Z', end='2025-12-17T00:00:00Z'),
]

def main():
    key = getpass.getpass('Databento API key (hidden, memory only): ')
    client = db.Historical(key=key); key = None
    results = []
    for fields in REQUESTS:
        req = dict(dataset='GLBX.MDP3', schema='ohlcv-1s', **fields)
        try:
            price = float(client.metadata.get_cost(**req))
            size = int(client.metadata.get_billable_size(**req))
            record = dict(request=req, quoted_cost_USD=price, billable_bytes_estimate=size,
                          exact_quote_is_zero=price == 0.0, status='quoted')
        except Exception as exc:
            record = dict(request=req, status='metadata_error', error_type=type(exc).__name__)
        results.append(record)
        print(json.dumps(record), flush=True)
    report = dict(state='authenticated_metadata_only_NO_downloads',
                  checked_at_utc=datetime.now(timezone.utc).isoformat(),
                  quotes=results, new_data_downloads=0, key_persisted=False,
                  metadata_calls_are_free=True, no_account_plan_inferred=True)
    (HERE/'Public/authenticated-finer-quotes.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Metadata-only price check finished. No data downloaded and no key saved.', flush=True)

if __name__ == '__main__': main()
