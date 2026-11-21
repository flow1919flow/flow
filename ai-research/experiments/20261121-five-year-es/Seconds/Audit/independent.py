"""Independent saved-case/fill/metric acceptance; no signal reconstruction.

Does not call the frozen SecondBook, delayed_shadow or runner. All348fixed
saved cases are audited; no new candidates, alternative policy or model fit.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import csv,json,hashlib,math
import numpy as np
import pyarrow.parquet as pq
from scipy.stats import rankdata

HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1];NS=10**9
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def native():
    result=[]
    for vpath in sorted((ROOT/'outputs/AI-Forschung-20261120/SQX/observer').glob('*/verified.json')):
        v=json.loads(vpath.read_text());folder=Path(v['folder']);segment=vpath.parent.name
        features={int(r['signal_ns']):r for r in csv.DictReader((folder/'ml-features.csv').open())}
        for row in csv.DictReader((folder/'candidates.csv').open()):
            ns=int(row['entry_decision_ns']);day=datetime.fromtimestamp(ns//NS,timezone.utc).astimezone(__import__('zoneinfo').ZoneInfo('America/Chicago')).date().isoformat()
            if not '2025-11-24'<=day<'2026-10-31':continue
            net=(int(row['net_pnl_cents'])-2500)/100;risk=float(features[ns]['planned_stop_risk_usd'])
            result.append(dict(contract=segment.rsplit('-',1)[-1],day=day,side=1 if row['side']=='LONG' else-1,signal_ns=ns,net=net,R=net/risk))
    assert len(result)==347
    return result


def main():
    frozen=json.loads((HERE/'Public/second-source-freeze-v2.json').read_text());go=json.loads((HERE/'Private/root-known-go.json').read_text())
    for name,digest in frozen['sources_sha256'].items():assert sha(HERE/'Source'/name)==digest
    assert sha(HERE/'Public/second-fixtures.json')==frozen['fixtures_sha256']
    for binding in go['protocol_files']:assert sha(binding['path'])==binding['sha256']
    assert go['source_freeze_sha256']==sha(HERE/'Public/second-source-freeze-v2.json')
    result=json.loads((HERE/'Public/second-native-acceptance.json').read_text());summary=json.loads((HERE/'Public/second-known-summary.json').read_text())
    casepath=HERE/'Private/second-candidates-known.jsonl';cases=[json.loads(line) for line in casepath.read_text().splitlines()]
    assert sha(casepath)==summary['candidates_jsonl_sha256']==result['sourcehashes']['candidates_jsonl_sha256']
    assert len(cases)==348 and len({c['case_key'] for c in cases})==348
    assert all('2025-11-24'<=c['day']<'2026-10-31' for c in cases)
    assert not (HERE/'Private/second-candidates-development.jsonl').exists() and not (HERE/'Private/second-candidates-sealed.jsonl').exists()
    schedules=json.loads((HERE/'Private/second-known-price-roll-freeze.json').read_text());clocks={r['day']:r for r in schedules}
    # These are only small5mprice aggregates, not anall-parentsecondsdataframe.
    bars=[];months={}
    for month in ['2025-11','2025-12']+[f'2026-{m:02d}' for m in range(1,11)]:
        p=HERE/'Private/Months'/month/'manifest.json';m=json.loads(p.read_text());months[month]=m
        assert m['zero_cost_download_receipt']['quoted_cost_USD']==0
        bars+=pq.read_table(HERE/m['bars_5m_path_relative_to_task']).to_pylist()
    close_lookup={}
    for symbol in {b['raw_symbol'] for b in bars}:
        b=sorted((r for r in bars if r['raw_symbol']==symbol),key=lambda r:r['bar_end_ns'])
        close_lookup[symbol]=(np.array([r['bar_end_ns'] for r in b],dtype=np.int64),np.array([r['close_nanos']/1e9 for r in b]))
    daycache={}
    def day_prices(symbol,day):
        if (symbol,day) not in daycache:
            shard=next(s for s in months[day[:7]]['second_shards'] if s['raw_symbol']==symbol)
            d=pq.read_table(HERE/shard['path_relative_to_task'],filters=[('day','=',day)],columns=['ts_event_ns','open_nanos','high_nanos','low_nanos','close_nanos']).to_pydict()
            daycache[(symbol,day)]={k:np.array(v,dtype=np.int64 if k=='ts_event_ns' else float)/(1 if k=='ts_event_ns' else 1e9) for k,v in d.items()}
        return daycache[(symbol,day)]
    def bb(symbol,start,price,side):
        ends,closes=close_lookup[symbol];index=int(np.searchsorted(ends,start,side='right'));previous=list(closes[max(0,index-19):index]);assert len(previous)==19
        values=previous+[price];mean=sum(values)/20;sigma=math.sqrt(sum((v-mean)**2 for v in values)/20)
        return mean+side*(1.75*sigma-.1875)
    max_net_error=0.;max_R_error=0.;max_path_error=0.;max_BB_error=0.;decision_reasons=Counter();entry_gap=0;exit_gap=0
    for c in cases:
        day=c['day'];symbol=c['contract'];side=c['side'];clock=clocks[day];d=day_prices(symbol,day);ts=d['ts_event_ns'].astype(np.int64)
        decision=c['signal_ns'];stop=c['stop_price'];source_second=decision-NS
        si=int(np.searchsorted(ts,source_second));assert si<len(ts) and ts[si]==source_second
        assert d['close_nanos'][si]==c['decision_price']
        quote=c['decision_price']+side*.25;risk=side*(quote-stop)*50+4.68+25
        assert abs(quote-c['decision_quote_proxy'])<1e-12 and abs(risk-c['planned_risk_usd'])<1e-10 and risk>0
        assert c['completed_feature_end_ns']<=source_second
        bound=bb(symbol,source_second,c['decision_price'],side);max_BB_error=max(max_BB_error,abs(bound-c['decision_BB_level']))
        expected_paths=[side*(bound-quote)]
        if decision>=clock['session_open_ns']+3600*NS:
            firsthour=ts<clock['session_open_ns']+3600*NS
            orlevel=float(d['high_nanos'][firsthour].max() if side==1 else d['low_nanos'][firsthour].min())
            assert c['decision_OR_level']==orlevel
            if side*(orlevel-quote)>=.25:expected_paths.append(side*(orlevel-quote))
        else:assert c['decision_OR_level'] is None
        max_path_error=max(max_path_error,abs(min(expected_paths)/(side*(quote-stop))-c['feature_target_path_R']))
        entry=int(np.searchsorted(ts,decision+2*NS));assert int(ts[entry])==c['entry_ns']<clock['flatten_ns']
        assert side*(d['open_nanos'][entry]-side*.25-stop)>0
        fill=d['open_nanos'][entry]+side*.25;assert fill==c['entry_price']
        # Independently locate first registeredtouch/scheduledflatten forfixedcase.
        flat=clock['flatten_ns'];exitdecision=None;reason=None
        firsthour=ts<clock['session_open_ns']+3600*NS
        orlevel=float(d['high_nanos'][firsthour].max() if side==1 else d['low_nanos'][firsthour].min())
        for j in range(entry,len(ts)):
            start=int(ts[j]);end=start+NS
            if start>=flat:exitdecision=flat;reason='session_flatten_delayed_market';break
            stop_touch=d['low_nanos'][j]<=stop if side==1 else d['high_nanos'][j]>=stop
            extreme=d['high_nanos'][j] if side==1 else d['low_nanos'][j];target=bb(symbol,start,float(extreme),side)
            bbtouch=extreme>target if side==1 else extreme<target
            ortouch=start>=clock['session_open_ns']+3600*NS and side*(orlevel-fill)>=.25 and (extreme>=orlevel if side==1 else extreme<=orlevel)
            if stop_touch:exitdecision=end;reason='stop_touch_second_end_delayed_market';break
            if bbtouch:exitdecision=end;reason='moving_BB_touch_second_end_delayed_market';break
            if ortouch:exitdecision=end;reason='OR60_touch_second_end_delayed_market';break
            if end>=flat:exitdecision=flat;reason='session_flatten_delayed_market';break
        assert exitdecision==c['exit_decision_ns'] and reason==c['exit_reason']
        index=int(np.searchsorted(ts,exitdecision+2*NS));assert int(ts[index])==c['exit_ns']
        exitprice=d['open_nanos'][index]-side*.25;assert exitprice==c['exit_price']
        gross=side*(exitprice-fill)*50;normal=gross-4.68;stress=normal-25
        max_net_error=max(max_net_error,abs(normal-c['normal_net_usd']),abs(stress-c['stress_net_usd']))
        max_R_error=max(max_R_error,abs(stress/risk-c['stress_net_R']))
        assert c['entry_latency_seconds']>=2 and c['exit_latency_seconds']>=2
        entry_gap+=c['entry_gap_extra_seconds']>0;exit_gap+=c['exit_gap_extra_seconds']>0;decision_reasons[reason]+=1
    assert max_net_error<1e-10 and max_R_error<1e-12 and max_path_error<1e-10 and max_BB_error<1e-9
    reference=native();proposed=[]
    for i,n in enumerate(reference):
        for j,c in enumerate(cases):
            if all(n[k]==c[k] for k in ['contract','day','side']):
                delta=abs(n['signal_ns']-c['signal_ns'])
                if delta<=300*NS:proposed.append((delta,n['signal_ns'],c['signal_ns'],i,j))
    usedn=set();usedc=set();matches=[]
    for delta,_,__,i,j in sorted(proposed):
        if i not in usedn and j not in usedc:usedn.add(i);usedc.add(j);matches.append((i,j,delta))
    nr=np.array([reference[i]['R'] for i,j,d in matches]);cr=np.array([cases[j]['stress_net_R'] for i,j,d in matches]);error=cr-nr
    rho=float(np.corrcoef(rankdata(nr),rankdata(cr))[0,1]);sign=float(np.mean([(reference[i]['net']>0)==(cases[j]['stress_net_usd']>0) for i,j,d in matches]))
    m=result['metrics'];assert len(matches)==m['matches']==347 and len(matches)/347==m['native_recall']==1.
    assert abs(len(matches)/len(cases)-m['second_precision'])<1e-15 and abs(rho-m['NettoR_Spearman'])<1e-12 and abs(sign-m['stress_profit_sign_agreement'])<1e-15
    assert abs(error.mean()-m['mean_net_R_error_second_minus_native'])<1e-14 and abs(np.abs(error).mean()-m['mean_absolute_net_R_error'])<1e-14
    ambiguities=json.loads((HERE/'Private/second-known-ambiguities.json').read_text());exclusions=json.loads((HERE/'Private/second-known-exclusions.json').read_text())
    assert len(ambiguities)==summary['stats'].get('ambiguous_return_seconds_entry_eligible_clock_and_history',0)
    assert dict(Counter(e['reason'] for e in exclusions))==summary['exclusion_reasons']
    assert entry_gap==summary['latency_gaps']['entries_with_gap'] and exit_gap==summary['latency_gaps']['exits_with_gap']
    assert all(result['checks'].values()) and result['accepted'] is True and abs(error.mean())<=.05
    for name,digest in frozen['sources_sha256'].items():assert sha(HERE/'Source'/name)==digest
    assert sha(casepath)==summary['candidates_jsonl_sha256']
    proof=dict(status='PASS_INDEPENDENT_RAW_PRICE_FILL_AND_METRIC_AUDIT',utc=datetime.now(timezone.utc).isoformat(),cases_verified=348,native_cases=347,independently_matched=347,independent_NetR_Spearman=rho,independent_sign_agreement=sign,independent_signed_mean_R_error=float(error.mean()),independent_mean_absolute_R_error=float(np.abs(error).mean()),max_normal_or_stress_net_USD_reconstruction_error=max_net_error,max_NetR_reconstruction_error=max_R_error,max_target_path_feature_error=max_path_error,max_decision_BB_feature_error=max_BB_error,all_entry_exit_first_present_Open_deadlines_verified=True,all348_first_exit_intents_independently_reconstructed=True,liquidation_guard_and_adverse_fill_ticks_verified=True,precommit_completed_feature_clocks_verified=True,ambiguity_seconds=len(ambiguities),exclusion_reasons=dict(Counter(e['reason'] for e in exclusions)),degraded_date_case_retained=sum(c['day']=='2025-11-28' for c in cases),frozen_sources_and_primary_outputs_unchanged=True,no_new_signal_reconstruction=True,no_older_or_sealed_labels=True,no_models_fit=True,acceptance_sha256=sha(HERE/'Public/second-native-acceptance.json'),candidate_jsonl_sha256=sha(casepath),audit_source_sha256=sha(Path(__file__)))
    path=HERE/'Public/second-independent-audit.json';path.write_text(json.dumps(proof,indent=2,allow_nan=False)+'\n');print(json.dumps(proof,indent=2))


if __name__=='__main__':main()
