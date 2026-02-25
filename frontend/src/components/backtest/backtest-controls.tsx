/** Controls bar: symbol selector, days dropdown, lookahead, run button. */

import { useMemo } from "react";
import { formatKrxLabel } from "../../utils/futures-format-utils";

interface BacktestControlsProps {
  symbol: string;
  days: number;
  lookahead: number;
  analyzing: boolean;
  /** Active VN30F contracts from /api/market/futures-contracts */
  futuresContracts: string[];
  onSymbolChange: (v: string) => void;
  onDaysChange: (v: number) => void;
  onLookaheadChange: (v: number) => void;
  onRun: () => void;
}

const DAYS_OPTIONS = [5, 10, 20, 30];
const LOOKAHEAD_OPTIONS = [1, 3, 5, 10];

export function BacktestControls({
  symbol,
  days,
  lookahead,
  analyzing,
  futuresContracts,
  onSymbolChange,
  onDaysChange,
  onLookaheadChange,
  onRun,
}: BacktestControlsProps) {
  // Build symbol options dynamically from active contracts
  const symbolOptions = useMemo(() => {
    const opts = futuresContracts.map((c) => ({ value: c, label: formatKrxLabel(c) }));
    opts.push({ value: "VN30", label: "VN30 Basket (Ro co so)" });
    return opts;
  }, [futuresContracts]);

  const selectClass =
    "bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500";

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="flex flex-wrap items-center gap-3">
        {/* Symbol */}
        <select
          value={symbol}
          onChange={(e) => onSymbolChange(e.target.value)}
          className={selectClass}
        >
          {symbolOptions.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>

        {/* Days */}
        <select
          value={days}
          onChange={(e) => onDaysChange(Number(e.target.value))}
          className={selectClass}
        >
          {DAYS_OPTIONS.map((d) => (
            <option key={d} value={d}>
              {d} ngay
            </option>
          ))}
        </select>

        {/* Lookahead */}
        <select
          value={lookahead}
          onChange={(e) => onLookaheadChange(Number(e.target.value))}
          className={selectClass}
        >
          {LOOKAHEAD_OPTIONS.map((l) => (
            <option key={l} value={l}>
              Lookahead {l} phut
            </option>
          ))}
        </select>

        {/* Run button */}
        <button
          onClick={onRun}
          disabled={analyzing}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-md transition-colors"
        >
          {analyzing ? "Dang phan tich..." : "Chay Phan Tich"}
        </button>
      </div>

      <p className="text-xs text-gray-600 mt-2">
        Tuong quan ≠ nhan qua. Ket qua chi mang tinh tham khao.
      </p>
    </div>
  );
}
