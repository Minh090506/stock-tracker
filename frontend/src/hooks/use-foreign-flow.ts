/** Polls /api/market/foreign-detail for per-symbol foreign investor data. */

import { usePolling } from "./use-polling";
import { apiFetch } from "../utils/api-client";
import type { ForeignDetailResponse } from "../types";

export function useForeignFlow(intervalMs = 5000) {
  return usePolling(
    () => apiFetch<ForeignDetailResponse>("/market/foreign-detail"),
    intervalMs,
  );
}
