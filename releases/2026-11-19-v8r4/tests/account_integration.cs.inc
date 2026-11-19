        private HYAccountReplayV8 accountReplay;
        private string accountReplayFailure;
        private Intent accountReservedIntent;
        private string accountReservationToken;
        private DateTime accountCalendarCheckedDay;

        private void InitializeAccountReplay()
        {
            if (!IsOrderAccount()) return;
            try
            {
                HYAccountProfileV8 profile = __PROFILE__;
                string identity = HYAccountReplayV8.Identity(Account.Name, GetType().Name, profile);
                string folder = System.IO.Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "HY-AccountReplay-v8");
                accountReplay = new HYAccountReplayV8(folder, identity, profile);
                accountReplay.ReconcileFlat(PositionAccount != null && PositionAccount.MarketPosition == MarketPosition.Flat
                    && PositionAccount.Quantity == 0 && Position != null && Position.MarketPosition == MarketPosition.Flat,
                    HasWorkingOrder());
                int executions = ReconcileNativeAccountExecutions(accountReplay);
                if (accountReplay.Fault == null && executions > 0)
                    VerifyNativeAccountNegativeProbe(identity, profile);
                AdvanceAccountReplay(EasternNow());
                Print("HY ACCOUNT V8 " + identity + " epoch=" + accountReplay.Epoch
                    + " net=" + (accountReplay.BalanceCents / 100.0).ToString("F2", CultureInfo.InvariantCulture)
                    + " floor=" + (accountReplay.FloorCents / 100.0).ToString("F2", CultureInfo.InvariantCulture)
                    + " status=" + accountReplay.Status);
            }
            catch (Exception e)
            {
                accountReplayFailure = e.GetType().Name + ": " + e.Message;
                entryBlocked = true;
                Print("HY ACCOUNT V8 BLOCKED " + accountReplayFailure);
            }
        }

        private int ReconcileNativeAccountExecutions(HYAccountReplayV8 book)
        {
            // Account.Executions is the current-session collection. The durable
            // pre-entry barrier covers crashes whose fills are no longer in it.
            int count = 0;
            lock (Account.Executions)
                foreach (Execution execution in Account.Executions)
                {
                    if (execution == null || execution.Order == null || execution.Instrument == null
                        || execution.Instrument.MasterInstrument.Name != Instrument.MasterInstrument.Name
                        || PlatformToEastern(execution.Time).Ticks < book.EpochStartTicks) continue;
                    count++;
                    bool buy = execution.Order.OrderAction == OrderAction.Buy || execution.Order.OrderAction == OrderAction.BuyToCover;
                    if (!book.KnowsExecution(execution.ExecutionId, Convert.ToDecimal(execution.Price), execution.Quantity, buy))
                        book.Fail("NinjaTrader-Ausführung fehlt/abweichend im Journal: " + execution.ExecutionId);
                }
            return count;
        }

        private void VerifyNativeAccountNegativeProbe(string identity, HYAccountProfileV8 profile)
        {
            // Isolated COPY only, no native orders, account changes or live ledger writes.
            string accepted = System.IO.Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "HY-AccountReplay-v8",
                HYAccountReplayV8.FileName(identity) + ".native-probe-v8r3.ok");
            if (System.IO.File.Exists(accepted) && System.IO.File.ReadAllText(accepted) == accountReplay.Epoch)
            { Print("HY ACCOUNT V8 NEGATIVE PROBE PASS (already accepted) " + identity); return; }
            var copy = accountReplay.Snapshot();
            if (copy.ExecutionFacts.Count == 0) return;
            string remove = null;
            lock (Account.Executions)
                foreach (Execution execution in Account.Executions)
                    if (execution != null && execution.Order != null && execution.Instrument != null
                        && execution.Instrument.MasterInstrument.Name == Instrument.MasterInstrument.Name
                        && PlatformToEastern(execution.Time).Ticks >= accountReplay.EpochStartTicks)
                    { remove = execution.ExecutionId + "|"; break; }
            if (remove == null) return;
            copy.ExecutionFacts.RemoveAll(fact => fact.StartsWith(remove, StringComparison.Ordinal));
            string probe = System.IO.Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "log", "HY-account-v8-acceptance", Guid.NewGuid().ToString("N"));
            HYAccountReplayV8.WriteSeed(System.IO.Path.Combine(probe, "seeds", HYAccountReplayV8.FileName(identity)), copy);
            using (var book = new HYAccountReplayV8(probe, identity, profile))
            {
                ReconcileNativeAccountExecutions(book);
                if (book.Fault == null || book.CanEnter)
                    throw new InvalidOperationException("Native Negativprobe muss fehlenden Fill sperren");
            }
            using (var book = new HYAccountReplayV8(probe, identity, profile))
                if (book.CanEnter) throw new InvalidOperationException("Native Negativprobe muss Neustart überstehen");
            System.IO.File.WriteAllText(System.IO.Path.Combine(probe, "PASS.txt"),
                "READ_ONLY_NATIVE_EXECUTION_NEGATIVE_PROBE_PASS\n" + DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture)
                + "\n" + identity + "\nProduction ledger unchanged; no orders submitted.\n");
            System.IO.File.WriteAllText(accepted, accountReplay.Epoch);
            Print("HY ACCOUNT V8 NEGATIVE PROBE PASS " + identity);
        }

        private bool AccountReplayReady()
        {
            if (!IsOrderAccount()) return true;
            return accountReplay != null && accountReplayFailure == null && accountReplay.CanEnter;
        }

        private string AccountReplayStatus()
        {
            if (accountReplayFailure != null) return "KONTOSTATUS PRÜFEN";
            if (accountReplay == null) return "KONTOJOURNAL AUSSTEHEND";
            return accountReplay.Status;
        }

        private void AdvanceAccountReplay(DateTime now)
        {
            try { AdvanceAccountReplayCore(now); }
            catch (Exception e) { BlockAccountException(e); }
        }

        private void BlockAccountException(Exception e)
        {
            accountReplayFailure = e.GetType().Name + ": " + e.Message;
            entryBlocked = true;
            if (accountReplay != null) accountReplay.Fail("Kontooperation fehlgeschlagen · " + accountReplayFailure);
            Print("HY ACCOUNT V8 BLOCKED " + accountReplayFailure);
        }

        private void AdvanceAccountReplayCore(DateTime now)
        {
            if (accountReplay == null) return;
            bool flat = positionSide == 0 && PositionAccount != null && PositionAccount.Quantity == 0
                && PositionAccount.MarketPosition == MarketPosition.Flat;
            if (accountReplay.DayTicks != 0 && accountReplay.LastClosedDayTicks < accountReplay.DayTicks && now.Ticks >= accountReplay.CloseTicks)
                accountReplay.CloseDay(now, flat, pending != null || submitted != null || HasWorkingOrder());
            if (accountCalendarCheckedDay != now.Date || (now >= sessionOpen && now < sessionEnd && accountReplay.DayTicks != sessionOpen.Date.Ticks))
            {
                CatchUpAccountCalendar(now, flat);
                accountCalendarCheckedDay = now.Date;
            }
            if (now >= sessionOpen && now < sessionEnd)
                accountReplay.StartDay(sessionOpen.Date, sessionEnd);
            modelRealized = accountReplay.BalanceCents / 100.0;
            modelLossLatched = accountReplay.Breached;
            if (accountReplay.Fault != null)
            {
                accountReplayFailure = accountReplay.Fault;
                entryBlocked = true;
            }
        }

        private void CatchUpAccountCalendar(DateTime now, bool flat)
        {
            if (accountReplay.LifecycleEnded || accountReplay.Fault != null || accountReplay.DayTicks == 0
                || accountReplay.LastClosedDayTicks < accountReplay.DayTicks) return;
            DateTime cursor = new DateTime(accountReplay.LastClosedDayTicks).Date.AddDays(1);
            if (cursor > now.Date || !flat || pending != null || submitted != null || HasWorkingOrder()) return;
            var calendar = new SessionIterator(Bars);
            for (int count = 0; count < 512 && cursor <= now.Date && !accountReplay.LifecycleEnded; count++)
            {
                DateTime query = TimeZoneInfo.ConvertTime(DateTime.SpecifyKind(cursor.AddHours(9.5), DateTimeKind.Unspecified), easternZone, platformZone);
                bool returned = calendar.GetNextSession(query, true);
                DateTime day = calendar.ActualTradingDayExchange.Date;
                DateTime rawDay = calendar.ActualTradingDayExchange;
                DateTime rawBegin = calendar.ActualSessionBegin, rawEnd = calendar.ActualSessionEnd;
                DateTime end = PlatformToEastern(rawEnd);
                DateTime begin = PlatformToEastern(rawBegin);
                DateTime open = day.AddHours(9.5);
                if (begin > open) open = begin;
                if (day < cursor || end <= begin || day.Year < 1900 || begin.Year < 1900 || end < cursor)
                { accountReplay.Fail("Ungültige Reihenfolge im Konto-Sitzungskalender"); return; }
                // NT8 may return false for a weekend/holiday gap while populating
                // valid next bounds. Confirm strictly inside that candidate,
                // exactly as in the frozen integrity-calendar implementation.
                if (!returned)
                {
                    long duration = (rawEnd - rawBegin).Ticks;
                    long offset = Math.Min(TimeSpan.TicksPerSecond, duration / 2);
                    if (offset <= 0 || offset >= duration || !calendar.GetNextSession(rawBegin.AddTicks(offset), false)
                        || calendar.ActualSessionBegin != rawBegin || calendar.ActualSessionBegin.Kind != rawBegin.Kind
                        || calendar.ActualSessionEnd != rawEnd || calendar.ActualSessionEnd.Kind != rawEnd.Kind
                        || calendar.ActualTradingDayExchange != rawDay || calendar.ActualTradingDayExchange.Kind != rawDay.Kind)
                    { accountReplay.Fail("Konto-Sitzungskalender nicht im Sitzungsinneren bestätigt"); return; }
                }
                if (end > day.AddHours(17)) end = day.AddHours(17);
                if (end > now || open >= end) return;
                accountReplay.StartDay(day, end);
                if (!accountReplay.CloseDay(now, true, false) || accountReplay.Fault != null) return;
                cursor = day.AddDays(1);
            }
        }

        private bool ReserveAccountIntent(Intent intent, DateTime now)
        {
            // The existing owned exit must still work if the disk fails. Never
            // turn a journal error into an unprotected open position.
            if (!intent.IsEntry && (accountReplay == null || accountReplayFailure != null || accountReplay.Fault != null))
            { Print("HY ACCOUNT V8: owned exit proceeds; journal reconciliation required."); return true; }
            if (accountReplay == null || accountReplayFailure != null) return false;
            string token = (intent.IsEntry ? "ENTRY" : "EXIT") + "|"
                + now.ToString("O", CultureInfo.InvariantCulture) + "|" + intent.Reason + "|" + Guid.NewGuid().ToString("N");
            if (!intent.IsEntry)
            {
                if (accountReplay.StageExit(token))
                { accountReservedIntent = intent; accountReservationToken = token; }
                return true;
            }
            if (!accountReplay.Reserve(token))
            {
                accountReplayFailure = accountReplay.Fault ?? "Ordervorbehalt nicht gespeichert";
                entryBlocked = true;
                if (!intent.IsEntry)
                { Print("HY ACCOUNT V8: owned exit proceeds after journal write failure; reconciliation required."); return true; }
                return false;
            }
            accountReservedIntent = intent;
            accountReservationToken = token;
            return true;
        }

        private void ResolveAccountOrderTerminal(Order order, int quantity, int filled, OrderState orderState)
        {
            if (accountReplay == null || order == null || quantity != 1 || filled != 0
                || (orderState != OrderState.Cancelled && orderState != OrderState.Rejected)) return;
            Intent owner = __ORDER_OWNER__(order);
            if (owner != null && object.ReferenceEquals(owner, accountReservedIntent))
            {
                accountReplay.ConfirmNoFill(accountReservationToken);
                accountReservedIntent = null;
                accountReservationToken = null;
            }
        }

        private void RecordAccountExecution(string executionId, Intent intent, double price, DateTime executionTime)
        {
            try { RecordAccountExecutionCore(executionId, intent, price, executionTime); }
            catch (Exception e) { BlockAccountException(e); }
        }

        private void RecordAccountExecutionCore(string executionId, Intent intent, double price, DateTime executionTime)
        {
            if (accountReplay == null) { accountReplayFailure = "Ausführung ohne Kontojournal"; entryBlocked = true; return; }
            bool ok = accountReplay.Fill(executionId, intent.IsEntry, intent.Side,
                Convert.ToDecimal(price, CultureInfo.InvariantCulture), PlatformToEastern(executionTime));
            DateTime fillTime = PlatformToEastern(executionTime);
            if (ok && intent.IsEntry && bidSize > 0 && askSize > 0 && bid > 0 && ask >= bid && !double.IsInfinity(ask)
                && MarketTimeAgrees(fillTime, bidClock) && MarketTimeAgrees(fillTime, askClock))
                accountReplay.Mark(Convert.ToDecimal(bid, CultureInfo.InvariantCulture), Convert.ToDecimal(ask, CultureInfo.InvariantCulture));
            modelRealized = accountReplay.BalanceCents / 100.0;
            modelLossLatched = accountReplay.Breached;
            if (object.ReferenceEquals(intent, accountReservedIntent))
            { accountReservedIntent = null; accountReservationToken = null; }
            if (!ok) { accountReplayFailure = accountReplay.Fault ?? "Kontobuchung fehlgeschlagen"; entryBlocked = true; }
        }

        private void CloseAccountReplay()
        {
            if (accountReplay != null)
            {
                accountReplay.Dispose();
                accountReplay = null;
            }
        }
