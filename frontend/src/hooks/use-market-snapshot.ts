/** Polls /api/market/snapshot for unified market data. */

import { usePolling } from "./use-polling";
import { apiFetch } from "../utils/api-client";
import type { MarketSnapshot } from "../types";

export function useMarketSnapshot(intervalMs = 5000) {
  return usePolling(
    () => apiFetch<MarketSnapshot>("/market/snapshot"),
    intervalMs,
  );
}
