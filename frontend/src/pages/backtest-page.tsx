/** Backtest analysis dashboard — correlation heatmap, threshold table, patterns. */

import { useState } from "react";
import { useBacktestData } from "../hooks/use-backtest-data";
import { BacktestSkeleton } from "../components/ui/backtest-skeleton";
import { ErrorBanner } from "../components/ui/error-banner";
import { BacktestControls } from "../components/backtest/backtest-controls";
import { BacktestSummaryCards } from "../components/backtest/backtest-summary-cards";
import { BacktestCorrelationChart } from "../components/backtest/backtest-correlation-chart";
import { BacktestThresholdTable } from "../components/backtest/backtest-threshold-table";
import { BacktestPatternChart } from "../components/backtest/backtest-pattern-chart";

export default function BacktestPage() {
  const { summary, custom, loading, analyzing, error, analysisError, runAnalysis } =
    useBacktestData();

  const [symbol, setSymbol] = useState("VN30F2603");
  const [days, setDays] = useState(20);
  const [lookahead, setLookahead] = useState(5);

  if (loading) return <BacktestSkeleton />;

  if (error && !summary) {
    return (
      <ErrorBanner message={`Failed to load backtest data: ${error.message}`} />
    );
  }

  // Use custom results if available, otherwise fall back to pre-computed summary
  const corrData = custom.correlation ?? summary?.cross_correlation ?? null;
  const threshData = custom.threshold ?? summary?.threshold ?? null;
  const patternData = custom.patterns ?? summary?.patterns ?? null;

  return (
    <div className="p-6 space-y-6">
      <BacktestControls
        symbol={symbol}
        days={days}
        lookahead={lookahead}
        analyzing={analyzing}
        onSymbolChange={setSymbol}
        onDaysChange={setDays}
        onLookaheadChange={setLookahead}
        onRun={() => runAnalysis(symbol, days, lookahead)}
      />

      <BacktestSummaryCards data={summary} />

      {analysisError && (
        <ErrorBanner message={`Analysis error: ${analysisError.message}`} />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <BacktestCorrelationChart data={corrData} />
        <BacktestPatternChart data={patternData} />
      </div>

      <BacktestThresholdTable data={threshData} />
    </div>
  );
}
