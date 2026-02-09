/** Combines real-time derivatives snapshot (WS) with polled basis trend. */

import { useWebSocket } from "./use-websocket";
import { usePolling } from "./use-polling";
import { apiFetch } from "../utils/api-client";
import type { MarketSnapshot, BasisPoint, DerivativesData } from "../types";

interface DerivativesPageData {
  derivatives: DerivativesData | null;
  basisTrend: BasisPoint[];
  loading: boolean;
  error: Error | null;
}

export function useDerivativesData(
  trendMinutes = 30,
  trendPollMs = 10_000,
): DerivativesPageData {
  // Real-time derivatives from existing WS market channel
  const ws = useWebSocket<MarketSnapshot>("market", {
    fallbackFetcher: () => apiFetch<MarketSnapshot>("/market/snapshot"),
    fallbackIntervalMs: 5000,
  });

  // Basis trend from new REST endpoint
  const trend = usePolling(
    () => apiFetch<BasisPoint[]>(`/market/basis-trend?minutes=${trendMinutes}`),
    trendPollMs,
  );

  return {
    derivatives: ws.data?.derivatives ?? null,
    basisTrend: trend.data ?? [],
    loading: !ws.data && !trend.data && trend.loading,
    error: ws.error ?? trend.error,
  };
}
