from pathlib import Path
import hashlib, json, re, sys, difflib

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'V71r1-Nullable-Audit-review-2fc0eef8/main'
sys.path.insert(0, str(HERE.parent/'ES-NQ-Combined-V71-20261119'))
from build_combined import member

NAMES = ('HY104RapidEvalSim', 'HY104C2803FundedSim', 'HY3TradeDayFastPassSim')
FROZEN = ('ObserveTrade', 'InitialStop', 'CrossesStop', 'UpdatePosition', 'RefreshSession',
          'CommitBar', 'CheckClose')

def once(src, old, new):
    assert src.count(old) == 1, (old[:100], src.count(old))
    return src.replace(old, new, 1)

def methods(src):
    out={}; counts={}
    for m in re.finditer(r'^        (?:private|protected|public|internal) (?:static |override |sealed |virtual )*[\w<>,.\[\]?]+\s+(\w+)\s*\(',src,re.M):
        name=m[1];ordinal=counts.get(name,0);counts[name]=ordinal+1
        out[name+'#'+str(ordinal)]=member(src[m.start():],name)
    return out

def build():
    manifest = {'status':'SOURCE_BUILD_NOT_NATIVE_ACCEPTED', 'base':str(BASE), 'files':[], 'unchanged_methods':list(FROZEN)}
    for name in NAMES:
        path = BASE / (name+'.cs')
        before = path.read_text(encoding='utf-8-sig')
        src = before
        nq = name.startswith('HY3')
        profile = ('FundedPhase ? HYAccountProfileV8.TradeDayFunded : HYAccountProfileV8.TradeDayEvaluation' if nq else
                   'HYAccountProfileV8.MffEvaluation' if name == NAMES[0] else 'HYAccountProfileV8.MffFunded')
        src = once(src, '        private const double IntradayLossFloor = OpeningModelBalance - 2000.0;\n', '')
        src = re.sub(r'^        private const double (OpeningModelBalance|ModelFeePerSide) = [^;]+;\n','',src,flags=re.M)
        src = src.replace('private static bool modelLossLatched;', 'private bool modelLossLatched;')
        src = src.replace('private static double modelRealized;', 'private double modelRealized;')
        src = once(src, '                Print("HY3: " + Account.Name' if nq else '                Print("HY104: " + Account.Name',
                   '                InitializeAccountReplay();\n' + ('                Print("HY3: " + Account.Name' if nq else '                Print("HY104: " + Account.Name'))
        src = once(src, '                lock (sync)\n                    CloseIntegrityAudit();',
                   '                lock (sync)\n                {\n                    CloseAccountReplay();\n                    CloseIntegrityAudit();\n                }')
        # Only account eligibility changes. Every technical signal expression stays identical.
        gate = member(src, 'CanEnter') if False else None
        src = once(src, '&& !modelLossLatched && !entryBlocked && sessionComplete && completeSessions >= WarmupSessions',
                   '&& AccountReplayReady() && !modelLossLatched && !entryBlocked && sessionComplete && completeSessions >= WarmupSessions')
        old = member(src, 'CheckModelLoss')
        new = '''        private bool CheckModelLoss(DateTime time, bool useNewQuote)
        {
            if (!IsOrderAccount()) return false;
            AdvanceAccountReplay(time);
            if (accountReplay == null) return false;
            if (positionSide != 0)
            {
                bool validBook = bidSize > 0 && askSize > 0 && bid > 0 && ask >= bid
                    && !double.IsInfinity(ask) && MarketTimeAgrees(time, bidClock) && MarketTimeAgrees(time, askClock);
                if (validBook)
                    try { accountReplay.Mark(Convert.ToDecimal(bid, CultureInfo.InvariantCulture), Convert.ToDecimal(ask, CultureInfo.InvariantCulture)); }
                    catch (Exception e) { BlockAccountException(e); }
            }
            modelLossLatched = accountReplay.Breached;
            if (!modelLossLatched) return false;
            if (pending != null && pending.IsEntry)
            {
                SetReturnOutcome(pending, "kein Einstieg · Sim-Konto beendet");
                pending = null;
            }
            if (positionSide != 0 && !exitSubmissionFailed && submitted == null && pending == null)
                Queue(new Intent(false, positionSide, "RapidLoss", time, positionStop));
            return useNewQuote;
        }'''
        if not nq:
            new = new.replace('                SetReturnOutcome(pending, "kein Einstieg · Sim-Konto beendet");\n', '')
        src = once(src, old, new)
        fee = '                modelRealized -= ModelFeePerSide;\n'
        src = once(src, fee, '                RecordAccountExecution(executionId, filled, price, time);\n')
        if nq:
            src = once(src, '                if (!filled.IsEntry)\n                    modelRealized += positionSide * (price - positionEntryPrice) * 20.0;\n', '')
        else:
            src = once(src, '                if (!filled.IsEntry)\n                    modelRealized += positionSide * (price - positionEntryPrice) * 50.0;\n', '')
        reservation = '                // Reservation belongs to this exact immutable intent lifetime, not a mutable news marker.' if nq else None
        # Put the durable send barrier after all existing final checks, before API reservation.
        needle = '                if (!intentApiSendStarted.Add(intent))'
        addition = '''                if (!ReserveAccountIntent(intent, now))
                {
                    FailSubmission(intent, "Kontojournal konnte Orderabsicht nicht dauerhaft speichern.");
                    return;
                }
'''
        reservation = re.search(r'                if \(!intentApiSendStarted.Add\(intent\)\)\s+return;', src)
        assert reservation
        src = src[:reservation.end()] + '\n' + addition + src[reservation.end():]
        handler = 'HandleOwnedOrderUpdate' if name == NAMES[0] else 'HandleNewsOrderUpdate'
        clock = 'OwnershipControlNow' if name == NAMES[0] else 'NewsControlNow'
        old_callback = '            lock (sync)\n                if ('+handler+'(order, quantity, filled, orderState, error, '+clock+'()))\n                    return;'
        new_callback = '            lock (sync)\n            {\n                bool handled = '+handler+'(order, quantity, filled, orderState, error, '+clock+'());\n                ResolveAccountOrderTerminal(order, quantity, filled, orderState);\n                if (handled) return;\n            }'
        src = once(src, old_callback, new_callback)
        # Surface persistence/account eligibility errors in the existing status card.
        old_legend = member(src,'GetLegendStatus')
        insertion = '''            if (!AccountReplayReady() && State == State.Realtime && IsOrderAccount())
            {
                accent = modelLossLatched || accountReplayFailure != null ? ErrorAccent : WaitingAccent;
                return AccountReplayStatus();
            }
'''
        new_legend = once(old_legend, '            if (integrityAuditFailed || integrityCalendarFailed)', insertion+'            if (integrityAuditFailed || integrityCalendarFailed)')
        src = once(src,old_legend,new_legend)
        # Keep the decision audit truthful when only account eligibility blocks.
        audit_start = src.index('        private string EntryAuditReason(')
        audit_end = src.index('        private ', src.index('                return "historischer Rücklauf', audit_start))
        audit_part = src[audit_start:audit_end]
        audit_part_new = once(audit_part,'            if (modelLossLatched)',
            '            if (!AccountReplayReady() && IsOrderAccount())\n                return AccountReplayStatus();\n            if (modelLossLatched)')
        src = src[:audit_start]+audit_part_new+src[audit_end:]
        inc = (HERE/'account_integration.cs.inc').read_text().replace('__PROFILE__', profile).replace('__ORDER_OWNER__', 'OwnedOrderIntent' if name == NAMES[0] else 'NewsOrderIntent')
        src = once(src, '        private sealed class IndicatorState', inc+'\n        private sealed class IndicatorState')
        src = re.sub(r'private const string AuditDiagnosticVersion = "[^"]+";',
                     'private const string AuditDiagnosticVersion = "V8-ACCOUNT-REPLAY-20261119";', src, count=1)
        for method in FROZEN:
            assert member(before,method)==member(src,method), (name,method)
        original_methods=methods(before);candidate_methods=methods(src)
        allowed={'OnStateChange','CanEnter','CheckModelLoss','Submit','OnExecutionUpdate','OnOrderUpdate','GetLegendStatus','EntryAuditReason'}
        changed=[]
        for key,value in original_methods.items():
            assert key in candidate_methods,(name,'deleted method',key)
            if value!=candidate_methods[key]:
                changed.append(key);assert key.split('#')[0] in allowed,(name,'unexpected existing method change',key)
        tail='        private sealed class IndicatorState'
        assert before[before.index(tail):] == src[src.index(tail):]
        target = HERE/'Strategies'/path.name
        target.write_bytes(src.replace('\n','\r\n').encode('utf-8-sig'))
        (HERE/(name+'.diff')).write_text(''.join(difflib.unified_diff(before.splitlines(True),src.splitlines(True),fromfile=name+'.v71r1',tofile=name+'.v8')))
        manifest['files'].append({'file':path.name,'base_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                                  'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                                  'changed_existing_methods':changed,'unchanged_existing_methods':len(original_methods)-len(changed)})
    (HERE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))

if __name__ == '__main__': build()
