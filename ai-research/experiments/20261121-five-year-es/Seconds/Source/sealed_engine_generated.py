def run_period(receipt):
    authorization = authorize(receipt)
    began = time.time()
    months, schedule = known_sources()
    known = [s for s in schedule if '2024-11-24' <= s['day'] < '2025-11-24']
    clock_byday = {s['day']: s for s in schedule}
    save(HERE / 'Private/second-known-price-roll-freeze.json', schedule)
    binding = dict(source_freeze_sha256=sha(authorization['source_freeze_path']), root_go_sha256=sha(receipt), known_schedule_sha256=sha(HERE / 'Private/second-known-price-roll-freeze.json'), month_manifest_sha256={m: sha(HERE / 'Private/Months' / m / 'manifest.json') for m in KNOWN_MONTHS}, builder_sha256=sha(Path(__file__)), kernel_sha256=sha(Path(__file__).with_name('second_kernel.py')))
    save(HERE / 'Public/second-execution-start.json', dict(utc=utcnow(), mode='sealed', no_unauthorized_period_labels=True, **binding))
    episodes = []
    for s in known:
        if s['raw_symbol'] is None:
            continue
        if not episodes or episodes[-1]['symbol'] != s['raw_symbol']:
            episodes.append(dict(symbol=s['raw_symbol'], sessions=[]))
        episodes[-1]['sessions'].append(s)
    cases = []
    exclusions = []
    ambiguities = []
    stats = Counter()
    feature_proof = []
    for episode in episodes:
        symbol = episode['symbol']
        book = SecondBook()
        first = episode['sessions'][0]
        warm = [w['day'] for w in first['warmup_previous_five_same_contract_sessions']]
        active = {s['day']: s for s in episode['sessions']}
        baseline_busy_until = -1
        baseline_entry_ns = None
        for day in warm + [s['day'] for s in episode['sessions']]:
            rows = read_day(months, symbol, day)
            clock = clock_byday[day]
            previews = []
            features = []
            for row in rows:
                preview = book.step(row, clock)
                previews.append(preview)
                if day not in active:
                    continue
                stats['known_seconds_processed'] += 1
                if preview['ambiguous_first_return']:
                    stats['ambiguous_return_seconds_all_windows'] += 1
                    if preview['signal_ns'] < clock['flatten_ns'] and active[day]['warmup_complete'] and preview['current_past_5m_grid_complete']:
                        stats['ambiguous_return_seconds_entry_eligible_clock_and_history'] += 1
                        ambiguities.append(dict(contract=symbol, day=day, signal_ns=preview['signal_ns'], state_mask_before=preview['state_mask_before'], state_mask_after=preview['state_mask_after'], possible_event_patterns=preview['possible_event_patterns'], paths_considered=preview['paths_considered']))
                side = preview['consensus_side']
                if not side:
                    continue
                stats['unanimous_single_return_seconds'] += 1
                signal = preview['signal_ns']
                reason = None
                if signal >= clock['flatten_ns']:
                    reason = 'consumed_consensus_at_or_after_flatten'
                elif not active[day]['warmup_complete']:
                    reason = 'consumed_consensus_incomplete_prior_five_same_contract_warmup'
                elif not preview['current_past_5m_grid_complete']:
                    reason = 'consumed_consensus_missing_past_current5m_bucket'
                if reason:
                    exclusions.append(dict(contract=symbol, day=day, signal_ns=signal, side=side, reason=reason))
                    continue
                feature, reason = decision_features(side, row['close'], preview, clock)
                if reason:
                    exclusions.append(dict(contract=symbol, day=day, signal_ns=signal, side=side, reason=reason))
                    continue
                features.append(dict(case_key=hashlib.sha256(f'C28_1s_consensus_v2|{symbol}|{signal}|{side}'.encode()).hexdigest(), contract=symbol, day=day, signal_ns=signal, side=side, decision_price=row['close'], **feature, vendor_quality_flag=row['vendor_quality_flag'], source_resolution='OHLCV1s_prescribed_order_scenarios_not_TBBO', state_mask_before=preview['state_mask_before'], state_mask_after=preview['state_mask_after']))
            if day not in active:
                continue
            digest = hashlib.sha256(json.dumps(features, sort_keys=True, allow_nan=False).encode()).hexdigest()
            feature_proof.append(dict(contract=symbol, day=day, feature_candidates=len(features), features_before_labels_sha256=digest))
            for candidate in features:
                signal = candidate['signal_ns']
                available = signal >= baseline_busy_until
                was_flat = baseline_entry_ns is None or not baseline_entry_ns <= signal < baseline_busy_until
                result = delayed_shadow(candidate, rows, previews, clock)
                if result['label_status'] != 'ok':
                    exclusions.append(dict(contract=symbol, day=day, signal_ns=signal, side=candidate['side'], reason=result['label_status']))
                    if available and result.get('entry_cancel_ns') is not None:
                        baseline_busy_until = result['entry_cancel_ns']
                        baseline_entry_ns = None
                    continue
                candidate.update(result, base_was_flat=bool(was_flat), base_available_for_entry=bool(available))
                if available:
                    baseline_busy_until = result['exit_ns']
                    baseline_entry_ns = result['entry_ns']
                cases.append(candidate)
            save(HERE / 'Public/second-preflight-progress.json', dict(status='RUNNING_SEALED_EXACT_FROZEN_ENGINE', contract=symbol, last_day=day, cases_so_far=len(cases), ambiguities_so_far=len(ambiguities), known_seconds_processed=stats['known_seconds_processed'], elapsed_seconds=time.time() - began, no_unauthorized_period_labels=True, no_models=True))
            print('sealed1s', symbol, day, 'filledcases', len(cases), 'ambiguous', len(ambiguities), flush=True)
    cases.sort(key=lambda c: (c['signal_ns'], c['contract'], c['side']))
    if not cases:
        raise ValueError('No genuinefilledsealedcandidates')
    if not all(('2024-11-24' <= c['day'] < '2025-11-24' for c in cases)):
        raise ValueError('Guard:labeloutsidesealedwindow')
    if len({c['case_key'] for c in cases}) != len(cases):
        raise ValueError('Duplicated1scandidate')
    jsonl = HERE / 'Private/second-candidates-known.jsonl'
    jsonl.write_text(''.join((json.dumps(c, allow_nan=False) + '\n' for c in cases)))
    csvpath = HERE / 'Private/second-candidates-known.csv'
    pd.DataFrame(cases).to_csv(csvpath, index=False)
    save(HERE / 'Private/second-known-exclusions.json', exclusions)
    save(HERE / 'Private/second-known-ambiguities.json', ambiguities)
    save(HERE / 'Private/second-known-feature-before-label-proof.json', feature_proof)
    binding.update(candidates_jsonl_sha256=sha(jsonl), candidates_csv_sha256=sha(csvpath))
    summary = dict(status='SEALED_LABELS_COMPLETE_FROZEN_ENGINE', utc=utcnow(), cases=len(cases), days=len({c['day'] for c in cases}), stats=dict(stats), exclusion_reasons=dict(Counter((e['reason'] for e in exclusions))), degraded_date_cases_retained=sum((c['day'] == '2025-11-28' for c in cases)), latency_gaps=dict(max_entry_extra_seconds=max((c['entry_gap_extra_seconds'] for c in cases)), max_exit_extra_seconds=max((c['exit_gap_extra_seconds'] for c in cases)), entries_with_gap=sum((c['entry_gap_extra_seconds'] > 0 for c in cases)), exits_with_gap=sum((c['exit_gap_extra_seconds'] > 0 for c in cases))), elapsed_seconds=time.time() - began, no_unauthorized_period_labels=True, no_models_fit=True, **binding)
    save(HERE / 'Public/second-known-summary.json', summary)
    result = acceptance(cases, binding)
    save(HERE / 'Public/second-preflight-progress.json', dict(status='FINISHED_' + result['status'], cases=len(cases), elapsed_seconds=time.time() - began, no_unauthorized_period_labels=True, no_models=True))
