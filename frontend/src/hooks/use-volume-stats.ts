/** Polls /api/market/volume-stats for per-symbol session breakdown. */

import { usePolling } from "./use-polling";
import { apiFetch } from "../utils/api-client";
import type { VolumeStatsResponse } from "../types";

export function useVolumeStats(intervalMs = 5000) {
  return usePolling(
    () => apiFetch<VolumeStatsResponse>("/market/volume-stats"),
    intervalMs,
  );
}
