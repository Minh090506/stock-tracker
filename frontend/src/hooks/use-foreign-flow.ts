/** Hybrid hook: WS for real-time ForeignSummary + REST polling for per-symbol detail.
 *  Accumulates total_net_value over time for intraday cumulative flow chart. */

import { useEffect, useRef, useMemo } from "react";
import { useWebSocket } from "./use-websocket";
import { usePolling } from "./use-polling";
import { apiFetch } from "../utils/api-client";
import type {
  ForeignSummary,
  ForeignDetailResponse,
  ForeignInvestorData,
} from "../types";

export interface FlowPoint {
  timestamp: string; // ISO string for chart X-axis
  net_value: number; // cumulative total_net_value at this point
}

export interface ForeignFlowData {
  summary: ForeignSummary | null;
  stocks: ForeignInvestorData[];
  flowHistory: FlowPoint[];
  loading: boolean;
  error: Error | null;
  isLive: boolean;
  status: string;
  reconnect: () => void;
}

const MAX_FLOW_POINTS = 300; // ~5 hours at 1 update/min
const DETAIL_POLL_INTERVAL = 10_000;

export function useForeignFlow(): ForeignFlowData {
  // Real-time summary via WebSocket
  const {
    data: wsSummary,
    status,
    error: wsError,
    isLive,
    reconnect,
  } = useWebSocket<ForeignSummary>("foreign", {
    fallbackFetcher: () =>
      apiFetch<ForeignDetailResponse>("/market/foreign-detail").then(
        (r) => r.summary,
      ),
    fallbackIntervalMs: 5000,
  });

  // Per-symbol detail via REST polling (10s)
  const {
    data: detailData,
    loading: detailLoading,
    error: detailError,
  } = usePolling(
    () => apiFetch<ForeignDetailResponse>("/market/foreign-detail"),
    DETAIL_POLL_INTERVAL,
  );

  // Accumulate flow history from WS summary updates
  const flowHistoryRef = useRef<FlowPoint[]>([]);
  const lastNetValueRef = useRef<number | null>(null);
  const sessionDateRef = useRef<string | null>(null);

  useEffect(() => {
    if (!wsSummary) return;

    // Reset history on new trading day
    const today = new Date().toISOString().split("T")[0] ?? "";
    if (sessionDateRef.current !== today) {
      sessionDateRef.current = today;
      flowHistoryRef.current = [];
      lastNetValueRef.current = null;
    }

    const netVal = wsSummary.total_net_value;
    // Only push if value changed (dedup flat updates)
    if (lastNetValueRef.current === netVal) return;
    lastNetValueRef.current = netVal;

    const point: FlowPoint = {
      timestamp: new Date().toISOString(),
      net_value: netVal,
    };
    flowHistoryRef.current = [
      ...flowHistoryRef.current.slice(-(MAX_FLOW_POINTS - 1)),
      point,
    ];
  }, [wsSummary]);

  // Prefer WS summary; fall back to detail response summary
  const summary = wsSummary ?? detailData?.summary ?? null;
  const stocks = detailData?.stocks ?? [];
  const loading = !summary && status === "connecting" && detailLoading;
  const error = wsError ?? detailError ?? null;

  const flowHistory = useMemo(
    () => [...flowHistoryRef.current],
    [wsSummary], // re-snapshot when WS pushes new data
  );

  return { summary, stocks, flowHistory, loading, error, isLive, status, reconnect };
}
