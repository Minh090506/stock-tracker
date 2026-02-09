/** Hook for price board: WS market data + sparkline accumulation + VN30 filtering. */

import { useState, useEffect, useRef, useMemo } from "react";
import { useWebSocket } from "./use-websocket";
import { apiFetch } from "../utils/api-client";
import type { MarketSnapshot, PriceData, SessionStats } from "../types";

export interface PriceBoardRow {
  symbol: string;
  price: PriceData;
  stats: SessionStats | null;
  sparkline: number[];
}

const MAX_SPARKLINE_POINTS = 50;

const EMPTY_PRICE: PriceData = {
  last_price: 0, change: 0, change_pct: 0,
  ref_price: 0, ceiling: 0, floor: 0,
};

export function usePriceBoardData() {
  const [vn30Symbols, setVn30Symbols] = useState<string[]>([]);

  // Fetch VN30 component list once
  useEffect(() => {
    apiFetch<{ symbols: string[] }>("/vn30-components")
      .then((res) => setVn30Symbols(res.symbols))
      .catch(() => {});
  }, []);

  // WebSocket with REST fallback
  const { data: snapshot, status, error, isLive, reconnect } =
    useWebSocket<MarketSnapshot>("market", {
      fallbackFetcher: () => apiFetch<MarketSnapshot>("/market/snapshot"),
      fallbackIntervalMs: 3000,
    });

  // Sparkline accumulation (persisted across renders via ref)
  const sparklineRef = useRef<Record<string, number[]>>({});

  // Update sparklines when snapshot changes
  useEffect(() => {
    if (!snapshot?.prices) return;
    for (const [symbol, pd] of Object.entries(snapshot.prices)) {
      if (pd.last_price === 0) continue;
      const arr = sparklineRef.current[symbol] ?? [];
      // Only push if price differs from last point (dedup flat updates)
      if (arr.length === 0 || arr[arr.length - 1] !== pd.last_price) {
        arr.push(pd.last_price);
        if (arr.length > MAX_SPARKLINE_POINTS) arr.shift();
        sparklineRef.current[symbol] = arr;
      }
    }
  }, [snapshot]);

  // Build rows filtered to VN30
  const rows: PriceBoardRow[] = useMemo(() => {
    if (!snapshot || vn30Symbols.length === 0) return [];
    return vn30Symbols
      .map((symbol) => ({
        symbol,
        price: snapshot.prices?.[symbol] ?? EMPTY_PRICE,
        stats: snapshot.quotes?.[symbol] ?? null,
        sparkline: sparklineRef.current[symbol] ?? [],
      }))
      .filter((r) => r.price.last_price > 0);
  }, [snapshot, vn30Symbols]);

  const loading = status === "connecting" && !snapshot;

  return { rows, loading, error, isLive, status, reconnect };
}
