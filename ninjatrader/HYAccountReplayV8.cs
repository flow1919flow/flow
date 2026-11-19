using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Xml;
using System.Xml.Serialization;

namespace NinjaTrader.NinjaScript.Strategies
{
    // Account accounting only. No indicator, setup, trade-stop or target calculations.
    public enum HYAccountProfileV8 { MffEvaluation, MffFunded, TradeDayEvaluation, TradeDayFunded }

    public sealed class HYAccountStateV8
    {
        public int Version = 1;
        public string Identity, Epoch, Profile, Provenance;
        public long EpochStartTicks, LastTradeDayTicks, CycleProfitCents, BlockedDayTicks;
        public long WaitingGrossCents, WaitingNetCents, PendingPayoutDayTicks;
        public string TerminalReason = "";
        public string ReconciliationReason = "";
        public long Sequence, BalanceCents, HighCents, FloorCents = -200000;
        public long DayTicks, CloseTicks, LastClosedDayTicks, DayOpeningCents;
        public long BestDayCents, PaidGrossCents, PaidNetCents, CycleStartCents;
        public int ActiveDays, WinningDays, PayoutCount, Side;
        public decimal EntryPrice;
        public long FirstFillTicks, LastPayoutTicks;
        public bool Breached, EvaluationPassed, ReviewRequired, DayHadTrade;
        public string PendingIntent = "";
        public List<string> Executions = new List<string>();
        public List<string> ExecutionFacts = new List<string>();
        public List<string> Events = new List<string>();
    }

    public sealed class HYAccountEnvelopeV8
    {
        public string Data, Sha256;
    }
    public sealed class HYAccountHeadV8 { public string Epoch; public long Sequence; }

    public sealed class HYAccountReplayV8 : IDisposable
    {
        private readonly string path;
        private readonly FileStream lease;
        private HYAccountStateV8 state;
        public readonly HYAccountProfileV8 Profile;
        public string Fault { get; private set; }
        public long BalanceCents { get { return state.BalanceCents; } }
        public long FloorCents { get { return state.FloorCents; } }
        public long HighCents { get { return state.HighCents; } }
        public bool Breached { get { return state.Breached; } }
        public bool CanEnter { get { return Fault == null && !state.Breached && !state.EvaluationPassed && !state.ReviewRequired
            && string.IsNullOrEmpty(state.TerminalReason) && state.BlockedDayTicks != state.DayTicks; } }
        public int Side { get { return state.Side; } }
        public long DayTicks { get { return state.DayTicks; } }
        public long LastClosedDayTicks { get { return state.LastClosedDayTicks; } }
        public bool LifecycleEnded { get { return state.Breached || state.EvaluationPassed || state.ReviewRequired || !string.IsNullOrEmpty(state.TerminalReason); } }
        public long CloseTicks { get { return state.CloseTicks; } }
        public string Epoch { get { return state.Epoch; } }
        public long EpochStartTicks { get { return state.EpochStartTicks; } }
        public bool HasPending { get { return !string.IsNullOrEmpty(state.PendingIntent); } }
        public string Status
        {
            get { return Fault != null ? "KONTOSTATUS PRÜFEN: " + Fault : state.Breached ? "SIM-KONTO BEENDET"
                : state.EvaluationPassed ? "EVAL BESTANDEN · Phasenwechsel ausstehend"
                : state.ReviewRequired ? "KONTOEREIGNIS PRÜFEN" : !string.IsNullOrEmpty(state.TerminalReason) ? state.TerminalReason
                : state.BlockedDayTicks == state.DayTicks ? "SIM-AUSZAHLUNGSTAG · Handel pausiert" : "KONTOREPLAY V8"; }
        }
        private bool IsTradeDay { get { return Profile == HYAccountProfileV8.TradeDayEvaluation || Profile == HYAccountProfileV8.TradeDayFunded; } }
        private bool IsEvaluation { get { return Profile == HYAccountProfileV8.MffEvaluation || Profile == HYAccountProfileV8.TradeDayEvaluation; } }
        private long FeeCents { get { return IsTradeDay ? 288 : 287; } }
        private decimal PointCents { get { return IsTradeDay ? 2000m : 5000m; } }

        public static string Identity(string account, string strategy, HYAccountProfileV8 profile)
        { return account.Trim().ToUpperInvariant() + "|" + strategy + "|" + profile.ToString(); }

        public static string FileName(string identity) { return Hash(Encoding.UTF8.GetBytes(identity)).Substring(0, 32) + ".xml"; }

        // A missing state never means a new account. A separately reviewed seed is mandatory.
        public HYAccountReplayV8(string directory, string identity, HYAccountProfileV8 profile)
        {
            Directory.CreateDirectory(directory);
            Profile = profile;
            path = Path.Combine(directory, FileName(identity));
            lease = new FileStream(path + ".lock", FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
            try
            {
                if (!File.Exists(path))
                {
                    if (File.Exists(path + ".initialized") || File.Exists(path + ".bak"))
                        throw new InvalidDataException("Primärdatei fehlt; kein automatischer Reset/Backup-Rollback");
                    string seed = Path.Combine(directory, "seeds", FileName(identity));
                    state = Read(seed);
                    Verify(identity);
                    Save();
                }
                else
                {
                    state = Read(path);
                    Verify(identity);
                    var head = Deserialize<HYAccountHeadV8>(File.ReadAllBytes(path + ".initialized"));
                    if (head.Epoch != state.Epoch || state.Sequence < head.Sequence)
                        throw new InvalidDataException("Älterer Kontostand zurückgespielt; kein automatischer Rollback");
                    if (state.Sequence > head.Sequence) SaveHead();
                }
                if (!string.IsNullOrEmpty(state.ReconciliationReason))
                    Fault = state.ReconciliationReason;
                else if (state.Side != 0 || HasPending)
                    Fault = "Neustart mit Position/Order · Ausführungen abgleichen";
            }
            catch { lease.Dispose(); throw; }
        }

        private void Verify(string identity)
        {
            if (state == null || state.Version != 1 || state.Identity != identity || state.Profile != Profile.ToString()
                || string.IsNullOrWhiteSpace(state.Epoch) || string.IsNullOrWhiteSpace(state.Provenance)
                || state.FloorCents < -200000 || state.FloorCents > (IsTradeDay ? 0 : 10000)
                || state.HighCents < 0 || state.Side < -1 || state.Side > 1 || state.Executions == null || state.Events == null
                || state.ExecutionFacts == null || state.EpochStartTicks <= 0
                || state.LastClosedDayTicks > state.DayTicks || state.ActiveDays < 0 || state.WinningDays < 0)
                throw new InvalidDataException("Kontodatei/Regelprofil inkonsistent");
        }

        public void ReconcileFlat(bool nativeFlat, bool workingOrders)
        {
            if (!nativeFlat || workingOrders || state.Side != 0 || HasPending)
                Fail("Kontoposition/Order stimmt beim Start nicht mit flachem Journal überein");
        }

        public void StartDay(DateTime day, DateTime close)
        {
            if (Fault != null || state.Breached || state.EvaluationPassed || state.ReviewRequired || !string.IsNullOrEmpty(state.TerminalReason)) return;
            day = day.Date;
            if (day.Ticks == state.DayTicks) return;
            if (day.Ticks <= state.LastClosedDayTicks || (state.DayTicks != 0 && state.LastClosedDayTicks < state.DayTicks))
            { Fail("Vorheriger Handelstag nicht abgeschlossen/Datumsrücklauf"); return; }
            if (close <= day || close >= day.AddDays(1)) { Fail("Ungültiger Sitzungsschluss"); return; }
            state.DayTicks = day.Ticks;
            state.CloseTicks = close.Ticks;
            state.DayOpeningCents = state.BalanceCents;
            state.DayHadTrade = false;
            if (state.WaitingGrossCents != 0)
            {
                state.PaidNetCents += state.WaitingNetCents;
                state.PayoutCount++;
                state.WaitingGrossCents = state.WaitingNetCents = 0;
                state.BlockedDayTicks = state.DayTicks;
                if (state.PayoutCount == 5) state.ReviewRequired = true;
                Commit("SIM_PAYOUT_APPROVED " + day.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture));
            }
            else
            {
                DateTime previous = state.LastTradeDayTicks != 0 ? new DateTime(state.LastTradeDayTicks).Date
                    : new DateTime(state.EpochStartTicks).Date.AddDays(IsTradeDay ? 0 : -1);
                if ((day - previous).Days >= (IsTradeDay ? 30 : 8))
                    state.TerminalReason = "SIM-KONTO INAKTIV";
            }
            Commit("DAY_BEGIN " + day.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture));
        }

        public bool Reserve(string intent)
        {
            if (Fault != null || HasPending || string.IsNullOrWhiteSpace(intent)) return false;
            state.PendingIntent = intent;
            return Commit("INTENT_RESERVED " + intent);
        }
        // An owned exit never waits for disk I/O. The already durable open
        // position (or entry barrier) forces reconciliation after any crash.
        public bool StageExit(string intent)
        {
            if (Fault != null || HasPending || string.IsNullOrWhiteSpace(intent)) return false;
            state.PendingIntent = intent;
            return true;
        }

        public void ConfirmNoFill(string intent)
        {
            if (Fault != null || state.PendingIntent != intent) return;
            state.PendingIntent = "";
            Commit("INTENT_TERMINAL_WITHOUT_FILL " + intent);
        }

        public bool Fill(string executionId, bool entry, int side, decimal price, DateTime time)
        {
            if (Fault != null) return false;
            if (string.IsNullOrWhiteSpace(executionId)) { Fail("Ausführungs-ID fehlt"); return false; }
            if (state.Executions.Contains(executionId))
            {
                if (KnowsExecution(executionId, price, 1, entry ? side > 0 : side < 0)) return true;
                Fail("Ausführung mit gleicher ID geändert"); return false;
            }
            if (state.DayTicks != time.Date.Ticks || state.LastClosedDayTicks >= state.DayTicks || price <= 0
                || price * 4 != decimal.Truncate(price * 4) || (side != 1 && side != -1)
                || entry && state.Side != 0 || !entry && state.Side != side)
            { Fail("Ausführung passt nicht zum gespeicherten Konto/Tag/Bestand"); return false; }
            // Same fee convention as the account-replay BBO path: entry fee now,
            // exit fee at the exit fill, not provisioned again on every open quote.
            state.BalanceCents -= FeeCents;
            if (entry)
            {
                state.Side = side; state.EntryPrice = price; state.DayHadTrade = true;
                state.LastTradeDayTicks = time.Date.Ticks;
                if (state.FirstFillTicks == 0) state.FirstFillTicks = UtcTicks(time);
            }
            else
            {
                state.BalanceCents += Money(side * (price - state.EntryPrice) * PointCents);
                state.Side = 0; state.EntryPrice = 0;
            }
            state.Executions.Add(executionId);
            state.ExecutionFacts.Add(ExecutionFact(executionId, price, 1, entry ? side > 0 : side < 0));
            state.PendingIntent = "";
            if (Crossed(state.BalanceCents)) state.Breached = true;
            if (Profile == HYAccountProfileV8.MffFunded && !state.Breached
                && state.BalanceCents - state.DayOpeningCents >= 1000000)
                state.ReviewRequired = true;
            return Commit("FILL " + executionId + " balance=" + state.BalanceCents);
        }

        public bool Mark(decimal bid, decimal ask)
        {
            if (state.Breached) return true;
            if (state.Side == 0 || bid <= 0 || ask < bid) return false;
            if (bid * 4 != decimal.Truncate(bid * 4) || ask * 4 != decimal.Truncate(ask * 4))
            { Fail("Ungültiges BBO-Tickraster; offene Position prüfen"); return false; }
            long equity = state.BalanceCents + Money(state.Side * ((state.Side > 0 ? bid : ask) - state.EntryPrice) * PointCents);
            if (Crossed(equity))
            {
                state.Breached = true;
                Commit("BREACH equity=" + equity + " floor=" + state.FloorCents);
            }
            return state.Breached;
        }

        public bool CloseDay(DateTime now, bool nativeFlat, bool workingOrders)
        {
            if (Fault != null || state.DayTicks == 0 || now.Ticks < state.CloseTicks || state.LastClosedDayTicks == state.DayTicks) return false;
            if (!nativeFlat || workingOrders || state.Side != 0 || HasPending)
            { Fail("Sitzungsende mit Position/Order · kein erfundener EOD-Saldo"); return false; }
            state.LastClosedDayTicks = state.DayTicks;
            if (!state.Breached && state.BlockedDayTicks != state.DayTicks && string.IsNullOrEmpty(state.TerminalReason))
            {
                long net = state.BalanceCents - state.DayOpeningCents;
                if (state.DayHadTrade) state.ActiveDays++;
                state.BestDayCents = Math.Max(state.BestDayCents, net);
                state.HighCents = Math.Max(state.HighCents, state.BalanceCents);
                long next = Math.Min(IsTradeDay ? 0 : 10000, state.HighCents - 200000);
                state.FloorCents = Math.Max(state.FloorCents, next);
                if (IsEvaluation)
                {
                    int consistency = IsTradeDay ? 45 : 30;
                    if (state.BalanceCents >= 300000 && state.ActiveDays >= (IsTradeDay ? 3 : 4)
                        && 100m * state.BestDayCents <= consistency * (decimal)state.BalanceCents)
                        state.EvaluationPassed = true;
                }
                else if (!state.ReviewRequired)
                {
                    state.CycleProfitCents += net;
                    if (Profile == HYAccountProfileV8.TradeDayFunded)
                    {
                        if (net >= 15000) state.WinningDays++;
                        if (state.WinningDays >= 5 && state.BalanceCents > state.CycleStartCents && state.BalanceCents > 0
                            && 100m * state.BestDayCents <= 45m * (state.BalanceCents + state.PaidGrossCents))
                        {
                            long gross = Math.Min(state.BalanceCents / 2, 150000);
                            if (gross >= 25000)
                            {
                                state.BalanceCents -= gross; state.PaidGrossCents += gross;
                                state.CycleStartCents = state.BalanceCents; state.WinningDays = 0;
                                state.HighCents = Math.Max(state.HighCents, 200000); state.FloorCents = 0;
                                state.WaitingGrossCents = gross; state.WaitingNetCents = (gross * 80 + 50) / 100;
                                state.PendingPayoutDayTicks = state.DayTicks;
                                state.Events.Add("SIM_PAYOUT_REQUEST gross=" + gross);
                            }
                        }
                    }
                    else
                    {
                        long gross = state.BalanceCents - 210000;
                        bool clock = state.FirstFillTicks != 0 && (state.LastPayoutTicks == 0
                            ? UtcTicks(new DateTime(state.CloseTicks)) - state.FirstFillTicks >= TimeSpan.TicksPerDay
                            : state.DayTicks > state.PendingPayoutDayTicks);
                        if (gross >= 50000 && clock && (state.PayoutCount == 0 || state.CycleProfitCents >= 50000))
                        {
                            state.BalanceCents -= gross; state.PaidGrossCents += gross;
                            state.PaidNetCents += (gross * 90 + 50) / 100; state.PayoutCount++;
                            state.LastPayoutTicks = UtcTicks(new DateTime(state.CloseTicks));
                            state.PendingPayoutDayTicks = state.DayTicks; state.CycleProfitCents = 0;
                            state.Events.Add("SIM_PAYOUT_PAID gross=" + gross);
                            if (Crossed(state.BalanceCents)) state.Breached = true;
                        }
                    }
                }
            }
            return Commit("EOD floor=" + state.FloorCents + " balance=" + state.BalanceCents);
        }

        public void ApplyPayout(string eventId, long grossCents, long netCents, DateTime time)
        {
            string key = "PAYOUT " + eventId;
            if (state.Events.Contains(key)) return;
            if (Fault != null || IsEvaluation || state.Breached || state.Side != 0 || HasPending
                || grossCents <= 0 || netCents <= 0 || netCents > grossCents || grossCents > state.BalanceCents)
            { Fail("Auszahlung nicht mit Konto vereinbar"); return; }
            state.BalanceCents -= grossCents;
            state.PaidGrossCents += grossCents; state.PaidNetCents += netCents; state.PayoutCount++;
            state.LastPayoutTicks = time.Ticks;
            if (IsTradeDay) { state.FloorCents = 0; state.HighCents = Math.Max(state.HighCents, 200000); }
            if (Crossed(state.BalanceCents)) state.Breached = true;
            state.Events.Add(key);
            Commit("PAYOUT_APPLIED gross=" + grossCents);
        }

        private bool Crossed(long equity) { return IsTradeDay ? equity <= state.FloorCents : equity < state.FloorCents; }
        public bool KnowsExecution(string id, decimal price, int quantity, bool buy)
        { return state.ExecutionFacts.Contains(ExecutionFact(id, price, quantity, buy)); }
        private static string ExecutionFact(string id, decimal price, int quantity, bool buy)
        { return id + "|" + price.ToString("0.############################", CultureInfo.InvariantCulture) + "|" + quantity + "|" + (buy ? "BUY" : "SELL"); }
        private static long UtcTicks(DateTime eastern)
        { return TimeZoneInfo.ConvertTimeToUtc(DateTime.SpecifyKind(eastern, DateTimeKind.Unspecified), TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time")).Ticks; }
        private static long Money(decimal cents)
        {
            if (cents != decimal.Truncate(cents)) throw new InvalidDataException("Nicht ganzzahliger Centbetrag");
            return checked((long)cents);
        }
        private bool Commit(string detail)
        {
            state.Events.Add(detail);
            try { Save(); return true; }
            catch (Exception e) { Fault = "Speichern fehlgeschlagen · " + e.GetType().Name; return false; }
        }
        public void Fail(string reason)
        {
            if (Fault != null) return;
            Fault = reason;
            state.ReconciliationReason = reason;
            state.Events.Add("RECONCILIATION_REQUIRED " + reason);
            try { Save(); } catch { /* Existing open-position/send barrier remains on disk. */ }
        }
        public HYAccountStateV8 Snapshot() { return Deserialize<HYAccountStateV8>(Serialize(state)); }

        private void Save()
        {
            state.Sequence++;
            WriteAtomic(path, state);
            SaveHead();
        }
        private void SaveHead()
        { WriteBytesAtomic(path + ".initialized", Serialize(new HYAccountHeadV8 { Epoch = state.Epoch, Sequence = state.Sequence })); }
        public static void WriteSeed(string path, HYAccountStateV8 seed)
        {
            if (File.Exists(path)) throw new IOException("Seed existiert bereits");
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            WriteAtomic(path, seed);
        }
        private static void WriteAtomic(string file, HYAccountStateV8 value)
        {
            byte[] data = Serialize(value);
            byte[] output = Serialize(new HYAccountEnvelopeV8 { Data = Convert.ToBase64String(data), Sha256 = Hash(data) });
            WriteBytesAtomic(file, output);
        }
        private static void WriteBytesAtomic(string file, byte[] output)
        {
            string temp = file + "." + Guid.NewGuid().ToString("N") + ".tmp";
            try
            {
                using (var stream = new FileStream(temp, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                { stream.Write(output, 0, output.Length); stream.Flush(true); }
                if (File.Exists(file)) File.Replace(temp, file, file + ".bak", true);
                else File.Move(temp, file);
            }
            finally { if (File.Exists(temp)) File.Delete(temp); }
        }
        private static HYAccountStateV8 Read(string file)
        {
            var envelope = Deserialize<HYAccountEnvelopeV8>(File.ReadAllBytes(file));
            byte[] data = Convert.FromBase64String(envelope.Data);
            if (Hash(data) != envelope.Sha256) throw new InvalidDataException("Prüfsumme ungültig");
            return Deserialize<HYAccountStateV8>(data);
        }
        private static byte[] Serialize<T>(T value)
        {
            using (var stream = new MemoryStream())
            { new XmlSerializer(typeof(T)).Serialize(stream, value); return stream.ToArray(); }
        }
        private static T Deserialize<T>(byte[] bytes)
        {
            using (var stream = new MemoryStream(bytes))
            using (var reader = XmlReader.Create(stream, new XmlReaderSettings { DtdProcessing = DtdProcessing.Prohibit, XmlResolver = null }))
                return (T)new XmlSerializer(typeof(T)).Deserialize(reader);
        }
        private static string Hash(byte[] data)
        { using (var sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(data)).Replace("-", "").ToLowerInvariant(); }
        public void Dispose() { lease.Dispose(); }
    }
}
