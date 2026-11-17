package SQ.Blocks.OtherActions;

import SQ.Blocks.Indicators.ADX.ADX;
import SQ.Blocks.Indicators.Aroon.Aroon;
import SQ.Blocks.Indicators.AwesomeOscillator.AwesomeOscillator;
import SQ.Blocks.Indicators.GannHiLo.GannHiLo;
import SQ.Blocks.Indicators.HullMovingAverage.HullMovingAverage;
import SQ.Blocks.Indicators.KAMA.KAMA;
import SQ.Blocks.Indicators.KaufmanEfficiencyRatio.KaufmanEfficiencyRatio;
import SQ.Blocks.Indicators.LaguerreRSI.LaguerreRSI;
import SQ.Blocks.Indicators.MTATR.MTATR;
import SQ.Blocks.Indicators.QQE.QQE;
import SQ.Blocks.Indicators.Reflex.Reflex;
import SQ.Blocks.Indicators.RSI.RSI;
import SQ.Blocks.Indicators.SchaffTrendCycle.SchaffTrendCycle;
import SQ.Blocks.Indicators.UlcerIndex.UlcerIndex;
import SQ.Blocks.Indicators.Vortex.Vortex;
import SQ.Blocks.Indicators.WaveTrend.WaveTrend;
import SQ.Internal.IndicatorBlock;
import SQ.Internal.Indicators;
import com.strategyquant.datalib.DataSeries;
import com.strategyquant.datalib.TradingException;
import com.strategyquant.datalib.dataseries.MedianDataSeries;
import com.strategyquant.tradinglib.Buffer;
import com.strategyquant.tradinglib.ChartData;
import com.strategyquant.tradinglib.Output;
import com.strategyquant.tradinglib.indicator.IndicatorBase;

import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;

/** Runs installed SQX indicators on completed trade bars supplied by the tick replay. */
final class SqxExtensionBarIndicators {
    record Values(long endNs, double main, double auxiliary) {}

    private static final Values EMPTY = new Values(Long.MIN_VALUE, Double.NaN, Double.NaN);
    private final ChartData chart = new ChartData();
    private final NativeBlock[] blocks;
    private final NativeBlock primaryBlock;
    private final DataSeries main;
    private final DataSeries auxiliary;
    private final int minimumBars;
    private Values latest = EMPTY;
    private Values previous = EMPTY;
    private int bars;

    SqxExtensionBarIndicators(int mode) throws TradingException {
        this(mode, 10);
    }

    SqxExtensionBarIndicators(int mode, int kerPeriod) throws TradingException {
        this(mode, kerPeriod, 10, 2, 30);
    }

    SqxExtensionBarIndicators(int mode, int kerPeriod, int kamaEfficiencyPeriod, int kamaFastPeriod,
                              int kamaSlowPeriod) throws TradingException {
        this(mode, kerPeriod, kamaEfficiencyPeriod, kamaFastPeriod, kamaSlowPeriod, 14);
    }

    SqxExtensionBarIndicators(int mode, int kerPeriod, int kamaEfficiencyPeriod, int kamaFastPeriod,
                              int kamaSlowPeriod, int adxPeriod) throws TradingException {
        this(mode, kerPeriod, kamaEfficiencyPeriod, kamaFastPeriod, kamaSlowPeriod, adxPeriod, new double[0]);
    }

    SqxExtensionBarIndicators(int mode, int kerPeriod, int kamaEfficiencyPeriod, int kamaFastPeriod,
                              int kamaSlowPeriod, int adxPeriod, double[] parameters) throws TradingException {
        chart.High = new DataSeries(256);
        chart.Low = new DataSeries(256);
        chart.Close = new DataSeries(256);

        IndicatorBlock indicator;
        IndicatorBlock companion = null;
        String mainName = "Value";
        String auxiliaryName = null;
        switch (mode) {
            case 6 -> {
                KaufmanEfficiencyRatio ker = new KaufmanEfficiencyRatio() {
                    @Override public int getCurrentBar() { return CurrentBar; }
                };
                ker.Chart = chart;
                if (kerPeriod != 8 && kerPeriod != 10 && kerPeriod != 14)
                    throw new IllegalArgumentException("Unknown KER period: " + kerPeriod);
                ker.Period = kerPeriod;
                indicator = ker;
                // The vendor starts accumulating price movement at bar index kerPeriod.
                minimumBars = 2 * kerPeriod;
            }
            case 7 -> {
                Aroon aroon = new Aroon() {
                    @Override public int getCurrentBar() { return CurrentBar; }
                };
                aroon.Chart = chart;
                aroon.Period = integerParameter(parameters, 0, 14);
                indicator = aroon;
                mainName = "Up";
                auxiliaryName = "Down";
                minimumBars = aroon.Period;
            }
            case 8 -> {
                MTATR trueRange = new MTATR() {
                    @Override public int getCurrentBar() { return CurrentBar; }
                };
                trueRange.Chart = chart;
                trueRange.Period = 1;
                companion = trueRange;
                Vortex vortex = new Vortex() {
                    @Override public int getCurrentBar() { return CurrentBar; }
                    {
                        Indicators = new Indicators(null) {
                            @Override public MTATR MTATR(ChartData input, int period) {
                                return trueRange;
                            }
                        };
                    }
                };
                vortex.Chart = chart;
                vortex.Period = integerParameter(parameters, 0, 12);
                indicator = vortex;
                mainName = "VIPlusSumRge";
                auxiliaryName = "VIMinusSumRge";
                minimumBars = 2 * vortex.Period;
            }
            case 9 -> {
                Reflex reflex = new Reflex() {
                    @Override protected void OnBarUpdate() throws TradingException {
                        // The source SQX execution jobs use the MetaTrader 5 hedged engine.
                        super.onBarUpdateMT();
                    }
                };
                reflex.Input = chart;
                reflex.Period = integerParameter(parameters, 0, 24);
                indicator = reflex;
                minimumBars = 4 * reflex.Period;
            }
            case 10 -> {
                WaveTrend waveTrend = new WaveTrend() {
                    @Override public int getCurrentBar() { return CurrentBar; }
                };
                waveTrend.Chart = chart;
                waveTrend.ChannelLength = integerParameter(parameters, 0, 10);
                waveTrend.AverageLength = integerParameter(parameters, 1, 21);
                indicator = waveTrend;
                mainName = "WT1";
                auxiliaryName = "WT2";
                minimumBars = waveTrend.ChannelLength + 2 * waveTrend.AverageLength + 12;
            }
            case 11 -> {
                SchaffTrendCycle schaff = new SchaffTrendCycle() {
                    @Override public int getCurrentBar() { return CurrentBar; }
                };
                schaff.Input = chart;
                schaff.StochPeriod = 10;
                schaff.FastPeriod = 20;
                schaff.SlowPeriod = 50;
                indicator = schaff;
                minimumBars = 110;
            }
            case 12 -> {
                QQE qqe = new QQE() {
                    @Override public int getCurrentBar() { return CurrentBar; }
                };
                qqe.Chart = chart;
                qqe.RSIPeriod = integerParameter(parameters, 0, 14);
                qqe.sF = 5;
                qqe.wF = 4.236;
                indicator = qqe;
                mainName = "Value1";
                auxiliaryName = "Value2";
                minimumBars = 6 * qqe.RSIPeriod - 2;
            }
            case 13 -> {
                LaguerreRSI laguerre = new LaguerreRSI();
                laguerre.Chart = chart;
                laguerre.Gamma = parameters.length == 0 ? 0.5 : parameters[0];
                indicator = laguerre;
                mainName = "LRSI"; // SQX returns 0 to 1.
                minimumBars = 40;
            }
            case 14 -> {
                indicator = ulcer(1);
                companion = ulcer(2);
                minimumBars = 72;
            }
            case 15 -> {
                HullMovingAverage hull = new HullMovingAverage() {
                    @Override public int getCurrentBar() { return CurrentBar; }
                };
                hull.Input = chart.Close;
                hull.Period = integerParameter(parameters, 0, 10);
                indicator = hull;
                minimumBars = hull.Period + 2 * (int) Math.sqrt(hull.Period);
            }
            case 16 -> {
                if (kamaEfficiencyPeriod < 2 || kamaFastPeriod < 2 || kamaFastPeriod >= kamaSlowPeriod)
                    throw new IllegalArgumentException("Invalid KAMA periods");
                int startup = Math.max(kamaEfficiencyPeriod, kamaSlowPeriod);
                if (2 * startup >= 256)
                    throw new IllegalArgumentException("KAMA period exceeds closed-bar buffer");
                KAMA kama = new KAMA() {
                    @Override public int getCurrentBar() { return CurrentBar; }
                    @Override protected void OnBarUpdate() throws TradingException {
                        if (CurrentBar == startup) {
                            // Anchor the first native recursive update to the last observed close.
                            Value.set(1, Chart.Close.get(1));
                        }
                        super.OnBarUpdate();
                    }
                };
                kama.Chart = chart;
                kama.ERPeriod = kamaEfficiencyPeriod;
                kama.ShortPeriod = kamaFastPeriod;
                kama.LongPeriod = kamaSlowPeriod;
                indicator = kama;
                minimumBars = 2 * startup;
            }
            case 17 -> {
                GannHiLo gann = new GannHiLo() {
                    @Override public int getCurrentBar() { return CurrentBar; }
                };
                gann.Chart = chart;
                gann.Period = integerParameter(parameters, 0, 10);
                indicator = gann;
                mainName = "GHA";
                minimumBars = 2 * gann.Period + 2;
            }
            case 18 -> {
                ADX adx = new ADX() {
                    @Override public int getCurrentBar() { return CurrentBar; }
                };
                adx.Input = chart;
                adx.Period = adxPeriod;
                indicator = adx;
                mainName = "Main";
                minimumBars = 2 * adxPeriod;
            }
            case 20 -> {
                RSI rsi = new RSI() {
                    @Override public int getCurrentBar() { return CurrentBar; }
                };
                rsi.Input = chart.Close;
                rsi.Period = 14;
                indicator = rsi;
                minimumBars = 15;
            }
            case 26 -> {
                chart.Median = new MedianDataSeries(chart.Close, chart.High, chart.Low, chart.Close, chart.Close);
                AwesomeOscillator awesome = new AwesomeOscillator() {
                    @Override public int getCurrentBar() { return CurrentBar; }
                };
                awesome.Input = chart;
                indicator = awesome;
                minimumBars = 35;
            }
            default -> throw new IllegalArgumentException("Unknown SQX extension indicator mode " + mode);
        }
        primaryBlock = new NativeBlock(indicator);
        NativeBlock extra = companion == null ? null : new NativeBlock(companion);
        // Vortex consumes the current true range, so its MTATR must run first.
        blocks = extra == null ? new NativeBlock[]{primaryBlock}
                : new NativeBlock[]{extra, primaryBlock};
        main = primaryBlock.series(mainName);
        auxiliary = mode == 14 ? extra.series("Value")
                : auxiliaryName == null ? null : primaryBlock.series(auxiliaryName);
    }

    private static int integerParameter(double[] parameters, int index, int fallback) {
        if (parameters.length <= index) return fallback;
        double value = parameters[index];
        if (value != Math.rint(value) || value < 2 || value > 60)
            throw new IllegalArgumentException("Invalid closed-bar indicator parameter");
        return (int) value;
    }

    private UlcerIndex ulcer(int direction) {
        UlcerIndex indicator = new UlcerIndex() {
            @Override public int getCurrentBar() { return CurrentBar; }
        };
        indicator.Input = chart;
        indicator.Period = 24;
        indicator.Mode = direction;
        return indicator;
    }

    void onBar(long endNs, double high, double low, double close) throws TradingException {
        if (endNs <= latest.endNs() || !Double.isFinite(high) || !Double.isFinite(low)
                || !Double.isFinite(close) || low > close || high < close) {
            throw new IllegalArgumentException("Expected chronologically increasing completed HLC bars");
        }
        chart.High.add(high);
        chart.Low.add(low);
        chart.Close.add(close);
        for (NativeBlock block : blocks) {
            block.step(bars);
        }
        bars++;
        double value = Double.NaN;
        double aux = Double.NaN;
        if (bars >= minimumBars) {
            value = finite(main.get(0));
            if (auxiliary != null) {
                aux = finite(auxiliary.get(0));
            } else if (primaryBlock.indicator instanceof GannHiLo gann) {
                double highAverage = gann.GHHigh.get(0);
                double lowAverage = gann.GHLow.get(0);
                if (highAverage > lowAverage) {
                    aux = value == lowAverage ? 1 : value == highAverage ? -1 : Double.NaN;
                }
            }
        }
        previous = latest;
        latest = new Values(endNs, value, aux);
    }

    Values latest() {
        return latest;
    }

    Values previous() {
        return previous;
    }

    private static double finite(double value) {
        return Double.isFinite(value) ? value : Double.NaN;
    }

    private static final class NativeBlock {
        private static final Field CURRENT_BAR;
        private static final Method ON_BAR_UPDATE;

        static {
            try {
                CURRENT_BAR = IndicatorBase.class.getDeclaredField("CurrentBar");
                ON_BAR_UPDATE = IndicatorBase.class.getDeclaredMethod("OnBarUpdate");
                CURRENT_BAR.setAccessible(true);
                ON_BAR_UPDATE.setAccessible(true);
            } catch (ReflectiveOperationException e) {
                throw new ExceptionInInitializerError(e);
            }
        }

        private final IndicatorBlock indicator;
        private final List<DataSeries> outputs = new ArrayList<>();

        NativeBlock(IndicatorBlock indicator) throws TradingException {
            this.indicator = indicator;
            for (Field field : indicator.getClass().getFields()) {
                if (field.isAnnotationPresent(Output.class) || field.isAnnotationPresent(Buffer.class)) {
                    DataSeries series = new DataSeries(256);
                    try {
                        field.set(indicator, series);
                    } catch (IllegalAccessException e) {
                        throw new IllegalStateException("Cannot attach SQX indicator series " + field, e);
                    }
                    outputs.add(series);
                }
            }
            indicator.callOnInit();
        }

        DataSeries series(String name) {
            try {
                return (DataSeries) indicator.getClass().getField(name).get(indicator);
            } catch (ReflectiveOperationException e) {
                throw new IllegalStateException("SQX indicator output missing: " + name, e);
            }
        }

        void step(int index) throws TradingException {
            for (DataSeries series : outputs) {
                series.add(0.0);
            }
            // Drive the native lifecycle using the trade-bar index and its isolated output buffers.
            try {
                CURRENT_BAR.setInt(indicator, index);
                ON_BAR_UPDATE.invoke(indicator);
            } catch (InvocationTargetException e) {
                if (e.getCause() instanceof TradingException tradingException) {
                    throw tradingException;
                }
                throw new IllegalStateException("SQX indicator failed at bar " + index, e.getCause());
            } catch (IllegalAccessException e) {
                throw new IllegalStateException("Cannot advance native SQX indicator", e);
            }
        }
    }
}
