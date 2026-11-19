using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.Linq;
using System.Threading;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
using D2D = SharpDX.Direct2D1;
using DWrite = SharpDX.DirectWrite;

namespace NinjaTrader.NinjaScript.Strategies
{
    public class HY104C2803FundedSim : Strategy
    {
        private const string LongEntry = "HY104C2803FundedSimLong";
        private const string ShortEntry = "HY104C2803FundedSimShort";
        private const string StopDrawing = "HY104C2803FundedSimFixedStop";
        private const string TradingHoursName = "CME US Index Futures ETH";
        private const int WarmupSessions = 5;
        private const string SimulationAccountName = "Sim104C28Funded";
        private const bool UsesOpeningRange = true;
        private static readonly TimeSpan OpeningWindow = TimeSpan.FromMinutes(60);
        private bool modelLossLatched;
        private double modelRealized;
        private double openingHigh, openingLow;
        private bool openingObserved, openingFromStart, openingReported;
        private DateTime bidClock, askClock;
        private const double TargetOffsetPoints = 0.75 * 0.25;
        private static readonly TimeSpan MaximumClockSkew = TimeSpan.FromSeconds(5);
        private static int simulationOrderSlot;
        private static readonly TimeSpan FiveMinutes = TimeSpan.FromMinutes(5);
        private static readonly TimeSpan PreviewWindow = TimeSpan.FromMinutes(30);
        private static readonly Brush EmaBrush = FrozenBrush(232, 182, 107);
        private static readonly Brush UpCandle = FrozenBrush(230, 236, 244);
        private static readonly Brush DownCandle = FrozenBrush(143, 136, 184);
        private static readonly Brush UpOutline = FrozenBrush(196, 206, 220);
        private static readonly Brush DownOutline = FrozenBrush(165, 159, 200);
        private static readonly Brush KeltnerBrush = FrozenBrush(94, 143, 138);
        private static readonly Brush BollingerBrush = FrozenBrush(112, 136, 191);
        private static readonly Brush StopBrush = FrozenBrush(255, 156, 172);
        private static readonly SharpDX.Color4 LiveAccent = Pigment(55, 222, 143);
        private static readonly SharpDX.Color4 ReplayAccent = Pigment(116, 147, 194);
        private static readonly SharpDX.Color4 ManualAccent = Pigment(166, 181, 203);
        private static readonly SharpDX.Color4 WaitingAccent = Pigment(255, 201, 74);
        private static readonly SharpDX.Color4 ClosedAccent = Pigment(255, 83, 105);
        private static readonly SharpDX.Color4 ErrorAccent = Pigment(255, 83, 105);
        private readonly object sync = new object();
        private readonly IndicatorState indicators = new IndicatorState();

        private TimeZoneInfo platformZone;
        private TimeZoneInfo easternZone;
        private TimeZoneInfo chicagoZone;
        private SessionIterator sessionIterator;
        private SessionIterator integrityCalendar;
        private bool integrityBoundaryProbed;
        private int verifiedCompleteSessions;
        private DateTime integritySeedBegin, lastUncoveredSession, integrityLastEventTime;
        private bool integrityCalendarFailed, integrityAuditFailed;
        private string integrityFailure, lastCoverageReason, integrityAuditPath;
        private System.IO.StreamWriter integrityAudit;
        private long integrityAuditSequence;
        private double integrityBarOpen;
        private long integrityBarTicks;
        private DateTime templateBegin;
        private DateTime templateEnd;
        private DateTime sessionOpen;
        private DateTime sessionEnd;
        private DateTime flattenAt;
        private DateTime lastMarketTime;
        private DateTime lastProcessedTradeTime; // Last-event order independent of quote/control clocks.
        private DateTime barStart;
        private double barHigh;
        private double barLow;
        private double barClose;
        private int committedBars;
        private int completeSessions;
        private int lastBand;
        private int setupSide;
        private bool sessionFinished;
        private bool sessionComplete;
        private bool sessionSeenTrade;
        private bool entryBlocked;
        private bool exitSubmissionFailed;
        private bool ready;
        private bool liveClock;
        private bool ownsSimulationOrderSlot;
        private DateTime lastTradeClock;
        private Timer watchdog;
        private int watchdogQueued;

        private double bid;
        private double ask;
        private long bidSize;
        private long askSize;
        private int positionSide;
        private double positionStop;
        private double positionEntryPrice;
        private double positionExitBand;
        private Intent pending;
        private Intent submitted;
        private IndicatorState previewIndicators;
        private DateTime previewSessionOpen;
        private DateTime previewBarStart;
        private double previewHigh;
        private double previewLow;
        private double previewClose;
        private bool firstPreviewBar;
        private Lines chartLines;
        private DateTime chartLinesBarEnd;
        private long legendSecond = -1;
        private StatusCard statusCard;
        private string lastModelSignal;
        private double drawnStop;
        private SetupPoint lastContactMark, armedFirstMark, armedSecondMark;
        private readonly List<EntryMarks> confirmedEntryMarks = new List<EntryMarks>(8);
        private readonly List<SetupBadge> sessionBadges = new List<SetupBadge>(24);

        private sealed class SetupPoint
        {
            public readonly int Bar;
            public readonly double Price;
            public readonly int Side;
            public readonly DateTime Session;
            public SetupPoint(int bar, double price, int side, DateTime session)
            { Bar = bar; Price = price; Side = side; Session = session; }
        }

        private sealed class SetupBadge
        {
            public readonly SetupPoint Point;
            public readonly int Step;
            public SetupBadge(SetupPoint point, int step)
            { Point = point; Step = step; }
        }

        private sealed class EntryMarks
        {
            public readonly SetupPoint First, Second, Return;
            public SetupPoint Fill;
            public EntryMarks(SetupPoint first, SetupPoint second, SetupPoint retrace)
            { First = first; Second = second; Return = retrace; }
            public bool Contains(SetupPoint point)
            { return point == First || point == Second || point == Return || point == Fill; }
        }

        [NinjaScriptProperty]
        [Display(Name = "Lokale Sim-Automatik", GroupName = "HY104", Order = 0)]
        public bool SimAutomatik { get; set; }

        protected override void OnStateChange()
        {
            // Diagnostic state identity only; no trading readiness or clock changes.
            if (State == State.Historical || State == State.Realtime)
                AuditRuntimeMetadata("state transition");
            if (State == State.SetDefaults)
            {
                Name = "104-C28.03 | Rapid EOD Funded SIM";
                Description = "HY104 mit einem ES, ausschließlich auf dem lokalen Simulationskonto "
                    + SimulationAccountName + ". Voreinstellung: Signale. Bollinger-Ziel um "
                    + (TargetOffsetPoints / 0.25).ToString(CultureInfo.InvariantCulture) + " ES-Tick verkürzt.";
                SimAutomatik = false;
                Calculate = Calculate.OnEachTick;
                BarsRequiredToTrade = 0;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                StartBehavior = StartBehavior.WaitUntilFlat;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                IsExitOnSessionCloseStrategy = false;
                IsInstantiatedOnEachOptimizationIteration = true;
                IsOverlay = true;
                AddPlot(new Stroke(BollingerBrush, DashStyleHelper.Dash, 1.5f), PlotStyle.Line, "HY104 BB-Ziel oben");
                AddPlot(new Stroke(BollingerBrush, DashStyleHelper.Dash, 1.5f), PlotStyle.Line, "HY104 BB-Ziel unten");
                AddPlot(new Stroke(KeltnerBrush, 1.5f), PlotStyle.Line, "HY104 Keltner oben");
                AddPlot(new Stroke(KeltnerBrush, 1.5f), PlotStyle.Line, "HY104 Keltner unten");
                AddPlot(new Stroke(EmaBrush, 2), PlotStyle.Line, "HY104 Mitte");
            }
            else if (State == State.DataLoaded)
            {
                platformZone = Core.Globals.GeneralOptions.TimeZoneInfo;
                easternZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
                chicagoZone = TimeZoneInfo.FindSystemTimeZoneById("Central Standard Time");
                if (!platformZone.HasSameRules(TimeZoneInfo.Local))
                    throw new InvalidOperationException("HY104: NinjaTrader and Windows must use the same time zone.");
                if (Instrument.MasterInstrument.Name != "ES" || Instrument.MasterInstrument.TickSize != 0.25
                    || Instrument.MasterInstrument.PointValue != 50.0)
                    throw new InvalidOperationException("HY104: select an individual ES futures contract.");
                if (BarsPeriod.BarsPeriodType != BarsPeriodType.Minute || BarsPeriod.Value != 5
                    || Bars.TradingHours.Name != TradingHoursName || IsTickReplays[0] != true)
                    throw new InvalidOperationException("HY104: use ES, 5 minutes, CME US Index Futures ETH and Tick Replay.");

                sessionIterator = new SessionIterator(Bars);
                integrityCalendar = new SessionIterator(Bars);
                InitializeNewsCalendar();
                InitializeIntegrityAudit();
                ready = true;
            }
            else if (State == State.Historical && ChartControl != null)
            {
                // A workspace can restore old plot strokes after SetDefaults.
                // Set the chart presentation explicitly without changing any series data.
                for (int i = 0; i < 5; ++i)
                {
                    Plots[i].Brush = i < 2 ? BollingerBrush : i < 4 ? KeltnerBrush : EmaBrush;
                    Plots[i].Width = i == 4 ? 2f : 1.5f;
                    Plots[i].DashStyleHelper = i < 2 ? DashStyleHelper.Dash : DashStyleHelper.Solid;
                }
                SetZOrder(-1);
            }
            else if (State == State.Realtime && ready)
            {
                bidSize = askSize = 0;
                if (Account == null)
                {
                    Print("HY104: select an account in the strategy settings.");
                    return;
                }

                liveClock = NinjaTrader.Cbi.Connection.PlaybackConnection == null;
                if (SimAutomatik && liveClock && MatchesSimulationAccount())
                    ownsSimulationOrderSlot = Interlocked.CompareExchange(ref simulationOrderSlot, 1, 0) == 0;
                InitializeAccountReplay();
                Print("HY104: " + Account.Name + " · " + ModeLabel()
                    + " · Aufwärmsitzungen " + completeSessions + "/" + WarmupSessions);
                if (ChartControl != null)
                    UpdateLegend(liveClock ? EasternNow() : lastMarketTime);
                if (liveClock)
                    watchdog = new Timer(QueueWatchdog, null, 250, 250);
            }
            else if (State == State.Terminated)
            {
                lock (sync)
                {
                    CloseAccountReplay();
                    CloseIntegrityAudit();
                }
                if (watchdog != null)
                    watchdog.Dispose();
                if (ownsSimulationOrderSlot)
                {
                    ownsSimulationOrderSlot = false;
                    Interlocked.Exchange(ref simulationOrderSlot, 0);
                }
            }
        }

        protected override void OnBarUpdate()
        {
            if (ChartControl != null && BarsInProgress == 0 && CurrentBar >= 0)
            {
                bool rising = Close[0] >= Open[0];
                BarBrush = rising ? UpCandle : DownCandle;
                CandleOutlineBrush = rising ? UpOutline : DownOutline;
            }
            if (ChartControl == null || !IsFirstTickOfBar || CurrentBar < 1)
                return;
            lock (sync)
            {
                // The chart timestamps time bars at their close.
                if (chartLinesBarEnd == PlatformToEastern(Time[1]))
                    PlotLines(1, chartLines);
            }
        }

        protected override void OnMarketData(MarketDataEventArgs update)
        {
            if (!ready || (State != State.Historical && State != State.Realtime))
                return;
            bool realtime = State == State.Realtime;
            if (realtime && Account == null)
                return;

            var kind = update.MarketDataType;
            if (!realtime && kind != MarketDataType.Last)
                return;
            if (kind != MarketDataType.Bid && kind != MarketDataType.Ask && kind != MarketDataType.Last)
                return;

            DateTime marketEventTime = PlatformToEastern(update.Time);
            DateTime time = realtime && liveClock ? EasternNow() : marketEventTime;
            if (realtime && liveClock && !MarketTimeAgrees(time, marketEventTime))
                return;
            Intent next;
            lock (sync)
            {
                // Quotes may be timestamped ahead of a Last during playback.
                // Keep receipt/control time monotonic without dropping that Last.
                if ((realtime && liveClock || kind != MarketDataType.Last) && time < lastMarketTime)
                    return;
                if (time > lastMarketTime)
                    lastMarketTime = time;
                integrityLastEventTime = marketEventTime;
                if (realtime)
                {
                    EnsureNewsCalendar(time);
                    AdvanceNews(time);
                }

                bool forceClose = realtime && CheckClose(time);
                // When crossing an entire session gap, handle the old position before replacing its close time.
                next = forceClose ? TakePending(time, false, true) : null;
                // Only a valid, ordered Last may advance/finalize market sessions.
                // Control time still governs CheckClose and pending order deadlines.
                bool processTrade = kind == MarketDataType.Last && update.Price > 0
                    && !double.IsInfinity(update.Price) && marketEventTime >= lastProcessedTradeTime;
                if (kind == MarketDataType.Last && !processTrade)
                    AuditIntegrity("LAST_IGNORED", marketEventTime,
                        "Invalid price or Last predates most recently processed Last; control dispatch remains active", update.Price);
                if (processTrade)
                {
                    lastProcessedTradeTime = marketEventTime;
                    RefreshSession(marketEventTime);
                }
                if (processTrade)
                    ObserveOpeningRange(marketEventTime, update.Price, realtime);
                if (realtime && kind == MarketDataType.Last)
                    CheckModelLoss(time, false);
                if (kind == MarketDataType.Last)
                {
                    if (processTrade)
                    {
                        // Last-trade timestamps determine the indicator candles; the local clock
                        // still drives order deadlines; Last time finalizes the session.
                        if (!sessionFinished && marketEventTime >= sessionOpen && marketEventTime < sessionEnd)
                            ObserveTrade(time, marketEventTime, update.Price, realtime);
                        else if (ChartControl != null && !sessionSeenTrade && marketEventTime >= templateBegin
                            && marketEventTime < sessionOpen && sessionOpen < sessionEnd)
                            ObservePreviewTrade(marketEventTime, update.Price);
                    }
                }
                else if (kind == MarketDataType.Bid)
                {
                    bid = update.Price;
                    bidSize = update.Volume;
                    bidClock = time;
                }
                else
                {
                    ask = update.Price;
                    askSize = update.Volume;
                    askClock = time;
                }

                if (realtime && next == null)
                {
                    bool loss = CheckModelLoss(time, true);
                    forceClose = CheckClose(time) || loss;
                    bool quote = kind == MarketDataType.Bid || kind == MarketDataType.Ask;
                    next = TakePending(time, quote, forceClose);
                }
            }
            if (next != null)
                Submit(next);
            if (realtime && ChartControl != null)
            {
                if (kind == MarketDataType.Last && CurrentBar >= 0)
                    PlotRealtime();
                if (!liveClock)
                    UpdateLegend(time);
            }
        }

        private bool IsPreviewTime(DateTime time)
        {
            return sessionOpen < sessionEnd && time >= templateBegin
                && time >= sessionOpen - PreviewWindow && time < sessionOpen;
        }

        private void ObservePreviewTrade(DateTime time, double price)
        {
            // Warm up the display on overnight trades without adding them to the strategy's indicators.
            if (previewSessionOpen != sessionOpen)
            {
                previewSessionOpen = sessionOpen;
                previewIndicators = new IndicatorState();
                previewBarStart = default(DateTime);
                firstPreviewBar = true;
            }

            long elapsed = (time - templateBegin).Ticks;
            DateTime bucket = templateBegin.AddTicks(elapsed / FiveMinutes.Ticks * FiveMinutes.Ticks);
            if (bucket < previewBarStart)
                return;
            if (previewBarStart != bucket)
            {
                if (previewBarStart != default(DateTime))
                {
                    previewIndicators.Commit(previewHigh, previewLow, previewClose, firstPreviewBar);
                    firstPreviewBar = false;
                }
                previewBarStart = bucket;
                previewHigh = previewLow = price;
            }
            previewHigh = Math.Max(previewHigh, price);
            previewLow = Math.Min(previewLow, price);
            previewClose = price;

            Lines lines;
            if (IsPreviewTime(time)
                && previewIndicators.TryPreview(previewHigh, previewLow, previewClose, firstPreviewBar, out lines))
            {
                chartLines = lines;
                chartLinesBarEnd = bucket + FiveMinutes;
            }
        }

        private void UpdateLegend(DateTime time)
        {
            if (ChartControl == null || Account == null || time == default(DateTime))
                return;
            long second = time.Ticks / TimeSpan.TicksPerSecond;
            lock (sync)
            {
                if (legendSecond == second)
                    return;
                legendSecond = second;
                bool simulatedOrders = IsOrderAccount();
                string mode = ModeLabel();
                string state = GetLegendStatus(time, simulatedOrders, out SharpDX.Color4 accent);
                string detail = simulatedOrders ? null : lastModelSignal;
                string levels = null;
                if (positionSide != 0)
                {
                    detail = GetPositionLegend(simulatedOrders);
                    levels = string.Format(CultureInfo.CurrentCulture,
                        "{0} {1:F2}   |   Stop {2:F2}   |   Ziel {3:F4}",
                        simulatedOrders ? "Einstieg" : "Modell", positionEntryPrice, positionStop, positionExitBand);
                }
                else if (!simulatedOrders && pending != null && pending.IsEntry)
                {
                    detail = "Setup " + (pending.Side > 0 ? "LONG" : "SHORT") + " · Quote ausstehend";
                    levels = string.Format(CultureInfo.CurrentCulture, "Stop {0:F2}   |   Ziel {1:F4}",
                        pending.Stop, pending.Side > 0 ? chartLines.BollingerUpper : chartLines.BollingerLower);
                }
                string integrityDetail = IntegrityLegend();
                if (integrityDetail != null)
                    detail = string.IsNullOrEmpty(detail) ? integrityDetail : detail + "\n" + integrityDetail;
                DateTime candleEnd = CurrentBar >= 0 ? PlatformToEastern(Time[0]) : default(DateTime);
                TimeSpan candleRemaining = candleEnd - time;
                bool currentCandle = candleRemaining > TimeSpan.Zero && candleRemaining <= FiveMinutes;
                string countdown = currentCandle
                    ? TimeSpan.FromSeconds(Math.Ceiling(candleRemaining.TotalSeconds))
                        .ToString(@"mm\:ss", CultureInfo.InvariantCulture)
                    : "—";
                DateTime orderDeadline = flattenAt == default(DateTime) ? sessionEnd : flattenAt.AddMinutes(1);
                TimeSpan marketRemaining = orderDeadline - time;
                string marketCountdown = time >= sessionOpen && marketRemaining > TimeSpan.Zero
                    ? TimeSpan.FromSeconds(Math.Ceiling(marketRemaining.TotalSeconds))
                        .ToString(@"hh\:mm\:ss", CultureInfo.InvariantCulture)
                    : null;
                DateTime chicago = TimeZoneInfo.ConvertTime(DateTime.SpecifyKind(time, DateTimeKind.Unspecified),
                    easternZone, chicagoZone);
                EntryMarks trace = (submitted ?? pending)?.Marks;
                if (positionSide != 0 && confirmedEntryMarks.Count > 0)
                    trace = confirmedEntryMarks[confirmedEntryMarks.Count - 1];
                SetupPoint first = trace != null ? trace.First
                    : armedSecondMark != null ? armedFirstMark : lastContactMark;
                SetupPoint opposite = trace != null ? trace.Second : armedSecondMark;
                statusCard = new StatusCard(Account.Name, chicago.ToString("HH:mm:ss", CultureInfo.InvariantCulture) + " CT",
                    mode, state, detail, levels, countdown, marketCountdown, accent,
                    FormatSetupPrice(first, sessionOpen.Date),
                    FormatSetupPrice(opposite, sessionOpen.Date),
                    FormatSetupPrice(trace?.Return, sessionOpen.Date), first?.Side ?? 0, opposite?.Side ?? 0);
            }
            ForceRefresh();
        }

        private static string FormatSetupPrice(SetupPoint point, DateTime session)
        {
            if (point == null)
                return null;
            string previous = point.Session < session ? " (Vorsitzung)" : "";
            return point.Price.ToString("F2", CultureInfo.CurrentCulture) + previous;
        }

        private string GetPositionLegend(bool simulatedOrders)
        {
            string status = (simulatedOrders ? "POSITION OFFEN · " : "SIGNALMODELL · ")
                + (positionSide > 0 ? "LONG ×1" : "SHORT ×1");
            if (exitSubmissionFailed)
                status += "  ·  Ausstieg fehlgeschlagen, Log prüfen";
            else if ((pending != null && !pending.IsEntry) || (submitted != null && !submitted.IsEntry))
                status += "  ·  Ausstieg läuft";
            return status;
        }

        private string GetLegendStatus(DateTime time, bool simulatedOrders, out SharpDX.Color4 accent)
        {
            accent = WaitingAccent;
            if (!MatchesSimulationAccount())
            {
                accent = ErrorAccent;
                return "LOKALES SIM-KONTO PRÜFEN";
            }
            if (SimAutomatik && !ownsSimulationOrderSlot && liveClock)
            {
                accent = ErrorAccent;
                return "SIM-KONTO BEREITS BELEGT";
            }
            if (SimAutomatik && (!liveClock || !OrderConnectionReady()))
            {
                accent = ErrorAccent;
                return "WARTET  ·  SIM-Orderverbindung";
            }
            if (!AccountReplayReady() && State == State.Realtime && IsOrderAccount())
            {
                accent = modelLossLatched || accountReplayFailure != null ? ErrorAccent : WaitingAccent;
                return AccountReplayStatus();
            }
            if (integrityAuditFailed || integrityCalendarFailed)
            {
                accent = ErrorAccent;
                return IntegrityGateReason();
            }
            string news = NewsEntryGateReason(time);
            if (news != null)
            {
                accent = ErrorAccent;
                return news;
            }
            if (IsPreviewTime(time))
            {
                var remaining = TimeSpan.FromSeconds(Math.Ceiling((sessionOpen - time).TotalSeconds));
                return "VORSCHAU  ·  Handelsstart in " + remaining.ToString(@"mm\:ss", CultureInfo.InvariantCulture);
            }
            if (time < sessionOpen || time >= sessionEnd)
            {
                accent = ClosedAccent;
                return "AUSSERHALB DER SITZUNG";
            }
            if (entryBlocked)
            {
                accent = ErrorAccent;
                return "EINSTIEGE GESPERRT  ·  Log prüfen";
            }
            if (time >= flattenAt)
            {
                accent = ClosedAccent;
                return "SITZUNGSENDE  ·  Keine neuen Einstiege";
            }
            if (modelLossLatched)
            {
                accent = ErrorAccent;
                return "SIM-VERLUSTGRENZE ERREICHT";
            }
            string integrity = IntegrityGateReason();
            if (integrity != null)
                return "GESPERRT  ·  " + integrity;
            if (completeSessions < WarmupSessions)
                return "WARTET  ·  Warm-up " + completeSessions + "/" + WarmupSessions;
            if (!sessionComplete)
                return "WARTET  ·  Unvollständige Sitzung";
            if (!sessionSeenTrade || (liveClock && !MarketTimeAgrees(time, lastTradeClock)))
                return "WARTET  ·  Aktuelle Marktdaten";
            accent = simulatedOrders ? (liveClock ? LiveAccent : ReplayAccent) : ManualAccent;
            return (liveClock ? "LIVE" : "REPLAY") + (simulatedOrders ? "  ·  Handel aktiv" : "  ·  Signale aktiv");
        }

        private void PlotRealtime()
        {
            double stop;
            lock (sync)
            {
                if (chartLinesBarEnd == PlatformToEastern(Time[0]))
                    PlotLines(0, chartLines);
                stop = positionSide == 0 ? 0 : positionStop;
            }

            if (stop == drawnStop)
                return;
            if (stop > 0)
                Draw.HorizontalLine(this, StopDrawing, false, stop, StopBrush, DashStyleHelper.Dash, 2);
            else
                RemoveDrawObject(StopDrawing);
            drawnStop = stop;
        }

        private void PlotLines(int barsAgo, Lines lines)
        {
            Values[4][barsAgo] = lines.Ema;
            Values[2][barsAgo] = lines.KeltnerUpper;
            Values[3][barsAgo] = lines.KeltnerLower;
            Values[0][barsAgo] = lines.BollingerUpper;
            Values[1][barsAgo] = lines.BollingerLower;
        }

        private static Brush FrozenBrush(byte red, byte green, byte blue)
        {
            var brush = new SolidColorBrush(Color.FromRgb(red, green, blue));
            brush.Freeze();
            return brush;
        }

        private static SharpDX.Color4 Pigment(byte red, byte green, byte blue, float alpha = 1f)
        {
            return new SharpDX.Color4(red / 255f, green / 255f, blue / 255f, alpha);
        }

        protected override void OnRender(ChartControl chartControl, ChartScale chartScale)
        {
            if (ChartBars != null && RenderTarget != null && Values != null && Values.Length == 5)
            {
                int first = Math.Max(0, ChartBars.FromIndex);
                int last = Math.Min(ChartBars.ToIndex, Values[1].Count - 1);
                int index = first;
                while (index <= last)
                {
                    if (!Values[1].IsValidDataPointAt(index))
                    {
                        index++;
                        continue;
                    }

                    int start = index++;
                    while (index <= last && Values[1].IsValidDataPointAt(index))
                        index++;
                    int end = index - 1;
                    if (end > start)
                    {
                        FillBand(chartControl, chartScale, start, end, Values[2], Values[3],
                            Pigment(94, 143, 138, 0.06f));
                    }
                }
            }
            base.OnRender(chartControl, chartScale);
            RenderEntryMarks(chartControl, chartScale);
            RenderBandLabels(chartControl, chartScale);
            RenderStatusCard();
        }

        private void RememberBadge(SetupPoint point, int step)
        {
            if (point == null || point.Session != sessionOpen.Date || sessionBadges.Any(b => b.Point == point))
                return;
            if (sessionBadges.Count == 96)
                sessionBadges.RemoveAt(0);
            sessionBadges.Add(new SetupBadge(point, step));
        }

        private void RenderEntryMarks(ChartControl chart, ChartScale scale)
        {
            if (RenderTarget == null || ChartBars == null || ChartPanel == null || Bars == null)
                return;
            EntryMarks active;
            EntryMarks[] recent;
            SetupBadge[] badges;
            SetupPoint first, second, retrace;
            lock (sync)
            {
                recent = confirmedEntryMarks.ToArray();
                badges = sessionBadges.ToArray();
                active = (submitted ?? pending)?.Marks;
                if (positionSide != 0 && recent.Length > 0)
                    active = recent[recent.Length - 1];
                first = active != null ? active.First : armedSecondMark == null ? lastContactMark : armedFirstMark;
                second = active != null ? active.Second : armedSecondMark;
                retrace = active?.Return;
            }

            // A contact reused by the current setup has one visible number, even if its role changed.
            var drawn = new HashSet<SetupPoint> { first, second, retrace, active?.Fill };
            using (var cyan = new D2D.SolidColorBrush(RenderTarget, Pigment(86, 228, 255)))
            using (var violet = new D2D.SolidColorBrush(RenderTarget, Pigment(204, 164, 255)))
            using (var gold = new D2D.SolidColorBrush(RenderTarget, Pigment(255, 214, 97)))
            using (var mint = new D2D.SolidColorBrush(RenderTarget, Pigment(88, 255, 184)))
            using (var gray = new D2D.SolidColorBrush(RenderTarget, Pigment(149, 158, 174, .66f)))
            using (var ink = new D2D.SolidColorBrush(RenderTarget, Pigment(11, 19, 33)))
            using (var number = new DWrite.TextFormat(Core.Globals.DirectWriteFactory, "Segoe UI Semibold", 28f))
            using (var smallNumber = new DWrite.TextFormat(Core.Globals.DirectWriteFactory, "Segoe UI Semibold", 17f))
            {
                number.TextAlignment = smallNumber.TextAlignment = DWrite.TextAlignment.Center;
                number.ParagraphAlignment = smallNumber.ParagraphAlignment = DWrite.ParagraphAlignment.Center;
                number.WordWrapping = smallNumber.WordWrapping = DWrite.WordWrapping.NoWrap;

                for (int i = recent.Length - 1; i >= 0; --i)
                {
                    EntryMarks trace = recent[i];
                    if (trace == active)
                        continue;
                    if (drawn.Add(trace.First)) DrawStep(trace.First, 1, false, chart, scale, gray, ink, smallNumber);
                    if (drawn.Add(trace.Second)) DrawStep(trace.Second, 2, false, chart, scale, gray, ink, smallNumber);
                    if (drawn.Add(trace.Return)) DrawStep(trace.Return, 3, false, chart, scale, gray, ink, smallNumber);
                    if (drawn.Add(trace.Fill)) DrawFillMark(trace.Fill, false, chart, scale, gray, ink, smallNumber);
                }
                for (int i = badges.Length - 1; i >= 0; --i)
                {
                    SetupBadge badge = badges[i];
                    if (drawn.Add(badge.Point))
                        DrawStep(badge.Point, badge.Step, false, chart, scale, gray, ink, smallNumber);
                }

                DrawStep(first, 1, true, chart, scale, cyan, ink, number);
                DrawStep(second, 2, true, chart, scale, violet, ink, number);
                DrawStep(retrace, 3, true, chart, scale, gold, ink, number);
                if (active?.Fill != null)
                    DrawFillMark(active.Fill, true, chart, scale, mint, ink, number);
            }
        }

        private void DrawStep(SetupPoint point, int step, bool current, ChartControl chart, ChartScale scale,
            D2D.Brush color, D2D.Brush ink, DWrite.TextFormat text)
        {
            if (point == null)
                return;
            if (step == 3)
                point = new SetupPoint(point.Bar, point.Price, -point.Side, point.Session);
            DrawSetupBadge(point, step == 1 ? "1" : step == 2 ? "2" : "3",
                step == 3 ? -59f : 0f, current ? 24f : 14f, false, chart, scale, color, ink, text);
        }

        private bool VisibleMark(SetupPoint p, ChartScale scale)
        {
            if (p == null || p.Bar < ChartBars.FromIndex || p.Bar > ChartBars.ToIndex || p.Bar >= Bars.Count)
                return false;
            float y = scale.GetYByValue(p.Price);
            return y >= ChartPanel.Y + 10f && y <= ChartPanel.Y + ChartPanel.H - 10f;
        }

        private void DrawSetupBadge(SetupPoint p, string label, float shift, float radius, bool fill,
            ChartControl chart, ChartScale scale, D2D.Brush color, D2D.Brush ink, DWrite.TextFormat text)
        {
            if (!VisibleMark(p, scale) || ChartPanel.W < 310f || ChartPanel.H < 175f)
                return;

            float barX = chart.GetXByBarIndex(ChartBars, p.Bar);
            float priceY = scale.GetYByValue(p.Price);
            float outer = p.Side > 0 ? scale.GetYByValue(Bars.GetHigh(p.Bar)) : scale.GetYByValue(Bars.GetLow(p.Bar));
            float x = Math.Max(ChartPanel.X + radius + 10f,
                Math.Min(ChartPanel.X + ChartPanel.W - radius - 14f, barX + shift));
            float y = Math.Max(ChartPanel.Y + 119f,
                Math.Min(ChartPanel.Y + ChartPanel.H - 42f, outer - p.Side * (fill ? 56f : 37f)));
            var center = new SharpDX.Vector2(x, y);
            var anchor = new SharpDX.Vector2(barX, priceY);

            RenderTarget.DrawLine(anchor, center, ink, 6f);
            RenderTarget.DrawLine(anchor, center, color, 2.5f);
            RenderTarget.FillEllipse(new D2D.Ellipse(anchor, 6f, 6f), ink);
            RenderTarget.FillEllipse(new D2D.Ellipse(anchor, 3.5f, 3.5f), color);
            RenderTarget.FillEllipse(new D2D.Ellipse(center, radius + 5f, radius + 5f), ink);
            RenderTarget.DrawEllipse(new D2D.Ellipse(center, radius + 3f, radius + 3f), color, 2.5f);
            RenderTarget.FillEllipse(new D2D.Ellipse(center, radius - 1f, radius - 1f), color);

            if (fill)
            {
                // The burst and the arrow are reserved for confirmed executions.
                for (int i = 0; i < 8; i++)
                {
                    double angle = i * Math.PI / 4;
                    float dx = (float)Math.Cos(angle);
                    float dy = (float)Math.Sin(angle);
                    var start = new SharpDX.Vector2(x + dx * (radius + 7f), y + dy * (radius + 7f));
                    var end = new SharpDX.Vector2(x + dx * (radius + 13f), y + dy * (radius + 13f));
                    RenderTarget.DrawLine(start, end, ink, 6f);
                    RenderTarget.DrawLine(start, end, color, 3f);
                }
            }
            DrawCardLine(label, x - radius, y - radius, 2f * radius, 2f * radius, text, ink);
        }

        private void DrawFillMark(SetupPoint fill, bool current, ChartControl chart, ChartScale scale,
            D2D.Brush color, D2D.Brush ink, DWrite.TextFormat text)
        {
            DrawSetupBadge(new SetupPoint(fill.Bar, fill.Price, -fill.Side, fill.Session),
                fill.Side > 0 ? "▲" : "▼", 62f, current ? 25f : 14f, current, chart, scale, color, ink, text);
        }

        private void RenderStatusCard()
        {
            if (RenderTarget == null || ChartPanel == null || ChartPanel.W < 310f)
                return;
            StatusCard card;
            lock (sync)
                card = statusCard;
            if (card == null)
                return;

            const float designWidth = 720f;
            float width = Math.Min(designWidth, ChartPanel.W - 18f);
            float scale = width / designWidth;
            string[] levels = (card.Levels ?? "").Split(new[] { '|' }, StringSplitOptions.RemoveEmptyEntries);
            bool hasDetail = !string.IsNullOrEmpty(card.Detail);
            float height = (224f + (hasDetail ? 32f : 0f) + (levels.Length > 0 ? 58f : 0f)) * scale;
            if (ChartPanel.H < height + 14f)
                return;
            float left = ChartPanel.X + (ChartPanel.W - width) / 2f;
            float top = ChartPanel.Y + 10f;
            float x = left + 20f * scale;
            const float inner = 680f;

            using (var surface = new D2D.SolidColorBrush(RenderTarget, Pigment(19, 29, 46, .97f)))
            using (var frame = new D2D.SolidColorBrush(RenderTarget, Pigment(54, 74, 102)))
            using (var tile = new D2D.SolidColorBrush(RenderTarget, Pigment(28, 42, 64)))
            using (var status = new D2D.SolidColorBrush(RenderTarget, card.Accent))
            using (var foreground = new D2D.SolidColorBrush(RenderTarget, Pigment(239, 245, 255)))
            using (var muted = new D2D.SolidColorBrush(RenderTarget, Pigment(169, 186, 211)))
            using (var cyan = new D2D.SolidColorBrush(RenderTarget, Pigment(86, 228, 255)))
            using (var violet = new D2D.SolidColorBrush(RenderTarget, Pigment(204, 164, 255)))
            using (var gold = new D2D.SolidColorBrush(RenderTarget, Pigment(255, 214, 97)))
            using (var ink = new D2D.SolidColorBrush(RenderTarget, Pigment(11, 19, 33)))
            using (var title = new DWrite.TextFormat(Core.Globals.DirectWriteFactory, "Segoe UI Semibold", 26f * scale))
            using (var timer = new DWrite.TextFormat(Core.Globals.DirectWriteFactory, "Segoe UI Semibold", 32f * scale))
            using (var value = new DWrite.TextFormat(Core.Globals.DirectWriteFactory, "Segoe UI Semibold", 21f * scale))
            using (var label = new DWrite.TextFormat(Core.Globals.DirectWriteFactory, "Segoe UI", 17f * scale))
            using (var right = new DWrite.TextFormat(Core.Globals.DirectWriteFactory, "Segoe UI Semibold", 21f * scale))
            using (var stepNumber = new DWrite.TextFormat(Core.Globals.DirectWriteFactory, "Segoe UI Semibold", 17f * scale))
            {
                title.WordWrapping = timer.WordWrapping = value.WordWrapping = label.WordWrapping = DWrite.WordWrapping.NoWrap;
                right.TextAlignment = DWrite.TextAlignment.Trailing;
                right.WordWrapping = DWrite.WordWrapping.NoWrap;
                stepNumber.TextAlignment = DWrite.TextAlignment.Center;
                stepNumber.ParagraphAlignment = DWrite.ParagraphAlignment.Center;
                stepNumber.WordWrapping = DWrite.WordWrapping.NoWrap;

                RenderTarget.FillRectangle(new SharpDX.RectangleF(left, top, width, height), surface);
                RenderTarget.DrawRectangle(new SharpDX.RectangleF(left, top, width, height), frame, 1f);
                DrawCardLine("104-C28.03 · Funded SIM", x, top + 15f * scale, 485f * scale, 38f * scale, title, foreground);
                DrawCardLine("CHICAGO", x + 485f * scale, top + 7f * scale, 195f * scale, 22f * scale, right, muted);
                DrawCardLine(card.Clock, x + 485f * scale, top + 29f * scale, 195f * scale, 29f * scale, right, foreground);

                float statusY = top + 67f * scale;
                RenderTarget.FillRectangle(new SharpDX.RectangleF(x, statusY, inner * scale, 72f * scale), tile);
                string[] state = card.State.Split(new[] { "  ·  " }, 2, StringSplitOptions.None);
                float stateY = statusY + (state.Length == 1 ? 32f : 24f) * scale;
                DrawStatusLed(x + 17f * scale, stateY + 14f * scale, scale, card.Accent, status);
                DrawCardLine("SITZUNG", x + 12f * scale, statusY + 6f * scale, 338f * scale, 24f * scale, label, muted);
                DrawCardLine(state[0], x + 30f * scale, stateY,
                    309f * scale, 28f * scale, value, foreground);
                if (state.Length > 1)
                    DrawCardLine(state[1], x + 30f * scale, statusY + 48f * scale, 309f * scale, 22f * scale, label, muted);
                DrawCardTimer("HANDELSFRIST IN", card.MarketRemaining, x + 360f * scale, statusY, 182f * scale,
                    scale, label, timer, cyan, muted);
                DrawCardTimer("KERZE ENDET IN", card.Countdown, x + 538f * scale, statusY, 142f * scale,
                    scale, label, timer, foreground, muted);

                float stepY = top + 148f * scale;
                float stepWidth = inner / 3f * scale;
                DrawSetupStep("1", "Keltnerband", card.FirstBand, card.FirstBandSide, x, stepY, stepWidth, scale,
                    label, value, stepNumber, cyan, foreground, muted, ink, tile);
                DrawSetupStep("2", "Gegenband", card.OppositeBand, card.OppositeBandSide, x + stepWidth, stepY, stepWidth, scale,
                    label, value, stepNumber, violet, foreground, muted, ink, tile);
                DrawSetupStep("3", "Rücklauf", card.Retrace, 0, x + 2f * stepWidth, stepY, stepWidth, scale,
                    label, value, stepNumber, gold, foreground, muted, ink, tile);

                float row = top + 224f * scale;
                if (hasDetail)
                {
                    DrawCardLine(card.Detail, x, row, inner * scale, 28f * scale, value, foreground);
                    row += 32f * scale;
                }
                for (int i = 0; i < levels.Length; ++i)
                {
                    string level = levels[i].Trim();
                    int separator = level.IndexOf(' ');
                    float column = x + i * stepWidth;
                    DrawCardLine(level.Substring(0, separator), column, row, stepWidth, 25f * scale, label, muted);
                    DrawCardLine(level.Substring(separator + 1), column, row + 23f * scale, stepWidth, 29f * scale, value, foreground);
                }
            }
        }

        private void DrawStatusLed(float x, float y, float scale, SharpDX.Color4 color, D2D.Brush light)
        {
            var center = new SharpDX.Vector2(x, y);
            using (var halo = new D2D.SolidColorBrush(RenderTarget,
                new SharpDX.Color4(color.Red, color.Green, color.Blue, .18f)))
            using (var rim = new D2D.SolidColorBrush(RenderTarget, Pigment(7, 15, 27)))
            using (var shine = new D2D.SolidColorBrush(RenderTarget, Pigment(255, 255, 255, .82f)))
            {
                RenderTarget.FillEllipse(new D2D.Ellipse(center, 10f * scale, 10f * scale), halo);
                RenderTarget.DrawEllipse(new D2D.Ellipse(center, 7.5f * scale, 7.5f * scale), halo, 1.5f * scale);
                RenderTarget.FillEllipse(new D2D.Ellipse(center, 6.4f * scale, 6.4f * scale), rim);
                RenderTarget.FillEllipse(new D2D.Ellipse(center, 5.3f * scale, 5.3f * scale), light);
                RenderTarget.FillEllipse(new D2D.Ellipse(new SharpDX.Vector2(x - 1.7f * scale, y - 1.7f * scale),
                    1.5f * scale, 1.5f * scale), shine);
            }
        }

        private void DrawCardTimer(string name, string time, float x, float y, float width, float scale,
            DWrite.TextFormat label, DWrite.TextFormat value, D2D.Brush highlight, D2D.Brush muted)
        {
            DrawCardLine(name, x, y + 6f * scale, width, 24f * scale, label, muted);
            DrawCardLine(time ?? "—", x, y + 25f * scale, width, 43f * scale, value,
                time == null || time == "—" ? muted : highlight);
        }

        private void DrawSetupStep(string step, string name, string price, int bandSide, float x, float y, float width,
            float scale, DWrite.TextFormat label, DWrite.TextFormat value, DWrite.TextFormat number,
            D2D.Brush accent, D2D.Brush text, D2D.Brush muted, D2D.Brush ink, D2D.Brush tile)
        {
            bool reached = price != null;
            bool previous = reached && price.EndsWith(" (Vorsitzung)", StringComparison.Ordinal);
            var center = new SharpDX.Vector2(x + 17f * scale, y + 19f * scale);
            RenderTarget.FillEllipse(new D2D.Ellipse(center, 14f * scale, 14f * scale), reached ? accent : tile);
            DrawCardLine(step, x + 3f * scale, y + 5f * scale, 28f * scale, 28f * scale, number, reached ? ink : muted);
            float textX = x + 41f * scale;
            float textWidth = width - 46f * scale;
            DrawCardLine(name, textX, y + 4f * scale, textWidth, 24f * scale, label, reached ? accent : muted);
            DrawCardLine(previous ? price.Substring(0, price.Length - " (Vorsitzung)".Length) : price ?? "Ausstehend",
                textX, y + 24f * scale, textWidth, 28f * scale, value, reached ? text : muted);
            string side = bandSide > 0 ? "↑ Oben" : bandSide < 0 ? "↓ Unten" : null;
            if (previous)
                side = side == null ? "Vorsitzung" : side + " · Vorsitzung";
            if (reached)
                DrawCardLine(side, textX, y + 49f * scale, textWidth, 24f * scale, label, muted);
        }

        private void RenderBandLabels(ChartControl chartControl, ChartScale scale)
        {
            if (ChartBars == null || ChartPanel == null || ChartPanel.H < 125 || ChartPanel.W < 200
                || RenderTarget == null || Values == null || Values.Length != 5)
                return;
            int last = Math.Min(ChartBars.ToIndex, Values[1].Count - 1);
            int visibleLast = last;
            int earliest = Math.Max(ChartBars.FromIndex, visibleLast - 180);
            while (last >= earliest && !Values[1].IsValidDataPointAt(last))
                last--;
            if (last < earliest || last < 0)
                return;

            const float labelWidth = 214f;
            const float gap = 30f;
            float panelTop = ChartPanel.Y + 12f;
            float panelBottom = ChartPanel.Y + ChartPanel.H - 12f;
            float barX = chartControl.GetXByBarIndex(ChartBars, last);
            float right = ChartPanel.X + ChartPanel.W - 7f;
            float x = right - labelWidth;
            float newest = chartControl.GetXByBarIndex(ChartBars, visibleLast);
            if (x <= newest + Math.Max(8f, (float)chartControl.BarWidth + 4f))
                return;
            double[] prices = { Values[2].GetValueAt(last), Values[3].GetValueAt(last),
                Values[0].GetValueAt(last), Values[1].GetValueAt(last), Values[4].GetValueAt(last) };
            string marker = last == visibleLast ? "" : "*";
            string[] names = { "Keltner oben" + marker, "Keltner unten" + marker, "Bollinger oben" + marker,
                "Bollinger unten" + marker, "EMA20" + marker };
            var visible = new List<int>();
            float[] anchors = new float[5];
            for (int i = 0; i < prices.Length; i++)
            {
                anchors[i] = scale.GetYByValue(prices[i]);
                if (anchors[i] >= ChartPanel.Y && anchors[i] <= ChartPanel.Y + ChartPanel.H)
                    visible.Add(i);
            }
            visible.Sort((a, b) => anchors[a].CompareTo(anchors[b]));
            float[] positions = new float[visible.Count];
            for (int i = 0; i < visible.Count; i++)
                positions[i] = Math.Max(i == 0 ? panelTop : positions[i - 1] + gap, anchors[visible[i]]);
            for (int i = visible.Count - 1; i >= 0; i--)
                positions[i] = Math.Min(positions[i], i == visible.Count - 1 ? panelBottom : positions[i + 1] - gap);

            using (var labelSurface = new D2D.SolidColorBrush(RenderTarget, Pigment(16, 23, 37)))
            using (var labelFrame = new D2D.SolidColorBrush(RenderTarget, Pigment(50, 64, 87)))
            using (var labelInk = new D2D.SolidColorBrush(RenderTarget, Pigment(237, 242, 252)))
            using (var keltner = new D2D.SolidColorBrush(RenderTarget, Pigment(94, 143, 138)))
            using (var bollinger = new D2D.SolidColorBrush(RenderTarget, Pigment(112, 136, 191)))
            using (var ema = new D2D.SolidColorBrush(RenderTarget, Pigment(232, 182, 107)))
            using (var font = new DWrite.TextFormat(Core.Globals.DirectWriteFactory, "Segoe UI Semibold", 18f))
            {
                for (int i = 0; i < visible.Count; i++)
                {
                    int index = visible[i];
                    float y = positions[i];
                    var accent = index < 2 ? keltner : index < 4 ? bollinger : ema;
                    float edge = barX <= x ? x : x + labelWidth;
                    RenderTarget.DrawLine(new SharpDX.Vector2(barX, anchors[index]),
                        new SharpDX.Vector2(edge, y), accent, 1f);
                    string label = string.Format(CultureInfo.CurrentCulture, "{0}  {1:F2}", names[index], prices[index]);
                    using (var layout = new DWrite.TextLayout(Core.Globals.DirectWriteFactory, label, font, labelWidth - 12f, 26f))
                    {
                        float width = Math.Min(labelWidth, layout.Metrics.Width + 12f);
                        RenderTarget.FillRectangle(new SharpDX.RectangleF(x, y - 12f, width, 26f), labelFrame);
                        RenderTarget.FillRectangle(new SharpDX.RectangleF(x + 1f, y - 11f, width - 2f, 24f), labelSurface);
                        RenderTarget.FillRectangle(new SharpDX.RectangleF(x, y - 12f, 3f, 26f), accent);
                        RenderTarget.DrawTextLayout(new SharpDX.Vector2(x + 6f, y - 10f), layout, labelInk, D2D.DrawTextOptions.Clip);
                    }
                }
            }
        }

        private void DrawCardLine(string text, float x, float y, float width, float height, DWrite.TextFormat format,
            D2D.Brush brush)
        {
            if (string.IsNullOrEmpty(text) || width <= 0f)
                return;
            using (var layout = new DWrite.TextLayout(Core.Globals.DirectWriteFactory, text, format, width, height))
                RenderTarget.DrawTextLayout(new SharpDX.Vector2(x, y), layout, brush, D2D.DrawTextOptions.Clip);
        }

        private void FillBand(ChartControl chartControl, ChartScale chartScale, int first, int last,
            Series<double> upper, Series<double> lower, SharpDX.Color4 color)
        {
            using (var path = new D2D.PathGeometry(Core.Globals.D2DFactory))
            using (var brush = new D2D.SolidColorBrush(RenderTarget, color))
            {
                using (var sink = path.Open())
                {
                    sink.BeginFigure(new SharpDX.Vector2(chartControl.GetXByBarIndex(ChartBars, first),
                        chartScale.GetYByValue(upper.GetValueAt(first))), D2D.FigureBegin.Filled);
                    for (int index = first + 1; index <= last; index++)
                        sink.AddLine(new SharpDX.Vector2(chartControl.GetXByBarIndex(ChartBars, index),
                            chartScale.GetYByValue(upper.GetValueAt(index))));
                    for (int index = last; index >= first; index--)
                        sink.AddLine(new SharpDX.Vector2(chartControl.GetXByBarIndex(ChartBars, index),
                            chartScale.GetYByValue(lower.GetValueAt(index))));
                    sink.EndFigure(D2D.FigureEnd.Closed);
                    sink.Close();
                }
                RenderTarget.FillGeometry(path, brush);
            }
        }

        // Independent readiness verification. It never alters indicators or setup state.
        private void VerifyCalendarContinuity(DateTime previousTemplateEnd, DateTime nextTemplateBegin)
        {
            if (previousTemplateEnd == default(DateTime) || nextTemplateBegin <= previousTemplateEnd)
                return;
            DateTime cursor = previousTemplateEnd;
            DateTime query = default(DateTime), diagnosticBegin = default(DateTime), diagnosticEnd = default(DateTime);
            DateTime diagnosticTradingDay = default(DateTime);
            string diagnosticStage = "initialize";
            string diagnosticPrevious = "not captured", diagnosticRaw = "not returned";
            int diagnosticIteration = -1;
            try
            {
                DateTime targetEnd = templateEnd;
                DateTime targetTradingDay = sessionIterator.ActualTradingDayExchange.Date;
                for (int count = 0; count < 512; ++count)
                {
                    diagnosticIteration = count;
                    diagnosticStage = "convert cursor+1tick ET to platform";
                    query = TimeZoneInfo.ConvertTime(DateTime.SpecifyKind(cursor.AddTicks(1),
                        DateTimeKind.Unspecified), easternZone, platformZone);
                    diagnosticStage = "GetNextSession(query,false)";
                    try
                    {
                        DateTime oldBegin = integrityCalendar.ActualSessionBegin, oldEnd = integrityCalendar.ActualSessionEnd;
                        diagnosticPrevious = oldBegin.ToString("O", CultureInfo.InvariantCulture) + " kind=" + oldBegin.Kind
                            + " ticks=" + oldBegin.Ticks + " / " + oldEnd.ToString("O", CultureInfo.InvariantCulture)
                            + " kind=" + oldEnd.Kind + " ticks=" + oldEnd.Ticks;
                    }
                    catch (Exception snapshotError) { diagnosticPrevious = "unavailable: " + snapshotError.GetType().Name; }
                    bool returned = integrityCalendar.GetNextSession(query, false);
                    diagnosticStage = "read candidate after GetNextSession returned " + returned;
                    DateTime rawBegin = integrityCalendar.ActualSessionBegin, rawEnd = integrityCalendar.ActualSessionEnd;
                    DateTime tradingDay = integrityCalendar.ActualTradingDayExchange;
                    diagnosticRaw = rawBegin.ToString("O", CultureInfo.InvariantCulture) + " kind=" + rawBegin.Kind
                        + " ticks=" + rawBegin.Ticks + " / " + rawEnd.ToString("O", CultureInfo.InvariantCulture)
                        + " kind=" + rawEnd.Kind + " ticks=" + rawEnd.Ticks;
                    diagnosticTradingDay = tradingDay;
                    diagnosticStage = "validate candidate dates and forward progress";
                    if (rawBegin.Year < 1900 || rawEnd.Year < 1900 || tradingDay.Year < 1900 || rawEnd <= rawBegin)
                        throw new InvalidOperationException("Kalender liefert leere oder ungültige Sitzungsgrenzen");
                    DateTime begin = PlatformToEastern(rawBegin), end = PlatformToEastern(rawEnd);
                    diagnosticBegin = begin;
                    diagnosticEnd = end;
                    if (end <= begin || end <= cursor || begin < cursor)
                        throw new InvalidOperationException("Trading-Hours-Kalender schreitet nicht voran");
                    if (begin > nextTemplateBegin)
                        throw new InvalidOperationException("Trading-Hours-Kalender überspringt die erwartete Zielsitzung");

                    // Native NT8 can populate correct next bounds while returning false
                    // for a maintenance-gap query. Never accept false on its own: confirm
                    // strictly inside the candidate and require true plus identical bounds.
                    if (!returned)
                    {
                        diagnosticStage = "confirm candidate from strictly interior timestamp";
                        long duration = (rawEnd - rawBegin).Ticks;
                        long offset = Math.Min(TimeSpan.TicksPerSecond, duration / 2);
                        if (offset <= 0 || offset >= duration)
                            throw new InvalidOperationException("Kalendersitzung hat keinen inneren Bestätigungszeitpunkt");
                        DateTime confirmationQuery = rawBegin.AddTicks(offset);
                        diagnosticStage += " query_PLATFORM=" + confirmationQuery.ToString("O", CultureInfo.InvariantCulture);
                        bool confirmed = integrityCalendar.GetNextSession(confirmationQuery, false);
                        if (!confirmed
                            || integrityCalendar.ActualSessionBegin != rawBegin || integrityCalendar.ActualSessionBegin.Kind != rawBegin.Kind
                            || integrityCalendar.ActualSessionEnd != rawEnd || integrityCalendar.ActualSessionEnd.Kind != rawEnd.Kind
                            || integrityCalendar.ActualTradingDayExchange != tradingDay
                            || integrityCalendar.ActualTradingDayExchange.Kind != tradingDay.Kind)
                            throw new InvalidOperationException("Kalenderkandidat im Sitzungsinneren nicht identisch bestätigt");
                        AuditIntegrity("CALENDAR_CONFIRMED", lastMarketTime,
                            "gapQueryReturned=False confirmation=True query_PLATFORM="
                            + confirmationQuery.ToString("O", CultureInfo.InvariantCulture)
                            + " begin_ET=" + AuditDate(begin) + " end_ET=" + AuditDate(end)
                            + " tradingDay=" + AuditDate(tradingDay), double.NaN);
                    }
                    diagnosticStage = "match main iterator target bounds and trading day";
                    if (begin == nextTemplateBegin)
                    {
                        if (end != targetEnd || tradingDay.Date != targetTradingDay)
                            throw new InvalidOperationException("Kalenderziel stimmt nicht mit Hauptiterator-Ende/Handelstag überein");
                        return;
                    }
                    diagnosticStage = "evaluate missing session overlap";
                    DateTime day = tradingDay.Date;
                    DateTime open = day.AddHours(9).AddMinutes(30);
                    if (begin > open)
                        open = begin;
                    DateTime regularEnd = day.AddHours(17);
                    DateTime close = end < regularEnd ? end : regularEnd;
                    if (close > open)
                        InvalidateIntegrity(day, "Erwartete Sitzung ohne beobachtete Tickabdeckung");
                    cursor = end;
                }
                throw new InvalidOperationException("Trading-Hours-Kalendergrenze von 512 Sitzungen erreicht");
            }
            catch (Exception error)
            {
                integrityCalendarFailed = true;
                integrityFailure = "Kalenderprüfung fehlgeschlagen: " + error.GetType().Name;
                string diagnostic = integrityFailure + ": " + error.Message
                    + " | stage=" + diagnosticStage + " iteration=" + diagnosticIteration
                    + " previousTemplateEnd_ET=" + AuditDate(previousTemplateEnd)
                    + " nextTemplateBegin_ET=" + AuditDate(nextTemplateBegin)
                    + " cursor_ET=" + AuditDate(cursor) + " query_PLATFORM=" + AuditDate(query)
                    + " actualBegin_ET=" + AuditDate(diagnosticBegin) + " actualEnd_ET=" + AuditDate(diagnosticEnd)
                    + " actualTradingDay=" + AuditDate(diagnosticTradingDay)
                    + " queryKind=" + query.Kind + " queryTicks=" + query.Ticks
                    + " previousIterator_PLATFORM=" + diagnosticPrevious + " returnedIterator_PLATFORM=" + diagnosticRaw
                    + " ETzone=" + easternZone.Id + " platformZone=" + platformZone.Id;
                AuditIntegrity("CALENDAR_FAILURE", lastMarketTime, diagnostic, double.NaN);
                if (!integrityBoundaryProbed && !integrityAuditFailed)
                {
                    integrityBoundaryProbed = true;
                    ProbeCalendarBoundary(cursor, nextTemplateBegin);
                }
                Print("HY HISTORIE: " + integrityFailure + ". Neue Einstiege gesperrt; Ausstiege bleiben aktiv.");
            }
        }

        private void InvalidateIntegrity(DateTime day, string reason)
        {
            verifiedCompleteSessions = 0;
            integritySeedBegin = default(DateTime);
            lastUncoveredSession = day.Date;
            lastCoverageReason = reason;
            AuditIntegrity("HISTORY_UNCOVERED", lastMarketTime,
                day.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture) + " " + reason, double.NaN);
            if (positionSide != 0)
                Print("HY ALARM: Historienabdeckung unvollständig bei offener Position. "
                    + "Indikatorziel möglicherweise abweichend; vorhandene Ausstiegslogik bleibt aktiv. "
                    + day.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture) + " " + reason);
        }

        private void CompleteIntegritySession(int expected)
        {
            bool complete = sessionComplete && expected > 0 && committedBars == expected;
            if (complete)
            {
                if (verifiedCompleteSessions == 0)
                    integritySeedBegin = sessionOpen;
                verifiedCompleteSessions++;
            }
            else
                InvalidateIntegrity(sessionOpen.Date, "Sitzung mit unvollständiger Tickabdeckung "
                    + committedBars + "/" + expected + " Abschnitte");
            AuditIntegrity("SESSION_END", lastMarketTime, complete ? "vollständig" : "unvollständig", double.NaN);
        }

        private string IntegrityGateReason()
        {
            if (integrityAuditFailed)
                return "Diagnose nicht schreibbar · neue Einstiege gesperrt";
            if (integrityCalendarFailed)
                return "Kalenderprüfung fehlgeschlagen · neu laden und Log prüfen";
            if (verifiedCompleteSessions < WarmupSessions)
                return "Historie " + verifiedCompleteSessions + "/" + WarmupSessions + " vollständige Folgesitzungen"
                    + (lastUncoveredSession == default(DateTime) ? "" : " · ohne Abdeckung "
                        + lastUncoveredSession.ToString("dd.MM.", CultureInfo.InvariantCulture));
            if (!sessionComplete)
                return "Aktuelle Sitzung ohne lückenlose Tickabdeckung";
            if (!sessionSeenTrade)
                return "Aktuelle Sitzung noch ohne Last-Tick";
            return null;
        }

        private string IntegrityLegend()
        {
            string reason = IntegrityGateReason();
            if (reason != null)
                return reason;
            return null;
        }

        private string EntryAuditReason(DateTime time, bool realtime)
        {
            string integrity = IntegrityGateReason();
            if (integrity != null)
                return integrity;
            string news = NewsEntryGateReason(time);
            if (news != null)
                return news;
            if (!realtime)
                return "historischer Rücklauf · keine Echtzeitorder";
            if (!AccountReplayReady() && IsOrderAccount())
                return AccountReplayStatus();
            if (modelLossLatched)
                return "Sim-Verlustgrenze erreicht";
            if (entryBlocked)
                return "Einstiege nach Orderfehler gesperrt";
            if (!sessionComplete)
                return "Aktuelle Sitzung unvollständig";
            if (completeSessions < WarmupSessions)
                return "Bestehender Warmlauf " + completeSessions + "/" + WarmupSessions;
            if (time < sessionOpen.AddMinutes(0))
                return "Vor dem erlaubten Eintrittsfenster";
            if (time >= flattenAt)
                return "Nach Eintrittsschluss / Glattstellungsfrist";
            if (liveClock && !MarketTimeAgrees(time, lastTradeClock))
                return "Marktzeit/Steueruhr außerhalb Toleranz";
            if (positionSide != 0)
                return "Position bereits offen";
            if (pending != null || submitted != null)
                return "Order bereits aktiv";
            return "Eintrittsprüfung freigegeben · Stop/Quote/Frist folgt";
        }

        // Operational parity with frozen SQX allowsEntry/advanceNews. Local SIM accounts only.
        private const string NewsModel = "ES_RAPID_FUNDED";
        private HYNewsCalendarV5 newsCalendar;
        private string newsCalendarLoadError = "NEWS-KALENDER FEHLT";
        private DateTime newsCalendarReloadAt, newsLastAdvanceUtc;
        private bool newsViolation;
        private Intent newsNoQuoteExitIntent;
        private Intent newsEscalatedOlderExit;
        private HYNewsCalendarV5.Window newsOlderExitWindow;
        private string newsOlderExitCalendarSha;
        private DateTime newsLateWindowBeginUtc;
        private bool newsPositionMismatchLogged;
        private readonly HashSet<Intent> intentApiSendStarted = new HashSet<Intent>();
        private readonly HashSet<Intent> intentExecutionCompleted = new HashSet<Intent>();
        private readonly HashSet<Intent> intentExecutionInvalid = new HashSet<Intent>();
        private readonly Dictionary<Intent, long> intentTradeClaims = new Dictionary<Intent, long>();
        private long nextOwnedTradeId, activeOwnedTradeId;
        private long nextOrderReferenceId;
        private readonly Dictionary<Order, long> orderReferenceIds = new Dictionary<Order, long>(new OrderReferenceComparer());
        private string newsViolationReason;
        private readonly Dictionary<Order, Intent> newsOwnedIntents = new Dictionary<Order, Intent>(new OrderReferenceComparer());
        private readonly HashSet<Order> newsCancelRequested = new HashSet<Order>(new OrderReferenceComparer());
        private readonly Dictionary<Order, int> newsOrderMaxFilled = new Dictionary<Order, int>(new OrderReferenceComparer());
        private readonly HashSet<string> newsSeenExecutionIds = new HashSet<string>();

        private sealed class OrderReferenceComparer : IEqualityComparer<Order>
        {
            public bool Equals(Order first, Order second) { return object.ReferenceEquals(first, second); }
            public int GetHashCode(Order order) { return System.Runtime.CompilerServices.RuntimeHelpers.GetHashCode(order); }
        }

        private long OrderReferenceId(Order order)
        {
            if (order == null) return 0;
            long id;
            if (!orderReferenceIds.TryGetValue(order, out id))
            {
                id = ++nextOrderReferenceId;
                orderReferenceIds.Add(order, id);
            }
            return id;
        }

        private Intent NewsOrderIntent(Order order)
        {
            Intent owner;
            return IsOwnNewsOrder(order) && newsOwnedIntents.TryGetValue(order, out owner) ? owner : null;
        }

        private DateTime NewsControlNow()
        {
            return liveClock || lastMarketTime == default(DateTime) ? EasternNow() : lastMarketTime;
        }

        private void InitializeNewsCalendar()
        {
            newsCalendarReloadAt = default(DateTime);
            EnsureNewsCalendar(EasternNow());
        }

        private void EnsureNewsCalendar(DateTime time)
        {
            if (newsCalendarReloadAt != default(DateTime) && time < newsCalendarReloadAt)
                return;
            newsCalendarReloadAt = time.AddMinutes(1);
            string path = System.IO.Path.Combine(NinjaTrader.Core.Globals.UserDataDir,
                "templates", "HY", "HYNewsCalendarV5.xml");
            try
            {
                var loaded = HYNewsCalendarV5.Load(path, easternZone);
                bool changed = newsCalendar == null || loaded.CsvSha256 != newsCalendar.CsvSha256
                    || loaded.VerifiedAtUtc != newsCalendar.VerifiedAtUtc || newsCalendarLoadError != null;
                newsCalendar = loaded;
                newsCalendarLoadError = null;
                if (changed)
                    AuditIntegrity("NEWS_CALENDAR_LOADED", time,
                        "scope=frozen_named_t1_only sha256=" + loaded.CsvSha256
                        + " verified=" + loaded.VerifiedAtUtc.ToString("O", CultureInfo.InvariantCulture)
                        + " expires=" + loaded.ExpiresAtUtc.ToString("O", CultureInfo.InvariantCulture), double.NaN);
            }
            catch (Exception error)
            {
                // Retain an older valid snapshot only for exit scheduling. Never use it to clear this entry block.
                string reason = "NEWS-KALENDER FEHLT/UNGÜLTIG · " + error.GetType().Name;
                if (newsCalendarLoadError != reason)
                    AuditIntegrity("NEWS_CALENDAR_INVALID", time, reason + " " + error.Message, double.NaN);
                newsCalendarLoadError = reason;
            }
        }

        private string NewsEntryGateReason(DateTime time)
        {
            if (newsViolation)
                return "NEWS-REGEL VERLETZT · Neue Einstiege gesperrt · Log prüfen";
            if (newsCalendarLoadError != null)
                return newsCalendarLoadError;
            return newsCalendar == null ? "NEWS-KALENDER FEHLT"
                : newsCalendar.GateReason(NewsModel, time, State == State.Realtime && liveClock);
        }

        private void LatchNewsViolation(DateTime time, string reason)
        {
            if (newsViolation)
                return;
            newsViolation = true;
            newsViolationReason = reason;
            AuditIntegrity("NEWS_VIOLATION", time, reason, double.NaN);
            Print("HY NEWS-REGEL VERLETZT: " + reason + ". Neue Einstiege gesperrt; Ausstiege bleiben aktiv.");
        }

        private bool IsOwnNewsOrder(Order order)
        {
            return order != null && order.Account == Account && order.Instrument == Instrument
                && newsOwnedIntents.ContainsKey(order);
        }

        private void TrackOwnNewsOrder(Order order)
        {
            if (order == null || order.Account != Account || order.Instrument != Instrument)
                return;
            // Never rebind a known order to a newer intent, even when OrderName is the same.
            if (newsOwnedIntents.ContainsKey(order))
                return;
            if (submitted == null || !intentApiSendStarted.Contains(submitted)
                || intentExecutionCompleted.Contains(submitted) || intentExecutionInvalid.Contains(submitted)
                || order.Name != submitted.OrderName)
                return;
            // NT may invoke this callback synchronously inside Enter/Exit before the API returns its Order.
            // The own API attempt has already been reserved; only this first association uses the name.
            foreach (var known in newsOwnedIntents)
                if (object.ReferenceEquals(known.Value, submitted))
                    return; // One API attempt owns one exact Order object; a same-name copy is not its owner.
            newsOwnedIntents.Add(order, submitted);
            AuditIntegrity("ORDER_INTENT_BOUND", NewsControlNow(),
                "orderId=" + order.OrderId + " orderRef=" + OrderReferenceId(order) + " ownerReason=" + submitted.Reason
                + " reservedAPI=true;exactOrderReference=true", double.NaN);
        }

        private bool HandleNewsOrderUpdate(Order order, int quantity, int filled, OrderState state, ErrorCode error, DateTime time)
        {
            if (!IsOrderAccount())
                return false;
            TrackOwnNewsOrder(order);
            Intent owner = NewsOrderIntent(order);
            if (owner == null)
            {
                if (order != null && order.Account == Account && order.Instrument == Instrument)
                {
                    LatchNewsViolation(time, "UNKNOWN ORDER CALLBACK OWNERSHIP · keine Zuordnung nur nach Name");
                    AuditIntegrity("ORDER_UPDATE_WITHOUT_INTENT_CLAIM", time,
                        "state=" + state + " orderId=" + order.OrderId + ";current reservation unchanged", double.NaN);
                }
                return true;
            }
            if (!object.ReferenceEquals(owner, submitted))
            {
                // Archive the retired owner's callback. It must never fail/clear a newer same-name intent.
                AuditIntegrity("ORDER_UPDATE_PRIOR_INTENT", time,
                    "state=" + state + " orderId=" + order.OrderId + " ownerReason=" + owner.Reason
                    + " quantity=" + quantity + " filled=" + filled + ";current reservation unchanged", double.NaN);
                return true;
            }
            int previousFilled;
            newsOrderMaxFilled.TryGetValue(order, out previousFilled);
            if (quantity < 0 || quantity > 1 || (quantity != 1 && state != OrderState.Initialized)
                || filled < 0 || filled > quantity || filled < previousFilled
                || (state == OrderState.Filled && filled != quantity))
            {
                LatchNewsViolation(time, "ORDER QUANTITY/PROGRESS ANOMALY · tatsächliche Kontoposition prüfen");
                AuditIntegrity("ORDER_UPDATE_PROGRESS_ANOMALY", time,
                    "state=" + state + " quantity=" + quantity + " filled=" + filled
                    + " previousFilled=" + previousFilled + ";no inferred repair;current reservation retained", double.NaN);
                return true;
            }
            newsOrderMaxFilled[order] = filled;
            if (!newsCancelRequested.Contains(order))
                return false;
            if (error != ErrorCode.NoError)
                LatchNewsViolation(time, "Eigene Entry-Stornierung nicht bestätigt: " + error);
            if (state == OrderState.Cancelled && filled == 0)
            {
                if (object.ReferenceEquals(submitted, owner))
                    submitted = null;
                AuditIntegrity("NEWS_ENTRY_CANCELLED", time,
                    "orderId=" + order.OrderId + " quantityFilled=0", double.NaN);
                EnsureNewsViolationExit(time);
                return true;
            }
            return false;
        }

        private void RequestOwnNewsEntryCancel(DateTime time)
        {
            if (submitted == null || !submitted.IsEntry || !IsOrderAccount() || !OrderConnectionReady())
                return;
            Order owned = null;
            foreach (var pair in newsOwnedIntents)
                if (pair.Value == submitted && IsOwnNewsOrder(pair.Key)) { owned = pair.Key; break; }
            if (owned == null || newsCancelRequested.Contains(owned))
                return;
            if (owned.OrderState == OrderState.Cancelled || owned.OrderState == OrderState.Rejected
                || owned.OrderState == OrderState.Filled)
                return;
            // Order objects identify ownership. OrderId alone is not stable across an order's lifetime.
            newsCancelRequested.Add(owned);
            AuditIntegrity("NEWS_ENTRY_CANCEL_REQUEST", time,
                "orderId=" + owned.OrderId + " reason=t1_preclose", double.NaN);
            try { CancelOrder(owned); }
            catch (Exception error)
            { LatchNewsViolation(time, "Entry-Stornierung fehlgeschlagen: " + error.GetType().Name); }
        }

        private Intent NewsExecutionIntent(Execution execution)
        {
            return execution == null ? null : NewsOrderIntent(execution.Order);
        }

        private bool DuplicateNewsExecution(string executionId, DateTime time)
        {
            if (string.IsNullOrEmpty(executionId))
                return false;
            if (newsSeenExecutionIds.Add(executionId))
                return false;
            AuditIntegrity("NEWS_DUPLICATE_EXECUTION_IGNORED", time, "executionId=" + executionId, double.NaN);
            return true;
        }

        private void NewsExecutionQuantityAnomaly(Intent filled, int quantity, DateTime time)
        {
            intentExecutionInvalid.Add(filled);
            string actual = PositionAccount == null ? "unavailable" : PositionAccount.MarketPosition
                + " quantity=" + PositionAccount.Quantity.ToString(CultureInfo.InvariantCulture);
            LatchNewsViolation(time, "Unerwartete Ausführungsmenge " + quantity.ToString(CultureInfo.InvariantCulture)
                + "; tatsächliche Kontoposition prüfen");
            AuditIntegrity("NEWS_ACTUAL_POSITION_MISMATCH", time,
                "executionQuantity=" + quantity.ToString(CultureInfo.InvariantCulture)
                + " permittedQuantity=1 actual=" + actual
                + " action=no_unapproved_quantity_close;manual_position_check_required", double.NaN);
            // A cancelled intent can still receive a late callback. Latch independently of submitted.
            // Never turn an unexpected quantity into an invented model fill or an unapproved size-2 close.
            FailSubmission(filled, "Unexpected execution quantity " + quantity + ". Actual account position must be checked.");
        }

        private void AfterNewsExecution(Execution execution, Intent filled)
        {
            DateTime now = NewsControlNow();
            if (filled.IsEntry && execution != null && newsCancelRequested.Contains(execution.Order))
                LatchNewsViolation(now, "Entry-Ausführung während/nach angeforderter News-Stornierung");
            // Even when cancellation races a fill, the regular OnExecution path has now updated the actual strategy position.
            AdvanceNews(now);
            EnsureNewsViolationExit(now);
        }

        private void EnsureNewsViolationExit(DateTime time)
        {
            if (!newsViolation)
                return;
            if (pending != null && pending.IsEntry)
                pending = null;
            RequestOwnNewsEntryCancel(time);
            if (positionSide != 0 && !exitSubmissionFailed && pending == null && submitted == null)
                Queue(new Intent(false, positionSide, "t1_preclose", time, positionStop));
        }

        // Explicit operational SIM exception to the SQX quote gate: no invented quote or fill.
        private bool CanDispatchNewsNoQuoteMarketExit(DateTime time)
        {
            return IsNewsNoQuoteExit(pending)
                && submitted == null && time >= pending.Time.AddSeconds(2)
                && NewsNoQuotePositionAgrees(pending.Side);
        }

        private bool RejectUnavailableIntent(Intent intent, DateTime time)
        {
            lock (sync)
            {
                if (intentApiSendStarted.Contains(intent) || intentExecutionCompleted.Contains(intent))
                {
                    AuditIntegrity("INTENT_DUPLICATE_SEND_IGNORED", time,
                        "exact intent already sent/completed; independent of current news marker", double.NaN);
                    return true;
                }
                if (submitted != intent)
                {
                    AuditIntegrity("INTENT_STALE_SEND_IGNORED", time,
                        "exact intent does not own current submitted reservation", double.NaN);
                    return true;
                }
                return false;
            }
        }

        private bool ClaimCurrentTradeExit(Intent intent, DateTime time)
        {
            long claimed;
            if (activeOwnedTradeId == 0 || positionSide == 0 || positionSide != intent.Side
                || (intentTradeClaims.TryGetValue(intent, out claimed) && claimed != activeOwnedTradeId))
            {
                LatchNewsViolation(time, "EXIT TRADE OWNERSHIP MISMATCH · keine fremde/neue Position schließen");
                AuditIntegrity("INTENT_TRADE_CLAIM_REJECTED", time,
                    "activeTrade=" + activeOwnedTradeId + " side=" + intent.Side + " reason=" + intent.Reason, double.NaN);
                return false;
            }
            intentTradeClaims[intent] = activeOwnedTradeId;
            return true;
        }

        private bool AcceptIntentExecutionLifetime(Intent intent, DateTime time)
        {
            if (intentExecutionCompleted.Contains(intent) || intentExecutionInvalid.Contains(intent))
            {
                AuditIntegrity("INTENT_DUPLICATE_EXECUTION_IGNORED", time,
                    "exact intent already completed/invalid; no repeated fee, model fill or trade reset", double.NaN);
                return false;
            }
            if (intent.IsEntry)
            {
                if (positionSide != 0 || activeOwnedTradeId != 0)
                {
                    intentExecutionInvalid.Add(intent);
                    LatchNewsViolation(time, "ENTRY TRADE OWNERSHIP COLLISION · tatsächliche Kontoposition prüfen");
                    AuditIntegrity("INTENT_TRADE_EXECUTION_REJECTED", time, "another owned trade is already active", double.NaN);
                    return false;
                }
                activeOwnedTradeId = ++nextOwnedTradeId;
                intentTradeClaims[intent] = activeOwnedTradeId;
            }
            else
            {
                long claimed;
                if (!intentTradeClaims.TryGetValue(intent, out claimed) || activeOwnedTradeId == 0
                    || claimed != activeOwnedTradeId || positionSide != intent.Side)
                {
                    intentExecutionInvalid.Add(intent);
                    LatchNewsViolation(time, "LATE EXIT TRADE OWNERSHIP MISMATCH · keine neue Modellposition ändern");
                    AuditIntegrity("INTENT_TRADE_EXECUTION_REJECTED", time,
                        "stale/unclaimed exit callback; activeTrade=" + activeOwnedTradeId, double.NaN);
                    return false;
                }
                activeOwnedTradeId = 0;
            }
            intentExecutionCompleted.Add(intent);
            return true;
        }

        private bool IsNewsNoQuoteExit(Intent intent)
        {
            return intent != null && !intent.IsEntry
                && (intent.Reason == "t1_preclose" || object.ReferenceEquals(intent, newsEscalatedOlderExit));
        }

        private void AnnotateOlderNewsExit(HYNewsCalendarV5.Window window, DateTime lead, DateTime time)
        {
            if (positionSide == 0 || submitted != null || pending == null || pending.IsEntry
                || pending.Reason == "t1_preclose" || pending.Time > lead
                || object.ReferenceEquals(pending, newsEscalatedOlderExit))
                return;
            // Keep the original intent/reference, reason, signal time, side, stop and OrderName.
            newsEscalatedOlderExit = pending;
            newsOlderExitWindow = window;
            newsOlderExitCalendarSha = newsCalendar.CsvSha256;
            AuditIntegrity("NEWS_OLDER_EXIT_ARMED", time,
                "originalReason=" + pending.Reason + " originalTime=" + pending.Time.ToString("O", CultureInfo.InvariantCulture)
                + " windowBeginUtc=" + window.BeginUtc.ToString("O", CultureInfo.InvariantCulture)
                + " calendarSha256=" + newsOlderExitCalendarSha + " sameIntent=true;not_submitted", double.NaN);
        }

        private string NewsNoQuoteAuditDetail(Intent intent)
        {
            string context = object.ReferenceEquals(intent, newsEscalatedOlderExit) && newsOlderExitWindow != null
                ? " escalation=preexisting_exit windowBeginUtc=" + newsOlderExitWindow.BeginUtc.ToString("O", CultureInfo.InvariantCulture)
                    + " calendarSha256=" + newsOlderExitCalendarSha : " escalation=t1_preclose";
            return "stage=actual_market_order_request;reference=NaN;filled_only_by_execution_callback;local_SIM_only"
                + " originalReason=" + intent.Reason + " originalTime=" + intent.Time.ToString("O", CultureInfo.InvariantCulture)
                + context;
        }

        private bool HasUnknownActiveAccountOrder()
        {
            if (Account == null)
                return false;
            lock (Account.Orders)
                foreach (Order order in Account.Orders)
                    if (order != null && order.Instrument == Instrument && !IsOwnNewsOrder(order)
                        && order.OrderState != OrderState.Filled && order.OrderState != OrderState.Cancelled
                        && order.OrderState != OrderState.Rejected)
                        return true;
            return false;
        }

        private void CheckNewsPositionMismatch(DateTime time)
        {
            if (State != State.Realtime || !liveClock || !IsOrderAccount())
                return;
            // A known order's account/strategy updates can precede its execution callback.
            // No new dispatch is possible while submitted is occupied; deadline enforcement remains in AdvanceNews.
            if (submitted != null && intentApiSendStarted.Contains(submitted))
                return;
            if (submitted != null)
                foreach (var pair in newsOwnedIntents)
                    if (pair.Value == submitted && IsOwnNewsOrder(pair.Key))
                        return;
            if (HasUnknownActiveAccountOrder())
            {
                LatchNewsViolation(time, "UNKNOWN ACTIVE ORDER · keine neue Order; Kontozuordnung prüfen");
                if (!newsPositionMismatchLogged)
                {
                    newsPositionMismatchLogged = true;
                    AuditIntegrity("INTENT_UNKNOWN_ORDER_OWNERSHIP", time,
                        "active account/instrument order has no strategy intent claim;entry_block;no_cancel_or_adoption", double.NaN);
                }
                return;
            }
            MarketPosition expected = positionSide > 0 ? MarketPosition.Long : positionSide < 0 ? MarketPosition.Short : MarketPosition.Flat;
            int expectedQuantity = positionSide == 0 ? 0 : 1;
            bool agrees = Position != null && PositionAccount != null
                && Position.MarketPosition == expected && PositionAccount.MarketPosition == expected
                && Position.Quantity == expectedQuantity && PositionAccount.Quantity == expectedQuantity;
            if (agrees)
                return;
            LatchNewsViolation(time, "NEWS POSITION MISMATCH · tatsächliche Strategie-/Kontoposition prüfen");
            if (newsPositionMismatchLogged)
                return;
            newsPositionMismatchLogged = true;
            string strategy = Position == null ? "unavailable" : Position.MarketPosition + " quantity=" + Position.Quantity;
            string account = PositionAccount == null ? "unavailable" : PositionAccount.MarketPosition + " quantity=" + PositionAccount.Quantity;
            AuditIntegrity("NEWS_POSITION_MISMATCH", time,
                "modelSide=" + positionSide + " strategy=" + strategy + " account=" + account
                + " action=entry_block;no_position_adoption;no_unapproved_close", double.NaN);
        }

        private bool NewsNoQuotePositionAgrees(int side)
        {
            if (State != State.Realtime || !liveClock || !IsOrderAccount() || !OrderConnectionReady()
                || !MatchesSimulationAccount() || positionSide != side || positionSide == 0)
                return false;
            MarketPosition expected = side > 0 ? MarketPosition.Long : MarketPosition.Short;
            if (Position == null || PositionAccount == null || Position.MarketPosition != expected
                || PositionAccount.MarketPosition != expected || Position.Quantity != 1 || PositionAccount.Quantity != 1)
                return false;
            // Never race an in-flight own entry/cancel/exit, or another active account/instrument order.
            foreach (var pair in newsOwnedIntents)
                if (IsOwnNewsOrder(pair.Key) && pair.Key.OrderState != OrderState.Filled
                    && pair.Key.OrderState != OrderState.Cancelled && pair.Key.OrderState != OrderState.Rejected)
                    return false;
            return !HasWorkingOrder();
        }

        private void AdvanceNews(DateTime time)
        {
            if (newsCalendar == null)
                return;
            DateTime utc = newsCalendar.ToUtc(time);
            DateTime from = newsLastAdvanceUtc == default(DateTime) ? utc : newsLastAdvanceUtc;
            if (utc < from)
                return;
            newsLastAdvanceUtc = utc;
            foreach (var window in newsCalendar.CrossedOrActive(NewsModel, from, utc))
            {
                DateTime lead = TimeZoneInfo.ConvertTimeFromUtc(window.PrecloseUtc, easternZone);
                if (pending != null && pending.IsEntry)
                {
                    AuditIntegrity("NEWS_PENDING_ENTRY_DROPPED", time,
                        "reason=t1_preclose label=" + window.Label, double.NaN);
                    pending = null;
                }
                RequestOwnNewsEntryCancel(time);
                bool accountExposure = IsOrderAccount() && PositionAccount != null && PositionAccount.Quantity != 0;
                if (utc >= window.BeginUtc && (positionSide != 0 || pending != null || submitted != null || accountExposure))
                {
                    LatchNewsViolation(time, "Nicht rechtzeitig glatt für " + window.Label);
                    if (newsLateWindowBeginUtc != window.BeginUtc)
                    {
                        newsLateWindowBeginUtc = window.BeginUtc;
                        AuditIntegrity("NEWS_PRECLOSE_LATE", time,
                            "label=" + window.Label + " lateByMilliseconds="
                            + (utc - window.BeginUtc).TotalMilliseconds.ToString("R", CultureInfo.InvariantCulture)
                            + " windowBeginUtc=" + window.BeginUtc.ToString("O", CultureInfo.InvariantCulture)
                            + " actualFlatNotConfirmed=true", double.NaN);
                    }
                }
                AnnotateOlderNewsExit(window, lead, time);
                if (positionSide != 0 && !exitSubmissionFailed && submitted == null
                    && (pending == null || pending.Reason != "t1_preclose")
                    && (pending == null || pending.Time > lead))
                    Queue(new Intent(false, positionSide, "t1_preclose", time, positionStop));
            }
            EnsureNewsViolationExit(time);
        }


        private const string AuditDiagnosticVersion = "V8-ACCOUNT-REPLAY-20261119";

        private string AuditPhaseLabel()
        {
            return "Funded OR60";
        }

        private void AuditRuntimeMetadata(string reason)
        {
            AuditIntegrity("RUNTIME_METADATA", integrityLastEventTime,
                reason + " source=" + AuditDiagnosticVersion, double.NaN);
        }

        private void AuditOrderState(Order order, double limitPrice, double stopPrice, int quantity,
            int filled, double averageFillPrice, OrderState orderState, DateTime time, ErrorCode error, string comment)
        {
            try
            {
            string detail = "orderRef=" + OrderReferenceId(order) + " state=" + orderState + " orderId=" + (order?.OrderId ?? "")
                + " orderName=" + (order?.Name ?? "") + " quantity=" + quantity + " filled=" + filled
                + " limit=" + limitPrice.ToString("R", CultureInfo.InvariantCulture)
                + " stop=" + stopPrice.ToString("R", CultureInfo.InvariantCulture)
                + " reason=" + (NewsOrderIntent(order)?.Reason ?? "unclaimed") + " error=" + error
                + " comment=" + (comment ?? "");
            AuditIntegrity("ORDER_STATE", PlatformToEastern(time), detail, averageFillPrice);
            }
            catch (Exception auditError)
            {
                MarkIntegrityAuditFailure(auditError);
            }
        }

        private void AuditExecutionCallback(Execution execution, string executionId, double price, int quantity,
            MarketPosition marketPosition, string orderId, DateTime time)
        {
            try
            {
            string detail = "orderRef=" + OrderReferenceId(execution?.Order) + " executionId=" + (executionId ?? "") + " orderId=" + (orderId ?? "")
                + " orderName=" + (execution?.Order?.Name ?? "") + " quantity=" + quantity
                + " marketPosition=" + marketPosition + " reason=" + (NewsExecutionIntent(execution)?.Reason ?? "unclaimed");
            AuditIntegrity("EXECUTION_CALLBACK", PlatformToEastern(time), detail, price);
            }
            catch (Exception auditError)
            {
                MarkIntegrityAuditFailure(auditError);
            }
        }

        private void InitializeIntegrityAudit()
        {
            try
            {
                string folder = System.IO.Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "log", "HY-integrity");
                System.IO.Directory.CreateDirectory(folder);
                integrityAuditPath = System.IO.Path.Combine(folder, GetType().Name + "-"
                    + DateTime.UtcNow.ToString("yyyyMMdd-HHmmss", CultureInfo.InvariantCulture) + "-"
                    + Guid.NewGuid().ToString("N") + ".csv");
                integrityAudit = new System.IO.StreamWriter(integrityAuditPath, false, new System.Text.UTF8Encoding(true));
                integrityAudit.WriteLine("seq,logged_utc,event,event_et,market_event_et,control_et,session_open_et,session_end_et,seed_begin_et,verified_sessions,legacy_warmup,committed_bars,expected_bars,session_complete,gate,price,bar_start_et,bar_open,bar_high,bar_low,bar_close,last_ticks_in_bar,ema,keltner_upper,keltner_lower,bollinger_upper,bollinger_lower,atr,last_band,setup_side,position_side,detail,runtime_state,strategy_class,strategy_phase,account_local,instrument,trading_hours,tick_replay,bar_period,audit_source_version,news_model,news_calendar_sha256,news_verified_utc,news_expires_utc,news_violation,news_gate");
                integrityAudit.Flush();
                Print("HY Historien-Diagnose: " + integrityAuditPath);
                AuditRuntimeMetadata("audit initialized");
            }
            catch (Exception error)
            {
                MarkIntegrityAuditFailure(error);
            }
        }

        private static string AuditCsv(string value)
        {
            return "\"" + (value ?? "").Replace("\"", "\"\"").Replace("\r", " ").Replace("\n", " ") + "\"";
        }

        private static string AuditDate(DateTime value)
        {
            return value == default(DateTime) ? "" : value.ToString("yyyy-MM-dd HH:mm:ss.fffffff", CultureInfo.InvariantCulture);
        }

        private void MarkIntegrityAuditFailure(Exception error)
        {
            if (!integrityAuditFailed)
                Print("HY DIAGNOSE NICHT SCHREIBBAR: " + error.GetType().Name
                    + ". Neue Einstiege gesperrt; Ausstiege bleiben aktiv.");
            integrityAuditFailed = true;
            // Disk/log failures must never throw out of the market-data or order thread.
            try { integrityAudit?.Dispose(); } catch { }
            integrityAudit = null;
        }

        private void AuditIntegrity(string kind, DateTime eventTime, string detail, double price)
        {
            if (integrityAuditFailed || integrityAudit == null)
                return;
            try
            {
                int expected = sessionEnd > sessionOpen
                    ? (int)((sessionEnd - sessionOpen).Ticks / FiveMinutes.Ticks) : 0;
                string[] values = {
                    (++integrityAuditSequence).ToString(CultureInfo.InvariantCulture),
                    DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture), kind,
                    AuditDate(eventTime), AuditDate(integrityLastEventTime), AuditDate(lastMarketTime),
                    AuditDate(sessionOpen), AuditDate(sessionEnd), AuditDate(integritySeedBegin),
                    verifiedCompleteSessions.ToString(CultureInfo.InvariantCulture),
                    completeSessions.ToString(CultureInfo.InvariantCulture),
                    committedBars.ToString(CultureInfo.InvariantCulture), expected.ToString(CultureInfo.InvariantCulture),
                    sessionComplete.ToString(), IntegrityGateReason() ?? "READY",
                    price.ToString("R", CultureInfo.InvariantCulture), AuditDate(barStart),
                    integrityBarOpen.ToString("R", CultureInfo.InvariantCulture),
                    barHigh.ToString("R", CultureInfo.InvariantCulture), barLow.ToString("R", CultureInfo.InvariantCulture),
                    barClose.ToString("R", CultureInfo.InvariantCulture), integrityBarTicks.ToString(CultureInfo.InvariantCulture),
                    chartLines.Ema.ToString("R", CultureInfo.InvariantCulture),
                    chartLines.KeltnerUpper.ToString("R", CultureInfo.InvariantCulture), chartLines.KeltnerLower.ToString("R", CultureInfo.InvariantCulture),
                    chartLines.BollingerUpper.ToString("R", CultureInfo.InvariantCulture), chartLines.BollingerLower.ToString("R", CultureInfo.InvariantCulture),
                    chartLines.Atr.ToString("R", CultureInfo.InvariantCulture), lastBand.ToString(CultureInfo.InvariantCulture),
                    setupSide.ToString(CultureInfo.InvariantCulture), positionSide.ToString(CultureInfo.InvariantCulture), detail,
                    State.ToString(), GetType().Name, AuditPhaseLabel(), Account?.Name ?? "",
                    Instrument?.FullName ?? "", Bars?.TradingHours?.Name ?? "",
                    (Bars != null && IsTickReplays[0] == true).ToString(),
                    BarsPeriod == null ? "" : BarsPeriod.BarsPeriodType + ":" + BarsPeriod.Value, AuditDiagnosticVersion,
                    NewsModel, newsCalendar?.CsvSha256 ?? "",
                    newsCalendar == null ? "" : newsCalendar.VerifiedAtUtc.ToString("O", CultureInfo.InvariantCulture),
                    newsCalendar == null ? "" : newsCalendar.ExpiresAtUtc.ToString("O", CultureInfo.InvariantCulture),
                    newsViolation.ToString(), NewsEntryGateReason(NewsControlNow()) ?? "READY"
                };
                integrityAudit.WriteLine(string.Join(",", Array.ConvertAll(values, AuditCsv)));
                integrityAudit.Flush();
            }
            catch (Exception error)
            {
                MarkIntegrityAuditFailure(error);
            }
        }

        private void CloseIntegrityAudit()
        {
            try
            {
                AuditIntegrity("TERMINATED", lastMarketTime, "Instanz beendet", double.NaN);
                integrityAudit?.Dispose();
                integrityAudit = null;
            }
            catch (Exception error)
            {
                MarkIntegrityAuditFailure(error);
            }
        }

        private void ProbeCalendarBoundary(DateTime cursor, DateTime nextTemplateBegin)
        {
            // Bounded diagnostics only. Fresh iterators cannot reposition either live iterator.
            long[] offsets = { 1, TimeSpan.TicksPerMillisecond, TimeSpan.TicksPerSecond, TimeSpan.TicksPerMinute };
            foreach (long offset in offsets)
            foreach (bool includesEnd in new[] { false, true })
            foreach (bool positioned in new[] { false, true })
            {
                string detail = "offsetTicks=" + offset + " includesEnd=" + includesEnd + " positioned=" + positioned
                    + " cursor_ET=" + AuditDate(cursor) + " expectedBegin_ET=" + AuditDate(nextTemplateBegin);
                try
                {
                    var probe = new SessionIterator(Bars);
                    if (positioned)
                    {
                        DateTime seed = TimeZoneInfo.ConvertTime(DateTime.SpecifyKind(cursor.AddMinutes(-1),
                            DateTimeKind.Unspecified), easternZone, platformZone);
                        bool seedReturned = probe.GetNextSession(seed, true);
                        detail += " seedReturned=" + seedReturned;
                    }
                    DateTime query = TimeZoneInfo.ConvertTime(DateTime.SpecifyKind(cursor.AddTicks(offset),
                        DateTimeKind.Unspecified), easternZone, platformZone);
                    bool returned = probe.GetNextSession(query, includesEnd);
                    DateTime rawBegin = probe.ActualSessionBegin, rawEnd = probe.ActualSessionEnd;
                    detail += " returned=" + returned + " query_PLATFORM=" + query.ToString("O", CultureInfo.InvariantCulture)
                        + " queryKind=" + query.Kind + " queryTicks=" + query.Ticks
                        + " actualBegin_PLATFORM=" + rawBegin.ToString("O", CultureInfo.InvariantCulture)
                        + " beginKind=" + rawBegin.Kind + " beginTicks=" + rawBegin.Ticks
                        + " actualEnd_PLATFORM=" + rawEnd.ToString("O", CultureInfo.InvariantCulture)
                        + " endKind=" + rawEnd.Kind + " endTicks=" + rawEnd.Ticks
                        + " actualBegin_ET=" + AuditDate(PlatformToEastern(rawBegin))
                        + " actualEnd_ET=" + AuditDate(PlatformToEastern(rawEnd))
                        + " tradingDay=" + AuditDate(probe.ActualTradingDayExchange);
                }
                catch (Exception error)
                {
                    detail += " error=" + error.GetType().Name + ": " + error.Message;
                }
                AuditIntegrity("CALENDAR_PROBE", lastMarketTime, detail, double.NaN);
            }
        }

        private void RefreshSession(DateTime time)
        {
            if (!sessionFinished && sessionEnd != default(DateTime) && time >= sessionEnd)
                FinishSession();
            if (templateEnd != default(DateTime) && time < templateEnd)
                return;

            DateTime local = TimeZoneInfo.ConvertTime(DateTime.SpecifyKind(time, DateTimeKind.Unspecified), easternZone, platformZone);
            DateTime previousTemplateEnd = templateEnd;
            sessionIterator.GetNextSession(local, false);
            templateBegin = PlatformToEastern(sessionIterator.ActualSessionBegin);
            templateEnd = PlatformToEastern(sessionIterator.ActualSessionEnd);
            VerifyCalendarContinuity(previousTemplateEnd, templateBegin);
            DateTime day = sessionIterator.ActualTradingDayExchange.Date;
            sessionOpen = day.AddHours(9).AddMinutes(30);
            if (templateBegin > sessionOpen)
                sessionOpen = templateBegin;
            DateTime regularEnd = day.AddHours(17);
            sessionEnd = templateEnd < regularEnd ? templateEnd : regularEnd;
            DateTime providerDeadline = ProviderDeadline(day);
            flattenAt = (sessionEnd < providerDeadline ? sessionEnd : providerDeadline).AddMinutes(-1);
            sessionFinished = sessionEnd <= sessionOpen;
            sessionComplete = !sessionFinished;
            sessionSeenTrade = false;
            committedBars = 0;
            openingHigh = double.NegativeInfinity;
            openingLow = double.PositiveInfinity;
            openingObserved = openingFromStart = openingReported = false;
            bidClock = askClock = default(DateTime);
            barStart = default(DateTime);
            bidSize = askSize = 0;
            AuditIntegrity("SESSION_BEGIN", time, "Kalendersitzung geladen", double.NaN);
        }

        private void FinishSession()
        {
            CommitBar();
            int expected = (int)((sessionEnd - sessionOpen).Ticks / FiveMinutes.Ticks);
            completeSessions = sessionComplete && committedBars == expected && expected > 0
                ? completeSessions + 1 : 0;
            CompleteIntegritySession(expected);
            sessionFinished = true;
        }

        private void ObserveOpeningRange(DateTime eventTime, double price, bool realtime)
        {
            if (!UsesOpeningRange || eventTime < sessionOpen
                || eventTime >= sessionEnd || !(price > 0) || double.IsInfinity(price))
                return;
            if (eventTime < sessionOpen + OpeningWindow)
            {
                if (openingReported)
                    return;
                if (!openingObserved)
                    openingFromStart = eventTime <= sessionOpen.AddSeconds(5);
                openingObserved = true;
                openingHigh = Math.Max(openingHigh, price);
                openingLow = Math.Min(openingLow, price);
            }
            else if (!openingReported && realtime)
            {
                openingReported = true;
                Print(string.Format(CultureInfo.InvariantCulture,
                    "104-C28.03 OR60 {0:yyyy-MM-dd} high={1:F2} low={2:F2} valid={3}",
                    eventTime, openingHigh, openingLow, openingObserved && openingFromStart && sessionComplete));
            }
        }

        private bool TouchesOpeningTarget(DateTime eventTime, double price)
        {
            if (!UsesOpeningRange || !openingObserved || !openingFromStart || !sessionComplete
                || eventTime < sessionOpen + OpeningWindow)
                return false;
            double level = positionSide > 0 ? openingHigh : openingLow;
            return positionSide * (level - positionEntryPrice) >= 0.25
                && positionSide * (price - level) >= 0;
        }

        private void ObserveTrade(DateTime time, DateTime marketEventTime, double price, bool realtime)
        {
            long elapsed = (marketEventTime - sessionOpen).Ticks;
            DateTime bucket = sessionOpen.AddTicks(elapsed / FiveMinutes.Ticks * FiveMinutes.Ticks);
            // A late print may still update the active bar, but never a bar already committed.
            if (bucket < barStart)
                return;
            if (realtime && marketEventTime > lastTradeClock)
                lastTradeClock = marketEventTime;
            if (barStart != bucket)
            {
                if ((!sessionSeenTrade && bucket != sessionOpen)
                    || (sessionSeenTrade && bucket != barStart + FiveMinutes))
                    sessionComplete = false;
                CommitBar();
                barStart = bucket;
                barHigh = barLow = price;
                integrityBarOpen = price;
                integrityBarTicks = 0;
                sessionSeenTrade = true;
            }
            barHigh = Math.Max(barHigh, price);
            barLow = Math.Min(barLow, price);
            barClose = price;
            integrityBarTicks++;

            Lines lines;
            if (!indicators.TryPreview(barHigh, barLow, barClose, committedBars == 0, out lines))
                return;
            chartLines = lines;
            chartLinesBarEnd = bucket + FiveMinutes;

            if (realtime && positionSide != 0)
                positionExitBand = positionSide > 0 ? lines.BollingerUpper : lines.BollingerLower;

            if (realtime && positionSide != 0 && !exitSubmissionFailed && pending == null && submitted == null)
            {
                if (CrossesStop(positionSide, price, positionStop))
                    Queue(new Intent(false, positionSide, "Stop", time, positionStop));
                else if (positionSide > 0 ? price > lines.BollingerUpper : price < lines.BollingerLower)
                    Queue(new Intent(false, positionSide, "Ziel", time, positionStop));
                else if (TouchesOpeningTarget(marketEventTime, price))
                    Queue(new Intent(false, positionSide, "OR60", time, positionStop));
            }

            // Evaluate an existing return before this tick can create a new setup.
            if (setupSide != 0 && (setupSide > 0 ? price <= lines.Ema : price >= lines.Ema))
            {
                int side = setupSide;
                setupSide = 0;
                var retrace = CurrentBar < 0 ? null : new SetupPoint(CurrentBar, price, side, time.Date);
                if (armedSecondMark != null)
                    RememberBadge(retrace, 3);
                AuditIntegrity("ENTRY_DECISION", time, "side=" + side + " " + EntryAuditReason(time, realtime), price);
                if (realtime && CanEnter(time) && positionSide == 0 && pending == null && submitted == null)
                {
                    double stop = InitialStop(side, lines);
                    if (!CrossesStop(side, price, stop))
                    {
                        var intent = new Intent(true, side, "FirstReturn", time, stop);
                        if (retrace != null)
                            intent.Marks = new EntryMarks(armedFirstMark, armedSecondMark, retrace);
                        Queue(intent);
                    }
                }
                armedFirstMark = armedSecondMark = null;
            }

            int contact = price >= lines.KeltnerUpper ? 1 : price <= lines.KeltnerLower ? -1 : 0;
            if (contact != 0 && contact != lastBand)
            {
                var touched = CurrentBar < 0 ? null : new SetupPoint(CurrentBar, price, contact, time.Date);
                if (lastBand != 0)
                {
                    setupSide = contact;
                    armedFirstMark = lastContactMark;
                    armedSecondMark = touched;
                    RememberBadge(armedFirstMark, 1);
                    RememberBadge(touched, 2);
                }
                else
                    RememberBadge(touched, 1);
                AuditIntegrity("BAND_CONTACT", time, "Band=" + contact
                    + (lastBand == 0 ? " erster Kontakt" : " Gegenband / Setup"), price);
                lastBand = contact;
                lastContactMark = touched;
            }
            else if (contact != 0 && setupSide == 0 && CurrentBar >= 0
                && (lastContactMark == null || lastContactMark.Session != time.Date))
            {
                // A real same-side retouch can give the carried contact a visible anchor today.
                // This refreshes only the display. It does not change the setup or lastBand.
                lastContactMark = new SetupPoint(CurrentBar, price, contact, time.Date);
                RememberBadge(lastContactMark, 1);
            }
        }

        private void CommitBar()
        {
            if (barStart == default(DateTime))
                return;
            indicators.Commit(barHigh, barLow, barClose, committedBars == 0);
            committedBars++;
            AuditIntegrity("BAR_COMMIT", barStart, "5-Minuten-Abschnitt abgeschlossen", barClose);
            barStart = default(DateTime);
        }

        private bool CanEnter(DateTime time)
        {
            return IntegrityGateReason() == null && NewsEntryGateReason(time) == null
                && AccountReplayReady() && !modelLossLatched && !entryBlocked && sessionComplete && completeSessions >= WarmupSessions
                && time >= sessionOpen && time < flattenAt
                && (!liveClock || MarketTimeAgrees(time, lastTradeClock));
        }

        private static double InitialStop(int side, Lines lines)
        {
            // Match the SQX outward rounding, including floating-point ties on an ES tick.
            double rawTicks = (lines.Ema - side * (2.0 + 0.15) * lines.Atr) * 4.0;
            double nearest = Math.Round(rawTicks, MidpointRounding.ToEven);
            double positive = Math.Abs(rawTicks);
            double ulp = BitConverter.Int64BitsToDouble(BitConverter.DoubleToInt64Bits(positive) + 1) - positive;
            if (Math.Abs(rawTicks - nearest) <= Math.Min(8.0 * ulp, 1e-8))
                rawTicks = nearest;
            return (side > 0 ? Math.Floor(rawTicks) : Math.Ceiling(rawTicks)) / 4.0;
        }

        private static bool CrossesStop(int side, double price, double stop)
        {
            return side > 0 ? price <= stop : price >= stop;
        }

        private void Queue(Intent intent)
        {
            AuditIntegrity(intent.IsEntry ? "ENTRY_SIGNAL" : "EXIT_SIGNAL", intent.Time,
                intent.Reason + " side=" + intent.Side + " stop="
                + intent.Stop.ToString("R", CultureInfo.InvariantCulture), double.NaN);
            pending = intent;
            Print(string.Format(CultureInfo.InvariantCulture,
                "104-C28.03 SIGNAL {0:yyyy-MM-dd HH:mm:ss.fff} ET {1} {2} stop={3:F2}",
                intent.Time, intent.Reason, intent.Side > 0 ? "LONG" : "SHORT", intent.Stop));
        }

        private bool CheckModelLoss(DateTime time, bool useNewQuote)
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
                pending = null;
            }
            if (positionSide != 0 && !exitSubmissionFailed && submitted == null && pending == null)
                Queue(new Intent(false, positionSide, "RapidLoss", time, positionStop));
            return useNewQuote;
        }

        private bool CheckClose(DateTime time)
        {
            if (flattenAt == default(DateTime) || time < flattenAt)
                return false;
            if (pending != null && pending.IsEntry)
                pending = null;
            if (positionSide != 0 && !exitSubmissionFailed && pending == null && submitted == null)
                Queue(new Intent(false, positionSide, "SessionEnd", flattenAt, positionStop));
            return time >= flattenAt.AddSeconds(30);
        }

        private Intent TakePending(DateTime time, bool quote, bool forceClose)
        {
            if (pending == null || submitted != null)
                return null;
            if (pending.IsEntry && !CanEnter(time))
            {
                AuditIntegrity("ENTRY_DISPATCH_BLOCKED", time, EntryAuditReason(time, true), double.NaN);
                pending = null;
                return null;
            }
            if (IsOrderAccount() && !OrderConnectionReady())
                return null;
            bool validQuote = quote && bidSize >= 1 && askSize >= 1 && bid > 0 && bid <= ask && !double.IsInfinity(ask);
            bool emergencyExit = forceClose && !pending.IsEntry;
            if (!emergencyExit && (!validQuote || time < pending.Time.AddSeconds(2)))
                return null;
            if (pending.IsEntry && CrossesStop(pending.Side, pending.Side > 0 ? bid : ask, pending.Stop))
            {
                pending = null;
                Print("HY104: entry skipped because the executable bid/ask has reached the stop.");
                return null;
            }
            if (emergencyExit && (!validQuote || time < pending.Time.AddSeconds(2)))
                Print(IsNewsNoQuoteExit(pending) ? "HY104 NEWS_NO_QUOTE_MARKET_EXIT: actual SIM execution pending; no reference quote." : "HY104: session-close fallback.");
            if (!IsOrderAccount())
            {
                Intent signal = pending;
                pending = null;
                if (SimAutomatik || !MatchesSimulationAccount())
                    return null;
                bool buy = signal.IsEntry ? signal.Side > 0 : signal.Side < 0;
                ApplyModelSignal(signal, validQuote ? (buy ? ask : bid) : double.NaN, time);
                return null;
            }
            if (!pending.IsEntry && !ClaimCurrentTradeExit(pending, time))
            {
                pending = null;
                return null;
            }
            if (IsNewsNoQuoteExit(pending))
                newsNoQuoteExitIntent = validQuote ? null : pending;
            submitted = pending;
            pending = null;
            return submitted;
        }

        private void Submit(Intent intent)
        {
            if (RejectUnavailableIntent(intent, NewsControlNow()))
                return;
            if (State != State.Realtime || !IsOrderAccount())
                return;
            if (!OrderConnectionReady())
            {
                lock (sync)
                {
                    if (RejectUnavailableIntent(intent, NewsControlNow()))
                        return;
                    if (submitted == intent)
                    {
                        pending = intent;
                        submitted = null;
                    }
                }
                return;
            }
            DateTime now = EasternNow();
            if (now.Date != intent.Time.Date || now >= ProviderDeadline(intent.Time)
                || now >= flattenAt.AddMinutes(1))
            {
                FailSubmission(intent, "Order nach dem ES-Schlusszeitpunkt gesperrt.");
                return;
            }
            if (intent.IsEntry && (!CanEnter(now) || PositionAccount == null
                || Position.MarketPosition != MarketPosition.Flat
                || PositionAccount.MarketPosition != MarketPosition.Flat || HasWorkingOrder()))
            {
                FailSubmission(intent, "Einstieg gesperrt. Sitzungsschluss oder ES-Kontoposition prüfen.");
                return;
            }
            if (intent == newsNoQuoteExitIntent)
                lock (sync) CheckNewsPositionMismatch(now);
            if (!intent.IsEntry)
            {
                MarketPosition expected = intent.Side > 0 ? MarketPosition.Long : MarketPosition.Short;
                if (PositionAccount == null || PositionAccount.MarketPosition != expected
                    || PositionAccount.Quantity != 1)
                {
                    FailSubmission(intent, "Ausstieg gesperrt. ES-Kontoposition stimmt nicht überein.");
                    return;
                }
            }

            lock (sync)
            {
                if (RejectUnavailableIntent(intent, now))
                    return;
                CheckNewsPositionMismatch(now);
                if (intent.IsEntry && (!CanEnter(now) || PositionAccount == null || Position == null
                    || Position.MarketPosition != MarketPosition.Flat
                    || PositionAccount.MarketPosition != MarketPosition.Flat || HasWorkingOrder()))
                {
                    FailSubmission(intent, "Entry blocked by final ownership/position/order recheck.");
                    return;
                }
                if (!intent.IsEntry)
                {
                    MarketPosition expectedFinal = intent.Side > 0 ? MarketPosition.Long : MarketPosition.Short;
                    if (Position == null || PositionAccount == null || Position.MarketPosition != expectedFinal
                        || PositionAccount.MarketPosition != expectedFinal || Position.Quantity != 1 || PositionAccount.Quantity != 1)
                    {
                        FailSubmission(intent, "Exit blocked by final owned position recheck.");
                        return;
                    }
                }
                if (!intent.IsEntry && !ClaimCurrentTradeExit(intent, now))
                {
                    FailSubmission(intent, "Exit intent does not own the active trade.");
                    return;
                }
                if (intent == newsNoQuoteExitIntent)
                {
                    CheckNewsPositionMismatch(now);
                    if (!NewsNoQuotePositionAgrees(intent.Side))
                    {
                        FailSubmission(intent, "News MarketExit blocked: strategy/account position or active order changed.");
                        return;
                    }
                }
                // Reservation belongs to this exact immutable intent lifetime, not a mutable news marker.
                if (!intentApiSendStarted.Add(intent))
                    return;
                if (!ReserveAccountIntent(intent, now))
                {
                    FailSubmission(intent, "Kontojournal konnte Orderabsicht nicht dauerhaft speichern.");
                    return;
                }

                AuditIntegrity("INTENT_API_REQUEST_RESERVED", now,
                    "reason=" + intent.Reason + " ownedTrade=" + activeOwnedTradeId + ";request_only", double.NaN);
                if (intent == newsNoQuoteExitIntent)
                    AuditIntegrity(object.ReferenceEquals(intent, newsEscalatedOlderExit)
                        ? "NEWS_PREEXISTING_EXIT_NO_QUOTE_MARKET_EXIT" : "NEWS_NO_QUOTE_MARKET_EXIT",
                        now, NewsNoQuoteAuditDetail(intent), double.NaN);
            }

            Order order;
            if (intent.IsEntry)
                order = intent.Side > 0 ? EnterLong(1, LongEntry) : EnterShort(1, ShortEntry);
            else
                order = intent.Side > 0 ? ExitLong(intent.OrderName, LongEntry) : ExitShort(intent.OrderName, ShortEntry);
            if (order == null)
                FailSubmission(intent, "NinjaTrader did not return an order. See the Log tab.");
            else
                Print("104-C28.03 ORDER " + intent.OrderName + " " + order.OrderId);
        }

        private static DateTime ProviderDeadline(DateTime date)
        {
            return date.Date.AddHours(16).AddMinutes(10);
        }

        private bool MatchesSimulationAccount()
        {
            return Account != null && Account.Provider == Provider.Simulator
                && string.Equals(Account.Name, SimulationAccountName, StringComparison.OrdinalIgnoreCase);
        }

        private bool IsOrderAccount()
        {
            return SimAutomatik && liveClock && ownsSimulationOrderSlot && MatchesSimulationAccount();
        }

        private bool OrderConnectionReady()
        {
            var connection = Account?.Connection;
            return connection != null && connection.Status == ConnectionStatus.Connected;
        }

        private string ModeLabel()
        {
            if (!MatchesSimulationAccount())
                return "KONTO PRÜFEN";
            return IsOrderAccount() ? "SIM-AUTOMATIK" : "SIGNAL";
        }

        private bool HasWorkingOrder()
        {
            lock (Account.Orders)
            {
                foreach (Order order in Account.Orders)
                    if (order != null && order.Instrument == Instrument
                        && order.OrderState != OrderState.Filled && order.OrderState != OrderState.Cancelled
                        && order.OrderState != OrderState.Rejected)
                        return true;
            }
            return false;
        }

        private static bool MarketTimeAgrees(DateTime current, DateTime market)
        {
            return market != default(DateTime) && current.Date == market.Date
                && (current - market).Duration() <= MaximumClockSkew;
        }

        private void ApplyModelSignal(Intent signal, double price, DateTime time)
        {
            UpdatePosition(signal, price);
            string direction = signal.Side > 0 ? "LONG" : "SHORT";
            string action = "Signal " + direction;
            if (!signal.IsEntry)
            {
                string reason = signal.Reason == "SessionEnd" ? "Handelsschluss" : signal.Reason;
                action = "Ausstieg " + direction + " · " + reason;
            }
            string prices = double.IsNaN(price) ? "ohne aktuelle Quote" : "Referenz " + price.ToString("F2", CultureInfo.CurrentCulture);
            if (signal.IsEntry)
                prices += string.Format(CultureInfo.CurrentCulture, " · Stop {0:F2} · Ziel {1:F2}", positionStop, positionExitBand);
            lastModelSignal = action + " · " + prices;
            Print(string.Format(CultureInfo.CurrentCulture, "HY104 MODELL {0:HH:mm:ss.fff} ET · {1} · {2}",
                time, action, prices));
        }

        private void UpdatePosition(Intent filled, double price)
        {
            positionSide = filled.IsEntry ? filled.Side : 0;
            positionStop = filled.IsEntry ? filled.Stop : 0;
            positionEntryPrice = filled.IsEntry ? price : 0;
            positionExitBand = positionSide > 0 ? chartLines.BollingerUpper
                : positionSide < 0 ? chartLines.BollingerLower : 0;
        }

        private void FailSubmission(Intent intent, string message)
        {
            lock (sync)
            {
                if (submitted != intent)
                    return;
                submitted = null;
                entryBlocked = true;
                if (!intent.IsEntry)
                {
                    exitSubmissionFailed = true;
                    Print("HY104: verify the remaining ES position on the strategy account.");
                }
                AuditIntegrity("ORDER_FAILURE", intent.Time, message, double.NaN);
                Print("HY104: " + message);
            }
        }

        protected override void OnOrderUpdate(Order order, double limitPrice, double stopPrice, int quantity,
            int filled, double averageFillPrice, OrderState orderState, DateTime time, ErrorCode error, string comment)
        {
            lock (sync)
                AuditOrderState(order, limitPrice, stopPrice, quantity, filled, averageFillPrice, orderState, time, error, comment);
            if (!IsOrderAccount())
                return;
            lock (sync)
            {
                bool handled = HandleNewsOrderUpdate(order, quantity, filled, orderState, error, NewsControlNow());
                ResolveAccountOrderTerminal(order, quantity, filled, orderState);
                if (handled) return;
            }
            if (orderState != OrderState.Rejected && orderState != OrderState.Cancelled)
                return;
            lock (sync)
            {
                Intent owner = NewsOrderIntent(order);
                if (owner != null && object.ReferenceEquals(owner, submitted) && filled == 0)
                    FailSubmission(owner, order.Name + " " + orderState + " " + error + " " + comment);
            }
        }

        protected override void OnExecutionUpdate(Execution execution, string executionId, double price, int quantity,
            MarketPosition marketPosition, string orderId, DateTime time)
        {
            lock (sync)
                AuditExecutionCallback(execution, executionId, price, quantity, marketPosition, orderId, time);
            if (!IsOrderAccount())
                return;
            lock (sync)
            {
                Intent correlated = NewsExecutionIntent(execution);
                if (execution.Order == null || execution.Order.Account != Account || execution.Order.Instrument != Instrument)
                    return;
                if (correlated == null)
                {
                    LatchNewsViolation(NewsControlNow(), "EXECUTION WITHOUT INTENT CLAIM · tatsächliche Kontoposition prüfen");
                    AuditIntegrity("EXECUTION_WITHOUT_INTENT_CLAIM", PlatformToEastern(time),
                        "executionId=" + executionId + " orderId=" + orderId + ";no name-only fill adoption", price);
                    return;
                }
                if (DuplicateNewsExecution(executionId, PlatformToEastern(time)))
                    return;
                Intent filled = correlated;
                AuditIntegrity(filled.IsEntry ? "ENTRY_FILL" : "EXIT_FILL", PlatformToEastern(time),
                    filled.Reason + " quantity=" + quantity, price);
                if (quantity != 1)
                {
                    NewsExecutionQuantityAnomaly(filled, quantity, NewsControlNow());
                    return;
                }
                if (!AcceptIntentExecutionLifetime(filled, NewsControlNow()))
                    return;
                RecordAccountExecution(executionId, filled, price, time);
                UpdatePosition(filled, price);
                if (filled.IsEntry && filled.Marks != null && CurrentBar >= 0)
                {
                    filled.Marks.Fill = new SetupPoint(CurrentBar, price, filled.Side, filled.Time.Date);
                    confirmedEntryMarks.Add(filled.Marks);
                    if (confirmedEntryMarks.Count > 8)
                        confirmedEntryMarks.RemoveAt(0);
                }
                Print(string.Format(CultureInfo.InvariantCulture, "Rapid EOD SIM realized={0:F2}", modelRealized));
                if (submitted == filled)
                    submitted = null;
                AfterNewsExecution(execution, filled);
                Print(string.Format(CultureInfo.InvariantCulture,
                    "104-C28.03 FILL {0:yyyy-MM-dd HH:mm:ss.fff} ET {1} {2} x{3} @ {4:F2}",
                    PlatformToEastern(time), filled.IsEntry ? "ENTRY" : "EXIT", filled.Reason, quantity, price));
            }
        }

        private void QueueWatchdog(object unused)
        {
            if (State != State.Realtime || Interlocked.Exchange(ref watchdogQueued, 1) != 0)
                return;
            try
            {
                TriggerCustomEvent(OnWatchdog, null);
            }
            catch (InvalidOperationException)
            {
                Interlocked.Exchange(ref watchdogQueued, 0);
            }
        }

        private void OnWatchdog(object unused)
        {
            try
            {
                if (State != State.Realtime || Account == null)
                    return;
                DateTime time = EasternNow();
                Intent next;
                lock (sync)
                {
                    EnsureNewsCalendar(time);
                    AdvanceNews(time);
                    CheckNewsPositionMismatch(time);
                    bool loss = CheckModelLoss(time, true);
                    next = TakePending(time, false, CheckClose(time) || loss || CanDispatchNewsNoQuoteMarketExit(time));
                }
                if (next != null)
                    Submit(next);
                UpdateLegend(time);
            }
            finally
            {
                Interlocked.Exchange(ref watchdogQueued, 0);
            }
        }

        private DateTime PlatformToEastern(DateTime time)
        {
            if (time.Kind == DateTimeKind.Utc)
                return TimeZoneInfo.ConvertTimeFromUtc(time, easternZone);
            return TimeZoneInfo.ConvertTime(DateTime.SpecifyKind(time, DateTimeKind.Unspecified), platformZone, easternZone);
        }

        private DateTime EasternNow()
        {
            return TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, easternZone);
        }

        private sealed class StatusCard
        {
            public readonly string Account;
            public readonly string Clock;
            public readonly string Mode;
            public readonly string State;
            public readonly string Detail;
            public readonly string Levels;
            public readonly string Countdown;
            public readonly string MarketRemaining;
            public readonly string FirstBand, OppositeBand, Retrace;
            public readonly int FirstBandSide, OppositeBandSide;
            public readonly SharpDX.Color4 Accent;

            public StatusCard(string account, string clock, string mode, string state,
                string detail, string levels, string countdown, string marketRemaining, SharpDX.Color4 accent, string firstBand, string oppositeBand, string retrace, int firstBandSide, int oppositeBandSide)
            {
                Account = account;
                Clock = clock;
                Mode = mode;
                State = state;
                Detail = detail;
                Levels = levels;
                Countdown = countdown;
                MarketRemaining = marketRemaining;
                FirstBand = firstBand;
                OppositeBand = oppositeBand;
                Retrace = retrace;
                FirstBandSide = firstBandSide;
                OppositeBandSide = oppositeBandSide;
                Accent = accent;
            }
        }

        private sealed class Intent
        {
            public readonly bool IsEntry;
            public EntryMarks Marks;
            public readonly int Side;
            public readonly string Reason;
            public readonly DateTime Time;
            public readonly double Stop;

            public Intent(bool isEntry, int side, string reason, DateTime time, double stop)
            {
                IsEntry = isEntry;
                Side = side;
                Reason = reason;
                Time = time;
                Stop = stop;
            }

            public string OrderName
            {
                get { return IsEntry ? (Side > 0 ? LongEntry : ShortEntry) : "HY104" + Reason; }
            }
        }

        private struct Lines
        {
            public double Ema;
            public double Atr;
            public double KeltnerUpper;
            public double KeltnerLower;
            public double BollingerUpper;
            public double BollingerLower;
        }

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
                HYAccountProfileV8 profile = HYAccountProfileV8.MffFunded;
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
            Intent owner = NewsOrderIntent(order);
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

        private sealed class IndicatorState
        {
            private readonly Queue<double> closes = new Queue<double>(19);
            private double? ema;
            private double? atr;
            private double previousClose;
            private double trueRangeSeed;
            private int trueRangeCount;

            private double TrueRange(double high, double low, bool firstSessionBar)
            {
                return !ema.HasValue || firstSessionBar ? high - low
                    : Math.Max(high - low, Math.Max(Math.Abs(high - previousClose), Math.Abs(low - previousClose)));
            }

            private double NextEma(double close)
            {
                return ema.HasValue ? ema.Value + (2.0 / 21.0) * (close - ema.Value) : close;
            }

            public void Commit(double high, double low, double close, bool firstSessionBar)
            {
                double range = TrueRange(high, low, firstSessionBar);
                if (atr.HasValue)
                    atr = (atr.Value * 9 + range) / 10;
                else
                {
                    trueRangeSeed += range;
                    trueRangeCount++;
                    if (trueRangeCount == 10)
                        atr = trueRangeSeed / 10;
                }
                ema = NextEma(close);
                previousClose = close;
                if (closes.Count == 19)
                    closes.Dequeue();
                closes.Enqueue(close);
            }

            public bool TryPreview(double high, double low, double close, bool firstSessionBar, out Lines lines)
            {
                lines = default(Lines);
                if (closes.Count < 19 || !atr.HasValue)
                    return false;
                double currentAtr = (atr.Value * 9 + TrueRange(high, low, firstSessionBar)) / 10;
                if (currentAtr <= 0)
                    return false;
                double currentEma = NextEma(close);
                // ES prices are in 0.25 increments. Centering also keeps the sum of squares small.
                double sum = close;
                foreach (double value in closes)
                    sum += value;
                double mean = sum / 20;
                double squared = (close - mean) * (close - mean);
                foreach (double value in closes)
                    squared += (value - mean) * (value - mean);
                // The target threshold stays off-grid. A last-trade print must strictly cross
                // it. The market order still executes at tradable prices in the local simulator.
                double band = 1.75 * Math.Sqrt(squared / 20) - TargetOffsetPoints;
                lines = new Lines
                {
                    Ema = currentEma, Atr = currentAtr,
                    KeltnerUpper = currentEma + 2 * currentAtr, KeltnerLower = currentEma - 2 * currentAtr,
                    BollingerUpper = mean + band, BollingerLower = mean - band
                };
                return true;
            }
        }
    }
}
