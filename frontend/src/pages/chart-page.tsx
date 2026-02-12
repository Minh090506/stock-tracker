/** Real-time 1-minute candlestick chart page for VN30F1M / VN30 stocks.
 *
 * Shows: candlestick (1m) + volume buy/sell + VN30 index overlay + basis spread.
 * Data persists after market close via TimescaleDB continuous aggregates.
 */

import { useState, useEffect } from "react";
import { useCandleData } from "../hooks/use-candle-data";
import { CandlestickChart } from "../components/charts/candlestick-chart";
import { apiFetch } from "../utils/api-client";

/** Default symbol shown on load */
const DEFAULT_SYMBOL = "VN30F2503";

export default function ChartPage() {
  const [symbol, setSymbol] = useState(DEFAULT_SYMBOL);
  const [vn30Symbols, setVn30Symbols] = useState<string[]>([]);

  // Fetch VN30 component list for symbol selector
  useEffect(() => {
    apiFetch<{ symbols: string[] }>("/vn30-components")
      .then((res) => setVn30Symbols(res.symbols))
      .catch(() => {});
  }, []);

  const { candles, volumes, indexCandles, basisPoints, loading, error } =
    useCandleData(symbol, "VN30");

  return (
    <div className="p-4 md:p-6 space-y-4">
      {/* Header with symbol selector */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-white">{symbol}</h2>
          <p className="text-xs text-gray-500">1-minute candles</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {/* Quick-select chips for key symbols */}
          {[DEFAULT_SYMBOL, "VN30"].map((s) => (
            <button
              key={s}
              onClick={() => setSymbol(s)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                symbol === s
                  ? "bg-gray-700 text-white"
                  : "bg-gray-800/50 text-gray-400 hover:text-white hover:bg-gray-800"
              }`}
            >
              {s}
            </button>
          ))}
          {/* Dropdown for VN30 stocks */}
          <select
            value={vn30Symbols.includes(symbol) ? symbol : ""}
            onChange={(e) => e.target.value && setSymbol(e.target.value)}
            className="bg-gray-800 text-gray-300 text-xs rounded-md px-2 py-1.5 border border-gray-700 focus:outline-none focus:border-gray-500"
          >
            <option value="">VN30 stocks...</option>
            {vn30Symbols.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-gray-500">
        <span className="flex items-center gap-1">
          <span className="w-3 h-0.5 bg-yellow-400 inline-block" /> VN30 Index
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-2 bg-red-500/50 inline-block rounded-sm" /> Buy Vol
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-2 bg-green-500/50 inline-block rounded-sm" /> Sell Vol
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-2 bg-red-500/30 inline-block rounded-sm" /> Basis +
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-2 bg-green-500/30 inline-block rounded-sm" /> Basis -
        </span>
      </div>

      {/* Chart */}
      {loading ? (
        <div className="bg-gray-900 border border-gray-800 rounded-lg h-[500px] flex items-center justify-center">
          <div className="text-gray-500 text-sm">Loading chart data...</div>
        </div>
      ) : error ? (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <p className="text-red-400 text-sm">
            Failed to load chart: {error.message}
          </p>
        </div>
      ) : candles.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 rounded-lg h-[500px] flex items-center justify-center">
          <div className="text-center">
            <p className="text-gray-500 text-sm">No candle data for {symbol} today</p>
            <p className="text-gray-600 text-xs mt-1">
              Data will appear during market hours (9:00 - 15:00)
            </p>
          </div>
        </div>
      ) : (
        <CandlestickChart
          candles={candles}
          volumes={volumes}
          indexCandles={symbol.startsWith("VN30F") ? indexCandles : []}
          basisPoints={symbol.startsWith("VN30F") ? basisPoints : []}
          height={500}
        />
      )}

      {/* Info footer */}
      <div className="text-xs text-gray-600 flex items-center justify-between">
        <span>
          {candles.length} candles loaded
          {volumes.length > 0 && ` | ${volumes.length} volume bars`}
        </span>
        <span>Data: TimescaleDB continuous aggregate (1m refresh)</span>
      </div>
    </div>
  );
}
