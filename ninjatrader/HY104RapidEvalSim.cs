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
    public class HY104RapidEvalSim : Strategy
    {
        private const string LongEntry = "HY104RapidEvalSimLong";
        private const string ShortEntry = "HY104RapidEvalSimShort";
        private const string StopDrawing = "HY104RapidEvalSimFixedStop";
        private const string TradingHoursName = "CME US Index Futures ETH";
        private const int WarmupSessions = 5;
        private const string SimulationAccountName = "SimHY104RapidEval";
        private static readonly DateTime TestDay = new DateTime(2026, 11, 16);
        private const bool UsesOpeningRange = false;
        private const double OpeningModelBalance = 50000.0;
        private const double IntradayLossFloor = OpeningModelBalance - 2000.0;
        private const double ModelFeePerSide = 2.87;
        private static readonly TimeSpan OpeningWindow = TimeSpan.FromMinutes(60);
        private static bool modelLossLatched;
        private static double modelRealized;
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
        private static readonly SharpDX.Color4 LiveAccent = Pigment(154, 187, 255);
        private static readonly SharpDX.Color4 ReplayAccent = Pigment(116, 147, 194);
        private static readonly SharpDX.Color4 ManualAccent = Pigment(166, 181, 203);
        private static readonly SharpDX.Color4 WaitingAccent = Pigment(116, 147, 194);
        private static readonly SharpDX.Color4 ClosedAccent = Pigment(166, 181, 203);
        private static readonly SharpDX.Color4 ErrorAccent = Pigment(255, 156, 172);
        private readonly object sync = new object();
        private readonly IndicatorState indicators = new IndicatorState();

        private TimeZoneInfo platformZone;
        private TimeZoneInfo easternZone;
        private TimeZoneInfo chicagoZone;
        private SessionIterator sessionIterator;
        private DateTime templateBegin;
        private DateTime templateEnd;
        private DateTime sessionOpen;
        private DateTime sessionEnd;
        private DateTime flattenAt;
        private DateTime lastMarketTime;
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
            if (State == State.SetDefaults)
            {
                Name = "HY104 | Rapid EOD Eval SIM";
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
                Print("HY104: " + Account.Name + " · " + ModeLabel()
                    + " · Aufwärmsitzungen " + completeSessions + "/" + WarmupSessions);
                if (ChartControl != null)
                    UpdateLegend(liveClock ? EasternNow() : lastMarketTime);
                if (liveClock)
                    watchdog = new Timer(QueueWatchdog, null, 250, 250);
            }
            else if (State == State.Terminated)
            {
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
                if (time < lastMarketTime)
                    return;
                lastMarketTime = time;

                bool forceClose = realtime && CheckClose(time);
                // When crossing an entire session gap, handle the old position before replacing its close time.
                next = forceClose ? TakePending(time, false, true) : null;
                RefreshSession(time);
                if (kind == MarketDataType.Last)
                    ObserveOpeningRange(marketEventTime, update.Price, realtime);
                if (realtime && kind == MarketDataType.Last)
                    CheckModelLoss(time, false);
                if (kind == MarketDataType.Last)
                {
                    if (update.Price > 0 && !double.IsInfinity(update.Price))
                    {
                        if (time >= sessionOpen && time < sessionEnd)
                        {
                            if (realtime)
                                lastTradeClock = marketEventTime;
                            ObserveTrade(time, marketEventTime, update.Price, realtime);
                        }
                        else if (ChartControl != null && time >= templateBegin && time < sessionOpen
                            && sessionOpen < sessionEnd)
                            ObservePreviewTrade(time, update.Price);
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
                string steps = null;
                if (time.Date == TestDay && time >= sessionOpen && time < flattenAt && positionSide == 0)
                {
                    EntryMarks intent = (submitted ?? pending)?.Marks;
                    if (intent != null)
                        steps = "1 Band  ·  2 Gegenband  ·  3 EMA " + (intent.Return.Side > 0 ? "Long" : "Short") + "  ·  Fill ausstehend";
                    else if (armedSecondMark != null)
                        steps = "1 Band  ·  2 Gegenband  ·  " + (armedSecondMark.Side > 0 ? "Long" : "Short") + " bereit";
                    else if (lastContactMark != null)
                        steps = "1 Band  ·  Gegenband ausstehend";
                }
                statusCard = new StatusCard(Account.Name, chicago.ToString("HH:mm:ss", CultureInfo.InvariantCulture) + " CT",
                    mode, state, detail, levels, countdown, marketCountdown, accent, steps);
            }
            ForceRefresh();
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
                return "SIM-KONTO BEREITS BELEGT";
            if (SimAutomatik && (!liveClock || !OrderConnectionReady()))
                return "WARTET  ·  SIM-Orderverbindung";
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
                return "SITZUNGSENDE  ·  Keine neuen Einstiege";
            if (!CanEnter(time))
                return completeSessions < WarmupSessions
                    ? "WARTET  ·  Warm-up " + completeSessions + "/" + WarmupSessions
                    : "WARTET  ·  Unvollständige Sitzung";
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
            if (point == null || point.Session != TestDay || sessionBadges.Any(b => b.Point == point))
                return;
            if (sessionBadges.Count == 96)
                sessionBadges.RemoveAt(0);
            sessionBadges.Add(new SetupBadge(point, step));
        }

        private void RenderEntryMarks(ChartControl chart, ChartScale scale)
        {
            if (RenderTarget == null || ChartBars == null || ChartPanel == null || Bars == null)
                return;
            EntryMarks live;
            EntryMarks[] recent;
            SetupBadge[] badges;
            SetupPoint first, second;
            lock (sync)
            {
                live = (submitted ?? pending)?.Marks;
                recent = confirmedEntryMarks.ToArray();
                badges = sessionBadges.ToArray();
                first = armedSecondMark == null ? lastContactMark : armedFirstMark;
                second = armedSecondMark;
            }
            using (var cyan = new D2D.SolidColorBrush(RenderTarget, Pigment(86, 228, 255)))
            using (var violet = new D2D.SolidColorBrush(RenderTarget, Pigment(189, 153, 255)))
            using (var gold = new D2D.SolidColorBrush(RenderTarget, Pigment(255, 214, 97)))
            using (var mint = new D2D.SolidColorBrush(RenderTarget, Pigment(88, 255, 184)))
            using (var ink = new D2D.SolidColorBrush(RenderTarget, Pigment(11, 19, 33)))
            using (var number = new DWrite.TextFormat(Core.Globals.DirectWriteFactory, "Segoe UI Black", 29f))
            {
                number.TextAlignment = DWrite.TextAlignment.Center;
                number.ParagraphAlignment = DWrite.ParagraphAlignment.Center;
                number.WordWrapping = DWrite.WordWrapping.NoWrap;
                foreach (SetupBadge badge in badges)
                {
                    if (badge.Point == first || badge.Point == second || live?.Contains(badge.Point) == true
                        || recent.Any(trace => trace.Contains(badge.Point)))
                        continue;
                    DrawStep(badge.Point, badge.Step, chart, scale, cyan, violet, gold, ink, number);
                }
                foreach (EntryMarks trace in recent)
                    DrawEntryTrace(trace, chart, scale, cyan, violet, gold, mint, ink, number);
                if (live != null)
                    DrawEntryTrace(live, chart, scale, cyan, violet, gold, mint, ink, number);
                else
                {
                    if (!recent.Any(t => t.First == first || t.Second == first))
                        DrawStep(first, 1, chart, scale, cyan, violet, gold, ink, number);
                    if (!recent.Any(t => t.Second == second))
                        DrawStep(second, 2, chart, scale, cyan, violet, gold, ink, number);
                }
            }
        }

        private void DrawStep(SetupPoint point, int step, ChartControl chart, ChartScale scale,
            D2D.Brush cyan, D2D.Brush violet, D2D.Brush gold, D2D.Brush ink, DWrite.TextFormat text)
        {
            if (point == null) return;
            if (step == 3)
                point = new SetupPoint(point.Bar, point.Price, -point.Side, point.Session);
            DrawSetupBadge(point, step == 1 ? "1" : step == 2 ? "2" : "3",
                step == 3 ? -59f : 0f, 24f, false, chart, scale,
                step == 1 ? cyan : step == 2 ? violet : gold, ink, text);
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

        private void DrawEntryTrace(EntryMarks m, ChartControl chart, ChartScale scale,
            D2D.Brush cyan, D2D.Brush violet, D2D.Brush gold, D2D.Brush mint, D2D.Brush ink, DWrite.TextFormat text)
        {
            DrawStep(m.First, 1, chart, scale, cyan, violet, gold, ink, text);
            DrawStep(m.Second, 2, chart, scale, cyan, violet, gold, ink, text);
            DrawStep(m.Return, 3, chart, scale, cyan, violet, gold, ink, text);
            if (m.Fill != null)
                DrawSetupBadge(new SetupPoint(m.Fill.Bar, m.Fill.Price, -m.Fill.Side, m.Fill.Session),
                    m.Fill.Side > 0 ? "▲" : "▼", 62f, 25f, true, chart, scale, mint, ink, text);
        }

        private void RenderStatusCard()
        {
            if (RenderTarget == null || ChartPanel == null || ChartPanel.W < 284)
                return;
            StatusCard card;
            lock (sync)
                card = statusCard;
            if (card == null)
                return;

            float width = Math.Min(680f, ChartPanel.W - 18f);
            const float pad = 15f;
            string[] levels = string.IsNullOrEmpty(card.Levels) ? new string[0] : card.Levels.Split('|');
            bool detail = !string.IsNullOrEmpty(card.Detail);
            bool steps = !string.IsNullOrEmpty(card.Steps);
            float height = 87f + (steps ? 28f : 0f) + (detail ? 28f : 0f) + 28f * levels.Length;
            if (ChartPanel.H < height + 14f)
                return;
            float left = ChartPanel.X + (ChartPanel.W - width) / 2f;
            float top = ChartPanel.Y + 10f;
            float x = left + pad;
            float inner = width - 2f * pad;

            using (var surface = new D2D.SolidColorBrush(RenderTarget, Pigment(25, 35, 53, .93f)))
            using (var frame = new D2D.SolidColorBrush(RenderTarget, Pigment(50, 64, 87)))
            using (var status = new D2D.SolidColorBrush(RenderTarget, card.Accent))
            using (var text = new D2D.SolidColorBrush(RenderTarget, Pigment(237, 242, 252)))
            using (var muted = new D2D.SolidColorBrush(RenderTarget, Pigment(166, 181, 203)))
            using (var title = new DWrite.TextFormat(Core.Globals.DirectWriteFactory, "Segoe UI Semibold", 24f))
            using (var body = new DWrite.TextFormat(Core.Globals.DirectWriteFactory, "Segoe UI Semibold", 19f))
            using (var small = new DWrite.TextFormat(Core.Globals.DirectWriteFactory, "Segoe UI", 16f))
            using (var right = new DWrite.TextFormat(Core.Globals.DirectWriteFactory, "Consolas", 20f))
            {
                right.TextAlignment = DWrite.TextAlignment.Trailing;
                right.WordWrapping = DWrite.WordWrapping.NoWrap;
                RenderTarget.FillRectangle(new SharpDX.RectangleF(left, top, width, height), surface);
                RenderTarget.DrawRectangle(new SharpDX.RectangleF(left, top, width, height), frame, 1f);
                DrawCardLine("HY104 · Eval SIM", x, top + 8f, inner - 195f, 30f, title, text);
                DrawCardLine("Chicago " + card.Clock, x, top + 12f, inner, 26f, right, text);
                RenderTarget.FillRectangle(new SharpDX.RectangleF(x, top + 43f, inner, 1f), frame);
                RenderTarget.FillEllipse(new D2D.Ellipse(new SharpDX.Vector2(x + 5f, top + 63f), 4.5f, 4.5f), status);
                float timerArea = 0f;
                if (inner > 550f && card.MarketRemaining != null)
                    timerArea = 187f;
                if (inner > 460f && card.Countdown != "—")
                    timerArea += 145f;
                DrawCardLine(card.State, x + 16f, top + 51f, inner - timerArea - 18f, 29f, body, text);
                if (timerArea >= 187f && card.MarketRemaining != null)
                    DrawCardLine("Markt " + card.MarketRemaining, x + inner - timerArea, top + 54f, 174f, 25f, small, muted);
                if (inner > 460f && card.Countdown != "—")
                    DrawCardLine("Kerze " + card.Countdown, x + inner - 135f, top + 51f, 135f, 29f, right, text);
                float row = top + 82f;
                if (steps)
                {
                    DrawCardLine(card.Steps, x, row, inner, 27f, small, muted);
                    row += 28f;
                }
                if (detail)
                {
                    DrawCardLine(card.Detail, x, row, inner, 27f, small, text);
                    row += 28f;
                }
                if (levels.Length > 0)
                {
                    for (int i = 0; i < levels.Length; ++i)
                    {
                        DrawCardLine(levels[i].Trim(), x, row, inner, 26f, body, text);
                        row += 28f;
                    }
                }
            }
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

        private void RefreshSession(DateTime time)
        {
            if (!sessionFinished && sessionEnd != default(DateTime) && time >= sessionEnd)
                FinishSession();
            if (templateEnd != default(DateTime) && time < templateEnd)
                return;

            DateTime local = TimeZoneInfo.ConvertTime(DateTime.SpecifyKind(time, DateTimeKind.Unspecified), easternZone, platformZone);
            sessionIterator.GetNextSession(local, false);
            templateBegin = PlatformToEastern(sessionIterator.ActualSessionBegin);
            templateEnd = PlatformToEastern(sessionIterator.ActualSessionEnd);
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
        }

        private void FinishSession()
        {
            CommitBar();
            int expected = (int)((sessionEnd - sessionOpen).Ticks / FiveMinutes.Ticks);
            completeSessions = sessionComplete && committedBars == expected && expected > 0
                ? completeSessions + 1 : 0;
            sessionFinished = true;
        }

        private void ObserveOpeningRange(DateTime eventTime, double price, bool realtime)
        {
            if (!UsesOpeningRange || eventTime.Date != TestDay || eventTime < sessionOpen
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
            long elapsed = (time - sessionOpen).Ticks;
            DateTime bucket = sessionOpen.AddTicks(elapsed / FiveMinutes.Ticks * FiveMinutes.Ticks);
            if (barStart != bucket)
            {
                if ((!sessionSeenTrade && bucket != sessionOpen)
                    || (sessionSeenTrade && bucket != barStart + FiveMinutes))
                    sessionComplete = false;
                CommitBar();
                barStart = bucket;
                barHigh = barLow = price;
                sessionSeenTrade = true;
            }
            barHigh = Math.Max(barHigh, price);
            barLow = Math.Min(barLow, price);
            barClose = price;

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
                lastBand = contact;
                lastContactMark = touched;
            }
            else if (contact != 0 && setupSide == 0 && time.Date == TestDay && CurrentBar >= 0
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
            barStart = default(DateTime);
        }

        private bool CanEnter(DateTime time)
        {
            return time.Date == TestDay && !modelLossLatched && !entryBlocked && sessionComplete && completeSessions >= WarmupSessions
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
            pending = intent;
            Print(string.Format(CultureInfo.InvariantCulture,
                "HY104 SIGNAL {0:yyyy-MM-dd HH:mm:ss.fff} ET {1} {2} stop={3:F2}",
                intent.Time, intent.Reason, intent.Side > 0 ? "LONG" : "SHORT", intent.Stop));
        }

        private bool CheckModelLoss(DateTime time, bool useNewQuote)
        {
            if (!IsOrderAccount() || time.Date != TestDay || time < sessionOpen || sessionOpen.Date != TestDay)
                return false;
            double openNet = 0;
            if (positionSide != 0)
            {
                bool validBook = bidSize > 0 && askSize > 0 && bid > 0 && ask >= bid
                    && !double.IsInfinity(ask) && MarketTimeAgrees(time, bidClock) && MarketTimeAgrees(time, askClock);
                if (!validBook && !modelLossLatched)
                    return false;
                double liquidation = positionSide > 0 ? bid : ask;
                if (validBook)
                    openNet = positionSide * (liquidation - positionEntryPrice) * 50.0 - ModelFeePerSide;
            }
            double equity = OpeningModelBalance + modelRealized + openNet;
            if (!modelLossLatched && equity <= IntradayLossFloor + 0.0000001)
            {
                modelLossLatched = true;
                Print(string.Format(CultureInfo.InvariantCulture,
                    "Rapid EOD SIM: loss floor reached {0:F2} / {1:F2}; new entries blocked.",
                    equity, IntradayLossFloor));
            }
            if (!modelLossLatched)
                return false;
            if (pending != null && pending.IsEntry)
                pending = null;
            if (positionSide != 0 && !exitSubmissionFailed && submitted == null && pending == null)
                Queue(new Intent(false, positionSide, "RapidLoss", time, positionStop));
            // Watchdog may dispatch a pending liquidation even without a new quote.
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
                Print("HY104: session-close fallback.");
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
            submitted = pending;
            pending = null;
            return submitted;
        }

        private void Submit(Intent intent)
        {
            if (State != State.Realtime || !IsOrderAccount())
                return;
            if (!OrderConnectionReady())
            {
                lock (sync)
                {
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

            Order order;
            if (intent.IsEntry)
                order = intent.Side > 0 ? EnterLong(1, LongEntry) : EnterShort(1, ShortEntry);
            else
                order = intent.Side > 0 ? ExitLong(intent.OrderName, LongEntry) : ExitShort(intent.OrderName, ShortEntry);
            if (order == null)
                FailSubmission(intent, "NinjaTrader did not return an order. See the Log tab.");
            else
                Print("HY104 ORDER " + intent.OrderName + " " + order.OrderId);
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
                Print("HY104: " + message);
            }
        }

        protected override void OnOrderUpdate(Order order, double limitPrice, double stopPrice, int quantity,
            int filled, double averageFillPrice, OrderState orderState, DateTime time, ErrorCode error, string comment)
        {
            if (!IsOrderAccount())
                return;
            if (orderState != OrderState.Rejected && orderState != OrderState.Cancelled)
                return;
            lock (sync)
            {
                if (submitted != null && order.Name == submitted.OrderName && filled == 0)
                    FailSubmission(submitted, order.Name + " " + orderState + " " + error + " " + comment);
            }
        }

        protected override void OnExecutionUpdate(Execution execution, string executionId, double price, int quantity,
            MarketPosition marketPosition, string orderId, DateTime time)
        {
            if (!IsOrderAccount())
                return;
            lock (sync)
            {
                if (submitted == null || execution.Order == null || execution.Order.Name != submitted.OrderName)
                    return;
                Intent filled = submitted;
                if (quantity != 1)
                {
                    FailSubmission(filled, "Unexpected execution quantity " + quantity + ".");
                    return;
                }
                modelRealized -= ModelFeePerSide;
                if (!filled.IsEntry)
                    modelRealized += positionSide * (price - positionEntryPrice) * 50.0;
                UpdatePosition(filled, price);
                if (filled.IsEntry && filled.Marks != null && CurrentBar >= 0)
                {
                    filled.Marks.Fill = new SetupPoint(CurrentBar, price, filled.Side, filled.Time.Date);
                    confirmedEntryMarks.Add(filled.Marks);
                    if (confirmedEntryMarks.Count > 8)
                        confirmedEntryMarks.RemoveAt(0);
                }
                Print(string.Format(CultureInfo.InvariantCulture, "Rapid EOD SIM realized={0:F2}", modelRealized));
                submitted = null;
                Print(string.Format(CultureInfo.InvariantCulture,
                    "HY104 FILL {0:yyyy-MM-dd HH:mm:ss.fff} ET {1} {2} x{3} @ {4:F2}",
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
                    bool loss = CheckModelLoss(time, true);
                    next = TakePending(time, false, CheckClose(time) || loss);
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
            public readonly string Steps;
            public readonly SharpDX.Color4 Accent;

            public StatusCard(string account, string clock, string mode, string state,
                string detail, string levels, string countdown, string marketRemaining, SharpDX.Color4 accent, string steps)
            {
                Account = account;
                Clock = clock;
                Mode = mode;
                State = state;
                Detail = detail;
                Levels = levels;
                Countdown = countdown;
                MarketRemaining = marketRemaining;
                Steps = steps;
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
