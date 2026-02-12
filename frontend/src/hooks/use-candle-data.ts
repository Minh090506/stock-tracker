/** Hook for 1-minute candle data — REST historical + real-time WS updates. */

import { useState, useEffect, useRef, useCallback } from "react";
import { useWebSocket } from "./use-websocket";
import { apiFetch } from "../utils/api-client";
import type { CandleData, IndexCandleData, MarketSnapshot } from "../types";

/** Lightweight-charts compatible candle format (UTC seconds) */
export interface LWCandle {
  time: number; // unix seconds
  open: number;
  high: number;
  low: number;
  close: number;
}

/** Active buy/sell volume bar pair for stacked display */
export interface LWBuySellVolume {
  time: number;
  buyVol: number;
  sellVol: number;
}

function todayStr(): string {
  const d = new Date();
  return d.toISOString().slice(0, 10); // YYYY-MM-DD
}

function toUnixSec(ts: string): number {
  return Math.floor(new Date(ts).getTime() / 1000);
}

/** Convert API candle to lightweight-charts format */
function toLC(c: CandleData | IndexCandleData): LWCandle {
  return {
    time: toUnixSec(c.timestamp),
    open: c.open,
    high: c.high,
    low: c.low,
    close: c.close,
  };
}

export interface CandleChartData {
  /** 1m candles for the selected symbol */
  candles: LWCandle[];
  /** Volume with buy/sell breakdown */
  volumes: LWBuySellVolume[];
  /** Index candles (VN30 line overlay) */
  indexCandles: LWCandle[];
  /** Basis spread points (futures - spot) */
  basisPoints: { time: number; value: number }[];
  /** True while initial data is loading */
  loading: boolean;
  error: Error | null;
  /** Refresh from REST */
  refresh: () => void;
}

export function useCandleData(
  symbol: string,
  indexName = "VN30",
): CandleChartData {
  const [candles, setCandles] = useState<LWCandle[]>([]);
  const [volumes, setVolumes] = useState<LWBuySellVolume[]>([]);
  const [indexCandles, setIndexCandles] = useState<LWCandle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  // Track current live candle being built from WS
  const liveCandle = useRef<LWCandle | null>(null);
  const liveBuySell = useRef<LWBuySellVolume | null>(null);

  // Fetch historical candles from REST
  const fetchCandles = useCallback(async () => {
    const today = todayStr();
    try {
      const [symbolData, indexData] = await Promise.all([
        apiFetch<CandleData[]>(
          `/history/${symbol}/candles?start=${today}&end=${today}`,
        ),
        apiFetch<IndexCandleData[]>(
          `/history/index/${indexName}/candles?start=${today}&end=${today}`,
        ),
      ]);

      setCandles(symbolData.map(toLC));
      setVolumes(
        symbolData.map((c) => ({
          time: toUnixSec(c.timestamp),
          buyVol: c.active_buy_vol,
          sellVol: c.active_sell_vol,
        })),
      );
      setIndexCandles(indexData.map(toLC));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, [symbol, indexName]);

  // Initial fetch + periodic refresh every 60s
  useEffect(() => {
    fetchCandles();
    const id = setInterval(fetchCandles, 60_000);
    return () => clearInterval(id);
  }, [fetchCandles]);

  // Subscribe to WS for real-time price to build current candle
  const { data: snapshot } = useWebSocket<MarketSnapshot>("market", {
    fallbackFetcher: () => apiFetch<MarketSnapshot>("/market/snapshot"),
    fallbackIntervalMs: 5000,
  });

  // Update live candle from WS snapshot
  useEffect(() => {
    if (!snapshot) return;

    // Get price for selected symbol (could be stock or futures)
    const priceData = snapshot.prices?.[symbol];
    const derivData = snapshot.derivatives;
    const price = priceData?.last_price ?? derivData?.last_price ?? 0;
    if (price <= 0) return;

    const nowSec = Math.floor(Date.now() / 1000);
    const minuteBucket = Math.floor(nowSec / 60) * 60;

    const current = liveCandle.current;
    if (!current || current.time !== minuteBucket) {
      // New minute — start fresh candle
      liveCandle.current = {
        time: minuteBucket,
        open: price,
        high: price,
        low: price,
        close: price,
      };
      liveBuySell.current = {
        time: minuteBucket,
        buyVol: 0,
        sellVol: 0,
      };
    } else {
      // Update existing candle
      current.high = Math.max(current.high, price);
      current.low = Math.min(current.low, price);
      current.close = price;
    }

    // Merge live candle into candles array (replace last if same minute, else append)
    setCandles((prev) => {
      const live = liveCandle.current;
      if (!live) return prev;
      const last = prev[prev.length - 1];
      if (last && last.time === live.time) {
        return [...prev.slice(0, -1), { ...live }];
      }
      return [...prev, { ...live }];
    });
  }, [snapshot, symbol]);

  // Compute basis points from candles + index candles
  const basisPoints = (() => {
    if (candles.length === 0 || indexCandles.length === 0) return [];
    // Build time→value map for index
    const indexMap = new Map(indexCandles.map((c) => [c.time, c.close]));
    return candles
      .filter((c) => indexMap.has(c.time))
      .map((c) => ({
        time: c.time,
        value: c.close - (indexMap.get(c.time) ?? 0),
      }));
  })();

  return {
    candles,
    volumes,
    indexCandles,
    basisPoints,
    loading,
    error,
    refresh: fetchCandles,
  };
}
