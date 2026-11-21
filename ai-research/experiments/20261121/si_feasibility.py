"""Count actual SI/setup overlap. Message presence is not feed coverage."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import importlib.util,json,re,sys
from native_check import HERE,DE,read,write,sha

def main():
    source=DE/'outputs/SI-Nautilus-Ereignistest-v1/source_reader.py'
    spec=importlib.util.spec_from_file_location('frozen_si_source',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    events,audit=m.read_archive()
    sys.path.insert(0,str(DE/'outputs/AI-Forschung-20261120/repo/ai-research'))
    from train_ml1 import data,splits
    dates,rows,_=data();es=[e for e in events if e['market']=='ES' and e['event_type'] in ['STOP','ICEBERG']]
    first=min(e['ts_init'] for e in es);last=max(e['ts_init'] for e in es)
    tests={i for _,_,test in splits(rows,dates) for i in test}
    candidates=[(i,r) for i,r in enumerate(rows) if r['day'] in dates and first<=r['ns']<=last]
    matches=[]
    for i,r in candidates:
        contract=re.search(r'ES[HMUZ]\d$',r['segment']).group()
        known=[e for e in es if e['symbol']==contract and 30_000_000_000<=r['ns']-e['ts_init']<=930_000_000_000]
        if known:matches.append(dict(in_outer_test=i in tests,event_types=sorted(set(e['event_type'] for e in known))))
    write(HERE/'SI/feasibility.json',dict(state='inventory_complete_training_not_eligible_without_feed_coverage',
        source_reader_sha256=sha(source),archive_sha256=audit['source_sha256'],archive_pagination_verified=audit['pagination_chain_verified'],
        ES_stop_iceberg_messages=len(es),ES_events_by_type=dict(Counter(e['event_type'] for e in es)),
        first_ES_message_utc=m.iso(first),last_ES_message_utc=m.iso(last),
        setup_candidates_in_message_date_span=len(candidates),
        span_is_not_verified_coverage=True,setup_candidates_with_same_contract_prior15min_event=len(matches),
        outer_test_candidates_with_prior15min_event=sum(r['in_outer_test'] for r in matches),
        availability='last Discord edit/sent proxy plus30seconds; not verified original event or bot receipt',
        verified_live_feed_coverage_sessions=0,
        coverage_boundary='Archive completeness verifies retained messages, not silent bot outages/deleted messages/feed liveness. Do not encode absent intervals as zero SI.',
        original_Bookmap_event_time_proven=False,own_receive_timestamp_proven=False,
        new_SI_model_trained=False,previous_boosting_study_preserved=True))
    print((HERE/'SI/feasibility.json').read_text())

if __name__=='__main__':main()
