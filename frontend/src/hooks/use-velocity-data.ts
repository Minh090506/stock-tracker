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
  historyMinutes = 60,
  historyPollMs = 10_000,
): VelocityPageData {
  const ws = useWebSocket<MarketSnapshot>("market", {
    fallbackFetcher: () => apiFetch<MarketSnapshot>("/market/snapshot"),
    fallbackIntervalMs: 5000,
  });

  const history = usePolling(
    () => apiFetch<VelocityHistoryPoint[]>(
      `/market/velocity/history?symbol=VN30F&minutes=${historyMinutes}`
    ),
    historyPollMs,
  );

  return {
    velocity: ws.data?.velocity ?? null,
    history: history.data ?? [],
    loading: !ws.data && !history.data && history.loading,
    error: ws.error ?? history.error,
  };
}
