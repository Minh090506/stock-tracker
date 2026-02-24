/** Hook for backtest data — pre-computed summary + on-demand custom analysis. */

import { useState, useCallback } from "react";
import { usePolling } from "./use-polling";
import { apiFetch } from "../utils/api-client";
import type {
  BacktestSummary,
  CrossCorrelationReport,
  ThresholdReport,
  PatternReport,
} from "../types";

interface OnDemandResult {
  correlation: CrossCorrelationReport | null;
  threshold: ThresholdReport | null;
  patterns: PatternReport | null;
}

interface BacktestPageData {
  summary: BacktestSummary | null;
  custom: OnDemandResult;
  loading: boolean;
  analyzing: boolean;
  error: Error | null;
  analysisError: Error | null;
  runAnalysis: (symbol: string, days: number, lookahead: number) => Promise<void>;
}

/** Fetch summary, treating 404 as null (not yet computed). */
async function fetchSummary(): Promise<BacktestSummary | null> {
  try {
    return await apiFetch<BacktestSummary>("/backtest/summary");
  } catch (err) {
    if (err instanceof Error && err.message.startsWith("API 404")) return null;
    throw err;
  }
}

export function useBacktestData(): BacktestPageData {
  const poll = usePolling(fetchSummary, 60_000);
  const [custom, setCustom] = useState<OnDemandResult>({
    correlation: null,
    threshold: null,
    patterns: null,
  });
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<Error | null>(null);

  const runAnalysis = useCallback(
    async (symbol: string, days: number, lookahead: number) => {
      setAnalyzing(true);
      setAnalysisError(null);
      try {
        const [correlation, threshold, patterns] = await Promise.all([
          apiFetch<CrossCorrelationReport>(
            `/backtest/correlation?symbol=${symbol}&days=${days}&max_lag=10`,
          ),
          apiFetch<ThresholdReport>(
            `/backtest/threshold?symbol=${symbol}&days=${days}&lookahead=${lookahead}&bins=5`,
          ),
          apiFetch<PatternReport>(
            `/backtest/patterns?symbol=${symbol}&days=${days}`,
          ),
        ]);
        setCustom({ correlation, threshold, patterns });
      } catch (err) {
        setAnalysisError(
          err instanceof Error ? err : new Error(String(err)),
        );
      } finally {
        setAnalyzing(false);
      }
    },
    [],
  );

  return {
    summary: poll.data ?? null,
    custom,
    loading: poll.loading,
    analyzing,
    error: poll.error,
    analysisError,
    runAnalysis,
  };
}
