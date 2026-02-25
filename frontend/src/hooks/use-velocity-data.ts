/** Combines real-time velocity snapshot (WS) with polled history. */

import { useWebSocket } from "./use-websocket";
import { usePolling } from "./use-polling";
import { apiFetch } from "../utils/api-client";
import type { MarketSnapshot, VelocitySnapshot, VelocityHistoryPoint } from "../types";

interface VelocityPageData {
  velocity: VelocitySnapshot | null;
  history: VelocityHistoryPoint[];
  loading: boolean;
  error: Error | null;
}

export function useVelocityData(
  /** Active VN30F contract symbol for history query (KRX or legacy format) */
  futuresSymbol = "",
  historyMinutes = 60,
  historyPollMs = 10_000,
): VelocityPageData {
  const ws = useWebSocket<MarketSnapshot>("market", {
    fallbackFetcher: () => apiFetch<MarketSnapshot>("/market/snapshot"),
    fallbackIntervalMs: 5000,
  });

  // Use active contract from snapshot if caller didn't provide one
  const symbol = futuresSymbol || ws.data?.derivatives?.symbol || "";

  const history = usePolling(
    symbol
      ? () => apiFetch<VelocityHistoryPoint[]>(
          `/market/velocity/history?symbol=${symbol}&minutes=${historyMinutes}`
        )
      : () => Promise.resolve([]),
    historyPollMs,
  );

  return {
    velocity: ws.data?.velocity ?? null,
    history: history.data ?? [],
    loading: !ws.data && !history.data && history.loading,
    error: ws.error ?? history.error,
  };
}
