"""Freeze the explicitly requested five-year study before candidate results/fits."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json

HERE = Path(__file__).resolve().parents[1]
TARGET = HERE / 'Public/preregister.json'

def main():
    assert not TARGET.exists(), 'Never overwrite a preregistration after results'
    plan = {
        'schema': 'ES-FIVE-YEAR-ML-1',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'user_scope': 'Four extra older ES years, 2021–2026, zero incremental data cost; implement actual Claude recommendations 1–4.',
        'data': {
            'source': 'Existing original Databento GLBX.MDP3 OHLCV-1m ES quarterly outrights; dated instrument mappings retained.',
            'inventory_proof': '../ES-FiveYear-ZeroCost-20261121/Public/local-coverage.json',
            'incremental_data_cost_usd': 0,
            'raw_data_uploaded': False,
            'resolution': 'Original minute bars, NOT five years of verified TBBO ticks.',
            'no_spreads_or_back_adjustment': True,
            'roll': 'Existing causal prior-session-volume rule, forward maturity only; freeze price-only schedule before labels. Five same-contract full warm-up sessions.',
            'calendar': 'Preserve exact native ES calendar/session/flatten where available; older exchange holidays/early closes must be verified before older labels.'
        },
        'periods': {
            'development': ['2021-11-24', '2024-11-24_exclusive'],
            'sealed_final': ['2024-11-24', '2025-11-24_exclusive'],
            'known_supplement': ['2025-11-24', '2026-10-31_exclusive'],
            'sealed_label_rule': 'No labels/outcomes until source, model coefficients/preprocessing, calibrator and rule are frozen; metadata/prices may be audited.',
            'known_year_status': 'Used repeatedly for strategy/model selection; never fresh OOS.',
            'older_year_status': 'Held out within this newly registered ML study; no claim of universal historical data independence.'
        },
        'review': {
            'actual_Claude_read': True,
            'accepted_specs': 'Latest actual candidate/label specification and subsequent acceptance-threshold correction, 21 November 2026.',
            'private_chat_metadata_published': False,
            'critical_conditions': ['Approximation acceptance before training', 'Strategy-only check on development years only', 'One sealed final evaluation', 'No operating strategy changes']
        },
        'candidate': {
            'strategy_reference': 'ES C28.03 funded EMA20, one definition; no near-duplicate EMA22/Eval/Funded rows.',
            'sequence': 'Band → opposite band → first EMA20 return; latest band determines side; consume first return regardless of later eligibility.',
            'overlap': 'Also independent shadow candidate while base position open; base_was_flat flag retained, never multiply one setup across accounts.',
            'timeframe_seconds': 300,
            'session_America_Chicago': ['08:30', '16:00'],
            'normal_entry_and_flatten_cutoff': '15:09 strictly; native early close/flatten overrides retained.',
            'center': 'EMA20 forming from prior committed 5-minute EMA and current minute close.',
            'ATR': 'Wilder10, initial mean10 TR; first bar each day H−L; subsequent TR includes prior close.',
            'Keltner': 'EMA20 ± 2.0 ATR10',
            'entry': 'Decision at minute close; execution at next observed minute open. Missing next minute is a data-quality exclusion, not invented liquidity.',
            'stop': 'Fixed decision EMA20 − side×2.15 ATR10, rounded outward to 0.25 point tick.',
            'news': 'Omitted consistently for research candidate inventory only; no historical SI/news invented. This is not provider-compliant payout simulation.',
            'other_logic': 'No extra filters, direction/parameter searches or changed session rules.'
        },
        'labels': {
            'primary': 'Minute approximation of original moving BB/OR target; NOT native tick label.',
            'BB': '20 values: 19 committed 5-minute closes plus current minute close; population sigma1.75, favorable offset0.75 tick. Minute-close crossing exits next open.',
            'OR': 'High/low first60 minutes; only active after60 and at least1 tick favorable from actual entry; minute high/low touch fills level.',
            'priority': 'Fixed stop before any target in same minute. Stop gap uses adverse of stop/open; entry already beyond stop is immediate stop.',
            'flatten': 'Open of first minute at/after native flatten time; report gaps/exclusions.',
            'normal_roundtrip_fee_usd': 4.68,
            'stress_extra_usd': 25.0,
            'net_R': '(grossUSD−4.68−25.00)/(side×(decisionClose−fixedStop)×50+4.68+25.00)',
            'secondary': 'Decision-fixed bracket label separately retained with explicit name; no model/search on this secondary label.'
        },
        'mandatory_known_year_approximation_acceptance': {
            'before_any_new_model_or_older_label': True,
            'reference': '347 unique native C28.03 candidates on same known242 sessions, source hashes checked.',
            'match': 'Same contract, Chicago date and side. All pairs within300s sorted by(abs time difference,native signal ns,coarse signal ns); take each native/coarse candidate at most once. No outcomes used.',
            'minimum_matches': 100,
            'minimum_native_recall': 0.70,
            'minimum_coarse_precision': 0.70,
            'minimum_NettoR_Spearman': 0.60,
            'minimum_stress_profit_sign_agreement': 0.75,
            'also_report': ['All counts/exclusions', 'Signed mean and mean absolute net-R error', 'Net-USD error', 'Decision-time offsets', 'Feature deviations', 'Source/version hashes'],
            'failure_action': 'STOP before older labels/training; keep final holdout sealed; report actual disagreement. Do not relax thresholds or silently train a different strategy.'
        },
        'features': ['planned_stop_risk_usd', 'nearest_active_target_path_R', 'signed_completed_ema_slope_atr', 'completed_relative_volume20', 'chicago_session_minute'],
        'feature_rules': 'At decision time only. Active target path can be zero/negative, no post-outcome exclusions; minimum of active signed distances. Only completed slope/volume. No future highs/lows/MFE/account payouts/SI coverage as input.',
        'models': {
            'primary': {'model': 'StandardScaler + Ridge', 'alpha': 10.0, 'solver': 'svd'},
            'fixed_secondary': {'model': 'HistGradientBoostingRegressor', 'max_depth': 1, 'learning_rate': 0.05, 'max_iter': 100, 'min_samples_leaf': 20, 'l2_regularization': 1.0, 'early_stopping': False, 'random_state': 20261121},
            'target': 'Unclipped primary stress net-R',
            'no_search': True,
            'calibration': 'Training-only expanding chronological cross-predictions, whole-session gap and label-end purge. a=unrestricted training mean(y), b=OLS slope of y on centered cross-prediction clipped[0,1]. Prediction=a+b×(raw−mean(cross-predictions)).',
            'gate': 'Omit only if calibrated expected net-R<0; if a<=0, gate inactive, explicitly reported.',
            'preprocessing': 'Fit scaler/imputation only on each training subset; no sealed covariate-assisted fitting.',
            'forward_shadow': 'Frozen portable model/rule; record forecast before outcome; no trading changes. Deployment requires subsequent native gate/account replay and forward evidence.'
        },
        'evaluation': {
            'primary_final': 'Ridge Spearman(prediction,stressNetR), one-sided session-level conditional permutation at alpha0.05; fixed boosting descriptive secondary, not selection winner.',
            'conditional_permutation': '1999 permutations,seed20261121; permute whole ordered daily outcome vectors within calendar-quarter and same daily candidate-count strata, report immovable fraction.',
            'uncertainty': '1999 moving5-session blocks for descriptive confidence intervals; report final test count, do not assert500 cases without counting.',
            'also_report': ['Mean omitted and taken stress net-R', 'Count omitted', 'Ungated baseline', 'No claim of payout gain without native policy/account rerun'],
            'no_leaderboard_or_live_promotion': True
        },
        'software_references': ['https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html', 'https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html'],
        'training_started': False,
        'sealed_labels_generated': False,
        'register_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    }
    TARGET.write_text(json.dumps(plan, indent=2, ensure_ascii=False)+'\n')
    print('Frozen plan SHA256', hashlib.sha256(TARGET.read_bytes()).hexdigest())

if __name__ == '__main__': main()
