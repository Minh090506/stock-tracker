/** Lightweight-charts candlestick chart with volume + basis overlay.
 *
 * Renders a TradingView-style chart with:
 * - Candlestick series (VN30F1M or stock)
 * - Line series overlay (VN30 index)
 * - Volume histogram (active buy = red, active sell = green, VN convention)
 * - Basis spread area (futures - spot)
 */

import { useEffect, useRef } from "react";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
  ColorType,
  CrosshairMode,
  LineStyle,
} from "lightweight-charts";
import type { LWCandle, LWBuySellVolume } from "../../hooks/use-candle-data";

// VN market: red=up/buy, green=down/sell
const UP_COLOR = "#ef4444";       // red-500
const DOWN_COLOR = "#22c55e";     // green-500
const BUY_VOL_COLOR = "rgba(239, 68, 68, 0.5)";
const SELL_VOL_COLOR = "rgba(34, 197, 94, 0.5)";
const INDEX_LINE_COLOR = "#facc15"; // yellow-400
const BASIS_POS_COLOR = "rgba(239, 68, 68, 0.3)";  // premium (red)
const BASIS_NEG_COLOR = "rgba(34, 197, 94, 0.3)";   // discount (green)

interface CandlestickChartProps {
  candles: LWCandle[];
  volumes: LWBuySellVolume[];
  indexCandles?: LWCandle[];
  basisPoints?: { time: number; value: number }[];
  height?: number;
}

export function CandlestickChart({
  candles,
  volumes,
  indexCandles = [],
  basisPoints = [],
  height = 500,
}: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const buyVolSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const sellVolSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const indexSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const basisSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  // Create chart once
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#111827" }, // gray-900
        textColor: "#9ca3af", // gray-400
      },
      grid: {
        vertLines: { color: "#1f2937" },  // gray-800
        horzLines: { color: "#1f2937" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#374151" },
      timeScale: {
        borderColor: "#374151",
        timeVisible: true,
        secondsVisible: false,
      },
      width: containerRef.current.clientWidth,
      height,
    });

    // Candlestick series (main pane)
    const candleSeries = chart.addCandlestickSeries({
      upColor: UP_COLOR,
      downColor: DOWN_COLOR,
      borderUpColor: UP_COLOR,
      borderDownColor: DOWN_COLOR,
      wickUpColor: UP_COLOR,
      wickDownColor: DOWN_COLOR,
    });

    // Buy volume histogram (lower pane via priceScaleId)
    const buyVolSeries = chart.addHistogramSeries({
      color: BUY_VOL_COLOR,
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });
    buyVolSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    // Sell volume as negative (overlaid on buy)
    const sellVolSeries = chart.addHistogramSeries({
      color: SELL_VOL_COLOR,
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });

    // VN30 index line overlay (right price scale, separate)
    const indexSeries = chart.addLineSeries({
      color: INDEX_LINE_COLOR,
      lineWidth: 1,
      lineStyle: LineStyle.Solid,
      priceScaleId: "idx",
      lastValueVisible: true,
      priceLineVisible: false,
    });
    indexSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.05, bottom: 0.25 },
    });

    // Basis spread histogram
    const basisSeries = chart.addHistogramSeries({
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
      priceScaleId: "basis",
    });
    basisSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    buyVolSeriesRef.current = buyVolSeries;
    sellVolSeriesRef.current = sellVolSeries;
    indexSeriesRef.current = indexSeries;
    basisSeriesRef.current = basisSeries;

    // Responsive resize
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) chart.applyOptions({ width: entry.contentRect.width });
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [height]);

  // Update candle data
  useEffect(() => {
    if (!candleSeriesRef.current || candles.length === 0) return;
    candleSeriesRef.current.setData(
      candles.map((c) => ({
        time: c.time as UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    );
  }, [candles]);

  // Update volume data
  useEffect(() => {
    if (!buyVolSeriesRef.current || !sellVolSeriesRef.current) return;
    buyVolSeriesRef.current.setData(
      volumes.map((v) => ({
        time: v.time as UTCTimestamp,
        value: v.buyVol,
        color: BUY_VOL_COLOR,
      })),
    );
    sellVolSeriesRef.current.setData(
      volumes.map((v) => ({
        time: v.time as UTCTimestamp,
        value: v.sellVol,
        color: SELL_VOL_COLOR,
      })),
    );
  }, [volumes]);

  // Update index overlay
  useEffect(() => {
    if (!indexSeriesRef.current) return;
    if (indexCandles.length === 0) {
      indexSeriesRef.current.setData([]);
      return;
    }
    indexSeriesRef.current.setData(
      indexCandles.map((c) => ({
        time: c.time as UTCTimestamp,
        value: c.close,
      })),
    );
  }, [indexCandles]);

  // Update basis spread
  useEffect(() => {
    if (!basisSeriesRef.current) return;
    if (basisPoints.length === 0) {
      basisSeriesRef.current.setData([]);
      return;
    }
    basisSeriesRef.current.setData(
      basisPoints.map((p) => ({
        time: p.time as UTCTimestamp,
        value: p.value,
        color: p.value >= 0 ? BASIS_POS_COLOR : BASIS_NEG_COLOR,
      })),
    );
  }, [basisPoints]);

  return (
    <div
      ref={containerRef}
      className="w-full rounded-lg overflow-hidden border border-gray-800"
    />
  );
}
