package SQ.Blocks.OtherActions;

import SQ.Internal.ActionBlock;
import com.strategyquant.datalib.TradingException;
import com.strategyquant.tradinglib.BuildingBlock;
import com.strategyquant.tradinglib.ILiveOrder;
import com.strategyquant.tradinglib.OrderCloseTypes;
import com.strategyquant.tradinglib.OrderTypes;
import com.strategyquant.tradinglib.Parameter;
import com.strategyquant.tradinglib.ReturnTypes;
import com.strategyquant.tradinglib.StrategyBase;
import com.strategyquant.tradinglib.engine.BacktestTradingSetup;
import java.io.*;
import java.lang.reflect.Field;
import java.nio.file.*;
import java.util.*;
import java.util.zip.GZIPInputStream;

@BuildingBlock(name="HYML1ESResearch", display="HYML1ESResearch", returnType=ReturnTypes.Action)
public class HYML1ESResearch extends ActionBlock {
    private static final double INSTRUMENT_TICK = 0.25;
    @Parameter(name="Job directory", defaultValue="")
    public String JobDirectory;
    @Parameter(name="TargetOffsetTicks", defaultValue="0.75", minValue=-2, maxValue=3, step=0.25, decimals=2)
    public double TargetOffsetTicks;
    @Parameter(name="BollingerWidth", defaultValue="1.75", minValue=1, maxValue=3, step=0.05, decimals=2)
    public double BollingerWidth;
    @Parameter(name="StopAtrPad", defaultValue="0.15", minValue=0, maxValue=0.5, step=0.05, decimals=2)
    public double StopAtrPad;
    @Parameter(name="EntryFilterMode", defaultValue="0", minValue=0, maxValue=7, step=1, decimals=0)
    public double EntryFilterMode;
    @Parameter(name="IndicatorFilterMode", defaultValue="0", minValue=0, maxValue=5, step=1, decimals=0)
    public double IndicatorFilterMode;
    @Parameter(name="StrategyExtension", defaultValue="0", minValue=0, maxValue=62, step=1, decimals=0)
    public double StrategyExtension;
    @Parameter(name="VwapBandSigma", defaultValue="0", minValue=0, maxValue=4, step=0.5, decimals=2)
    public double VwapBandSigma;
    @Parameter(name="VwapWarmupMinutes", defaultValue="15", minValue=1, maxValue=60, step=1, decimals=0)
    public double VwapWarmupMinutes = 15;
    @Parameter(name="VwapGridCase", defaultValue="-1", minValue=-1, maxValue=10, step=1, decimals=0)
    public double VwapGridCase = -1;
    @Parameter(name="TpoGridCase", defaultValue="-1", minValue=-1, maxValue=10, step=1, decimals=0)
    public double TpoGridCase = -1;
    @Parameter(name="KerGridCase", defaultValue="-1", minValue=-1, maxValue=9, step=1, decimals=0)
    public double KerGridCase = -1;
    @Parameter(name="KamaGridCase", defaultValue="-1", minValue=-1, maxValue=6, step=1, decimals=0)
    public double KamaGridCase = -1;
    @Parameter(name="VolumeProfileGridCase", defaultValue="-1", minValue=-1, maxValue=4, step=1, decimals=0)
    public double VolumeProfileGridCase = -1;
    @Parameter(name="AdxExitGridCase", defaultValue="-1", minValue=-1, maxValue=6, step=1, decimals=0)
    public double AdxExitGridCase = -1;
    @Parameter(name="AtrStopGridCase", defaultValue="-1", minValue=-1, maxValue=3, step=1, decimals=0)
    public double AtrStopGridCase = -1;
    @Parameter(name="BarIndicatorGridCase", defaultValue="-1", minValue=-1, maxValue=6, step=1, decimals=0)
    public double BarIndicatorGridCase = -1;
    @Parameter(name="NqResearchCase", defaultValue="0", minValue=0, maxValue=4, step=1, decimals=0)
    public double NqResearchCase;
    @Parameter(name="NqEntryAverage", defaultValue="0", minValue=0, maxValue=2, step=1, decimals=0)
    public double NqEntryAverage;
    @Parameter(name="IntegrityMode", defaultValue="0", minValue=0, maxValue=1, step=1, decimals=0)
    public double IntegrityMode;
    @Parameter(name="RunReplica", defaultValue="0", minValue=0, maxValue=1, step=1, decimals=0)
    public double RunReplica;
    private Replay replay;
    private boolean replayFailed;

    @Override public void OnAction() throws TradingException {
        try {
            if (replay == null) {
                double extension = StrategyExtension, sigma = VwapBandSigma;
                if (VwapGridCase != -1) {
                    int c = (int) VwapGridCase;
                    if (c != VwapGridCase || c < 0 || c > 10)
                        throw new IllegalArgumentException("Invalid VWAP optimizer case: " + VwapGridCase);
                    if (c == 0) { extension = 0; sigma = 0; }
                    else if (c <= 3) { extension = 2; sigma = c * 0.5; }
                    else if (c <= 6) { extension = 3; sigma = (c - 3) * 0.5; }
                    else { extension = 1; sigma = (c - 5) * 0.5; }
                }
                int tpoCase = (int) TpoGridCase;
                if (tpoCase != TpoGridCase || tpoCase < -1 || tpoCase > 10)
                    throw new IllegalArgumentException("Invalid TPO optimizer case: " + TpoGridCase);
                if (tpoCase >= 0) {
                    require(VwapGridCase == -1 && StrategyExtension == 0, "One optimizer family per strategy");
                    extension = tpoCase == 0 ? 0 : 5;
                }
                int kerCase = (int) KerGridCase;
                if (kerCase != KerGridCase || kerCase < -1 || kerCase > 9)
                    throw new IllegalArgumentException("Invalid KER optimizer case: " + KerGridCase);
                if (kerCase >= 0) {
                    require(VwapGridCase == -1 && tpoCase == -1 && StrategyExtension == 0
                            && EntryFilterMode == 0 && IndicatorFilterMode == 0,
                            "One optimizer family per strategy");
                    extension = kerCase == 0 ? 0 : 6;
                }
                int kamaCase = (int) KamaGridCase;
                if (kamaCase != KamaGridCase || kamaCase < -1 || kamaCase > 6)
                    throw new IllegalArgumentException("Invalid KAMA optimizer case: " + KamaGridCase);
                if (kamaCase >= 0) {
                    require(VwapGridCase == -1 && tpoCase == -1 && kerCase == -1 && StrategyExtension == 0
                            && EntryFilterMode == 0 && IndicatorFilterMode == 0,
                            "One optimizer family per strategy");
                    extension = kamaCase == 0 ? 0 : 16;
                }
                int volumeCase = (int) VolumeProfileGridCase;
                if (volumeCase != VolumeProfileGridCase || volumeCase < -1 || volumeCase > 4)
                    throw new IllegalArgumentException("Invalid Volume Profile optimizer case: " + VolumeProfileGridCase);
                if (volumeCase >= 0) {
                    require(VwapGridCase == -1 && tpoCase == -1 && kerCase == -1 && kamaCase == -1
                            && StrategyExtension == 0 && EntryFilterMode == 0 && IndicatorFilterMode == 0,
                            "One optimizer family per strategy");
                    extension = volumeCase == 0 ? 0 : 4;
                }
                int adxCase = (int) AdxExitGridCase;
                int atrCase = (int) AtrStopGridCase;
                require(adxCase == AdxExitGridCase && adxCase >= -1 && adxCase <= 6, "Invalid ADX case");
                require(atrCase == AtrStopGridCase && atrCase >= -1 && atrCase <= 3, "Invalid ATR case");
                if (adxCase >= 0 || atrCase >= 0) {
                    require((adxCase < 0 || atrCase < 0) && VwapGridCase == -1 && tpoCase == -1
                            && kerCase == -1 && kamaCase == -1 && volumeCase == -1 && StrategyExtension == 0
                            && EntryFilterMode == 0 && IndicatorFilterMode == 0, "One optimizer family per strategy");
                    extension = adxCase > 0 ? 18 : atrCase > 0 ? 19 : 0;
                }
                int barCase = (int) BarIndicatorGridCase;
                require(barCase == BarIndicatorGridCase && barCase >= -1 && barCase <= 6,
                        "Invalid closed-bar indicator case");
                Path directory = Path.of(JobDirectory);
                BarRule barRule = loadBarRule(directory, barCase);
                if (barRule != null) {
                    require(adxCase == -1 && atrCase == -1 && VwapGridCase == -1 && tpoCase == -1
                            && kerCase == -1 && kamaCase == -1 && volumeCase == -1 && StrategyExtension == 0
                            && EntryFilterMode == 0 && IndicatorFilterMode == 0, "One optimizer family per strategy");
                    extension = barCase == 0 ? 0 : barRule.extension();
                }
                int researchCase = (int) NqResearchCase;
                require(researchCase == NqResearchCase && researchCase >= 0 && researchCase <= 4,
                        "Invalid NQ research case");
                int variant = (int) NqEntryAverage;
                require(variant == NqEntryAverage && variant >= 0 && variant <= 2 && (researchCase == 0 || researchCase == 3),
                        "TradeDay test must use frozen HY3");
                int maCase = switch (variant) { case 1 -> 5; case 2 -> 12; default -> 0; };
                replay = new Replay(getStrategy(), directory, TargetOffsetTicks,
                        BollingerWidth, StopAtrPad, EntryFilterMode, IndicatorFilterMode, extension,
                        sigma, VwapWarmupMinutes, tpoCase, kerCase, kamaCase, volumeCase, adxCase, atrCase, barRule, researchCase, maCase, (int)IntegrityMode);
            }
            replay.next();
        } catch (Exception e) {
            replayFailed = true;
            throw new TradingException("HYML1ESResearch: " + e.getMessage());
        }
    }

    @Override public void deinitialize() {
        try {
            if (replay != null && !replayFailed) replay.finish();
        } catch (Exception e) {
            throw new IllegalStateException("HYML1ESResearch: " + e.getMessage(), e);
        } finally {
            replay = null;
            replayFailed = false;
            super.deinitialize();
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new IllegalStateException(message);
    }

    record KerParameters(int period, double threshold) {}

    static KerParameters kerParametersForCase(int caseIndex) {
        if (caseIndex == -1 || caseIndex == 0) {
            return new KerParameters(10, 0.30);
        }
        require(caseIndex >= 1 && caseIndex <= 9, "Unknown KER case");
        int index = caseIndex - 1;
        int period = switch (index / 3) {
            case 0 -> 8;
            case 1 -> 10;
            default -> 14;
        };
        double threshold = switch (index % 3) {
            case 0 -> 0.20;
            case 1 -> 0.30;
            default -> 0.40;
        };
        return new KerParameters(period, threshold);
    }

    static boolean kerCrossedBelow(double previous, double current, double threshold) {
        return previous >= threshold && current < threshold;
    }

    record KamaParameters(int efficiencyPeriod, int fastPeriod, int slowPeriod) {}

    static KamaParameters kamaParametersForCase(int caseIndex) {
        return switch (caseIndex) {
            case 1 -> new KamaParameters(8, 2, 30);
            case 2 -> new KamaParameters(10, 2, 20);
            case -1, 0, 3 -> new KamaParameters(10, 2, 30);
            case 4 -> new KamaParameters(10, 3, 30);
            case 5 -> new KamaParameters(14, 2, 30);
            case 6 -> new KamaParameters(14, 2, 40);
            default -> throw new IllegalArgumentException("Unknown KAMA case");
        };
    }

    private record BarRule(String slug, int extension, int ordinal, String settings, double[] parameters) {
        double setting(int index, double fallback) {
            return index < parameters.length ? parameters[index] : fallback;
        }
    }

    private static BarRule loadBarRule(Path directory, int ordinal) throws IOException {
        Path grid = directory.resolve("closed-bar-cases.csv");
        require(Files.isRegularFile(grid) == (ordinal >= 0), "Closed-bar indicator case provenance mismatch");
        if (ordinal < 0) return null;
        var rows = Files.readAllLines(grid);
        require(ordinal < rows.size(), "Closed-bar case outside grid");
        String[] identity = rows.get(0).split(",", -1);
        require(identity.length == 2 && identity[0].matches("[a-z]+"), "Invalid closed-bar grid identity");
        String slug = identity[0];
        int mode = Integer.parseInt(identity[1]);
        int length = switch (slug) {
            case "rsi" -> mode == 20 ? 1 : 0;
            case "aroon" -> mode == 7 ? 2 : 0;
            case "vortex" -> mode == 8 ? 1 : 0;
            case "reflex" -> mode == 9 ? 1 : 0;
            case "wavetrend" -> mode == 10 ? 2 : 0;
            case "schaff" -> mode == 11 ? 2 : 0;
            case "qqe" -> mode == 12 ? 1 : 0;
            case "laguerre" -> mode == 13 ? 1 : 0;
            case "ulcer" -> mode == 14 ? 2 : 0;
            case "hma" -> mode == 15 ? 1 : 0;
            case "gann" -> mode == 17 ? 1 : 0;
            case "ema" -> mode == 21 ? 1 : 0;
            case "bollinger" -> mode == 22 ? 1 : 0;
            case "keltner" -> mode == 23 ? 1 : 0;
            case "rollingvwap" -> mode == 24 ? 1 : 0;
            case "averagevolume" -> mode == 25 ? 2 : 0;
            case "awesome" -> mode == 26 ? 2 : 0;
            case "barrange" -> mode == 27 ? 1 : 0;
            case "biggestrange" -> mode == 28 ? 1 : 0;
            case "smallestrange" -> mode == 29 ? 1 : 0;
            case "openingrange" -> mode == 30 ? 1 : 0;
            case "bullbearpower" -> mode == 31 ? 1 : 0;
            case "cci" -> mode == 32 ? 2 : 0;
            case "demarker" -> mode == 33 ? 1 : 0;
            case "directional" -> mode == 34 ? 2 : 0;
            case "fibo" -> mode == 35 ? 1 : 0;
            case "fractal" -> mode == 36 ? 1 : 0;
            case "heikenashi" -> mode == 37 ? 1 : 0;
            case "highlow" -> mode == 38 ? 1 : 0;
            case "highlowindex" -> mode == 39 ? 1 : 0;
            case "ichimoku" -> mode == 40 ? 3 : 0;
            case "linreg" -> mode == 41 ? 1 : 0;
            case "macd" -> mode == 42 ? 3 : 0;
            case "mtatr" -> mode == 43 ? 1 : 0;
            case "mtkeltner" -> mode == 44 ? 1 : 0;
            case "momentum" -> mode == 45 ? 1 : 0;
            case "ma" -> mode == 46 ? 1 : 0;
            case "sma" -> mode == 47 ? 1 : 0;
            case "lwma" -> mode == 48 ? 1 : 0;
            case "smma" -> mode == 49 ? 1 : 0;
            case "tema" -> mode == 50 ? 1 : 0;
            case "osma" -> mode == 51 ? 2 : 0;
            case "psar" -> mode == 52 ? 2 : 0;
            case "pivots" -> mode == 53 ? 1 : 0;
            case "roc" -> mode == 54 ? 1 : 0;
            case "srpercrank" -> mode == 55 ? 2 : 0;
            case "stddev" -> mode == 56 ? 1 : 0;
            case "stochastic" -> mode == 57 ? 3 : 0;
            case "supertrend" -> mode == 58 ? 2 : 0;
            case "truerange" -> mode == 59 ? 1 : 0;
            case "williams" -> mode == 60 ? 1 : 0;
            case "bbrange" -> mode == 61 ? 2 : 0;
            case "bbwidth" -> mode == 62 ? 1 : 0;
            default -> 0;
        };
        require(length > 0 && Files.isRegularFile(directory.resolve(slug + "-grid-experiment")),
                "Invalid closed-bar grid strategy");
        String settings = rows.get(ordinal);
        double[] parameters = ordinal == 0 ? new double[0] :
                java.util.Arrays.stream(settings.split(",", -1)).mapToDouble(Double::parseDouble).toArray();
        require(ordinal == 0 || (parameters.length == length &&
                java.util.Arrays.stream(parameters).allMatch(Double::isFinite)), "Invalid closed-bar parameter row");
        return new BarRule(slug, mode, ordinal, settings, parameters);
    }

    private record ClosedRange(double high, double low) {}

    private record Intent(int side, long time, int stop, String reason) {
        boolean entry() { return reason.equals("first_return"); }
    }

    private record Position(ILiveOrder order, int side, int price, long time, long signal, int stop) {}

    private static final class Replay {
        private static final long SECOND = 1_000_000_000L;
        private final long barWidth;
        private final String targetRule;
        private final StrategyBase strategy;
        private final Path result;

        // Entry eligibility only. Setup consumption and all exit paths remain unchanged.
        private final int integrityMode;
        private int historyConsecutive, historyObserved, historyLastSlot = -1;
        private long historyOpen, historyClose;
        private boolean historyComplete, historySeen;
        private boolean historyCalendarValid = true;
        private final NavigableMap<Long,Long> historyCalendar = new TreeMap<>();
        private long historyBlockedReturns;
        private final StringBuilder historyAudit = new StringBuilder(
                "day_open_ns,prior_complete,observed,expected,complete,phase\n");

        private void historyStart(long opening, long closing) {
            if (historyOpen != 0) {
                int expected = Math.toIntExact((historyClose-historyOpen) / (300*SECOND));
                boolean complete = historyComplete && historySeen && historyObserved == expected;
                historyAudit.append(historyOpen).append(',').append(historyConsecutive).append(',')
                    .append(historyObserved).append(',').append(expected).append(',').append(complete)
                    .append(",completed\n");
                historyConsecutive = complete ? historyConsecutive+1 : 0;
                Long expectedNext = historyCalendar.higherKey(historyOpen);
                if (expectedNext == null || expectedNext.longValue() != opening)
                    historyConsecutive = 0;
            }
            historyOpen = opening;
            historyClose = closing;
            historyObserved=0;
            historyLastSlot=-1;
            historyComplete=closing>opening;
            historyCalendarValid = historyCalendar.containsKey(opening)
                    && historyCalendar.get(opening).longValue() == closing;
            historySeen=false;
        }

        private void historyObserve(long ns) {
            int slot = Math.toIntExact((ns-historyOpen)/(300*SECOND));
            if (!historySeen || slot != historyLastSlot) {
                if ((!historySeen && slot != 0) || (historySeen && slot != historyLastSlot+1))
                    historyComplete=false;
                historyObserved++;
                historyLastSlot=slot;
                historySeen=true;
            }
        }

        private boolean historyAllows() {
            boolean ready = historyConsecutive>=5 && historyComplete && historySeen && historyCalendarValid;
            if (integrityMode==1 && !ready) historyBlockedReturns++;
            return integrityMode==0 || ready;
        }

        private final BufferedReader tape, seeds;
        private final PrintWriter trades;

        // Research-only inventory of every eligible return, including returns
        // ignored by the baseline while its one native position is occupied.
        // This does not send orders or change the original Replay state.
        private final PrintWriter candidateTrades, candidateMarks, nativeRisks, signalQuotes, mlFeatures;
        private final Map<Long,Boolean> mlDecisions = new HashMap<>();
        private boolean mlGated = false;
        private long mlVolume = 0;
        private double mlLastEma = Double.NaN, mlPrevEma = Double.NaN, mlClosedAtr = Double.NaN;
        private double mlRelativeVolume = Double.NaN;
        private final Deque<Long> mlVolumes = new ArrayDeque<>();
        private final boolean providerTradeDay;
        private final ArrayList<Intent> candidateEntries = new ArrayList<>();
        private final ArrayList<Shadow> candidates = new ArrayList<>();
        private int candidateId;
        private static final class Shadow {
            final int id, side, price, stop;
            final long signal, time, startBar;
            Intent exit;
            long low = Long.MAX_VALUE;
            Shadow(int id, Intent intent, int entry, long ns, long startBar) {
                this.id=id;side=intent.side();price=entry;stop=intent.stop();
                signal=intent.time();time=ns;this.startBar=startBar;
            }
        }
        private void candidateDeadlines(long ns) {
            if (ns>=flatten) {
                candidateEntries.clear();
                for (Shadow s:candidates) if(s.exit==null)
                    s.exit=new Intent(s.side,flatten,0,"session_end");
            }
            if(newsIndex<newsWindows.size()) {
                long begin=newsWindows.get(newsIndex)[0];
                if(ns>=begin-newsLead) {
                    candidateEntries.clear();
                    for(Shadow s:candidates)
                        if(s.exit==null || !s.exit.reason().equals("t1_preclose") && s.exit.time()>begin-newsLead)
                            s.exit=new Intent(s.side,ns,0,"t1_preclose");
                }
            }
        }
        private void candidateUseTrade(long ns,int print,double last) {
            for(Shadow s:candidates) {
                if(s.exit!=null)continue;
                String reason=null;
                if(pastStop(s.side,print,s.stop))reason="stop";
                else {
                    Position shadowPosition=new Position(null,s.side,s.price,s.time,s.signal,s.stop);
                    reason=targetReason(ns,last,shadowPosition);
                    if(reason==null && extension==30 && ns-dayOpen>=openingRangeDuration && openingLow<=openingHigh) {
                        double level=(s.side==1?openingHigh:openingLow)*INSTRUMENT_TICK;
                        if(s.side*(level/INSTRUMENT_TICK-s.price)>=1 && s.side*(last-level)>=0)
                            reason="opening_range_target";
                    }
                    if(reason==null && extension==54) {
                        var c=extraBars.latest();var p=extraBars.previous();
                        if(c.endNs()>s.startBar && s.side*p.main()>=0 && s.side*c.main()<0)
                            reason="indicator_exit_54";
                    }
                }
                if(reason!=null)s.exit=new Intent(s.side,ns,0,reason);
            }
        }
        private void candidateMark(Shadow s,long ns,int bid,int ask) {
            long gross=(long)s.side*((s.side==1?bid:ask)-s.price)* 1250;
            if(gross<s.low) {
                s.low=gross;
                candidateMarks.printf(Locale.ROOT,"%d,%d,%d%n",s.id,ns,gross);
            }
        }
        private void candidateUseQuote(long ns,int bid,int ask) {
            for(var it=candidates.iterator();it.hasNext();) {
                Shadow s=it.next();candidateMark(s,ns,bid,ask);
                if(s.exit!=null && ns>=s.exit.time()+2*SECOND) {
                    int px=s.side==1?bid:ask;
                    candidateTrades.printf(Locale.ROOT,"%d,%s,%d,%d,%d,%d,%d,%d,%d,%s,%d%n",
                        s.id,s.side==1?"LONG":"SHORT",s.signal,s.time,s.price*25L,s.stop*25L,
                        s.exit.time(),ns,px*25L,s.exit.reason(),(long)s.side*(px-s.price)* 1250- 468);
                    it.remove();
                }
            }
            for(var it=candidateEntries.iterator();it.hasNext();) {
                Intent e=it.next();if(ns<e.time()+2*SECOND)continue;it.remove();
                int executable=e.side()==1?bid:ask;
                if(ns>=flatten || !allowsEntry(e.side(),ns) || pastStop(e.side(),executable,e.stop()))continue;
                Shadow s=new Shadow(candidateId++,e,e.side()==1?ask:bid,ns,extraBars==null?closedTime:extraBars.latest().endNs());
                candidates.add(s);candidateMark(s,ns,bid,ask);
            }
        }

        private final double targetOffset, bollingerWidth, stopAtrMultiplier;
        private final long expected;
        private final int filterMode;
        private final int indicatorMode;
        private final SqxCompletedBarIndicators indicators;
        private final int extension;
        private final BufferedReader sizes;
        private final SqxSessionVwap vwap;
        private final SqxRollingVwap rollingVwap;
        private final String[] volumeHistory;
        private final String volumeHistoryDigest;
        private final int volumeLookback;
        private final double volumeThreshold;
        private final int rangeLookback;
        private final double rangeThreshold;
        private final ArrayDeque<Double> recentRanges = new ArrayDeque<>();
        private final long openingRangeDuration, openingEntryDelay, riskLimitCents;
        private final int researchCase, maCase;
        private long layerSetupTime;
        private boolean outerBroken;
        private long riskRejected, largestAcceptedRiskCents;
        private final long[] expectedVolume = new long[90];
        private long barVolume, lastBarVolume;
        private int lastVolumeSlot = -1;
        private int openingHigh, openingLow;
        private final int recentPriceBars;
        private final ArrayDeque<ClosedRange> closedRanges = new ArrayDeque<>();
        private final double fiboFraction;
        private final String priorRangeSource;
        private final long[] priorRangeSeed;
        private int dayHigh, dayLow, dayLast, priorDayHigh, priorDayLow, priorDayLast;
        private double previousClosedAtr = Double.NaN;
        private double previousClosedPrice = Double.NaN, closedPrice = Double.NaN;
        private final ArrayDeque<Double> widthReference = new ArrayDeque<>();
        private double widthRank = Double.NaN;
        private boolean stochasticExtreme;
        private long stochasticCheckedBar;
        private double fractalHigh = Double.NaN, fractalLow = Double.NaN;
        private int consecutiveHa, lastHaSide;
        private final double vwapBandSigma;
        private final SqxSessionPriceProfile profile;
        private final boolean volumeGrid;
        private final boolean volumePointTarget;
        private final int volumeValueAreaPercent;
        private final Path volumeSeed;
        private final boolean volumeSeedExternal;
        private String volumeSeedReceipt;
        private long volumeWarmupOpen = -1, volumeWarmupClose = -1;
        private final SqxParametricTpoProfile tpo;
        private final boolean tpoPointTarget;
        private final Path tpoSeed;
        private final boolean tpoSeedExternal;
        private String tpoSeedReceipt;
        private long tpoWarmupOpen = -1, tpoWarmupClose = -1;
        private final SqxExtensionBarIndicators extraBars;
        private final int adxPeriod, adxThreshold;
        private final BarRule barRule;
        private final int entryEmaPeriod, targetBollingerPeriod;
        private final double contactMultiplier, mtKeltnerDeviation;
        private final ArrayDeque<Double> mtKeltnerRanges = new ArrayDeque<>();
        private double mtRangeSum, mtCloseSum;
        private final String mtSeedDigest;
        private final int[] firstContact;
        private final ArrayDeque<Double> targetCloses = new ArrayDeque<>();
        private double entryEma = Double.NaN;
        private final double atrStopMultiplier;
        private final KerParameters kerParameters;
        private final boolean reportKerParameters;
        private final KamaParameters kamaParameters;
        private final boolean reportKamaParameters;
        private long tradeSizesRead;
        private double setupEntryLevel = Double.NaN;
        private long confirmationBar = -1, positionStartBar = -1;
        private int extensionEntries, extensionStops, extensionTargets;
        private final List<long[]> newsWindows = new ArrayList<>();
        private final long newsLead = 10 * SECOND;
        private int newsIndex;
        private final ArrayDeque<Double> closes = new ArrayDeque<>();
        private final ArrayList<Double> initialRanges = new ArrayList<>(10);
        private long dayOpen = -1, sessionClose, flatten, bar = -1, previous, seen;
        private long quoteTime, closedTime, earlierClosedTime;
        private int quoteBid, quoteAsk;
        private double closedUpper, closedLower, earlierClosedUpper, earlierClosedLower;
        private int dayIndex = -1, lastBand, setupSide, open, high, low, close, roundTrips;
        private int indicatorAccepted, indicatorBlocked;
        private double ema, atr, previousClose;
        private boolean firstBar, flatRequested, sessionClosed, warmup;
        private Intent intent;
        private Position position;

        Replay(StrategyBase strategy, Path directory, double ticks, double sigma, double pad,
               double entryFilter, double indicatorFilter, double strategyExtension,
               double vwapSigma, double vwapWarmupMinutes, int tpoCase, int kerCase, int kamaCase, int volumeCase,
               int adxCase, int atrCase, BarRule barRule, int researchCase, int maCase, int integrityMode) throws Exception {
            this.strategy = strategy;
            this.barRule = barRule;
            this.researchCase = researchCase;
            this.maCase = maCase;
            String provider=Files.readString(directory.resolve("provider.txt")).strip();
            require(provider.equals("TradeDay") || provider.equals("MFF"),"Unknown provider policy");
            providerTradeDay=provider.equals("TradeDay");
            Path initial=directory.resolve("history-initial-count.txt");
            if(Files.isRegularFile(initial))historyConsecutive=Integer.parseInt(Files.readString(initial).strip());
            require(historyConsecutive>=0 && historyConsecutive<=5,"Invalid externally attested warmup count");
            require(integrityMode==1 && ((strategyExtension==54 && researchCase==3) || ((strategyExtension==0 || strategyExtension==30) && researchCase==0)),"Only frozen HY3 or HY104/OR inventory is supported");
            require(integrityMode==0 || integrityMode==1, "Invalid history gate mode");
            this.integrityMode=integrityMode;
            for (String expectedSession : Files.readAllLines(directory.resolve("history-expected-sessions.csv"))) {
                String[] fields=expectedSession.split(",");
                require(fields.length==2,"Invalid expected-session calendar row");
                long opening=Long.parseLong(fields[0]), closing=Long.parseLong(fields[1]);
                require(closing>opening && historyCalendar.put(opening,closing)==null,"Invalid expected-session calendar");
            }

            riskLimitCents = switch (researchCase) {
                case 1 -> 75000;
                case 2 -> 100000;
                default -> Long.MAX_VALUE;
            };
            openingEntryDelay = researchCase == 3 ? 30 * 60 * SECOND : 0;
            Field setup = StrategyBase.class.getDeclaredField("tradingSetup");
            setup.setAccessible(true);
            require(setup.get(strategy) instanceof BacktestTradingSetup, "Historical retester only");
            require(Math.abs(strategy.BigPointValue() - 50) < 1e-9, "Unexpected contract point value");
            var cfg = Files.readAllLines(directory.resolve("manifest.txt"));
            require(cfg.size() == 4, "Manifest fields");
            Path variantFile = directory.resolve("annual-hypothesis.txt");
            String hypothesis = Files.isRegularFile(variantFile) ? Files.readString(variantFile).strip() : "HY18b";
            require(Set.of("HY18b", "HY53b", "HY120", "HY121").contains(hypothesis), "Unknown annual hypothesis");
            barWidth = (hypothesis.equals("HY53b") ? 40 : 300) * SECOND;
            targetRule = hypothesis;
            targetOffset = ticks * INSTRUMENT_TICK;
            bollingerWidth = sigma;
            stopAtrMultiplier = 2 + pad;
            require(entryFilter == Math.rint(entryFilter) && entryFilter >= 0 && entryFilter <= 7, "Unknown entry filter");
            filterMode = (int) entryFilter;
            require(indicatorFilter == Math.rint(indicatorFilter) && indicatorFilter >= 0 && indicatorFilter <= 5,
                    "Unknown indicator filter");
            indicatorMode = (int) indicatorFilter;
            require(strategyExtension == Math.rint(strategyExtension) && strategyExtension >= 0 && strategyExtension <= 62,
                    "Unknown strategy extension");
            extension = (int) strategyExtension;
            require(extension == 0 || (filterMode == 0 && indicatorMode == 0), "One modification per strategy");
            require(Double.isFinite(vwapSigma) && vwapSigma >= 0 && vwapSigma <= 4
                            && vwapWarmupMinutes == Math.rint(vwapWarmupMinutes)
                            && vwapWarmupMinutes >= 1 && vwapWarmupMinutes <= 60, "Invalid VWAP settings");
            vwapBandSigma = vwapSigma == 0 ? (extension == 1 ? 2 : 1) : vwapSigma;
            vwap = extension >= 1 && extension <= 3 ? new SqxSessionVwap((int) vwapWarmupMinutes) : null;
            boolean tpoGrid = Files.exists(directory.resolve("tpo-grid-experiment"));
            require(tpoGrid == (tpoCase >= 0), "TPO case provenance mismatch");
            volumeGrid = Files.exists(directory.resolve("volume-profile-grid-experiment"));
            require(volumeGrid == (volumeCase >= 0), "Volume Profile case provenance mismatch");
            volumePointTarget = volumeCase <= 1;
            volumeValueAreaPercent = switch (volumeCase) {
                case 2 -> 60;
                case 4 -> 80;
                default -> 70;
            };
            profile = !tpoGrid && (extension == 4 || extension == 5)
                    ? new SqxSessionPriceProfile(extension, volumeValueAreaPercent) : null;
            volumeSeed = directory.resolve("volume-profile-previous-rth.csv");
            volumeSeedExternal = volumeGrid && profile != null && Files.size(volumeSeed) > 0;
            int bracket = tpoCase == 10 ? 30 : (15 << ((Math.max(1,tpoCase)-1)/3));
            int area = tpoCase == 10 ? 70 : 60 + 10 * ((Math.max(1,tpoCase)-1)%3);
            tpo = tpoCase > 0 ? new SqxParametricTpoProfile(bracket, area) : null;
            tpoPointTarget = tpoCase == 10;
            tpoSeed = directory.resolve("tpo-previous-rth.csv");
            tpoSeedExternal = tpo != null && Files.size(tpoSeed) > 0;
            boolean kerGrid = Files.exists(directory.resolve("ker-grid-experiment"));
            require(kerGrid == (kerCase >= 0), "KER case provenance mismatch");
            kerParameters = kerParametersForCase(kerCase);
            reportKerParameters = kerGrid && extension == 6;
            boolean kamaGrid = Files.exists(directory.resolve("kama-grid-experiment"));
            require(kamaGrid == (kamaCase >= 0), "KAMA case provenance mismatch");
            kamaParameters = kamaParametersForCase(kamaCase);
            reportKamaParameters = kamaGrid && extension == 16;
            boolean adxGrid = Files.exists(directory.resolve("adx-grid-experiment"));
            boolean atrGrid = Files.exists(directory.resolve("atr-grid-experiment"));
            require(adxGrid == (adxCase >= 0) && (extension == 18) == (adxCase > 0), "ADX case provenance mismatch");
            require(atrGrid == (atrCase >= 0) && (extension == 19) == (atrCase > 0), "ATR case provenance mismatch");
            adxPeriod = extension == 34 ? (int) barRule.setting(0, 14)
                    : switch (adxCase) { case 1, 2 -> 10; case 5, 6 -> 20; default -> 14; };
            adxThreshold = adxCase > 0 && adxCase % 2 == 0 ? 22 : 18;
            atrStopMultiplier = atrCase > 0 ? 0.5 + 0.5 * atrCase : Double.NaN;
            entryEmaPeriod = switch (maCase) {
                case 1, 2, 3 -> 16 + maCase;
                case 4, 5, 6 -> 17 + maCase;
                default -> 20;
            };
            targetBollingerPeriod = extension == 22 ? (int) barRule.setting(0, 20) : 20;
            require(entryEmaPeriod >= 2 && entryEmaPeriod <= 60 && targetBollingerPeriod >= 2
                    && targetBollingerPeriod <= 60, "Unsupported entry EMA or target Bollinger period");
            contactMultiplier = extension == 23 ? barRule.setting(0, 2.0) : 2.0;
            mtKeltnerDeviation = extension == 44 ? barRule.setting(0, 1.5) : Double.NaN;
            if (extension == 44) {
                var file = directory.resolve("mt-keltner-contact.csv");
                firstContact = readFirstContact(file, mtKeltnerDeviation);
                mtSeedDigest = HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256")
                        .digest(Files.readAllBytes(file)));
            } else {
                firstContact = contactMultiplier == 2.0 ? null
                        : readFirstContact(directory.resolve("keltner-first-contact.csv"), contactMultiplier);
                mtSeedDigest = null;
            }
            extraBars = (extension >= 6 && extension <= 20 && extension != 19) || extension == 26 || (extension >= 31 && extension <= 34)
                    || extension == 37 || (extension >= 40 && extension != 44 && extension != 53)
                    ? new SqxExtensionBarIndicators(extension,
                    kerParameters.period(), kamaParameters.efficiencyPeriod(), kamaParameters.fastPeriod(),
                    kamaParameters.slowPeriod(), adxPeriod, barRule == null ? new double[0] : barRule.parameters()) : null;
            recentPriceBars = switch (extension) {
                case 36, 38 -> (int) barRule.setting(0, 5);
                case 39 -> 12;
                default -> 0;
            };
            fiboFraction = extension == 35 ? barRule.setting(0, 50) / 100.0 : Double.NaN;
            priorDayHigh = Integer.MIN_VALUE;
            priorDayLow = Integer.MAX_VALUE;
            if (usesPriorRange()) {
                byte[] input = Files.readAllBytes(directory.resolve("previous-rth-range.csv"));
                priorRangeSource = HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(input));
                priorRangeSeed = input.length == 0 ? null : Arrays.stream(new String(input,
                        java.nio.charset.StandardCharsets.US_ASCII).strip().split(",")).mapToLong(Long::parseLong).toArray();
            } else {
                priorRangeSource = null;
                priorRangeSeed = null;
            }
            rollingVwap = extension == 24 ? new SqxRollingVwap((int) barRule.setting(0, 20)) : null;
            var volumeFile = directory.resolve("average-volume-history.csv");
            if (extension == 25) {
                byte[] input = Files.readAllBytes(volumeFile);
                volumeHistoryDigest = HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(input));
                volumeHistory = new String(input, java.nio.charset.StandardCharsets.US_ASCII).split("\n");
                volumeLookback = (int) barRule.setting(0, 10);
                volumeThreshold = barRule.setting(1, 1.25);
                require(volumeLookback == 10 || volumeLookback == 20, "Invalid Average Volume window");
            } else {
                volumeHistory = null;
                volumeHistoryDigest = null;
                volumeLookback = 0;
                volumeThreshold = Double.NaN;
            }
            rangeLookback = extension == 27 ? 1 : extension == 28 || extension == 29 ? (int) barRule.setting(0, 3) : 0;
            rangeThreshold = extension == 27 ? barRule.setting(0, 2.0) : extension == 28 ? 2.5 : 0.25;
            openingRangeDuration = researchCase == 4 ? 60 * 60 * SECOND
                    : extension == 30 ? (long) barRule.setting(0, 15) * 60 * SECOND : 0;
            sizes = true /* research observer consumes the attested trade-size stream */
                    ? new BufferedReader(new InputStreamReader(
                    new GZIPInputStream(Files.newInputStream(directory.resolve("trade-sizes.csv.gz"))))) : null;
            indicators = indicatorMode == 0 ? null : new SqxCompletedBarIndicators();
            if (indicators != null || extraBars != null || rangeLookback > 0 || recentPriceBars > 0 || extension == 44
                    || entryEmaPeriod != 20 || targetBollingerPeriod != 20) {
                long warmupBar = Long.MIN_VALUE;
                var rows = Files.readAllLines(directory.resolve("indicator-warmup.csv"));
                List<String> opens = extension == 37 ?
                        Files.readAllLines(directory.resolve("indicator-warmup-opens.csv")) : null;
                if (opens != null) require(opens.size() == rows.size(), "Misaligned Heiken Ashi warmup");
                for (int i = 0; i < rows.size(); i++) {
                    String line = rows.get(i);
                    String[] values = line.split(",");
                    require(values.length == 3, "Unexpected indicator warmup row");
                    double warmupClose = Integer.parseInt(values[2]) * INSTRUMENT_TICK;
                    double warmupOpen = opens == null ? warmupClose : Integer.parseInt(opens.get(i)) * INSTRUMENT_TICK;
                    updateClosedIndicators(++warmupBar, warmupOpen, Integer.parseInt(values[0]) * INSTRUMENT_TICK,
                            Integer.parseInt(values[1]) * INSTRUMENT_TICK, warmupClose);
                    updateEntryAndTargetHistory(warmupClose);
                }
            }
            expected = Long.parseLong(cfg.get(1));
            Path newsFile = directory.resolve("news-windows.csv");
            if (Files.isRegularFile(newsFile)) {
                for (String line : Files.readAllLines(newsFile)) {
                    String[] fields = line.split(",");
                    require(fields.length == 3, "Malformed news window");
                    long lo = Long.parseLong(fields[0]), hi = Long.parseLong(fields[1]);
                    require(lo < hi && (newsWindows.isEmpty() || lo - newsLead > newsWindows.get(newsWindows.size()-1)[1]),
                            "Conflicting news windows");
                    newsWindows.add(new long[]{lo, hi});
                }
            }
            seeds = Files.newBufferedReader(Path.of(cfg.get(2)));
            tape = new BufferedReader(new InputStreamReader(
                new GZIPInputStream(Files.newInputStream(Path.of(cfg.get(3))))), 128 * 1024);
            String variant = barRule != null ? barRule.slug() + "_" + barRule.ordinal() + "_"
                    : adxGrid ? "adx_" + adxCase + "_"
                    : atrGrid ? "atr_" + atrCase + "_"
                    : volumeGrid ? "vp_" + volumeCase + "_"
                    : kamaGrid ? "kama_" + kamaCase + "_"
                    : kerGrid ? "ker_" + kerCase + "_"
                    : tpoGrid ? "tpo_" + tpoCase + "_"
                    : Files.exists(directory.resolve("vwap-grid-experiment")) ?
                    extension + "_" + vwapSigma + "_" + (int) vwapWarmupMinutes + "_"
                    : Files.exists(directory.resolve("strategy-extension-experiment")) ? extension + "_"
                    : Files.exists(directory.resolve("indicator-filter-experiment")) ? indicatorMode + "_"
                    : Files.exists(directory.resolve("entry-filter-experiment")) ? filterMode + "_" : "";
            variant += "nqresearch_" + researchCase + "_ma_" + maCase + "_";
            variant += "history_"+integrityMode+"_";
            result = directory.resolve("native_export_" + ticks + "_" + sigma + "_" + pad + "_" + variant + UUID.randomUUID());
            Files.createDirectory(result);
            trades = new PrintWriter(Files.newBufferedWriter(result.resolve("trades.csv")));
            trades.println("side,entry_decision_ns,entry_time_ns,entry_price_cents,exit_decision_ns,exit_time_ns,exit_price_cents,exit_reason,net_pnl_cents");
            candidateTrades=new PrintWriter(Files.newBufferedWriter(result.resolve("candidates.csv")));
            candidateTrades.println("id,side,entry_decision_ns,entry_time_ns,entry_price_cents,stop_price_cents,exit_decision_ns,exit_time_ns,exit_price_cents,exit_reason,net_pnl_cents");
            candidateMarks=new PrintWriter(Files.newBufferedWriter(result.resolve("candidate-mae.csv")));
            candidateMarks.println("id,timestamp_ns,gross_cents");
            nativeRisks=new PrintWriter(Files.newBufferedWriter(result.resolve("native-entry-risks.csv")));
            nativeRisks.println("entry_time_ns,entry_price_cents,stop_price_cents,planned_risk_cents");
            signalQuotes=new PrintWriter(Files.newBufferedWriter(result.resolve("signal-quotes.csv")));
            signalQuotes.println("signal_ns,side,quote_ns,bid_ticks,ask_ticks,stop_ticks");
            mlFeatures = new PrintWriter(Files.newBufferedWriter(result.resolve("ml-features.csv")));
            mlFeatures.println("signal_ns,side,quote_ns,planned_stop_risk_usd,bollinger_keltner_width_ratio,signed_completed_ema_slope_atr,completed_relative_volume20,chicago_session_minute");
            Path decisionFile=directory.resolve("ml-decisions.csv");
            mlGated=Files.isRegularFile(decisionFile);
            if(mlGated) {
                for(String line:Files.readAllLines(decisionFile)) {
                    if(line.startsWith("signal_ns,"))continue;
                    String[] values=line.split(",");
                    require(values.length==2,"Invalid ML decision row");
                    long ns=Long.parseLong(values[0]);
                    require(values[1].equals("0")||values[1].equals("1"),"Invalid ML decision");
                    require(mlDecisions.put(ns,values[1].equals("1"))==null,"Duplicate ML decision");
                }
            }
        }

        private boolean usesPriorRange() {
            return extension == 35 || extension == 53;
        }

        private static int[] readFirstContact(Path file, double factor) throws IOException {
            var rows = Files.readAllLines(file);
            if (rows.isEmpty()) return null; // The five preceding native tape sessions supply the state.
            require(rows.size() == 3, "Invalid Keltner warmup state");
            for (String row : rows) {
                var fields = row.split(",");
                require(fields.length == 3, "Invalid Keltner warmup row");
                if (Double.parseDouble(fields[0]) != factor) continue;
                int band = Integer.parseInt(fields[1]), setup = Integer.parseInt(fields[2]);
                require(Math.abs(band) <= 1 && Math.abs(setup) <= 1, "Invalid warmup band sides");
                return new int[]{band, setup};
            }
            throw new IllegalArgumentException("Missing Keltner-contact warmup for factor " + factor);
        }

        void startDay(int day) throws IOException {
            require(candidates.isEmpty() && candidateEntries.isEmpty(),"Inventory open at prior session end");
            require(position == null && intent == null && (dayIndex < 0 || sessionClosed), "Incomplete prior session");
            require(day == dayIndex + 1, "Nonconsecutive session index");
            String line = seeds.readLine();
            require(line != null, "Missing session state");
            String[] seed = line.split(",");
            require(seed.length == 27 || seed.length == 4, "Unexpected session state columns");
            dayIndex = day;
            dayOpen = Long.parseLong(seed[0]);
            if (usesPriorRange()) {
                if (day > 0) {
                    require(dayLow <= dayHigh, "No trades in prior instrument session");
                    priorDayHigh = dayHigh;
                    priorDayLow = dayLow;
                    priorDayLast = dayLast;
                } else if (priorRangeSeed != null) {
                    require((priorRangeSeed.length == 6 || extension == 35 && priorRangeSeed.length == 5)
                            && priorRangeSeed[0] < priorRangeSeed[1]
                            && priorRangeSeed[1] <= priorRangeSeed[2] && priorRangeSeed[2] == dayOpen
                            && priorRangeSeed[3] >= priorRangeSeed[4] && priorRangeSeed[4] > 0,
                            "Invalid previous-session range source");
                    priorDayHigh = Math.toIntExact(priorRangeSeed[3]);
                    priorDayLow = Math.toIntExact(priorRangeSeed[4]);
                    if (priorRangeSeed.length == 6) {
                        priorDayLast = Math.toIntExact(priorRangeSeed[5]);
                        require(priorDayLast >= priorDayLow && priorDayLast <= priorDayHigh, "Invalid predecessor close");
                    }
                } else {
                    require(seed.length == 4 && seed[3].equals("warmup"),
                            "No replay or seed for previous-session range");
                }
                dayHigh = Integer.MIN_VALUE;
                dayLow = Integer.MAX_VALUE;
            }
            consecutiveHa = 0;
            lastHaSide = 0;
            if (vwap != null) vwap.reset(dayOpen);
            if (rollingVwap != null) rollingVwap.reset(dayOpen);
            lastVolumeSlot = -1;
            if (volumeHistory != null) {
                require(day < volumeHistory.length, "Missing preceding RTH volumes");
                String[] row = volumeHistory[day].split(",");
                require(row.length == 181 && Integer.parseInt(row[0]) == day, "Misaligned Average Volume source");
                int offset = volumeLookback == 10 ? 1 : 91;
                for (int i = 0; i < expectedVolume.length; i++) {
                    expectedVolume[i] = Long.parseLong(row[offset + i]);
                }
            }
            openingHigh = Integer.MIN_VALUE;
            openingLow = Integer.MAX_VALUE;

            setupEntryLevel = Double.NaN;
            confirmationBar = -1;
            sessionClose = Long.parseLong(seed[1]);
            historyStart(dayOpen,sessionClose);
            flatten = providerTradeDay ? Math.min(Long.parseLong(seed[2]), sessionClose - 610 * SECOND) : Long.parseLong(seed[2]);
            warmup = seed.length == 4 && seed[3].equals("warmup");
            if (profile != null) {
                if (volumeSeedExternal && day == 0) {
                    require(!warmup, "External Volume Profile predecessor expects a first scored day");
                    volumeSeedReceipt = profile.loadVolumePredecessor(volumeSeed, dayOpen);
                }
                profile.beginSession();
                if (volumeGrid && !warmup && volumeSeedReceipt == null) {
                    require(volumeWarmupOpen > 0 && volumeWarmupClose < dayOpen && profile.previous() != null,
                            "Missing completed in-tape Volume Profile predecessor");
                    volumeSeedReceipt = "in-tape:" + volumeWarmupOpen + "," + volumeWarmupClose;
                }
            }
            if (tpo != null && (!warmup || !tpoSeedExternal)) {
                if (!warmup && tpoSeedReceipt == null) {
                    if (tpoSeedExternal) {
                        tpo.seed(tpoSeed, dayOpen);
                        try (var seedStream = Files.newBufferedReader(tpoSeed)) {
                            tpoSeedReceipt = seedStream.readLine();
                        }
                    } else {
                        require(tpoWarmupOpen > 0 && tpoWarmupClose < dayOpen && tpo.previous() != null,
                                "Missing completed in-tape TPO predecessor");
                        tpoSeedReceipt = "in-tape:" + tpoWarmupOpen + "," + tpoWarmupClose;
                    }
                }
                tpo.beginSession(dayOpen, sessionClose);
            }
            if (seed.length == 27) {
                ema = Double.parseDouble(seed[3]);
                atr = Double.parseDouble(seed[4]);
                previousClose = Double.parseDouble(seed[5]);
                if (contactMultiplier == 2.0 && extension != 44) {
                    lastBand = Integer.parseInt(seed[6]);
                    setupSide = Integer.parseInt(seed[7]);
                } else if (day == 0) {
                    require(firstContact != null, "Missing causal Keltner-contact warmup");
                    lastBand = firstContact[0];
                    setupSide = firstContact[1];
                }
                closes.clear();
                for (int i = 8; i < seed.length; i++) closes.add(Double.parseDouble(seed[i]));
                if (extension == 44) mtCloseSum = closes.stream().mapToDouble(Double::doubleValue).sum();
            } else if (day == 0) {
                ema = atr = previousClose = Double.NaN;
                require(warmup, "Cold start must begin in warmup");
            }
            firstBar = true;
            flatRequested = sessionClosed = false;
            bar = -1;
            quoteTime = closedTime = earlierClosedTime = -1;
        }

        void next() throws Exception {
            String line = tape.readLine();
            require(line != null, "Unexpected extra native callback");
            String[] row = line.split(",");
            long clock = Long.parseLong(row[0]), ns = Long.parseLong(row[1]);
            int day = Integer.parseInt(row[2]), bid = Integer.parseInt(row[3]), ask = Integer.parseInt(row[4]);
            int kind = Integer.parseInt(row[5]), print = Integer.parseInt(row[6]);
            require(ns >= previous && strategy.TimeCurrent() == clock, "Clock mismatch at " + seen);
            require(Math.round(strategy.Bid() / INSTRUMENT_TICK) == bid && Math.round(strategy.Ask() / INSTRUMENT_TICK) == ask,
                    "Native quote mismatch at " + seen);
            previous = ns;
            seen++;
            if (day != dayIndex) startDay(day);
            if (bar >= 0 && ns >= barEnd()) commit();
            if (!flatRequested && ns >= flatten) {
                flatRequested = true;
                if (intent != null && intent.entry()) intent = null;
                if (position != null && intent == null)
                    intent = new Intent(position.side(), flatten, 0, "session_end");
            }
            if (!sessionClosed && ns >= sessionClose) {
                if (tpo != null && (!warmup || !tpoSeedExternal)) {
                    tpo.closeSession(true);
                    if (warmup) {
                        tpoWarmupOpen = dayOpen;
                        tpoWarmupClose = sessionClose;
                    }
                }
                if (volumeGrid && profile != null) {
                    require(kind == 0 && ns == sessionClose, "Missing scheduled Volume Profile close marker");
                    if (warmup) {
                        volumeWarmupOpen = dayOpen;
                        volumeWarmupClose = sessionClose;
                    }
                }
                sessionClosed = true;
            }
            candidateDeadlines(ns);
            advanceNews(ns);
            if (kind == 1) {
                quoteTime = ns;
                quoteBid = bid;
                quoteAsk = ask;
                useQuote(ns, bid, ask);
                candidateUseQuote(ns,bid,ask);
            }
            if (kind == 2) {
                int quantity = 0;
                if (sizes != null) {
                    String value = sizes.readLine();
                    require(value != null, "Missing executed trade size");
                    quantity = Integer.parseInt(value);
                    require(quantity > 0, "Nonpositive executed trade size");
                    tradeSizesRead++;
                }
                if (ns < sessionClose) {
                    if (vwap != null) vwap.onTrade(ns, print * INSTRUMENT_TICK, quantity);
                    if (profile != null) profile.onTrade(ns, print, quantity, dayOpen);
                    if (rollingVwap != null) rollingVwap.onTrade(ns, print, quantity);
                    if (usesPriorRange()) {
                        dayHigh = Math.max(dayHigh, print);
                        dayLow = Math.min(dayLow, print);
                        dayLast = print;
                    }
                    if (openingRangeDuration > 0 && ns - dayOpen < openingRangeDuration) {
                        openingHigh = Math.max(openingHigh, print);
                        openingLow = Math.min(openingLow, print);
                    }
                    if (tpo != null && (!warmup || !tpoSeedExternal)) tpo.onTrade(ns, print);
                    useTrade(ns, print, quantity);
                }
            }
        }


        double previousCloseSma(int samples) {
            var iter = closes.descendingIterator();
            double sum = 0.0;
            for (int i = 0; i < samples; i++) sum += iter.next();
            return sum;
        }

        double selectedSma(double current) {
            int period = switch (maCase) { case 7 -> 7; case 8 -> 9; case 9 -> 5; default -> 10; };
            return (current + previousCloseSma(period-1)) / period;
        }

        boolean twoLayerEntry(long ns, double last) {
            if (layerSetupTime == 0 || ns - layerSetupTime > 30 * 60 * SECOND) return false;
            int fastPeriod = maCase == 11 ? 7 : 5;
            int slowPeriod = maCase == 11 ? 9 : 10;
            double fast = previousCloseSma(fastPeriod) / fastPeriod;
            double slow = previousCloseSma(slowPeriod) / slowPeriod;
            if (setupSide * (fast-slow) < INSTRUMENT_TICK || setupSide * (slow-ema) < INSTRUMENT_TICK) {
                outerBroken = false;
                return false;
            }
            if (outerBroken) return setupSide * (last-slow) <= 0.0;
            if (setupSide * (last-fast) <= -INSTRUMENT_TICK && setupSide * (last-slow) > 0.0)
                outerBroken = true;
            return false;
        }

        double emaAt(double last) { return Double.isNaN(ema) ? last : ema + (2.0 / 21.0) * (last - ema); }

        double entryEmaAt(double last) {
            return Double.isNaN(entryEma) ? last : entryEma + (2.0 / (entryEmaPeriod + 1)) * (last - entryEma);
        }

        void updateEntryAndTargetHistory(double last) {
            if (entryEmaPeriod != 20) entryEma = entryEmaAt(last);
            if (targetBollingerPeriod != 20) {
                if (targetCloses.size() == targetBollingerPeriod - 1) targetCloses.removeFirst();
                targetCloses.addLast(last);
            }
        }

        double trueRange() {
            double h = high * INSTRUMENT_TICK, l = low * INSTRUMENT_TICK;
            return firstBar ? h - l : Math.max(h - l, Math.max(Math.abs(h - previousClose), Math.abs(l - previousClose)));
        }

        double atrAt() {
            double tr = trueRange();
            if (!Double.isNaN(atr)) return (atr * 9 + tr) / 10;
            if (initialRanges.size() < 9) return Double.NaN;
            for (double value : initialRanges) tr += value;
            return tr / 10;
        }

        long barEnd() { return Math.min(bar + barWidth, sessionClose); }

        void updateClosedIndicators(long end, double o, double h, double l, double c) throws TradingException {
            if (indicators != null) indicators.onBar(end, h, l, c);
            if (extraBars != null) extraBars.onBar(end, o, h, l, c);
            if (extension == 62) {
                double current = extraBars.latest().main();
                if (Double.isFinite(current)) {
                    if (widthReference.size() == 120) {
                        int below = 0, ties = 0;
                        for (double width : widthReference) {
                            if (width < current) below++;
                            else if (width == current) ties++;
                        }
                        widthRank = (below + 0.5 * ties) * (100.0 / 120);
                        widthReference.removeFirst();
                    }
                    widthReference.addLast(current);
                }
            }
            if (extension == 37) {
                var ha = extraBars.latest();
                double color = ha.main() - ha.auxiliary();
                int side = color > 0 ? 1 : color < 0 ? -1 : 0;
                consecutiveHa = side == 0 ? 0 : side == lastHaSide ? consecutiveHa + 1 : 1;
                lastHaSide = side;
            }
            if (extension == 44) {
                if (mtKeltnerRanges.size() == 19) mtRangeSum -= mtKeltnerRanges.removeFirst();
                double range = h - l;
                mtKeltnerRanges.addLast(range);
                mtRangeSum += range;
            }
            if (recentPriceBars > 0) {
                if (closedRanges.size() == recentPriceBars) closedRanges.removeFirst();
                closedRanges.addLast(new ClosedRange(h, l));
                if (extension == 36 && closedRanges.size() == recentPriceBars) commitFractal();
            }
            if (rangeLookback > 0) {
                if (recentRanges.size() == rangeLookback) recentRanges.removeFirst();
                recentRanges.addLast(h - l);
            }
        }

        void commitFractal() {
            var bars = closedRanges.toArray(ClosedRange[]::new);
            int middle = bars.length / 2;
            var extreme = bars[middle];
            boolean swingHigh = true, swingLow = true;
            for (int i = 0; i < bars.length; i++) {
                if (i == middle) continue;
                if (bars[i].high() >= extreme.high()) swingHigh = false;
                if (bars[i].low() <= extreme.low()) swingLow = false;
            }
            if (swingHigh) fractalHigh = extreme.high();
            if (swingLow) fractalLow = extreme.low();
        }

        void commit() throws TradingException {
            double last = close * INSTRUMENT_TICK;
            updateClosedIndicators(barEnd(), open * INSTRUMENT_TICK, high * INSTRUMENT_TICK, low * INSTRUMENT_TICK, last);
            if (volumeHistory != null) {
                lastBarVolume = barVolume;
                lastVolumeSlot = Math.toIntExact((bar - dayOpen) / barWidth);
            }
            if (targetRule.equals("HY121")) {
                earlierClosedTime = closedTime;
                earlierClosedUpper = closedUpper;
                earlierClosedLower = closedLower;
                closedTime = barEnd();
                closedUpper = closes.size() == 19 ? target(last, 1) : Double.NaN;
                closedLower = closes.size() == 19 ? target(last, -1) : Double.NaN;
            }
            ema = emaAt(last);
            if (extension == 59) {
                previousClosedAtr = atr;
                previousClosedPrice = closedPrice;
                closedPrice = last;
            }
            atr = atrAt();
            mlPrevEma=mlLastEma; mlLastEma=ema; mlClosedAtr=atr;
            if(mlVolumes.size()==20) {
                long totalVolume=0; for(long value:mlVolumes)totalVolume+=value;
                mlRelativeVolume=totalVolume>0 ? mlVolume/(totalVolume/20.0) : Double.NaN;
            }
            mlVolumes.addLast(mlVolume);
            if(mlVolumes.size()>20)mlVolumes.removeFirst();
            if (Double.isNaN(atr)) initialRanges.add(trueRange());
            previousClose = last;
            updateEntryAndTargetHistory(last);
            if (closes.size() == 19) {
                double oldest = closes.removeFirst();
                if (extension == 44) mtCloseSum -= oldest;
            }
            closes.addLast(last);
            if (extension == 44) mtCloseSum += last;
            firstBar = false;
            bar = -1;
        }

        void useTrade(long ns, int print, int quantity) {
            historyObserve(ns);
            long slot = dayOpen + ((ns - dayOpen) / barWidth) * barWidth;
            if (bar < 0) { bar = slot; open = high = low = print; barVolume = 0; mlVolume=0; }
            mlVolume+=quantity;
            if (volumeHistory != null) barVolume += quantity;
            high = Math.max(high, print);
            low = Math.min(low, print);
            close = print;
            double last = print * INSTRUMENT_TICK, center = emaAt(last), width = atrAt();
            if (closes.size() < 19 || !(width > 0)) return;
            candidateUseTrade(ns,print,last);
            if (position != null && intent == null) {
                trailGann(last);
                trailFractal(last);
                trailIndicator(last);
                if (pastStop(position.side(), print, position.stop()))
                    intent = new Intent(position.side(), ns, 0, "stop");
                else {
                    String reason = targetReason(ns, last, position);
                    if (reason == null) reason = extensionExit(ns, last);
                    if (reason != null) intent = new Intent(position.side(), ns, 0, reason);
                }
            }
            double entryLevel = Double.isFinite(setupEntryLevel) ? setupEntryLevel
                    : entryEmaPeriod == 20 ? center : entryEmaAt(last);
            if (setupSide != 0 && maCase >= 7 && maCase <= 10) entryLevel = selectedSma(last);
            if (setupSide != 0 && (entryReached(ns, last, entryLevel)
                    || (maCase >= 11 && twoLayerEntry(ns, last)))) {
                int side = setupSide;
                setupSide = 0;
                confirmationBar = -1;
                boolean changedEntry = Double.isFinite(setupEntryLevel)
                        || extension == 7 || extension == 20 || extension == 37 || extension == 44 || extension == 45
                        || entryEmaPeriod != 20 || contactMultiplier != 2.0;
                setupEntryLevel = Double.NaN;
                if(!warmup && ns<flatten && allowsEntry(side,ns) && historyConsecutive>=5 && historyComplete && historySeen && historyCalendarValid) {
                    int shadowStop=outward((center-side*stopAtrMultiplier*width)/INSTRUMENT_TICK,side);
                    if(!pastStop(side,print,shadowStop)) {
                        candidateEntries.add(new Intent(side,ns,shadowStop,"first_return"));
                        signalQuotes.printf(Locale.ROOT,"%d,%d,%d,%d,%d,%d%n",ns,side,quoteTime,quoteBid,quoteAsk,shadowStop);
                        double risk=side*((side==1?quoteAsk:quoteBid)-shadowStop)*12.5+4.68+25.0;
                        double bbHalf=(target(last,1)-target(last,-1))/2+targetOffset;
                        double ratio=bbHalf/(contactMultiplier*width);
                        double slope=side*(mlLastEma-mlPrevEma)/mlClosedAtr;
                        require(quoteTime<=ns && risk>0 && Double.isFinite(ratio) && Double.isFinite(slope)
                            && Double.isFinite(mlRelativeVolume),"Incomplete causal ML feature state");
                        mlFeatures.printf(Locale.ROOT,"%d,%d,%d,%.17g,%.17g,%.17g,%.17g,%.17g%n",ns,side,
                            quoteTime,risk,ratio,slope,mlRelativeVolume,(ns-dayOpen)/(60.0*SECOND));
                    }
                }
                if (!warmup && position == null && intent == null && ns < flatten && allowsEntry(side, ns) && historyAllows()) {
                    int stop = outward((center - side * stopAtrMultiplier * width) / INSTRUMENT_TICK, side);
                    int candidate = extensionStop(side, print, stop);
                    if (extension == 19) {
                        // Signal-price distance, rounded outward and capped by the baseline stop.
                        int atrStop = outward(print - side * atrStopMultiplier * width / INSTRUMENT_TICK, side);
                        if (side * (atrStop - stop) > 0 && !pastStop(side, print, atrStop)) candidate = atrStop;
                    }
                    if (candidate != stop) extensionStops++;
                    if (!pastStop(side, print, candidate) && indicatorPermits(side)) {
                        if (!extensionPermitsEntry(side)) extensionEntries++;
                        else {
                            if (changedEntry) extensionEntries++;
                            if(mlGated)require(mlDecisions.containsKey(ns),"Missing precomputed chronological ML decision");
                            if(!mlGated || mlDecisions.get(ns))intent = new Intent(side, ns, candidate, "first_return");
                        }
                    }
                }
            }
            double contactCenter = center, contactDistance = contactMultiplier * width;
            if (extension == 44) {
                if (mtKeltnerRanges.size() < 19) return;
                contactCenter = (mtCloseSum + last) / 20.0;
                contactDistance = mtKeltnerDeviation * (mtRangeSum + (high - low) * INSTRUMENT_TICK) / 20.0;
            }
            int contact = last >= contactCenter + contactDistance ? 1
                    : last <= contactCenter - contactDistance ? -1 : 0;
            if (contact != 0 && contact != lastBand) {
                if (lastBand != 0) {
                    layerSetupTime = ns;
                    outerBroken = false;
                    setupSide = contact;
                    confirmationBar = -1;
                    double level = switch (extension) {
                        case 2 -> vwap.band(contact * vwapBandSigma);
                        case 15, 16, 41, 46, 47, 48, 49, 50 -> extraBars.latest().main();
                        case 24 -> rollingVwap.value();
                        default -> Double.NaN;
                    };
                    setupEntryLevel = contact * (last - level) > 0 ? level : Double.NaN;
                }
                lastBand = contact;
            }
        }

        boolean entryReached(long ns, double last, double level) {
            boolean touched = setupSide * (last - level) <= 0;
            if (extension != 7 && extension != 20 && extension != 37 && extension != 45) return touched;
            var indicator = extraBars.latest();
            if (confirmationBar < 0) {
                if (touched) confirmationBar = barEnd();
                return false;
            }
            if (extension == 20 || extension == 45) {
                // The three consecutive closes after the touch are the only confirmation opportunities.
                if (ns >= confirmationBar + 3 * barWidth) {
                    setupSide = 0;
                    confirmationBar = -1;
                    return false;
                }
                double threshold = barRule.setting(0, 50);
                double levelForSide = extension == 45 ? 100 : setupSide == 1 ? threshold : 100 - threshold;
                return indicator.endNs() >= confirmationBar
                        && setupSide * (extraBars.previous().main() - levelForSide) <= 0
                        && setupSide * (indicator.main() - levelForSide) > 0;
            }
            if (extension == 37) {
                if (ns >= confirmationBar + 3 * barWidth) {
                    setupSide = 0;
                    confirmationBar = -1;
                    return false;
                }
                long required = (long) barRule.setting(0, 1);
                return lastHaSide == setupSide && consecutiveHa >= required
                        && indicator.endNs() >= confirmationBar + (required - 1) * barWidth;
            }
            long confirmationWindow = (long) (barRule == null ? 3 : barRule.setting(1, 3));
            if (ns >= confirmationBar + confirmationWindow * barWidth) {
                setupSide = 0;
                confirmationBar = -1;
                return false;
            }
            return indicator.endNs() >= confirmationBar && setupSide * (indicator.main() - indicator.auxiliary()) > 0
                    && setupSide * (last - level) >= 0;
        }

        int extensionStop(int side, int print, int stop) {
            double level = Double.NaN;
            if (extension == 3) level = vwap.band(-side * vwapBandSigma) / INSTRUMENT_TICK;
            if (extension == 56) {
                double width = extraBars.latest().main();
                if (!Double.isFinite(width) || width <= 0) return stop;
                int levelTicks = outward(print - side * width / INSTRUMENT_TICK * barRule.setting(0, 2), side);
                return side * (levelTicks - stop) > 0 && !pastStop(side, print, levelTicks) ? levelTicks : stop;
            }
            if (extension == 43) {
                double mtAtr = extraBars.latest().main();
                if (!Double.isFinite(mtAtr) || mtAtr <= 0) return stop;
                double center = emaAt(print * INSTRUMENT_TICK);
                int candidate = outward((center - side * stopAtrMultiplier * mtAtr) / INSTRUMENT_TICK, side);
                return pastStop(side, print, candidate) ? stop : candidate;
            }
            if (extension == 14) {
                var stress = extraBars.latest();
                double threshold = barRule == null ? 0.15 : barRule.setting(0, 0.15);
                double retained = barRule == null ? 0.5 : barRule.setting(1, 0.5);
                if ((side == 1 ? stress.main() : stress.auxiliary()) >= threshold)
                    level = print + retained * (stop - (double) print);
            }
            if (!Double.isFinite(level)) return stop;
            int candidate = outward(level, side);
            return side * (candidate - stop) > 0 && side * (print - candidate) >= 4 ? candidate : stop;
        }

        void trailGann(double last) {
            if (extension != 17) return;
            var gann = extraBars.latest();
            var p = position;
            if (!(gann.endNs() > positionStartBar && gann.auxiliary() == p.side()) || !Double.isFinite(gann.main())) return;
            int level = outward(gann.main() / INSTRUMENT_TICK, p.side());
            if (p.side() * (level - p.stop()) > 0 && p.side() * (last / INSTRUMENT_TICK - level) >= 1) {
                position = new Position(p.order(), p.side(), p.price(), p.time(), p.signal(), level);
                extensionStops++;
            }
        }

        void trailFractal(double last) {
            if (extension != 36) return;
            var p = position;
            double extreme = p.side() == 1 ? fractalLow : fractalHigh;
            if (!Double.isFinite(extreme)) return;
            int candidate = outward(extreme / INSTRUMENT_TICK, p.side());
            int executable = p.side() == 1 ? quoteBid : quoteAsk;
            if (p.side() * (candidate - p.stop()) > 0 && p.side() * (last / INSTRUMENT_TICK - candidate) >= 1
                    && quoteTime >= dayOpen && p.side() * (executable - candidate) >= 1) {
                position = new Position(p.order(), p.side(), p.price(), p.time(), p.signal(), candidate);
                extensionStops++;
            }
        }

        void trailIndicator(double last) {
            if (extension != 52 && extension != 58) return;
            var p = position;
            var completed = extraBars.latest();
            double price = completed.main();
            if (completed.endNs() <= positionStartBar || !Double.isFinite(price)
                    || p.side() * (extraBars.barClose() - price) <= 0) return;
            int level = outward(price / INSTRUMENT_TICK, p.side());
            int executable = p.side() == 1 ? quoteBid : quoteAsk;
            if (p.side() * (level - p.stop()) > 0 && p.side() * (last / INSTRUMENT_TICK - level) >= 1
                    && quoteTime >= dayOpen && p.side() * (executable - level) >= 1) {
                position = new Position(p.order(), p.side(), p.price(), p.time(), p.signal(), level);
                extensionStops++;
            }
        }

        int barsSinceExtreme(int side) {
            int age = closedRanges.size(), bestAge = 0;
            double best = Double.NEGATIVE_INFINITY;
            for (ClosedRange range : closedRanges) {
                double value = side == 1 ? range.high() : -range.low();
                age--;
                if (value >= best) {
                    best = value;
                    bestAge = age;
                }
            }
            return bestAge;
        }

        boolean directionIsEntryGate() {
            return extension == 34 && barRule.setting(1, 0) == 0;
        }

        boolean extensionPermitsEntry(int side) {
            if (extension == 55 || extension == 61 || extension == 62) {
                double value = extension == 62 ? widthRank : extraBars.latest().main();
                if (extension == 61) value = atr > 0 ? value / atr : Double.NaN;
                double lower = extension == 62 ? 20 : barRule.setting(0, 20);
                double upper = extension == 62 ? barRule.setting(0, 85) : barRule.setting(1, 85);
                return !Double.isFinite(value) || value >= lower && value <= upper;
            }
            if (extension == 51) {
                double oscillator = extraBars.latest().main();
                return !Double.isFinite(oscillator) || side * oscillator > 0;
            }
            if (extension == 39 && closedRanges.size() == recentPriceBars)
                return barsSinceExtreme(side) <= barRule.setting(0, 4);
            if (directionIsEntryGate() || extension == 40) {
                var last = extraBars.latest();
                double direction = last.main() - last.auxiliary();
                return !Double.isFinite(direction) || side * direction > 0;
            }
            if (volumeHistory != null) {
                if (lastVolumeSlot < 0 || expectedVolume[lastVolumeSlot] < 0) return true;
                if (expectedVolume[lastVolumeSlot] == 0) return lastBarVolume > 0;
                return lastBarVolume * volumeLookback >= volumeThreshold * expectedVolume[lastVolumeSlot];
            }
            if (rangeLookback == 0 || recentRanges.size() < rangeLookback || !(atr > 0)) return true;
            double boundary = rangeThreshold * atr;
            for (double range : recentRanges) {
                if (extension == 29 ? range < boundary : range > boundary) return false;
            }
            return true;
        }

        String extensionExit(long ns, double last) {
            int side = position.side();
            double level = Double.NaN;
            if (extension == 1) level = vwap.band(side * vwapBandSigma);
            if (profile != null && profile.previous() != null) {
                var prior = profile.previous();
                level = extension == 4 && volumePointTarget ? prior.poc() : side == 1 ? prior.valueAreaHigh() : prior.valueAreaLow();
            }
            if (tpo != null && tpo.previous() != null) {
                var prior = tpo.previous();
                level = tpoPointTarget ? prior.poc() : side == 1 ? prior.valueAreaHigh() : prior.valueAreaLow();
            }
            if (openingRangeDuration > 0 && ns - dayOpen >= openingRangeDuration && openingLow <= openingHigh)
                level = (side == 1 ? openingHigh : openingLow) * INSTRUMENT_TICK;
            if (extension == 35 && priorDayLow <= priorDayHigh) {
                double range = priorDayHigh - priorDayLow;
                level = (side == 1 ? priorDayLow + fiboFraction * range : priorDayHigh - fiboFraction * range) * INSTRUMENT_TICK;
            }
            if (extension == 53 && priorDayLow <= priorDayHigh) {
                double pivot = (priorDayHigh + priorDayLow + priorDayLast) / 3.0;
                double target = barRule.setting(0, 1) == 1
                        ? 2 * pivot - (side == 1 ? priorDayLow : priorDayHigh)
                        : pivot + side * (priorDayHigh - priorDayLow);
                level = target * INSTRUMENT_TICK;
            }
            if (extension == 38 && closedRanges.size() == recentPriceBars) {
                level = side == 1 ? Double.NEGATIVE_INFINITY : Double.POSITIVE_INFINITY;
                for (ClosedRange range : closedRanges)
                    level = side == 1 ? Math.max(level, range.high()) : Math.min(level, range.low());
            }
            if (side * (level / INSTRUMENT_TICK - position.price()) >= 1 && side * (last - level) >= 0) {
                extensionTargets++;
                if (researchCase == 4) return "opening_range_target";
                return switch (extension) {
                    case 1 -> "vwap_band_target";
                    case 30 -> "opening_range_target";
                    case 35 -> "fibo_target";
                    case 38 -> "closed_range_target";
                    case 53 -> "prior_rth_pivot_target";
                    default -> "prior_session_profile_target";
                };
            }
            if (extraBars == null || directionIsEntryGate()) return null;
            var current = extraBars.latest();
            var previous = extraBars.previous();
            if (current.endNs() <= positionStartBar) return null;
            double a = current.main(), b = previous.main();
            boolean exit = switch (extension) {
                case 6 -> kerCrossedBelow(b, a, kerParameters.threshold());
                case 18 -> b >= adxThreshold && a < adxThreshold;
                case 8, 10, 12, 42 -> side * (b - previous.auxiliary()) >= 0 && side * (a - current.auxiliary()) < 0;
                case 9, 26, 54 -> side * b >= 0 && side * a < 0;
                case 11 -> {
                    double longLevel = barRule == null ? 75 : barRule.setting(0, 75);
                    double shortLevel = barRule == null ? 25 : barRule.setting(1, 25);
                    yield side == 1 ? b >= longLevel && a < longLevel : b <= shortLevel && a > shortLevel;
                }
                case 13 -> side == 1 ? b >= 0.80 && a < 0.80 : b <= 0.20 && a > 0.20;
                case 31 -> side == 1 ? b >= 0 && a < 0
                        : previous.auxiliary() <= 0 && current.auxiliary() > 0;
                case 32 -> {
                    double threshold = barRule.setting(1, 50);
                    yield side * b >= threshold && side * a < threshold;
                }
                case 33 -> {
                    double threshold = barRule.setting(0, 0.6);
                    double inverse = Math.round((1 - threshold) * 100) / 100.0;
                    yield side == 1 ? b >= threshold && a < threshold : b <= inverse && a > inverse;
                }
                case 34 -> side * (b - previous.auxiliary()) >= 0 && side * (a - current.auxiliary()) < 0;
                case 57 -> stochasticExit(side, current, previous);
                case 59 -> side * (closedPrice - previousClosedPrice) < 0
                        && previousClosedAtr > 0 && a > barRule.setting(0, 2) * previousClosedAtr;
                case 60 -> side == 1 ? b >= -20 && a < -20 : b <= -80 && a > -80;
                default -> false;
            };
            if (!exit) return null;
            extensionTargets++;
            return "indicator_exit_" + extension;
        }

        boolean stochasticExit(int side, SqxExtensionBarIndicators.Values current,
                               SqxExtensionBarIndicators.Values previous) {
            if (current.endNs() == stochasticCheckedBar) return false;
            stochasticCheckedBar = current.endNs();
            boolean crossed = side * (previous.main() - previous.auxiliary()) >= 0
                    && side * (current.main() - current.auxiliary()) < 0;
            boolean reached = side * (current.main() - 50) >= 30;
            boolean exit = stochasticExtreme && crossed;
            stochasticExtreme |= reached;
            return exit;
        }

        boolean indicatorPermits(int side) {
            if (indicators == null) return true;
            var value = indicators.latest();
            boolean allowed = switch (indicatorMode) {
                case 1 -> value.adx14() >= 20;
                case 2 -> value.adx14() >= 25;
                case 3 -> side == 1 ? value.rsi14() > 50 : value.rsi14() < 50;
                case 4 -> value.atr50() > 0 && value.atr10() <= 1.30 * value.atr50();
                case 5 -> value.ker10() >= 0.30;
                default -> false;
            };
            if (allowed) indicatorAccepted++;
            else indicatorBlocked++;
            return allowed;
        }

        double target(double last, int side) {
            var history = targetBollingerPeriod == 20 ? closes : targetCloses;
            int period = targetBollingerPeriod;
            if (history.size() != period - 1) return Double.NaN;
            double mean = last;
            for (double value : history) mean += value;
            mean /= period;
            double variance = (last - mean) * (last - mean);
            for (double value : history) variance += (value - mean) * (value - mean);
            return mean + side * (bollingerWidth * Math.sqrt(variance / period) - targetOffset);
        }

        String targetReason(long ns, double last, Position p) {
            int side = p.side();
            double running = target(last, side);
            boolean crossed = side == 1 ? last > running : last < running;
            if (crossed && targetBollingerPeriod != 20) extensionTargets++;
            if (targetRule.equals("HY120")) {
                int executable = side == 1 ? quoteBid : quoteAsk;
                return crossed && quoteTime == ns && side * (executable - p.price()) >= 2 ? "target_green_hit" : null;
            }
            if (targetRule.equals("HY121")) {
                double completed = Double.NaN;
                if (closedTime >= 0 && closedTime < ns) completed = side == 1 ? closedUpper : closedLower;
                else if (earlierClosedTime >= 0 && earlierClosedTime < ns)
                    completed = side == 1 ? earlierClosedUpper : earlierClosedLower;
                double effective = !Double.isFinite(completed) ? running : side == 1 ? Math.min(running, completed) : Math.max(running, completed);
                if (side == 1 ? last >= effective : last <= effective) return crossed ? "bb" : "target_closed_target";
                return null;
            }
            return crossed ? "bb" : null;
        }

        int outward(double tick, int side) {
            double nearest = Math.rint(tick);
            if (Math.abs(tick - nearest) <= Math.min(8 * Math.ulp(tick), 1e-8)) tick = nearest;
            return (int) (side == 1 ? Math.floor(tick) : Math.ceil(tick));
        }

        boolean pastStop(int side, int tick, int stop) {
            return side == 1 ? tick <= stop : tick >= stop;
        }

        boolean allowsEntry(int side, long ns) {
            if (ns - dayOpen < openingEntryDelay) return false;
            if (newsIndex < newsWindows.size() && ns >= newsWindows.get(newsIndex)[0] - newsLead)
                return false;
            long minutes = (ns - dayOpen) / (60 * SECOND);
            return switch (filterMode) {
                case 1 -> minutes >= 5;
                case 2 -> side != -1 || minutes >= 60;
                case 3 -> side != 1 || minutes < 120 || minutes >= 180;
                case 4 -> side != 1 || minutes >= 60;
                case 5 -> side != -1 || minutes < 120 || minutes >= 180;
                case 6 -> side != -1 || minutes < 60 || minutes >= 120;
                case 7 -> side != 1 || minutes < 180 || minutes >= 240;
                default -> true;
            };
        }

        void advanceNews(long ns) {
            while (newsIndex < newsWindows.size()) {
                long[] interval = newsWindows.get(newsIndex);
                if (ns < interval[0] - newsLead) break;
                if (intent != null && intent.entry()) intent = null;
                if (ns >= interval[0]) require(position == null && intent == null,
                    "Position did not flatten in time for T1 blackout at " + interval[0]);
                if (position != null && (intent == null || !intent.reason().equals("t1_preclose"))
                        && (intent == null || intent.time() > interval[0] - newsLead))
                    intent = new Intent(position.side(), ns, 0, "t1_preclose");
                if (ns <= interval[1]) break;
                ++newsIndex;
            }
        }

        void useQuote(long ns, int bid, int ask) throws Exception {
            if (intent == null || ns < intent.time() + 2 * SECOND) return;
            Intent next = intent;
            intent = null;
            int side = next.side();
            int executable = side == 1 ? bid : ask;
            if (next.entry()) {
                if (ns >= flatten || !allowsEntry(side, ns) || pastStop(side, executable, next.stop())) return;
                int entry = side == 1 ? ask : bid;
                // Use the executable quote at the normal entry time and reserve both adverse ticks.
                long plannedRiskCents = (long) side * (entry - next.stop()) * 1250
                        + 2968;
                if (plannedRiskCents > riskLimitCents) {
                    riskRejected++;
                    return;
                }
                largestAcceptedRiskCents = Math.max(largestAcceptedRiskCents, plannedRiskCents);
                ILiveOrder order = strategy.Trader.Open(side == 1 ? OrderTypes.Buy : OrderTypes.Sell, strategy.Symbol, 0)
                    .setSize(1).setComment("HY18b_SQX_Retest").setMagicNumber(18104);
                order.Send();
                require(order.isSuccessful() && !order.isRefused() && !order.isClosedOrder(), "SQX entry rejected");
                require(order.getOpenTime() == strategy.TimeCurrent() && Math.round(order.getOpenPrice() / INSTRUMENT_TICK) == entry,
                        "SQX native entry price/time differs");
                position = new Position(order, side, entry, ns, next.time(), next.stop());
                nativeRisks.printf(Locale.ROOT,"%d,%d,%d,%d%n",ns,entry*25L,next.stop()*25L,plannedRiskCents);
                positionStartBar = extraBars == null ? -1 : extraBars.latest().endNs();
                stochasticExtreme = false;
                stochasticCheckedBar = Long.MIN_VALUE;
                return;
            }
            Position p = position;
            require(p != null && p.side() == side, "Exit without corresponding open position");
            p.order().Close(OrderCloseTypes.Manual);
            require(p.order().isSuccessful() && !p.order().isRefused() && p.order().isClosedOrder(), "SQX exit rejected");
            require(p.order().getCloseTime() == strategy.TimeCurrent()
                && Math.round(p.order().getClosePrice() / INSTRUMENT_TICK) == executable, "SQX native exit price/time differs");
            long net = Math.round(p.order().getPL() * 100);
            require(Math.abs(p.order().getCommSwap() + 4.68) < 1e-5, "Unexpected native commissions");
            require(net == (long) side * (executable - p.price()) * 1250 - 468, "Native PnL mismatch");
            trades.printf(Locale.ROOT, "%s,%d,%d,%d,%d,%d,%d,%s,%d%n", side == 1 ? "LONG" : "SHORT",
                p.signal(), p.time(), p.price() * 25L, next.time(), ns, executable * 25L, next.reason(), net);
            position = null;
            roundTrips++;
        }

        void finish() throws IOException {
            try (tape; seeds; trades; sizes; candidateTrades; candidateMarks; nativeRisks; signalQuotes; mlFeatures) {
                if (Files.exists(result.getParent().resolve("ml-prefix-only.txt"))) {
                    require(seen == expected && tape.readLine() == null && seeds.readLine() == null,
                            "Native prefix did not consume exactly its physical input");
                    require(sizes == null || sizes.readLine() == null, "Unused prefix trade sizes");
                    require(!mlFeatures.checkError(), "Prefix feature output error");
                    Files.writeString(result.resolve("prefix-complete.txt"),seen+"\n"+previous+"\n");
                    return; // Diagnostic prefix may end with open positions; never report its PnL.
                }
                require(seen == expected && tape.readLine() == null && seeds.readLine() == null,
                        "SQX did not consume the entire tape: " + seen + " / " + expected);
                require(position == null && intent == null && sessionClosed, "Unfinished final session");
                require(candidates.isEmpty() && candidateEntries.isEmpty(),"Unfinished candidate inventory");
                require(!candidateTrades.checkError() && !candidateMarks.checkError() && !nativeRisks.checkError(),"Inventory write error");
                require(!trades.checkError() && !mlFeatures.checkError(), "Could not write trades/features");
                int historyExpected=Math.toIntExact((historyClose-historyOpen)/(300*SECOND));
                historyAudit.append(historyOpen).append(',').append(historyConsecutive).append(',')
                    .append(historyObserved).append(',').append(historyExpected).append(',')
                    .append(historyComplete && historySeen && historyObserved==historyExpected).append(",final\n");
                Files.writeString(result.resolve("history-audit.csv"),historyAudit.toString());
                Files.writeString(result.resolve("history-blocked-returns.txt"),historyBlockedReturns+"\n");
                if (sizes != null) {
                    require(sizes.readLine() == null, "Extra executed trade sizes");
                    Files.writeString(result.resolve("trade-sizes-used.txt"), tradeSizesRead + "\n");
                }
                if (mtSeedDigest != null)
                    Files.writeString(result.resolve("mt-keltner-contact-used.txt"), mtSeedDigest + "\n");
                if (priorRangeSource != null)
                    Files.writeString(result.resolve("previous-rth-range-used.txt"), priorRangeSource + "\n");
                if (volumeHistory != null) {
                    require(dayIndex + 1 == volumeHistory.length, "Unused Average Volume input sessions");
                    Files.writeString(result.resolve("average-volume-history-used.txt"), volumeHistoryDigest + "\n");
                }
                if (barRule != null && barRule.ordinal() > 0)
                    Files.writeString(result.resolve(barRule.slug() + "-settings.txt"), barRule.settings() + "\n");
                if (extension == 18)
                    Files.writeString(result.resolve("adx-settings.txt"), adxPeriod + "," + adxThreshold + "\n");
                if (extension == 19)
                    Files.writeString(result.resolve("atr-settings.txt"), atrStopMultiplier + "\n");
                if (reportKerParameters)
                    Files.writeString(result.resolve("ker-settings.txt"),
                            kerParameters.period() + "," + kerParameters.threshold() + "\n");
                if (reportKamaParameters)
                    Files.writeString(result.resolve("kama-settings.txt"),
                            kamaParameters.efficiencyPeriod() + "," + kamaParameters.fastPeriod() + ","
                                    + kamaParameters.slowPeriod() + "\n");
                if (volumeGrid && profile != null) {
                    require(volumeSeedReceipt != null, "Missing Volume Profile RTH seed use");
                    String role = volumePointTarget ? "poc" : "value-area";
                    Files.writeString(result.resolve("volume-profile-settings.txt"),
                            role + "," + volumeValueAreaPercent + "\n");
                    Files.writeString(result.resolve("volume-profile-predecessor-used.txt"), volumeSeedReceipt + "\n");
                }
                if (tpo != null) {
                    require(tpoSeedReceipt != null, "Missing TPO RTH seed use");
                    Files.writeString(result.resolve("tpo-predecessor-used.txt"), tpoSeedReceipt + "\n");
                }
                if (extension != 0) Files.writeString(result.resolve("extension-actions.txt"),
                        extensionEntries + "\n" + extensionStops + "\n" + extensionTargets + "\n");
                Files.writeString(result.resolve("nq-research.txt"),
                        researchCase + "\n" + riskRejected + "\n" + largestAcceptedRiskCents + "\n");
                Files.writeString(result.resolve("complete.txt"), seen + "\n" + roundTrips + "\n");
                if (indicators != null)
                    Files.writeString(result.resolve("indicator-gate.txt"), indicatorAccepted + "\n" + indicatorBlocked + "\n");
            }
        }
    }
}
